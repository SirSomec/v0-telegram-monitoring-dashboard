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

**Установка на сервер с нуля (порядок шагов):** [docs/INSTALL-SERVER.md](docs/INSTALL-SERVER.md) — клонирование, `.env`, запуск, доступ по домену (в т.ч. integration-wa.ru), первый вход, парсер.

**Установка на чистый Ubuntu (подробно):** [docs/install-ubuntu.md](docs/install-ubuntu.md).

### Требования

- Docker и Docker Compose
- Файл `.env` в корне проекта (скопируйте из `.env.example` и заполните)

### Обязательные переменные в `.env`

- `JWT_SECRET` — **обязательно смените** на случайную строку в проде
- `POSTGRES_PASSWORD` — пароль пользователя PostgreSQL (один и тот же подставляется в контейнер postgres и в `DATABASE_URL` бэкенда). При первом запуске задайте любой пароль; если том БД уже был создан с другим паролем, либо укажите тот же в `.env`, либо пересоздайте том: `docker compose down -v`, затем заново `docker compose up -d`
- `TG_API_ID`, `TG_API_HASH` — данные с my.telegram.org
- `TG_SESSION_STRING` — сессия Telethon (рекомендуется для сервера без интерактивного входа)

### Доступ по домену (главная и весь сайт)

**Если по домену не грузится даже главная страница** — нужен Nginx перед приложением.

1. **Установите Nginx** на сервере (если ещё нет):
   ```bash
   sudo apt install -y nginx
   ```

2. **Скопируйте конфиг и подставьте свой домен:**
   ```bash
   sudo cp deploy/nginx-domain.conf /etc/nginx/sites-available/telegram-monitor
   sudo sed -i 's/YOUR_DOMAIN/ваш-домен.com/' /etc/nginx/sites-available/telegram-monitor
   ```
   (или откройте файл и замените `YOUR_DOMAIN` вручную)

3. **Включите сайт и перезагрузите Nginx:**
   ```bash
   sudo ln -sf /etc/nginx/sites-available/telegram-monitor /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t && sudo systemctl reload nginx
   ```

4. **В `.env` не задавайте `NEXT_PUBLIC_API_URL`** (или оставьте пустым) и **пересоберите фронт**, чтобы запросы шли на тот же домен:
   ```bash
   docker compose up -d --build frontend
   ```

5. **HTTPS** (рекомендуется): `sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx -d ваш-домен.com`

В этом конфиге весь трафик идёт на порт 3000 (фронт), Next.js сам проксирует `/api`, `/auth`, `/ws` на бэкенд. CORS можно не настраивать.

**Вариант: Nginx в Docker (integration-wa.ru, без установки Nginx на хост)**  
В проекте есть сервис `nginx` в `docker-compose.yml` и конфиг `deploy/nginx-integration-wa.ru-docker.conf`. Он проксирует на `frontend:3000` и `backend:8000` внутри сети Docker. Запуск:

```bash
docker compose up -d --build
```

Порт 80 будет отдан контейнеру Nginx. Убедитесь, что на хосте порт 80 свободен (остановите системный Nginx: `sudo systemctl stop nginx`). Домен integration-wa.ru должен указывать на IP сервера. В `.env` оставьте `NEXT_PUBLIC_API_URL` пустым и пересоберите фронт при смене: `docker compose up -d --build frontend`.

**Диагностика:** на сервере выполните `bash deploy/check-domain.sh` или `bash deploy/check-domain.sh integration-wa.ru` — скрипт проверит порты, Nginx и ответ по домену.

### CORS и URL фронта в проде

Если вы **не** используете Nginx и открываете фронт по домену напрямую (например домен:3000):

- `CORS_ORIGINS` — пусто или добавьте ваш домен
- `NEXT_PUBLIC_API_URL` — если API на том же домене, оставьте пустым; если на поддомене — укажите URL API

### Запуск

```bash
docker compose up -d --build
```

- Фронт: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000](http://localhost:8000)
- PostgreSQL: порт 5432 (внутри сети контейнеров — сервис `postgres`)
- Сервис **semantic** (порт 8001 внутри сети): эмбеддинги для ИИ-семантического поиска; образ собирается с PyTorch только для CPU (меньше места на диске). Бэкенд по умолчанию использует его (`SEMANTIC_PROVIDER=http`, `SEMANTIC_SERVICE_URL=http://semantic:8001`). При первом запросе к эмбеддингам модель скачивается (~500 MB).

Таблицы БД создаются при первом запросе к API (init_db). Парсер можно запустить из админки (вкладка «Парсер») или задать `AUTO_START_SCANNER=1` в `.env`.

### Если бэкенд падает при старте

Ошибка `password authentication failed for user "postgres"` означает, что пароль в `DATABASE_URL` не совпадает с паролем, под которым запущен PostgreSQL (пароль задаётся при первом создании тома). Варианты:

1. **Задать в `.env` тот же пароль**, с которым когда-то создавался том postgres, и перезапустить backend: `docker compose up -d --force-recreate backend`.
2. **Пересоздать БД** (все данные удалятся): `docker compose down -v`, в `.env` задать `POSTGRES_PASSWORD=нужный_пароль`, затем `docker compose up -d`.

Подробнее см. [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) (раздел 7, пункт про пароль PostgreSQL).

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
