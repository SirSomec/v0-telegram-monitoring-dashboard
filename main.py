from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from auth_utils import create_token, decode_token, hash_password, verify_password
from database import get_db, init_db
from models import Chat, ChatGroup, Keyword, Mention, User
from parser import TelegramScanner


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


class ChatOut(BaseModel):
    id: int
    identifier: str
    title: str | None
    description: str | None
    groupIds: list[int]
    enabled: bool
    userId: int
    createdAt: str


class ChatUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    enabled: bool | None = None
    groupIds: list[int] | None = None


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


app = FastAPI(title="Telegram Monitoring Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
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

    # Сканер можно включить через ENV AUTO_START_SCANNER=1
    import os

    if os.getenv("AUTO_START_SCANNER", "").strip() in {"1", "true", "True", "yes", "YES"}:
        scanner = TelegramScanner(
            user_id=int(os.getenv("TG_USER_ID", "1")),
            on_mention=lambda payload: _schedule_ws_broadcast(payload),
        )
        scanner.start()


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


@app.get("/api/chats", response_model=list[ChatOut])
def list_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(Chat).where(Chat.user_id == user.id).order_by(Chat.id.asc())).all()
    out: list[ChatOut] = []
    for c in rows:
        identifier = c.username or (str(c.tg_chat_id) if c.tg_chat_id is not None else "")
        created_at = c.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        out.append(
            ChatOut(
                id=c.id,
                identifier=identifier,
                title=c.title,
                description=c.description,
                groupIds=[g.id for g in (c.groups or [])],
                enabled=bool(c.enabled),
                userId=c.user_id,
                createdAt=created_at.isoformat(),
            )
        )
    return out


@app.post("/api/chats", response_model=ChatOut)
def create_chat(body: ChatCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatOut:
    _ensure_default_user(db)
    user_id = user.id

    ident = body.identifier.strip()
    if not ident:
        raise HTTPException(status_code=400, detail="identifier is required")

    username: str | None = None
    tg_chat_id: int | None = None
    if ident.lstrip("-").isdigit():
        tg_chat_id = int(ident)
    else:
        username = ident.lstrip("@")

    c = Chat(
        user_id=user_id,
        username=username,
        tg_chat_id=tg_chat_id,
        title=body.title,
        description=body.description,
        enabled=body.enabled,
    )

    if body.groupIds:
        groups = db.scalars(select(ChatGroup).where(ChatGroup.user_id == user_id, ChatGroup.id.in_(body.groupIds))).all()
        c.groups = list(groups)
    db.add(c)
    db.commit()
    db.refresh(c)

    identifier = c.username or (str(c.tg_chat_id) if c.tg_chat_id is not None else "")
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
        createdAt=created_at.isoformat(),
    )


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

    if body.groupIds is not None:
        groups = db.scalars(
            select(ChatGroup).where(ChatGroup.user_id == c.user_id, ChatGroup.id.in_(body.groupIds))
        ).all()
        c.groups = list(groups)

    db.add(c)
    db.commit()
    db.refresh(c)

    identifier = c.username or (str(c.tg_chat_id) if c.tg_chat_id is not None else "")
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
        createdAt=created_at.isoformat(),
    )


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


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    c = db.scalar(select(Chat).where(Chat.id == chat_id))
    if not c:
        raise HTTPException(status_code=404, detail="chat not found")
    if c.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    db.delete(c)
    db.commit()
    return {"ok": True}


@app.get("/api/mentions", response_model=list[MentionOut])
def list_mentions(
    user: User = Depends(get_current_user),
    limit: int = 50,
    unreadOnly: bool = False,
    db: Session = Depends(get_db),
) -> list[MentionOut]:
    _ensure_default_user(db)
    limit = max(1, min(500, limit))
    stmt = select(Mention).where(Mention.user_id == user.id)
    if unreadOnly:
        stmt = stmt.where(Mention.is_read.is_(False))
    rows = db.scalars(stmt.order_by(desc(Mention.created_at)).limit(limit)).all()
    return [_mention_to_front(m) for m in rows][::-1]


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

