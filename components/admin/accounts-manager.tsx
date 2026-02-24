"use client"

import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Trash2, Plus, RefreshCw, KeyRound, CreditCard, ChartColumn, MessageSquare } from "lucide-react"
import { apiJson } from "@/components/admin/api"
import type { UserAccount } from "@/components/admin/types"

const PLAN_LABELS: Record<string, string> = {
  free: "Без оплаты",
  basic: "Базовый",
  pro: "Про",
  business: "Бизнес",
}

const MENTIONS_PAGE_SIZE = 20

type ExclusionWord = {
  id: number
  text: string
  createdAt: string
}

type AdminKeyword = {
  id: number
  text: string
  useSemantic: boolean
  enabled: boolean
  exclusionWords: ExclusionWord[]
}

type AdminChannel = {
  id: number
  identifier: string
  title: string | null
  description: string | null
  source: string
  enabled: boolean
  isOwner: boolean
  viaGroupId: number | null
  viaGroupName: string | null
  createdAt: string
}

type PlanLimits = {
  maxGroups: number
  maxChannels: number
  maxKeywordsExact: number
  maxKeywordsSemantic: number
  maxOwnChannels: number
  label: string
}

type PlanUsage = {
  groups: number
  channels: number
  keywordsExact: number
  keywordsSemantic: number
  ownChannels: number
}

type AdminUserOverview = {
  user: UserAccount
  limits: PlanLimits
  usage: PlanUsage
  ownChannels: AdminChannel[]
  subscribedChannels: AdminChannel[]
  keywords: AdminKeyword[]
  mentionsCount: number
}

type AdminMention = {
  id: string
  groupName: string
  userName: string
  message: string
  keyword: string
  timestamp: string
  isLead: boolean
  isRead: boolean
  createdAt: string
  source: string
}

