"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Trash2, Plus, RefreshCw, Search } from "lucide-react"
import { apiJson } from "@/lib/api"

export type ChatOut = {
  id: number
  identifier: string
  title: string | null
  description: string | null
  groupIds: number[]
  enabled: boolean
  userId: number
  isGlobal: boolean
  isOwner: boolean
  hasLinkedChat: boolean
  bundleSize: number
  createdAt: string
}

export type ChatAvailableOut = {
  id: number
  identifier: string
  title: string | null
  description: string | null
  groupNames: string[]
  enabled: boolean
  subscribed: boolean
  subscriptionEnabled: boolean | null
  hasLinkedChat: boolean
  bundleSize: number
  createdAt: string
}

function scoreChannelMatch(ch: ChatAvailableOut, q: string): number {
  const lower = q.toLowerCase().trim()
  if (!lower) return 0
  let score = 0
  const title = (ch.title || "").toLowerCase()
  const desc = (ch.description || "").toLowerCase()
  const ident = (ch.identifier || "").toLowerCase()
  const groupsStr = (ch.groupNames || []).join(" ").toLowerCase()
  if (title.includes(lower)) score += 10
  if (ident.includes(lower)) score += 8
  if (desc.includes(lower)) score += 5
  if (groupsStr.includes(lower)) score += 6
  if (title.startsWith(lower) || ident.startsWith(lower)) score += 4
  return score
}

