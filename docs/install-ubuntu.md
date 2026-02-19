# Установка TeleScope на чистый сервер Ubuntu

Пошаговая инструкция для развёртывания на Ubuntu 22.04 LTS (или 24.04) с нуля. Все команды выполняются на сервере по SSH.

---

## 1. Подключение и обновление системы

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 2. Установка Docker

Устанавливаем Docker из официального репозитория:

```bash
# Зависимости
sudo apt install -y ca-certificates curl

# Ключ и репозиторий Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Проверка:

```bash
docker --version
docker compose version
```

Опционально: текущий пользователь в группу `docker`, чтобы не писать `sudo`:

```bash
sudo usermod -aG docker "$USER"
# Выйдите из SSH и зайдите снова, чтобы группа применилась
```

---

## 3. Каталог проекта

Выберите каталог, где будет лежать проект (например `/opt/telegram-monitor` или домашняя папка).

**Вариант А: клонирование из Git**

Обратите внимание: в конце команды **точка (`.`)** — клонирование в текущий каталог. Без точки Git создаст подпапку с именем репозитория, и все следующие команды нужно выполнять уже в ней.

```bash
sudo mkdir -p /opt/telegram-monitor
sudo chown "$USER:$USER" /opt/telegram-monitor
cd /opt/telegram-monitor
git clone https://github.com/SirSomec/v0-telegram-monitoring-dashboard.git .
# или, если репозиторий приватный, настройте SSH-ключ и:
# git clone git@github.com:SirSomec/v0-telegram-monitoring-dashboard.git .
```

Если вы уже склонировали **без точки**, перейдите в каталог репозитория и дальше работайте из него:

```bash
cd /opt/telegram-monitor/v0-telegram-monitoring-dashboard
```

**Вариант Б: загрузка архива**

На своей машине соберите архив (без `node_modules`, `.next`, `.env`, `.git`), загрузите на сервер в нужный каталог и распакуйте:

```bash
mkdir -p /opt/telegram-monitor
cd /opt/telegram-monitor
# после загрузки архива:
tar -xvf telescope.tar.gz
```

---

## 4. Файл окружения `.env`

Создайте `.env` из примера и заполните переменные (команды выполняйте **в корне проекта** — там, где лежат `docker-compose.yml` и `.env.example`):

```bash
cd /opt/telegram-monitor   # или cd /opt/telegram-monitor/v0-telegram-monitoring-dashboard
cp .env.example .env
nano .env
```

**Обязательно задайте:**

| Переменная | Пример / описание |
|------------|-------------------|
| `JWT_SECRET` | Длинная случайная строка (например `openssl rand -hex 32`) |
| `TG_API_ID` | Число с [my.telegram.org](https://my.telegram.org) |
| `TG_API_HASH` | Строка с my.telegram.org |
| `TG_SESSION_STRING` | Сессия Telethon (StringSession), созданная локально |

**Для Docker Compose** `DATABASE_URL` можно не менять — в `docker-compose.yml` он переопределён на `postgresql+psycopg2://postgres:postgres@postgres:5432/telegram_monitor`. При одном сервере (фронт :3000, бэкенд :8000) CORS настраивать не нужно — бэкенд по умолчанию разрешает запросы с любого origin.

**Если фронт и API доступны по домену через Nginx**, добавьте в `.env`:

```env
CORS_ORIGINS=https://ваш-домен.com
NEXT_PUBLIC_API_URL=
```

(Если Nginx проксирует API с того же домена, `NEXT_PUBLIC_API_URL` можно оставить пустым.)

**Опционально:** автозапуск парсера при старте контейнеров:

```env
AUTO_START_SCANNER=1
```

Сохраните файл (в nano: `Ctrl+O`, Enter, `Ctrl+X`).

---

## 5. Запуск приложения

Из корня проекта:

```bash
docker compose up -d --build
```

Первый запуск может занять **5–15 минут**: скачиваются образы, ставятся зависимости Python/Node, собирается фронт (Next.js). Это нормально.

Если на этапе `[frontend builder 7/7] RUN pnpm build` или сообщения «Creating an optimized production build» вывод не меняется несколько минут — сборка Next.js тяжёлая на слабом сервере. Подождите 5–10 минут. **Если сервер зависает или SSH отваливается** — используйте вариант без сборки фронта на сервере: раздел **5a** ниже.

Проверка после успешного запуска:

