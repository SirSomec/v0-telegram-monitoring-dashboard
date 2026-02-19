"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { RefreshCw, Play, Square, RotateCw } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { ParserStatus } from "@/components/admin/types"

export function ParserManager() {
  const [status, setStatus] = useState<ParserStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string>("")

  async function refresh() {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<ParserStatus>("/api/admin/parser/status")
      setStatus(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки статуса")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

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
  const modeLabel = status?.multiUser
    ? "Мультипользовательский (чаты и ключевые слова всех пользователей)"
    : status?.userId != null
      ? `Один пользователь (user_id: ${status.userId})`
      : "—"

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <CardTitle>Парсер Telegram</CardTitle>
            <CardDescription>
              Запуск и остановка сканера сообщений. Парсер отслеживает чаты из базы и записывает упоминания ключевых слов.
              Если на сервере задано AUTO_START_SCANNER=1, парсер может быть уже запущен — его можно остановить или перезапустить здесь.
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
  )
}
