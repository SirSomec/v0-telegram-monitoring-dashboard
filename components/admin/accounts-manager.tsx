"use client"

import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Trash2, Plus, RefreshCw } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { UserAccount } from "@/components/admin/types"

export function AccountsManager() {
  const [users, setUsers] = useState<UserAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [isAdmin, setIsAdmin] = useState(false)

  async function refresh() {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<UserAccount[]>("/api/users")
      setUsers(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const canCreate = useMemo(() => {
    return (email.trim().length > 0 || name.trim().length > 0) && !loading
  }, [email, name, loading])

  async function createUser() {
    if (!canCreate) return
    setLoading(true)
    setError("")
    try {
      await apiJson<UserAccount>("/api/users", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim() || null,
          name: name.trim() || null,
          isAdmin,
        }),
      })
      setEmail("")
      setName("")
      setIsAdmin(false)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания")
    } finally {
      setLoading(false)
    }
  }

  async function toggleAdmin(user: UserAccount) {
    setLoading(true)
    setError("")
    try {
      await apiJson<UserAccount>(`/api/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ isAdmin: !user.isAdmin }),
      })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обновления")
    } finally {
      setLoading(false)
    }
  }

  async function deleteUser(id: number) {
    setLoading(true)
    setError("")
    try {
      await apiJson<{ ok: boolean }>(`/api/users/${id}`, { method: "DELETE" })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2 border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-card-foreground">Создать учётку</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email (опционально)"
            className="bg-secondary border-border"
          />
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Имя (опционально)"
            className="bg-secondary border-border"
          />

          <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-3 py-2">
            <Label htmlFor="is-admin" className="text-sm text-foreground cursor-pointer">
              Администратор
            </Label>
            <Switch id="is-admin" checked={isAdmin} onCheckedChange={setIsAdmin} />
          </div>

          <Button onClick={createUser} disabled={!canCreate} className="w-full">
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
          <CardTitle className="text-base font-semibold text-card-foreground">Учётные записи</CardTitle>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>
            <RefreshCw className="mr-2 size-4" />
            Обновить
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Имя</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Роль</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="font-mono text-xs">{u.id}</TableCell>
                  <TableCell className="whitespace-normal">{u.name || "—"}</TableCell>
                  <TableCell className="whitespace-normal">{u.email || "—"}</TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant={u.isAdmin ? "default" : "outline"}
                      onClick={() => toggleAdmin(u)}
                      disabled={loading || u.id === 1}
                      className="h-7 text-xs"
                    >
                      {u.isAdmin ? "Admin" : "User"}
                    </Button>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deleteUser(u.id)}
                      disabled={loading || u.id === 1}
                      className="text-destructive hover:text-destructive"
                      title={u.id === 1 ? "Нельзя удалить системного пользователя" : "Удалить"}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-8">
                    Пользователи не созданы
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

