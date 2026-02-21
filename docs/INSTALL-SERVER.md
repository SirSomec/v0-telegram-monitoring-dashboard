# Установка на сервер с нуля (Docker, домен integration-wa.ru)

Порядок действий от чистого сервера до работающего сайта по домену.

---

## 1. Подготовка сервера

- **ОС:** Ubuntu 22.04 LTS (или 20.04).
- **Порты:** 80 (и при необходимости 443 для HTTPS) должны быть открыты в фаерволе/security group.
- Убедитесь, что домен **integration-wa.ru** указывает на IP сервера (A-запись у регистратора).

```bash
# Открыть порт 80 (если используется ufw)
sudo ufw allow 80/tcp
sudo ufw reload
```

---

## 2. Установка Docker и Docker Compose

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
# Выйти и зайти в SSH заново, чтобы применилась группа docker
```

---

## 3. Клонирование проекта

```bash
cd /opt
sudo git clone https://github.com/YOUR_ORG/v0-telegram-monitoring-dashboard.git telegram-monitor
# или свой URL репозитория
cd telegram-monitor
```

Если репозиторий приватный — настройте SSH-ключ или токен для git.

---

## 4. Файл `.env`

```bash
cp .env.example .env
nano .env
```

**Обязательно задать:**

| Переменная | Пример / описание |
|------------|-------------------|
| `POSTGRES_PASSWORD` | Любой пароль (например `SecurePass123`). Один и тот же подставляется в БД и в бэкенд. |
| `JWT_SECRET` | Случайная строка (например `openssl rand -hex 32`). В проде обязательно своя. |
| `TG_API_ID` | Число с https://my.telegram.org (API development tools). |
| `TG_API_HASH` | Строка с той же страницы. |

**Для доступа по домену integration-wa.ru:**

- `NEXT_PUBLIC_API_URL` — **не задавать** или оставить пустым (запросы пойдут на тот же домен).
- `CORS_ORIGINS` — можно не задавать (по умолчанию разрешён любой origin).

**Опционально:**

- `TG_SESSION_STRING` — строка сессии Telethon (чтобы не вводить код вручную на сервере).
- `AUTO_START_SCANNER=1` — автозапуск парсера Telegram при старте бэкенда.
- `NOTIFY_TELEGRAM_BOT_TOKEN` — токен бота **@telescopemsg_bot** для уведомлений пользователей; после запуска настройте webhook (см. раздел «Webhook для бота» ниже).

Сохранить и выйти (Ctrl+O, Enter, Ctrl+X).

---

## 5. Запуск контейнеров (включая Nginx)

В проекте уже есть сервис **nginx** в `docker-compose.yml` — он слушает порт 80 и проксирует на фронт и бэкенд. Отдельно ставить Nginx на хост не нужно.

```bash
cd /opt/telegram-monitor
docker compose up -d --build
```

Первый запуск может занять несколько минут (сборка образов, загрузка модели для semantic при первом запросе).

**Проверка:**

```bash
docker compose ps
```

Должны быть в состоянии Up: postgres, semantic, backend, frontend, nginx.

---

## 6. Проверка по IP и по домену

- По IP сервера: **http://IP_СЕРВЕРА** (порт 80) — должна открыться главная.
- По домену: **http://integration-wa.ru** — то же, если A-запись домена указывает на этот IP.

Диагностика на сервере:

```bash
bash deploy/check-domain.sh integration-wa.ru
```

Если пункт 5 даёт HTTP 200, а в браузере по домену не открывается — проверьте DNS и фаервол (см. конец файла).

---

## 7. Первый вход и парсер

1. Откройте в браузере **http://integration-wa.ru** (или http://IP_СЕРВЕРА).
2. Перейдите в «Регистрация», заведите учётную запись. **Первый зарегистрированный пользователь получает права администратора.**
3. Войдите, перейдите в **Админка** → **Парсер**.
4. В **Настройки парсера** укажите Telegram (API ID, Hash, при необходимости сессию). Сессию можно получить локально и вставить в админке или в `.env` как `TG_SESSION_STRING`.
5. Запустите парсер кнопкой **Запустить** на вкладке «Парсер».
6. В **Дашборд** добавьте ключевые слова и каналы — после этого начнёт заполняться лента упоминаний.

Таблицы БД создаются при первом обращении к API (init_db), отдельно создавать схему не нужно.

---

## 8. HTTPS (рекомендуется)

Если домен уже открывается по HTTP и порт 80 доступен с интернета:

```bash
sudo apt install -y certbot
# Только основной домен (если у www нет DNS-записи — не добавляйте -d www...):
sudo certbot certonly --standalone -d integration-wa.ru
# Либо оба, если в DNS есть A-запись и для www.integration-wa.ru:
# sudo certbot certonly --standalone -d integration-wa.ru -d www.integration-wa.ru
```

**Если Nginx в контейнере (docker compose):**

1. Остановите nginx, чтобы certbot занял порт 80:
   ```bash
   cd /opt/telegram-monitor
   docker compose stop nginx
   ```
2. Получите сертификат (только основной домен):
   ```bash
   sudo certbot certonly --standalone -d integration-wa.ru
   ```
3. В проекте уже должны быть: в `docker-compose.yml` — порт 443 и монтирование `/etc/letsencrypt:/etc/letsencrypt:ro`, в `deploy/nginx-integration-wa.ru-docker.conf` — блок `listen 443 ssl`. Если вы клонировали репозиторий недавно, они там есть. Подтяните изменения (`git pull`) или добавьте вручную (см. [deploy/NGINX-SETUP.md](../deploy/NGINX-SETUP.md)).
4. Запустите nginx снова:
   ```bash
   docker compose start nginx
   ```
5. Проверьте: **https://integration-wa.ru** должен открываться по HTTPS. В `.env` добавьте в `CORS_ORIGINS` значение `https://integration-wa.ru` и перезапустите backend: `docker compose restart backend`.

