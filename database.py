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


def init_db() -> None:
    from models import Chat, ChatGroup, Keyword, Mention, ParserSetting, User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_keywords_use_semantic()


def drop_all_tables() -> None:
    """Удаляет все таблицы (для пересоздания схемы). Все данные будут потеряны."""
    from models import Chat, ChatGroup, Keyword, Mention, ParserSetting, User  # noqa: F401

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

