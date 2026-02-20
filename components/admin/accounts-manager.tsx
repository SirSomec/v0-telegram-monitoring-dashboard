"use client"

import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Trash2, Plus, RefreshCw, KeyRound, CreditCard } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { UserAccount } from "@/components/admin/types"

const PLAN_LABELS: Record<string, string> = {
  free: "Без оплаты",
  basic: "Базовый",
  pro: "Про",
  business: "Бизнес",
}

export function AccountsManager() {
  const [users, setUsers] = useState<UserAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [password, setPassword] = useState("")
  const [isAdmin, setIsAdmin] = useState(false)

  const [passwordDialogUser, setPasswordDialogUser] = useState<UserAccount | null>(null)
  const [newPassword, setNewPassword] = useState("")
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("")
  const [passwordDialogError, setPasswordDialogError] = useState("")
  const [passwordDialogSubmitting, setPasswordDialogSubmitting] = useState(false)

  const [planDialogUser, setPlanDialogUser] = useState<UserAccount | null>(null)
  const [planSlug, setPlanSlug] = useState<string>("free")
  const [planExpiresAt, setPlanExpiresAt] = useState<string>("")
  const [planDialogSubmitting, setPlanDialogSubmitting] = useState(false)

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
    const hasAny = email.trim().length > 0 || name.trim().length > 0 || password.trim().length > 0
    const validPassword = !password.trim() || password.trim().length >= 8
    return hasAny && validPassword && !loading
  }, [email, name, password, loading])

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
          password: password.trim() || null,
          isAdmin,
        }),
      })
      setEmail("")
      setName("")
      setPassword("")
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

  function openPasswordDialog(user: UserAccount) {
    setPasswordDialogUser(user)
    setNewPassword("")
    setNewPasswordConfirm("")
    setPasswordDialogError("")
  }

  function openPlanDialog(user: UserAccount) {
    setPlanDialogUser(user)
    setPlanSlug(user.planSlug ?? user.plan ?? "free")
    setPlanExpiresAt(user.planExpiresAt ? user.planExpiresAt.slice(0, 16) : "")
  }

  function closePlanDialog() {
    setPlanDialogUser(null)
    setPlanSlug("free")
    setPlanExpiresAt("")
  }

  async function submitPlan() {
    if (!planDialogUser) return
    setPlanDialogSubmitting(true)
    try {
      await apiJson<UserAccount>(`/api/users/${planDialogUser.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          plan: planSlug,
          planExpiresAt: planExpiresAt.trim() ? planExpiresAt.trim() : "",
        }),
      })
      closePlanDialog()
      await refresh()
    } catch (e) {
      // keep dialog open
    } finally {
      setPlanDialogSubmitting(false)
    }
  }

  function closePasswordDialog() {
    setPasswordDialogUser(null)
    setNewPassword("")
    setNewPasswordConfirm("")
    setPasswordDialogError("")
  }

  async function submitSetPassword() {
    if (!passwordDialogUser) return
    setPasswordDialogError("")
    if (newPassword.length < 8) {
      setPasswordDialogError("Пароль должен быть не менее 8 символов")
      return
    }
    if (newPassword !== newPasswordConfirm) {
      setPasswordDialogError("Пароли не совпадают")
      return
    }
    setPasswordDialogSubmitting(true)
    try {
      await apiJson<{ ok: boolean }>(`/api/users/${passwordDialogUser.id}/password`, {
        method: "PATCH",
        body: JSON.stringify({ newPassword }),
      })
      closePasswordDialog()
    } catch (e) {
      setPasswordDialogError(e instanceof Error ? e.message : "Ошибка смены пароля")
    } finally {
      setPasswordDialogSubmitting(false)
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
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Пароль (мин. 8 символов, опционально)"
            className="bg-secondary border-border"
            autoComplete="new-password"
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
                <TableHead>Тариф</TableHead>
                <TableHead>Действует до</TableHead>
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
                    <span className="text-sm">
                      {PLAN_LABELS[u.planSlug as keyof typeof PLAN_LABELS] ?? u.planSlug}
                      {u.plan !== u.planSlug && u.plan === "free" && (
                        <span className="ml-1 text-muted-foreground text-xs">(истёк)</span>
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {u.planExpiresAt ? new Date(u.planExpiresAt).toLocaleDateString("ru-RU") : "—"}
                  </TableCell>
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
                      onClick={() => openPlanDialog(u)}
                      disabled={loading}
                      className="text-muted-foreground hover:text-foreground"
                      title="Назначить тариф"
                    >
                      <CreditCard className="size-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => openPasswordDialog(u)}
                      disabled={loading}
                      className="text-muted-foreground hover:text-foreground"
                      title="Сменить пароль"
                    >
                      <KeyRound className="size-4" />
                    </Button>
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
                  <TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-8">
                    Пользователи не созданы
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={!!planDialogUser} onOpenChange={(open) => !open && closePlanDialog()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Назначить тариф</DialogTitle>
            <DialogDescription>
              {planDialogUser && (
                <>Тариф и срок действия для {planDialogUser.email || planDialogUser.name || `#${planDialogUser.id}`}. По истечении срока учётная запись перейдёт на «Без оплаты».</>
              )}
            </DialogDescription>
          </DialogHeader>
          {planDialogUser && (
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label>Тариф</Label>
                <select
                  value={planSlug}
                  onChange={(e) => setPlanSlug(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                >
                  {(["free", "basic", "pro", "business"] as const).map((p) => (
                    <option key={p} value={p}>{PLAN_LABELS[p]}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="plan-expires">Действует до (необязательно)</Label>
                <Input
                  id="plan-expires"
                  type="datetime-local"
                  value={planExpiresAt}
                  onChange={(e) => setPlanExpiresAt(e.target.value)}
                  className="bg-secondary border-border"
                />
                <p className="text-xs text-muted-foreground">Оставьте пустым, чтобы тариф действовал без срока.</p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={closePlanDialog} disabled={planDialogSubmitting}>Отмена</Button>
            <Button onClick={submitPlan} disabled={planDialogSubmitting}>{planDialogSubmitting ? "Сохранение…" : "Сохранить"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!passwordDialogUser} onOpenChange={(open) => !open && closePasswordDialog()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Сменить пароль</DialogTitle>
            <DialogDescription>
              {passwordDialogUser && (
                <>Новый пароль для пользователя {passwordDialogUser.email || passwordDialogUser.name || `#${passwordDialogUser.id}`} (мин. 8 символов).</>
              )}
            </DialogDescription>
          </DialogHeader>
          {passwordDialogUser && (
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="admin-new-password">Новый пароль</Label>
                <Input
                  id="admin-new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Минимум 8 символов"
                  className="bg-secondary border-border"
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin-new-password-confirm">Подтверждение</Label>
                <Input
                  id="admin-new-password-confirm"
                  type="password"
                  value={newPasswordConfirm}
                  onChange={(e) => setNewPasswordConfirm(e.target.value)}
                  placeholder="Повторите пароль"
                  className="bg-secondary border-border"
                  autoComplete="new-password"
                />
              </div>
              {passwordDialogError && <p className="text-sm text-destructive">{passwordDialogError}</p>}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={closePasswordDialog} disabled={passwordDialogSubmitting}>
              Отмена
            </Button>
            <Button onClick={submitSetPassword} disabled={passwordDialogSubmitting || !newPassword.trim() || newPassword.length < 8}>
              {passwordDialogSubmitting ? "Сохранение…" : "Сохранить пароль"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

