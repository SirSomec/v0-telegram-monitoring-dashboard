from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import socks  # PySocks
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ImportChatInviteRequest

from database import db_session
from models import Chat, ExclusionWord, Keyword, Mention, User, user_chat_subscriptions, CHAT_SOURCE_TELEGRAM
import mention_notifications
from parser_log import append as log_append, append_exception as log_exception
from plans import can_track, get_effective_plan
from parser_config import (
    get_parser_setting_str,
    get_parser_setting_bool,
    get_parser_setting_int,
    get_parser_setting,
    get_user_semantic_threshold,
    get_user_semantic_min_topic_percent,
)

try:
    from semantic import embed, cosine_similarity, similarity_threshold, KeywordEmbeddingCache
except ImportError:
    embed = None
    cosine_similarity = None
    similarity_threshold = None
    KeywordEmbeddingCache = None

# Потоки для embed(): не блокируют event loop; 2 воркера снижают очередь при пачке сообщений
_SEMANTIC_EXECUTOR = ThreadPoolExecutor(max_workers=2) if embed else None


def _run_semantic_embed(cache: Any, keyword_texts: list[str], to_embed: list[str]) -> list[list[float]] | None:
    """Синхронная работа для executor: обновить кэш ключей и эмбеддинги текста сообщения."""
    if cache is not None and keyword_texts:
        cache.update(keyword_texts)
    return embed(to_embed) if embed else None


load_dotenv()


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


def _truthy(v: str | None) -> bool:
    return (v or "").strip() in {"1", "true", "True", "yes", "YES", "on", "ON"}


def _message_has_exclusion(text_cf: str, exclusion_words: list[str]) -> bool:
    """True, если в тексте (casefold) есть хотя бы одно слово-исключение как подстрока."""
    if not text_cf:
        return False
    for e in exclusion_words:
        t = (e or "").strip()
        if t and t.casefold() in text_cf:
            return True
    return False


@dataclass(frozen=True)
class KeywordItem:
    """Ключевое слово с флагом режима поиска и своими словами-исключениями."""
    text: str
    use_semantic: bool
    exclusion_words: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProxyConfig:
    host: str
    port: int
    username: str | None = None
    password: str | None = None

    def to_telethon(self) -> tuple:
        # Telethon proxy format: (proxy_type, addr, port, rdns, username, password)
        return (socks.SOCKS5, self.host, self.port, True, self.username, self.password)


def _proxy_from_config() -> ProxyConfig | None:
    host = get_parser_setting_str("TG_PROXY_HOST")
    port = get_parser_setting_str("TG_PROXY_PORT")
    if not host or not port:
        return None
    try:
        p = int(port)
    except ValueError:
        return None
    return ProxyConfig(
        host=host,
        port=p,
        username=get_parser_setting_str("TG_PROXY_USER") or None,
        password=get_parser_setting_str("TG_PROXY_PASS") or None,
    )


def _parse_chat_identifiers(raw: str | None) -> list[str]:
    if not raw:
        return []
    items: list[str] = []
    for part in raw.split(","):
        v = part.strip()
        if not v:
            continue
        items.append(v)
    return items


