# Удалённый деплой с локальной машины (Windows).
# Использование: .\scripts\remote-deploy.ps1 -Target "user@host" [-RemotePath "/path/to/project"]
#
# Вариант 1: если на сервере есть git и вы пушите код в репозиторий —
#   скрипт по SSH выполнит git pull и ./scripts/deploy.sh
# Вариант 2: если установлены WSL или Git Bash — вызывается scripts/remote-deploy.sh (rsync + deploy)

param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [string]$RemotePath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RemotePath) {
    $ProjectName = Split-Path -Leaf $ProjectRoot
    $RemotePath = "~/$ProjectName"
}

Write-Host "[remote-deploy] Сервер: $Target"
Write-Host "[remote-deploy] Путь на сервере: $RemotePath"

# Пробуем запустить bash-скрипт (WSL или Git Bash) для полного деплоя через rsync
$bashScript = Join-Path $ProjectRoot "scripts\remote-deploy.sh"
$bash = $null
if (Get-Command "wsl" -ErrorAction SilentlyContinue) {
    $bash = "wsl"
} elseif (Get-Command "bash" -ErrorAction SilentlyContinue) {
    $bash = "bash"
}

if ($bash -and (Test-Path $bashScript)) {
    Write-Host "[remote-deploy] Запуск через $bash (rsync + deploy)..."
    & $bash $bashScript $Target $RemotePath
    exit $LASTEXITCODE
}

# Иначе: деплой через git pull на сервере (на сервере должен быть клон репозитория)
Write-Host "[remote-deploy] rsync не используется. Выполняем на сервере: git pull и ./scripts/deploy.sh"
$cmd = "cd '$RemotePath' && (test -d .git && (git pull && ./scripts/deploy.sh) || (echo 'Не найден .git. Установите WSL/Git Bash и запустите remote-deploy.sh для синхронизации по rsync.'; exit 1))"
& ssh $Target $cmd
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[remote-deploy] Деплой завершён."
