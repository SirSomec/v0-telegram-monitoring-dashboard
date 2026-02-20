# Настройка Nginx для integration-wa.ru (и по IP)

Чтобы переход по **IP** или по домену **integration-wa.ru** вёл на фронтенд (и API через тот же хост), на сервере нужен Nginx как обратный прокси.

## Предполагается

- На сервере уже запущены контейнеры: фронт на порту **3000**, бэкенд на **8000** (например, `docker compose up -d`).
- Домен integration-wa.ru указывает на IP этого сервера (A-запись в DNS).

## Шаги на сервере

### 1. Установить Nginx и Certbot (если ещё не стоят)

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2. Скопировать конфиг из репозитория

Из корня проекта на сервере (например `/opt/telegram-monitor/v0-telegram-monitoring-dashboard`):

```bash
sudo cp deploy/nginx-integration-wa.ru.conf /etc/nginx/sites-available/telegram-monitor
```

Либо создать файл вручную: `sudo nano /etc/nginx/sites-available/telegram-monitor` и вставить содержимое из `deploy/nginx-integration-wa.ru.conf`.

### 3. Включить сайт и убрать дефолтный сайт Nginx (опционально)

```bash
# Включить наш конфиг
sudo ln -sf /etc/nginx/sites-available/telegram-monitor /etc/nginx/sites-enabled/

# Убрать дефолтную заглушку Nginx, чтобы по IP открывался наш фронт
sudo rm -f /etc/nginx/sites-enabled/default
```

### 4. Проверить конфиг и перезагрузить Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

После этого:

- **http://integration-wa.ru** — фронтенд  
- **http://IP_СЕРВЕРА** — тот же фронтенд (благодаря `default_server`)  
- **http://integration-wa.ru/api/...** и **http://IP_СЕРВЕРА/api/...** — бэкенд

### 5. Переменные окружения на сервере

В `.env` на сервере:

- **NEXT_PUBLIC_API_URL** — оставьте **пустым** или не задавайте. Тогда фронт ходит на тот же хост (`/api`, `/auth`, `/ws`), и Nginx проксирует на бэкенд.
- **CORS_ORIGINS** — укажите домен и при необходимости IP (для доступа по IP с того же сервера можно не добавлять):

  ```env
  CORS_ORIGINS=https://integration-wa.ru,http://integration-wa.ru
  ```

После смены `.env` перезапустите бэкенд:

```bash
docker compose up -d --force-recreate backend
```

### 6. HTTPS (рекомендуется для продакшена)

Когда DNS уже указывает на сервер:

```bash
sudo certbot --nginx -d integration-wa.ru
```

Certbot сам добавит блок `listen 443 ssl` и сертификаты. В `CORS_ORIGINS` добавьте `https://integration-wa.ru` и перезапустите backend.

---

## Краткая шпаргалка

| Действие              | Команда |
|-----------------------|--------|
| Скопировать конфиг    | `sudo cp deploy/nginx-integration-wa.ru.conf /etc/nginx/sites-available/telegram-monitor` |
| Включить сайт         | `sudo ln -sf /etc/nginx/sites-available/telegram-monitor /etc/nginx/sites-enabled/` |
| Убрать default        | `sudo rm -f /etc/nginx/sites-enabled/default` |
| Проверка и перезагрузка | `sudo nginx -t && sudo systemctl reload nginx` |
| HTTPS                 | `sudo certbot --nginx -d integration-wa.ru` |
