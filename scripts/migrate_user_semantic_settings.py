#!/usr/bin/env python3
"""
Миграция: добавляет в users колонки semantic_threshold и semantic_min_topic_percent.
Безопасно вызывать на уже обновлённой БД (проверяет наличие колонок).
Запуск из корня проекта: python scripts/migrate_user_semantic_settings.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import engine


def migrate() -> None:
    with engine.connect() as conn:
        for col, col_type in [
            ("semantic_threshold", "FLOAT"),
            ("semantic_min_topic_percent", "FLOAT"),
        ]:
            try:
                conn.execute(text(f"""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS {col} {col_type}
                """))
                conn.commit()
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    conn.rollback()
                else:
                    raise


if __name__ == "__main__":
    migrate()
    print("OK: user semantic settings columns")
