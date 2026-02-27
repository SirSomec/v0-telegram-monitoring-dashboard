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


def _migrate_mentions_sender_phone() -> None:
    """Добавить колонку sender_phone в mentions (номер телефона лида, если доступен)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'mentions' AND column_name = 'sender_phone'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE mentions ADD COLUMN sender_phone VARCHAR(32)"))
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


def _migrate_mentions_semantic_similarity() -> None:
    """Добавить колонку semantic_similarity в mentions (процент совпадения с темой при семантическом поиске)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'mentions' AND column_name = 'semantic_similarity'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE mentions ADD COLUMN semantic_similarity DOUBLE PRECISION"))
        conn.commit()


def _migrate_mentions_semantic_matched_span() -> None:
    """Добавить колонку semantic_matched_span в mentions (фрагмент сообщения для подсветки семантического совпадения)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'mentions' AND column_name = 'semantic_matched_span'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE mentions ADD COLUMN semantic_matched_span TEXT"))
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


def _migrate_chats_is_global_and_invite_hash() -> None:
    """Добавить колонки is_global и invite_hash в chats при их отсутствии (глобальные каналы и подписки)."""
    with engine.connect() as conn:
        for col, col_def in (
            ("is_global", "BOOLEAN NOT NULL DEFAULT false"),
            ("invite_hash", "VARCHAR(128)"),
        ):
            r = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'chats' AND column_name = :col"
                ),
                {"col": col},
            )
            if r.scalar() is not None:
                continue
            conn.execute(text(f"ALTER TABLE chats ADD COLUMN {col} {col_def}"))
            conn.commit()


def _migrate_chats_billing_key() -> None:
    """Добавить колонку billing_key в chats для объединения связанных чатов в одну биллинговую единицу."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'chats' AND column_name = 'billing_key'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE chats ADD COLUMN billing_key VARCHAR(128)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chats_billing_key ON chats (billing_key)"))
        conn.commit()


def _migrate_support_ticket_user_last_read_at() -> None:
    """Добавить колонку user_last_read_at в support_tickets при отсутствии."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'support_tickets' AND column_name = 'user_last_read_at'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE support_tickets ADD COLUMN user_last_read_at TIMESTAMP WITH TIME ZONE"))
        conn.commit()


def _migrate_user_thematic_group_subscriptions() -> None:
    """Создать таблицу подписок на тематические группы и один раз заполнить из текущих подписок на каналы.
    Backfill выполняется только при пустой таблице, чтобы новые пользователи не получали подписки."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload
    from models import (
        ChatGroup,
        User,
        user_chat_subscriptions,
        user_thematic_group_subscriptions,
    )

    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'user_thematic_group_subscriptions'"
            )
        )
        table_exists = r.scalar() is not None
    if not table_exists:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        n = db.scalar(select(func.count()).select_from(user_thematic_group_subscriptions)) or 0
        if n > 0:
            return
        admin_ids = set(db.scalars(select(User.id).where(User.is_admin.is_(True))).all() or ())
        if not admin_ids:
            return
        admin_groups = db.scalars(
            select(ChatGroup).where(ChatGroup.user_id.in_(admin_ids)).options(selectinload(ChatGroup.chats))
        ).all()
        for g in admin_groups:
            global_chats = [c for c in (g.chats or []) if getattr(c, "is_global", False)]
            if not global_chats:
                continue
            chat_ids = {c.id for c in global_chats}
            sub_rows = db.execute(
                select(user_chat_subscriptions.c.user_id)
                .where(user_chat_subscriptions.c.chat_id.in_(chat_ids))
                .distinct()
            ).all()
            for (uid,) in sub_rows:
                user_subs = set(
                    db.execute(
                        select(user_chat_subscriptions.c.chat_id).where(
                            user_chat_subscriptions.c.user_id == uid,
                            user_chat_subscriptions.c.chat_id.in_(chat_ids),
                        )
                    ).scalars().all()
                )
                if chat_ids.issubset(user_subs):
                    existing = db.execute(
                        select(user_thematic_group_subscriptions).where(
                            user_thematic_group_subscriptions.c.user_id == uid,
                            user_thematic_group_subscriptions.c.group_id == g.id,
                        )
                    ).first()
                    if not existing:
                        db.execute(
                            user_thematic_group_subscriptions.insert().values(user_id=uid, group_id=g.id)
                        )
        db.commit()


