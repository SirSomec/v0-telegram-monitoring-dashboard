from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    # Пример:
    # postgresql+psycopg2://postgres:postgres@localhost:5432/telegram_monitor
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/telegram_monitor",
    )


engine = create_engine(_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _migrate_keywords_use_semantic() -> None:
    """Добавить колонку use_semantic в keywords, если её ещё нет (миграция без потери данных)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'keywords' AND column_name = 'use_semantic'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE keywords ADD COLUMN use_semantic BOOLEAN NOT NULL DEFAULT false"))
        conn.commit()


def _migrate_mentions_sender_username() -> None:
    """Добавить колонку sender_username в mentions, если её ещё нет."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'mentions' AND column_name = 'sender_username'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE mentions ADD COLUMN sender_username VARCHAR(128)"))
        conn.commit()


def _migrate_users_plan() -> None:
    """Добавить колонки plan_slug и plan_expires_at в users, если их ещё нет."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'plan_slug'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE users ADD COLUMN plan_slug VARCHAR(32) NOT NULL DEFAULT 'free'"))
        conn.execute(text("ALTER TABLE users ADD COLUMN plan_expires_at TIMESTAMP WITH TIME ZONE"))
        conn.commit()


def _migrate_chats_source_and_max_chat_id() -> None:
    """Добавить колонки source и max_chat_id в chats для поддержки MAX."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'chats' AND column_name = 'source'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE chats ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'telegram'"))
        conn.execute(text("ALTER TABLE chats ADD COLUMN max_chat_id VARCHAR(128)"))
        conn.commit()


def _migrate_mentions_source() -> None:
    """Добавить колонку source в mentions."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'mentions' AND column_name = 'source'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE mentions ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'telegram'"))
        conn.commit()


def _migrate_plan_limits() -> None:
    """Заполнить plan_limits значениями по умолчанию из plans.LIMITS, если таблица пуста."""
    from sqlalchemy import func, select
    from models import PlanLimit
    from plans import LIMITS, PLAN_ORDER

    with SessionLocal() as db:
        n = db.scalar(select(func.count()).select_from(PlanLimit)) or 0
        if n > 0:
            return
        for slug in PLAN_ORDER:
            L = LIMITS[slug]
            row = PlanLimit(
                plan_slug=slug,
                max_groups=L["max_groups"],
                max_channels=L["max_channels"],
                max_keywords_exact=L["max_keywords_exact"],
                max_keywords_semantic=L["max_keywords_semantic"],
                max_own_channels=L["max_own_channels"],
                label=L["label"],
                can_track=L["can_track"],
            )
            db.add(row)
        db.commit()


def init_db() -> None:
    from models import Chat, ChatGroup, Keyword, Mention, NotificationSettings, ParserSetting, User, PasswordResetToken, PlanLimit  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_keywords_use_semantic()
    _migrate_mentions_sender_username()
    _migrate_users_plan()
    _migrate_chats_source_and_max_chat_id()
    _migrate_mentions_source()
    _migrate_plan_limits()


def drop_all_tables() -> None:
    """Удаляет все таблицы (для пересоздания схемы). Все данные будут потеряны."""
    from models import Chat, ChatGroup, Keyword, Mention, NotificationSettings, ParserSetting, User, PasswordResetToken, PlanLimit  # noqa: F401

    Base.metadata.drop_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

