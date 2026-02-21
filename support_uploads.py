"""Хранение вложений поддержки на диске. Срок хранения 30 дней."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Каталог для загрузок (относительно CWD или абсолютный)
SUPPORT_UPLOAD_DIR = os.getenv("SUPPORT_UPLOAD_DIR", "").strip() or os.path.join(os.getcwd(), "data", "support_uploads")
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
RETENTION_DAYS = 30

# Безопасное расширение из имени файла (только буквы, цифры, точка)
SAFE_EXT_RE = re.compile(r"\.([a-zA-Z0-9]+)$")


def get_upload_dir() -> Path:
    p = Path(SUPPORT_UPLOAD_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_stored_filename(original_filename: str) -> str:
    """Уникальное имя файла на диске."""
    ext = ""
    m = SAFE_EXT_RE.search(original_filename or "")
    if m:
        ext = "." + m.group(1).lower()[:8]
    return uuid.uuid4().hex + ext


def get_path(stored_filename: str) -> Path:
    return get_upload_dir() / stored_filename


def save_file(content: bytes, original_filename: str, content_type: str | None) -> tuple[str, int]:
    """
    Сохранить файл на диск. Возвращает (stored_filename, size_bytes).
    Вызывающий должен проверить size <= MAX_FILE_SIZE_BYTES до вызова.
    """
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File size exceeds {MAX_FILE_SIZE_BYTES} bytes")
    stored = make_stored_filename(original_filename or "file")
    path = get_path(stored)
    path.write_bytes(content)
    return stored, len(content)


def delete_file(stored_filename: str) -> None:
    """Удалить файл с диска (игнорировать ошибки)."""
    try:
        get_path(stored_filename).unlink(missing_ok=True)
    except Exception:
        pass
