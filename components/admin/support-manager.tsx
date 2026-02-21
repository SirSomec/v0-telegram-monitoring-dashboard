"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { apiJson } from "@/components/admin/api"
import { Loader2, MessageSquare, ArrowLeft, Send } from "lucide-react"

type SupportTicketItem = {
  id: number
  userId: number
  userEmail?: string | null
  userName?: string | null
  subject: string
  status: string
  createdAt: string
  updatedAt: string
  messageCount: number
  lastMessageAt: string | null
}

type SupportMessageItem = {
  id: number
  ticketId: number
  senderId: number
  isFromStaff: boolean
  body: string
  createdAt: string
}

type SupportTicketDetail = SupportTicketItem & {
  messages: SupportMessageItem[]
}

const STATUS_OPTIONS = [
  { value: "open", label: "Открыт" },
  { value: "answered", label: "Отвечен" },
  { value: "closed", label: "Закрыт" },
]

function formatDate(iso: string) {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60_000) return "только что"
    if (diff < 3600_000) return `${Math.floor(diff / 60_000)} мин назад`
    if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} ч назад`
    return d.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "short",
      year: d.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    })
  } catch {
    return iso
  }
}

export function SupportManager() {
  const [tickets, setTickets] = useState<SupportTicketItem[]>([])
  const [detail, setDetail] = useState<SupportTicketDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const [replyBody, setReplyBody] = useState("")
  const [sending, setSending] = useState(false)
  const [updatingStatus, setUpdatingStatus] = useState(false)

  async function loadTickets() {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<SupportTicketItem[]>("/api/admin/support/tickets")
      setTickets(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить обращения")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTickets()
  }, [])

  async function loadTicketDetail(id: number) {
    setError("")
    try {
      const data = await apiJson<SupportTicketDetail>(`/api/support/tickets/${id}`)
      setDetail(data)
      setReplyBody("")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить обращение")
    }
  }

  async function handleSendReply() {
    if (!detail || !replyBody.trim()) return
    setSending(true)
    setError("")
    try {
      const newMsg = await apiJson<SupportMessageItem>(
        `/api/support/tickets/${detail.id}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ body: replyBody.trim() }),
        }
      )
      setDetail((prev) => (prev ? { ...prev, messages: [...prev.messages, newMsg], status: "answered" } : null))
      setReplyBody("")
      await loadTickets()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка отправки")
    } finally {
      setSending(false)
    }
  }

  async function handleStatusChange(newStatus: string) {
    if (!detail) return
    setUpdatingStatus(true)
    setError("")
    try {
      await apiJson(`/api/support/tickets/${detail.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      })
      setDetail((prev) => (prev ? { ...prev, status: newStatus } : null))
      await loadTickets()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка смены статуса")
    } finally {
      setUpdatingStatus(false)
    }
  }

  const canReply = detail && detail.status !== "closed" && replyBody.trim().length > 0

  if (detail) {
    const userLabel = detail.userName || detail.userEmail || `ID ${detail.userId}`

    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => setDetail(null)} className="gap-2">
          <ArrowLeft className="size-4" />
          К списку обращений
        </Button>
        <Card>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-lg">{detail.subject}</CardTitle>
                <CardDescription>
                  От: {userLabel} · Обращение #{detail.id} · {detail.messageCount} сообщ.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Label htmlFor="admin-ticket-status" className="text-xs text-muted-foreground">
                  Статус
                </Label>
                <Select
                  value={detail.status}
                  onValueChange={handleStatusChange}
                  disabled={updatingStatus}
                >
                  <SelectTrigger id="admin-ticket-status" className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3 max-h-[360px] overflow-y-auto pr-2">
              {detail.messages.map((m) => (
                <div
                  key={m.id}
                  className={
                    m.isFromStaff
                      ? "bg-primary/10 rounded-lg p-3 ml-4 border border-primary/20"
                      : "bg-muted/60 rounded-lg p-3 mr-4"
                  }
                >
                  <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground mb-1">
                    <span>{m.isFromStaff ? "Поддержка" : userLabel}</span>
                    <span>{formatDate(m.createdAt)}</span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap break-words">{m.body}</p>
                </div>
              ))}
            </div>
            {detail.status !== "closed" && (
              <div className="flex gap-2">
                <Textarea
                  placeholder="Ответ пользователю..."
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  rows={2}
                  className="resize-none"
                />
                <Button
                  onClick={handleSendReply}
                  disabled={!canReply || sending}
                  size="icon"
                  className="shrink-0 h-auto"
                >
                  {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="size-5" />
          Обращения в поддержку
        </CardTitle>
        <CardDescription>
          Все обращения пользователей. Откройте тикет, чтобы ответить или изменить статус. При новом сообщении от пользователя вы получите уведомление в Telegram (если в разделе «Уведомления» указан ваш Chat ID).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-muted-foreground flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" />
            Загрузка...
          </p>
        ) : tickets.length === 0 ? (
          <p className="text-muted-foreground">Обращений пока нет.</p>
        ) : (
          <ul className="space-y-2">
            {tickets.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => loadTicketDetail(t.id)}
                  className="w-full text-left rounded-lg border border-border bg-card p-3 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium truncate">{t.subject}</span>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {STATUS_OPTIONS.find((o) => o.value === t.status)?.label ?? t.status} ·{" "}
                      {formatDate(t.lastMessageAt ?? t.updatedAt)}
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">
                    {t.userName || t.userEmail || `User #${t.userId}`} · {t.messageCount} сообщ.
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && <p className="text-sm text-destructive mt-2">{error}</p>}
      </CardContent>
    </Card>
  )
}