---

## Webhook для бота @telescopemsg_bot

Чтобы пользователи могли нажать /start в Telegram и получить инструкцию (или «Проверить» после добавления Chat ID в личном кабинете), настройте webhook:

1. В `.env` задайте `NOTIFY_TELEGRAM_BOT_TOKEN` (токен от @BotFather для бота @telescopemsg_bot).
2. Укажите Telegram URL для приёма обновлений. **Токен подставляйте без угловых скобок** (в URL не должно быть символов `<` и `>`):

```bash
# Подставьте вместо 123456:ABC... ваш реальный токен (числа:буквы от BotFather)
curl -X POST "https://api.telegram.org/bot123456:ABC.../setWebhook?url=https://integration-wa.ru/api/telegram-webhook"
```

**Важно:** Telegram принимает webhook только по **HTTPS** (не HTTP и не по IP). Используйте домен с настроенным SSL, например:
```bash
curl -X POST "https://api.telegram.org/botВАШ_ТОКЕН/setWebhook" --data-urlencode "url=https://integration-wa.ru/api/telegram-webhook"
```
(замените `ВАШ_ТОКЕН` на токен целиком, без `<` и `>`). Сначала настройте HTTPS для домена (раздел «HTTPS» выше).

После этого при команде /start в боте пользователь получит инструкцию и кнопку «Проверить».

---

## Сохранность данных при обновлениях

Все пользовательские данные хранятся **только в PostgreSQL** и переживают перезапуск и обновление сервера:

- **Учётные записи**, тариф (`plan_slug`), срок действия тарифа (`plan_expires_at`)
- **Ключевые слова** (отслеживаемые слова), группы каналов, каналы и подписки
- **Настройки уведомлений** (email, Telegram, режим)
- **Упоминания**, настройки парсера (админ), лимиты тарифов

**При обновлении кода и перезапуске контейнеров:**

1. **Не удаляйте том БД.** Команда `docker compose down -v` удаляет том `postgres_data` — все данные будут потеряны. Для обычного обновления используйте:
   ```bash
   git pull
   docker compose up -d --build
   ```
2. При каждом старте бэкенда выполняется `init_db()`: создаются недостающие таблицы и применяются миграции (новые колонки и т.п.). Данные при этом не теряются.
3. Пароль БД в `.env` (`POSTGRES_PASSWORD`) должен оставаться тем же, что и при первом запуске; иначе контейнер PostgreSQL не сможет использовать существующий том.

---

## Краткий порядок (чеклист)

| Шаг | Действие |
|-----|----------|
| 1 | Сервер Ubuntu, порт 80 открыт, DNS: integration-wa.ru → IP сервера |
| 2 | Установить Docker и Docker Compose |
| 3 | Клонировать репозиторий в `/opt/telegram-monitor` |
| 4 | Скопировать `.env.example` в `.env`, задать POSTGRES_PASSWORD, JWT_SECRET, TG_API_ID, TG_API_HASH; NEXT_PUBLIC_API_URL не задавать |
| 5 | `docker compose up -d --build` |
| 6 | Проверить http://IP и http://integration-wa.ru, при проблемах — `bash deploy/check-domain.sh integration-wa.ru` |
| 7 | Зарегистрироваться, войти, в админке настроить парсер и запустить его |
| 8 | (Опционально) Настроить HTTPS через Certbot |

---

## Если что-то пошло не так

- **Ошибка `database "telegram_monitor" does not exist` (Internal Server Error при входе)** — база не была создана (например том PostgreSQL создан до появления `POSTGRES_DB: telegram_monitor` в compose). Создайте БД вручную (данные не теряются):
  ```bash
  cd /opt/telegram-monitor
  docker compose exec postgres psql -U postgres -c 'CREATE DATABASE telegram_monitor;'
  ```
  Затем перезапустите бэкенд: `docker compose restart backend`. Таблицы создадутся при первом запросе к API (init_db).
- **Бэкенд падает с ошибкой про пароль PostgreSQL** — в `.env` должен быть тот же `POSTGRES_PASSWORD`, что использовался при первом запуске; иначе пересоздайте том: `docker compose down -v`, задайте пароль в `.env`, снова `docker compose up -d`.
- **По домену не открывается** — проверьте DNS (`dig +short integration-wa.ru`), фаервол (порт 80), что порт 80 занят именно docker-proxy: `ss -tlnp | grep 80`. Локальная проверка: `curl -H 'Host: integration-wa.ru' http://127.0.0.1:80/` должен вернуть HTTP 200.
- **По IP:3000 работает, по домену нет** — убедитесь, что в `.env` не задан `NEXT_PUBLIC_API_URL` и пересоберите фронт: `docker compose up -d --build frontend`.

Подробнее: [README.md](../README.md), [deploy/TROUBLESHOOT-DOMAIN.md](../deploy/TROUBLESHOOT-DOMAIN.md).
