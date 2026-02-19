# Скрипты деплоя

## deploy.sh — деплой на сервере

Запускается **на сервере** в корне проекта. Поднимает контейнеры через Docker Compose.

```bash
cd /path/to/v0-telegram-monitoring-dashboard
./scripts/deploy.sh
```

Перед первым запуском создайте на сервере файл `.env` (скопируйте из `.env.example` и заполните).

---

## remote-deploy.sh — деплой с локальной машины (Linux/macOS)

Синхронизирует проект на сервер через **rsync** и запускает `deploy.sh` по SSH.

```bash
./scripts/remote-deploy.sh user@host
./scripts/remote-deploy.sh user@host /var/www/telegram-monitor
```

- Файл `.env` **не** копируется — настройте его на сервере вручную.
- Требуются `rsync` и `ssh`.

---

## remote-deploy.ps1 — деплой с Windows

Запуск из PowerShell:

```powershell
.\scripts\remote-deploy.ps1 -Target "user@host"
.\scripts\remote-deploy.ps1 -Target "user@host" -RemotePath "/var/www/telegram-monitor"
```

- Если доступны **WSL** или **Git Bash**, вызывается `remote-deploy.sh` (полная синхронизация через rsync).
- Иначе выполняется по SSH: `git pull` в каталоге проекта на сервере и затем `./scripts/deploy.sh` (на сервере должен быть клон репозитория).

---

## Вариант деплоя через Git

1. На сервере: клонируйте репозиторий, создайте `.env`.
2. С локальной машины пушите изменения в `main` и деплойте:

   ```bash
   ssh user@host 'cd /path/to/project && git pull && ./scripts/deploy.sh'
   ```

   Или используйте `remote-deploy.ps1` без WSL/Git Bash — он сделает то же самое.
