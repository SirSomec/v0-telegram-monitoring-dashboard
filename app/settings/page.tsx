"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, Settings, Loader2 } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { apiBaseUrl, apiJson } from "@/lib/api"

export default function SettingsPage() {
  const router = useRouter()
  const { user, loading } = useAuth()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (loading) return
    if (!user) {
      router.replace("/auth")
      return
    }
  }, [loading, user, router])

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
      </main>
    </div>
  )
}