def _migrate_user_chat_subscriptions_via_group_id() -> None:
    """Добавить колонку via_group_id в user_chat_subscriptions (источник подписки: группа или индивидуально)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'user_chat_subscriptions' AND column_name = 'via_group_id'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(
            text(
                "ALTER TABLE user_chat_subscriptions "
                "ADD COLUMN via_group_id INTEGER REFERENCES chat_groups(id) ON DELETE CASCADE"
            )
        )
        conn.commit()


def _migrate_user_chat_subscriptions_enabled() -> None:
    """Добавить колонку enabled в user_chat_subscriptions (вкл/выкл мониторинг для подписки)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'user_chat_subscriptions' AND column_name = 'enabled'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(
            text(
                "ALTER TABLE user_chat_subscriptions ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT true"
            )
        )
        conn.commit()


def _migrate_user_semantic_settings() -> None:
    """Добавить колонки semantic_threshold и semantic_min_topic_percent в users (настройки семантического поиска)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'semantic_threshold'"
            )
        )
        if r.scalar() is not None:
            return
        conn.execute(text("ALTER TABLE users ADD COLUMN semantic_threshold FLOAT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN semantic_min_topic_percent FLOAT"))
        conn.commit()


def _migrate_exclusion_words_to_keyword() -> None:
    """Привязать слова-исключения к ключевым словам: заменить user_id на keyword_id."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'exclusion_words' AND column_name = 'user_id'"
            )
        )
        if r.scalar() is None:
            return
        conn.execute(
            text(
                "ALTER TABLE exclusion_words ADD COLUMN keyword_id INTEGER REFERENCES keywords(id) ON DELETE CASCADE"
            )
        )
        conn.commit()
        conn.execute(
            text(
                "UPDATE exclusion_words SET keyword_id = (SELECT MIN(k.id) FROM keywords k WHERE k.user_id = exclusion_words.user_id)"
            )
        )
        conn.commit()
        conn.execute(text("DELETE FROM exclusion_words WHERE keyword_id IS NULL"))
        conn.commit()
        conn.execute(text("ALTER TABLE exclusion_words ALTER COLUMN keyword_id SET NOT NULL"))
        conn.commit()
        conn.execute(text("ALTER TABLE exclusion_words DROP COLUMN user_id"))
        conn.commit()


def init_db() -> None:
    from models import Chat, ChatGroup, ExclusionWord, Keyword, Mention, NotificationSettings, ParserSetting, User, PasswordResetToken, PlanLimit, SupportTicket, SupportMessage, SupportAttachment, user_thematic_group_subscriptions  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_keywords_use_semantic()
    _migrate_mentions_sender_username()
    _migrate_mentions_sender_phone()
    _migrate_users_plan()
    _migrate_chats_source_and_max_chat_id()
    _migrate_mentions_source()
    _migrate_mentions_semantic_similarity()
    _migrate_mentions_semantic_matched_span()
    _migrate_plan_limits()
    _migrate_chats_is_global_and_invite_hash()
    _migrate_chats_billing_key()
    _migrate_support_ticket_user_last_read_at()
    _migrate_user_thematic_group_subscriptions()
    _migrate_user_chat_subscriptions_via_group_id()
    _migrate_user_chat_subscriptions_enabled()
    _migrate_user_semantic_settings()
    _migrate_exclusion_words_to_keyword()


def drop_all_tables() -> None:
    """Удаляет все таблицы (для пересоздания схемы). Все данные будут потеряны."""
    from models import Chat, ChatGroup, Keyword, Mention, NotificationSettings, ParserSetting, User, PasswordResetToken, PlanLimit, SupportTicket, SupportMessage, SupportAttachment  # noqa: F401

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

