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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Trash2, Plus, RefreshCw, Pencil } from "lucide-react"
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
  const [isGlobal, setIsGlobal] = useState(false)

  const [editingChannel, setEditingChannel] = useState<Chat | null>(null)
  const [editTitle, setEditTitle] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [editGroupIds, setEditGroupIds] = useState<number[]>([])
  const [editEnabled, setEditEnabled] = useState(true)
  const [editIsGlobal, setEditIsGlobal] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const [editError, setEditError] = useState("")

  async function refresh() {
    setLoading(true)
    setError("")
    try {
      const [ch, gr] = await Promise.all([
        apiJson<Chat[]>("/api/chats"),
        apiJson<ChatGroup[]>("/api/chat-groups"),
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

  function openEdit(c: Chat) {
    setEditingChannel(c)
    setEditTitle(c.title ?? "")
    setEditDescription(c.description ?? "")
    setEditGroupIds(c.groupIds ?? [])
    setEditEnabled(c.enabled ?? true)
    setEditIsGlobal(c.isGlobal ?? false)
    setEditError("")
  }

  function toggleEditGroup(id: number) {
    setEditGroupIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function saveEdit() {
    if (!editingChannel) return
    setSavingEdit(true)
    setEditError("")
    try {
      await apiJson<Chat>(`/api/chats/${editingChannel.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editTitle.trim() || null,
          description: editDescription.trim() || null,
          groupIds: editGroupIds,
          enabled: editEnabled,
          isGlobal: editIsGlobal,
        }),
      })
      setEditingChannel(null)
      await refresh()
    } catch (e) {
      setEditError(e instanceof Error ? e.message : "Ошибка сохранения")
    } finally {
      setSavingEdit(false)
    }
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
          isGlobal,
        }),
      })
      setIdentifier("")
      setTitle("")
      setDescription("")
      setSelectedGroupIds([])
      setEnabled(true)
      setIsGlobal(false)
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

  async function setChannelGlobal(channel: Chat, value: boolean) {
    setLoading(true)
    setError("")
    try {
      await apiJson<Chat>(`/api/chats/${channel.id}`, {
        method: "PATCH",
        body: JSON.stringify({ isGlobal: value }),
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
            placeholder="Ссылка (t.me/…), @username или chat_id"
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
            <p className="text-xs font-medium text-muted-foreground">Группы (канал может входить в несколько)</p>
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
                <span className="text-xs text-muted-foreground">Сначала создайте группы (вкладка «Группы каналов»)</span>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-3 py-2">
            <Label htmlFor="enabled" className="text-sm text-foreground cursor-pointer">
              Мониторить
            </Label>
            <Switch id="enabled" checked={enabled} onCheckedChange={setEnabled} />
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-3 py-2">
            <Label htmlFor="isGlobal" className="text-sm text-foreground cursor-pointer">
              Доступен всем пользователям
            </Label>
            <Switch
              id="isGlobal"
              checked={isGlobal}
              onCheckedChange={setIsGlobal}
              title="Канал появится в разделе «Группы» у всех пользователей для подписки"
            />
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
          <div>
            <CardTitle className="text-base font-semibold text-card-foreground">Каналы мониторинга</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">Канал может входить в несколько групп. Используйте «Изменить» для смены групп.</p>
          </div>
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
                <TableHead>Всем</TableHead>
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
                      checked={c.isGlobal ?? false}
                      onCheckedChange={(v) => setChannelGlobal(c, v)}
                      disabled={loading}
                      title="Доступен всем для подписки"
                    />
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={c.enabled}
                      onCheckedChange={(v) => setChannelEnabled(c, v)}
                      disabled={loading}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openEdit(c)}
                        disabled={loading}
                        title="Изменить группы и настройки"
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => deleteChannel(c.id)}
                        disabled={loading}
                        className="text-destructive hover:text-destructive"
                        title="Удалить канал"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {channels.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-8">
                    Каналы не добавлены
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={!!editingChannel} onOpenChange={(open) => !open && setEditingChannel(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Редактировать канал</DialogTitle>
          </DialogHeader>
          {editingChannel && (
            <div className="space-y-4 py-2">
              <div className="text-sm text-muted-foreground font-mono">{editingChannel.identifier}</div>
              <div className="space-y-2">
                <Label>Название</Label>
                <Input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="Название канала"
                  className="bg-secondary border-border"
                />
              </div>
              <div className="space-y-2">
                <Label>Описание</Label>
                <Textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Описание (опционально)"
                  className="bg-secondary border-border"
                />
              </div>
              <div className="space-y-2">
                <Label>Группы (канал может входить в несколько)</Label>
                <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-secondary/40 p-3">
                  {groups.map((g) => {
                    const active = editGroupIds.includes(g.id)
                    return (
                      <button
                        key={g.id}
                        type="button"
                        onClick={() => toggleEditGroup(g.id)}
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
                    <span className="text-xs text-muted-foreground">Нет групп</span>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-3 py-2">
                <Label htmlFor="edit-enabled" className="text-sm cursor-pointer">Мониторить</Label>
                <Switch id="edit-enabled" checked={editEnabled} onCheckedChange={setEditEnabled} />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-3 py-2">
                <Label htmlFor="edit-isGlobal" className="text-sm cursor-pointer">Доступен всем пользователям</Label>
                <Switch id="edit-isGlobal" checked={editIsGlobal} onCheckedChange={setEditIsGlobal} />
              </div>
              {editError && <p className="text-sm text-destructive">{editError}</p>}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingChannel(null)} disabled={savingEdit}>
              Отмена
            </Button>
            <Button onClick={saveEdit} disabled={savingEdit}>
              {savingEdit ? "Сохранение…" : "Сохранить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

