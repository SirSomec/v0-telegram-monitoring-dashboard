from __future__ import annotations

import asyncio
import csv
import io
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session, selectinload

from auth_utils import create_token, decode_token, hash_password, verify_password
from database import get_db, init_db
from models import Chat, ChatGroup, Keyword, Mention, NotificationSettings, PasswordResetToken, User, user_chat_subscriptions, PlanLimit
from parser import TelegramScanner
from plans import PLAN_FREE, PLAN_ORDER, get_effective_plan, get_limits
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
    useSemantic: bool = False
    userId: int | None = None


class KeywordOut(BaseModel):
    id: int
    text: str
    useSemantic: bool
    userId: int
    createdAt: str
    enabled: bool = True


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


class ChatGroupChannelOut(BaseModel):
    id: int
    identifier: str
    title: str | None


class ChatGroupAvailableOut(BaseModel):
    """Группа каналов (по тематике), созданная администратором; пользователь может подписаться на всю группу."""
    id: int
    name: str
    description: str | None
    channelCount: int
    channels: list[ChatGroupChannelOut]
    subscribed: bool  # подписан ли текущий пользователь на все каналы группы


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
    plan: str = "free"  # эффективный план (при истечении срока — free)
    planSlug: str = "free"  # назначенный тариф в БД (для отображения в админке)
    planExpiresAt: str | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    name: str | None = None
    isAdmin: bool | None = None
    plan: str | None = None  # free | basic | pro | business (только админ)
    planExpiresAt: str | None = None  # ISO datetime или null — снять срок (только админ)


class AdminSetPasswordRequest(BaseModel):
    """Установка пароля учётной записи администратором."""
    newPassword: str = Field(..., min_length=8)


class NotificationSettingsOut(BaseModel):
    notifyEmail: bool
    notifyTelegram: bool
    notifyMode: str  # all | leads_only | digest
    telegramChatId: str | None = None


class NotificationSettingsUpdate(BaseModel):
    notifyEmail: bool | None = None
    notifyTelegram: bool | None = None
    notifyMode: str | None = None  # all | leads_only | digest
    telegramChatId: str | None = None


def _group_link(chat_username: str | None) -> str | None:
    """Ссылка на группу/канал в Telegram (если есть username)."""
    if not chat_username or not str(chat_username).strip():
        return None
    uname = str(chat_username).strip().lstrip("@")
    return f"https://t.me/{uname}" if uname else None


class MentionOut(BaseModel):
    id: str
    groupName: str
    groupIcon: str
    userName: str
    userInitials: str
    userLink: str | None = None  # ссылка на профиль TG: t.me/username или tg://user?id=...
    message: str
    keyword: str
    timestamp: str
    isLead: bool
    isRead: bool
    createdAt: str
    messageLink: str | None = None
    groupLink: str | None = None  # ссылка на группу/канал t.me/chat_username


class MentionGroupOut(BaseModel):
    """Одно сообщение с перечнем всех совпавших ключевых слов."""
    id: str
    groupName: str
    groupIcon: str
    userName: str
    userInitials: str
    userLink: str | None = None
    message: str
    keywords: list[str]
    timestamp: str
    isLead: bool
    isRead: bool
    createdAt: str
    groupLink: str | None = None
    messageLink: str | None = None


class StatsOut(BaseModel):
    mentionsToday: int
    keywordsCount: int
    leadsCount: int


class PlanLimitsOut(BaseModel):
    maxGroups: int
    maxChannels: int
    maxKeywordsExact: int
    maxKeywordsSemantic: int
    maxOwnChannels: int
    label: str


class PlanUsageOut(BaseModel):
    groups: int
    channels: int
    keywordsExact: int
    keywordsSemantic: int
    ownChannels: int


class PlanOut(BaseModel):
    plan: str
    planExpiresAt: str | None
    limits: PlanLimitsOut
    usage: PlanUsageOut


class AdminPlanLimitOut(BaseModel):
    """Лимиты одного тарифа (для админки)."""
    planSlug: str
    label: str
    maxGroups: int
    maxChannels: int
    maxKeywordsExact: int
    maxKeywordsSemantic: int
    maxOwnChannels: int
    canTrack: bool


class AdminPlanLimitUpdate(BaseModel):
    """Обновление лимитов одного тарифа (админ)."""
    planSlug: str = Field(..., pattern="^(free|basic|pro|business)$")
    label: str = Field(..., min_length=1, max_length=64)
    maxGroups: int = Field(..., ge=0)
    maxChannels: int = Field(..., ge=0)
    maxKeywordsExact: int = Field(..., ge=0)
    maxKeywordsSemantic: int = Field(..., ge=0)
    maxOwnChannels: int = Field(..., ge=0)
    canTrack: bool = True


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


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=1)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
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


