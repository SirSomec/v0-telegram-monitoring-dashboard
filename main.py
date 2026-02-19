from __future__ import annotations

import asyncio
import csv
import io
import os
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from auth_utils import create_token, decode_token, hash_password, verify_password
from database import get_db, init_db
from models import Chat, ChatGroup, Keyword, Mention, User, user_chat_subscriptions
from parser import TelegramScanner
from parser_config import (
    get_all_parser_settings,
    get_parser_setting_bool,
    get_parser_setting_int,
    save_parser_settings,
)
from parser_log import get_lines as get_parser_log_lines


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
    # Простая “человекочитаемая” строка, чтобы фронт мог вывести timestamp как есть.
    # Фронтенд сейчас использует строки вида "2 мин назад".
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


class KeywordCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=400)
    userId: int | None = None


class KeywordOut(BaseModel):
    id: int
    text: str
    userId: int
    createdAt: str


class ChatCreate(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=256, description="username (@name) или числовой chat_id")
    title: str | None = None
    description: str | None = None
    groupIds: list[int] = Field(default_factory=list)
    enabled: bool = True
    userId: int | None = None
    isGlobal: bool | None = None  # только для админа: канал доступен всем пользователям


class ChatOut(BaseModel):
    id: int
    identifier: str
    title: str | None
    description: str | None
    groupIds: list[int]
    enabled: bool
    userId: int
    isGlobal: bool = False
    isOwner: bool = True  # True = свой канал, False = подписка на глобальный
    createdAt: str


class ChatUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    enabled: bool | None = None
    groupIds: list[int] | None = None
    isGlobal: bool | None = None  # только для админа при редактировании своего канала


class ChatAvailableOut(BaseModel):
    id: int
    identifier: str
    title: str | None
    description: str | None
    enabled: bool
    subscribed: bool  # подписан ли текущий пользователь
    createdAt: str


class SubscribeByIdentifierBody(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=256, description="@username или числовой chat_id")


class ChatGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    userId: int | None = None


class ChatGroupOut(BaseModel):
    id: int
    name: str
    description: str | None
    userId: int
    createdAt: str


class UserCreate(BaseModel):
    email: str | None = None
    name: str | None = None
    password: str | None = Field(None, min_length=8, description="Пароль для входа (опционально)")
    isAdmin: bool = False


class UserOut(BaseModel):
    id: int
    email: str | None
    name: str | None
    isAdmin: bool
    createdAt: str


class UserUpdate(BaseModel):
    email: str | None = None
    name: str | None = None
    isAdmin: bool | None = None


class MentionOut(BaseModel):
    id: str
    groupName: str
    groupIcon: str
    userName: str
    userInitials: str
    message: str
    keyword: str
    timestamp: str
    isLead: bool
    isRead: bool
    createdAt: str
    messageLink: str | None = None


class StatsOut(BaseModel):
    mentionsToday: int
    keywordsCount: int
    leadsCount: int


class MentionLeadPatch(BaseModel):
    isLead: bool


class MentionReadPatch(BaseModel):
    isRead: bool


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=1)
    name: str | None = None
    password: str = Field(..., min_length=8)


class AuthResponse(BaseModel):
    token: str
    user: "UserOut"


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8)


class ParserStatusOut(BaseModel):
    running: bool
    multiUser: bool
    userId: int | None = None


class ParserSettingsOut(BaseModel):
    """Настройки парсера (значения из БД или env). Пустые строки — не задано."""
    TG_API_ID: str = ""
    TG_API_HASH: str = ""
    TG_SESSION_STRING: str = ""
    TG_SESSION_NAME: str = ""
    TG_BOT_TOKEN: str = ""
    TG_CHATS: str = ""
    TG_PROXY_HOST: str = ""
    TG_PROXY_PORT: str = ""
    TG_PROXY_USER: str = ""
    TG_PROXY_PASS: str = ""
    AUTO_START_SCANNER: str = ""
    MULTI_USER_SCANNER: str = ""
    TG_USER_ID: str = ""


class ParserSettingsUpdate(BaseModel):
    """Обновление настроек (все поля опциональны)."""
    TG_API_ID: str | None = None
    TG_API_HASH: str | None = None
    TG_SESSION_STRING: str | None = None
    TG_SESSION_NAME: str | None = None
    TG_BOT_TOKEN: str | None = None
    TG_CHATS: str | None = None
    TG_PROXY_HOST: str | None = None
    TG_PROXY_PORT: str | None = None
    TG_PROXY_USER: str | None = None
    TG_PROXY_PASS: str | None = None
    AUTO_START_SCANNER: bool | None = None
    MULTI_USER_SCANNER: bool | None = None
    TG_USER_ID: int | None = None


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


