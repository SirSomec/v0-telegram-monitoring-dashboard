#!/usr/bin/env python3
"""
Миграция: добавляет is_global в chats и таблицу user_chat_subscriptions.
Безопасно вызывать на уже обновлённой БД (проверяет наличие колонки/таблицы).
Запуск из корня проекта: python scripts/migrate_global_chats.py
"""
from __future__ import annotations

import os
import sys

# корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import engine


def migrate() -> None:
    with engine.connect() as conn:
        # PostgreSQL: добавить колонку is_global в chats, если её нет
        try:
            conn.execute(text("""
                ALTER TABLE chats
                ADD COLUMN IF NOT EXISTS is_global BOOLEAN NOT NULL DEFAULT false
            """))
            conn.commit()
        except Exception as e:
            # Для SQLite и др. может не быть IF NOT EXISTS для колонки
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                pass
            else:
                raise

        # Создать таблицу подписок, если её нет (create_all обычно создаёт, но миграция для ручного запуска)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_chat_subscriptions (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, chat_id)
            )
        """))
        conn.commit()

    print("Миграция выполнена: is_global в chats, user_chat_subscriptions создана.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
