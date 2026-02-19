from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    keywords: Mapped[list["Keyword"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mentions: Mapped[list["Mention"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chats: Mapped[list["Chat"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    text: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="keywords")


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    tg_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="chats")
    groups: Mapped[list["ChatGroup"]] = relationship(
        secondary=chat_group_links,
        back_populates="chats",
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


class ParserSetting(Base):
    """Настройки парсера (админ-панель). Один ряд на ключ. Значение из БД имеет приоритет над env."""
    __tablename__ = "parser_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    keyword_text: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    chat_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    chat_username: Mapped[str | None] = mapped_column(String(128), nullable=True)

    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    sender_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    sender_name: Mapped[str | None] = mapped_column(String(300), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="mentions")

