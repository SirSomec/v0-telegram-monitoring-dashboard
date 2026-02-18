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
from telethon.sessions import StringSession

from database import db_session
from models import Chat, Keyword, Mention, User

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
class ProxyConfig:
    host: str
    port: int
    username: str | None = None
    password: str | None = None

    def to_telethon(self) -> tuple:
        # Telethon proxy format: (proxy_type, addr, port, rdns, username, password)
        return (socks.SOCKS5, self.host, self.port, True, self.username, self.password)


def _proxy_from_env() -> ProxyConfig | None:
    host = os.getenv("TG_PROXY_HOST")
    port = os.getenv("TG_PROXY_PORT")
    if not host or not port:
        return None
    try:
        p = int(port)
    except ValueError:
        return None
    return ProxyConfig(
        host=host,
        port=p,
        username=os.getenv("TG_PROXY_USER") or None,
        password=os.getenv("TG_PROXY_PASS") or None,
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
    Сканер Telegram на Telethon, который:
    - читает активные keywords из БД
    - слушает events.NewMessage
    - при совпадении (регистронезависимо, корректно для кириллицы через casefold)
      пишет запись в mentions и дергает on_mention(payload)
    """

    def __init__(
        self,
        *,
        user_id: int = 1,
        on_mention: Callable[[dict], None] | None = None,
    ) -> None:
        self.user_id = user_id
        self.on_mention = on_mention

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._client: TelegramClient | None = None

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
        asyncio.run(self._run())

    async def _run(self) -> None:
        api_id = os.getenv("TG_API_ID")
        api_hash = os.getenv("TG_API_HASH")
        if not api_id or not api_hash:
            raise RuntimeError("Нужно задать TG_API_ID и TG_API_HASH в .env")

        session_string = os.getenv("TG_SESSION_STRING")
        session_name = os.getenv("TG_SESSION_NAME", "telegram_monitor")

        proxy_cfg = _proxy_from_env()
        proxy = proxy_cfg.to_telethon() if proxy_cfg else None

        if session_string:
            client = TelegramClient(StringSession(session_string), int(api_id), api_hash, proxy=proxy)
        else:
            client = TelegramClient(session_name, int(api_id), api_hash, proxy=proxy)

        self._client = client

        # Создаем/гарантируем user, чтобы FK не падали
        with db_session() as db:
            user = db.get(User, self.user_id)
            if not user:
                db.add(User(id=self.user_id, name="Default"))

        chats_filter = await self._load_chats_filter()

        @client.on(events.NewMessage(chats=chats_filter or None))
        async def handler(event: events.NewMessage.Event) -> None:
            try:
                await self._handle_message(event)
            except Exception:
                # чтобы не убить цикл сканера из-за одного сообщения
                return

        # start(): если нет bot token и нет сохраненной сессии, Telethon попросит интерактивный ввод в консоли.
        # Для server-mode используйте TG_SESSION_STRING (StringSession) или заранее авторизованную session.
        await client.start(bot_token=os.getenv("TG_BOT_TOKEN") or None)
        await client.run_until_disconnected()

    async def _load_chats_filter(self) -> list[str | int]:
        # 1) Если задан TG_CHATS, используем его (username/@name или числовые id)
        env_chats = _parse_chat_identifiers(os.getenv("TG_CHATS"))
        if env_chats:
            parsed: list[str | int] = []
            for c in env_chats:
                v = c.strip()
                if v.lstrip("-").isdigit():
                    parsed.append(int(v))
                else:
                    parsed.append(v.lstrip("@"))
            return parsed

        # 2) Иначе берем enabled-чаты из БД
        with db_session() as db:
            rows: list[Chat] = (
                db.query(Chat)
                .filter(Chat.user_id == self.user_id, Chat.enabled.is_(True))
                .order_by(Chat.id.asc())
                .all()
            )
            parsed2: list[str | int] = []
            for r in rows:
                if r.tg_chat_id is not None:
                    parsed2.append(int(r.tg_chat_id))
                elif r.username:
                    parsed2.append(r.username)
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

        keywords = self._load_keywords()
        if not keywords:
            return

        matches: list[str] = []
        for kw in keywords:
            kw_cf = kw.casefold()
            if kw_cf and kw_cf in text_cf:
                matches.append(kw)

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
                    },
                }

            if self.on_mention:
                self.on_mention(payload)

    def _load_keywords(self) -> list[str]:
        with db_session() as db:
            rows: list[Keyword] = (
                db.query(Keyword)
                .filter(Keyword.user_id == self.user_id, Keyword.enabled.is_(True))
                .order_by(Keyword.id.asc())
                .all()
            )
            return [r.text for r in rows if (r.text or "").strip()]

