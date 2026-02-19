"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ExternalLink, UserPlus, Check, MessageSquare, Loader2 } from "lucide-react"
import { apiBaseUrl, apiJson, wsMentionsUrl } from "@/lib/api"

export interface Mention {
  id: string
  groupName: string
  groupIcon: string
  userName: string
  userInitials: string
  message: string
  keyword: string
  timestamp: string
  isLead: boolean
  isRead?: boolean
}

function highlightKeyword(text: string, keyword: string) {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const regex = new RegExp(`(${escaped})`, "gi")
  const parts = text.split(regex)
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="rounded bg-primary/20 px-0.5 text-primary font-medium">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    )
  )
}

export function MentionFeed({ userId = 1 }: { userId?: number }) {
  const [mentions, setMentions] = useState<Mention[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")
  const wsRef = useRef<WebSocket | null>(null)

  const fetchMentions = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<Mention[]>(`${apiBaseUrl()}/api/mentions?userId=${userId}&limit=50`)
      setMentions(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    fetchMentions()
  }, [fetchMentions])

  useEffect(() => {
    const url = wsMentionsUrl(userId)
    if (!url.startsWith("ws")) return
    const ws = new WebSocket(url)
    wsRef.current = ws
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data as string)
        if (payload.type === "init" && Array.isArray(payload.data)) {
          setMentions(payload.data)
        }
        if (payload.type === "mention" && payload.data) {
          setMentions((prev) => [payload.data, ...prev])
        }
      } catch {
        // ignore
      }
    }
    ws.onerror = () => {}
    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [userId])

  async function toggleLead(id: string) {
    const m = mentions.find((x) => x.id === id)
    if (!m) return
    setError("")
    try {
      await apiJson<Mention>(`${apiBaseUrl()}/api/mentions/${id}/lead`, {
        method: "PATCH",
        body: JSON.stringify({ isLead: !m.isLead }),
      })
      setMentions((prev) =>
        prev.map((x) => (x.id === id ? { ...x, isLead: !x.isLead } : x))
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обновления")
    }
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-card-foreground">
            <MessageSquare className="size-4 text-primary" />
            Лента упоминаний
          </CardTitle>
          <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-xs font-mono">
            {mentions.length} результатов
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        {error && <p className="text-sm text-destructive">{error}</p>}
        {loading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground justify-center">
            <Loader2 className="size-4 animate-spin" />
            Загрузка...
          </div>
        ) : (
          mentions.map((mention) => (
            <div
              key={mention.id}
              className="group rounded-lg border border-border bg-secondary/50 p-4 transition-colors hover:bg-secondary/80"
            >
              <div className="flex items-start gap-3">
                <Avatar className="mt-0.5 size-10 shrink-0 border border-border">
                  <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
                    {mention.groupIcon}
                  </AvatarFallback>
                </Avatar>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-card-foreground">
                      {mention.groupName}
                    </span>
                    <span className="text-muted-foreground">{"/"}</span>
                    <span className="text-sm text-muted-foreground">
                      {mention.userName}
                    </span>
                    <Badge variant="outline" className="ml-auto border-border text-xs text-muted-foreground font-mono">
                      {mention.timestamp}
                    </Badge>
                  </div>

                  <p className="mt-2 text-sm leading-relaxed text-secondary-foreground">
                    {highlightKeyword(mention.message, mention.keyword)}
                  </p>

                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <Badge variant="secondary" className="bg-primary/10 text-primary border-0 text-xs">
                      {mention.keyword}
                    </Badge>

                    <div className="ml-auto flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="size-3" />
                        К сообщению
                      </Button>
                      <Button
                        variant={mention.isLead ? "default" : "outline"}
                        size="sm"
                        onClick={() => toggleLead(mention.id)}
                        className={
                          mention.isLead
                            ? "h-7 gap-1.5 text-xs bg-success text-success-foreground hover:bg-success/90"
                            : "h-7 gap-1.5 text-xs border-border text-muted-foreground hover:border-success hover:text-success"
                        }
                      >
                        {mention.isLead ? (
                          <>
                            <Check className="size-3" />
                            Лид сохранён
                          </>
                        ) : (
                          <>
                            <UserPlus className="size-3" />
                            Отметить как лид
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}

        {!loading && mentions.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Упоминаний пока нет. Добавьте ключевые слова и каналы для мониторинга.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
