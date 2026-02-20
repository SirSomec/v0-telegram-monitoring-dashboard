# -*- coding: utf-8 -*-
"""
Тарифы учётных записей: лимиты по планам и определение эффективного плана с учётом срока действия.
Лимиты могут храниться в БД (таблица plan_limits); при отсутствии строки используются значения по умолчанию.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from models import User

# Ключи планов
PLAN_FREE = "free"
PLAN_BASIC = "basic"
PLAN_PRO = "pro"
PLAN_BUSINESS = "business"

PLAN_ORDER = (PLAN_FREE, PLAN_BASIC, PLAN_PRO, PLAN_BUSINESS)

# Лимиты: группы каналов, всего каналов (свои + подписки), ключевые слова точные, семантические, своих каналов
# free: только просмотр и выгрузка ранее спарсенных сообщений
LIMITS = {
    PLAN_FREE: {
        "max_groups": 0,
        "max_channels": 0,
        "max_keywords_exact": 0,
        "max_keywords_semantic": 0,
        "max_own_channels": 0,
        "label": "Без оплаты",
        "can_track": False,  # не участвует в мониторинге
    },
    PLAN_BASIC: {
        "max_groups": 2,
        "max_channels": 5,
        "max_keywords_exact": 5,
        "max_keywords_semantic": 2,
        "max_own_channels": 2,
        "label": "Базовый",
        "can_track": True,
    },
    PLAN_PRO: {
        "max_groups": 10,
        "max_channels": 30,
        "max_keywords_exact": 30,
        "max_keywords_semantic": 10,
        "max_own_channels": 10,
        "label": "Про",
        "can_track": True,
    },
    PLAN_BUSINESS: {
        "max_groups": 50,
        "max_channels": 200,
        "max_keywords_exact": 100,
        "max_keywords_semantic": 50,
        "max_own_channels": 50,
        "label": "Бизнес",
        "can_track": True,
    },
}


def get_limits(plan_slug: str, db: "Session | None" = None) -> dict[str, Any]:
    """
    Возвращает лимиты для плана. Для неизвестного плана — лимиты free.
    Если передан db и в таблице plan_limits есть строка для плана — используются значения из БД.
    """
    if db is not None:
        from models import PlanLimit
        row = db.get(PlanLimit, plan_slug)
        if row is not None:
            return {
                "max_groups": row.max_groups,
                "max_channels": row.max_channels,
                "max_keywords_exact": row.max_keywords_exact,
                "max_keywords_semantic": row.max_keywords_semantic,
                "max_own_channels": row.max_own_channels,
                "label": row.label,
                "can_track": row.can_track,
            }
    return LIMITS.get(plan_slug, LIMITS[PLAN_FREE]).copy()


def get_effective_plan(user: "User") -> str:
    """
    Эффективный план пользователя: при истёкшем сроке — free.
    user должен иметь атрибуты plan_slug и plan_expires_at.
    """
    now = datetime.now(timezone.utc)
    slug = getattr(user, "plan_slug", None) or PLAN_FREE
    expires_at = getattr(user, "plan_expires_at", None)
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now >= expires_at:
            return PLAN_FREE
    return slug if slug in LIMITS else PLAN_FREE


def can_track(plan_slug: str, db: "Session | None" = None) -> bool:
    """Участвует ли план в мониторинге (парсер учитывает ключевые слова и каналы)."""
    return get_limits(plan_slug, db).get("can_track", False)
