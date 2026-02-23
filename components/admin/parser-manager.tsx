"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip"
import { RefreshCw, Play, Square, RotateCw, HelpCircle, Save, FileText, Mail } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type {
  ParserStatus,
  ParserSettings,
  ParserSettingsUpdate,
  EmailStatus,
} from "@/components/admin/types"

const PARSER_HINTS: Record<string, string> = {
  TG_API_ID:
    "Зайдите на https://my.telegram.org → войдите по номеру → API development tools → создайте приложение. API ID — число (например 123456).",
  TG_API_HASH:
    "Рядом с API ID на my.telegram.org отображается API Hash — длинная строка. Скопируйте её сюда.",
  TG_SESSION_STRING:
    "Для работы без интерактивного входа: локально запустите скрипт с Telethon StringSession, войдите в аккаунт один раз, сохраните выданную строку и вставьте сюда. Иначе оставьте пустым и используйте TG_SESSION_NAME.",
  TG_SESSION_NAME:
    "Имя файла сессии (например telegram_monitor). Файл .session создаётся рядом с запуском приложения. Используется, если TG_SESSION_STRING не задан.",
  TG_BOT_TOKEN:
    "Опционально. В Telegram откройте @BotFather → /newbot → создайте бота → скопируйте выданный токен.",
  TG_CHATS:
    "Только для режима «один пользователь». Список чатов через запятую: @username, username или числовые id (-100...). Пусто — чаты из таблицы «Каналы».",
  TG_PROXY_HOST:
    "SOCKS5-прокси (актуально для РФ). Хост, например proxy.example.com или IP.",
  TG_PROXY_PORT: "Порт SOCKS5-прокси (обычно 1080).",
  TG_PROXY_USER: "Логин прокси (если требуется).",
  TG_PROXY_PASS: "Пароль прокси (если требуется).",
  AUTO_START_SCANNER:
    "При запуске API автоматически запускать парсер. Иначе запуск только вручную из этой вкладки.",
  MULTI_USER_SCANNER:
    "Вкл: мониторинг по всем пользователям (чаты и ключевые слова из БД). Выкл: один пользователь — укажите TG_USER_ID.",
  TG_USER_ID:
    "ID пользователя в БД в режиме «один пользователь». Список id можно посмотреть во вкладке «Учётки».",
  // MAX messenger
  MAX_ACCESS_TOKEN:
    "Токен доступа бота для API мессенджера MAX. Получить можно при создании бота в платформе MAX для партнёров (dev.max.ru). Без токена парсер MAX не будет запрашивать сообщения.",
  MAX_BASE_URL:
    "Базовый URL API MAX. По умолчанию: https://platform-api.max.ru. Менять только если используете другой хост.",
  MAX_POLL_INTERVAL_SEC:
    "Интервал опроса чатов MAX в секундах (15–600). Чем меньше — чаще проверка новых сообщений; учтите лимит API (около 30 запросов/сек). Рекомендуется 30–60.",
  AUTO_START_MAX_SCANNER:
    "При запуске API автоматически запускать парсер MAX (Long Polling). Иначе запуск только вручную кнопкой «Запустить» в блоке «Парсер MAX».",
  // Семантический анализ
  SEMANTIC_PROVIDER:
    "http — запросы к отдельному контейнеру semantic (рекомендуется). local — модель в процессе бэкенда. Пусто — семантика отключена.",
  SEMANTIC_SERVICE_URL:
    "URL сервиса эмбеддингов при провайдере http. В Docker: http://semantic:8001. Порог и модель задаются здесь; смена модели в контейнере требует перезапуска сервиса semantic с нужной переменной окружения.",
  SEMANTIC_MODEL_NAME:
    "Имя модели sentence-transformers. По умолчанию paraphrase-multilingual-mpnet-base-v2 (тема сообщения, EN+RU). Для смены модели в контейнере перезапустите сервис semantic с этим значением в env.",
  SEMANTIC_SIMILARITY_THRESHOLD:
    "Порог косинусного сходства 0.0–1.0. Ниже — больше срабатываний (например 0.5–0.55). Выше — строже совпадение (0.65–0.75).",
  MESSAGE_CONCURRENCY:
    "Сколько сообщений обрабатывать одновременно (1–50). Больше — быстрее вывод в дашборд, выше нагрузка на CPU и память. Рекомендуется 10–20.",
  SEMANTIC_EXECUTOR_WORKERS:
    "Число потоков для расчёта семантики (1–16). Больше — быстрее сравнение с ключевыми словами при высокой нагрузке. Рекомендуется 4–8.",
}

function SettingRow({
  id,
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  hint,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  type?: "text" | "password"
  placeholder?: string
  hint: string
}) {
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2">
        <Label htmlFor={id}>{label}</Label>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex text-muted-foreground hover:text-foreground"
                aria-label="Подсказка"
              >
                <HelpCircle className="size-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="max-w-xs">
              {hint}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <Input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="font-mono text-sm"
      />
    </div>
  )
}

