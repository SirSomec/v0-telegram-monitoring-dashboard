from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

import socks  # PySocks
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ImportChatInviteRequest

from database import db_session
from models import Chat, Keyword, Mention, User, user_chat_subscriptions
from parser_log import append as log_append, append_exception as log_exception
from parser_config import (
    get_parser_setting_str,
    get_parser_setting_bool,
    get_parser_setting_int,
    get_parser_setting,
)

try:
    from semantic import embed, cosine_similarity, similarity_threshold, KeywordEmbeddingCache
except ImportError:
    embed = None
    cosine_similarity = None
    similarity_threshold = None
    KeywordEmbeddingCache = None

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


@dataclass(frozen=True)
class KeywordItem:
    """Ключевое слово с флагом режима поиска."""
    text: str
    use_semantic: bool


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
            except Exception:
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

    async def _resolve_invite(self, client: TelegramClient, invite_hash: str) -> int | str | None:
        """
        Возвращает chat_id или username для фильтра. Если мы ещё не в чате — принимаем инвайт в TG (один раз).
        При каждом обновлении списка (каждые 60 с) сначала проверяем get_entity: если уже в чате — не дергаем Join.
        """
        link = f"https://t.me/joinchat/{invite_hash}"
        entity = None
        try:
            # 1) Сначала проверяем: уже в чате? Тогда get_entity по ссылке сработает — не вызываем Join повторно
            try:
                entity = await client.get_entity(link)
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
                        entity = await client.get_entity(link)
                    except Exception as retry_e:
                        log_exception(retry_e)
                        return None
                except UserAlreadyParticipantError:
                    entity = await client.get_entity(link)
                except Exception as e:
                    log_exception(e)
                    return None

            if entity is None:
                return None
            chat_id = getattr(entity, "id", None)
            if chat_id is not None:
                return int(chat_id)
            username = getattr(entity, "username", None)
            if username:
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
                rows: list[Chat] = (
                    db.query(Chat).filter(Chat.enabled.is_(True)).order_by(Chat.id.asc()).all()
                )
                # Для глобальных каналов — пользователи из подписок; для остальных — владелец
                user_ids_by_chat: dict[int, set[int]] = {}
                for r in rows:
                    if getattr(r, "is_global", False):
                        sub_ids = set(
                            db.execute(
                                select(user_chat_subscriptions.c.user_id).where(
                                    user_chat_subscriptions.c.chat_id == r.id
                                )
                            ).scalars().all()
                        )
                        user_ids_by_chat[r.id] = sub_ids
                    else:
                        user_ids_by_chat[r.id] = {r.user_id}

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

        # Один пользователь: TG_CHATS или БД
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

            sub_chat_ids = set(
                db.execute(
                    select(user_chat_subscriptions.c.chat_id).where(
                        user_chat_subscriptions.c.user_id == self.user_id
                    )
                ).scalars().all()
            )
            rows_owned = (
                db.query(Chat)
                .filter(Chat.user_id == self.user_id, Chat.enabled.is_(True))
                .order_by(Chat.id.asc())
                .all()
            )
            rows_subs = (
                db.query(Chat)
                .filter(Chat.id.in_(sub_chat_ids), Chat.is_global.is_(True), Chat.enabled.is_(True))
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
        text = (msg.message or "").strip()
        if not text:
            return

        text_cf = text.casefold()

        chat = await event.get_chat()
        sender = await event.get_sender()

        chat_id = getattr(chat, "id", None)
        chat_title = getattr(chat, "title", None) or getattr(chat, "name", None)
        chat_username = getattr(chat, "username", None)

        sender_id = getattr(sender, "id", None)
        first_name = getattr(sender, "first_name", None) or ""
        last_name = getattr(sender, "last_name", None) or ""
        sender_name = (f"{first_name} {last_name}").strip() or getattr(sender, "username", None)

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
                matches = self._match_keywords(items, text, text_cf)
                for kw in matches:
                    with db_session() as db:
                        mention = Mention(
                            user_id=uid,
                            keyword_text=kw,
                            message_text=text,
                            chat_id=cid,
                            chat_name=chat_title,
                            chat_username=chat_username,
                            message_id=msg_id,
                            sender_id=int(sender_id) if sender_id is not None else None,
                            sender_name=sender_name,
                            is_read=False,
                            is_lead=False,
                            created_at=created_at,
                        )
                        db.add(mention)
                        db.flush()
                        message_link = None
                        if cid is not None and msg_id is not None:
                            aid = abs(cid)
                            part = aid % (10**10) if aid >= 10**10 else aid
                            message_link = f"https://t.me/c/{part}/{msg_id}"
                        payload = {
                            "type": "mention",
                            "data": {
                                "id": str(mention.id),
                                "userId": uid,
                                "groupName": (chat_title or chat_username or "Неизвестный чат"),
                                "groupIcon": _initials(chat_title or chat_username),
                                "userName": (sender_name or "Неизвестный пользователь"),
                                "userInitials": _initials(sender_name),
                                "message": text,
                                "keyword": kw,
                                "timestamp": _humanize_ru(created_at),
                                "isLead": False,
                                "isRead": False,
                                "createdAt": created_at.isoformat(),
                                "messageLink": message_link,
                            },
                        }
                    if self.on_mention:
                        self.on_mention(payload)
            return

        items = self._load_keywords()
        if not items:
            return
        matches = self._match_keywords(items, text, text_cf)
        if not matches:
            return

        # Записываем mention для каждого совпавшего keyword (можно поменять на “первое совпадение” при желании)
        for kw in matches:
            with db_session() as db:
                mention = Mention(
                    user_id=self.user_id,
                    keyword_text=kw,
                    message_text=text,
                    chat_id=int(chat_id) if chat_id is not None else None,
                    chat_name=chat_title,
                    chat_username=chat_username,
                    message_id=int(msg.id) if getattr(msg, "id", None) is not None else None,
                    sender_id=int(sender_id) if sender_id is not None else None,
                    sender_name=sender_name,
                    is_read=False,
                    is_lead=False,
                    created_at=created_at,
                )
                db.add(mention)
                db.flush()
                msg_id = int(msg.id) if getattr(msg, "id", None) is not None else None
                cid = int(chat_id) if chat_id is not None else None
                message_link = None
                if cid is not None and msg_id is not None:
                    aid = abs(cid)
                    part = aid % (10**10) if aid >= 10**10 else aid
                    message_link = f"https://t.me/c/{part}/{msg_id}"
                payload = {
                    "type": "mention",
                    "data": {
                        "id": str(mention.id),
                        "groupName": (chat_title or chat_username or "Неизвестный чат"),
                        "groupIcon": _initials(chat_title or chat_username),
                        "userName": (sender_name or "Неизвестный пользователь"),
                        "userInitials": _initials(sender_name),
                        "message": text,
                        "keyword": kw,
                        "timestamp": _humanize_ru(created_at),
                        "isLead": False,
                        "isRead": False,
                        "createdAt": created_at.isoformat(),
                        "messageLink": message_link,
                    },
                }

            if self.on_mention:
                self.on_mention(payload)

    def _load_keywords(self) -> list[KeywordItem]:
        with db_session() as db:
            rows = (
                db.query(Keyword)
                .filter(Keyword.user_id == self.user_id, Keyword.enabled.is_(True))
                .order_by(Keyword.id.asc())
                .all()
            )
            out: list[KeywordItem] = []
            for r in rows:
                t = (r.text or "").strip()
                if t:
                    use_sem = getattr(r, "use_semantic", False)
                    out.append(KeywordItem(text=t, use_semantic=use_sem))
            return out

    def _load_keywords_multi(self) -> dict[int, list[KeywordItem]]:
        with db_session() as db:
            rows = (
                db.query(Keyword)
                .filter(Keyword.enabled.is_(True))
                .order_by(Keyword.user_id, Keyword.id.asc())
                .all()
            )
            out: dict[int, list[KeywordItem]] = {}
            for r in rows:
                t = (r.text or "").strip()
                if t:
                    use_sem = getattr(r, "use_semantic", False)
                    out.setdefault(r.user_id, []).append(KeywordItem(text=t, use_semantic=use_sem))
            return out

    def _match_keywords(self, items: list[KeywordItem], text: str, text_cf: str) -> list[str]:
        """Возвращает список текстов ключевых слов, совпавших с сообщением (точное и/или семантическое)."""
        exact_items = [kw for kw in items if not kw.use_semantic]
        semantic_items = [kw for kw in items if kw.use_semantic]
        matches: list[str] = [kw.text for kw in exact_items if kw.text.casefold() in text_cf]
        if not semantic_items:
            return matches
        cache = self._embedding_cache
        if cache is None or embed is None or cosine_similarity is None or similarity_threshold is None:
            for kw in semantic_items:
                if kw.text.casefold() in text_cf:
                    matches.append(kw.text)
            return matches
        cache.update([kw.text for kw in semantic_items])
        if not cache.is_available():
            for kw in semantic_items:
                if kw.text.casefold() in text_cf:
                    matches.append(kw.text)
            return matches
        msg_vectors = embed([text])
        if not msg_vectors:
            for kw in semantic_items:
                if kw.text.casefold() in text_cf:
                    matches.append(kw.text)
            return matches
        msg_vec = msg_vectors[0]
        thresh = similarity_threshold()
        for kw in semantic_items:
            kw_vec = cache.get(kw.text)
            if kw_vec is not None and cosine_similarity(msg_vec, kw_vec) >= thresh:
                matches.append(kw.text)
            elif kw_vec is None:
                if kw.text.casefold() in text_cf:
                    matches.append(kw.text)
        return matches

