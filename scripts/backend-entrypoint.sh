#!/bin/sh
set -e
# Применяем миграции БД при каждом запуске контейнера (деплой)
echo "Running database migrations..."
python -c "
from database import init_db
init_db()
print('Migrations OK')
"
exec "$@"