def _user_plan_expires_iso(u: User) -> str | None:
    expires = getattr(u, "plan_expires_at", None)
    if expires is None:
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires.isoformat()


def _user_to_out(u: User) -> UserOut:
    created_at = u.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    plan = get_effective_plan(u)
    plan_slug = getattr(u, "plan_slug", None) or "free"
    return UserOut(
        id=u.id,
        email=u.email,
        name=u.name,
        isAdmin=bool(u.is_admin),
        createdAt=created_at.isoformat(),
        plan=plan,
        planSlug=plan_slug,
        planExpiresAt=_user_plan_expires_iso(u),
    )


def _usage_counts(db: Session, user_id: int) -> dict[str, int]:
    """Текущее использование: groups, channels (всего), keywords_exact, keywords_semantic, own_channels."""
    groups = db.scalar(select(func.count(ChatGroup.id)).where(ChatGroup.user_id == user_id)) or 0
    own_chats = db.scalar(select(func.count(Chat.id)).where(Chat.user_id == user_id)) or 0
    sub_count = db.scalar(
        select(func.count()).select_from(user_chat_subscriptions).where(
            user_chat_subscriptions.c.user_id == user_id
        )
    ) or 0
    channels_total = own_chats + sub_count
    keywords_exact = (
        db.scalar(
            select(func.count(Keyword.id)).where(
                Keyword.user_id == user_id,
                Keyword.enabled.is_(True),
                Keyword.use_semantic.is_(False),
            )
        )
        or 0
    )
    keywords_semantic = (
        db.scalar(
            select(func.count(Keyword.id)).where(
                Keyword.user_id == user_id,
                Keyword.enabled.is_(True),
                Keyword.use_semantic.is_(True),
            )
        )
        or 0
    )
    return {
        "groups": groups,
        "channels": channels_total,
        "keywords_exact": keywords_exact,
        "keywords_semantic": keywords_semantic,
        "own_channels": own_chats,
    }


def _check_plan_can_track(user: User) -> None:
    """Поднимает HTTPException 403, если эффективный план не позволяет добавлять ресурсы (free)."""
    plan = get_effective_plan(user)
    if plan == PLAN_FREE:
        raise HTTPException(
            status_code=403,
            detail="Тариф «Без оплаты» позволяет только просмотр и выгрузку ранее сохранённых упоминаний. Выберите платный тариф для мониторинга.",
        )


