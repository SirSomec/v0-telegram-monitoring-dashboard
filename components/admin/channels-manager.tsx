"use client"

import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Trash2, Plus, RefreshCw } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { Chat, ChatGroup } from "@/components/admin/types"

export function ChannelsManager({ userId = 1 }: { userId?: number }) {
  const [channels, setChannels] = useState<Chat[]>([])
  const [groups, setGroups] = useState<ChatGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  const [identifier, setIdentifier] = useState("")
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([])
  const [enabled, setEnabled] = useState(true)

  async function refresh() {
    setLoading(true)
    setError("")
    try {
      const [ch, gr] = await Promise.all([
        apiJson<Chat[]>(`/api/chats?userId=${userId}`),
        apiJson<ChatGroup[]>(`/api/chat-groups?userId=${userId}`),
      ])
      setChannels(ch)
      setGroups(gr)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const canCreate = useMemo(() => identifier.trim().length > 0, [identifier])

  function toggleGroup(id: number) {
    setSelectedGroupIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function createChannel() {
    if (!canCreate) return
    setLoading(true)
    setError("")
    try {
      await apiJson<Chat>("/api/chats", {
        method: "POST",
        body: JSON.stringify({
          identifier: identifier.trim(),
          title: title.trim() || null,
          description: description.trim() || null,
          groupIds: selectedGroupIds,
          enabled,
          userId,
        }),
      })
      setIdentifier("")
      setTitle("")
      setDescription("")
      setSelectedGroupIds([])
      setEnabled(true)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания")
    } finally {
      setLoading(false)
    }
  }

  async function deleteChannel(id: number) {
    setLoading(true)
    setError("")
    try {
      await apiJson<{ ok: boolean }>(`/api/chats/${id}`, { method: "DELETE" })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления")
    } finally {
      setLoading(false)
    }
  }

  async function setChannelEnabled(channel: Chat, value: boolean) {
    setLoading(true)
    setError("")
    try {
      await apiJson<Chat>(`/api/chats/${channel.id}`, {
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

  const groupNameById = useMemo(() => {
    const map = new Map<number, string>()
    for (const g of groups) map.set(g.id, g.name)
    return map
  }, [groups])

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2 border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-card-foreground">Добавить канал</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
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
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Описание (опционально)"
            className="bg-secondary border-border"
          />

          <div className="rounded-lg border border-border bg-secondary/40 p-3">
            <p className="text-xs font-medium text-muted-foreground">Группы</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {groups.map((g) => {
                const active = selectedGroupIds.includes(g.id)
                return (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => toggleGroup(g.id)}
                    className={
                      active
                        ? "rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs text-primary"
                        : "rounded-md border border-border bg-secondary px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                    }
                  >
                    {g.name}
                  </button>
                )
              })}
              {groups.length === 0 && (
                <span className="text-xs text-muted-foreground">Сначала создайте группы (вкладка “Группы”)</span>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-3 py-2">
            <Label htmlFor="enabled" className="text-sm text-foreground cursor-pointer">
              Мониторить
            </Label>
            <Switch id="enabled" checked={enabled} onCheckedChange={setEnabled} />
          </div>

          <Button onClick={createChannel} disabled={loading || !canCreate} className="w-full">
            <Plus className="mr-2 size-4" />
            Добавить
          </Button>
          <Button variant="outline" onClick={refresh} disabled={loading} className="w-full">
            <RefreshCw className="mr-2 size-4" />
            Обновить
          </Button>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <Card className="lg:col-span-3 border-border bg-card">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base font-semibold text-card-foreground">Каналы мониторинга</CardTitle>
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
                <TableHead>Описание</TableHead>
                <TableHead>Группы</TableHead>
                <TableHead>Мониторинг</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {channels.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="whitespace-normal">
                    <div className="font-medium">{c.title || c.identifier}</div>
                    <div className="text-xs text-muted-foreground font-mono">{c.identifier}</div>
                  </TableCell>
                  <TableCell className="whitespace-normal">{c.description || "—"}</TableCell>
                  <TableCell className="whitespace-normal">
                    <div className="flex flex-wrap gap-1.5">
                      {(c.groupIds || []).map((id) => (
                        <Badge key={id} variant="secondary" className="text-xs">
                          {groupNameById.get(id) ?? `#${id}`}
                        </Badge>
                      ))}
                      {(c.groupIds || []).length === 0 && <span className="text-xs text-muted-foreground">—</span>}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={c.enabled}
                      onCheckedChange={(v) => setChannelEnabled(c, v)}
                      disabled={loading}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deleteChannel(c.id)}
                      disabled={loading}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {channels.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-8">
                    Каналы не добавлены
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

