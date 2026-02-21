"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { RefreshCw, Search, Users, UserPlus, UserMinus, ChevronLeft, ChevronRight } from "lucide-react"
import { apiJson } from "@/lib/api"

const PAGE_SIZE = 6

export type ChatGroupChannelOut = {
  id: number
  identifier: string
  title: string | null
}

export type ChatGroupAvailableOut = {
  id: number
  name: string
  description: string | null
  channelCount: number
  channels: ChatGroupChannelOut[]
  subscribed: boolean
}

function scoreGroupMatch(g: ChatGroupAvailableOut, q: string): number {
  const lower = q.toLowerCase().trim()
  if (!lower) return 0
  let score = 0
  if (g.name.toLowerCase().includes(lower)) score += 10
  if (g.description?.toLowerCase().includes(lower)) score += 3
  for (const c of g.channels) {
    if ((c.title || "").toLowerCase().includes(lower)) score += 5
    if (c.identifier.toLowerCase().includes(lower)) score += 4
    const link = `t.me/${c.identifier.replace(/^@/, "")}`
    if (link.toLowerCase().includes(lower)) score += 4
  }
  return score
}

export function ChannelGroupsSection({ onSubscribedChange, canAddResources = true }: { onSubscribedChange?: () => void; canAddResources?: boolean }) {
  const [groups, setGroups] = useState<ChatGroupAvailableOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")
  const [actingId, setActingId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [page, setPage] = useState(1)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<ChatGroupAvailableOut[]>("/api/chat-groups/available")
      setGroups(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки групп")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const filteredAndSorted = useMemo(() => {
    const q = searchQuery.trim()
    if (q.length < 3) return groups
    const withScores = groups
      .map((g) => ({ g, score: scoreGroupMatch(g, q) }))
      .filter((x) => x.score > 0)
    withScores.sort((a, b) => b.score - a.score)
    return withScores.map((x) => x.g)
  }, [groups, searchQuery])

  const totalPages = Math.max(1, Math.ceil(filteredAndSorted.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const paginatedGroups = useMemo(
    () => filteredAndSorted.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [filteredAndSorted, safePage]
  )

  useEffect(() => {
    setPage((p) => Math.min(p, Math.max(1, Math.ceil(filteredAndSorted.length / PAGE_SIZE)) || 1))
  }, [filteredAndSorted.length])

  async function subscribeGroup(groupId: number) {
    setActingId(groupId)
    setError("")
    try {
      await apiJson<{ ok: boolean; subscribedCount: number }>(
        `/api/chat-groups/${groupId}/subscribe`,
        { method: "POST" }
      )
      await refresh()
      onSubscribedChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка подписки")
    } finally {
      setActingId(null)
    }
  }

  async function unsubscribeGroup(groupId: number) {
    setActingId(groupId)
    setError("")
    try {
      await apiJson<{ ok: boolean; unsubscribedCount: number }>(
        `/api/chat-groups/${groupId}/unsubscribe`,
        { method: "POST" }
      )
      await refresh()
      onSubscribedChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка отписки")
    } finally {
      setActingId(null)
    }
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle className="text-base font-semibold text-card-foreground flex items-center gap-2">
            <Users className="size-5" />
            Группы каналов по тематикам
          </CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Мы собрали сотни каналов в разных тематиках. Подпишитесь на группу — мониторинг всех каналов группы будет включён сразу.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!canAddResources && (
          <p className="text-xs text-amber-600 bg-amber-500/10 border border-amber-500/30 rounded-md px-3 py-2">
            Тариф «Без оплаты»: подписка на группы недоступна. Раздел «Оплата» или администратор.
          </p>
        )}
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        {groups.length > 0 && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
            <Input
              placeholder="Поиск по названию группы, канала или ссылке (от 3 символов)"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setPage(1)
              }}
              className="pl-9 mb-4"
            />
          </div>
        )}
        {groups.length === 0 && !loading ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            Нет доступных групп каналов. Администратор может создать группы во вкладке «Группы каналов» в админ-панели и добавить в них каналы с опцией «Доступен всем».
          </p>
        ) : filteredAndSorted.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            По запросу «{searchQuery}» ничего не найдено. Введите другой запрос или очистите поле поиска.
          </p>
        ) : (
          <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {paginatedGroups.map((g) => (
              <Card key={g.id} className="border-border bg-secondary/30">
                <CardHeader className="pb-2">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <CardTitle className="text-sm font-semibold leading-tight">{g.name}</CardTitle>
                    <Badge variant={g.subscribed ? "default" : "secondary"} className="shrink-0">
                      {g.channelCount} каналов
                    </Badge>
                  </div>
                  {g.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{g.description}</p>
                  )}
                </CardHeader>
                <CardContent className="space-y-3">
                  {g.channels.length > 0 && (
                    <ul className="text-xs text-muted-foreground space-y-0.5 max-h-24 overflow-y-auto">
                      {g.channels.slice(0, 8).map((c) => (
                        <li key={c.id} className="truncate" title={c.title || c.identifier}>
                          {c.title || c.identifier}
                        </li>
                      ))}
                      {g.channels.length > 8 && (
                        <li className="text-muted-foreground/80">… и ещё {g.channels.length - 8}</li>
                      )}
                    </ul>
                  )}
                  <Button
                    size="sm"
                    variant={g.subscribed ? "outline" : "default"}
                    className="w-full"
                    disabled={actingId !== null || (!canAddResources && !g.subscribed)}
                    onClick={() => (g.subscribed ? unsubscribeGroup(g.id) : subscribeGroup(g.id))}
                  >
                    {actingId === g.id ? (
                      <RefreshCw className="mr-2 size-4 animate-spin" />
                    ) : g.subscribed ? (
                      <UserMinus className="mr-2 size-4" />
                    ) : (
                      <UserPlus className="mr-2 size-4" />
                    )}
                    {g.subscribed ? "Отписаться от группы" : "Подписаться на группу"}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
              >
                <ChevronLeft className="size-4 mr-1" />
                Назад
              </Button>
              <span className="text-sm text-muted-foreground px-2">
                {safePage} из {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
              >
                Вперёд
                <ChevronRight className="size-4 ml-1" />
              </Button>
            </div>
          )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
