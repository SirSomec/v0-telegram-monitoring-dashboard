"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, Settings, Loader2, LogOut, Search } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { apiBaseUrl, apiJson } from "@/lib/api"

type SemanticSettings = {
  semanticThreshold: number | null
  semanticMinTopicPercent: number | null
}

export default function SettingsPage() {
  const router = useRouter()
  const { user, loading, logout } = useAuth()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)
  const [semantic, setSemantic] = useState<SemanticSettings>({ semanticThreshold: null, semanticMinTopicPercent: null })
  const [semanticDirty, setSemanticDirty] = useState(false)
  const [semanticSaving, setSemanticSaving] = useState(false)

  useEffect(() => {
    if (loading) return
    if (!user) {
      router.replace("/auth")
      return
    }
  }, [loading, user, router])

  useEffect(() => {
    if (!user) return
    apiJson<SemanticSettings>(`${apiBaseUrl()}/api/settings/semantic`)
      .then((data) => setSemantic({
        semanticThreshold: data.semanticThreshold ?? null,
        semanticMinTopicPercent: data.semanticMinTopicPercent ?? null,
      }))
      .catch(() => {})
  }, [user])

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setSuccess(false)
    if (newPassword.length < 8) {
      setError("Новый пароль не менее 8 символов")
      return
    }
    if (newPassword !== confirmPassword) {
      setError("Пароли не совпадают")
      return
    }
    setSubmitting(true)
    try {
      await apiJson<{ id: number }>(`${apiBaseUrl()}/auth/me`, {
        method: "PATCH",
        body: JSON.stringify({
          currentPassword,
          newPassword,
        }),
      })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      setSuccess(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка смены пароля")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || !user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Загрузка...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto w-full max-w-xl space-y-6 p-4 lg:p-6">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          На дашборд
        </Link>

        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Settings className="size-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Настройки</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Профиль и безопасность
            </p>
          </div>
        </div>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="text-base">Профиль</CardTitle>
            <CardDescription>Данные учётной записи</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              <Label className="text-muted-foreground text-xs">Email</Label>
              <p className="text-sm font-medium text-foreground">{user.email || "—"}</p>
            </div>
            <div>
              <Label className="text-muted-foreground text-xs">Имя</Label>
              <p className="text-sm font-medium text-foreground">{user.name || "—"}</p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Search className="size-4" />
              Семантический поиск
            </CardTitle>
            <CardDescription>
              Порог срабатывания и минимальный % совпадения с темой. Пусто — используются общие настройки системы.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="threshold" className="text-muted-foreground text-xs">
                Порог срабатывания, % (0–100). Выше — строже отбор совпадений.
              </Label>
              <Input
                id="threshold"
                type="number"
                min={0}
                max={100}
                step={1}
                placeholder="например 55"
                value={semantic.semanticThreshold != null ? Math.round(semantic.semanticThreshold * 100) : ""}
                onChange={(e) => {
                  const v = e.target.value
                  setSemantic((s) => ({
                    ...s,
                    semanticThreshold: v === "" ? null : Math.min(100, Math.max(0, Number(v))) / 100,
                  }))
                  setSemanticDirty(true)
                }}
                className="mt-1 bg-secondary border-border max-w-[8rem]"
              />
            </div>
            <div>
              <Label htmlFor="minTopic" className="text-muted-foreground text-xs">
                Мин. % совпадения с темой (0–100). Сообщения ниже этого процента не попадают в ленту.
              </Label>
              <Input
                id="minTopic"
                type="number"
                min={0}
                max={100}
                step={1}
                placeholder="например 50"
                value={semantic.semanticMinTopicPercent ?? ""}
                onChange={(e) => {
                  const v = e.target.value
                  setSemantic((s) => ({
                    ...s,
                    semanticMinTopicPercent: v === "" ? null : Math.min(100, Math.max(0, Number(v))),
                  }))
                  setSemanticDirty(true)
                }}
                className="mt-1 bg-secondary border-border max-w-[8rem]"
              />
            </div>
            {semanticDirty && (
              <Button
                type="button"
                disabled={semanticSaving}
                className="gap-2"
                onClick={async () => {
                  setSemanticSaving(true)
                  try {
                    const res = await apiJson<SemanticSettings>(`${apiBaseUrl()}/api/settings/semantic`, {
                      method: "PATCH",
                      body: JSON.stringify({
                        semanticThreshold: semantic.semanticThreshold,
                        semanticMinTopicPercent: semantic.semanticMinTopicPercent,
                      }),
                    })
                    setSemantic(res)
                    setSemanticDirty(false)
                  } finally {
                    setSemanticSaving(false)
                  }
                }}
              >
                {semanticSaving && <Loader2 className="size-4 animate-spin" />}
                Сохранить настройки поиска
              </Button>
            )}
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="text-base">Смена пароля</CardTitle>
            <CardDescription>Введите текущий пароль и новый (не менее 8 символов)</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <Label htmlFor="current">Текущий пароль</Label>
                <Input
                  id="current"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="mt-1 bg-secondary border-border"
                  required
                  autoComplete="current-password"
                />
              </div>
              <div>
                <Label htmlFor="new">Новый пароль</Label>
                <Input
                  id="new"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1 bg-secondary border-border"
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </div>
              <div>
                <Label htmlFor="confirm">Повторите новый пароль</Label>
                <Input
                  id="confirm"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1 bg-secondary border-border"
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              {success && <p className="text-sm text-green-600">Пароль успешно изменён</p>}
              <Button type="submit" disabled={submitting} className="gap-2">
                {submitting && <Loader2 className="size-4 animate-spin" />}
                Сохранить пароль
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="text-base">Выход из аккаунта</CardTitle>
            <CardDescription>Завершить сессию на этом устройстве</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              className="gap-2 text-muted-foreground hover:text-destructive hover:border-destructive"
              onClick={() => {
                logout()
                router.replace("/auth")
              }}
            >
              <LogOut className="size-4" />
              Выйти из профиля
            </Button>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
