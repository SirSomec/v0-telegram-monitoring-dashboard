"""
Буфер логов парсера для отображения в админ-панели. Последние 80 строк, потокобезопасно.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from threading import Lock

MAX_LINES = 80
_lock = Lock()
_lines: list[str] = []


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def append(message: str) -> None:
    """Добавить одну строку в лог (без переносов — одна запись = одна строка)."""
    with _lock:
        global _lines
        line = f"[{_ts()}] {message}"
        _lines.append(line)
        if len(_lines) > MAX_LINES:
            _lines = _lines[-MAX_LINES:]


def append_exception(exc: BaseException) -> None:
    """Добавить сообщение об ошибке и traceback в лог (несколько строк как одна запись)."""
    with _lock:
        global _lines
        head = f"[{_ts()}] ERROR: {type(exc).__name__}: {exc}"
        _lines.append(head)
        for line in traceback.format_exc().strip().splitlines():
            _lines.append(f"  {line}")
        if len(_lines) > MAX_LINES:
            _lines = _lines[-MAX_LINES:]


def get_lines() -> list[str]:
    """Вернуть последние до MAX_LINES строк лога."""
    with _lock:
        return list(_lines[-MAX_LINES:])


def clear() -> None:
    """Очистить буфер (опционально)."""
    with _lock:
        global _lines
        _lines.clear()