function usePercent(used: number, max: number): number {
  if (max <= 0) return 0
  return Math.min(100, Math.round((used / max) * 100))
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

  const [detailsDialogUser, setDetailsDialogUser] = useState<UserAccount | null>(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [detailsError, setDetailsError] = useState("")
  const [detailsData, setDetailsData] = useState<AdminUserOverview | null>(null)

  const [mentionsDialogUser, setMentionsDialogUser] = useState<UserAccount | null>(null)
  const [mentionsLoading, setMentionsLoading] = useState(false)
  const [mentionsError, setMentionsError] = useState("")
  const [mentions, setMentions] = useState<AdminMention[]>([])
  const [mentionsTotal, setMentionsTotal] = useState(0)
  const [mentionsPage, setMentionsPage] = useState(1)
  const [mentionsSearch, setMentionsSearch] = useState("")
  const [mentionsKeyword, setMentionsKeyword] = useState("")
  const [mentionsSortOrder, setMentionsSortOrder] = useState<"desc" | "asc">("desc")

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

  const mentionsPages = Math.max(1, Math.ceil(mentionsTotal / MENTIONS_PAGE_SIZE))

  async function openDetailsDialog(user: UserAccount) {
    setDetailsDialogUser(user)
    setDetailsLoading(true)
    setDetailsError("")
    try {
      const data = await apiJson<AdminUserOverview>(`/api/admin/users/${user.id}/overview`)
      setDetailsData(data)
    } catch (e) {
      setDetailsData(null)
      setDetailsError(e instanceof Error ? e.message : "Ошибка загрузки деталей пользователя")
    } finally {
      setDetailsLoading(false)
    }
  }

  function closeDetailsDialog() {
    setDetailsDialogUser(null)
    setDetailsData(null)
    setDetailsError("")
    setDetailsLoading(false)
  }

  function openMentionsDialog(user: UserAccount) {
    setDetailsDialogUser(null)
    setMentionsDialogUser(user)
    setMentionsError("")
    setMentions([])
    setMentionsTotal(0)
    setMentionsPage(1)
    setMentionsSearch("")
    setMentionsKeyword("")
    setMentionsSortOrder("desc")
  }

  function closeMentionsDialog() {
    setMentionsDialogUser(null)
    setMentionsError("")
    setMentions([])
    setMentionsTotal(0)
    setMentionsPage(1)
    setMentionsSearch("")
    setMentionsKeyword("")
    setMentionsSortOrder("desc")
  }

  useEffect(() => {
    if (!mentionsDialogUser) return
    const params = new URLSearchParams({
      limit: String(MENTIONS_PAGE_SIZE),
      offset: String((mentionsPage - 1) * MENTIONS_PAGE_SIZE),
      sortOrder: mentionsSortOrder,
    })
    if (mentionsSearch.trim()) params.set("search", mentionsSearch.trim())
    if (mentionsKeyword.trim()) params.set("keyword", mentionsKeyword.trim())
    setMentionsLoading(true)
    setMentionsError("")
    Promise.all([
      apiJson<AdminMention[]>(`/api/admin/users/${mentionsDialogUser.id}/mentions?${params.toString()}`),
      apiJson<{ total: number }>(
        `/api/admin/users/${mentionsDialogUser.id}/mentions/count?${params.toString()}`
      ),
    ])
      .then(([rows, count]) => {
        setMentions(Array.isArray(rows) ? rows : [])
        setMentionsTotal(count?.total ?? 0)
      })
      .catch((e) => {
        setMentions([])
        setMentionsTotal(0)
        setMentionsError(e instanceof Error ? e.message : "Ошибка загрузки сообщений")
      })
      .finally(() => {
        setMentionsLoading(false)
      })
  }, [mentionsDialogUser, mentionsPage, mentionsSortOrder, mentionsSearch, mentionsKeyword])

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
                      {PLAN_LABELS[(u.planSlug ?? u.plan ?? "free") as keyof typeof PLAN_LABELS] ?? (u.planSlug ?? u.plan ?? "free")}
                      {(u.plan ?? "free") !== (u.planSlug ?? u.plan ?? "free") && (u.plan ?? "free") === "free" && (
                        <span className="ml-1 text-muted-foreground text-xs">(истёк)</span>
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {u.planExpiresAt ? (() => {
                      const d = new Date(u.planExpiresAt)
                      return isNaN(d.getTime()) ? "—" : d.toLocaleDateString("ru-RU")
                    })() : "—"}
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
                      onClick={() => openDetailsDialog(u)}
                      disabled={loading}
                      className="text-muted-foreground hover:text-foreground"
                      title="Показатели пользователя"
                    >
                      <ChartColumn className="size-4" />
                    </Button>
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

      <Dialog open={!!detailsDialogUser} onOpenChange={(open) => !open && closeDetailsDialog()}>
        <DialogContent className="sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>Аналитика пользователя</DialogTitle>
            <DialogDescription>
              {detailsDialogUser && (
                <>Лимиты, каналы, ключевые слова и активность для {detailsDialogUser.email || detailsDialogUser.name || `#${detailsDialogUser.id}`}.</>
              )}
            </DialogDescription>
          </DialogHeader>
          {detailsLoading && <p className="text-sm text-muted-foreground py-4">Загрузка данных пользователя…</p>}
          {!detailsLoading && detailsError && <p className="text-sm text-destructive">{detailsError}</p>}
          {!detailsLoading && detailsData && (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-lg border border-border bg-secondary/30 p-3 space-y-2">
                  <p className="text-xs text-muted-foreground">Тариф</p>
                  <div className="flex items-center justify-between gap-2">
                    <Badge>{PLAN_LABELS[detailsData.user.plan] ?? detailsData.limits.label}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {detailsData.user.planExpiresAt
                        ? new Date(detailsData.user.planExpiresAt).toLocaleDateString("ru-RU")
                        : "без срока"}
                    </span>
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-secondary/30 p-3 space-y-2">
                  <p className="text-xs text-muted-foreground">Подписок на каналы</p>
                  <p className="text-lg font-semibold text-foreground">{detailsData.subscribedChannels.length}</p>
                </div>
                <div className="rounded-lg border border-border bg-secondary/30 p-3 space-y-2">
                  <p className="text-xs text-muted-foreground">Спарсенные сообщения</p>
                  <p className="text-lg font-semibold text-foreground">{detailsData.mentionsCount}</p>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-secondary/20 p-3 space-y-2">
                <p className="text-sm font-medium text-foreground">Биллинг и лимиты использования</p>
                <UsageMetric label="Группы" used={detailsData.usage.groups} limit={detailsData.limits.maxGroups} />
                <UsageMetric label="Каналы" used={detailsData.usage.channels} limit={detailsData.limits.maxChannels} />
                <UsageMetric label="Ключевые слова (точные)" used={detailsData.usage.keywordsExact} limit={detailsData.limits.maxKeywordsExact} />
                <UsageMetric label="Ключевые слова (семантика)" used={detailsData.usage.keywordsSemantic} limit={detailsData.limits.maxKeywordsSemantic} />
                <UsageMetric label="Своих каналов" used={detailsData.usage.ownChannels} limit={detailsData.limits.maxOwnChannels} />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-lg border border-border bg-secondary/20 p-3 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">Каналы пользователя</p>
                    <Badge variant="secondary">{detailsData.ownChannels.length} своих</Badge>
                  </div>
                  <ScrollArea className="h-64 pr-3">
                    <div className="space-y-2">
                      {detailsData.ownChannels.map((ch) => (
                        <div key={`own-${ch.id}`} className="rounded border border-border bg-background/60 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm font-medium">{ch.title || ch.identifier}</p>
                            <Badge variant={ch.enabled ? "default" : "outline"}>{ch.enabled ? "вкл" : "выкл"}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground font-mono">{ch.identifier}</p>
                        </div>
                      ))}
                      {detailsData.ownChannels.length === 0 && (
                        <p className="text-xs text-muted-foreground">Собственных каналов нет.</p>
                      )}
                    </div>
                  </ScrollArea>
                </div>

                <div className="rounded-lg border border-border bg-secondary/20 p-3 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">На какие каналы подписан</p>
                    <Badge variant="secondary">{detailsData.subscribedChannels.length} подписок</Badge>
                  </div>
                  <ScrollArea className="h-64 pr-3">
                    <div className="space-y-2">
                      {detailsData.subscribedChannels.map((ch) => (
                        <div key={`sub-${ch.id}-${ch.viaGroupId ?? "direct"}`} className="rounded border border-border bg-background/60 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm font-medium">{ch.title || ch.identifier}</p>
                            <Badge variant={ch.enabled ? "default" : "outline"}>{ch.enabled ? "вкл" : "выкл"}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground font-mono">{ch.identifier}</p>
                          <p className="text-xs text-muted-foreground">
                            {ch.viaGroupName ? `Через группу: ${ch.viaGroupName}` : "Индивидуальная подписка"}
                          </p>
                        </div>
                      ))}
                      {detailsData.subscribedChannels.length === 0 && (
                        <p className="text-xs text-muted-foreground">Подписок на каналы нет.</p>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-secondary/20 p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-foreground">Ключевые слова и исключения</p>
                  <Badge variant="secondary">{detailsData.keywords.length}</Badge>
                </div>
                <ScrollArea className="h-64 pr-3">
                  <div className="space-y-2">
                    {detailsData.keywords.map((kw) => (
                      <div key={kw.id} className="rounded border border-border bg-background/60 p-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant={kw.useSemantic ? "default" : "secondary"}>
                            {kw.useSemantic ? "Семантика" : "Точное"}
                          </Badge>
                          <span className="text-sm font-medium">{kw.text}</span>
                          {!kw.enabled && <Badge variant="outline">Отключено</Badge>}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {kw.exclusionWords.length > 0 ? (
                            kw.exclusionWords.map((w) => (
                              <Badge key={w.id} variant="outline" className="text-xs">
                                {w.text}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-xs text-muted-foreground">Исключения не заданы</span>
                          )}
                        </div>
                      </div>
                    ))}
                    {detailsData.keywords.length === 0 && (
                      <p className="text-xs text-muted-foreground">Ключевых слов нет.</p>
                    )}
                  </div>
                </ScrollArea>
              </div>

              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => detailsDialogUser && openMentionsDialog(detailsDialogUser)}
                  disabled={!detailsDialogUser}
                >
                  <MessageSquare className="mr-2 size-4" />
                  Просмотреть спарсенные сообщения
                </Button>
                <Button onClick={closeDetailsDialog}>Закрыть</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!mentionsDialogUser} onOpenChange={(open) => !open && closeMentionsDialog()}>
        <DialogContent className="sm:max-w-6xl">
          <DialogHeader>
            <DialogTitle>Спарсенные сообщения пользователя</DialogTitle>
            <DialogDescription>
              {mentionsDialogUser && (
                <>Полный просмотр сообщений для {mentionsDialogUser.email || mentionsDialogUser.name || `#${mentionsDialogUser.id}`}</>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Input
                value={mentionsSearch}
                onChange={(e) => {
                  setMentionsSearch(e.target.value)
                  setMentionsPage(1)
                }}
                placeholder="Поиск по тексту сообщения..."
                className="w-full max-w-sm bg-secondary border-border"
              />
              <select
                value={mentionsKeyword}
                onChange={(e) => {
                  setMentionsKeyword(e.target.value)
                  setMentionsPage(1)
                }}
                className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                <option value="">Все ключевые слова</option>
                {(detailsData?.keywords ?? []).map((k) => (
                  <option key={k.id} value={k.text}>{k.text}</option>
                ))}
              </select>
              <select
                value={mentionsSortOrder}
                onChange={(e) => {
                  setMentionsSortOrder(e.target.value as "desc" | "asc")
                  setMentionsPage(1)
                }}
                className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                <option value="desc">Сначала новые</option>
                <option value="asc">Сначала старые</option>
              </select>
              <Badge variant="outline" className="font-mono">{mentionsTotal}</Badge>
            </div>

            {mentionsError && <p className="text-sm text-destructive">{mentionsError}</p>}
            {mentionsLoading ? (
              <p className="text-sm text-muted-foreground py-4">Загрузка сообщений…</p>
            ) : (
              <ScrollArea className="h-[55vh] rounded-md border border-border p-3">
                <div className="space-y-2">
                  {mentions.map((m) => (
                    <div key={m.id} className="rounded border border-border bg-secondary/30 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{m.groupName}</span>
                        <span className="text-xs text-muted-foreground">/ {m.userName}</span>
                        <Badge variant="secondary">{m.keyword}</Badge>
                        <Badge variant={m.isLead ? "default" : "outline"}>{m.isLead ? "Лид" : "Обычное"}</Badge>
                        <Badge variant={m.isRead ? "outline" : "default"}>{m.isRead ? "Прочитано" : "Новое"}</Badge>
                        <span className="ml-auto text-xs text-muted-foreground">{m.timestamp}</span>
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-sm">{m.message}</p>
                    </div>
                  ))}
                  {mentions.length === 0 && (
                    <p className="text-sm text-muted-foreground py-8 text-center">
                      По выбранным фильтрам сообщений не найдено.
                    </p>
                  )}
                </div>
              </ScrollArea>
            )}

            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                disabled={mentionsPage <= 1 || mentionsLoading}
                onClick={() => setMentionsPage((p) => Math.max(1, p - 1))}
              >
                Назад
              </Button>
              <span className="text-sm text-muted-foreground">
                Страница {mentionsPage} из {mentionsPages}
              </span>
              <Button
                variant="outline"
                disabled={mentionsPage >= mentionsPages || mentionsLoading}
                onClick={() => setMentionsPage((p) => Math.min(mentionsPages, p + 1))}
              >
                Вперёд
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

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

function UsageMetric({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = usePercent(used, limit)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">
          {used} / {limit <= 0 ? "—" : limit}
        </span>
      </div>
      <Progress value={pct} className="h-1.5" />
    </div>
  )
}

