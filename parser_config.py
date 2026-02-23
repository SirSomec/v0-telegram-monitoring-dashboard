"""
Чтение настроек парсера: сначала из БД (parser_settings), затем из env.
Позволяет задавать настройки в админ-панели без правки .env.
"""
from __future__ import annotations

import os
from typing import Any

from database import db_session
from models import ParserSetting, User


def get_parser_setting(key: str, env_fallback: str | None = None) -> str | None:
    """Возвращает значение настройки: из БД, иначе из os.getenv(key) или env_fallback."""
    with db_session() as db:
        row = db.get(ParserSetting, key)
        if row is not None and row.value is not None and row.value.strip():
            return row.value.strip()
    return os.getenv(key, env_fallback) or None


def get_parser_setting_str(key: str, default: str = "") -> str:
    """Строковая настройка; пустая строка если не задана."""
    v = get_parser_setting(key, default)
    return (v or "").strip()


def get_parser_setting_bool(key: str, default: bool = False) -> bool:
    """Булева настройка (1/true/yes → True)."""
    v = get_parser_setting(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def get_parser_setting_int(key: str, default: int = 0) -> int:
    """Числовая настройка."""
    v = get_parser_setting(key)
    if v is None or not v.strip():
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


def get_parser_setting_float(key: str, default: float = 0.0) -> float:
    """Числовая настройка (float)."""
    v = get_parser_setting(key)
    if v is None or not v.strip():
        return default
    try:
        return float(v.strip())
    except ValueError:
        return default


def get_user_semantic_threshold(user_id: int) -> float | None:
    """Порог срабатывания семантического поиска для пользователя (0–1). None = использовать глобальный."""
    with db_session() as db:
        u = db.get(User, user_id)
        if u is None or u.semantic_threshold is None:
            return None
        t = float(u.semantic_threshold)
        return t if 0 <= t <= 1 else None


def get_user_semantic_min_topic_percent(user_id: int) -> float | None:
    """Минимальный % совпадения с темой для пользователя (0–100). None = не фильтровать по минимуму."""
    with db_session() as db:
        u = db.get(User, user_id)
        if u is None or u.semantic_min_topic_percent is None:
            return None
        p = float(u.semantic_min_topic_percent)
        return p if 0 <= p <= 100 else None


def set_parser_setting(key: str, value: str | None) -> None:
    """Записать настройку в БД. value=None или пустая строка — удалить (будет использоваться env)."""
    with db_session() as db:
        row = db.get(ParserSetting, key)
        val = (value or "").strip() or None
        if val is None:
            if row is not None:
                db.delete(row)
            return
        if row is None:
            db.add(ParserSetting(key=key, value=val))
        else:
            row.value = val


def get_all_parser_settings() -> dict[str, str]:
    """Все ключи настроек парсера и их значения из env (для отображения масок/подсказок). Не возвращает секреты из БД."""
    keys = [
        "TG_API_ID",
        "TG_API_HASH",
        "TG_SESSION_STRING",
        "TG_SESSION_NAME",
        "TG_BOT_TOKEN",
        "TG_CHATS",
        "TG_PROXY_HOST",
        "TG_PROXY_PORT",
        "TG_PROXY_USER",
        "TG_PROXY_PASS",
        "AUTO_START_SCANNER",
        "MULTI_USER_SCANNER",
        "TG_USER_ID",
        # MAX messenger
        "MAX_ACCESS_TOKEN",
        "MAX_BASE_URL",
        "MAX_POLL_INTERVAL_SEC",
        "AUTO_START_MAX_SCANNER",
        # Семантический анализ (ИИ)
        "SEMANTIC_PROVIDER",
        "SEMANTIC_SERVICE_URL",
        "SEMANTIC_MODEL_NAME",
        "SEMANTIC_SIMILARITY_THRESHOLD",
        # Производительность
        "MESSAGE_CONCURRENCY",
        "SEMANTIC_EXECUTOR_WORKERS",
    ]
    with db_session() as db:
        out: dict[str, str] = {}
        for k in keys:
            row = db.get(ParserSetting, k)
            if row is not None and row.value:
                out[k] = row.value  # храним как есть для формы
            else:
                env_val = os.getenv(k, "")
                out[k] = env_val if env_val is not None else ""
        return out


def save_parser_settings(settings: dict[str, Any]) -> None:
    """Сохранить настройки из словаря (ключи — имена переменных, значения — строки или bool/int)."""
    for key, value in settings.items():
        if value is None:
            set_parser_setting(key, None)
        elif isinstance(value, bool):
            set_parser_setting(key, "1" if value else "0")
        elif isinstance(value, int):
            set_parser_setting(key, str(value))
        else:
            set_parser_setting(key, str(value).strip() or None)
