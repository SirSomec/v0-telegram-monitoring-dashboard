"use client"

import { useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, Loader2 } from "lucide-react"
import { apiJson } from "@/lib/api"

/** При том же origin — POST в /auth-api/forgot-password (Next.js проксирует на бэкенд; путь не под /api, чтобы Nginx не слал запрос на бэкенд). */
function forgotPasswordApiUrl(): string {
  if (typeof window === "undefined") return ""
  const env = (process.env.NEXT_PUBLIC_API_URL ?? "").trim()
  if (env === "." || env.toLowerCase() === "same_origin" || !env) return "/auth-api/forgot-password"
  return `${env}/auth/forgot-password`
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState("")
  const [resetLink, setResetLink] = useState("")
  const [successMessage, setSuccessMessage] = useState(
    "Если аккаунт с таким email существует, мы отправили на него ссылку для сброса пароля. Проверьте почту (и папку «Спам»).",
  )

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    if (!email.trim()) {
      setError("Введите email.")
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Введите корректный email.")
      return
    }
    setSubmitting(true)
    try {
      const result = await apiJson<{ ok: boolean; message?: string; resetLink?: string }>(forgotPasswordApiUrl(), {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      })
      setResetLink(result.resetLink ?? "")
      setSuccessMessage(
        result.message ??
          "Если аккаунт с таким email существует, мы отправили на него ссылку для сброса пароля. Проверьте почту (и папку «Спам»).",
      )
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка запроса")
    } finally {
      setSubmitting(false)
    }
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
            <CardTitle className="text-xl text-card-foreground">Восстановление пароля</CardTitle>
            <CardDescription className="text-muted-foreground">
              {sent ? successMessage : "Введите email вашего аккаунта — мы отправим ссылку для сброса пароля."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {sent ? (
              <div className="space-y-3">
                {resetLink && (
                  <a
                    href={resetLink}
                    className="block rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground hover:bg-secondary/80"
                  >
                    Перейти по ссылке сброса пароля
                  </a>
                )}
                <Button asChild className="w-full">
                  <Link href="/auth">Вернуться к входу</Link>
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-card-foreground">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="bg-secondary border-border text-foreground placeholder:text-muted-foreground"
                  />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" disabled={submitting} className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
                  {submitting ? <Loader2 className="size-4 animate-spin" /> : "Отправить ссылку"}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
