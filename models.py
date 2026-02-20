from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


chat_group_links = Table(
    "chat_group_links",
    Base.metadata,
    Column("chat_id", ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("chat_groups.id", ondelete="CASCADE"), primary_key=True),
)

# Подписки пользователей на глобальные каналы (добавленные администратором)
user_chat_subscriptions = Table(
    "user_chat_subscriptions",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("chat_id", ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Тариф: free | basic | pro | business; при истечении plan_expires_at эффективный план = free
    plan_slug: Mapped[str] = mapped_column(String(32), nullable=False, default="free", server_default="'free'")
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    keywords: Mapped[list["Keyword"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mentions: Mapped[list["Mention"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chats: Mapped[list["Chat"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscribed_chats: Mapped[list["Chat"]] = relationship(
        secondary=user_chat_subscriptions,
        back_populates="subscriber_users",
    )


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    text: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    use_semantic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="keywords")


# Источник чата/упоминания: telegram | max
CHAT_SOURCE_TELEGRAM = "telegram"
CHAT_SOURCE_MAX = "max"


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    source: Mapped[str] = mapped_column(String(32), nullable=False, default=CHAT_SOURCE_TELEGRAM, server_default="'telegram'", index=True)
    tg_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    max_chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    invite_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="chats")
    groups: Mapped[list["ChatGroup"]] = relationship(
        secondary=chat_group_links,
        back_populates="chats",
    )
    subscriber_users: Mapped[list["User"]] = relationship(
        secondary=user_chat_subscriptions,
        back_populates="subscribed_chats",
    )


class ChatGroup(Base):
    __tablename__ = "chat_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chats: Mapped[list["Chat"]] = relationship(
        secondary=chat_group_links,
        back_populates="groups",
    )


class PlanLimit(Base):
    """Лимиты тарифного плана. Одна строка на план (free, basic, pro, business). При отсутствии строки используются значения по умолчанию из plans.LIMITS."""
    __tablename__ = "plan_limits"

    plan_slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    max_groups: Mapped[int] = mapped_column(Integer, nullable=False)
    max_channels: Mapped[int] = mapped_column(Integer, nullable=False)
    max_keywords_exact: Mapped[int] = mapped_column(Integer, nullable=False)
    max_keywords_semantic: Mapped[int] = mapped_column(Integer, nullable=False)
    max_own_channels: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    can_track: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ParserSetting(Base):
    """Настройки парсера (админ-панель). Один ряд на ключ. Значение из БД имеет приоритет над env."""
    __tablename__ = "parser_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class PasswordResetToken(Base):
    """Токены для восстановления пароля (один раз, с истечением)."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NotificationSettings(Base):
    """Настройки уведомлений пользователя: каналы и что отправлять."""
    __tablename__ = "notification_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notify_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    notify_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="all", server_default="'all'")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    source: Mapped[str] = mapped_column(String(32), nullable=False, default=CHAT_SOURCE_TELEGRAM, server_default="'telegram'", index=True)
    keyword_text: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    chat_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    chat_username: Mapped[str | None] = mapped_column(String(128), nullable=True)

    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    sender_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    sender_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sender_username: Mapped[str | None] = mapped_column(String(128), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # Косинусное сходство 0.0–1.0 при семантическом совпадении; NULL при точном совпадении.
    semantic_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="mentions")