export function UserChannelsManager(
  {
    canAddResources = true,
    onMyChannelsChange,
    onSubscriptionsChange,
    refreshToken = 0,
  }: {
    canAddResources?: boolean
    onMyChannelsChange?: (count: number) => void
    onSubscriptionsChange?: () => void
    refreshToken?: number
  } = {}
) {
  const [myChannels, setMyChannels] = useState<ChatOut[]>([])
  const [availableChannels, setAvailableChannels] = useState<ChatAvailableOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  const [identifier, setIdentifier] = useState("")
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [enabled, setEnabled] = useState(true)

  const [channelSearchQuery, setChannelSearchQuery] = useState("")

  const filteredAndSortedChannels = useMemo(() => {
    const q = channelSearchQuery.trim()
    if (q.length < 3) return availableChannels
    const withScores = availableChannels
      .map((ch) => ({ ch, score: scoreChannelMatch(ch, q) }))
      .filter((x) => x.score > 0)
    withScores.sort((a, b) => b.score - a.score)
    return withScores.map((x) => x.ch)
  }, [availableChannels, channelSearchQuery])

  async function refresh() {
    setLoading(true)
    setError("")
    try {
      const [mine, available] = await Promise.all([
        apiJson<ChatOut[]>("/api/chats"),
        apiJson<ChatAvailableOut[]>("/api/chats/available"),
      ])
      setMyChannels(mine)
      onMyChannelsChange?.(mine.length)
      setAvailableChannels(available)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [refreshToken])

  const canCreate = identifier.trim().length > 0

  async function createChannel() {
    if (!canCreate) return
    setLoading(true)
    setError("")
    try {
      await apiJson<ChatOut>("/api/chats", {
        method: "POST",
        body: JSON.stringify({
          identifier: identifier.trim(),
          title: title.trim() || null,
          description: description.trim() || null,
          groupIds: [],
          enabled,
        }),
      })
      setIdentifier("")
      setTitle("")
      setDescription("")
      setEnabled(true)
      await refresh()
      onSubscriptionsChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания")
    } finally {
      setLoading(false)
    }
  }

  async function removeChannel(c: ChatOut) {
    setLoading(true)
    setError("")
    try {
      await apiJson<{ ok: boolean }>(`/api/chats/${c.id}`, { method: "DELETE" })
      await refresh()
      onSubscriptionsChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка")
    } finally {
      setLoading(false)
    }
  }

  async function setChannelEnabled(c: ChatOut, value: boolean) {
    if (!c.isOwner) return
    setLoading(true)
    setError("")
    try {
      await apiJson<ChatOut>(`/api/chats/${c.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: value }),
      })
      await refresh()
      onSubscriptionsChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обновления")
    } finally {
      setLoading(false)
    }
  }

  async function subscribe(chatId: number) {
    setLoading(true)
    setError("")
    try {
      await apiJson<ChatOut>(`/api/chats/${chatId}/subscribe`, { method: "POST" })
      await refresh()
      onSubscriptionsChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка подписки")
    } finally {
      setLoading(false)
    }
  }

  const setSubscriptionEnabled = useCallback(async (chatId: number, enabled: boolean) => {
    setLoading(true)
    setError("")
    try {
      await apiJson<ChatOut>(`/api/chats/${chatId}/subscription`, {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      })
      await refresh()
      onSubscriptionsChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обновления")
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <div className="space-y-6">
      <Card className="border-border bg-card">
        <CardHeader>
          {!canAddResources && (
            <p className="text-xs text-amber-600 bg-amber-500/10 border border-amber-500/30 rounded-md px-3 py-2 mb-2">
              Тариф «Без оплаты»: добавление и подписка на каналы недоступны. Раздел «Оплата» или администратор.
            </p>
          )}
          <CardTitle className="text-base font-semibold text-card-foreground">Добавить свой канал</CardTitle>
          <p className="text-sm text-muted-foreground">
            Вставьте ссылку (t.me/… или приглашение t.me/joinchat/…), @username или числовой chat_id.
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Где взять: публичный канал — нажмите на название канала → «Поделиться» / скопировать ссылку или @username из шапки; приватный — ссылку-приглашение даёт админ (t.me/joinchat/…). Либо добавьте в чат бота @userinfobot — он покажет chat_id чата.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="Ссылка, @username или chat_id"
              disabled={!canAddResources}
              className="bg-secondary border-border"
            />
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Название (опционально)"
              className="bg-secondary border-border"
            />
          </div>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Описание (опционально)"
            className="bg-secondary border-border"
          />
          <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-3 py-2">
            <Label htmlFor="enabled-add" className="text-sm text-foreground cursor-pointer">
              Включить мониторинг
            </Label>
            <Switch id="enabled-add" checked={enabled} onCheckedChange={setEnabled} />
          </div>
          <Button onClick={createChannel} disabled={!canAddResources || loading || !canCreate}>
            <Plus className="mr-2 size-4" />
            Добавить канал
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base font-semibold text-card-foreground">Мои каналы для мониторинга</CardTitle>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>
            <RefreshCw className="mr-2 size-4" />
            Обновить
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Канал</TableHead>
                <TableHead>Тип</TableHead>
                <TableHead>Мониторинг</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {myChannels.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="whitespace-normal">
                    <div className="font-medium flex flex-wrap items-center gap-2">
                      <span>{c.title || c.identifier}</span>
                      {c.hasLinkedChat && (
                        <Badge variant="secondary" className="text-[10px]">
                          Канал + обсуждение x{c.bundleSize}
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono">{c.identifier}</div>
                  </TableCell>
                  <TableCell>
                    {c.isOwner ? (
                      <Badge variant="secondary">Свой</Badge>
                    ) : (
                      <Badge variant="outline">От администратора</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={c.enabled}
                      onCheckedChange={(v) =>
                        c.isOwner ? setChannelEnabled(c, v) : setSubscriptionEnabled(c.id, v)
                      }
                      disabled={loading}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => removeChannel(c)}
                      disabled={loading}
                      className="text-destructive hover:text-destructive"
                      title={c.isOwner ? "Удалить канал" : "Отписаться"}
                    >
                      <Trash2 className="size-4" />
                      <span className="ml-1 sr-only sm:not-sr-only">{c.isOwner ? "Удалить" : "Отписаться"}</span>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {myChannels.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-8">
                    Нет каналов. Добавьте свой или выберите из доступных ниже.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-card-foreground">
            Доступные каналы
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Включите мониторинг для нужных каналов — переключатель в колонке «Мониторинг».
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="text-sm font-medium text-foreground mb-2">Каналы</h4>
            {availableChannels.length > 0 && (
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                <Input
                  placeholder="Поиск по названию, описанию или группе (от 3 символов)"
                  value={channelSearchQuery}
                  onChange={(e) => setChannelSearchQuery(e.target.value)}
                  className="pl-9 bg-secondary border-border"
                />
              </div>
            )}
            {availableChannels.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">
                Нет доступных каналов. Администратор может добавить каналы в админ-панели и отметить их как «Доступен всем».
              </p>
            ) : filteredAndSortedChannels.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">
                По запросу «{channelSearchQuery}» ничего не найдено. Измените запрос или очистите поле поиска.
              </p>
            ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Канал</TableHead>
                  <TableHead>Описание</TableHead>
                  <TableHead>Группы</TableHead>
                  <TableHead className="w-[120px]">Мониторинг</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAndSortedChannels.map((av) => (
                  <TableRow key={av.id}>
                    <TableCell className="whitespace-normal">
                      <div className="font-medium flex flex-wrap items-center gap-2">
                        <span>{av.title || av.identifier}</span>
                        {av.hasLinkedChat && (
                          <Badge variant="secondary" className="text-[10px]">
                            Канал + обсуждение x{av.bundleSize}
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground font-mono">{av.identifier}</div>
                    </TableCell>
                    <TableCell className="max-w-[200px]">
                      {av.description ? (
                        <p className="text-xs text-muted-foreground line-clamp-2">{av.description}</p>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[180px]">
                      {(av.groupNames?.length ?? 0) > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {av.groupNames.map((name) => (
                            <Badge key={name} variant="secondary" className="text-xs font-normal">
                              {name}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Switch
                        checked={av.subscribed && (av.subscriptionEnabled ?? true) && av.enabled}
                        onCheckedChange={(v) => {
                          if (av.subscribed) {
                            // Если канал глобально выключен админом, локальное включение
                            // подписки не даст фактического мониторинга.
                            if (v && !av.enabled) return
                            setSubscriptionEnabled(av.id, v)
                          } else {
                            if (v) subscribe(av.id)
                          }
                        }}
                        disabled={loading || (!canAddResources && !av.subscribed)}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