```bash
docker compose ps
```

Должны быть в состоянии `running`: `postgres`, `backend`, `frontend`.

- Фронт: **http://IP_СЕРВЕРА:3000**
- API: **http://IP_СЕРВЕРА:8000**
- Документация API: **http://IP_СЕРВЕРА:8000/docs**

Откройте в браузере `http://IP_СЕРВЕРА:3000`, зарегистрируйтесь — первый пользователь станет администратором.

---

## 5a. Слабый сервер (мало RAM): не собирать фронт на сервере

Если при `docker compose up -d --build` сервер зависает или сборка фронта идёт больше 15–20 минут, соберите образ фронта **на своей машине** (ПК или другой сервер с достаточной памятью) и перенесите его на сервер. На сервере тогда собирается только backend.

**На своей машине** (в каталоге проекта, где есть `Dockerfile.frontend`):

```bash
# Сборка образа фронта (задайте NEXT_PUBLIC_API_URL, если API будет по другому адресу)
export NEXT_PUBLIC_API_URL=   # или например https://api.ваш-домен.com
docker build -f Dockerfile.frontend -t telescope-frontend:latest --build-arg NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" .

# Сохранить образ в файл
docker save telescope-frontend:latest -o telescope-frontend.tar
```

Перенесите `telescope-frontend.tar` на сервер (например через `scp`):

```bash
scp telescope-frontend.tar root@IP_СЕРВЕРА:/opt/telegram-monitor/
```

**На сервере** (в каталоге проекта, где лежат `docker-compose.yml` и `.env`):

```bash
cd /opt/telegram-monitor   # или cd /opt/telegram-monitor/v0-telegram-monitoring-dashboard
docker load -i telescope-frontend.tar
docker compose -f docker-compose.weak-server.yml up -d --build
```

Файл `telescope-frontend.tar` положите в этот же каталог или укажите полный путь в `docker load -i`.

Файл `docker-compose.weak-server.yml` поднимает postgres и backend (backend собирается на сервере — он лёгкий), а frontend берётся из уже загруженного образа `telescope-frontend:latest`. Сборки Node/Next.js на сервере не будет.

---

## 6. Фаервол (опционально)

Если включён `ufw`, откройте порты:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

Для продакшена лучше выставить в интернет только 80/443 и проксировать трафик через Nginx (см. ниже).

---

## 7. Nginx и HTTPS (опционально, для продакшена)

Установка Nginx и Certbot:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Создайте конфиг виртуального хоста (подставьте свой домен):

```bash
sudo nano /etc/nginx/sites-available/telegram-monitor
```

Пример (замените `your-domain.com` на ваш домен):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

Включите сайт и получите сертификат:

```bash
sudo ln -s /etc/nginx/sites-available/telegram-monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com
```

В `.env` на сервере укажите:

```env
CORS_ORIGINS=https://your-domain.com
```

И перезапустите backend:

```bash
docker compose up -d --build backend
```

После этого приложение доступно по **https://your-domain.com**.

---

## 8. Дальнейшие обновления

После изменений в коде на сервере:

```bash
cd /opt/telegram-monitor
git pull
./scripts/deploy.sh
```

Или с локальной машины (если настроен доступ по SSH и путь на сервере известен):

```bash
./scripts/remote-deploy.sh user@IP_СЕРВЕРА /opt/telegram-monitor
```

Подробнее про скрипты деплоя — в [scripts/README.md](../scripts/README.md).

---

## 9. Полезные команды

| Действие | Команда |
|----------|---------|
| Логи всех контейнеров | `docker compose logs -f` |
| Логи только backend | `docker compose logs -f backend` |
| Остановить | `docker compose down` |
| Остановить и удалить данные БД | `docker compose down -v` |
| Перезапустить один сервис | `docker compose up -d --build backend` |

---

## Краткий чеклист

1. Обновить систему: `sudo apt update && sudo apt upgrade -y`
2. Установить Docker и Docker Compose (раздел 2)
3. Создать каталог и положить код (клонировать или загрузить архив)
4. Скопировать `.env.example` в `.env` и заполнить `JWT_SECRET`, `TG_*`, при необходимости `CORS_ORIGINS`
5. Запустить: `docker compose up -d --build`
6. Открыть в браузере `http://IP:3000`, зарегистрироваться
7. (Опционально) Настроить Nginx и HTTPS (раздел 7)
