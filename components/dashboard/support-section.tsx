"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { apiBaseUrl, apiJson } from "@/lib/api"
import { Loader2, MessageSquare, ArrowLeft, Send } from "lucide-react"

type SupportTicketItem = {
  id: number
  userId: number
  subject: string
  status: string
  createdAt: string
  updatedAt: string
  messageCount: number
  lastMessageAt: string | null
  hasUnread?: boolean
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
  userEmail?: string | null
  userName?: string | null
  messages: SupportMessageItem[]
}

const STATUS_LABELS: Record<string, string> = {
  open: "Открыт",
  answered: "Отвечен",
  closed: "Закрыт",
}

function formatDate(iso: string) {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60_000) return "только что"
    if (diff < 3600_000) return `${Math.floor(diff / 60_000)} мин назад`
    if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} ч назад`
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: d.getFullYear() !== now.getFullYear() ? "numeric" : undefined })
  } catch {
    return iso
  }
}

interface SupportSectionProps {
  onTicketViewed?: () => void
}

export function SupportSection({ onTicketViewed }: SupportSectionProps) {
  const [tickets, setTickets] = useState<SupportTicketItem[]>([])
  const [detail, setDetail] = useState<SupportTicketDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const [subject, setSubject] = useState("")
  const [message, setMessage] = useState("")
  const [creating, setCreating] = useState(false)

  const [replyBody, setReplyBody] = useState("")
  const [sending, setSending] = useState(false)

  async function loadTickets() {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<SupportTicketItem[]>(`${apiBaseUrl()}/api/support/tickets`)
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
      const data = await apiJson<SupportTicketDetail>(`${apiBaseUrl()}/api/support/tickets/${id}`)
      setDetail(data)
      setReplyBody("")
      onTicketViewed?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить обращение")
    }
  }

  async function handleCreate() {
    const sub = subject.trim()
    const msg = message.trim()
    if (!sub || !msg) return
    setCreating(true)
    setError("")
    try {
      const created = await apiJson<SupportTicketDetail>(`${apiBaseUrl()}/api/support/tickets`, {
        method: "POST",
        body: JSON.stringify({ subject: sub, message: msg }),
      })
      setSubject("")
      setMessage("")
      setTickets((prev) => [{ ...created, messages: [] }, ...prev])
      setDetail(created)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания обращения")
    } finally {
      setCreating(false)
    }
  }

  async function handleSendReply() {
    if (!detail || !replyBody.trim()) return
    setSending(true)
    setError("")
    try {
      const newMsg = await apiJson<SupportMessageItem>(`${apiBaseUrl()}/api/support/tickets/${detail.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ body: replyBody.trim() }),
      })
      setDetail((prev) => (prev ? { ...prev, messages: [...prev.messages, newMsg] } : null))
      setReplyBody("")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка отправки")
    } finally {
      setSending(false)
    }
  }

  const canReply = detail && detail.status !== "closed" && replyBody.trim().length > 0

  if (detail) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => setDetail(null)} className="gap-2">
          <ArrowLeft className="size-4" />
          К списку обращений
        </Button>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">{detail.subject}</CardTitle>
            <CardDescription>
              Обращение #{detail.id} · {STATUS_LABELS[detail.status] ?? detail.status} · {detail.messageCount} сообщ.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3 max-h-[360px] overflow-y-auto pr-2">
              {detail.messages.map((m) => (
                <div
                  key={m.id}
                  className={m.isFromStaff ? "bg-muted/60 rounded-lg p-3 ml-4" : "bg-primary/10 rounded-lg p-3 mr-4"}
                >
                  <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground mb-1">
                    <span>{m.isFromStaff ? "Поддержка" : "Вы"}</span>
                    <span>{formatDate(m.createdAt)}</span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap break-words">{m.body}</p>
                </div>
              ))}
            </div>
            {detail.status !== "closed" && (
              <div className="flex gap-2">
                <Textarea
                  placeholder="Напишите сообщение..."
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  rows={2}
                  className="resize-none"
                />
                <Button onClick={handleSendReply} disabled={!canReply || sending} size="icon" className="shrink-0 h-auto">
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
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="size-5" />
            Новое обращение
          </CardTitle>
          <CardDescription>
            Опишите вопрос или проблему — администратор ответит в этом разделе и при необходимости уведомит вас.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="support-subject">Тема</Label>
            <Input
              id="support-subject"
              placeholder="Кратко о чём обращение"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              maxLength={300}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="support-message">Сообщение</Label>
            <Textarea
              id="support-message"
              placeholder="Подробно опишите вопрос..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              className="resize-none"
              maxLength={10000}
            />
          </div>
          <Button
            onClick={handleCreate}
            disabled={!subject.trim() || !message.trim() || creating}
          >
            {creating ? <Loader2 className="size-4 animate-spin mr-2" /> : null}
            Отправить обращение
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Мои обращения</CardTitle>
          <CardDescription>Список ваших обращений в поддержку</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground flex items-center gap-2">
              <Loader2 className="size-4 animate-spin" />
              Загрузка...
            </p>
          ) : tickets.length === 0 ? (
            <p className="text-muted-foreground">Пока нет обращений. Создайте новое выше.</p>
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
                      <span className="font-medium truncate flex items-center gap-2">
                        {t.subject}
                        {t.hasUnread && (
                          <span className="size-2 rounded-full bg-destructive shrink-0" aria-hidden />
                        )}
                      </span>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {STATUS_LABELS[t.status] ?? t.status} · {formatDate(t.lastMessageAt ?? t.updatedAt)}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {t.messageCount} сообщ.
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