def _check_limits(
    db: Session,
    user: User,
    *,
    delta_groups: int = 0,
    delta_channels: int = 0,
    delta_keywords_exact: int = 0,
    delta_keywords_semantic: int = 0,
    delta_own_channels: int = 0,
) -> None:
    """Проверяет, не превысят ли текущие значения + дельта лимиты плана. Поднимает HTTPException 403."""
    plan = get_effective_plan(user)
    limits = get_limits(plan, db)
    usage = _usage_counts(db, user.id)
    if usage["groups"] + delta_groups > limits["max_groups"]:
        raise HTTPException(
            status_code=403,
            detail=f"Лимит групп каналов по тарифу: {limits['max_groups']}. Сейчас: {usage['groups']}.",
        )
    if usage["channels"] + delta_channels > limits["max_channels"]:
        raise HTTPException(
            status_code=403,
            detail=f"Лимит отслеживаемых каналов по тарифу: {limits['max_channels']}. Сейчас: {usage['channels']}.",
        )
    if usage["keywords_exact"] + delta_keywords_exact > limits["max_keywords_exact"]:
        raise HTTPException(
            status_code=403,
            detail=f"Лимит ключевых слов (точное совпадение): {limits['max_keywords_exact']}. Сейчас: {usage['keywords_exact']}.",
        )
    if usage["keywords_semantic"] + delta_keywords_semantic > limits["max_keywords_semantic"]:
        raise HTTPException(
            status_code=403,
            detail=f"Лимит ключевых слов (семантика): {limits['max_keywords_semantic']}. Сейчас: {usage['keywords_semantic']}.",
        )
    if usage["own_channels"] + delta_own_channels > limits["max_own_channels"]:
        raise HTTPException(
            status_code=403,
            detail=f"Лимит самостоятельно добавляемых каналов: {limits['max_own_channels']}. Сейчас: {usage['own_channels']}.",
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


def _message_link(
    chat_id: int | None,
    message_id: int | None,
    chat_username: str | None = None,
) -> str | None:
    """Ссылка на сообщение в Telegram. Для публичных каналов — t.me/username/msg_id, иначе t.me/c/chat_part/msg_id."""
    if message_id is None:
        return None
    if chat_username and str(chat_username).strip():
        uname = str(chat_username).strip().lstrip("@")
        if uname:
            return f"https://t.me/{uname}/{message_id}"
    if chat_id is None:
        return None
    cid = abs(chat_id)
    part = cid % (10**10) if cid >= 10**10 else cid
    return f"https://t.me/c/{part}/{message_id}"


def _user_profile_link(m: Mention) -> str | None:
    """Ссылка на профиль пользователя в Telegram."""
    if getattr(m, "sender_username", None) and str(m.sender_username).strip():
        uname = str(m.sender_username).strip().lstrip("@")
        return f"https://t.me/{uname}" if uname else None
    if m.sender_id is not None:
        return f"tg://user?id={m.sender_id}"
    return None


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
        userLink=_user_profile_link(m),
        message=(m.message_text or ""),
        keyword=m.keyword_text,
        timestamp=_humanize_ru(created_at),
        isLead=bool(m.is_lead),
        isRead=bool(m.is_read),
        createdAt=created_at.isoformat(),
        messageLink=_message_link(m.chat_id, m.message_id, m.chat_username),
        groupLink=_group_link(m.chat_username),
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
            scanner = TelegramScanner(on_mention=_on_mention_callback)
        else:
            scanner = TelegramScanner(
                user_id=get_parser_setting_int("TG_USER_ID", 1),
                on_mention=_on_mention_callback,
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


def _do_notify_mention_sync(payload: dict[str, Any]) -> None:
    """Отправить уведомления о упоминании (email/Telegram) по настройкам пользователя. Вызывается из executor."""
    try:
        data = payload.get("data") or {}
        user_id = data.get("userId")
        if user_id is None:
            return
        from database import SessionLocal
        from email_sender import send_mention_notification_email
        from notify_telegram import send_mention_notification as send_telegram_mention

        with SessionLocal() as db:
            settings = db.scalar(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
            if not settings:
                return
            notify_mode = (settings.notify_mode or "all").strip()
            is_lead = data.get("isLead") is True
            if notify_mode == "leads_only" and not is_lead:
                return
            # digest пока не реализован — не шлём мгновенные уведомления
            if notify_mode == "digest":
                return

            keyword = (data.get("keyword") or "").strip()
            message = (data.get("message") or "").strip()
            message_link = data.get("messageLink") or None

            if settings.notify_email:
                user = db.scalar(select(User).where(User.id == user_id))
                if user and user.email and user.email.strip():
                    send_mention_notification_email(
                        user.email.strip(),
                        keyword or "—",
                        message,
                        message_link,
                    )
            if settings.notify_telegram and settings.telegram_chat_id and settings.telegram_chat_id.strip():
                send_telegram_mention(
                    settings.telegram_chat_id.strip(),
                    keyword or "—",
                    message,
                    message_link,
                )
    except Exception:  # не ломаем парсер из-за уведомлений
        import logging
        logging.getLogger(__name__).exception("Ошибка отправки уведомления об упоминании")


def _schedule_notify_mention(payload: dict[str, Any]) -> None:
    """Запустить отправку уведомлений в пуле потоков (не блокируя парсер)."""
    loop = main_loop
    if loop and loop.is_running():
        loop.run_in_executor(None, _do_notify_mention_sync, payload)
    else:
        try:
            _do_notify_mention_sync(payload)
        except Exception:
            pass


def _on_mention_callback(payload: dict[str, Any]) -> None:
    """Единый callback при новом упоминании: WebSocket + уведомления."""
    _schedule_ws_broadcast(payload)
    _schedule_notify_mention(payload)


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


# --- Восстановление пароля ---
RESET_TOKEN_EXPIRE_HOURS = 1
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()


@app.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Запрос на сброс пароля. Всегда возвращает 200, чтобы не раскрывать наличие email в системе.
    Если пользователь найден — создаётся токен, отправляется письмо (если настроен SMTP).
    """
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not user.password_hash:
        return {"ok": True, "message": "If an account exists, you will receive an email with instructions."}

    # Удаляем старые токены этого пользователя
    for old in db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)).all():
        db.delete(old)

    token = secrets.token_urlsafe(32)
    expires_at = _now_utc() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
    prt = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    db.add(prt)
    db.commit()

    base = (FRONTEND_URL or "").rstrip("/")
    reset_link = f"{base}/auth/reset-password?token={token}" if base else f"/auth/reset-password?token={token}"

    from email_sender import send_password_reset_email
    send_password_reset_email(user.email or email, reset_link)

    return {"ok": True, "message": "If an account exists, you will receive an email with instructions."}


@app.post("/auth/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Установка нового пароля по токену из письма. Токен одноразовый и после использования удаляется."""
    now = _now_utc()
    prt = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token == body.token.strip(),
            PasswordResetToken.expires_at > now,
        )
    )
    if not prt:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Request a new one.")

    user = db.scalar(select(User).where(User.id == prt.user_id))
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    user.password_hash = hash_password(body.newPassword)
    db.delete(prt)
    db.add(user)
    db.commit()
    return {"ok": True, "message": "Password has been reset. You can now log in."}


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


@app.get("/api/plan", response_model=PlanOut)
def get_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PlanOut:
    """Текущий тариф пользователя, лимиты и использование."""
    _ensure_default_user(db)
    plan = get_effective_plan(user)
    limits_dict = get_limits(plan, db)
    usage = _usage_counts(db, user.id)
    return PlanOut(
        plan=plan,
        planExpiresAt=_user_plan_expires_iso(user),
        limits=PlanLimitsOut(
            maxGroups=limits_dict["max_groups"],
            maxChannels=limits_dict["max_channels"],
            maxKeywordsExact=limits_dict["max_keywords_exact"],
            maxKeywordsSemantic=limits_dict["max_keywords_semantic"],
            maxOwnChannels=limits_dict["max_own_channels"],
            label=limits_dict.get("label", plan),
        ),
        usage=PlanUsageOut(
            groups=usage["groups"],
            channels=usage["channels"],
            keywordsExact=usage["keywords_exact"],
            keywordsSemantic=usage["keywords_semantic"],
            ownChannels=usage["own_channels"],
        ),
    )


def _get_or_create_notification_settings(db: Session, user_id: int) -> NotificationSettings:
    settings = db.scalar(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
    if settings:
        return settings
    settings = NotificationSettings(
        user_id=user_id,
        notify_email=True,
        notify_telegram=False,
        notify_mode="all",
        telegram_chat_id=None,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


@app.get("/api/notifications/settings", response_model=NotificationSettingsOut)
def get_notification_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> NotificationSettingsOut:
    _ensure_default_user(db)
    s = _get_or_create_notification_settings(db, user.id)
    return NotificationSettingsOut(
        notifyEmail=bool(s.notify_email),
        notifyTelegram=bool(s.notify_telegram),
        notifyMode=(s.notify_mode or "all"),
        telegramChatId=s.telegram_chat_id,
    )


@app.patch("/api/notifications/settings", response_model=NotificationSettingsOut)
def update_notification_settings(
    body: NotificationSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettingsOut:
    _ensure_default_user(db)
    s = _get_or_create_notification_settings(db, user.id)
    if body.notifyEmail is not None:
        s.notify_email = bool(body.notifyEmail)
    if body.notifyTelegram is not None:
        s.notify_telegram = bool(body.notifyTelegram)
    if body.notifyMode is not None and body.notifyMode.strip() in ("all", "leads_only", "digest"):
        s.notify_mode = body.notifyMode.strip()
    if body.telegramChatId is not None:
        s.telegram_chat_id = (body.telegramChatId.strip() or None)
    db.add(s)
    db.commit()
    db.refresh(s)
    return NotificationSettingsOut(
        notifyEmail=bool(s.notify_email),
        notifyTelegram=bool(s.notify_telegram),
        notifyMode=(s.notify_mode or "all"),
        telegramChatId=s.telegram_chat_id,
    )


@app.get("/api/keywords", response_model=list[KeywordOut])
def list_keywords(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[KeywordOut]:
    _ensure_default_user(db)
    rows = (
        db.scalars(
            select(Keyword)
            .where(Keyword.user_id == user.id)
            .order_by(Keyword.enabled.desc(), Keyword.id.asc())
        )
    ).all()
    out: list[KeywordOut] = []
    for k in rows:
        created_at = k.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        out.append(
            KeywordOut(
                id=k.id,
                text=k.text,
                useSemantic=getattr(k, "use_semantic", False),
                userId=k.user_id,
                createdAt=created_at.isoformat(),
                enabled=getattr(k, "enabled", True),
            )
        )
    return out


@app.post("/api/keywords", response_model=KeywordOut)
def create_keyword(body: KeywordCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> KeywordOut:
    _ensure_default_user(db)
    user_id = user.id
    _check_plan_can_track(user)
    use_semantic = getattr(body, "useSemantic", False)
    _check_limits(
        db,
        user,
        delta_keywords_exact=0 if use_semantic else 1,
        delta_keywords_semantic=1 if use_semantic else 0,
    )

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # Не дублируем по (user_id, text); при наличии отключённого — включаем (восстановление)
    existing = db.scalar(select(Keyword).where(Keyword.user_id == user_id, Keyword.text == text))
    if existing:
        if not getattr(existing, "enabled", True):
            _check_limits(
                db,
                user,
                delta_keywords_exact=0 if getattr(existing, "use_semantic", False) else 1,
                delta_keywords_semantic=1 if getattr(existing, "use_semantic", False) else 0,
            )
            existing.enabled = True
            db.commit()
            db.refresh(existing)
        created_at = existing.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return KeywordOut(
            id=existing.id,
            text=existing.text,
            useSemantic=getattr(existing, "use_semantic", False),
            userId=existing.user_id,
            createdAt=created_at.isoformat(),
            enabled=getattr(existing, "enabled", True),
        )

    use_semantic = getattr(body, "useSemantic", False)
    k = Keyword(user_id=user_id, text=text, use_semantic=use_semantic, enabled=True)
    db.add(k)
    db.commit()
    db.refresh(k)
    created_at = k.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return KeywordOut(
        id=k.id,
        text=k.text,
        useSemantic=k.use_semantic,
        userId=k.user_id,
        createdAt=created_at.isoformat(),
        enabled=True,
    )


@app.delete("/api/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    k = db.scalar(select(Keyword).where(Keyword.id == keyword_id))
    if not k:
        raise HTTPException(status_code=404, detail="keyword not found")
    if k.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    k.enabled = False
    db.commit()
    return {"ok": True}


@app.patch("/api/keywords/{keyword_id}/restore", response_model=KeywordOut)
def restore_keyword(keyword_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> KeywordOut:
    k = db.scalar(select(Keyword).where(Keyword.id == keyword_id))
    if not k:
        raise HTTPException(status_code=404, detail="keyword not found")
    if k.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    if getattr(k, "enabled", True):
        created_at = k.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return KeywordOut(
            id=k.id,
            text=k.text,
            useSemantic=getattr(k, "use_semantic", False),
            userId=k.user_id,
            createdAt=created_at.isoformat(),
            enabled=True,
        )
    _check_limits(
        db,
        user,
        delta_keywords_exact=0 if getattr(k, "use_semantic", False) else 1,
        delta_keywords_semantic=1 if getattr(k, "use_semantic", False) else 0,
    )
    k.enabled = True
    db.commit()
    db.refresh(k)
    created_at = k.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return KeywordOut(
        id=k.id,
        text=k.text,
        useSemantic=k.use_semantic,
        userId=k.user_id,
        createdAt=created_at.isoformat(),
        enabled=True,
    )


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
    _check_plan_can_track(user)

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
            _check_limits(db, user, delta_channels=1)
            db.execute(
                user_chat_subscriptions.insert().values(user_id=user_id, chat_id=existing_global.id)
            )
            db.commit()
        db.refresh(existing_global)
        return _chat_to_out(existing_global, is_owner=False)

    _check_limits(db, user, delta_channels=1, delta_own_channels=1)
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


@app.get("/api/chat-groups/available", response_model=list[ChatGroupAvailableOut])
def list_available_chat_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatGroupAvailableOut]:
    """Группы каналов по тематикам, созданные администраторами. Пользователь может подписаться на всю группу сразу."""
    _ensure_default_user(db)
    admin_ids = {u.id for u in db.scalars(select(User).where(User.is_admin.is_(True))).all()}
    if not admin_ids:
        return []
    groups = db.scalars(
        select(ChatGroup)
        .where(ChatGroup.user_id.in_(admin_ids))
        .order_by(ChatGroup.id.asc())
        .options(selectinload(ChatGroup.chats))
    ).all()
    sub_ids = set(
        db.execute(
            select(user_chat_subscriptions.c.chat_id).where(user_chat_subscriptions.c.user_id == user.id)
        ).scalars().all()
    )
    out: list[ChatGroupAvailableOut] = []
    for g in groups:
        global_chats = [c for c in (g.chats or []) if c.is_global]
        if not global_chats:
            continue
        channel_outs = []
        for c in global_chats:
            ident = (
                (c.username or "")
                or (str(c.tg_chat_id) if c.tg_chat_id is not None else "")
                or (f"t.me/joinchat/{c.invite_hash}" if getattr(c, "invite_hash", None) else "")
            ) or "—"
            channel_outs.append(ChatGroupChannelOut(id=c.id, identifier=ident, title=c.title))
        subscribed = all(c.id in sub_ids for c in global_chats)
        out.append(
            ChatGroupAvailableOut(
                id=g.id,
                name=g.name,
                description=g.description,
                channelCount=len(global_chats),
                channels=channel_outs,
                subscribed=subscribed,
            )
        )
    return out


@app.post("/api/chat-groups/{group_id}/subscribe")
def subscribe_chat_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Подписаться на все глобальные каналы в группе (мониторинг всех каналов группы сразу)."""
    _ensure_default_user(db)
    _check_plan_can_track(user)
    g = db.scalar(
        select(ChatGroup).where(ChatGroup.id == group_id).options(selectinload(ChatGroup.chats))
    )
    if not g:
        raise HTTPException(status_code=404, detail="group not found")
    admin_ids = {u.id for u in db.scalars(select(User).where(User.is_admin.is_(True))).all()}
    if g.user_id not in admin_ids:
        raise HTTPException(status_code=404, detail="group not available")
    global_chats = [c for c in (g.chats or []) if c.is_global]
    new_subs = sum(
        1
        for c in global_chats
        if not db.execute(
            select(user_chat_subscriptions).where(
                user_chat_subscriptions.c.user_id == user.id,
                user_chat_subscriptions.c.chat_id == c.id,
            )
        ).first()
    )
    if new_subs > 0:
        _check_limits(db, user, delta_channels=new_subs)
    for c in global_chats:
        existing = db.execute(
            select(user_chat_subscriptions).where(
                user_chat_subscriptions.c.user_id == user.id,
                user_chat_subscriptions.c.chat_id == c.id,
            )
        ).first()
        if not existing:
            db.execute(user_chat_subscriptions.insert().values(user_id=user.id, chat_id=c.id))
    db.commit()
    return {"ok": True, "subscribedCount": len(global_chats)}


@app.post("/api/chat-groups/{group_id}/unsubscribe")
def unsubscribe_chat_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Отписаться от всех каналов в группе."""
    _ensure_default_user(db)
    g = db.scalar(
        select(ChatGroup).where(ChatGroup.id == group_id).options(selectinload(ChatGroup.chats))
    )
    if not g:
        raise HTTPException(status_code=404, detail="group not found")
    admin_ids = {u.id for u in db.scalars(select(User).where(User.is_admin.is_(True))).all()}
    if g.user_id not in admin_ids:
        raise HTTPException(status_code=404, detail="group not available")
    global_chat_ids = [c.id for c in (g.chats or []) if c.is_global]
    if not global_chat_ids:
        return {"ok": True, "unsubscribedCount": 0}
    r = db.execute(
        user_chat_subscriptions.delete().where(
            user_chat_subscriptions.c.user_id == user.id,
            user_chat_subscriptions.c.chat_id.in_(global_chat_ids),
        )
    )
    db.commit()
    return {"ok": True, "unsubscribedCount": r.rowcount}


@app.post("/api/chat-groups", response_model=ChatGroupOut)
def create_chat_group(body: ChatGroupCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatGroupOut:
    _ensure_default_user(db)
    user_id = user.id
    _check_plan_can_track(user)
    _check_limits(db, user, delta_groups=1)

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
    return [_user_to_out(u) for u in rows]


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
    return _user_to_out(u)


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
    if body.plan is not None and body.plan.strip() in ("free", "basic", "pro", "business"):
        u.plan_slug = body.plan.strip()
    if body.planExpiresAt is not None:
        if body.planExpiresAt.strip() == "":
            u.plan_expires_at = None
        else:
            try:
                dt = datetime.fromisoformat(body.planExpiresAt.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                u.plan_expires_at = dt
            except ValueError:
                pass

    db.add(u)
    db.commit()
    db.refresh(u)
    return _user_to_out(u)


@app.patch("/api/users/{user_id}/password")
def admin_set_user_password(
    user_id: int,
    body: AdminSetPasswordRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Установить новый пароль для любой учётной записи (только администратор)."""
    _ensure_default_user(db)
    u = db.scalar(select(User).where(User.id == user_id))
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    u.password_hash = hash_password(body.newPassword)
    db.add(u)
    db.commit()
    return {"ok": True}


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


@app.get("/api/admin/plan-limits", response_model=list[AdminPlanLimitOut])
def get_admin_plan_limits(_: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[AdminPlanLimitOut]:
    """Список лимитов всех тарифов (из БД или значения по умолчанию)."""
    _ensure_default_user(db)
    out: list[AdminPlanLimitOut] = []
    for slug in PLAN_ORDER:
        limits = get_limits(slug, db)
        out.append(
            AdminPlanLimitOut(
                planSlug=slug,
                label=limits.get("label", slug),
                maxGroups=limits["max_groups"],
                maxChannels=limits["max_channels"],
                maxKeywordsExact=limits["max_keywords_exact"],
                maxKeywordsSemantic=limits["max_keywords_semantic"],
                maxOwnChannels=limits["max_own_channels"],
                canTrack=limits.get("can_track", False),
            )
        )
    return out


@app.patch("/api/admin/plan-limits", response_model=AdminPlanLimitOut)
def update_admin_plan_limit(
    body: AdminPlanLimitUpdate,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminPlanLimitOut:
    """Обновить лимиты тарифа. Создаёт или обновляет строку в plan_limits."""
    _ensure_default_user(db)
    row = db.get(PlanLimit, body.planSlug)
    if row is None:
        row = PlanLimit(
            plan_slug=body.planSlug,
            max_groups=body.maxGroups,
            max_channels=body.maxChannels,
            max_keywords_exact=body.maxKeywordsExact,
            max_keywords_semantic=body.maxKeywordsSemantic,
            max_own_channels=body.maxOwnChannels,
            label=body.label,
            can_track=body.canTrack,
        )
        db.add(row)
    else:
        row.max_groups = body.maxGroups
        row.max_channels = body.maxChannels
        row.max_keywords_exact = body.maxKeywordsExact
        row.max_keywords_semantic = body.maxKeywordsSemantic
        row.max_own_channels = body.maxOwnChannels
        row.label = body.label
        row.can_track = body.canTrack
    db.commit()
    db.refresh(row)
    return AdminPlanLimitOut(
        planSlug=row.plan_slug,
        label=row.label,
        maxGroups=row.max_groups,
        maxChannels=row.max_channels,
        maxKeywordsExact=row.max_keywords_exact,
        maxKeywordsSemantic=row.max_keywords_semantic,
        maxOwnChannels=row.max_own_channels,
        canTrack=row.can_track,
    )


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
        scanner = TelegramScanner(on_mention=_on_mention_callback)
    else:
        scanner = TelegramScanner(
            user_id=get_parser_setting_int("TG_USER_ID", 1),
            on_mention=_on_mention_callback,
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
    _check_plan_can_track(user)
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
    _check_limits(db, user, delta_channels=1)
    db.execute(user_chat_subscriptions.insert().values(user_id=user.id, chat_id=c.id))
    db.commit()
    db.refresh(c)
    return _chat_to_out(c, is_owner=False)


@app.post("/api/chats/{chat_id}/subscribe", response_model=ChatOut)
def subscribe_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatOut:
    _check_plan_can_track(user)
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
    _check_limits(db, user, delta_channels=1)
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


class MentionsCountOut(BaseModel):
    total: int


def _mentions_filter_stmt(stmt, user_id: int, unreadOnly: bool, keyword: str | None, search: str | None):
    stmt = stmt.where(Mention.user_id == user_id)
    if unreadOnly:
        stmt = stmt.where(Mention.is_read.is_(False))
    if keyword is not None and keyword.strip():
        stmt = stmt.where(Mention.keyword_text == keyword.strip())
    if search is not None and search.strip():
        stmt = stmt.where(Mention.message_text.ilike(f"%{search.strip()}%"))
    return stmt


def _group_keys():
    return [
        Mention.user_id,
        Mention.chat_id,
        Mention.message_id,
        Mention.created_at,
        Mention.message_text,
        Mention.chat_name,
        Mention.chat_username,
        Mention.sender_id,
        Mention.sender_name,
        Mention.sender_username,
    ]


def _row_to_group_out(row) -> MentionGroupOut:
    """Собрать MentionGroupOut из строки сгруппированного запроса."""
    group_name = (row.chat_name or row.chat_username or "Неизвестный чат").strip()
    user_name = (row.sender_name or "Неизвестный пользователь").strip()
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    user_link = None
    if getattr(row, "sender_username", None) and str(row.sender_username).strip():
        user_link = f"https://t.me/{str(row.sender_username).strip().lstrip('@')}"
    elif getattr(row, "sender_id", None) is not None:
        user_link = f"tg://user?id={row.sender_id}"
    keywords = list(row.keywords) if row.keywords else []
    return MentionGroupOut(
        id=str(row.id),
        groupName=group_name,
        groupIcon=_initials(group_name),
        userName=user_name,
        userInitials=_initials(user_name),
        userLink=user_link,
        message=(row.message_text or ""),
        keywords=keywords,
        timestamp=_humanize_ru(created_at),
        isLead=bool(row.is_lead),
        isRead=bool(row.is_read),
        createdAt=created_at.isoformat(),
        groupLink=_group_link(row.chat_username),
        messageLink=_message_link(row.chat_id, row.message_id, row.chat_username),
    )


@app.get("/api/mentions/count", response_model=MentionsCountOut)
def count_mentions(
    user: User = Depends(get_current_user),
    unreadOnly: bool = False,
    keyword: str | None = None,
    search: str | None = None,
    grouped: bool = False,
    db: Session = Depends(get_db),
) -> MentionsCountOut:
    _ensure_default_user(db)
    if grouped:
        stmt = (
            select(*_group_keys())
            .where(Mention.user_id == user.id)
        )
        stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search)
        subq = stmt.group_by(*_group_keys()).subquery()
        total = db.scalar(select(func.count()).select_from(subq)) or 0
    else:
        stmt = select(func.count(Mention.id))
        stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search)
        total = db.scalar(stmt) or 0
    return MentionsCountOut(total=total)


@app.get("/api/mentions", response_model=list[MentionOut] | list[MentionGroupOut])
def list_mentions(
    user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    unreadOnly: bool = False,
    keyword: str | None = None,
    search: str | None = None,
    sortOrder: Literal["desc", "asc"] = "desc",
    grouped: bool = False,
    db: Session = Depends(get_db),
) -> list[MentionOut] | list[MentionGroupOut]:
    _ensure_default_user(db)
    limit = max(1, min(500, limit))
    offset = max(0, offset)
    if grouped:
        stmt = select(
            func.min(Mention.id).label("id"),
            Mention.user_id,
            Mention.chat_id,
            Mention.message_id,
            Mention.created_at,
            Mention.message_text,
            Mention.chat_name,
            Mention.chat_username,
            Mention.sender_id,
            Mention.sender_name,
            Mention.sender_username,
            func.array_agg(Mention.keyword_text).label("keywords"),
            func.bool_or(Mention.is_lead).label("is_lead"),
            func.bool_and(Mention.is_read).label("is_read"),
        )
        stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search)
        stmt = stmt.group_by(*_group_keys())
        order = desc(Mention.created_at) if sortOrder == "desc" else Mention.created_at
        stmt = stmt.order_by(order).offset(offset).limit(limit)
        rows = db.execute(stmt).all()
        return [_row_to_group_out(row) for row in rows]
    stmt = select(Mention)
    stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search)
    order = desc(Mention.created_at) if sortOrder == "desc" else Mention.created_at
    rows = (
        db.scalars(
            stmt.order_by(order).offset(offset).limit(limit)
        ).all()
    )
    return [_mention_to_front(m) for m in rows]


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
        ["id", "created_at", "chat", "sender", "message", "keyword", "is_lead", "is_read", "user_link"]
    )
    for m in rows:
        created = m.created_at.isoformat() if m.created_at else ""
        chat = (m.chat_name or m.chat_username or "").strip()
        sender = (m.sender_name or "").strip()
        user_link = _user_profile_link(m) or ""
        writer.writerow(
            [str(m.id), created, chat, sender, (m.message_text or ""), m.keyword_text, m.is_lead, m.is_read, user_link]
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


def _same_group_where(m: Mention):
    """Условие WHERE: те же user_id, chat_id, message_id, created_at (одно сообщение — одна группа)."""
    return (
        Mention.user_id == m.user_id,
        Mention.chat_id == m.chat_id,
        Mention.message_id == m.message_id,
        Mention.created_at == m.created_at,
    )


@app.patch("/api/mentions/{mention_id}/lead", response_model=MentionOut)
def set_mention_lead(mention_id: int, body: MentionLeadPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MentionOut:
    m = db.scalar(select(Mention).where(Mention.id == mention_id))
    if not m:
        raise HTTPException(status_code=404, detail="mention not found")
    if m.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    where_clauses = _same_group_where(m)
    db.execute(update(Mention).where(*where_clauses).values(is_lead=bool(body.isLead)))
    db.commit()
    db.refresh(m)
    if body.isLead:
        payload = {
            "type": "mention",
            "data": {
                "userId": m.user_id,
                "keyword": m.keyword_text,
                "message": m.message_text or "",
                "messageLink": _message_link(m.chat_id, m.message_id, m.chat_username),
                "isLead": True,
            },
        }
        _schedule_notify_mention(payload)
    return _mention_to_front(m)


@app.patch("/api/mentions/{mention_id}/read", response_model=MentionOut)
def set_mention_read(mention_id: int, body: MentionReadPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MentionOut:
    m = db.scalar(select(Mention).where(Mention.id == mention_id))
    if not m:
        raise HTTPException(status_code=404, detail="mention not found")
    if m.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    where_clauses = _same_group_where(m)
    db.execute(update(Mention).where(*where_clauses).values(is_read=bool(body.isRead)))
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

