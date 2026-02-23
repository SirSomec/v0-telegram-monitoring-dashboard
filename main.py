from __future__ import annotations

import asyncio
import csv
import io
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, selectinload

from auth_utils import create_token, decode_token, hash_password, verify_password
from database import get_db, init_db
from models import Chat, ChatGroup, Keyword, Mention, NotificationSettings, PasswordResetToken, User, user_chat_subscriptions, user_thematic_group_subscriptions, PlanLimit, SupportTicket, SupportMessage, SupportAttachment, CHAT_SOURCE_TELEGRAM, CHAT_SOURCE_MAX
from parser import TelegramScanner
from parser_max import MaxScanner
from plans import PLAN_BASIC, PLAN_FREE, PLAN_ORDER, get_effective_plan, get_limits
from parser_config import (
    get_all_parser_settings,
    get_parser_setting_bool,
    get_parser_setting_int,
    save_parser_settings,
)
from parser_log import get_lines as get_parser_log_lines
import notify_telegram
import support_uploads


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
    identifier: str = Field(..., min_length=1, max_length=256, description="username (@name), chat_id или ID чата MAX")
    title: str | None = None
    description: str | None = None
    groupIds: list[int] = Field(default_factory=list)
    enabled: bool = True
    userId: int | None = None
    isGlobal: bool | None = None  # только для админа: канал доступен всем пользователям
    source: Literal["telegram", "max"] = "telegram"


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
    source: str = "telegram"
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
    groupNames: list[str]  # названия групп (тематик), в которые входит канал
    enabled: bool
    subscribed: bool  # подписан ли текущий пользователь
    subscriptionEnabled: bool | None  # при подписке — включён ли мониторинг у пользователя
    createdAt: str


class SubscribeByIdentifierBody(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=256, description="@username или числовой chat_id")


class SubscriptionUpdateBody(BaseModel):
    enabled: bool


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
    clearTelegramChatId: bool | None = None  # true — сбросить Chat ID (вместе с пустым telegramChatId)


class SemanticSettingsOut(BaseModel):
    """Настройки семантического поиска пользователя."""
    semanticThreshold: float | None = None  # 0–1, порог срабатывания; None = глобальный
    semanticMinTopicPercent: float | None = None  # 0–100, ниже — не учитывать; None = не фильтровать


class SemanticSettingsUpdate(BaseModel):
    semanticThreshold: float | None = None  # 0–1
    semanticMinTopicPercent: float | None = None  # 0–100


# --- Поддержка (обращения пользователей) ---

class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=300)
    message: str = Field(..., min_length=1, max_length=10000)


class SupportMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class SupportAttachmentOut(BaseModel):
    id: int
    supportMessageId: int
    originalFilename: str
    contentType: str | None = None
    sizeBytes: int
    createdAt: str


class SupportMessageOut(BaseModel):
    id: int
    ticketId: int
    senderId: int
    isFromStaff: bool
    body: str
    createdAt: str
    attachments: list[SupportAttachmentOut] = []


class SupportTicketOut(BaseModel):
    id: int
    userId: int
    userEmail: str | None = None
    userName: str | None = None
    subject: str
    status: str  # open | answered | closed
    createdAt: str
    updatedAt: str
    messageCount: int = 0
    lastMessageAt: str | None = None
    hasUnread: bool = False  # у владельца есть непрочитанный ответ от поддержки


class SupportTicketDetailOut(SupportTicketOut):
    messages: list[SupportMessageOut] = []


class SupportTicketStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|answered|closed)$")


def _notify_admins_support(
    db: Session,
    ticket_id: int,
    user_email: str | None,
    user_name: str | None,
    subject: str,
    message_preview: str,
) -> None:
    """Отправить уведомление в Telegram всем администраторам, у которых настроен telegram_chat_id."""
    try:
        admin_ids = [u.id for u in db.scalars(select(User).where(User.is_admin.is_(True))).all()]
        for uid in admin_ids:
            settings = db.scalar(select(NotificationSettings).where(NotificationSettings.user_id == uid))
            if not settings or not settings.telegram_chat_id or not settings.telegram_chat_id.strip():
                continue
            notify_telegram.send_support_notification(
                settings.telegram_chat_id.strip(),
                ticket_id,
                user_email,
                user_name,
                subject,
                message_preview,
            )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Ошибка уведомления админов о поддержке")