class TelegramScanner:
    """
    Сканер Telegram на Telethon.
    - Один пользователь (user_id задан): ключевые слова и чаты этого пользователя.
    - Мультипользовательский (user_id=None): ключевые слова и чаты всех пользователей из БД,
      упоминания пишутся с соответствующим user_id, в payload передаётся userId.
    """

    def __init__(
        self,
        *,
        user_id: int | None = None,
        on_mention: Callable[[dict], None] | None = None,
    ) -> None:
        self.user_id = user_id  # None = мультипользовательский режим
        self.on_mention = on_mention
        self._multi_user = user_id is None

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._client: TelegramClient | None = None
        self._chat_ids_to_users: dict[int, set[int]] = {}
        self._chat_usernames_to_users: dict[str, set[int]] = {}
        self._embedding_cache: KeywordEmbeddingCache | None = (
            KeywordEmbeddingCache() if KeywordEmbeddingCache else None
        )
        # Кэш разрешённых инвайтов (invite_hash -> (chat_id|username, expiry)), чтобы не дергать CheckChatInvite/Join каждые 60 с
        self._invite_cache: dict[str, tuple[int | str, float]] = {}
        self._invite_cache_ttl = 3600.0  # 1 час

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_thread, name="TelegramScanner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        client = self._client
        if client:
            try:
                asyncio.run(client.disconnect())
            except Exception:
                pass

    def _run_thread(self) -> None:
        try:
            log_append("Поток парсера запущен.")
            asyncio.run(self._run())
        except Exception as e:
            log_exception(e)
        finally:
            log_append("Поток парсера завершён.")

    async def _run(self) -> None:
        api_id = get_parser_setting_str("TG_API_ID")
        api_hash = get_parser_setting_str("TG_API_HASH")
        if not api_id or not api_hash:
            raise RuntimeError(
                "Задайте TG_API_ID и TG_API_HASH в настройках парсера (Админ → Парсер) или в .env"
            )

        session_string = get_parser_setting_str("TG_SESSION_STRING")
        session_name = get_parser_setting_str("TG_SESSION_NAME") or "telegram_monitor"

        proxy_cfg = _proxy_from_config()
        proxy = proxy_cfg.to_telethon() if proxy_cfg else None

        if session_string:
            client = TelegramClient(StringSession(session_string), int(api_id), api_hash, proxy=proxy)
        else:
            client = TelegramClient(session_name, int(api_id), api_hash, proxy=proxy)

        self._client = client

        if not self._multi_user:
            with db_session() as db:
                user = db.get(User, self.user_id)
                if not user:
                    db.add(User(id=self.user_id, name="Default"))

        # Запускаем клиент до загрузки чатов, чтобы разрешать invite-ссылки через Telethon
        try:
            await client.start(bot_token=get_parser_setting_str("TG_BOT_TOKEN") or None)
        except EOFError:
            raise RuntimeError(
                "Интерактивный вход невозможен (нет консоли). "
                "Задайте TG_SESSION_STRING в настройках парсера: создайте сессию локально через Telethon StringSession, "
                "войдите в аккаунт один раз и вставьте выданную строку в админке (Парсер → Настройки)."
            ) from None

        chats_filter = await self._load_chats_filter(client)
        state: dict = {"filter": chats_filter, "handler": None}

        async def on_message(event: events.NewMessage.Event) -> None:
            try:
                await self._handle_message(event)
            except Exception as e:
                log_exception(e)
                return

        state["handler"] = client.add_event_handler(
            on_message,
            events.NewMessage(chats=chats_filter or None),
        )

        async def refresh_chats_loop() -> None:
            """Периодически перезагружаем список каналов из БД, чтобы подхватить новые без перезапуска парсера."""
            interval = 60
            while True:
                await asyncio.sleep(interval)
                if not client.is_connected():
                    break
                try:
                    new_filter = await self._load_chats_filter(client)
                    old_set = set(state["filter"] or [])
                    new_set = set(new_filter or [])
                    if old_set != new_set:
                        client.remove_event_handler(state["handler"])
                        state["filter"] = new_filter
                        state["handler"] = client.add_event_handler(
                            on_message,
                            events.NewMessage(chats=new_filter or None),
                        )
                        log_append(f"Парсер: обновлён список каналов (теперь {len(new_set)}).")
                except Exception as e:
                    log_exception(e)

        asyncio.create_task(refresh_chats_loop())

        await client.run_until_disconnected()

    def _resolve_invite_cached_result(self, invite_hash: str) -> int | str | None:
        """Возвращает закэшированный chat_id/username по инвайту, если кэш валиден."""
        entry = self._invite_cache.get(invite_hash)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del self._invite_cache[invite_hash]
            return None
        return value

    def _resolve_invite_cache_put(self, invite_hash: str, value: int | str) -> None:
        self._invite_cache[invite_hash] = (value, time.monotonic() + self._invite_cache_ttl)

    async def _resolve_invite(self, client: TelegramClient, invite_hash: str) -> int | str | None:
        """
        Возвращает chat_id или username для фильтра. Если мы ещё не в чате — принимаем инвайт в TG (один раз).
        Результат кэшируется на 1 час, чтобы не вызывать CheckChatInvite/Join при каждом обновлении списка (60 с).
        """
        cached = self._resolve_invite_cached_result(invite_hash)
        if cached is not None:
            return cached

        link = f"https://t.me/joinchat/{invite_hash}"
        entity = None
        try:
            # 1) Уже в чате? get_entity по ссылке сработает — не вызываем Join
            try:
                entity = await client.get_entity(link)
            except FloodWaitError as e:
                log_append(f"Парсер: ограничение Telegram по инвайту, ждём {e.seconds} с…")
                await asyncio.sleep(e.seconds)
                try:
                    entity = await client.get_entity(link)
                except Exception:
                    return None
            except Exception:
                pass

            # 2) Не в чате — принимаем инвайт один раз (ImportChatInviteRequest)
            if entity is None:
                try:
                    updates = await client(ImportChatInviteRequest(invite_hash))
                    if updates and getattr(updates, "chats", None) and len(updates.chats) > 0:
                        entity = updates.chats[0]
                        title = getattr(entity, "title", None) or getattr(entity, "name", None) or invite_hash[:16]
                        log_append(f"Парсер: присоединились к чату по инвайту: {title}")
                except FloodWaitError as e:
                    log_append(f"Парсер: ограничение Telegram, ждём {e.seconds} с перед присоединением по инвайту…")
                    await asyncio.sleep(e.seconds)
                    try:
                        updates = await client(ImportChatInviteRequest(invite_hash))
                        if updates and getattr(updates, "chats", None) and len(updates.chats) > 0:
                            entity = updates.chats[0]
                    except UserAlreadyParticipantError:
                        # Уже в чате — один раз получаем entity (get_entity дергает CheckChatInvite, может дать FloodWait)
                        try:
                            entity = await client.get_entity(link)
                        except FloodWaitError as ew:
                            await asyncio.sleep(ew.seconds)
                            entity = await client.get_entity(link)
                    except Exception as retry_e:
                        log_exception(retry_e)
                        return None
                except UserAlreadyParticipantError:
                    # Уже в чате — не вызываем Join снова; один раз get_entity, при FloodWait — ждём и повторяем
                    try:
                        entity = await client.get_entity(link)
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                        entity = await client.get_entity(link)
                except Exception as e:
                    log_exception(e)
                    return None

            if entity is None:
                return None
            chat_id = getattr(entity, "id", None)
            if chat_id is not None:
                result: int | str = int(chat_id)
                self._resolve_invite_cache_put(invite_hash, result)
                return result
            username = getattr(entity, "username", None)
            if username:
                self._resolve_invite_cache_put(invite_hash, username)
                return username
            return None
        except Exception as e:
            log_exception(e)
            return None

    async def _load_chats_filter(self, client: TelegramClient | None = None) -> list[str | int] | None:
        # Мультипользовательский режим: только из БД, без TG_CHATS
        if self._multi_user:
            from sqlalchemy import select

            with db_session() as db:
                users = db.query(User).all()
                allowed_user_ids = {u.id for u in users if can_track(get_effective_plan(u), db)}
                rows: list[Chat] = (
                    db.query(Chat).filter(Chat.enabled.is_(True), Chat.source == CHAT_SOURCE_TELEGRAM).order_by(Chat.id.asc()).all()
                )
                # Для глобальных каналов — пользователи из подписок (с включённым мониторингом); для остальных — владелец.
                user_ids_by_chat: dict[int, set[int]] = {}
                for r in rows:
                    if getattr(r, "is_global", False):
                        try:
                            sub_rows = db.execute(
                                select(user_chat_subscriptions.c.user_id, user_chat_subscriptions.c.enabled).where(
                                    user_chat_subscriptions.c.chat_id == r.id
                                )
                            ).all()
                            sub_ids = {row[0] for row in sub_rows if len(row) < 2 or row[1] is None or row[1]}
                        except Exception:
                            sub_ids = set(
                                row[0] for row in db.execute(
                                    select(user_chat_subscriptions.c.user_id).where(
                                        user_chat_subscriptions.c.chat_id == r.id
                                    )
                                ).scalars().all()
                            )
                        user_ids_by_chat[r.id] = sub_ids & allowed_user_ids
                    else:
                        user_ids_by_chat[r.id] = {r.user_id} if r.user_id in allowed_user_ids else set()

            self._chat_ids_to_users = {}
            self._chat_usernames_to_users = {}
            seen: set[str | int] = set()
            result: list[str | int] = []
            for r in rows:
                user_ids = user_ids_by_chat.get(r.id, set())
                if not user_ids:
                    continue
                resolved: int | str | None = None
                if r.tg_chat_id is not None:
                    resolved = int(r.tg_chat_id)
                elif (r.username or "").strip():
                    resolved = (r.username or "").strip()
                elif getattr(r, "invite_hash", None) and client:
                    resolved = await self._resolve_invite(client, r.invite_hash)
                if resolved is not None:
                    if isinstance(resolved, int):
                        self._chat_ids_to_users.setdefault(resolved, set()).update(user_ids)
                        if resolved not in seen:
                            seen.add(resolved)
                            result.append(resolved)
                    else:
                        self._chat_usernames_to_users.setdefault(resolved, set()).update(user_ids)
                        if resolved not in seen:
                            seen.add(resolved)
                            result.append(resolved)
            return result if result else None

        # Один пользователь: TG_CHATS или БД. Не загружаем чаты, если у пользователя тариф free.
        with db_session() as db:
            user = db.get(User, self.user_id)
            if not user or not can_track(get_effective_plan(user), db):
                return None
        env_chats = _parse_chat_identifiers(get_parser_setting_str("TG_CHATS"))
        if env_chats:
            parsed: list[str | int] = []
            for c in env_chats:
                v = c.strip()
                if v.lstrip("-").isdigit():
                    parsed.append(int(v))
                else:
                    parsed.append(v.lstrip("@"))
            return parsed

        with db_session() as db:
            from sqlalchemy import select

            sub_chat_ids = set()
            try:
                sub_rows = db.execute(
                    select(user_chat_subscriptions.c.chat_id, user_chat_subscriptions.c.enabled).where(
                        user_chat_subscriptions.c.user_id == self.user_id
                    )
                ).all()
                for r in sub_rows:
                    if len(r) < 2 or r[1] is None or r[1]:
                        sub_chat_ids.add(r[0])
            except Exception:
                sub_chat_ids = set(
                    rid for (rid,) in db.execute(
                        select(user_chat_subscriptions.c.chat_id).where(
                            user_chat_subscriptions.c.user_id == self.user_id
                        )
                    ).scalars().all()
                )
            rows_owned = (
                db.query(Chat)
                .filter(Chat.user_id == self.user_id, Chat.enabled.is_(True), Chat.source == CHAT_SOURCE_TELEGRAM)
                .order_by(Chat.id.asc())
                .all()
            )
            rows_subs = (
                db.query(Chat)
                .filter(Chat.id.in_(sub_chat_ids), Chat.is_global.is_(True), Chat.enabled.is_(True), Chat.source == CHAT_SOURCE_TELEGRAM)
                .order_by(Chat.id.asc())
                .all()
            ) if sub_chat_ids else []
        seen_id: set[int] = set()
        parsed2: list[str | int] = []
        for r in rows_owned + rows_subs:
            if r.id in seen_id:
                continue
            seen_id.add(r.id)
            if r.tg_chat_id is not None:
                parsed2.append(int(r.tg_chat_id))
            elif (r.username or "").strip():
                parsed2.append((r.username or "").strip())
            elif getattr(r, "invite_hash", None) and client:
                resolved = await self._resolve_invite(client, r.invite_hash)
                if resolved is not None:
                    parsed2.append(resolved)
        return parsed2

    async def _handle_message(self, event: events.NewMessage.Event) -> None:
        msg = event.message
        text_raw = msg.message or ""
        text = text_raw.strip()
        if not text:
            return
        # Сохраняем в БД исходный текст без искажений; для поиска по ключам — нормализованная строка
        text_cf = text.casefold()

        chat = await event.get_chat()
        sender = await event.get_sender()

        chat_id = getattr(chat, "id", None)
        chat_title = getattr(chat, "title", None) or getattr(chat, "name", None)
        chat_username = getattr(chat, "username", None)

        sender_id = getattr(sender, "id", None)
        first_name = getattr(sender, "first_name", None) or ""
        last_name = getattr(sender, "last_name", None) or ""
        sender_username = getattr(sender, "username", None)
        sender_name = (f"{first_name} {last_name}").strip() or sender_username

        created_at = msg.date
        if created_at is None:
            created_at = _now_utc()
        elif created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if self._multi_user:
            user_ids = set()
            if chat_id is not None:
                user_ids |= self._chat_ids_to_users.get(int(chat_id), set())
            if chat_username:
                user_ids |= self._chat_usernames_to_users.get((chat_username or "").strip(), set())
            if not user_ids:
                return
            keywords_by_user = self._load_keywords_multi()
            msg_id = int(msg.id) if getattr(msg, "id", None) is not None else None
            cid = int(chat_id) if chat_id is not None else None
            for uid in user_ids:
                items = keywords_by_user.get(uid, [])
                exclusion_map = {item.text: list(item.exclusion_words) for item in items}
                thresh = get_user_semantic_threshold(uid)
                thresh = float(thresh) if thresh is not None else 0.6  # стандартный порог 60%
                min_topic = get_user_semantic_min_topic_percent(uid)
                if min_topic is None:
                    min_topic = 70.0  # стандартный мин. % совпадения с темой 70%
                matches = await self._match_keywords(items, text, text_cf, threshold=thresh, min_topic_percent=min_topic)
                for kw, sim, span in matches:
                    if _message_has_exclusion(text_cf, exclusion_map.get(kw, [])):
                        continue
                    with db_session() as db:
                        mention = Mention(
                            user_id=uid,
                            keyword_text=kw,
                            message_text=text_raw,
                            chat_id=cid,
                            chat_name=chat_title,
                            chat_username=chat_username,
                            message_id=msg_id,
                            sender_id=int(sender_id) if sender_id is not None else None,
                            sender_name=sender_name,
                            sender_username=sender_username,
                            is_read=False,
                            is_lead=False,
                            semantic_similarity=sim,
                            semantic_matched_span=(span or None),
                            created_at=created_at,
                        )
                        db.add(mention)
                        db.flush()
                        message_link = None
                        if msg_id is not None:
                            if chat_username and str(chat_username).strip():
                                uname = str(chat_username).strip().lstrip("@")
                                if uname:
                                    message_link = f"https://t.me/{uname}/{msg_id}"
                            elif cid is not None:
                                aid = abs(cid)
                                part = aid % (10**10) if aid >= 10**10 else aid
                                message_link = f"tg://privatepost?channel={part}&post={msg_id}"
                        user_link = None
                        if sender_username and str(sender_username).strip():
                            user_link = f"https://t.me/{str(sender_username).strip().lstrip('@')}"
                        elif sender_id is not None:
                            user_link = f"tg://user?id={sender_id}"
                        payload = {
                            "type": "mention",
                            "data": {
                                "id": str(mention.id),
                                "userId": uid,
                                "groupName": (chat_title or chat_username or "Неизвестный чат"),
                                "groupIcon": _initials(chat_title or chat_username),
                                "userName": (sender_name or "Неизвестный пользователь"),
                                "userInitials": _initials(sender_name),
                                "userLink": user_link,
                                "message": text_raw,
                                "keyword": kw,
                                "timestamp": _humanize_ru(created_at),
                                "isLead": False,
                                "isRead": False,
                                "createdAt": created_at.isoformat(),
                                "messageLink": message_link,
                                "topicMatchPercent": round(sim * 100) if sim is not None else None,
                            },
                        }
                    if self.on_mention:
                        self.on_mention(payload)
                    mention_notifications.enqueue_mention_notification(mention.id)
            return

        items = self._load_keywords()
        if not items:
            return
        exclusion_map = {item.text: list(item.exclusion_words) for item in items}
        thresh = get_user_semantic_threshold(self.user_id)
        thresh = float(thresh) if thresh is not None else 0.6  # стандартный порог 60%
        min_topic = get_user_semantic_min_topic_percent(self.user_id)
        if min_topic is None:
            min_topic = 70.0  # стандартный мин. % совпадения с темой 70%
        matches = await self._match_keywords(items, text, text_cf, threshold=thresh, min_topic_percent=min_topic)
        if not matches:
            return

        # Записываем mention для каждого совпавшего keyword (можно поменять на “первое совпадение” при желании)
        for kw, sim, span in matches:
            if _message_has_exclusion(text_cf, exclusion_map.get(kw, [])):
                continue
            with db_session() as db:
                mention = Mention(
                    user_id=self.user_id,
                    keyword_text=kw,
                    message_text=text_raw,
                    chat_id=int(chat_id) if chat_id is not None else None,
                    chat_name=chat_title,
                    chat_username=chat_username,
                    message_id=int(msg.id) if getattr(msg, "id", None) is not None else None,
                    sender_id=int(sender_id) if sender_id is not None else None,
                    sender_name=sender_name,
                    sender_username=sender_username,
                    is_read=False,
                    is_lead=False,
                    semantic_similarity=sim,
                    semantic_matched_span=(span or None),
                    created_at=created_at,
                )
                db.add(mention)
                db.flush()
                msg_id = int(msg.id) if getattr(msg, "id", None) is not None else None
                cid = int(chat_id) if chat_id is not None else None
                message_link = None
                if msg_id is not None:
                    if chat_username and str(chat_username).strip():
                        uname = str(chat_username).strip().lstrip("@")
                        if uname:
                            message_link = f"https://t.me/{uname}/{msg_id}"
                    elif cid is not None:
                        aid = abs(cid)
                        part = aid % (10**10) if aid >= 10**10 else aid
                        message_link = f"tg://privatepost?channel={part}&post={msg_id}"
                user_link = None
                if sender_username and str(sender_username).strip():
                    user_link = f"https://t.me/{str(sender_username).strip().lstrip('@')}"
                elif sender_id is not None:
                    user_link = f"tg://user?id={sender_id}"
                payload = {
                    "type": "mention",
                    "data": {
                        "id": str(mention.id),
                        "userId": self.user_id,
                        "groupName": (chat_title or chat_username or "Неизвестный чат"),
                        "groupIcon": _initials(chat_title or chat_username),
                        "userName": (sender_name or "Неизвестный пользователь"),
                        "userInitials": _initials(sender_name),
                        "userLink": user_link,
                        "message": text_raw,
                        "keyword": kw,
                        "timestamp": _humanize_ru(created_at),
                        "isLead": False,
                        "isRead": False,
                        "createdAt": created_at.isoformat(),
                        "messageLink": message_link,
                        "topicMatchPercent": round(sim * 100) if sim is not None else None,
                    },
                }

            if self.on_mention:
                self.on_mention(payload)
            mention_notifications.enqueue_mention_notification(mention.id)

    def _load_keywords(self) -> list[KeywordItem]:
        with db_session() as db:
            user = db.get(User, self.user_id)
            if not user or not can_track(get_effective_plan(user), db):
                return []
            rows = (
                db.query(Keyword)
                .filter(Keyword.user_id == self.user_id, Keyword.enabled.is_(True))
                .order_by(Keyword.id.asc())
                .all()
            )
            if not rows:
                return []
            kw_ids = [r.id for r in rows]
            excl_rows = db.query(ExclusionWord).filter(ExclusionWord.keyword_id.in_(kw_ids)).all()
            excl_by_kw: dict[int, list[str]] = {}
            for e in excl_rows:
                t = (e.text or "").strip()
                if t:
                    excl_by_kw.setdefault(e.keyword_id, []).append(t)
            out: list[KeywordItem] = []
            for r in rows:
                t = (r.text or "").strip()
                if t:
                    use_sem = getattr(r, "use_semantic", False)
                    out.append(
                        KeywordItem(
                            text=t,
                            use_semantic=use_sem,
                            exclusion_words=tuple(excl_by_kw.get(r.id, [])),
                        )
                    )
            return out

    def _load_keywords_multi(self) -> dict[int, list[KeywordItem]]:
        with db_session() as db:
            users = db.query(User).all()
            allowed_user_ids = {u.id for u in users if can_track(get_effective_plan(u), db)}
            rows = (
                db.query(Keyword)
                .filter(Keyword.enabled.is_(True))
                .order_by(Keyword.user_id, Keyword.id.asc())
                .all()
            )
            if not rows:
                return {}
            kw_ids = [r.id for r in rows]
            excl_rows = db.query(ExclusionWord).filter(ExclusionWord.keyword_id.in_(kw_ids)).all()
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

    def _message_chunks(self, text: str, max_chunks: int = 6) -> list[str]:
        """Фрагменты сообщения для сравнения с короткими ключами (тема лучше видна в короткой фразе)."""
        import re
        t = (text or "").strip()
        if not t or len(t) < 10:
            return []
        parts = re.split(r"[.!?;\n]+", t)
        chunks: list[str] = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            words = p.split()
            if len(words) <= 4:
                chunks.append(p)
            else:
                # Добавить полную фразу и скользящие окна 3–5 слов (напр. «будет стоить 20 рублей»)
                if len(words) <= 8:
                    chunks.append(p)
                for w in (4, 5, 3):
                    if len(words) < w:
                        continue
                    for i in range(0, min(2, len(words) - w + 1)):  # первые 2 окна каждого размера
                        chunk = " ".join(words[i : i + w])
                        if chunk not in chunks:
                            chunks.append(chunk)
                        if len(chunks) >= max_chunks:
                            return chunks[:max_chunks]
            if len(chunks) >= max_chunks:
                break
        return chunks[:max_chunks]

    def _message_words(self, text: str, max_words: int = 40) -> list[str]:
        """Отдельные слова сообщения для семантического сравнения (синонимы, другой язык, перефразирование)."""
        import re
        t = (text or "").strip()
        if not t:
            return []
        # Токены: буквы (в т.ч. кириллица, латиница), цифры; минимум 2 символа
        tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}", t)
        seen: set[str] = set()
        out: list[str] = []
        for w in tokens:
            w_lower = w.casefold()
            if w_lower in seen:
                continue
            seen.add(w_lower)
            out.append(w)
            if len(out) >= max_words:
                break
        return out

    async def _match_keywords(
        self,
        items: list[KeywordItem],
        text: str,
        text_cf: str,
        threshold: float | None = None,
        min_topic_percent: float | None = None,
    ) -> list[tuple[str, float | None, str | None]]:
        """
        Совпадение по смыслу: общая тема сообщения, перефразирование (фразы), отдельные слова (синонимы, другой язык).
        Возвращает (keyword, similarity, matched_span): matched_span — фрагмент сообщения, давший лучшее сходство (для подсветки).
        Тяжёлый embed() выполняется в отдельном потоке (1 worker), чтобы не блокировать event loop и не давать 100% CPU при пачке сообщений.
        """
        exact_items = [kw for kw in items if not kw.use_semantic]
        semantic_items = [kw for kw in items if kw.use_semantic]
        # ключ -> (sim, matched_span)
        by_kw: dict[str, tuple[float | None, str | None]] = {}
        for kw in exact_items:
            if kw.text.casefold() in text_cf:
                by_kw[kw.text] = (None, kw.text)  # точное: подсвечиваем сам ключ
        if not semantic_items:
            return [(k, sim, span) for k, (sim, span) in by_kw.items()]
        thresh = (float(threshold) if threshold is not None else None) or (
            similarity_threshold() if similarity_threshold else 0.55
        )
        cache = self._embedding_cache
        if cache is None or embed is None or cosine_similarity is None:
            for kw in semantic_items:
                if kw.text.casefold() in text_cf and kw.text not in by_kw:
                    by_kw[kw.text] = (None, kw.text)
            return [(k, sim, span) for k, (sim, span) in by_kw.items()]
        # Вся тяжёлая работа (cache.update + embed) только в executor — не блокируем event loop
        chunks = self._message_chunks(text)
        words = self._message_words(text)
        to_embed: list[str] = [text]
        to_embed.extend(chunks)
        to_embed.extend(words)
        all_vectors = None
        try:
            if _SEMANTIC_EXECUTOR:
                loop = asyncio.get_running_loop()
                all_vectors = await loop.run_in_executor(
                    _SEMANTIC_EXECUTOR,
                    _run_semantic_embed,
                    cache,
                    [kw.text for kw in semantic_items],
                    to_embed,
                )
            else:
                cache.update([kw.text for kw in semantic_items])
                all_vectors = embed(to_embed)
        except Exception as e:
            log_exception(e)
            for kw in semantic_items:
                if kw.text.casefold() in text_cf and kw.text not in by_kw:
                    by_kw[kw.text] = (None, kw.text)
            return [(k, sim, span) for k, (sim, span) in by_kw.items()]
        if not all_vectors or len(all_vectors) < 1:
            for kw in semantic_items:
                if kw.text.casefold() in text_cf and kw.text not in by_kw:
                    by_kw[kw.text] = (None, kw.text)
            return [(k, sim, span) for k, (sim, span) in by_kw.items()]
        msg_vec = all_vectors[0]
        n_chunks = len(chunks)
        chunk_vecs = all_vectors[1 : 1 + n_chunks] if n_chunks else []
        word_vecs = all_vectors[1 + n_chunks :] if words else []
        for kw in semantic_items:
            kw_vec = cache.get(kw.text)
            if kw_vec is None:
                if kw.text.casefold() in text_cf and kw.text not in by_kw:
                    by_kw[kw.text] = (None, kw.text)
                continue
            best_sim = cosine_similarity(msg_vec, kw_vec)
            best_span: str = text.strip()  # по умолчанию — всё сообщение
            for i, cvec in enumerate(chunk_vecs):
                s = cosine_similarity(cvec, kw_vec)
                if s > best_sim:
                    best_sim = s
                    best_span = chunks[i] if i < len(chunks) else best_span
            for i, wvec in enumerate(word_vecs):
                s = cosine_similarity(wvec, kw_vec)
                if s > best_sim:
                    best_sim = s
                    best_span = words[i] if i < len(words) else best_span
            if best_sim >= thresh:
                if min_topic_percent is not None and best_sim * 100 < min_topic_percent:
                    continue
                cur = by_kw.get(kw.text)
                if cur is None or (cur[0] is None or (best_sim is not None and best_sim > cur[0])):
                    by_kw[kw.text] = (best_sim, best_span.strip() or text.strip()[:200])
            elif kw.text.casefold() in text_cf and kw.text not in by_kw:
                by_kw[kw.text] = (None, kw.text)
        return [(k, sim, span) for k, (sim, span) in by_kw.items()]

