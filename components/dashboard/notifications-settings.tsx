"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { apiBaseUrl, apiJson } from "@/lib/api"
import { Loader2 } from "lucide-react"

type NotificationSettings = {
  notifyEmail: boolean
  notifyTelegram: boolean
  notifyMode: string
  telegramChatId: string | null
}

const NOTIFY_MODE_OPTIONS = [
  { value: "all", label: "Каждое упоминание" },
  { value: "leads_only", label: "Только лиды" },
  { value: "digest", label: "Дайджест (скоро)" },
] as const

export function NotificationsSettings() {
  const [settings, setSettings] = useState<NotificationSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const [notifyEmail, setNotifyEmail] = useState(true)
  const [notifyTelegram, setNotifyTelegram] = useState(false)
  const [notifyMode, setNotifyMode] = useState("all")
  const [telegramChatId, setTelegramChatId] = useState("")

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")
    apiJson<NotificationSettings>(`${apiBaseUrl()}/api/notifications/settings`)
      .then((data) => {
        if (!cancelled) {
          setSettings(data)
          setNotifyEmail(data.notifyEmail)
          setNotifyTelegram(data.notifyTelegram)
          setNotifyMode(data.notifyMode || "all")
          setTelegramChatId(data.telegramChatId || "")
        }
      })
      .catch(() => {
        if (!cancelled) setError("Не удалось загрузить настройки")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSave() {
    setSaving(true)
    setError("")
    try {
      const data = await apiJson<NotificationSettings>(`${apiBaseUrl()}/api/notifications/settings`, {
        method: "PATCH",
        body: JSON.stringify({
          notifyEmail: notifyEmail,
          notifyTelegram: notifyTelegram,
          notifyMode: notifyMode,
          telegramChatId: telegramChatId.trim() || null,
        }),
      })
      setSettings(data)
      setNotifyEmail(data.notifyEmail)
      setNotifyTelegram(data.notifyTelegram)
      setNotifyMode(data.notifyMode || "all")
      setTelegramChatId(data.telegramChatId || "")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения")
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-card-foreground">Каналы уведомлений</CardTitle>
          <CardDescription className="text-muted-foreground">
            Выберите, куда отправлять уведомления о новых упоминаниях. Email использует адрес вашего аккаунта.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-4 py-3">
            <div>
              <Label htmlFor="notify-email" className="text-base font-medium text-foreground">
                Email
              </Label>
              <p className="text-sm text-muted-foreground">Уведомления на почту аккаунта</p>
            </div>
            <Switch
              id="notify-email"
              checked={notifyEmail}
              onCheckedChange={setNotifyEmail}
            />
          </div>

          <div className="flex flex-col gap-3 rounded-lg border border-border bg-secondary/40 px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="notify-telegram" className="text-base font-medium text-foreground">
                  Telegram
                </Label>
                <p className="text-sm text-muted-foreground">Сообщения в бот @telescopemsg_bot</p>
              </div>
              <Switch
                id="notify-telegram"
                checked={notifyTelegram}
                onCheckedChange={setNotifyTelegram}
              />
            </div>
            {notifyTelegram && (
              <div className="space-y-2 pt-2">
                <Label htmlFor="telegram-chat-id">ID чата или @username</Label>
                <Input
                  id="telegram-chat-id"
                  value={telegramChatId}
                  onChange={(e) => setTelegramChatId(e.target.value)}
                  placeholder="Например: 123456789 или @username"
                  className="bg-background border-border"
                />
                <p className="text-xs text-muted-foreground">
                  Как добавить: начните диалог с ботом @telescopemsg_bot в Telegram (команда /start). Бот покажет ваш Chat ID и инструкцию. Скопируйте Chat ID сюда, сохраните настройки и в боте нажмите «Проверить».
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-card-foreground">Что отправлять</CardTitle>
          <CardDescription className="text-muted-foreground">
            Каждое упоминание — сразу при совпадении. Только лиды — после того как вы отметите упоминание как лид.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {NOTIFY_MODE_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-border bg-secondary/40 px-4 py-3 has-[:checked]:border-primary has-[:checked]:bg-primary/5"
            >
              <input
                type="radio"
                name="notifyMode"
                value={opt.value}
                checked={notifyMode === opt.value}
                onChange={() => setNotifyMode(opt.value)}
                className="size-4 accent-primary"
              />
              <span className="text-sm font-medium text-foreground">{opt.label}</span>
            </label>
          ))}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button onClick={handleSave} disabled={saving}>
        {saving ? <Loader2 className="size-4 animate-spin" /> : "Сохранить настройки"}
      </Button>
    </div>
  )
}
