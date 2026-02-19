#!/usr/bin/env bash
#
# Скрипт деплоя на сервере.
# Запускать из корня проекта на сервере: ./scripts/deploy.sh
# Или по SSH: ssh user@host 'cd /path/to/project && ./scripts/deploy.sh'
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "[deploy] Проект: $PROJECT_ROOT"

# Проверка Docker
if ! command -v docker &>/dev/null; then
  echo "[deploy] Ошибка: docker не найден. Установите Docker." >&2
  exit 1
fi
if ! docker compose version &>/dev/null; then
  echo "[deploy] Ошибка: docker compose не найден. Установите Docker Compose." >&2
  exit 1
fi

# Проверка .env
if [[ ! -f .env ]]; then
  echo "[deploy] Ошибка: файл .env не найден. Скопируйте .env.example в .env и заполните переменные." >&2
  exit 1
fi

# Опционально: обновление из git (раскомментируйте, если деплой через git pull)
# git fetch origin
# git reset --hard origin/main

echo "[deploy] Запуск: docker compose up -d --build"
docker compose up -d --build

echo "[deploy] Готово. Проверка контейнеров:"
docker compose ps