def _cors_config() -> dict:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        origins = [x.strip() for x in raw.split(",") if x.strip()]
        return {"allow_origins": origins, "allow_origin_regex": None}
    # Один сервер (фронт :3000, бэкенд :8000) — разрешаем любой origin, в .env ничего не нужно
    return {"allow_origins": [], "allow_origin_regex": r"https?://.*"}


app = FastAPI(title="Telegram Monitoring Backend", version="0.1.0")

_cors = _cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors["allow_origins"],
    allow_origin_regex=_cors["allow_origin_regex"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_manager = ConnectionManager()
scanner: TelegramScanner | None = None
main_loop: asyncio.AbstractEventLoop | None = None


def _ensure_default_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.id == 1))
    if user:
        return user
    user = User(id=1, email=None, name="Default", is_admin=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _user_to_out(u: User) -> UserOut:
    created_at = u.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return UserOut(
        id=u.id,
        email=u.email,
        name=u.name,
        isAdmin=bool(u.is_admin),
        createdAt=created_at.isoformat(),
    )


def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:].strip()
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _message_link(chat_id: int | None, message_id: int | None) -> str | None:
    if chat_id is None or message_id is None:
        return None
    cid = abs(chat_id)
    part = cid % (10**10) if cid >= 10**10 else cid
    return f"https://t.me/c/{part}/{message_id}"


def _mention_to_front(m: Mention) -> MentionOut:
    group_name = (m.chat_name or m.chat_username or "Неизвестный чат").strip()
    user_name = (m.sender_name or "Неизвестный пользователь").strip()
    created_at = m.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return MentionOut(
        id=str(m.id),
        groupName=group_name,
        groupIcon=_initials(group_name),
        userName=user_name,
        userInitials=_initials(user_name),
        message=m.message_text,
        keyword=m.keyword_text,
        timestamp=_humanize_ru(created_at),
        isLead=bool(m.is_lead),
        isRead=bool(m.is_read),
        createdAt=created_at.isoformat(),
        messageLink=_message_link(m.chat_id, m.message_id),
    )


@app.on_event("startup")
async def on_startup() -> None:
    global scanner, main_loop
    main_loop = asyncio.get_running_loop()
    init_db()

    # Создаем пользователя “по умолчанию”, чтобы CRUD можно было сразу дергать.
    # (Фронт пока без авторизации/токенов.)
    from database import SessionLocal

    with SessionLocal() as db:
        _ensure_default_user(db)

    # Сканер можно включить через настройки (админ) или ENV AUTO_START_SCANNER=1
    if get_parser_setting_bool("AUTO_START_SCANNER", False):
        from parser_log import append as parser_log_append
        parser_log_append("Автозапуск парсера при старте API.")
        multi = get_parser_setting_bool("MULTI_USER_SCANNER", True)
        if multi:
            scanner = TelegramScanner(on_mention=lambda payload: _schedule_ws_broadcast(payload))
        else:
            scanner = TelegramScanner(
                user_id=get_parser_setting_int("TG_USER_ID", 1),
                on_mention=lambda payload: _schedule_ws_broadcast(payload),
            )
        scanner.start()
        parser_log_append("Парсер запущен (автостарт).")


def _schedule_ws_broadcast(payload: dict[str, Any]) -> None:
    # Callback из фонового потока (Telethon) -> отправляем в WS асинхронно.
    loop = main_loop
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), loop)
    else:
        # fallback (например, если uvicorn не поднят)
        try:
            asyncio.run(ws_manager.broadcast(payload))
        except Exception:
            pass


