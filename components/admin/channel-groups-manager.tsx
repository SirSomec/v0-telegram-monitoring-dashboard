"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Trash2, Plus, RefreshCw, List, Search } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { ChatGroup, TelegramDialog } from "@/components/admin/types"

export function ChannelGroupsManager({ userId = 1 }: { userId?: number }) {
  const [groups, setGroups] = useState<ChatGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  const [name, setName] = useState("")
  const [description, setDescription] = useState("")

  const [dialogs, setDialogs] = useState<TelegramDialog[] | null>(null)
  const [dialogsLoading, setDialogsLoading] = useState(false)
  const [addingIdentifier, setAddingIdentifier] = useState<string | null>(null)
  const [dialogSearch, setDialogSearch] = useState("")

  const refresh = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<ChatGroup[]>("/api/chat-groups")
      setGroups(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const canCreate = useMemo(() => name.trim().length > 0, [name])

  async function createGroup() {
    if (!canCreate) return
    setLoading(true)
    setError("")
    try {
      await apiJson<ChatGroup>("/api/chat-groups", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      })
      setName("")
      setDescription("")
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания")
    } finally {
      setLoading(false)
    }
  }

  async function deleteGroup(id: number) {
    setLoading(true)
    setError("")
    try {
      await apiJson<{ ok: boolean }>(`/api/chat-groups/${id}`, { method: "DELETE" })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления")
    } finally {
      setLoading(false)
    }
  }

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
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2 border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-card-foreground">Создать группу</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Название группы (например: Крипто / Web3)"
            className="bg-secondary border-border"
          />
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Описание (опционально)"
            className="bg-secondary border-border"
          />
          <Button onClick={createGroup} disabled={loading || !canCreate} className="w-full">
            <Plus className="mr-2 size-4" />
            Добавить группу
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
          <CardTitle className="text-base font-semibold text-card-foreground">Группы каналов</CardTitle>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>
            <RefreshCw className="mr-2 size-4" />
            Обновить
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Название</TableHead>
                <TableHead>Описание</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groups.map((g) => (
                <TableRow key={g.id}>
                  <TableCell className="font-medium">{g.name}</TableCell>
                  <TableCell className="whitespace-normal">{g.description || "—"}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deleteGroup(g.id)}
                      disabled={loading}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {groups.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-8">
                    Группы не созданы
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="lg:col-span-5 border-border bg-card">
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base font-semibold text-card-foreground">
                <List className="size-5" />
                Подписки аккаунта Telegram
              </CardTitle>
              <CardDescription className="mt-1">
                Группы и каналы, в которых состоит аккаунт парсера. Запустите парсер во вкладке «Парсер» и нажмите «Загрузить» — затем добавьте нужные чаты в мониторинг (они появятся в разделе «Каналы»).
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchDialogs}
              disabled={dialogsLoading}
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
              <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Поиск по названию, @username или идентификатору…"
                value={dialogSearch}
                onChange={(e) => setDialogSearch(e.target.value)}
                className="pl-8 bg-secondary border-border"
              />
            </div>
          )}
          {dialogs === null ? (
            <p className="text-muted-foreground text-sm">
              Нажмите «Загрузить список», чтобы получить группы и каналы аккаунта (парсер должен быть запущен во вкладке «Парсер»).
            </p>
          ) : dialogs.length === 0 ? (
            <p className="text-muted-foreground text-sm">Подписок не найдено или парсер не подключён.</p>
          ) : (
            <div className="rounded-md border overflow-auto max-h-[400px]">
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
                      <TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-6">
                        Ничего не найдено по запросу «{dialogSearch.trim()}»
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredDialogs.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="font-medium max-w-[200px] truncate" title={d.title}>
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
    </div>
  )
}

