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

### 2. Создать конфиг Nginx на сервере

**Вариант А:** на сервере есть клон репозитория с папкой `deploy`:
```bash
cd /path/to/v0-telegram-monitoring-dashboard
sudo cp deploy/nginx-integration-wa.ru.conf /etc/nginx/sites-available/telegram-monitor
```

**Вариант Б:** папки `deploy` на сервере нет — создайте файл вручную:
```bash
sudo nano /etc/nginx/sites-available/telegram-monitor
```
Скопируйте в редактор **полный конфиг** из раздела «Конфиг для копирования» в конце этого файла. Сохраните: Ctrl+O, Enter, Ctrl+X.

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
  **Важно:** если эта переменная задана (например `http://IP:8000`), при входе по домену регистрация/авторизация могут не работать (запросы уходят на порт 8000, CORS или фаервол блокируют). По IP:3000 при этом всё работает. Решение: очистить `NEXT_PUBLIC_API_URL` и пересобрать фронт (см. ниже).
- **CORS_ORIGINS** — укажите домен и при необходимости IP:

  ```env
  CORS_ORIGINS=https://integration-wa.ru,http://integration-wa.ru
  ```

После смены `.env` перезапустите бэкенд и при смене `NEXT_PUBLIC_API_URL` — пересоберите фронт:

```bash
docker compose build --no-cache frontend
docker compose up -d --force-recreate
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

---

## Конфиг для копирования (если на сервере нет deploy)

Если на сервере нет файла `deploy/nginx-integration-wa.ru.conf`, создайте `/etc/nginx/sites-available/telegram-monitor` и вставьте целиком:

```nginx
# Nginx: фронтенд по IP и по домену integration-wa.ru
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name integration-wa.ru www.integration-wa.ru;

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

    location /auth {
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
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