@app.get("/health")
def health() -> dict[str, Literal["ok"]]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthResponse)
def auth_register(body: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    _ensure_default_user(db)
    existing = db.scalar(select(User).where(User.email == body.email.strip()))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    # Первый зарегистрированный пользователь получает права админа
    count = db.scalar(select(func.count(User.id)).where(User.password_hash.isnot(None))) or 0
    is_first_user = count == 0
    user = User(
        email=body.email.strip(),
        name=(body.name or "").strip() or None,
        password_hash=hash_password(body.password),
        is_admin=is_first_user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(token=create_token(user.id), user=_user_to_out(user))


@app.post("/auth/login", response_model=AuthResponse)
def auth_login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    _ensure_default_user(db)
    user = db.scalar(select(User).where(User.email == body.email.strip()))
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return AuthResponse(token=create_token(user.id), user=_user_to_out(user))


@app.get("/auth/me", response_model=UserOut)
def auth_me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_to_out(user)


@app.patch("/auth/me", response_model=UserOut)
def update_me(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="User has no password set")
    if not verify_password(body.currentPassword, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid current password")
    user.password_hash = hash_password(body.newPassword)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_to_out(user)


@app.get("/api/stats", response_model=StatsOut)
def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StatsOut:
    _ensure_default_user(db)
    now = _now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    mentions_today = (
        db.scalar(
            select(func.count(Mention.id)).where(
                Mention.user_id == user.id,
                Mention.created_at >= today_start,
            )
        )
        or 0
    )
    keywords_count = (
        db.scalar(
            select(func.count(Keyword.id)).where(
                Keyword.user_id == user.id,
                Keyword.enabled.is_(True),
            )
        )
        or 0
    )
    leads_count = (
        db.scalar(
            select(func.count(Mention.id)).where(
                Mention.user_id == user.id,
                Mention.is_lead.is_(True),
            )
        )
        or 0
    )
    return StatsOut(
        mentionsToday=mentions_today,
        keywordsCount=keywords_count,
        leadsCount=leads_count,
    )


@app.get("/api/keywords", response_model=list[KeywordOut])
def list_keywords(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[KeywordOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(Keyword).where(Keyword.user_id == user.id).order_by(Keyword.id.asc())).all()
    out: list[KeywordOut] = []
    for k in rows:
        created_at = k.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        out.append(
            KeywordOut(
                id=k.id,
                text=k.text,
                userId=k.user_id,
                createdAt=created_at.isoformat(),
            )
        )
    return out


@app.post("/api/keywords", response_model=KeywordOut)
def create_keyword(body: KeywordCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> KeywordOut:
    _ensure_default_user(db)
    user_id = user.id

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # Не дублируем по (user_id, text) в рамках простого MVP
    existing = db.scalar(select(Keyword).where(Keyword.user_id == user_id, Keyword.text == text))
    if existing:
        created_at = existing.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return KeywordOut(id=existing.id, text=existing.text, userId=existing.user_id, createdAt=created_at.isoformat())

    k = Keyword(user_id=user_id, text=text, enabled=True)
    db.add(k)
    db.commit()
    db.refresh(k)
    created_at = k.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return KeywordOut(id=k.id, text=k.text, userId=k.user_id, createdAt=created_at.isoformat())


@app.delete("/api/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    k = db.scalar(select(Keyword).where(Keyword.id == keyword_id))
    if not k:
        raise HTTPException(status_code=404, detail="keyword not found")
    if k.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    db.delete(k)
    db.commit()
    return {"ok": True}


def _parse_chat_identifier(ident: str) -> tuple[str | None, int | None, str | None]:
    """
    Парсит идентификатор: ссылку (t.me/...), @username или chat_id.
    Возвращает (username, tg_chat_id, invite_hash).
    """
    raw = ident.strip()
    if not raw:
        return (None, None, None)
    # Ссылка t.me/...
    if "t.me/" in raw or "telegram.me/" in raw:
        s = raw.replace("https://", "").replace("http://", "").strip()
        for prefix in ("t.me/", "telegram.me/"):
            if prefix in s:
                part = s.split(prefix, 1)[-1].split("?")[0].rstrip("/")
                if not part:
                    break
                # t.me/c/1234567890 -> -1001234567890
                if part.startswith("c/") and part[2:].lstrip("-").isdigit():
                    return (None, -1000000000000 - int(part[2:]), None)
                # t.me/joinchat/HASH или t.me/+HASH
                if part.startswith("joinchat/"):
                    return (None, None, part[9:].strip())
                if part.startswith("+"):
                    return (None, None, part[1:].strip())
                # t.me/username
                return (part.strip(), None, None)
        return (None, None, None)
    # Числовой chat_id
    if raw.lstrip("-").isdigit():
        return (None, int(raw), None)
    # @username или username
    return (raw.lstrip("@"), None, None)


def _chat_to_out(c: Chat, is_owner: bool) -> ChatOut:
    identifier = (
        (c.username or "")
        or (str(c.tg_chat_id) if c.tg_chat_id is not None else "")
        or (f"t.me/joinchat/{c.invite_hash}" if getattr(c, "invite_hash", None) else "")
    ) or "—"
    created_at = c.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return ChatOut(
        id=c.id,
        identifier=identifier,
        title=c.title,
        description=c.description,
        groupIds=[g.id for g in (c.groups or [])],
        enabled=bool(c.enabled),
        userId=c.user_id,
        isGlobal=bool(c.is_global),
        isOwner=is_owner,
        createdAt=created_at.isoformat(),
    )


@app.get("/api/chats", response_model=list[ChatOut])
def list_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatOut]:
    _ensure_default_user(db)
    out: list[ChatOut] = []
    seen_ids: set[int] = set()
    # Свои каналы (включая глобальные, созданные админом)
    owned = db.scalars(select(Chat).where(Chat.user_id == user.id).order_by(Chat.id.asc())).all()
    for c in owned:
        seen_ids.add(c.id)
        out.append(_chat_to_out(c, is_owner=True))
    # Подписки на глобальные каналы
    sub_rows = (
        db.execute(
            select(Chat).join(user_chat_subscriptions).where(
                user_chat_subscriptions.c.user_id == user.id,
                Chat.id == user_chat_subscriptions.c.chat_id,
            ).order_by(Chat.id.asc())
        )
    ).scalars().all()
    for c in sub_rows:
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            out.append(_chat_to_out(c, is_owner=False))
    out.sort(key=lambda x: x.id)
    return out


@app.post("/api/chats", response_model=ChatOut)
def create_chat(body: ChatCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatOut:
    _ensure_default_user(db)
    user_id = user.id

    ident = body.identifier.strip()
    if not ident:
        raise HTTPException(status_code=400, detail="identifier is required")

    is_global = bool(body.isGlobal) if body.isGlobal is not None else False
    if is_global and not user.is_admin:
        raise HTTPException(status_code=403, detail="only admin can create global channels")

    username, tg_chat_id, invite_hash = _parse_chat_identifier(ident)

    # Если канал уже есть среди глобальных (добавлен администратором) — подписываем пользователя вместо создания дубликата
    existing_global: Chat | None = None
    if tg_chat_id is not None:
        existing_global = db.scalar(
            select(Chat).where(Chat.is_global.is_(True), Chat.tg_chat_id == tg_chat_id)
        )
    if existing_global is None and username:
        existing_global = db.scalar(
            select(Chat).where(Chat.is_global.is_(True), Chat.username == username)
        )
    if existing_global is None and invite_hash:
        existing_global = db.scalar(
            select(Chat).where(Chat.is_global.is_(True), Chat.invite_hash == invite_hash)
        )

    if existing_global is not None:
        already = db.execute(
            select(user_chat_subscriptions).where(
                user_chat_subscriptions.c.user_id == user_id,
                user_chat_subscriptions.c.chat_id == existing_global.id,
            )
        ).first()
        if not already:
            db.execute(
                user_chat_subscriptions.insert().values(user_id=user_id, chat_id=existing_global.id)
            )
            db.commit()
        db.refresh(existing_global)
        return _chat_to_out(existing_global, is_owner=False)

    c = Chat(
        user_id=user_id,
        username=username,
        tg_chat_id=tg_chat_id,
        invite_hash=invite_hash,
        title=body.title,
        description=body.description,
        enabled=body.enabled,
        is_global=is_global,
    )

    if body.groupIds:
        groups = db.scalars(select(ChatGroup).where(ChatGroup.user_id == user_id, ChatGroup.id.in_(body.groupIds))).all()
        c.groups = list(groups)
    db.add(c)
    db.commit()
    db.refresh(c)

    return _chat_to_out(c, is_owner=True)


@app.patch("/api/chats/{chat_id}", response_model=ChatOut)
def update_chat(chat_id: int, body: ChatUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatOut:
    c = db.scalar(select(Chat).where(Chat.id == chat_id))
    if not c:
        raise HTTPException(status_code=404, detail="chat not found")
    if c.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")

    if body.title is not None:
        c.title = body.title
    if body.description is not None:
        c.description = body.description
    if body.enabled is not None:
        c.enabled = bool(body.enabled)
    if body.isGlobal is not None and user.is_admin:
        c.is_global = bool(body.isGlobal)

    if body.groupIds is not None:
        groups = db.scalars(
            select(ChatGroup).where(ChatGroup.user_id == c.user_id, ChatGroup.id.in_(body.groupIds))
        ).all()
        c.groups = list(groups)

    db.add(c)
    db.commit()
    db.refresh(c)

    return _chat_to_out(c, is_owner=True)


@app.get("/api/chat-groups", response_model=list[ChatGroupOut])
def list_chat_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatGroupOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(ChatGroup).where(ChatGroup.user_id == user.id).order_by(ChatGroup.id.asc())).all()
    out: list[ChatGroupOut] = []
    for g in rows:
        created_at = g.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        out.append(
            ChatGroupOut(
                id=g.id,
                name=g.name,
                description=g.description,
                userId=g.user_id,
                createdAt=created_at.isoformat(),
            )
        )
    return out


@app.post("/api/chat-groups", response_model=ChatGroupOut)
def create_chat_group(body: ChatGroupCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatGroupOut:
    _ensure_default_user(db)
    user_id = user.id

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    g = ChatGroup(user_id=user_id, name=name, description=body.description)
    db.add(g)
    db.commit()
    db.refresh(g)

    created_at = g.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return ChatGroupOut(
        id=g.id,
        name=g.name,
        description=g.description,
        userId=g.user_id,
        createdAt=created_at.isoformat(),
    )


@app.delete("/api/chat-groups/{group_id}")
def delete_chat_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    g = db.scalar(select(ChatGroup).where(ChatGroup.id == group_id))
    if not g:
        raise HTTPException(status_code=404, detail="group not found")
    if g.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    db.delete(g)
    db.commit()
    return {"ok": True}


@app.get("/api/users", response_model=list[UserOut])
def list_users(_: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[UserOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(User).order_by(User.id.asc())).all()
    out: list[UserOut] = []
    for u in rows:
        created_at = u.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        out.append(
            UserOut(
                id=u.id,
                email=u.email,
                name=u.name,
                isAdmin=bool(u.is_admin),
                createdAt=created_at.isoformat(),
            )
        )
    return out


@app.post("/api/users", response_model=UserOut)
def create_user(body: UserCreate, _: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> UserOut:
    _ensure_default_user(db)
    u = User(
        email=body.email,
        name=body.name,
        is_admin=bool(body.isAdmin),
        password_hash=hash_password(body.password.strip()) if (body.password and body.password.strip()) else None,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    created_at = u.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return UserOut(
        id=u.id,
        email=u.email,
        name=u.name,
        isAdmin=bool(u.is_admin),
        createdAt=created_at.isoformat(),
    )


@app.patch("/api/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, _: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> UserOut:
    _ensure_default_user(db)
    u = db.scalar(select(User).where(User.id == user_id))
    if not u:
        raise HTTPException(status_code=404, detail="user not found")

    if body.email is not None:
        u.email = body.email
    if body.name is not None:
        u.name = body.name
    if body.isAdmin is not None:
        u.is_admin = bool(body.isAdmin)

    db.add(u)
    db.commit()
    db.refresh(u)
    created_at = u.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return UserOut(
        id=u.id,
        email=u.email,
        name=u.name,
        isAdmin=bool(u.is_admin),
        createdAt=created_at.isoformat(),
    )


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, _: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_default_user(db)
    if user_id == 1:
        raise HTTPException(status_code=400, detail="default user cannot be deleted")
    u = db.scalar(select(User).where(User.id == user_id))
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    db.delete(u)
    db.commit()
    return {"ok": True}


def _parser_status() -> ParserStatusOut:
    global scanner
    if scanner is None:
        return ParserStatusOut(running=False, multiUser=True, userId=None)
    multi = getattr(scanner, "_multi_user", True)
    uid = getattr(scanner, "user_id", None)
    return ParserStatusOut(
        running=scanner.is_running,
        multiUser=multi,
        userId=uid,
    )


def _parser_settings_to_out() -> ParserSettingsOut:
    raw = get_all_parser_settings()
    return ParserSettingsOut(
        TG_API_ID=raw.get("TG_API_ID", ""),
        TG_API_HASH=raw.get("TG_API_HASH", ""),
        TG_SESSION_STRING=raw.get("TG_SESSION_STRING", ""),
        TG_SESSION_NAME=raw.get("TG_SESSION_NAME", ""),
        TG_BOT_TOKEN=raw.get("TG_BOT_TOKEN", ""),
        TG_CHATS=raw.get("TG_CHATS", ""),
        TG_PROXY_HOST=raw.get("TG_PROXY_HOST", ""),
        TG_PROXY_PORT=raw.get("TG_PROXY_PORT", ""),
        TG_PROXY_USER=raw.get("TG_PROXY_USER", ""),
        TG_PROXY_PASS=raw.get("TG_PROXY_PASS", ""),
        AUTO_START_SCANNER=raw.get("AUTO_START_SCANNER", ""),
        MULTI_USER_SCANNER=raw.get("MULTI_USER_SCANNER", ""),
        TG_USER_ID=raw.get("TG_USER_ID", ""),
    )


@app.get("/api/admin/parser/status", response_model=ParserStatusOut)
def get_parser_status(_: User = Depends(get_current_admin)) -> ParserStatusOut:
    return _parser_status()


@app.get("/api/admin/parser/logs")
def get_parser_logs(_: User = Depends(get_current_admin)) -> list[str]:
    """Последние 80 строк лога парсера (ошибки, старт/стоп)."""
    return get_parser_log_lines()


class ParserAuthRequestCodeBody(BaseModel):
    phone: str = Field(..., min_length=1, description="Номер телефона в формате +79...")


class ParserAuthSubmitCodeBody(BaseModel):
    code: str = Field(..., min_length=1, description="Код из Telegram")
    password: str | None = Field(None, description="Пароль 2FA, если включён")


@app.post("/api/admin/parser/auth/request-code")
async def parser_auth_request_code(
    body: ParserAuthRequestCodeBody,
    _: User = Depends(get_current_admin),
) -> dict[str, bool]:
    """Запросить код для входа в Telegram. Код придёт в приложение Telegram."""
    from telegram_auth import request_code
    try:
        await request_code(body.phone.strip())
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/parser/auth/submit-code")
async def parser_auth_submit_code(
    body: ParserAuthSubmitCodeBody,
    _: User = Depends(get_current_admin),
) -> dict[str, bool]:
    """Ввести код (и пароль 2FA при необходимости). Сессия сохранится в настройки парсера."""
    from telegram_auth import submit_code
    try:
        await submit_code(body.code.strip(), body.password.strip() if body.password else None)
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/parser/auth/status")
def parser_auth_status(_: User = Depends(get_current_admin)) -> dict[str, bool]:
    """Есть ли ожидание ввода кода (показать форму ввода кода)."""
    from telegram_auth import has_pending
    return {"pending": has_pending()}


@app.get("/api/admin/parser/settings", response_model=ParserSettingsOut)
def get_parser_settings(_: User = Depends(get_current_admin)) -> ParserSettingsOut:
    return _parser_settings_to_out()


@app.patch("/api/admin/parser/settings", response_model=ParserSettingsOut)
def update_parser_settings(
    body: ParserSettingsUpdate,
    _: User = Depends(get_current_admin),
) -> ParserSettingsOut:
    data = body.model_dump(exclude_none=True)
    save_parser_settings(data)
    return _parser_settings_to_out()


@app.post("/api/admin/parser/start", response_model=ParserStatusOut)
def start_parser(_: User = Depends(get_current_admin)) -> ParserStatusOut:
    global scanner
    from parser_log import append as parser_log_append
    if scanner is not None and scanner.is_running:
        return _parser_status()
    parser_log_append("Запуск парсера по запросу из админки.")
    multi = get_parser_setting_bool("MULTI_USER_SCANNER", True)
    if multi:
        scanner = TelegramScanner(on_mention=lambda payload: _schedule_ws_broadcast(payload))
    else:
        scanner = TelegramScanner(
            user_id=get_parser_setting_int("TG_USER_ID", 1),
            on_mention=lambda payload: _schedule_ws_broadcast(payload),
        )
    scanner.start()
    parser_log_append("Парсер запущен.")
    return _parser_status()


@app.post("/api/admin/parser/stop", response_model=ParserStatusOut)
def stop_parser(_: User = Depends(get_current_admin)) -> ParserStatusOut:
    global scanner
    from parser_log import append as parser_log_append
    if scanner is not None:
        scanner.stop()
        scanner = None
        parser_log_append("Парсер остановлен.")
    return _parser_status()


@app.get("/api/chats/available", response_model=list[ChatAvailableOut])
def list_available_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatAvailableOut]:
    """Глобальные каналы (добавленные администратором), доступные для подписки."""
    _ensure_default_user(db)
    rows = db.scalars(
        select(Chat).where(Chat.is_global.is_(True)).order_by(Chat.id.asc())
    ).all()
    sub_ids = set(
        db.execute(
            select(user_chat_subscriptions.c.chat_id).where(user_chat_subscriptions.c.user_id == user.id)
        ).scalars().all()
    )
    out: list[ChatAvailableOut] = []
    for c in rows:
        created_at = c.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        ident_display = (
            (c.username or "")
            or (str(c.tg_chat_id) if c.tg_chat_id is not None else "")
            or (f"t.me/joinchat/{c.invite_hash}" if getattr(c, "invite_hash", None) else "")
        ) or "—"
        out.append(
            ChatAvailableOut(
                id=c.id,
                identifier=ident_display,
                title=c.title,
                description=c.description,
                enabled=bool(c.enabled),
                subscribed=c.id in sub_ids,
                createdAt=created_at.isoformat(),
            )
        )
    return out


@app.post("/api/chats/subscribe-by-identifier", response_model=ChatOut)
def subscribe_by_identifier(
    body: SubscribeByIdentifierBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatOut:
    """Подписаться на глобальный канал по ссылке, @username или chat_id."""
    _ensure_default_user(db)
    username, tg_chat_id, invite_hash = _parse_chat_identifier(body.identifier)

    c = None
    if tg_chat_id is not None:
        c = db.scalar(
            select(Chat).where(
                Chat.is_global.is_(True),
                Chat.tg_chat_id == tg_chat_id,
            )
        )
    if c is None and username:
        c = db.scalar(
            select(Chat).where(
                Chat.is_global.is_(True),
                Chat.username == username,
            )
        )
    if c is None and invite_hash:
        c = db.scalar(
            select(Chat).where(
                Chat.is_global.is_(True),
                Chat.invite_hash == invite_hash,
            )
        )
    if not c:
        raise HTTPException(
            status_code=404,
            detail="Канал не найден среди доступных. Добавьте свой канал выше или попросите администратора добавить его в список доступных.",
        )
    existing = db.execute(
        select(user_chat_subscriptions).where(
            user_chat_subscriptions.c.user_id == user.id,
            user_chat_subscriptions.c.chat_id == c.id,
        )
    ).first()
    if existing:
        return _chat_to_out(c, is_owner=False)
    db.execute(user_chat_subscriptions.insert().values(user_id=user.id, chat_id=c.id))
    db.commit()
    db.refresh(c)
    return _chat_to_out(c, is_owner=False)


@app.post("/api/chats/{chat_id}/subscribe", response_model=ChatOut)
def subscribe_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatOut:
    c = db.scalar(select(Chat).where(Chat.id == chat_id))
    if not c:
        raise HTTPException(status_code=404, detail="chat not found")
    if not c.is_global:
        raise HTTPException(status_code=400, detail="only global channels can be subscribed to")
    existing = db.execute(
        select(user_chat_subscriptions).where(
            user_chat_subscriptions.c.user_id == user.id,
            user_chat_subscriptions.c.chat_id == chat_id,
        )
    ).first()
    if existing:
        return _chat_to_out(c, is_owner=False)
    db.execute(
        user_chat_subscriptions.insert().values(user_id=user.id, chat_id=chat_id)
    )
    db.commit()
    db.refresh(c)
    return _chat_to_out(c, is_owner=False)


@app.delete("/api/chats/{chat_id}/unsubscribe")
def unsubscribe_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    deleted = db.execute(
        user_chat_subscriptions.delete().where(
            user_chat_subscriptions.c.user_id == user.id,
            user_chat_subscriptions.c.chat_id == chat_id,
        )
    )
    db.commit()
    if deleted.rowcount == 0:
        raise HTTPException(status_code=404, detail="subscription not found")
    return {"ok": True}


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    c = db.scalar(select(Chat).where(Chat.id == chat_id))
    if not c:
        raise HTTPException(status_code=404, detail="chat not found")
    if c.user_id != user.id:
        # Пользователь не владелец: если он подписан на глобальный канал — отписать
        if c.is_global:
            r = db.execute(
                user_chat_subscriptions.delete().where(
                    user_chat_subscriptions.c.user_id == user.id,
                    user_chat_subscriptions.c.chat_id == chat_id,
                )
            )
            db.commit()
            if r.rowcount:
                return {"ok": True}
        raise HTTPException(status_code=403, detail="forbidden")
    db.delete(c)
    db.commit()
    return {"ok": True}


@app.get("/api/mentions", response_model=list[MentionOut])
def list_mentions(
    user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    unreadOnly: bool = False,
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> list[MentionOut]:
    _ensure_default_user(db)
    limit = max(1, min(500, limit))
    offset = max(0, offset)
    stmt = select(Mention).where(Mention.user_id == user.id)
    if unreadOnly:
        stmt = stmt.where(Mention.is_read.is_(False))
    if keyword is not None and keyword.strip():
        stmt = stmt.where(Mention.keyword_text == keyword.strip())
    rows = (
        db.scalars(
            stmt.order_by(desc(Mention.created_at)).offset(offset).limit(limit)
        ).all()
    )
    return [_mention_to_front(m) for m in rows][::-1]


_EXPORT_MAX = 10_000


@app.get("/api/mentions/export")
def export_mentions_csv(
    user: User = Depends(get_current_user),
    keyword: str | None = None,
    leadsOnly: bool = False,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    db: Session = Depends(get_db),
) -> Response:
    _ensure_default_user(db)
    stmt = select(Mention).where(Mention.user_id == user.id)
    if keyword is not None and keyword.strip():
        stmt = stmt.where(Mention.keyword_text == keyword.strip())
    if leadsOnly:
        stmt = stmt.where(Mention.is_lead.is_(True))
    if dateFrom:
        try:
            dt_from = datetime.fromisoformat(dateFrom.replace("Z", "+00:00"))
            if dt_from.tzinfo is None:
                dt_from = dt_from.replace(tzinfo=timezone.utc)
            stmt = stmt.where(Mention.created_at >= dt_from)
        except ValueError:
            pass
    if dateTo:
        try:
            dt_to = datetime.fromisoformat(dateTo.replace("Z", "+00:00"))
            if dt_to.tzinfo is None:
                dt_to = dt_to.replace(tzinfo=timezone.utc)
            stmt = stmt.where(Mention.created_at <= dt_to)
        except ValueError:
            pass
    rows = db.scalars(
        stmt.order_by(desc(Mention.created_at)).limit(_EXPORT_MAX)
    ).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["id", "created_at", "chat", "sender", "message", "keyword", "is_lead", "is_read", "message_link"]
    )
    for m in rows:
        created = m.created_at.isoformat() if m.created_at else ""
        chat = (m.chat_name or m.chat_username or "").strip()
        sender = (m.sender_name or "").strip()
        link = _message_link(m.chat_id, m.message_id) or ""
        writer.writerow(
            [str(m.id), created, chat, sender, (m.message_text or ""), m.keyword_text, m.is_lead, m.is_read, link]
        )
    body = out.getvalue().encode("utf-8-sig")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=mentions.csv"},
    )


class MarkAllReadOut(BaseModel):
    marked: int


@app.post("/api/mentions/mark-all-read", response_model=MarkAllReadOut)
def mark_all_mentions_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarkAllReadOut:
    _ensure_default_user(db)
    result = db.execute(
        update(Mention)
        .where(Mention.user_id == user.id, Mention.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return MarkAllReadOut(marked=result.rowcount or 0)


@app.patch("/api/mentions/{mention_id}/lead", response_model=MentionOut)
def set_mention_lead(mention_id: int, body: MentionLeadPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MentionOut:
    m = db.scalar(select(Mention).where(Mention.id == mention_id))
    if not m:
        raise HTTPException(status_code=404, detail="mention not found")
    if m.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    m.is_lead = bool(body.isLead)
    db.add(m)
    db.commit()
    db.refresh(m)
    return _mention_to_front(m)


@app.patch("/api/mentions/{mention_id}/read", response_model=MentionOut)
def set_mention_read(mention_id: int, body: MentionReadPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MentionOut:
    m = db.scalar(select(Mention).where(Mention.id == mention_id))
    if not m:
        raise HTTPException(status_code=404, detail="mention not found")
    if m.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    m.is_read = bool(body.isRead)
    db.add(m)
    db.commit()
    db.refresh(m)
    return _mention_to_front(m)


@app.websocket("/ws/mentions")
async def ws_mentions(ws: WebSocket) -> None:
    # Токен в query: token=... (WebSocket не передаёт заголовки из браузера)
    token = (ws.query_params.get("token") or "").strip()
    user_id = decode_token(token) if token else None
    if user_id is None:
        await ws.close(code=4001)
        return
    await ws_manager.connect(ws)
    try:
        await ws.send_json({"type": "hello", "message": "connected"})

        # Отдаем последние упоминания сразу после коннекта (удобно для фронта)
        from database import SessionLocal

        with SessionLocal() as db:
            rows = db.scalars(
                select(Mention)
                .where(Mention.user_id == user_id)
                .order_by(desc(Mention.created_at))
                .limit(50)
            ).all()
            init_payload = [_mention_to_front(m).model_dump() for m in rows][::-1]
        await ws.send_json({"type": "init", "data": init_payload})

        while True:
            # поддерживаем соединение; фронт может слать ping/filters позже
            _ = await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)

