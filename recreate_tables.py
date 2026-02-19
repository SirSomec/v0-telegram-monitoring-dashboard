#!/usr/bin/env python3
"""
Пересоздаёт все таблицы БД: удаляет старые и создаёт заново по текущим моделям.
Все данные будут потеряны. Запуск: python recreate_tables.py
"""
from __future__ import annotations

import sys

from database import SessionLocal, drop_all_tables, init_db
from models import User


def main() -> None:
    print("Удаление таблиц...")
    drop_all_tables()
    print("Создание таблиц...")
    init_db()

    print("Создание пользователя по умолчанию (id=1)...")
    with SessionLocal() as db:
        if db.get(User, 1) is None:
            db.add(User(id=1, email=None, name="Default", is_admin=True))
            db.commit()
            print("  Пользователь id=1 создан.")
        else:
            print("  Пользователь id=1 уже есть (не перезаписываем).")

    print("Готово.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
