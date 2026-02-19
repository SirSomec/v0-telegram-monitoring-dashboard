#!/usr/bin/env bash
#
# Удалённый деплой: синхронизация проекта на сервер и запуск deploy.sh по SSH.
# Запускать с локальной машины: ./scripts/remote-deploy.sh [user@]host [путь_на_сервере]
#
# Примеры:
#   ./scripts/remote-deploy.sh myuser@myserver.com
#   ./scripts/remote-deploy.sh myuser@myserver.com /var/www/telegram-monitor
#
# Требования: rsync, ssh. На сервере должен быть уже склонирован проект и настроен .env.
#
set -euo pipefail

REMOTE="${1:-}"
REMOTE_PATH="${2:-}"

if [[ -z "$REMOTE" ]]; then
  echo "Использование: $0 user@host [путь_на_сервере]" >&2
  echo "  путь_на_сервере — каталог проекта на сервере (по умолчанию: текущее имя каталога в домашней директории)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_NAME="$(basename "$PROJECT_ROOT")"

if [[ -z "$REMOTE_PATH" ]]; then
  REMOTE_PATH="~/$(echo "$PROJECT_NAME" | tr ' ' '_')"
fi

echo "[remote-deploy] Локальный проект: $PROJECT_ROOT"
echo "[remote-deploy] Сервер: $REMOTE"
echo "[remote-deploy] Путь на сервере: $REMOTE_PATH"

# Исключения при синхронизации (как в .dockerignore + не трогаем секреты и кэш)
RSYNC_EXCLUDE=(
  --exclude='.git'
  --exclude='.env'
  --exclude='.env.*'
  --exclude='!.env.example'
  --exclude='node_modules'
  --exclude='.next'
  --exclude='.venv'
  --exclude='__pycache__'
  --exclude='*.pyc'
  --exclude='telescope'
)

echo "[remote-deploy] Синхронизация файлов (rsync)..."
rsync -avz --delete "${RSYNC_EXCLUDE[@]}" \
  "$PROJECT_ROOT/" \
  "$REMOTE:$REMOTE_PATH/"

echo "[remote-deploy] Запуск deploy.sh на сервере..."
ssh "$REMOTE" "cd '$REMOTE_PATH' && chmod +x scripts/deploy.sh && ./scripts/deploy.sh"

echo "[remote-deploy] Деплой завершён."
