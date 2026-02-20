"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ExternalLink, UserPlus, Check, MessageSquare, Loader2, CheckCheck, ChevronLeft, ChevronRight, Download } from "lucide-react"
import { apiBaseUrl, apiJson, wsMentionsUrl, downloadMentionsCsv } from "@/lib/api"
import { getStoredToken } from "@/lib/auth-context"

const FEED_PAGE_SIZE = 10

/** Элемент ленты: одно сообщение, все совпавшие ключевые слова (grouped API). */
export interface MentionGroup {
  id: string
  groupName: string
  groupIcon: string
  userName: string
  userInitials: string
  userLink?: string | null
  message: string
  keywords: string[]
  timestamp: string
  isLead: boolean
  isRead?: boolean
  groupLink?: string | null
  messageLink?: string | null
  createdAt?: string
  /** % совпадения с темой по семантике (0–100), только при семантическом совпадении */
  topicMatchPercent?: number | null
}

/** Подсветка всех ключевых слов в тексте (без искажения самого текста). */
function highlightKeywords(text: string, keywords: string[]) {
  if (!keywords.length) return <span>{text}</span>
  const escaped = keywords.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
  const regex = new RegExp(`(${escaped.join("|")})`, "gi")
  const kwSet = new Set(keywords.map((k) => k.toLowerCase()))
  const parts = text.split(regex)
  return (
    <>
      {parts.map((part, i) =>
        part && kwSet.has(part.toLowerCase()) ? (
          <mark key={i} className="rounded bg-primary/20 px-0.5 text-primary font-medium">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

type KeywordOption = { id: number; text: string }

export function MentionFeed({ userId }: { userId?: number }) {
  const [mentions, setMentions] = useState<MentionGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [keywordFilter, setKeywordFilter] = useState<string>("")
  const [searchPhrase, setSearchPhrase] = useState<string>("")
  const [searchQuery, setSearchQuery] = useState<string>("") // debounced для запросов
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc")
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [keywords, setKeywords] = useState<KeywordOption[]>([])
  const [exporting, setExporting] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const fetchPageRef = useRef<() => Promise<void>>(() => Promise.resolve())
  const token = typeof window !== "undefined" ? getStoredToken() : null

  const totalPages = Math.max(1, Math.ceil(totalCount / FEED_PAGE_SIZE))

  useEffect(() => {
    apiJson<KeywordOption[]>(`${apiBaseUrl()}/api/keywords`)
      .then(setKeywords)
      .catch(() => {})
  }, [])

  useEffect(() => {
    const t = setTimeout(() => {
      setSearchQuery(searchPhrase)
      setPage(1)
    }, 300)
    return () => clearTimeout(t)
  }, [searchPhrase])

  const buildParams = useCallback(
    (overrides: { offset?: number } = {}) => {
      const params = new URLSearchParams({
        limit: String(FEED_PAGE_SIZE),
        offset: String(overrides.offset ?? (page - 1) * FEED_PAGE_SIZE),
        sortOrder,
        grouped: "true",
      })
      if (unreadOnly) params.set("unreadOnly", "true")
      if (keywordFilter.trim()) params.set("keyword", keywordFilter.trim())
      if (searchQuery.trim()) params.set("search", searchQuery.trim())
      return params
    },
    [page, sortOrder, unreadOnly, keywordFilter, searchQuery]
  )

  const countParams = useCallback(() => {
    const p: string[] = ["grouped=true"]
    if (unreadOnly) p.push("unreadOnly=true")
    if (keywordFilter.trim()) p.push(`keyword=${encodeURIComponent(keywordFilter.trim())}`)
    if (searchQuery.trim()) p.push(`search=${encodeURIComponent(searchQuery.trim())}`)
    return p.join("&")
  }, [unreadOnly, keywordFilter, searchQuery])

  const fetchPage = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true)
      setError("")
    }
    try {
      const countQuery = countParams()
      const [data, countRes] = await Promise.all([
        apiJson<MentionGroup[]>(`${apiBaseUrl()}/api/mentions?${buildParams()}`),
        apiJson<{ total: number }>(
          `${apiBaseUrl()}/api/mentions/count${countQuery ? `?${countQuery}` : ""}`
        ),
      ])
      setMentions(data)
      setTotalCount(countRes.total)
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      if (!silent) setLoading(false)
    }
  }, [buildParams, countParams])

  fetchPageRef.current = () => fetchPage(false)

  useEffect(() => {
    fetchPage(false)
  }, [fetchPage])

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
          fetchPageRef.current()
        }
        if (payload.type === "mention" && payload.data) {
          const data = payload.data as {
            userId?: number
            id?: string
            groupName?: string
            groupIcon?: string
            userName?: string
            userInitials?: string
            userLink?: string | null
            message?: string
            keyword?: string
            timestamp?: string
            isLead?: boolean
            isRead?: boolean
            createdAt?: string
            messageLink?: string | null
            topicMatchPercent?: number | null
          }
          if (data.userId === undefined || data.userId === userId) {
            // Мгновенно показываем карточку из WebSocket, затем подтягиваем актуальную ленту с сервера
            const optimistic: MentionGroup = {
              id: data.id ?? `ws-${Date.now()}`,
              groupName: data.groupName ?? "—",
              groupIcon: data.groupIcon ?? "??",
              userName: data.userName ?? "—",
              userInitials: data.userInitials ?? "??",
              userLink: data.userLink ?? null,
              message: data.message ?? "",
              keywords: data.keyword ? [data.keyword] : [],
              timestamp: data.timestamp ?? "только что",
              isLead: data.isLead ?? false,
              isRead: data.isRead ?? false,
              messageLink: data.messageLink ?? null,
              createdAt: data.createdAt,
              topicMatchPercent: data.topicMatchPercent ?? null,
            }
            setMentions((prev) => [optimistic, ...prev])
            setTotalCount((c) => c + 1)
            fetchPage(true) // тихий refetch — подставит сгруппированные данные и уберёт дубли
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
            <input
              type="text"
              placeholder="Поиск по тексту..."
              value={searchPhrase}
              onChange={(e) => setSearchPhrase(e.target.value)}
              className="h-8 w-40 rounded-md border border-border bg-secondary px-2 text-xs text-foreground placeholder:text-muted-foreground"
            />
            <select
              value={keywordFilter}
              onChange={(e) => {
                setKeywordFilter(e.target.value)
                setPage(1)
              }}
              className="h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground"
            >
              <option value="">Все ключевые слова</option>
              {keywords.map((k) => (
                <option key={k.id} value={k.text}>
                  {k.text}
                </option>
              ))}
            </select>
            <select
              value={sortOrder}
              onChange={(e) => {
                setSortOrder(e.target.value as "desc" | "asc")
                setPage(1)
              }}
              className="h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground"
            >
              <option value="desc">Сначала новые</option>
              <option value="asc">Сначала старые</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={(e) => {
                  setUnreadOnly(e.target.checked)
                  setPage(1)
                }}
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
              {totalCount}
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
                    {mention.userLink ? (
                      <a
                        href={mention.userLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary hover:underline"
                      >
                        {mention.userName}
                      </a>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        {mention.userName}
                      </span>
                    )}
                    <Badge variant="outline" className="ml-auto border-border text-xs text-muted-foreground font-mono">
                      {mention.timestamp}
                    </Badge>
                  </div>

                  <p className="mt-2 text-sm leading-relaxed text-secondary-foreground whitespace-pre-wrap">
                    {highlightKeywords(mention.message, mention.keywords)}
                  </p>

                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    {mention.keywords.map((kw) => (
                      <Badge key={kw} variant="secondary" className="bg-primary/10 text-primary border-0 text-xs">
                        {kw}
                      </Badge>
                    ))}
                    {mention.topicMatchPercent != null && (
                      <Badge variant="outline" className="text-xs font-mono border-primary/30 text-primary">
                        Совпадение с темой: {mention.topicMatchPercent}%
                      </Badge>
                    )}

                    <div className="ml-auto flex items-center gap-2 flex-wrap">
                      {(mention.groupLink || mention.messageLink) ? (
                        <a
                          href={mention.groupLink || mention.messageLink || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
                        >
                          <ExternalLink className="size-3" />
                          {mention.groupLink ? "В группу" : "К сообщению"}
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

        {!loading && totalCount > 0 && (
          <div className="flex items-center justify-center gap-2 pt-4">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="gap-1"
            >
              <ChevronLeft className="size-3" />
              Назад
            </Button>
            <span className="text-sm text-muted-foreground">
              Страница {page} из {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="gap-1"
            >
              Вперёд
              <ChevronRight className="size-3" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