def _notify_user_support_reply(db: Session, ticket: SupportTicket, reply_preview: str) -> None:
    """Уведомить владельца тикета об ответе поддержки (email + Telegram по настройкам)."""
    try:
        owner = db.scalar(select(User).where(User.id == ticket.user_id))
        if not owner:
            return
        settings = db.scalar(select(NotificationSettings).where(NotificationSettings.user_id == ticket.user_id))
        if settings and settings.notify_email and owner.email and owner.email.strip():
            from email_sender import send_support_reply_email
            send_support_reply_email(
                owner.email.strip(),
                ticket.subject,
                reply_preview,
            )
        if settings and settings.notify_telegram and settings.telegram_chat_id and settings.telegram_chat_id.strip():
            notify_telegram.send_support_reply_to_user(
                settings.telegram_chat_id.strip(),
                ticket.subject,
                reply_preview,
            )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Ошибка уведомления пользователя об ответе поддержки")


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
    source: str = "telegram"
    topicMatchPercent: int | None = None  # % совпадения с темой (семантика), 0–100


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
    """Фрагменты сообщения, давшие семантическое совпадение (в том же порядке, что и keywords); для подсветки."""
    matchedSpans: list[str | None] | None = None
    timestamp: str
    isLead: bool
    isRead: bool
    createdAt: str
    groupLink: str | None = None
    messageLink: str | None = None
    source: str = "telegram"
    topicMatchPercent: int | None = None  # макс. % совпадения с темой по семантике среди ключей


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
    maxRunning: bool = False


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
    # MAX messenger
    MAX_ACCESS_TOKEN: str = ""
    MAX_BASE_URL: str = ""
    MAX_POLL_INTERVAL_SEC: str = ""
    AUTO_START_MAX_SCANNER: str = ""
    # Семантический анализ
    SEMANTIC_PROVIDER: str = ""
    SEMANTIC_SERVICE_URL: str = ""
    SEMANTIC_MODEL_NAME: str = ""
    SEMANTIC_SIMILARITY_THRESHOLD: str = ""


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
    # MAX messenger
    MAX_ACCESS_TOKEN: str | None = None
    MAX_BASE_URL: str | None = None
    MAX_POLL_INTERVAL_SEC: int | None = None
    AUTO_START_MAX_SCANNER: bool | None = None
    # Семантический анализ
    SEMANTIC_PROVIDER: str | None = None
    SEMANTIC_SERVICE_URL: str | None = None
    SEMANTIC_MODEL_NAME: str | None = None
    SEMANTIC_SIMILARITY_THRESHOLD: str | None = None

    @field_validator("TG_USER_ID", "MAX_POLL_INTERVAL_SEC", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip() == "":
            return None
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                return None
        return None


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._ws_user_ids: dict[WebSocket, int] = {}

    async def connect(self, ws: WebSocket, user_id: int | None = None) -> None:
        await ws.accept()
        self._connections.add(ws)
        if user_id is not None:
            self._ws_user_ids[ws] = user_id

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        self._ws_user_ids.pop(ws, None)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws, uid in list(self._ws_user_ids.items()):
            if uid != user_id:
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


def _cors_config() -> dict:
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    # Старый дефолт из docker-compose — разрешаем любой origin (работает доступ по домену и по IP)
    if raw == "http://localhost:3000,http://127.0.0.1:3000":
        raw = ""
    if raw:
        origins = [x.strip() for x in raw.split(",") if x.strip()]
        return {"allow_origins": origins, "allow_origin_regex": None}
    # Пусто или не задано — разрешаем любой origin (https?://.*)
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
max_scanner: MaxScanner | None = None
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
    """Текущее использование: groups, channels (всего), keywords_exact, keywords_semantic, own_channels.
    groups = свои группы + подписанные тематические (записи в user_thematic_group_subscriptions)."""
    own_groups = db.scalar(select(func.count(ChatGroup.id)).where(ChatGroup.user_id == user_id)) or 0
    subscribed_thematic = (
        db.scalar(
            select(func.count()).select_from(user_thematic_group_subscriptions).where(
                user_thematic_group_subscriptions.c.user_id == user_id
            )
        )
        or 0
    )
    groups = own_groups + subscribed_thematic
    own_chats = db.scalar(select(func.count(Chat.id)).where(Chat.user_id == user_id)) or 0
    # В лимит каналов входят только индивидуальные подписки (via_group_id IS NULL); подписки через группы не считаются
    sub_count_individual = (
        db.scalar(
            select(func.count()).select_from(user_chat_subscriptions).where(
                user_chat_subscriptions.c.user_id == user_id,
                user_chat_subscriptions.c.via_group_id.is_(None),
            )
        )
        or 0
    )
    channels_total = own_chats + sub_count_individual
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
    """Ссылка на сообщение в Telegram.
    Публичные: https://t.me/username/msg_id (работает в браузере и в приложении).
    Приватные: tg://privatepost (открывает приложение TG: если пользователь в группе — сообщение, иначе — чат/вступить).
    """
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
    return f"tg://privatepost?channel={part}&post={message_id}"


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
    source = getattr(m, "source", None) or CHAT_SOURCE_TELEGRAM
    sim = getattr(m, "semantic_similarity", None)
    topic_pct = round(sim * 100) if sim is not None else None
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
        source=source,
        topicMatchPercent=topic_pct,
    )


@app.on_event("startup")
async def on_startup() -> None:
    global scanner, max_scanner, main_loop
    main_loop = asyncio.get_running_loop()
    init_db()
    import logging
    _startup_log = logging.getLogger(__name__)
    if notify_telegram.is_configured():
        _startup_log.info("Уведомления в Telegram: бот настроен (NOTIFY_TELEGRAM_BOT_TOKEN задан)")
    else:
        _startup_log.warning("Уведомления в Telegram отключены: NOTIFY_TELEGRAM_BOT_TOKEN не задан в окружении")

    # Создаем пользователя “по умолчанию”, чтобы CRUD можно было сразу дергать.
    # (Фронт пока без авторизации/токенов.)
    from database import SessionLocal

    with SessionLocal() as db:
        _ensure_default_user(db)

    # Сканер можно включить через настройки (админ) или ENV AUTO_START_SCANNER=1
    global max_scanner
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

    if get_parser_setting_bool("AUTO_START_MAX_SCANNER", False):
        from parser_log import append as parser_log_append
        parser_log_append("[MAX] Автозапуск парсера MAX при старте API.")
        max_scanner = MaxScanner(on_mention=_on_mention_callback)
        max_scanner.start()
        parser_log_append("[MAX] Парсер MAX запущен (автостарт).")

    # Очистка вложений поддержки старше 30 дней — при старте и раз в сутки
    async def _support_attachments_cleanup_loop() -> None:
        import logging
        log = logging.getLogger(__name__)
        try:
            await asyncio.get_running_loop().run_in_executor(None, _cleanup_expired_support_attachments)
        except Exception:
            log.exception("Ошибка очистки вложений поддержки при старте")
        while True:
            await asyncio.sleep(3600 * 24)  # 24 часа
            try:
                await asyncio.get_running_loop().run_in_executor(None, _cleanup_expired_support_attachments)
                log.info("Очистка вложений поддержки (старше %s дн.) выполнена", support_uploads.RETENTION_DAYS)
            except Exception:
                log.exception("Ошибка очистки вложений поддержки")

    asyncio.create_task(_support_attachments_cleanup_loop())


# Троттлинг WS: при пачке упоминаний не планируем сотни broadcast-корутин, а сбрасываем раз в 80 ms
_ws_pending: list[dict[str, Any]] = []
_ws_lock = threading.Lock()
_ws_flush_scheduled = False


async def _ws_broadcast_flush() -> None:
    global _ws_flush_scheduled  # noqa: PLW0603
    await asyncio.sleep(0.08)
    with _ws_lock:
        to_send = _ws_pending[:]
        _ws_pending.clear()
        _ws_flush_scheduled = False
    for p in to_send:
        if p.get("type") == "mention":
            uid = (p.get("data") or {}).get("userId")
            if uid is not None:
                await ws_manager.broadcast_to_user(int(uid), p)
            else:
                await ws_manager.broadcast(p)
        else:
            await ws_manager.broadcast(p)
    with _ws_lock:
        if _ws_pending and not _ws_flush_scheduled:
            _ws_flush_scheduled = True
            asyncio.create_task(_ws_broadcast_flush())


def _schedule_ws_broadcast(payload: dict[str, Any]) -> None:
    # Callback из фонового потока (Telethon) -> отправляем в WS асинхронно (с троттлингом).
    global _ws_flush_scheduled  # noqa: PLW0603
    loop = main_loop
    if loop and loop.is_running():
        with _ws_lock:
            _ws_pending.append(payload)
            if not _ws_flush_scheduled:
                _ws_flush_scheduled = True
                asyncio.run_coroutine_threadsafe(_ws_broadcast_flush(), loop)
    else:
        try:
            asyncio.run(ws_manager.broadcast(payload))
        except Exception:
            pass


def _on_mention_callback(payload: dict[str, Any]) -> None:
    """Callback при новом упоминании: только рассылка в WebSocket (уведомления email/Telegram — через mention_notifications по mention_id)."""
    try:
        _schedule_ws_broadcast(payload)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Ошибка WebSocket при упоминании: %s", e)
        try:
            from parser_log import append as parser_log_append
            parser_log_append(f"WebSocket упоминание: ошибка — {type(e).__name__}: {e}")
        except Exception:
            pass


