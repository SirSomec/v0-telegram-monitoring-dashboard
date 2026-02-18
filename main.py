from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import Chat, Keyword, Mention, User
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
    enabled: bool = True
    userId: int | None = None


class ChatOut(BaseModel):
    id: int
    identifier: str
    title: str | None
    enabled: bool
    userId: int
    createdAt: str


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
    user = User(id=1, email=None, name="Default")
    db.add(user)
    db.commit()
    db.refresh(user)
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


@app.get("/api/keywords", response_model=list[KeywordOut])
def list_keywords(userId: int = 1, db: Session = Depends(get_db)) -> list[KeywordOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(Keyword).where(Keyword.user_id == userId).order_by(Keyword.id.asc())).all()
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
def create_keyword(body: KeywordCreate, db: Session = Depends(get_db)) -> KeywordOut:
    user_id = body.userId or 1
    _ensure_default_user(db)

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
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    k = db.scalar(select(Keyword).where(Keyword.id == keyword_id))
    if not k:
        raise HTTPException(status_code=404, detail="keyword not found")
    db.delete(k)
    db.commit()
    return {"ok": True}


@app.get("/api/chats", response_model=list[ChatOut])
def list_chats(userId: int = 1, db: Session = Depends(get_db)) -> list[ChatOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(Chat).where(Chat.user_id == userId).order_by(Chat.id.asc())).all()
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
                enabled=bool(c.enabled),
                userId=c.user_id,
                createdAt=created_at.isoformat(),
            )
        )
    return out


@app.post("/api/chats", response_model=ChatOut)
def create_chat(body: ChatCreate, db: Session = Depends(get_db)) -> ChatOut:
    user_id = body.userId or 1
    _ensure_default_user(db)

    ident = body.identifier.strip()
    if not ident:
        raise HTTPException(status_code=400, detail="identifier is required")

    username: str | None = None
    tg_chat_id: int | None = None
    if ident.lstrip("-").isdigit():
        tg_chat_id = int(ident)
    else:
        username = ident.lstrip("@")

    c = Chat(user_id=user_id, username=username, tg_chat_id=tg_chat_id, title=body.title, enabled=body.enabled)
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
        enabled=bool(c.enabled),
        userId=c.user_id,
        createdAt=created_at.isoformat(),
    )


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = db.scalar(select(Chat).where(Chat.id == chat_id))
    if not c:
        raise HTTPException(status_code=404, detail="chat not found")
    db.delete(c)
    db.commit()
    return {"ok": True}


@app.get("/api/mentions", response_model=list[MentionOut])
def list_mentions(
    userId: int = 1,
    limit: int = 50,
    unreadOnly: bool = False,
    db: Session = Depends(get_db),
) -> list[MentionOut]:
    _ensure_default_user(db)
    limit = max(1, min(500, limit))
    stmt = select(Mention).where(Mention.user_id == userId)
    if unreadOnly:
        stmt = stmt.where(Mention.is_read.is_(False))
    rows = db.scalars(stmt.order_by(desc(Mention.created_at)).limit(limit)).all()
    return [_mention_to_front(m) for m in rows][::-1]


@app.patch("/api/mentions/{mention_id}/lead", response_model=MentionOut)
def set_mention_lead(mention_id: int, body: MentionLeadPatch, db: Session = Depends(get_db)) -> MentionOut:
    m = db.scalar(select(Mention).where(Mention.id == mention_id))
    if not m:
        raise HTTPException(status_code=404, detail="mention not found")
    m.is_lead = bool(body.isLead)
    db.add(m)
    db.commit()
    db.refresh(m)
    return _mention_to_front(m)


@app.patch("/api/mentions/{mention_id}/read", response_model=MentionOut)
def set_mention_read(mention_id: int, body: MentionReadPatch, db: Session = Depends(get_db)) -> MentionOut:
    m = db.scalar(select(Mention).where(Mention.id == mention_id))
    if not m:
        raise HTTPException(status_code=404, detail="mention not found")
    m.is_read = bool(body.isRead)
    db.add(m)
    db.commit()
    db.refresh(m)
    return _mention_to_front(m)


@app.websocket("/ws/mentions")
async def ws_mentions(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    try:
        await ws.send_json({"type": "hello", "message": "connected"})

        # Отдаем последние упоминания сразу после коннекта (удобно для фронта)
        user_id = int(ws.query_params.get("userId", "1"))
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

