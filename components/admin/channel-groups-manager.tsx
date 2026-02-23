"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Trash2, Plus, RefreshCw } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { ChatGroup } from "@/components/admin/types"

export function ChannelGroupsManager({ userId = 1 }: { userId?: number }) {
  const [groups, setGroups] = useState<ChatGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  const [name, setName] = useState("")
  const [description, setDescription] = useState("")

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

  return (
    <div className="grid min-w-0 gap-4 sm:gap-6 lg:grid-cols-5">
      <Card className="min-w-0 lg:col-span-2 border-border bg-card">
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

      <Card className="min-w-0 lg:col-span-3 border-border bg-card">
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base font-semibold text-card-foreground">Группы каналов</CardTitle>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading} className="shrink-0">
            <RefreshCw className="mr-2 size-4" />
            Обновить
          </Button>
        </CardHeader>
        <CardContent className="min-w-0 overflow-auto">
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
    </div>
  )
}

