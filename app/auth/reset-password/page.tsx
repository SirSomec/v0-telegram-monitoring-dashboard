"use client"

import { Suspense, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, Eye, EyeOff, Loader2 } from "lucide-react"
import { apiJson } from "@/lib/api"

function authBase(): string {
  if (typeof window === "undefined") return ""
  const env = (process.env.NEXT_PUBLIC_API_URL ?? "").trim()
  if (env === "." || env.toLowerCase() === "same_origin") return ""
  if (env) return env
  return ""
}

function ResetPasswordContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token") ?? ""

  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    if (!token.trim()) {
      setError("Отсутствует ссылка для сброса. Запросите новую ссылку на странице «Забыли пароль?».")
      return
    }
    if (!password.trim() || !confirm.trim()) {
      setError("Заполните оба поля пароля.")
      return
    }
    if (password.length < 8) {
      setError("Пароль должен быть не менее 8 символов.")
      return
    }
    if (password !== confirm) {
      setError("Пароли не совпадают.")
      return
    }
    setSubmitting(true)
    try {
      await apiJson<{ ok: boolean }>(`${authBase()}/auth/reset-password`, {
        method: "POST",
        body: JSON.stringify({ token: token.trim(), newPassword: password }),
      })
      setSuccess(true)
      setTimeout(() => router.replace("/auth"), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сброса пароля")
    } finally {
      setSubmitting(false)
    }
  }

  if (!token.trim()) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-10">
        <div className="relative w-full max-w-md">
          <Link href="/auth" className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-4" />
            Назад к входу
          </Link>
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-xl text-card-foreground">Неверная ссылка</CardTitle>
              <CardDescription>
                Ссылка для сброса пароля отсутствует или некорректна. Перейдите на страницу «Забыли пароль?» и запросите новую ссылку.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild className="w-full">
                <Link href="/auth/forgot-password">Запросить ссылку</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-10">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,oklch(0.62_0.18_250/0.08),transparent_60%)]" />

      <div className="relative w-full max-w-md">
        <Link
          href="/auth"
          className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Назад к входу
        </Link>

        <div className="mb-8 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-primary-foreground">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="text-xl font-bold tracking-tight text-foreground">TeleScope</span>
        </div>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="text-xl text-card-foreground">Новый пароль</CardTitle>
            <CardDescription className="text-muted-foreground">
              {success
                ? "Пароль успешно изменён. Перенаправляем на страницу входа..."
                : "Введите новый пароль (не менее 8 символов)."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {success ? (
              <div className="flex justify-center py-2">
                <Loader2 className="size-6 animate-spin text-primary" />
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password" className="text-card-foreground">Новый пароль</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="Минимум 8 символов"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="bg-secondary border-border text-foreground placeholder:text-muted-foreground pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm" className="text-card-foreground">Подтверждение</Label>
                  <div className="relative">
                    <Input
                      id="confirm"
                      type={showConfirm ? "text" : "password"}
                      placeholder="Повторите пароль"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      className="bg-secondary border-border text-foreground placeholder:text-muted-foreground pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm(!showConfirm)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      aria-label={showConfirm ? "Скрыть пароль" : "Показать пароль"}
                    >
                      {showConfirm ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" disabled={submitting} className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
                  {submitting ? <Loader2 className="size-4 animate-spin" /> : "Сохранить пароль"}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Загрузка...</p>
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  )
}
