"""
Парсер мессенджера MAX: получение сообщений через REST API (Long Polling).
Работает в отдельном потоке внутри того же процесса, что и backend.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select

from database import db_session
from models import Chat, ExclusionWord, Keyword, Mention, User, user_chat_subscriptions
import mention_notifications
from parser_log import append as log_append, append_exception as log_exception
from plans import can_track, get_effective_plan
from parser_config import (
    get_parser_setting_int,
    get_parser_setting_str,
)
from models import CHAT_SOURCE_MAX

try:
    import requests
except ImportError:
    requests = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _initials(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return "??"
    parts = [p for p in v.split() if p]
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][:1] + parts[1][:1]).upper()


def _humanize_ru(dt: datetime) -> str:
    now = _now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = max(0, int((now - dt).total_seconds()))
    if diff < 10:
        return "только что"
    if diff < 60:
        return f"{diff} сек назад"
    minutes = diff // 60
    if minutes < 60:
        return f"{minutes} мин назад"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч назад"
    days = hours // 24
    return f"{days} дн назад"


@dataclass(frozen=True)
class KeywordItem:
    text: str
    use_semantic: bool
    exclusion_words: tuple[str, ...] = ()


def _load_keywords_multi() -> dict[int, list[KeywordItem]]:
    """Ключевые слова по user_id (только включённые, пользователи с правом трекинга), с их словами-исключениями."""
    with db_session() as db:
        users = db.scalars(select(User)).all()
        allowed_user_ids = {u.id for u in users if can_track(get_effective_plan(u), db)}
        rows = db.scalars(
            select(Keyword)
            .where(Keyword.enabled.is_(True))
            .order_by(Keyword.user_id, Keyword.id.asc())
        ).all()
        if not rows:
            return {}
        kw_ids = [r.id for r in rows]
        excl_rows = db.scalars(select(ExclusionWord).where(ExclusionWord.keyword_id.in_(kw_ids))).all()
        excl_by_kw: dict[int, list[str]] = {}
        for e in excl_rows:
            t = (e.text or "").strip()
            if t:
                excl_by_kw.setdefault(e.keyword_id, []).append(t)
        out: dict[int, list[KeywordItem]] = {}
        for r in rows:
            if r.user_id not in allowed_user_ids:
                continue
            t = (r.text or "").strip()
            if t:
                use_sem = getattr(r, "use_semantic", False)
                out.setdefault(r.user_id, []).append(
                    KeywordItem(
                        text=t,
                        use_semantic=use_sem,
                        exclusion_words=tuple(excl_by_kw.get(r.id, [])),
                    )
                )
        return out


def _match_keywords_exact(items: list[KeywordItem], text: str, text_cf: str) -> list[str]:
    """Совпадения по точному вхождению (семантику для MAX пока не подключаем)."""
    return [kw.text for kw in items if kw.text.casefold() in text_cf]


def _message_has_exclusion(text_cf: str, exclusion_words: list[str]) -> bool:
    """True, если в тексте (casefold) есть хотя бы одно слово-исключение как подстрока."""
    if not text_cf:
        return False
    for e in exclusion_words:
        t = (e or "").strip()
        if t and t.casefold() in text_cf:
            return True
    return False


class MaxScanner:
    """
    Сканер чатов MAX через Long Polling (GET /messages).
    Запускается в отдельном потоке, использует тот же callback on_mention, что и Telegram.
    """

    def __init__(
        self,
        *,
        on_mention: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.on_mention = on_mention
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_message_time_by_chat: dict[str, int] = {}  # max_chat_id -> unix ts последнего сообщения

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_thread, name="MaxScanner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run_thread(self) -> None:
        try:
            log_append("[MAX] Поток парсера MAX запущен.")
            self._run_loop()
        except Exception as e:
            log_exception(e)
        finally:
            log_append("[MAX] Поток парсера MAX завершён.")

    def _run_loop(self) -> None:
        if requests is None:
            log_append("[MAX] Ошибка: не установлен пакет requests. Установите: pip install requests")
            return

        token = get_parser_setting_str("MAX_ACCESS_TOKEN")
        base_url = (get_parser_setting_str("MAX_BASE_URL") or "https://platform-api.max.ru").rstrip("/")
        interval = get_parser_setting_int("MAX_POLL_INTERVAL_SEC", 60)
        interval = max(15, min(600, interval))

        if not token:
            log_append("[MAX] MAX_ACCESS_TOKEN не задан. Парсер MAX не будет запрашивать API.")
            while not self._stop_event.wait(timeout=float(interval)):
                pass
            return

        session = requests.Session()
        session.headers["Authorization"] = token
        session.headers["Content-Type"] = "application/json"

        while not self._stop_event.is_set():
            try:
                self._poll_once(session, base_url)
            except Exception as e:
                log_exception(e)
            self._stop_event.wait(timeout=float(interval))

    def _poll_once(self, session: requests.Session, base_url: str) -> None:
        chats_map = self._load_max_chats()
        if not chats_map:
            return

        keywords_by_user = _load_keywords_multi()
        url = f"{base_url}/messages"

        for max_chat_id, (chat_title, user_ids) in chats_map.items():
            if self._stop_event.is_set():
                break
            user_ids = user_ids & set(keywords_by_user.keys())
            if not user_ids:
                continue

            params: dict[str, Any] = {"chat_id": max_chat_id, "count": 100}
            last_ts = self._last_message_time_by_chat.get(max_chat_id)
            if last_ts is not None:
                params["from"] = last_ts

            try:
                r = session.get(url, params=params, timeout=30)
            except requests.RequestException as e:
                log_append(f"[MAX] Ошибка запроса chat_id={max_chat_id}: {e}")
                continue

            if r.status_code == 401:
                log_append("[MAX] 401 Unauthorized: проверьте MAX_ACCESS_TOKEN.")
                return
            if r.status_code == 403:
                log_append("[MAX] 403 Forbidden: нет доступа к чату или API.")
                continue
            if r.status_code == 429:
                log_append("[MAX] 429 Rate limit. Увеличьте MAX_POLL_INTERVAL_SEC.")
                time.sleep(10)
                continue
            if r.status_code != 200:
                log_append(f"[MAX] HTTP {r.status_code} для chat_id={max_chat_id}")
                continue

            try:
                data = r.json()
            except Exception as e:
                log_append(f"[MAX] Не удалось разобрать JSON: {e}")
                continue

            messages = data.get("messages") or data.get("items") or data.get("data") or []
            if not isinstance(messages, list):
                continue

            newest_ts = last_ts
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                text = (msg.get("text") or msg.get("message") or msg.get("body") or "").strip()
                if not text:
                    continue

                msg_id = msg.get("id")
                date_val = msg.get("date") or msg.get("created_at") or msg.get("timestamp")
                if date_val is not None:
                    try:
                        if isinstance(date_val, (int, float)):
                            ts = int(date_val)
                        else:
                            ts = int(datetime.fromisoformat(str(date_val).replace("Z", "+00:00")).timestamp())
                        if newest_ts is None or ts > newest_ts:
                            newest_ts = ts
                    except (ValueError, TypeError):
                        pass

                from_obj = msg.get("from") or msg.get("sender") or {}
                if not isinstance(from_obj, dict):
                    from_obj = {}
                sender_id = from_obj.get("id")
                sender_name = (from_obj.get("name") or from_obj.get("first_name") or "").strip()
                if not sender_name and from_obj.get("last_name"):
                    sender_name = f"{sender_name} {from_obj.get('last_name')}".strip()
                sender_username = from_obj.get("username")

                text_cf = text.casefold()
                created_at = _now_utc()
                if date_val is not None:
                    try:
                        if isinstance(date_val, (int, float)):
                            created_at = datetime.fromtimestamp(int(date_val), tz=timezone.utc)
                        else:
                            created_at = datetime.fromisoformat(str(date_val).replace("Z", "+00:00"))
                            if created_at.tzinfo is None:
                                created_at = created_at.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                for uid in user_ids:
                    items = keywords_by_user.get(uid, [])
                    exclusion_map = {item.text: list(item.exclusion_words) for item in items}
                    matches = _match_keywords_exact(items, text, text_cf)
                    for kw in matches:
                        if _message_has_exclusion(text_cf, exclusion_map.get(kw, [])):
                            continue
                        with db_session() as db:
                            if msg_id is not None:
                                existing = db.scalar(
                                    select(Mention).where(
                                        Mention.user_id == uid,
                                        Mention.source == CHAT_SOURCE_MAX,
                                        Mention.message_id == int(msg_id),
                                        Mention.keyword_text == kw,
                                    )
                                )
                                if existing:
                                    continue
                            mention = Mention(
                                user_id=uid,
                                source=CHAT_SOURCE_MAX,
                                keyword_text=kw,
                                message_text=text,
                                chat_id=None,
                                chat_name=chat_title,
                                chat_username=None,
                                message_id=int(msg_id) if msg_id is not None else None,
                                sender_id=int(sender_id) if sender_id is not None else None,
                                sender_name=sender_name or None,
                                sender_username=str(sender_username).strip() if sender_username else None,
                                is_read=False,
                                is_lead=False,
                                created_at=created_at,
                            )
                            db.add(mention)
                            db.flush()

                            message_link = None  # Формат ссылки MAX уточнить по документации
                            user_link = None
                            if sender_username and str(sender_username).strip():
                                user_link = f"https://max.ru/@{str(sender_username).strip().lstrip('@')}"
                            elif sender_id is not None:
                                user_link = f"https://max.ru/user/{sender_id}"

                            payload = {
                                "type": "mention",
                                "data": {
                                    "id": str(mention.id),
                                    "userId": uid,
                                    "source": CHAT_SOURCE_MAX,
                                    "groupName": chat_title or max_chat_id,
                                    "groupIcon": _initials(chat_title or max_chat_id),
                                    "userName": sender_name or "Неизвестный пользователь",
                                    "userInitials": _initials(sender_name),
                                    "userLink": user_link,
                                    "message": text,
                                    "keyword": kw,
                                    "timestamp": _humanize_ru(created_at),
                                    "isLead": False,
                                    "isRead": False,
                                    "createdAt": created_at.isoformat(),
                                    "messageLink": message_link,
                                },
                            }
                            mention_id = mention.id
                        if self.on_mention:
                            self.on_mention(payload)
                        mention_notifications.enqueue_mention_notification(mention_id)

            if newest_ts is not None:
                self._last_message_time_by_chat[max_chat_id] = newest_ts

    def _load_max_chats(self) -> dict[str, tuple[str, set[int]]]:
        """
        Возвращает dict: max_chat_id -> (chat_title, set of user_ids).
        Только чаты с source='max', enabled=True.
        """
        with db_session() as db:
            users = db.scalars(select(User)).all()
            allowed = {u.id for u in users if can_track(get_effective_plan(u), db)}
            rows = db.scalars(
                select(Chat).where(
                    Chat.source == CHAT_SOURCE_MAX,
                    Chat.enabled.is_(True),
                    Chat.max_chat_id.isnot(None),
                ).order_by(Chat.id.asc())
            ).all()

            result: dict[str, tuple[str, set[int]]] = {}
            for r in rows:
                mid = (r.max_chat_id or "").strip()
                if not mid:
                    continue
                title = (r.title or r.username or mid).strip()
                user_ids: set[int] = set()
                if r.is_global:
                    sub_ids = db.scalars(
                        select(user_chat_subscriptions.c.user_id).where(
                            user_chat_subscriptions.c.chat_id == r.id
                        )
                    ).all()
                    user_ids = set(sub_ids) & allowed
                else:
                    if r.user_id in allowed:
                        user_ids.add(r.user_id)
                if user_ids:
                    result[mid] = (title, user_ids)
            return result
