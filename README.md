# TeleScope — мониторинг Telegram

Дашборд для отслеживания упоминаний ключевых слов в Telegram-чатах в реальном времени. Регистрация и вход по email, разделение данных по пользователям, админ-панель для управления каналами и учётными записями.

## Стек

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, JWT, Telethon (сканер Telegram)
- **Frontend:** Next.js 16, React 19, Tailwind CSS

## Требования

- Python 3.11+
- Node.js 18+ (pnpm)
- PostgreSQL

## Настройка

### 1. Клонирование и зависимости

```bash
# Backend
pip install -r requirements.txt

# Frontend
pnpm install
```

### 2. Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

**Обязательно:**

| Переменная      | Описание |
|-----------------|----------|
| `DATABASE_URL`  | Подключение к PostgreSQL, например: `postgresql+psycopg2://user:pass@localhost:5432/telegram_monitor` |
| `JWT_SECRET`    | Секрет для JWT (в проде обязательно сменить) |
| `TG_API_ID`     | API ID приложения с my.telegram.org |
| `TG_API_HASH`   | API Hash приложения |

**Опционально (бэкенд):**

- `AUTO_START_SCANNER=1` — запускать сканер Telegram вместе с API
- По умолчанию сканер мультипользовательский: чаты и ключевые слова берутся из БД по всем пользователям, упоминания сохраняются с соответствующим `user_id`.
- `MULTI_USER_SCANNER=0` — режим одного пользователя: сканировать только чаты и ключевые слова пользователя с id из `TG_USER_ID`.
- `TG_USER_ID` — id пользователя в БД (используется при `MULTI_USER_SCANNER=0`, по умолчанию 1).
- `TG_SESSION_STRING` или `TG_SESSION_NAME` — сессия Telethon (для работы без интерактивного входа).
- `TG_CHATS` — список чатов через запятую (только в режиме одного пользователя); если пусто — берутся из таблицы `chats`.
- `TG_PROXY_*` — SOCKS5-прокси при необходимости.

**Опционально (фронт):**

- `NEXT_PUBLIC_API_URL` — URL бэкенда. В разработке: `http://localhost:8000`. В проде при прокси через Nginx можно оставить пустым.

### 3. База данных

Создайте БД и при необходимости таблицы:

```bash
# Таблицы создаются при первом запуске API (init_db).
# Для существующей БД после обновления (глобальные каналы и подписки):
python scripts/migrate_global_chats.py
# Для пересоздания схемы (осторожно, данные удалятся):
python recreate_tables.py
```

### 4. Запуск

**Backend (из корня проекта):**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**

```bash
pnpm dev
```

Откройте [http://localhost:3000](http://localhost:3000). Регистрация и вход — на `/auth`, после входа — дашборд на `/dashboard`. Админ-панель — `/admin` (доступна только пользователям с правами администратора).

## Деплой (Docker Compose)

Для развёртывания на сервере используйте Docker и Docker Compose.

**Установка на чистый Ubuntu:** пошаговая инструкция — [docs/install-ubuntu.md](docs/install-ubuntu.md).

### Требования

- Docker и Docker Compose
- Файл `.env` в корне проекта (скопируйте из `.env.example` и заполните)

### Обязательные переменные в `.env`

- `JWT_SECRET` — **обязательно смените** на случайную строку в проде
- `TG_API_ID`, `TG_API_HASH` — данные с my.telegram.org
- `TG_SESSION_STRING` — сессия Telethon (рекомендуется для сервера без интерактивного входа)

### CORS и URL фронта в проде

Если фронт открывается по своему домену (не localhost), задайте в `.env`:

- `CORS_ORIGINS=https://ваш-домен.com` (или несколько через запятую)
- `NEXT_PUBLIC_API_URL=https://api.ваш-домен.com` — если API на поддомене; если Nginx проксирует `/api` и `/ws` на бэкенд с того же домена — оставьте пустым

### Запуск

```bash
docker compose up -d --build
```

- Фронт: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000](http://localhost:8000)
- PostgreSQL: порт 5432 (внутри сети контейнеров — сервис `postgres`)
- Сервис **semantic** (порт 8001 внутри сети): эмбеддинги для ИИ-семантического поиска; бэкенд по умолчанию использует его (`SEMANTIC_PROVIDER=http`, `SEMANTIC_SERVICE_URL=http://semantic:8001`). При первом запросе к эмбеддингам модель скачивается (~500 MB).

Таблицы БД создаются при первом запросе к API (init_db). Парсер можно запустить из админки (вкладка «Парсер») или задать `AUTO_START_SCANNER=1` в `.env`.

### Остановка

```bash
docker compose down
```

Данные PostgreSQL сохраняются в volume `postgres_data`. Для полного удаления с данными: `docker compose down -v`.

### Автоматический деплой

В каталоге `scripts/` лежат скрипты для автоматизации деплоя:

| Скрипт | Назначение |
|--------|------------|
| `scripts/deploy.sh` | Запуск на **сервере**: `docker compose up -d --build` |
| `scripts/remote-deploy.sh` | Запуск **с локальной машины** (Linux/macOS): синхронизация по rsync и вызов `deploy.sh` по SSH |
| `scripts/remote-deploy.ps1` | То же с **Windows** (PowerShell): при наличии WSL/Git Bash — rsync, иначе `git pull` на сервере и `deploy.sh` |

Подробнее см. [scripts/README.md](scripts/README.md).

## Основные сценарии

- **Регистрация** — первый зарегистрированный пользователь получает права администратора.
- **Вход** — JWT сохраняется в localStorage, все запросы к API и WebSocket идут с токеном.
- **Дашборд** — ключевые слова, лента упоминаний в реальном времени (WebSocket). Без входа дашборд перенаправляет на `/auth`.
- **Админка** — каналы, группы каналов, учётные записи. При создании пользователя можно задать пароль (мин. 8 символов).

## Лицензия

Частный проект.