@app.get("/health")
def health() -> dict[str, Any]:
    """Проверка доступности API и статуса парсера (running = сервис онлайн в дашборде)."""
    parser = _parser_status()
    return {"status": "ok", "parser_running": parser.running}


def _telegram_chat_registered(db: Session, chat_id: int | str) -> bool:
    """Проверить, добавлен ли chat_id в настройках уведомлений какого-либо пользователя (личный кабинет)."""
    sid = str(chat_id).strip()
    row = db.scalar(
        select(NotificationSettings).where(
            NotificationSettings.telegram_chat_id.isnot(None),
            func.trim(NotificationSettings.telegram_chat_id) == sid,
        )
    )
    return row is not None


@app.post("/api/telegram-webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Webhook для бота @telescopemsg_bot: при /start проверяем, добавлен ли пользователь в личном кабинете;
    если нет — инструкция и кнопка «Проверить».
    """
    if not notify_telegram.is_configured():
        return {"ok": True}
    try:
        body = await request.json()
    except Exception:
        return {"ok": False}
    # Обработка /start
    message = body.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is not None and text == "/start":
        registered = _telegram_chat_registered(db, chat_id)
        if registered:
            notify_telegram.send_message(
                chat_id,
                "✅ Вы зарегистрированы в личном кабинете. Уведомления о упоминаниях будут приходить сюда.",
            )
        else:
            instructions = (
                f"Чтобы получать уведомления, добавьте свой Telegram в личном кабинете:\n\n"
                f"1. Войдите в дашборд (сайт мониторинга).\n"
                f"2. Откройте раздел «Уведомления».\n"
                f"3. Включите «Telegram» и в поле «ID чата или @username» укажите ваш Chat ID: {chat_id}\n\n"
                f"4. Сохраните настройки и нажмите кнопку «Проверить» ниже."
            )
            notify_telegram.send_message(
                chat_id,
                instructions,
                reply_markup={"inline_keyboard": [[{"text": "Проверить", "callback_data": "check_registration"}]]},
            )
        return {"ok": True}
    # Обработка нажатия «Проверить»
    callback = body.get("callback_query") or {}
    if callback.get("data") == "check_registration" and callback.get("id"):
        cb_id = callback["id"]
        msg = callback.get("message") or {}
        cb_chat_id = (msg.get("chat") or {}).get("id")
        if cb_chat_id is None:
            notify_telegram.answer_callback_query(cb_id, "Ошибка")
            return {"ok": True}
        notify_telegram.answer_callback_query(cb_id)
        registered = _telegram_chat_registered(db, cb_chat_id)
        if registered:
            notify_telegram.send_message(
                cb_chat_id,
                "✅ Вы зарегистрированы. Уведомления о упоминаниях будут приходить сюда.",
            )
        else:
            notify_telegram.send_message(
                cb_chat_id,
                "Пока не найдено. Убедитесь, что в личном кабинете в разделе «Уведомления» вы указали этот Chat ID и сохранили настройки, затем нажмите «Проверить» снова.",
                reply_markup={"inline_keyboard": [[{"text": "Проверить", "callback_data": "check_registration"}]]},
            )
        return {"ok": True}
    return {"ok": True}


@app.post("/auth/register", response_model=AuthResponse)
def auth_register(body: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    _ensure_default_user(db)
    existing = db.scalar(select(User).where(User.email == body.email.strip()))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    # Первый зарегистрированный пользователь получает права админа
    count = db.scalar(select(func.count(User.id)).where(User.password_hash.isnot(None))) or 0
    is_first_user = count == 0
    # Новым пользователям назначается базовый тариф на 7 дней
    plan_expires_at = _now_utc() + timedelta(days=7)
    user = User(
        email=body.email.strip(),
        name=(body.name or "").strip() or None,
        password_hash=hash_password(body.password),
        is_admin=is_first_user,
        plan_slug=PLAN_BASIC,
        plan_expires_at=plan_expires_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(token=create_token(user.id), user=_user_to_out(user))


@app.post("/auth/login", response_model=AuthResponse)
def auth_login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    import logging
    try:
        _ensure_default_user(db)
        user = db.scalar(select(User).where(User.email == body.email.strip()))
        if not user or not user.password_hash:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return AuthResponse(token=create_token(user.id), user=_user_to_out(user))
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger(__name__).exception("auth/login error: %s", e)
        raise HTTPException(status_code=500, detail="Ошибка входа. Проверьте логи бэкенда.")


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


@app.get("/api/notifications/telegram-status")
def get_telegram_notify_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Статус для отладки: настроен ли бот, задан ли chat_id, совпадает ли user id с парсером."""
    _ensure_default_user(db)
    s = _get_or_create_notification_settings(db, user.id)
    chat_id = (s.telegram_chat_id or "").strip()
    multi = get_parser_setting_bool("MULTI_USER_SCANNER", True)
    parser_user_id = None if multi else get_parser_setting_int("TG_USER_ID", 1)
    return {
        "botConfigured": notify_telegram.is_configured(),
        "telegramEnabled": bool(s.notify_telegram),
        "chatIdSet": bool(chat_id),
        "chatIdPreview": f"{chat_id[:4]}...{chat_id[-2:]}" if len(chat_id) > 8 else (chat_id or None),
        "userId": user.id,
        "multiUserScanner": multi,
        "parserUserId": parser_user_id,
        "userIdMatchesParser": (parser_user_id is None or user.id == parser_user_id),
    }


@app.post("/api/notifications/test-telegram")
def test_telegram_notification(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Отправить тестовое уведомление в Telegram (для проверки токена и chat_id)."""
    _ensure_default_user(db)
    if not notify_telegram.is_configured():
        return {"ok": False, "error": "NOTIFY_TELEGRAM_BOT_TOKEN не задан в окружении"}
    s = _get_or_create_notification_settings(db, user.id)
    chat_id = (s.telegram_chat_id or "").strip()
    if not chat_id:
        return {"ok": False, "error": "Укажите ID чата или @username в настройках уведомлений и сохраните"}
    ok = notify_telegram.send_message(
        chat_id,
        "🔔 Тестовое уведомление от дашборда мониторинга. Если вы видите это сообщение — уведомления настроены верно.",
    )
    if ok:
        return {"ok": True, "message": "Тестовое сообщение отправлено в Telegram"}
    return {"ok": False, "error": "Telegram API вернул ошибку. Проверьте логи бэкенда и правильность Chat ID (число или @username)."}


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
    # Обновлять chat_id только при непустом значении, чтобы случайная пустая отправка (напр. при включении только Email) не затирала его.
    # Очистить можно через кнопку «Очистить»: фронт отправляет clearTelegramChatId: true вместе с пустым telegramChatId.
    if "telegramChatId" in body.model_fields_set:
        raw = body.telegramChatId
        if raw is not None and str(raw).strip():
            s.telegram_chat_id = str(raw).strip()
        elif getattr(body, "clearTelegramChatId", False) is True:
            s.telegram_chat_id = None
    db.add(s)
    db.commit()
    db.refresh(s)
    return NotificationSettingsOut(
        notifyEmail=bool(s.notify_email),
        notifyTelegram=bool(s.notify_telegram),
        notifyMode=(s.notify_mode or "all"),
        telegramChatId=s.telegram_chat_id,
    )


@app.get("/api/settings/semantic", response_model=SemanticSettingsOut)
def get_semantic_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SemanticSettingsOut:
    _ensure_default_user(db)
    db.refresh(user)
    return SemanticSettingsOut(
        semanticThreshold=user.semantic_threshold,
        semanticMinTopicPercent=user.semantic_min_topic_percent,
    )


@app.patch("/api/settings/semantic", response_model=SemanticSettingsOut)
def update_semantic_settings(
    body: SemanticSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SemanticSettingsOut:
    _ensure_default_user(db)
    # Обновляем только переданные поля; null означает сброс на глобальные настройки
    sent = body.model_dump(exclude_unset=True)
    if "semanticThreshold" in sent:
        v = sent["semanticThreshold"]
        user.semantic_threshold = None if v is None else (float(v) if 0 <= float(v) <= 1 else user.semantic_threshold)
    if "semanticMinTopicPercent" in sent:
        v = sent["semanticMinTopicPercent"]
        user.semantic_min_topic_percent = None if v is None else (float(v) if 0 <= float(v) <= 100 else user.semantic_min_topic_percent)
    db.add(user)
    db.commit()
    db.refresh(user)
    return SemanticSettingsOut(
        semanticThreshold=user.semantic_threshold,
        semanticMinTopicPercent=user.semantic_min_topic_percent,
    )


# --- API поддержки (пользователь: свои тикеты; админ: все + ответы) ---

@app.post("/api/support/tickets", response_model=SupportTicketDetailOut)
async def create_support_ticket(
    subject: str = Form(..., min_length=1, max_length=300),
    message: str = Form(..., min_length=1, max_length=10000),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportTicketDetailOut:
    _ensure_default_user(db)
    ticket = SupportTicket(user_id=user.id, subject=subject.strip(), status="open")
    db.add(ticket)
    db.flush()
    msg = SupportMessage(
        ticket_id=ticket.id,
        sender_id=user.id,
        is_from_staff=False,
        body=message.strip(),
    )
    db.add(msg)
    db.flush()
    for upload in files or []:
        if not upload.filename or upload.filename.strip() == "":
            continue
        content = await upload.read()
        if len(content) > support_uploads.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл «{upload.filename}» превышает лимит 5 МБ",
            )
        try:
            stored_name, size = support_uploads.save_file(
                content,
                upload.filename or "file",
                upload.content_type,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        att = SupportAttachment(
            support_message_id=msg.id,
            original_filename=(upload.filename or "file").strip()[:255],
            stored_filename=stored_name,
            content_type=(upload.content_type or "").strip()[:128] or None,
            size_bytes=size,
        )
        db.add(att)
    db.commit()
    db.refresh(ticket)
    db.refresh(msg)
    msg_attachments = db.scalars(select(SupportAttachment).where(SupportAttachment.support_message_id == msg.id)).all()
    _notify_admins_support(
        db,
        ticket.id,
        user.email,
        user.name,
        ticket.subject,
        message.strip()[:300],
    )
    created_at = msg.created_at.replace(tzinfo=timezone.utc) if msg.created_at.tzinfo is None else msg.created_at
    return SupportTicketDetailOut(
        id=ticket.id,
        userId=ticket.user_id,
        userEmail=user.email,
        userName=user.name,
        subject=ticket.subject,
        status=ticket.status,
        createdAt=ticket.created_at.isoformat() if ticket.created_at.tzinfo else ticket.created_at.replace(tzinfo=timezone.utc).isoformat(),
        updatedAt=ticket.updated_at.isoformat() if ticket.updated_at.tzinfo else ticket.updated_at.replace(tzinfo=timezone.utc).isoformat(),
        messageCount=1,
        lastMessageAt=created_at.isoformat(),
        messages=[
            SupportMessageOut(
                id=msg.id,
                ticketId=ticket.id,
                senderId=msg.sender_id,
                isFromStaff=msg.is_from_staff,
                body=msg.body,
                createdAt=created_at.isoformat(),
                attachments=[
                    SupportAttachmentOut(
                        id=a.id,
                        supportMessageId=a.support_message_id,
                        originalFilename=a.original_filename,
                        contentType=a.content_type,
                        sizeBytes=a.size_bytes,
                        createdAt=a.created_at.isoformat() if a.created_at.tzinfo else a.created_at.replace(tzinfo=timezone.utc).isoformat(),
                    )
                    for a in msg_attachments
                ],
            )
        ],
    )


def _support_ticket_to_out(
    t: SupportTicket, db: Session, include_user: bool = False, for_user_id: int | None = None
) -> SupportTicketOut:
    user = db.scalar(select(User).where(User.id == t.user_id)) if include_user else None
    msg_count = db.scalar(select(func.count()).select_from(SupportMessage).where(SupportMessage.ticket_id == t.id)) or 0
    last_msg = db.scalar(
        select(SupportMessage).where(SupportMessage.ticket_id == t.id).order_by(desc(SupportMessage.created_at)).limit(1)
    )
    last_at = None
    if last_msg and last_msg.created_at:
        last_at = last_msg.created_at.isoformat() if last_msg.created_at.tzinfo else last_msg.created_at.replace(tzinfo=timezone.utc).isoformat()

    has_unread = False
    if for_user_id is not None and t.user_id == for_user_id:
        read_at = t.user_last_read_at
        if read_at is not None and read_at.tzinfo is None:
            read_at = read_at.replace(tzinfo=timezone.utc)
        threshold = read_at if read_at else datetime(1970, 1, 1, tzinfo=timezone.utc)
        has_staff_after = db.scalar(
            select(func.count()).select_from(SupportMessage).where(
                SupportMessage.ticket_id == t.id,
                SupportMessage.is_from_staff.is_(True),
                SupportMessage.created_at > threshold,
            )
        ) or 0
        has_unread = has_staff_after > 0

    return SupportTicketOut(
        id=t.id,
        userId=t.user_id,
        userEmail=user.email if user else None,
        userName=user.name if user else None,
        subject=t.subject,
        status=t.status,
        createdAt=t.created_at.isoformat() if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc).isoformat(),
        updatedAt=t.updated_at.isoformat() if t.updated_at.tzinfo else t.updated_at.replace(tzinfo=timezone.utc).isoformat(),
        messageCount=msg_count,
        lastMessageAt=last_at,
        hasUnread=has_unread,
    )


@app.get("/api/support/tickets", response_model=list[SupportTicketOut])
def list_my_support_tickets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SupportTicketOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(SupportTicket).where(SupportTicket.user_id == user.id).order_by(desc(SupportTicket.updated_at))).all()
    return [_support_ticket_to_out(t, db, include_user=False, for_user_id=user.id) for t in rows]


@app.get("/api/support/has-any-unread")
def support_has_any_unread(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Есть ли у текущего пользователя непрочитанные ответы от поддержки (для индикатора в меню)."""
    _ensure_default_user(db)
    rows = db.scalars(select(SupportTicket).where(SupportTicket.user_id == user.id)).all()
    for t in rows:
        read_at = t.user_last_read_at
        if read_at is not None and read_at.tzinfo is None:
            read_at = read_at.replace(tzinfo=timezone.utc)
        threshold = read_at if read_at else datetime(1970, 1, 1, tzinfo=timezone.utc)
        has_staff_after = db.scalar(
            select(func.count()).select_from(SupportMessage).where(
                SupportMessage.ticket_id == t.id,
                SupportMessage.is_from_staff.is_(True),
                SupportMessage.created_at > threshold,
            )
        ) or 0
        if has_staff_after > 0:
            return {"hasUnread": True}
    return {"hasUnread": False}


@app.get("/api/support/tickets/{ticket_id}", response_model=SupportTicketDetailOut)
def get_support_ticket(
    ticket_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportTicketDetailOut:
    _ensure_default_user(db)
    ticket = db.scalar(
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id)
        .options(selectinload(SupportTicket.messages).selectinload(SupportMessage.attachments))
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    if ticket.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="forbidden")
    if ticket.user_id == user.id:
        ticket.user_last_read_at = _now_utc()
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
    author = db.scalar(select(User).where(User.id == ticket.user_id))
    messages_out: list[SupportMessageOut] = []
    for m in ticket.messages:
        created = m.created_at.replace(tzinfo=timezone.utc) if m.created_at.tzinfo is None else m.created_at
        att_out = [
            SupportAttachmentOut(
                id=a.id,
                supportMessageId=a.support_message_id,
                originalFilename=a.original_filename,
                contentType=a.content_type,
                sizeBytes=a.size_bytes,
                createdAt=a.created_at.isoformat() if a.created_at.tzinfo else a.created_at.replace(tzinfo=timezone.utc).isoformat(),
            )
            for a in (m.attachments or [])
        ]
        messages_out.append(
            SupportMessageOut(
                id=m.id,
                ticketId=m.ticket_id,
                senderId=m.sender_id,
                isFromStaff=m.is_from_staff,
                body=m.body,
                createdAt=created.isoformat(),
                attachments=att_out,
            )
        )
    return SupportTicketDetailOut(
        **_support_ticket_to_out(ticket, db, include_user=True).model_dump(),
        messages=messages_out,
    )


@app.post("/api/support/tickets/{ticket_id}/messages", response_model=SupportMessageOut)
async def add_support_message(
    ticket_id: int,
    body: str = Form(..., min_length=1, max_length=10000),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportMessageOut:
    _ensure_default_user(db)
    ticket = db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    if ticket.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="forbidden")
    body_clean = body.strip()
    is_staff = user.is_admin
    msg = SupportMessage(
        ticket_id=ticket_id,
        sender_id=user.id,
        is_from_staff=is_staff,
        body=body_clean,
    )
    db.add(msg)
    db.flush()
    for upload in files or []:
        if not upload.filename or upload.filename.strip() == "":
            continue
        content = await upload.read()
        if len(content) > support_uploads.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл «{upload.filename}» превышает лимит 5 МБ",
            )
        try:
            stored_name, size = support_uploads.save_file(
                content,
                upload.filename or "file",
                upload.content_type,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        att = SupportAttachment(
            support_message_id=msg.id,
            original_filename=(upload.filename or "file").strip()[:255],
            stored_filename=stored_name,
            content_type=(upload.content_type or "").strip()[:128] or None,
            size_bytes=size,
        )
        db.add(att)
    if is_staff:
        ticket.status = "answered"
    db.add(ticket)
    db.commit()
    db.refresh(msg)
    if not is_staff:
        author = db.scalar(select(User).where(User.id == ticket.user_id))
        _notify_admins_support(
            db,
            ticket.id,
            author.email if author else None,
            author.name if author else None,
            ticket.subject,
            body_clean[:300],
        )
    else:
        _notify_user_support_reply(db, ticket, body_clean[:500])
    created = msg.created_at.replace(tzinfo=timezone.utc) if msg.created_at.tzinfo is None else msg.created_at
    db.refresh(msg)
    att_out = [
        SupportAttachmentOut(
            id=a.id,
            supportMessageId=a.support_message_id,
            originalFilename=a.original_filename,
            contentType=a.content_type,
            sizeBytes=a.size_bytes,
            createdAt=a.created_at.isoformat() if a.created_at.tzinfo else a.created_at.replace(tzinfo=timezone.utc).isoformat(),
        )
        for a in (msg.attachments or [])
    ]
    return SupportMessageOut(
        id=msg.id,
        ticketId=msg.ticket_id,
        senderId=msg.sender_id,
        isFromStaff=msg.is_from_staff,
        body=msg.body,
        createdAt=created.isoformat(),
        attachments=att_out,
    )


@app.get("/api/support/attachments/{attachment_id}")
def download_support_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Скачать вложение (доступ: автор тикета или админ)."""
    _ensure_default_user(db)
    att = db.scalar(
        select(SupportAttachment).where(SupportAttachment.id == attachment_id).options(selectinload(SupportAttachment.message))
    )
    if not att or not att.message:
        raise HTTPException(status_code=404, detail="attachment not found")
    ticket = db.scalar(select(SupportTicket).where(SupportTicket.id == att.message.ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    if ticket.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="forbidden")
    path = support_uploads.get_path(att.stored_filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(
        path=str(path),
        filename=att.original_filename,
        media_type=att.content_type or "application/octet-stream",
    )


def _cleanup_expired_support_attachments() -> None:
    """Удалить вложения старше RETENTION_DAYS (30 дней)."""
    from database import SessionLocal
    cutoff = _now_utc() - timedelta(days=support_uploads.RETENTION_DAYS)
    with SessionLocal() as db:
        rows = db.scalars(
            select(SupportAttachment).where(SupportAttachment.created_at < cutoff)
        ).all()
        for a in rows:
            support_uploads.delete_file(a.stored_filename)
            db.delete(a)
        db.commit()


@app.patch("/api/support/tickets/{ticket_id}", response_model=SupportTicketOut)
def update_support_ticket_status(
    ticket_id: int,
    body: SupportTicketStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportTicketOut:
    _ensure_default_user(db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    ticket = db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    ticket.status = body.status
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return _support_ticket_to_out(ticket, db, include_user=True)


@app.get("/api/admin/support/tickets", response_model=list[SupportTicketOut])
def list_all_support_tickets(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[SupportTicketOut]:
    _ensure_default_user(db)
    rows = db.scalars(select(SupportTicket).order_by(desc(SupportTicket.updated_at))).all()
    return [_support_ticket_to_out(t, db, include_user=True) for t in rows]


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
def delete_keyword(
    keyword_id: int,
    permanent: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    k = db.scalar(select(Keyword).where(Keyword.id == keyword_id))
    if not k:
        raise HTTPException(status_code=404, detail="keyword not found")
    if k.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    if permanent:
        if getattr(k, "enabled", True):
            raise HTTPException(
                status_code=400,
                detail="Cannot permanently delete an active keyword; disable it first.",
            )
        db.delete(k)
    else:
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


def _chat_to_out(c: Chat, is_owner: bool, subscription_enabled: bool | None = None) -> ChatOut:
    source = getattr(c, "source", None) or CHAT_SOURCE_TELEGRAM
    if source == CHAT_SOURCE_MAX:
        identifier = (getattr(c, "max_chat_id", None) or "") or (c.title or "—")
    else:
        identifier = (
            (c.username or "")
            or (str(c.tg_chat_id) if c.tg_chat_id is not None else "")
            or (f"t.me/joinchat/{c.invite_hash}" if getattr(c, "invite_hash", None) else "")
        ) or "—"
    created_at = c.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    enabled = bool(subscription_enabled) if subscription_enabled is not None else bool(c.enabled)
    return ChatOut(
        id=c.id,
        identifier=identifier,
        title=c.title,
        description=c.description,
        groupIds=[g.id for g in (c.groups or [])],
        enabled=enabled,
        userId=c.user_id,
        isGlobal=bool(c.is_global),
        isOwner=is_owner,
        source=source,
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
    sub_enabled_map: dict[int, bool] = {}
    try:
        sub_enabled_rows = db.execute(
            select(user_chat_subscriptions.c.chat_id, user_chat_subscriptions.c.enabled).where(
                user_chat_subscriptions.c.user_id == user.id
            )
        ).all()
        for r in sub_enabled_rows:
            sub_enabled_map[r[0]] = r[1] if (len(r) > 1 and r[1] is not None) else True
    except Exception:
        pass  # колонка enabled может отсутствовать до миграции
    for c in sub_rows:
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            out.append(_chat_to_out(c, is_owner=False, subscription_enabled=sub_enabled_map.get(c.id, True)))
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

    source = (body.source or "telegram").strip().lower()
    if source not in ("telegram", "max"):
        source = CHAT_SOURCE_TELEGRAM

    if source == CHAT_SOURCE_MAX:
        username, tg_chat_id, invite_hash = None, None, None
        max_chat_id = ident
        existing_global = db.scalar(
            select(Chat).where(
                Chat.is_global.is_(True),
                Chat.source == CHAT_SOURCE_MAX,
                Chat.max_chat_id == max_chat_id,
            )
        )
    else:
        username, tg_chat_id, invite_hash = _parse_chat_identifier(ident)
        max_chat_id = None
        existing_global = None
        if tg_chat_id is not None:
            existing_global = db.scalar(
                select(Chat).where(Chat.is_global.is_(True), Chat.source == CHAT_SOURCE_TELEGRAM, Chat.tg_chat_id == tg_chat_id)
            )
        if existing_global is None and username:
            existing_global = db.scalar(
                select(Chat).where(Chat.is_global.is_(True), Chat.source == CHAT_SOURCE_TELEGRAM, Chat.username == username)
            )
        if existing_global is None and invite_hash:
            existing_global = db.scalar(
                select(Chat).where(Chat.is_global.is_(True), Chat.source == CHAT_SOURCE_TELEGRAM, Chat.invite_hash == invite_hash)
            )

    if existing_global is not None:
        already = db.execute(
            select(user_chat_subscriptions).where(
                user_chat_subscriptions.c.user_id == user_id,
                user_chat_subscriptions.c.chat_id == existing_global.id,
            )
        ).first()
        if already:
            if already[user_chat_subscriptions.c.via_group_id] is not None:
                db.execute(
                    update(user_chat_subscriptions)
                    .where(
                        user_chat_subscriptions.c.user_id == user_id,
                        user_chat_subscriptions.c.chat_id == existing_global.id,
                    )
                    .values(via_group_id=None)
                )
            db.commit()
        else:
            _check_limits(db, user, delta_channels=1)
            db.execute(
                user_chat_subscriptions.insert().values(
                    user_id=user_id, chat_id=existing_global.id, via_group_id=None, enabled=True
                )
            )
            db.commit()
        db.refresh(existing_global)
        return _chat_to_out(existing_global, is_owner=False)

    _check_limits(db, user, delta_channels=1, delta_own_channels=1)
    c = Chat(
        user_id=user_id,
        source=source,
        username=username,
        tg_chat_id=tg_chat_id,
        max_chat_id=max_chat_id,
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
    """Группы каналов по тематикам, созданные администраторами. Пользователь может подписаться на всю группу сразу.
    Подписан только если есть запись в user_thematic_group_subscriptions для текущего user.id."""
    _ensure_default_user(db)
    admin_ids = set(db.scalars(select(User.id).where(User.is_admin.is_(True))).all() or ())
    if not admin_ids:
        return []
    groups = db.scalars(
        select(ChatGroup)
        .where(ChatGroup.user_id.in_(admin_ids))
        .order_by(ChatGroup.id.asc())
        .options(selectinload(ChatGroup.chats))
    ).all()
    rows = db.execute(
        select(user_thematic_group_subscriptions.c.group_id).where(
            user_thematic_group_subscriptions.c.user_id == user.id
        )
    ).all()
    subscribed_group_ids = {int(r[0]) for r in rows if r[0] is not None}
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
        subscribed = g.id in subscribed_group_ids
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
    admin_ids = set(db.scalars(select(User.id).where(User.is_admin.is_(True))).all() or ())
    if g.user_id not in admin_ids:
        raise HTTPException(status_code=404, detail="group not available")
    global_chats = [c for c in (g.chats or []) if c.is_global]
    already_subscribed_to_group = db.execute(
        select(user_thematic_group_subscriptions).where(
            user_thematic_group_subscriptions.c.user_id == user.id,
            user_thematic_group_subscriptions.c.group_id == group_id,
        )
    ).first()
    if already_subscribed_to_group:
        return {"ok": True, "subscribedCount": len(global_chats)}
    _check_limits(db, user, delta_groups=1)
    # Каналы группы в лимит каналов не входят — проверку delta_channels не делаем
    sub_ids = set(
        db.execute(
            select(user_chat_subscriptions.c.chat_id).where(user_chat_subscriptions.c.user_id == user.id)
        ).scalars().all()
    )
    db.execute(
        user_thematic_group_subscriptions.insert().values(user_id=user.id, group_id=group_id)
    )
    for c in global_chats:
        if c.id not in sub_ids:
            db.execute(
                user_chat_subscriptions.insert().values(
                    user_id=user.id, chat_id=c.id, via_group_id=group_id, enabled=True
                )
            )
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
    admin_ids = set(db.scalars(select(User.id).where(User.is_admin.is_(True))).all() or ())
    if g.user_id not in admin_ids:
        raise HTTPException(status_code=404, detail="group not available")
    global_chat_ids = [c.id for c in (g.chats or []) if c.is_global]
    db.execute(
        user_thematic_group_subscriptions.delete().where(
            user_thematic_group_subscriptions.c.user_id == user.id,
            user_thematic_group_subscriptions.c.group_id == group_id,
        )
    )
    unsub_count = 0
    if global_chat_ids:
        r = db.execute(
            user_chat_subscriptions.delete().where(
                user_chat_subscriptions.c.user_id == user.id,
                user_chat_subscriptions.c.chat_id.in_(global_chat_ids),
                user_chat_subscriptions.c.via_group_id == group_id,
            )
        )
        unsub_count = r.rowcount
    db.commit()
    return {"ok": True, "unsubscribedCount": unsub_count}


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
    global scanner, max_scanner
    tg_running = False
    multi = True
    uid = None
    if scanner is not None:
        tg_running = scanner.is_running
        multi = getattr(scanner, "_multi_user", True)
        uid = getattr(scanner, "user_id", None)
    max_running = max_scanner is not None and max_scanner.is_running
    return ParserStatusOut(
        running=tg_running,
        multiUser=multi,
        userId=uid,
        maxRunning=max_running,
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
        MAX_ACCESS_TOKEN=raw.get("MAX_ACCESS_TOKEN", ""),
        MAX_BASE_URL=raw.get("MAX_BASE_URL", ""),
        MAX_POLL_INTERVAL_SEC=raw.get("MAX_POLL_INTERVAL_SEC", ""),
        AUTO_START_MAX_SCANNER=raw.get("AUTO_START_MAX_SCANNER", ""),
        SEMANTIC_PROVIDER=raw.get("SEMANTIC_PROVIDER", ""),
        SEMANTIC_SERVICE_URL=raw.get("SEMANTIC_SERVICE_URL", ""),
        SEMANTIC_MODEL_NAME=raw.get("SEMANTIC_MODEL_NAME", ""),
        SEMANTIC_SIMILARITY_THRESHOLD=raw.get("SEMANTIC_SIMILARITY_THRESHOLD", ""),
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
    # Только ключи, реально переданные в запросе (в т.ч. null для сброса)
    data = body.model_dump(exclude_unset=True)
    save_parser_settings(data)
    return _parser_settings_to_out()


@app.post("/api/admin/parser/start", response_model=ParserStatusOut)
def start_parser(_: User = Depends(get_current_admin)) -> ParserStatusOut:
    global scanner
    from parser_log import append as parser_log_append
    try:
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
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Ошибка запуска парсера")
        raise HTTPException(status_code=400, detail=f"Ошибка запуска парсера: {e}")


@app.post("/api/admin/parser/stop", response_model=ParserStatusOut)
def stop_parser(_: User = Depends(get_current_admin)) -> ParserStatusOut:
    global scanner
    from parser_log import append as parser_log_append
    if scanner is not None:
        scanner.stop()
        scanner = None
        parser_log_append("Парсер остановлен.")
    return _parser_status()


@app.post("/api/admin/parser/max/start", response_model=ParserStatusOut)
def start_max_parser(_: User = Depends(get_current_admin)) -> ParserStatusOut:
    """Запустить парсер MAX (Long Polling)."""
    global max_scanner
    from parser_log import append as parser_log_append
    try:
        if max_scanner is not None and max_scanner.is_running:
            return _parser_status()
        parser_log_append("[MAX] Запуск парсера MAX по запросу из админки.")
        max_scanner = MaxScanner(on_mention=_on_mention_callback)
        max_scanner.start()
        parser_log_append("[MAX] Парсер MAX запущен.")
        return _parser_status()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Ошибка запуска парсера MAX")
        raise HTTPException(status_code=400, detail=f"Ошибка запуска парсера MAX: {e}")


@app.post("/api/admin/parser/max/stop", response_model=ParserStatusOut)
def stop_max_parser(_: User = Depends(get_current_admin)) -> ParserStatusOut:
    """Остановить парсер MAX."""
    global max_scanner
    from parser_log import append as parser_log_append
    if max_scanner is not None:
        max_scanner.stop()
        max_scanner = None
        parser_log_append("[MAX] Парсер MAX остановлен.")
    return _parser_status()


@app.get("/api/chats/available", response_model=list[ChatAvailableOut])
def list_available_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatAvailableOut]:
    """Глобальные каналы (добавленные администратором), доступные для подписки."""
    _ensure_default_user(db)
    rows = db.scalars(
        select(Chat)
        .where(Chat.is_global.is_(True))
        .order_by(Chat.id.asc())
        .options(selectinload(Chat.groups))
    ).all()
    sub_rows = db.execute(
        select(user_chat_subscriptions.c.chat_id).where(user_chat_subscriptions.c.user_id == user.id)
    ).all()
    sub_ids = {r[0] for r in sub_rows}
    sub_enabled: dict[int, bool] = {cid: True for cid in sub_ids}
    try:
        sub_enabled_rows = db.execute(
            select(user_chat_subscriptions.c.chat_id, user_chat_subscriptions.c.enabled).where(
                user_chat_subscriptions.c.user_id == user.id
            )
        ).all()
        for r in sub_enabled_rows:
            sub_enabled[r[0]] = r[1] if (len(r) > 1 and r[1] is not None) else True
    except Exception:
        pass  # колонка enabled может отсутствовать до миграции
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
        group_names = [g.name for g in (c.groups or [])]
        out.append(
            ChatAvailableOut(
                id=c.id,
                identifier=ident_display,
                title=c.title,
                description=c.description,
                groupNames=group_names,
                enabled=bool(c.enabled),
                subscribed=c.id in sub_ids,
                subscriptionEnabled=sub_enabled.get(c.id) if c.id in sub_ids else None,
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
    if c is None:
        ident_stripped = body.identifier.strip()
        c = db.scalar(
            select(Chat).where(
                Chat.is_global.is_(True),
                Chat.source == CHAT_SOURCE_MAX,
                Chat.max_chat_id == ident_stripped,
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
        if existing[user_chat_subscriptions.c.via_group_id] is not None:
            db.execute(
                update(user_chat_subscriptions)
                .where(
                    user_chat_subscriptions.c.user_id == user.id,
                    user_chat_subscriptions.c.chat_id == c.id,
                )
                .values(via_group_id=None)
            )
        db.commit()
        db.refresh(c)
        return _chat_to_out(c, is_owner=False)
    _check_limits(db, user, delta_channels=1)
    db.execute(
        user_chat_subscriptions.insert().values(user_id=user.id, chat_id=c.id, via_group_id=None, enabled=True)
    )
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
        if existing[user_chat_subscriptions.c.via_group_id] is not None:
            db.execute(
                update(user_chat_subscriptions)
                .where(
                    user_chat_subscriptions.c.user_id == user.id,
                    user_chat_subscriptions.c.chat_id == chat_id,
                )
                .values(via_group_id=None)
            )
        db.commit()
        db.refresh(c)
        return _chat_to_out(c, is_owner=False)
    _check_limits(db, user, delta_channels=1)
    db.execute(
        user_chat_subscriptions.insert().values(user_id=user.id, chat_id=chat_id, via_group_id=None, enabled=True)
    )
    db.commit()
    db.refresh(c)
    return _chat_to_out(c, is_owner=False)


@app.patch("/api/chats/{chat_id}/subscription", response_model=ChatOut)
def update_chat_subscription(
    chat_id: int,
    body: SubscriptionUpdateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatOut:
    """Включить/выключить мониторинг для подписанного канала (только для подписок, не для своих каналов)."""
    c = db.scalar(select(Chat).where(Chat.id == chat_id))
    if not c:
        raise HTTPException(status_code=404, detail="chat not found")
    if c.user_id == user.id:
        raise HTTPException(status_code=400, detail="use PATCH /api/chats/:id for own channels")
    sub = db.execute(
        select(user_chat_subscriptions).where(
            user_chat_subscriptions.c.user_id == user.id,
            user_chat_subscriptions.c.chat_id == chat_id,
        )
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="subscription not found")
    try:
        db.execute(
            update(user_chat_subscriptions)
            .where(
                user_chat_subscriptions.c.user_id == user.id,
                user_chat_subscriptions.c.chat_id == chat_id,
            )
            .values(enabled=body.enabled)
        )
        db.commit()
    except Exception:
        raise HTTPException(status_code=500, detail="subscription update not supported (migrate DB)")
    db.refresh(c)
    return _chat_to_out(c, is_owner=False, subscription_enabled=body.enabled)


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


def _mentions_filter_stmt(stmt, user_id: int, unreadOnly: bool, keyword: str | None, search: str | None, source: str | None = None):
    stmt = stmt.where(Mention.user_id == user_id)
    if unreadOnly:
        stmt = stmt.where(Mention.is_read.is_(False))
    if keyword is not None and keyword.strip():
        stmt = stmt.where(Mention.keyword_text == keyword.strip())
    if search is not None and search.strip():
        stmt = stmt.where(Mention.message_text.ilike(f"%{search.strip()}%"))
    if source is not None and source.strip() and source.strip() in ("telegram", "max"):
        stmt = stmt.where(Mention.source == source.strip())
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
        Mention.source,
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
    kws = list(row.keywords or [])
    spans = list(getattr(row, "matched_spans", None) or [])
    seen: set[str] = set()
    keywords = []
    matched_spans_out: list[str | None] = []
    for i, kw in enumerate(kws):
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)
            matched_spans_out.append(spans[i] if i < len(spans) else None)
    src = getattr(row, "source", None) or CHAT_SOURCE_TELEGRAM
    max_sim = getattr(row, "max_semantic_similarity", None)
    topic_pct = round(max_sim * 100) if max_sim is not None else None
    return MentionGroupOut(
        id=str(row.id),
        groupName=group_name,
        groupIcon=_initials(group_name),
        userName=user_name,
        userInitials=_initials(user_name),
        userLink=user_link,
        message=(row.message_text or ""),
        keywords=keywords,
        matchedSpans=matched_spans_out if matched_spans_out else None,
        timestamp=_humanize_ru(created_at),
        isLead=bool(row.is_lead),
        isRead=bool(row.is_read),
        createdAt=created_at.isoformat(),
        groupLink=_group_link(row.chat_username),
        messageLink=_message_link(row.chat_id, row.message_id, row.chat_username),
        source=src,
        topicMatchPercent=topic_pct,
    )


@app.get("/api/mentions/count", response_model=MentionsCountOut)
def count_mentions(
    user: User = Depends(get_current_user),
    unreadOnly: bool = False,
    keyword: str | None = None,
    search: str | None = None,
    source: str | None = None,
    grouped: bool = False,
    db: Session = Depends(get_db),
) -> MentionsCountOut:
    _ensure_default_user(db)
    if grouped:
        stmt = (
            select(*_group_keys())
            .where(Mention.user_id == user.id)
        )
        stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search, source)
        subq = stmt.group_by(*_group_keys()).subquery()
        total = db.scalar(select(func.count()).select_from(subq)) or 0
    else:
        stmt = select(func.count(Mention.id))
        stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search, source)
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
    source: str | None = None,
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
            Mention.source,
            func.array_agg(Mention.keyword_text).label("keywords"),
            func.array_agg(Mention.semantic_matched_span).label("matched_spans"),
            func.bool_or(Mention.is_lead).label("is_lead"),
            func.bool_and(Mention.is_read).label("is_read"),
            func.max(Mention.semantic_similarity).label("max_semantic_similarity"),
        )
        stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search, source)
        stmt = stmt.group_by(*_group_keys())
        order = desc(Mention.created_at) if sortOrder == "desc" else Mention.created_at
        stmt = stmt.order_by(order).offset(offset).limit(limit)
        try:
            rows = db.execute(stmt).all()
        except (OperationalError, ProgrammingError):
            # Колонка semantic_matched_span может отсутствовать до выполнения миграции
            stmt_fallback = select(
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
                Mention.source,
                func.array_agg(Mention.keyword_text).label("keywords"),
                func.bool_or(Mention.is_lead).label("is_lead"),
                func.bool_and(Mention.is_read).label("is_read"),
                func.max(Mention.semantic_similarity).label("max_semantic_similarity"),
            )
            stmt_fallback = _mentions_filter_stmt(stmt_fallback, user.id, unreadOnly, keyword, search, source)
            stmt_fallback = stmt_fallback.group_by(*_group_keys()).order_by(order).offset(offset).limit(limit)
            rows = db.execute(stmt_fallback).all()
            # у fallback-строк нет matched_spans — _row_to_group_out возьмёт getattr(..., None)
        return [_row_to_group_out(row) for row in rows]
    stmt = select(Mention)
    stmt = _mentions_filter_stmt(stmt, user.id, unreadOnly, keyword, search, source)
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
    source: str | None = None,
    leadsOnly: bool = False,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    db: Session = Depends(get_db),
) -> Response:
    _ensure_default_user(db)
    stmt = select(Mention).where(Mention.user_id == user.id)
    if keyword is not None and keyword.strip():
        stmt = stmt.where(Mention.keyword_text == keyword.strip())
    if source is not None and source.strip() and source.strip() in ("telegram", "max"):
        stmt = stmt.where(Mention.source == source.strip())
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
        ["id", "created_at", "source", "chat", "sender", "message", "keyword", "is_lead", "is_read", "user_link"]
    )
    for m in rows:
        created = m.created_at.isoformat() if m.created_at else ""
        src = getattr(m, "source", None) or "telegram"
        chat = (m.chat_name or m.chat_username or "").strip()
        sender = (m.sender_name or "").strip()
        user_link = _user_profile_link(m) or ""
        writer.writerow(
            [str(m.id), created, src, chat, sender, (m.message_text or ""), m.keyword_text, m.is_lead, m.is_read, user_link]
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
        import mention_notifications
        mention_notifications.enqueue_mention_notification(m.id)
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
    await ws_manager.connect(ws, user_id)
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

