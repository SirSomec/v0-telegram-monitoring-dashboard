"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ExternalLink, UserPlus, Check, MessageSquare, Loader2, CheckCheck, ChevronDown, Download } from "lucide-react"
import { apiBaseUrl, apiJson, wsMentionsUrl, downloadMentionsCsv } from "@/lib/api"
import { getStoredToken } from "@/lib/auth-context"

const PAGE_SIZE = 50

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
  messageLink?: string | null
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

type KeywordOption = { id: number; text: string }

export function MentionFeed({ userId }: { userId?: number }) {
  const [mentions, setMentions] = useState<Mention[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string>("")
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [keywordFilter, setKeywordFilter] = useState<string>("")
  const [keywords, setKeywords] = useState<KeywordOption[]>([])
  const [hasMore, setHasMore] = useState(true)
  const [exporting, setExporting] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const token = typeof window !== "undefined" ? getStoredToken() : null

  useEffect(() => {
    apiJson<KeywordOption[]>(`${apiBaseUrl()}/api/keywords`)
      .then(setKeywords)
      .catch(() => {})
  }, [])

  const initialFetch = useCallback(async () => {
    setLoading(true)
    setError("")
    setHasMore(true)
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: "0" })
      if (unreadOnly) params.set("unreadOnly", "true")
      if (keywordFilter.trim()) params.set("keyword", keywordFilter.trim())
      const data = await apiJson<Mention[]>(`${apiBaseUrl()}/api/mentions?${params}`)
      setMentions(data)
      setHasMore(data.length >= PAGE_SIZE)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }, [unreadOnly, keywordFilter])

  useEffect(() => {
    initialFetch()
  }, [initialFetch])

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return
    setLoadingMore(true)
    setError("")
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(mentions.length),
      })
      if (unreadOnly) params.set("unreadOnly", "true")
      if (keywordFilter.trim()) params.set("keyword", keywordFilter.trim())
      const data = await apiJson<Mention[]>(`${apiBaseUrl()}/api/mentions?${params}`)
      setMentions((prev) => [...prev, ...data])
      setHasMore(data.length >= PAGE_SIZE)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoadingMore(false)
    }
  }, [loadingMore, hasMore, mentions.length, unreadOnly, keywordFilter])

  useEffect(() => {
    if (!token) return
    const url = wsMentionsUrl(token)
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
          const data = payload.data as Mention & { userId?: number }
          if (data.userId === undefined || data.userId === userId) {
            setMentions((prev) => [data, ...prev])
          }
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
  }, [token, userId])

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

  async function markRead(id: string, read: boolean) {
    setError("")
    try {
      await apiJson<Mention>(`${apiBaseUrl()}/api/mentions/${id}/read`, {
        method: "PATCH",
        body: JSON.stringify({ isRead: read }),
      })
      setMentions((prev) =>
        prev.map((x) => (x.id === id ? { ...x, isRead: read } : x))
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обновления")
    }
  }

  async function markAllRead() {
    const unreadCount = mentions.filter((m) => !m.isRead).length
    if (unreadCount === 0) return
    setError("")
    try {
      await apiJson<{ marked: number }>(`${apiBaseUrl()}/api/mentions/mark-all-read`, {
        method: "POST",
      })
      setMentions((prev) => prev.map((m) => ({ ...m, isRead: true })))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обновления")
    }
  }

  const hasUnread = mentions.some((m) => !m.isRead)

  async function handleExportCsv() {
    setExporting(true)
    setError("")
    try {
      await downloadMentionsCsv({
        keyword: keywordFilter.trim() || undefined,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка экспорта")
    } finally {
      setExporting(false)
    }
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-card-foreground">
            <MessageSquare className="size-4 text-primary" />
            Лента упоминаний
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={keywordFilter}
              onChange={(e) => setKeywordFilter(e.target.value)}
              className="h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground"
            >
              <option value="">Все ключевые слова</option>
              {keywords.map((k) => (
                <option key={k.id} value={k.text}>
                  {k.text}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={(e) => setUnreadOnly(e.target.checked)}
                className="rounded border-border"
              />
              Только непрочитанные
            </label>
            {hasUnread ? (
              <Button
                variant="outline"
                size="sm"
                className="h-7 gap-1.5 text-xs"
                onClick={markAllRead}
              >
                <CheckCheck className="size-3" />
                Всё прочитано
              </Button>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              className="h-7 gap-1.5 text-xs"
              onClick={handleExportCsv}
              disabled={exporting}
            >
              {exporting ? <Loader2 className="size-3 animate-spin" /> : <Download className="size-3" />}
              Экспорт CSV
            </Button>
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-xs font-mono">
              {mentions.length}
            </Badge>
          </div>
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

                    <div className="ml-auto flex items-center gap-2 flex-wrap">
                      {mention.messageLink ? (
                        <a
                          href={mention.messageLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
                        >
                          <ExternalLink className="size-3" />
                          К сообщению
                        </a>
                      ) : null}
                      {!mention.isRead ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                          onClick={() => markRead(mention.id, true)}
                        >
                          <CheckCheck className="size-3" />
                          Прочитано
                        </Button>
                      ) : null}
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

        {!loading && mentions.length > 0 && hasMore && (
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              size="sm"
              disabled={loadingMore}
              onClick={loadMore}
              className="gap-2"
            >
              {loadingMore ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <ChevronDown className="size-4" />
              )}
              Загрузить ещё
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
