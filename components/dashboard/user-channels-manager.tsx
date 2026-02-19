"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Trash2, Plus, RefreshCw, UserPlus } from "lucide-react"
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
  createdAt: string
}

export type ChatAvailableOut = {
  id: number
  identifier: string
  title: string | null
  description: string | null
  enabled: boolean
  subscribed: boolean
  createdAt: string
}

export function UserChannelsManager() {
  const [myChannels, setMyChannels] = useState<ChatOut[]>([])
  const [availableChannels, setAvailableChannels] = useState<ChatAvailableOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  const [identifier, setIdentifier] = useState("")
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [enabled, setEnabled] = useState(true)

  async function refresh() {
    setLoading(true)
    setError("")
    try {
      const [mine, available] = await Promise.all([
        apiJson<ChatOut[]>("/api/chats"),
        apiJson<ChatAvailableOut[]>("/api/chats/available"),
      ])
      setMyChannels(mine)
      setAvailableChannels(available)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка подписки")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-card-foreground">Добавить свой канал</CardTitle>
          <p className="text-sm text-muted-foreground">
            Введите @username канала или группы в Telegram либо числовой chat_id (например -100xxxxxxxxxx).
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="@username или chat_id (-100...)"
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
          <Button onClick={createChannel} disabled={loading || !canCreate}>
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
                    <div className="font-medium">{c.title || c.identifier}</div>
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
                    {c.isOwner ? (
                      <Switch
                        checked={c.enabled}
                        onCheckedChange={(v) => setChannelEnabled(c, v)}
                        disabled={loading}
                      />
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        {c.enabled ? "Включён" : "Выключен"}
                      </span>
                    )}
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
            Доступные каналы (добавлены администратором)
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Подпишитесь на каналы, которые администратор сделал доступными для всех пользователей.
          </p>
        </CardHeader>
        <CardContent>
          {availableChannels.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">
              Нет доступных каналов. Администратор может добавить каналы в админ-панели и отметить их как «Доступен всем».
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Канал</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="text-right">Действие</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {availableChannels.map((av) => (
                  <TableRow key={av.id}>
                    <TableCell className="whitespace-normal">
                      <div className="font-medium">{av.title || av.identifier}</div>
                      <div className="text-xs text-muted-foreground font-mono">{av.identifier}</div>
                    </TableCell>
                    <TableCell>
                      {av.subscribed ? (
                        <Badge variant="default">Подписан</Badge>
                      ) : (
                        <span className="text-sm text-muted-foreground">Не подписан</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {av.subscribed ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => removeChannel({ id: av.id } as ChatOut)}
                          disabled={loading}
                        >
                          Отписаться
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          onClick={() => subscribe(av.id)}
                          disabled={loading}
                        >
                          <UserPlus className="mr-2 size-4" />
                          Подписаться
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