export function ParserManager() {
  const [status, setStatus] = useState<ParserStatus | null>(null)
  const [settings, setSettings] = useState<ParserSettings | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)
  const [error, setError] = useState<string>("")
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [parserLogs, setParserLogs] = useState<string[]>([])
  const [logLoading, setLogLoading] = useState(false)
  const [authPending, setAuthPending] = useState(false)
  const [authPhone, setAuthPhone] = useState("")
  const [authCode, setAuthCode] = useState("")
  const [authPassword, setAuthPassword] = useState("")
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState("")
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null)
  const [emailTestLoading, setEmailTestLoading] = useState(false)
  const [emailTestMessage, setEmailTestMessage] = useState<string>("")
  const [emailTestOk, setEmailTestOk] = useState<boolean | null>(null)

  // Локальное состояние формы настроек (для редактирования)
  const [form, setForm] = useState<
    ParserSettingsUpdate & {
      AUTO_START_SCANNER?: boolean
      MULTI_USER_SCANNER?: boolean
      TG_USER_ID?: number
      AUTO_START_MAX_SCANNER?: boolean
      MAX_POLL_INTERVAL_SEC?: number
      MESSAGE_CONCURRENCY?: number
      SEMANTIC_EXECUTOR_WORKERS?: number
    }
  >({})

  async function fetchEmailStatus() {
    try {
      const data = await apiJson<EmailStatus>("/api/admin/email/status")
      setEmailStatus(data)
    } catch {
      setEmailStatus(null)
    }
  }

  async function refresh() {
    setLoading(true)
    setError("")
    try {
      const [statusData, settingsData] = await Promise.all([
        apiJson<ParserStatus>("/api/admin/parser/status"),
        apiJson<ParserSettings>("/api/admin/parser/settings"),
      ])
      setStatus(statusData)
      setSettings(settingsData)
      await fetchEmailStatus()
      setForm({
        ...settingsData,
        AUTO_START_SCANNER: settingsData.AUTO_START_SCANNER === "1" || settingsData.AUTO_START_SCANNER?.toLowerCase() === "true",
        MULTI_USER_SCANNER: settingsData.MULTI_USER_SCANNER !== "0" && (settingsData.MULTI_USER_SCANNER === "1" || settingsData.MULTI_USER_SCANNER?.toLowerCase() === "true"),
        TG_USER_ID: settingsData.TG_USER_ID ? parseInt(settingsData.TG_USER_ID, 10) : undefined,
        MAX_POLL_INTERVAL_SEC: settingsData.MAX_POLL_INTERVAL_SEC ? parseInt(settingsData.MAX_POLL_INTERVAL_SEC, 10) : undefined,
        AUTO_START_MAX_SCANNER: settingsData.AUTO_START_MAX_SCANNER === "1" || settingsData.AUTO_START_MAX_SCANNER?.toLowerCase() === "true",
        MESSAGE_CONCURRENCY: settingsData.MESSAGE_CONCURRENCY ? parseInt(settingsData.MESSAGE_CONCURRENCY, 10) : undefined,
        SEMANTIC_EXECUTOR_WORKERS: settingsData.SEMANTIC_EXECUTOR_WORKERS ? parseInt(settingsData.SEMANTIC_EXECUTOR_WORKERS, 10) : undefined,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки статуса")
    } finally {
      setLoading(false)
    }
  }

  async function fetchLogs() {
    setLogLoading(true)
    try {
      const lines = await apiJson<string[]>("/api/admin/parser/logs")
      setParserLogs(Array.isArray(lines) ? lines : [])
    } catch {
      setParserLogs([])
    } finally {
      setLogLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  useEffect(() => {
    fetchLogs()
  }, [status?.running])

  useEffect(() => {
    if (!status?.running) return
    const interval = setInterval(fetchLogs, 5000)
    return () => clearInterval(interval)
  }, [status?.running])

  async function fetchAuthStatus() {
    try {
      const data = await apiJson<{ pending: boolean }>("/api/admin/parser/auth/status")
      setAuthPending(data.pending)
    } catch {
      setAuthPending(false)
    }
  }

  useEffect(() => {
    fetchAuthStatus()
  }, [])

  useEffect(() => {
    fetchEmailStatus()
  }, [])

  async function sendTestEmail() {
    setEmailTestLoading(true)
    setEmailTestMessage("")
    setEmailTestOk(null)
    try {
      const res = await apiJson<{ ok: boolean; message?: string }>("/api/admin/email/test", {
        method: "POST",
      })
      setEmailTestOk(res.ok)
      setEmailTestMessage(res.message ?? (res.ok ? "Письмо отправлено." : "Ошибка отправки."))
      await fetchLogs()
    } catch (e) {
      setEmailTestOk(false)
      setEmailTestMessage(e instanceof Error ? e.message : "Ошибка запроса")
      await fetchLogs()
    } finally {
      setEmailTestLoading(false)
    }
  }

  async function requestAuthCode() {
    const phone = authPhone.trim()
    if (!phone) {
      setAuthError("Введите номер телефона в формате +79...")
      return
    }
    setAuthLoading(true)
    setAuthError("")
    try {
      await apiJson<{ ok: boolean }>("/api/admin/parser/auth/request-code", {
        method: "POST",
        body: JSON.stringify({ phone }),
      })
      setAuthPending(true)
      setAuthCode("")
      setAuthPassword("")
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : "Не удалось отправить код")
    } finally {
      setAuthLoading(false)
    }
  }

  async function submitAuthCode() {
    const code = authCode.trim()
    if (!code) {
      setAuthError("Введите код из Telegram")
      return
    }
    setAuthLoading(true)
    setAuthError("")
    try {
      await apiJson<{ ok: boolean }>("/api/admin/parser/auth/submit-code", {
        method: "POST",
        body: JSON.stringify({ code, password: authPassword.trim() || null }),
      })
      setAuthPending(false)
      setAuthPhone("")
      setAuthCode("")
      setAuthPassword("")
      await refresh()
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : "Не удалось войти")
    } finally {
      setAuthLoading(false)
    }
  }

  async function startParser() {
    setActionLoading(true)
    setError("")
    try {
      const data = await apiJson<ParserStatus>("/api/admin/parser/start", {
        method: "POST",
      })
      setStatus(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось запустить парсер")
    } finally {
      setActionLoading(false)
    }
  }

  async function stopParser() {
    setActionLoading(true)
    setError("")
    try {
      const data = await apiJson<ParserStatus>("/api/admin/parser/stop", {
        method: "POST",
      })
      setStatus(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось остановить парсер")
    } finally {
      setActionLoading(false)
    }
  }

  async function restartParser() {
    setActionLoading(true)
    setError("")
    try {
      await apiJson<ParserStatus>("/api/admin/parser/stop", { method: "POST" })
      const data = await apiJson<ParserStatus>("/api/admin/parser/start", {
        method: "POST",
      })
      setStatus(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось перезапустить парсер")
    } finally {
      setActionLoading(false)
    }
  }

  async function startMaxParser() {
    setActionLoading(true)
    setError("")
    try {
      const data = await apiJson<ParserStatus>("/api/admin/parser/max/start", {
        method: "POST",
      })
      setStatus(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось запустить парсер MAX")
    } finally {
      setActionLoading(false)
    }
  }

  async function stopMaxParser() {
    setActionLoading(true)
    setError("")
    try {
      const data = await apiJson<ParserStatus>("/api/admin/parser/max/stop", {
        method: "POST",
      })
      setStatus(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось остановить парсер MAX")
    } finally {
      setActionLoading(false)
    }
  }

  function updateForm<K extends keyof ParserSettings>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function saveSettings() {
    if (!settings) return
    setSaveLoading(true)
    setError("")
    setSaveSuccess(false)
    try {
      const maxPollSec =
        typeof form.MAX_POLL_INTERVAL_SEC === "number"
          ? form.MAX_POLL_INTERVAL_SEC
          : settings.MAX_POLL_INTERVAL_SEC
            ? parseInt(settings.MAX_POLL_INTERVAL_SEC, 10)
            : undefined
      const messageConcurrency =
        typeof form.MESSAGE_CONCURRENCY === "number"
          ? form.MESSAGE_CONCURRENCY
          : settings.MESSAGE_CONCURRENCY
            ? parseInt(settings.MESSAGE_CONCURRENCY, 10)
            : undefined
      const semanticWorkers =
        typeof form.SEMANTIC_EXECUTOR_WORKERS === "number"
          ? form.SEMANTIC_EXECUTOR_WORKERS
          : settings.SEMANTIC_EXECUTOR_WORKERS
            ? parseInt(settings.SEMANTIC_EXECUTOR_WORKERS, 10)
            : undefined
      const userId =
        typeof form.TG_USER_ID === "number"
          ? form.TG_USER_ID
          : settings.TG_USER_ID
            ? parseInt(settings.TG_USER_ID, 10)
            : undefined
      // Всегда отправляем полный объект со всеми ключами, чтобы прокси/бэкенд не получали пустое тело
      const payload: ParserSettingsUpdate = {
        TG_API_ID: (form.TG_API_ID ?? settings.TG_API_ID) ?? "",
        TG_API_HASH: (form.TG_API_HASH ?? settings.TG_API_HASH) ?? "",
        TG_SESSION_STRING: (form.TG_SESSION_STRING ?? settings.TG_SESSION_STRING) ?? "",
        TG_SESSION_NAME: (form.TG_SESSION_NAME ?? settings.TG_SESSION_NAME) ?? "",
        TG_BOT_TOKEN: (form.TG_BOT_TOKEN ?? settings.TG_BOT_TOKEN) ?? "",
        TG_CHATS: (form.TG_CHATS ?? settings.TG_CHATS) ?? "",
        TG_PROXY_HOST: (form.TG_PROXY_HOST ?? settings.TG_PROXY_HOST) ?? "",
        TG_PROXY_PORT: (form.TG_PROXY_PORT ?? settings.TG_PROXY_PORT) ?? "",
        TG_PROXY_USER: (form.TG_PROXY_USER ?? settings.TG_PROXY_USER) ?? "",
        TG_PROXY_PASS: (form.TG_PROXY_PASS ?? settings.TG_PROXY_PASS) ?? "",
        AUTO_START_SCANNER: form.AUTO_START_SCANNER ?? false,
        MULTI_USER_SCANNER: form.MULTI_USER_SCANNER ?? true,
        TG_USER_ID: userId ?? null,
        MAX_ACCESS_TOKEN: (form.MAX_ACCESS_TOKEN ?? settings.MAX_ACCESS_TOKEN) ?? "",
        MAX_BASE_URL: (form.MAX_BASE_URL ?? settings.MAX_BASE_URL) ?? "",
        MAX_POLL_INTERVAL_SEC: maxPollSec ?? null,
        AUTO_START_MAX_SCANNER: form.AUTO_START_MAX_SCANNER ?? false,
        SEMANTIC_PROVIDER: (form.SEMANTIC_PROVIDER ?? settings.SEMANTIC_PROVIDER) ?? "",
        SEMANTIC_SERVICE_URL: (form.SEMANTIC_SERVICE_URL ?? settings.SEMANTIC_SERVICE_URL) ?? "",
        SEMANTIC_MODEL_NAME: (form.SEMANTIC_MODEL_NAME ?? settings.SEMANTIC_MODEL_NAME) ?? "",
        SEMANTIC_SIMILARITY_THRESHOLD:
          (form.SEMANTIC_SIMILARITY_THRESHOLD ?? settings.SEMANTIC_SIMILARITY_THRESHOLD) ?? "",
        MESSAGE_CONCURRENCY: messageConcurrency ?? null,
        SEMANTIC_EXECUTOR_WORKERS: semanticWorkers ?? null,
      }
      const data = await apiJson<ParserSettings>("/api/admin/parser/settings", {
        method: "PATCH",
        body: JSON.stringify(payload),
      })
      setSettings(data)
      setForm({
        ...data,
        AUTO_START_SCANNER: data.AUTO_START_SCANNER === "1" || data.AUTO_START_SCANNER?.toLowerCase() === "true",
        MULTI_USER_SCANNER: data.MULTI_USER_SCANNER !== "0" && (data.MULTI_USER_SCANNER === "1" || data.MULTI_USER_SCANNER?.toLowerCase() === "true"),
        TG_USER_ID: data.TG_USER_ID ? parseInt(data.TG_USER_ID, 10) : undefined,
        MAX_POLL_INTERVAL_SEC: data.MAX_POLL_INTERVAL_SEC ? parseInt(data.MAX_POLL_INTERVAL_SEC, 10) : undefined,
        AUTO_START_MAX_SCANNER: data.AUTO_START_MAX_SCANNER === "1" || data.AUTO_START_MAX_SCANNER?.toLowerCase() === "true",
        MESSAGE_CONCURRENCY: data.MESSAGE_CONCURRENCY ? parseInt(data.MESSAGE_CONCURRENCY, 10) : undefined,
        SEMANTIC_EXECUTOR_WORKERS: data.SEMANTIC_EXECUTOR_WORKERS ? parseInt(data.SEMANTIC_EXECUTOR_WORKERS, 10) : undefined,
      })
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения настроек")
    } finally {
      setSaveLoading(false)
    }
  }

  if (loading && status === null) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground text-sm">Загрузка статуса парсера...</p>
        </CardContent>
      </Card>
    )
  }

  const running = status?.running ?? false
  const maxRunning = status?.maxRunning ?? false
  const modeLabel = status?.multiUser
    ? "Мультипользовательский (чаты и ключевые слова всех пользователей)"
    : status?.userId != null
      ? `Один пользователь (user_id: ${status.userId})`
      : "—"

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle>Парсер Telegram</CardTitle>
              <CardDescription>
                Запуск и остановка сканера сообщений. Парсер отслеживает чаты из базы и записывает упоминания ключевых слов.
                Если задано автостарт в настройках ниже, парсер может быть уже запущен — его можно остановить или перезапустить здесь.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={running ? "default" : "secondary"}>
                {running ? "Работает" : "Остановлен"}
              </Badge>
              <Button
                variant="outline"
                size="icon"
                onClick={refresh}
                disabled={loading}
                aria-label="Обновить статус"
              >
                <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {status && (
            <div className="rounded-lg border bg-muted/30 p-3 text-sm">
              <p className="font-medium text-muted-foreground">Режим</p>
              <p className="mt-1">{modeLabel}</p>
            </div>
          )}

          {error && (
            <p className="text-destructive text-sm">{error}</p>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={startParser}
              disabled={running || actionLoading}
              aria-label="Запустить парсер"
            >
              <Play className="mr-2 size-4" />
              Запустить
            </Button>
            <Button
              variant="destructive"
              onClick={stopParser}
              disabled={!running || actionLoading}
              aria-label="Остановить парсер"
            >
              <Square className="mr-2 size-4" />
              Остановить
            </Button>
            <Button
              variant="outline"
              onClick={restartParser}
              disabled={!running || actionLoading}
              aria-label="Перезапустить парсер"
            >
              <RotateCw className="mr-2 size-4" />
              Перезапустить
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle>Парсер MAX</CardTitle>
              <CardDescription>
                Сканер сообщений мессенджера MAX (Long Polling). Добавьте чаты с источником «MAX» в разделе «Каналы», укажите токен и настройки ниже — затем запустите парсер.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={maxRunning ? "default" : "secondary"}>
                {maxRunning ? "Работает" : "Остановлен"}
              </Badge>
              <Button
                variant="outline"
                size="icon"
                onClick={refresh}
                disabled={loading}
                aria-label="Обновить статус"
              >
                <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={startMaxParser}
              disabled={maxRunning || actionLoading}
              aria-label="Запустить парсер MAX"
            >
              <Play className="mr-2 size-4" />
              Запустить
            </Button>
            <Button
              variant="destructive"
              onClick={stopMaxParser}
              disabled={!maxRunning || actionLoading}
              aria-label="Остановить парсер MAX"
            >
              <Square className="mr-2 size-4" />
              Остановить
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Mail className="size-5" />
                Почта (SMTP)
              </CardTitle>
              <CardDescription>
                Проверка настройки отправки писем (сброс пароля, уведомления). Ошибки отправки выводятся в лог парсера ниже.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchEmailStatus}
              disabled={loading}
              aria-label="Обновить статус почты"
            >
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {emailStatus ? (
              <>
                <Badge variant={emailStatus.configured ? "default" : "secondary"}>
                  {emailStatus.configured ? "Настроено" : "Не настроено"}
                </Badge>
                {emailStatus.configured && (
                  <span className="text-muted-foreground text-sm">
                    {emailStatus.smtpHost} : {emailStatus.smtpPort}, от: {emailStatus.smtpFrom}
                  </span>
                )}
              </>
            ) : (
              <span className="text-muted-foreground text-sm">Загрузка…</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={sendTestEmail}
              disabled={!emailStatus?.configured || emailTestLoading}
              aria-label="Отправить тестовое письмо на почту администратора"
            >
              {emailTestLoading ? "Отправка…" : "Отправить тестовое письмо"}
            </Button>
            {emailTestMessage && (
              <span className={emailTestOk === true ? "text-muted-foreground text-sm" : emailTestOk === false ? "text-destructive text-sm" : "text-muted-foreground text-sm"}>
                {emailTestMessage}
              </span>
            )}
          </div>
          {emailStatus && !emailStatus.configured && (
            <p className="text-muted-foreground text-xs">
              Задайте SMTP_HOST, SMTP_USER и SMTP_PASSWORD в переменных окружения или в настройках развёртывания.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-5" />
                Лог парсера
              </CardTitle>
              <CardDescription>
                Последние 80 строк: запуск, остановка, ошибки. Обновляется автоматически при работе парсера.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchLogs}
              disabled={logLoading}
            >
              <RefreshCw className={`mr-2 size-4 ${logLoading ? "animate-spin" : ""}`} />
              Обновить лог
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <pre className="max-h-[320px] overflow-auto rounded-md border bg-muted/50 p-3 font-mono text-xs whitespace-pre-wrap break-all">
            {parserLogs.length === 0 && !logLoading
              ? "Лог пуст. Запустите парсер — здесь появятся сообщения и ошибки."
              : parserLogs.join("\n")}
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Настройки парсера</CardTitle>
          <CardDescription>
            Укажите ID, hash, токены и прочее здесь — переменные в .env можно не задавать. Значения из этой формы сохраняются в БД и имеют приоритет над окружением. После сохранения перезапустите парсер, если он уже запущен.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {settings && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <SettingRow
                  id="TG_API_ID"
                  label="TG API ID"
                  value={form.TG_API_ID ?? settings.TG_API_ID}
                  onChange={(v) => updateForm("TG_API_ID", v)}
                  placeholder="123456"
                  hint={PARSER_HINTS.TG_API_ID}
                />
                <SettingRow
                  id="TG_API_HASH"
                  label="TG API Hash"
                  value={form.TG_API_HASH ?? settings.TG_API_HASH}
                  onChange={(v) => updateForm("TG_API_HASH", v)}
                  type="password"
                  placeholder="abcdef1234567890..."
                  hint={PARSER_HINTS.TG_API_HASH}
                />
                <div className="sm:col-span-2">
                  <SettingRow
                    id="TG_SESSION_STRING"
                    label="TG Session String"
                    value={form.TG_SESSION_STRING ?? settings.TG_SESSION_STRING}
                    onChange={(v) => updateForm("TG_SESSION_STRING", v)}
                    type="password"
                    placeholder="1BVtsOH0Bu..."
                    hint={PARSER_HINTS.TG_SESSION_STRING}
                  />
                </div>
                <div className="sm:col-span-2 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-4">
                  <p className="mb-3 text-sm font-medium">Получить сессию через браузер</p>
                  <p className="mb-3 text-muted-foreground text-xs">
                    Укажите API ID и Hash выше и сохраните настройки. Введите номер — код придёт в приложение Telegram (откройте чат «Telegram» в списке чатов; SMS для входа Telegram не отправляет). Введите код и при необходимости пароль 2FA.
                  </p>
                  {!authPending ? (
                    <div className="flex flex-wrap items-end gap-2">
                      <div className="min-w-[200px] flex-1">
                        <Label htmlFor="auth-phone">Номер телефона</Label>
                        <Input
                          id="auth-phone"
                          type="tel"
                          placeholder="+79001234567"
                          value={authPhone}
                          onChange={(e) => setAuthPhone(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <Button onClick={requestAuthCode} disabled={authLoading}>
                        {authLoading ? "Отправка…" : "Запросить код"}
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-muted-foreground text-xs">
                        Код приходит в чат «Telegram» в приложении (не по SMS). Если не пришёл — проверьте лог парсера выше на ошибки.
                      </p>
                      <div>
                        <Label htmlFor="auth-code">Код из Telegram</Label>
                        <Input
                          id="auth-code"
                          type="text"
                          placeholder="12345"
                          value={authCode}
                          onChange={(e) => setAuthCode(e.target.value)}
                          className="mt-1 font-mono"
                        />
                      </div>
                      <div>
                        <Label htmlFor="auth-password">Пароль 2FA (если включён)</Label>
                        <Input
                          id="auth-password"
                          type="password"
                          placeholder="Не обязательно"
                          value={authPassword}
                          onChange={(e) => setAuthPassword(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <Button onClick={submitAuthCode} disabled={authLoading}>
                        {authLoading ? "Вход…" : "Войти и сохранить сессию"}
                      </Button>
                    </div>
                  )}
                  {authError && (
                    <p className="mt-2 text-destructive text-sm">{authError}</p>
                  )}
                </div>
                <SettingRow
                  id="TG_SESSION_NAME"
                  label="TG Session Name"
                  value={form.TG_SESSION_NAME ?? settings.TG_SESSION_NAME}
                  onChange={(v) => updateForm("TG_SESSION_NAME", v)}
                  placeholder="telegram_monitor"
                  hint={PARSER_HINTS.TG_SESSION_NAME}
                />
                <SettingRow
                  id="TG_BOT_TOKEN"
                  label="TG Bot Token (опционально)"
                  value={form.TG_BOT_TOKEN ?? settings.TG_BOT_TOKEN}
                  onChange={(v) => updateForm("TG_BOT_TOKEN", v)}
                  type="password"
                  placeholder="123456:ABC..."
                  hint={PARSER_HINTS.TG_BOT_TOKEN}
                />
                <div className="sm:col-span-2">
                  <SettingRow
                    id="TG_CHATS"
                    label="TG Chats (режим одного пользователя)"
                    value={form.TG_CHATS ?? settings.TG_CHATS}
                    onChange={(v) => updateForm("TG_CHATS", v)}
                    placeholder="@channel, -1001234567890"
                    hint={PARSER_HINTS.TG_CHATS}
                  />
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="mb-3 text-sm font-medium text-muted-foreground">SOCKS5-прокси</h4>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <SettingRow
                    id="TG_PROXY_HOST"
                    label="Хост"
                    value={form.TG_PROXY_HOST ?? settings.TG_PROXY_HOST}
                    onChange={(v) => updateForm("TG_PROXY_HOST", v)}
                    placeholder="proxy.example.com"
                    hint={PARSER_HINTS.TG_PROXY_HOST}
                  />
                  <SettingRow
                    id="TG_PROXY_PORT"
                    label="Порт"
                    value={form.TG_PROXY_PORT ?? settings.TG_PROXY_PORT}
                    onChange={(v) => updateForm("TG_PROXY_PORT", v)}
                    placeholder="1080"
                    hint={PARSER_HINTS.TG_PROXY_PORT}
                  />
                  <SettingRow
                    id="TG_PROXY_USER"
                    label="Логин"
                    value={form.TG_PROXY_USER ?? settings.TG_PROXY_USER}
                    onChange={(v) => updateForm("TG_PROXY_USER", v)}
                    hint={PARSER_HINTS.TG_PROXY_USER}
                  />
                  <SettingRow
                    id="TG_PROXY_PASS"
                    label="Пароль"
                    value={form.TG_PROXY_PASS ?? settings.TG_PROXY_PASS}
                    onChange={(v) => updateForm("TG_PROXY_PASS", v)}
                    type="password"
                    hint={PARSER_HINTS.TG_PROXY_PASS}
                  />
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="mb-3 text-sm font-medium text-muted-foreground">Режим сканера</h4>
                <div className="flex flex-wrap items-center gap-6">
                  <div className="flex items-center gap-2">
                    <Switch
                      id="AUTO_START_SCANNER"
                      checked={form.AUTO_START_SCANNER ?? false}
                      onCheckedChange={(v) => setForm((p) => ({ ...p, AUTO_START_SCANNER: v }))}
                    />
                    <Label htmlFor="AUTO_START_SCANNER">Автозапуск парсера при старте API</Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button type="button" className="inline-flex text-muted-foreground hover:text-foreground" aria-label="Подсказка">
                            <HelpCircle className="size-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          {PARSER_HINTS.AUTO_START_SCANNER}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      id="MULTI_USER_SCANNER"
                      checked={form.MULTI_USER_SCANNER ?? true}
                      onCheckedChange={(v) => setForm((p) => ({ ...p, MULTI_USER_SCANNER: v }))}
                    />
                    <Label htmlFor="MULTI_USER_SCANNER">Мультипользовательский режим</Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button type="button" className="inline-flex text-muted-foreground hover:text-foreground" aria-label="Подсказка">
                            <HelpCircle className="size-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          {PARSER_HINTS.MULTI_USER_SCANNER}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label htmlFor="TG_USER_ID">TG User ID (если один пользователь)</Label>
                    <Input
                      id="TG_USER_ID"
                      type="number"
                      className="w-24 font-mono"
                      value={form.TG_USER_ID ?? settings.TG_USER_ID ?? ""}
                      onChange={(e) => setForm((p) => ({ ...p, TG_USER_ID: e.target.value ? parseInt(e.target.value, 10) : undefined }))}
                      placeholder="1"
                    />
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button type="button" className="inline-flex text-muted-foreground hover:text-foreground" aria-label="Подсказка">
                            <HelpCircle className="size-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          {PARSER_HINTS.TG_USER_ID}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="mb-3 text-sm font-medium text-muted-foreground">Семантический анализ (ИИ)</h4>
                <p className="mb-3 text-muted-foreground text-xs">
                  Понимание общей темы сообщения и ключевых слов (в т.ч. на английском). Порог и URL применяются сразу; смена модели в контейнере требует перезапуска сервиса semantic.
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <SettingRow
                    id="SEMANTIC_PROVIDER"
                    label="Провайдер"
                    value={form.SEMANTIC_PROVIDER ?? settings.SEMANTIC_PROVIDER ?? ""}
                    onChange={(v) => updateForm("SEMANTIC_PROVIDER", v)}
                    placeholder="http"
                    hint={PARSER_HINTS.SEMANTIC_PROVIDER}
                  />
                  <SettingRow
                    id="SEMANTIC_SERVICE_URL"
                    label="URL сервиса эмбеддингов"
                    value={form.SEMANTIC_SERVICE_URL ?? settings.SEMANTIC_SERVICE_URL ?? ""}
                    onChange={(v) => updateForm("SEMANTIC_SERVICE_URL", v)}
                    placeholder="http://semantic:8001"
                    hint={PARSER_HINTS.SEMANTIC_SERVICE_URL}
                  />
                  <SettingRow
                    id="SEMANTIC_MODEL_NAME"
                    label="Модель"
                    value={form.SEMANTIC_MODEL_NAME ?? settings.SEMANTIC_MODEL_NAME ?? ""}
                    onChange={(v) => updateForm("SEMANTIC_MODEL_NAME", v)}
                    placeholder="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
                    hint={PARSER_HINTS.SEMANTIC_MODEL_NAME}
                  />
                  <div className="grid gap-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor="SEMANTIC_SIMILARITY_THRESHOLD">Порог сходства (0.0–1.0)</Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button type="button" className="inline-flex text-muted-foreground hover:text-foreground" aria-label="Подсказка">
                              <HelpCircle className="size-4" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            {PARSER_HINTS.SEMANTIC_SIMILARITY_THRESHOLD}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Input
                      id="SEMANTIC_SIMILARITY_THRESHOLD"
                      type="text"
                      inputMode="decimal"
                      value={form.SEMANTIC_SIMILARITY_THRESHOLD ?? settings.SEMANTIC_SIMILARITY_THRESHOLD ?? ""}
                      onChange={(e) => updateForm("SEMANTIC_SIMILARITY_THRESHOLD", e.target.value)}
                      placeholder="0.55"
                      className="font-mono text-sm w-24"
                    />
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="mb-3 text-sm font-medium text-muted-foreground">Производительность</h4>
                <p className="mb-3 text-muted-foreground text-xs">
                  Настройки параллельной обработки. Применяются при следующем запуске парсера. Увеличение ускоряет появление сообщений в дашборде и повышает нагрузку на сервер.
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="grid gap-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor="MESSAGE_CONCURRENCY">Одновременная обработка сообщений</Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button type="button" className="inline-flex text-muted-foreground hover:text-foreground" aria-label="Подсказка">
                              <HelpCircle className="size-4" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            {PARSER_HINTS.MESSAGE_CONCURRENCY}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Input
                      id="MESSAGE_CONCURRENCY"
                      type="number"
                      min={1}
                      max={50}
                      value={form.MESSAGE_CONCURRENCY ?? settings.MESSAGE_CONCURRENCY ?? ""}
                      onChange={(e) =>
                        setForm((p) => ({
                          ...p,
                          MESSAGE_CONCURRENCY: e.target.value ? parseInt(e.target.value, 10) : undefined,
                        }))
                      }
                      placeholder="10"
                      className="font-mono text-sm w-28"
                    />
                  </div>
                  <div className="grid gap-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor="SEMANTIC_EXECUTOR_WORKERS">Воркеры семантики</Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button type="button" className="inline-flex text-muted-foreground hover:text-foreground" aria-label="Подсказка">
                              <HelpCircle className="size-4" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            {PARSER_HINTS.SEMANTIC_EXECUTOR_WORKERS}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Input
                      id="SEMANTIC_EXECUTOR_WORKERS"
                      type="number"
                      min={1}
                      max={16}
                      value={form.SEMANTIC_EXECUTOR_WORKERS ?? settings.SEMANTIC_EXECUTOR_WORKERS ?? ""}
                      onChange={(e) =>
                        setForm((p) => ({
                          ...p,
                          SEMANTIC_EXECUTOR_WORKERS: e.target.value ? parseInt(e.target.value, 10) : undefined,
                        }))
                      }
                      placeholder="6"
                      className="font-mono text-sm w-28"
                    />
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="mb-3 text-sm font-medium text-muted-foreground">Парсер MAX</h4>
                <p className="mb-3 text-muted-foreground text-xs">
                  Настройки для мониторинга чатов мессенджера MAX. Чаты с источником «MAX» добавляются в разделе «Каналы» (идентификатор — ID чата в MAX).
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <SettingRow
                    id="MAX_ACCESS_TOKEN"
                    label="MAX Access Token"
                    value={form.MAX_ACCESS_TOKEN ?? settings.MAX_ACCESS_TOKEN ?? ""}
                    onChange={(v) => updateForm("MAX_ACCESS_TOKEN", v)}
                    type="password"
                    placeholder="Токен бота из платформы MAX"
                    hint={PARSER_HINTS.MAX_ACCESS_TOKEN}
                  />
                  <SettingRow
                    id="MAX_BASE_URL"
                    label="MAX Base URL"
                    value={form.MAX_BASE_URL ?? settings.MAX_BASE_URL ?? ""}
                    onChange={(v) => updateForm("MAX_BASE_URL", v)}
                    placeholder="https://platform-api.max.ru"
                    hint={PARSER_HINTS.MAX_BASE_URL}
                  />
                  <div className="grid gap-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor="MAX_POLL_INTERVAL_SEC">Интервал опроса (сек)</Label>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              className="inline-flex text-muted-foreground hover:text-foreground"
                              aria-label="Подсказка"
                            >
                              <HelpCircle className="size-4" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            {PARSER_HINTS.MAX_POLL_INTERVAL_SEC}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Input
                      id="MAX_POLL_INTERVAL_SEC"
                      type="number"
                      min={15}
                      max={600}
                      value={form.MAX_POLL_INTERVAL_SEC ?? settings.MAX_POLL_INTERVAL_SEC ?? ""}
                      onChange={(e) =>
                        setForm((p) => ({
                          ...p,
                          MAX_POLL_INTERVAL_SEC: e.target.value ? parseInt(e.target.value, 10) : undefined,
                        }))
                      }
                      placeholder="60"
                      className="font-mono text-sm w-28"
                    />
                  </div>
                  <div className="flex items-center gap-2 sm:col-span-2">
                    <Switch
                      id="AUTO_START_MAX_SCANNER"
                      checked={form.AUTO_START_MAX_SCANNER ?? false}
                      onCheckedChange={(v) => setForm((p) => ({ ...p, AUTO_START_MAX_SCANNER: v }))}
                    />
                    <Label htmlFor="AUTO_START_MAX_SCANNER">Автозапуск парсера MAX при старте API</Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            className="inline-flex text-muted-foreground hover:text-foreground"
                            aria-label="Подсказка"
                          >
                            <HelpCircle className="size-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          {PARSER_HINTS.AUTO_START_MAX_SCANNER}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 border-t pt-4">
                <Button onClick={saveSettings} disabled={saveLoading}>
                  <Save className="mr-2 size-4" />
                  {saveLoading ? "Сохранение…" : "Сохранить настройки"}
                </Button>
                {saveSuccess && (
                  <span className="text-muted-foreground text-sm">Настройки сохранены.</span>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
