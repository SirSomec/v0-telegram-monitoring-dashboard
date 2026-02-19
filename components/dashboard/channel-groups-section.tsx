"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { RefreshCw, Users, UserPlus, UserMinus } from "lucide-react"
import { apiJson } from "@/lib/api"

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

export function ChannelGroupsSection({ onSubscribedChange }: { onSubscribedChange?: () => void }) {
  const [groups, setGroups] = useState<ChatGroupAvailableOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")
  const [actingId, setActingId] = useState<number | null>(null)

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
            Администратор объединяет каналы в группы. Подпишитесь на группу — мониторинг всех каналов группы будет включён сразу.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>
          <RefreshCw className={`mr-2 size-4 ${loading ? "animate-spin" : ""}`} />
          Обновить
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        {groups.length === 0 && !loading ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            Нет доступных групп каналов. Администратор может создать группы во вкладке «Группы каналов» в админ-панели и добавить в них каналы с опцией «Доступен всем».
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {groups.map((g) => (
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
                    disabled={actingId !== null}
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
        )}
      </CardContent>
    </Card>
  )
}
