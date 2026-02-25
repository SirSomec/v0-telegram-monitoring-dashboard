# Почта в контейнере для `integration-wa.ru`

Инструкция для отдельного почтового контейнера (`docker-mailserver`) в этом проекте и ящика `noreply@integration-wa.ru`.

## 1) Подготовка DNS

Добавьте у регистратора домена `integration-wa.ru`:

- `A`: `mail.integration-wa.ru` -> `IP_ВАШЕГО_VPS`
- `MX`: `integration-wa.ru` -> `mail.integration-wa.ru` (priority 10)
- `TXT` SPF:
  - `integration-wa.ru` -> `v=spf1 mx a ip4:IP_ВАШЕГО_VPS -all`
- `TXT` DMARC:
  - `_dmarc.integration-wa.ru` -> `v=DMARC1; p=quarantine; rua=mailto:postmaster@integration-wa.ru; adkim=s; aspf=s`

Также у провайдера VPS задайте reverse DNS (PTR):

- `IP_ВАШЕГО_VPS` -> `mail.integration-wa.ru`

## 2) Порты на сервере

Откройте входящие порты:

- `25/tcp` (SMTP)
- `465/tcp` (SMTPS)
- `587/tcp` (Submission)
- `993/tcp` (IMAPS)

## 3) Сертификат для почты

Почтовому серверу нужен отдельный сертификат для `mail.integration-wa.ru`.

```bash
cd /opt/telegram-monitor
docker compose stop nginx
sudo certbot certonly --standalone -d mail.integration-wa.ru
docker compose start nginx
```

Если `nginx` не запущен или порт 80 свободен, можно не останавливать контейнер.

## 4) Подготовка каталога mailserver

```bash
cd /opt/telegram-monitor
mkdir -p mailserver/config
mkdir -p mailserver/docker-data/mail-data mailserver/docker-data/mail-state mailserver/docker-data/mail-logs
```

## 5) Запуск почтового контейнера

```bash
cd /opt/telegram-monitor
docker compose -f docker-compose.yml -f docker-compose.mail.yml up -d mailserver
```

Проверка:

```bash
docker compose -f docker-compose.yml -f docker-compose.mail.yml ps
docker compose -f docker-compose.yml -f docker-compose.mail.yml logs -f mailserver
```

## 6) Создание ящика `noreply@integration-wa.ru`

Задайте надежный пароль (пример):

```bash
export NOREPLY_PASSWORD='CHANGE_ME_STRONG_PASSWORD'
```

Добавьте почтовый ящик:

```bash
docker run --rm \
  -v "$(pwd)/mailserver/docker-data/mail-data/:/var/mail/" \
  -v "$(pwd)/mailserver/docker-data/mail-state/:/var/mail-state/" \
  -v "$(pwd)/mailserver/docker-data/mail-logs/:/var/log/mail/" \
  -v "$(pwd)/mailserver/config/:/tmp/docker-mailserver/" \
  --entrypoint /usr/local/bin/setup \
  ghcr.io/docker-mailserver/docker-mailserver:latest \
  email add noreply@integration-wa.ru "$NOREPLY_PASSWORD"
```

Перезапустите контейнер:

```bash
docker compose -f docker-compose.yml -f docker-compose.mail.yml restart mailserver
```

## 7) DKIM для домена

Сгенерируйте DKIM-ключи:

```bash
docker run --rm \
  -v "$(pwd)/mailserver/docker-data/mail-data/:/var/mail/" \
  -v "$(pwd)/mailserver/docker-data/mail-state/:/var/mail-state/" \
  -v "$(pwd)/mailserver/docker-data/mail-logs/:/var/log/mail/" \
  -v "$(pwd)/mailserver/config/:/tmp/docker-mailserver/" \
  --entrypoint /usr/local/bin/setup \
  ghcr.io/docker-mailserver/docker-mailserver:latest \
  config dkim
```

Откройте сгенерированную DKIM TXT-запись:

```bash
cat mailserver/config/opendkim/keys/integration-wa.ru/mail.txt
```

После генерации добавьте DKIM TXT из файла:

- `mailserver/config/opendkim/keys/integration-wa.ru/mail.txt`

И перезапустите контейнер:

```bash
docker compose -f docker-compose.yml -f docker-compose.mail.yml restart mailserver
```

## 8) Подключение приложения к SMTP

В `.env` проекта выставьте:

```env
SMTP_HOST=mailserver
SMTP_PORT=587
SMTP_USER=noreply@integration-wa.ru
SMTP_PASSWORD=CHANGE_ME_STRONG_PASSWORD
SMTP_FROM=noreply@integration-wa.ru
SMTP_USE_TLS=1
```

Перезапустите backend:

```bash
docker compose up -d --build backend
```

## 9) Проверка доставки

- В админке TeleScope отправьте тестовое письмо.
- Проверьте репутацию и заголовки на `mail-tester.com`.
- Убедитесь, что в заголовках есть `spf=pass`, `dkim=pass`, `dmarc=pass`.

## Быстрый чеклист

- DNS: `A`, `MX`, `SPF`, `DKIM`, `DMARC`, `PTR`.
- Порты открыты: `25/465/587/993`.
- Есть сертификат для `mail.integration-wa.ru`.
- Создан ящик `noreply@integration-wa.ru`.
- В `.env` backend указан SMTP на `mailserver:587`.
