"use client"

import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Trash2, Plus, RefreshCw, Pencil, List, Search } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { Chat, ChatGroup, TelegramDialog } from "@/components/admin/types"

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

  const [dialogs, setDialogs] = useState<TelegramDialog[] | null>(null)
  const [dialogsLoading, setDialogsLoading] = useState(false)
  const [addingIdentifier, setAddingIdentifier] = useState<string | null>(null)
  const [dialogSearch, setDialogSearch] = useState("")

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

  async function fetchDialogs() {
    setDialogsLoading(true)
    setError("")
    try {
      const list = await apiJson<TelegramDialog[]>("/api/admin/parser/dialogs")
      setDialogs(Array.isArray(list) ? list : [])
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить список подписок")
      setDialogs([])
    } finally {
      setDialogsLoading(false)
    }
  }

  async function addDialogToMonitoring(d: TelegramDialog) {
    setAddingIdentifier(d.identifier)
    try {
      await apiJson("/api/chats", {
        method: "POST",
        body: JSON.stringify({
          identifier: d.identifier,
          title: d.title || undefined,
          isGlobal: true,
          enabled: true,
        }),
      })
      setAddingIdentifier(null)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка добавления канала")
      setAddingIdentifier(null)
    }
  }

  const filteredDialogs = useMemo(() => {
    if (!dialogs) return []
    const q = dialogSearch.trim().toLowerCase()
    if (!q) return dialogs
    return dialogs.filter(
      (d) =>
        (d.title || "").toLowerCase().includes(q) ||
        (d.username || "").toLowerCase().includes(q) ||
        (d.identifier || "").toLowerCase().includes(q)
    )
  }, [dialogs, dialogSearch])

  return (
    <div className="grid min-w-0 gap-4 sm:gap-6 lg:grid-cols-5">
      <Card className="min-w-0 lg:col-span-2 border-border bg-card">
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

      <Card className="min-w-0 lg:col-span-3 border-border bg-card">
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <CardTitle className="text-base font-semibold text-card-foreground">Каналы мониторинга</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">Канал может входить в несколько групп. Используйте «Изменить» для смены групп.</p>
          </div>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading} className="shrink-0">
            <RefreshCw className="mr-2 size-4" />
            Обновить
          </Button>
        </CardHeader>
        <CardContent className="min-w-0 overflow-auto">
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

      <Card className="min-w-0 lg:col-span-5 border-border bg-card">
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <CardTitle className="flex items-center gap-2 text-base font-semibold text-card-foreground">
                <List className="size-5 shrink-0" />
                Подписки аккаунта Telegram
              </CardTitle>
              <CardDescription className="mt-1">
                Группы и каналы, в которых состоит аккаунт парсера. Запустите парсер во вкладке «Парсер» и нажмите «Загрузить» — затем добавьте нужные чаты в мониторинг (они появятся в списке выше).
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchDialogs}
              disabled={dialogsLoading}
              className="shrink-0"
              aria-label="Загрузить список подписок"
            >
              <RefreshCw className={`mr-2 size-4 ${dialogsLoading ? "animate-spin" : ""}`} />
              Загрузить список
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {dialogs !== null && dialogs.length > 0 && (
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 shrink-0 text-muted-foreground" />
              <Input
                placeholder="Поиск по названию, @username или идентификатору…"
                value={dialogSearch}
                onChange={(e) => setDialogSearch(e.target.value)}
                className="pl-8 bg-secondary border-border"
              />
            </div>
          )}
          {dialogs === null ? (
            <p className="text-sm text-muted-foreground">
              Нажмите «Загрузить список», чтобы получить группы и каналы аккаунта (парсер должен быть запущен во вкладке «Парсер»).
            </p>
          ) : dialogs.length === 0 ? (
            <p className="text-sm text-muted-foreground">Подписок не найдено или парсер не подключён.</p>
          ) : (
            <div className="min-w-0 overflow-auto rounded-md border max-h-[400px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Название</TableHead>
                    <TableHead className="font-mono text-xs">Идентификатор</TableHead>
                    <TableHead className="w-[140px]">Действие</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDialogs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3} className="py-6 text-center text-sm text-muted-foreground">
                        Ничего не найдено по запросу «{dialogSearch.trim()}»
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredDialogs.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="max-w-[200px] truncate font-medium" title={d.title}>
                          {d.title || "—"}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {d.username ? `@${d.username}` : d.identifier}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => addDialogToMonitoring(d)}
                            disabled={addingIdentifier !== null}
                            aria-label={`Добавить ${d.title || d.identifier} в мониторинг`}
                          >
                            <Plus className="mr-1 size-4" />
                            {addingIdentifier === d.identifier ? "Добавление…" : "В мониторинг"}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
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

