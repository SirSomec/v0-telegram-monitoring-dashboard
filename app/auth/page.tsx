"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Eye, EyeOff, ArrowLeft } from "lucide-react"

export default function AuthPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const defaultTab = searchParams.get("tab") === "register" ? "register" : "login"

  const [activeTab, setActiveTab] = useState(defaultTab)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  // Login form state
  const [loginEmail, setLoginEmail] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [loginError, setLoginError] = useState("")

  // Register form state
  const [regName, setRegName] = useState("")
  const [regEmail, setRegEmail] = useState("")
  const [regPassword, setRegPassword] = useState("")
  const [regConfirm, setRegConfirm] = useState("")
  const [regAgree, setRegAgree] = useState(false)
  const [regError, setRegError] = useState("")

  function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoginError("")

    if (!loginEmail.trim() || !loginPassword.trim()) {
      setLoginError("Пожалуйста, заполните все поля.")
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(loginEmail)) {
      setLoginError("Введите корректный email-адрес.")
      return
    }

    router.push("/dashboard")
  }

  function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    setRegError("")

    if (!regName.trim() || !regEmail.trim() || !regPassword.trim() || !regConfirm.trim()) {
      setRegError("Пожалуйста, заполните все поля.")
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(regEmail)) {
      setRegError("Введите корректный email-адрес.")
      return
    }
    if (regPassword.length < 8) {
      setRegError("Пароль должен содержать минимум 8 символов.")
      return
    }
    if (regPassword !== regConfirm) {
      setRegError("Пароли не совпадают.")
      return
    }
    if (!regAgree) {
      setRegError("Необходимо принять условия использования.")
      return
    }

    router.push("/dashboard")
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-10">
      {/* Background effect */}
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,oklch(0.62_0.18_250/0.08),transparent_60%)]" />

      <div className="relative w-full max-w-md">
        {/* Back to landing */}
        <Link
          href="/"
          className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          На главную
        </Link>

        {/* Logo */}
        <div className="mb-8 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-primary-foreground">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="text-xl font-bold tracking-tight text-foreground">TeleScope</span>
        </div>

        <Card className="border-border bg-card">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <CardHeader className="pb-0">
              <TabsList className="grid w-full grid-cols-2 bg-secondary">
                <TabsTrigger value="login">Вход</TabsTrigger>
                <TabsTrigger value="register">Регистрация</TabsTrigger>
              </TabsList>
            </CardHeader>

            <CardContent className="pt-6">
              {/* Login Tab */}
              <TabsContent value="login" className="mt-0">
                <CardTitle className="text-xl text-card-foreground">Добро пожаловать</CardTitle>
                <CardDescription className="mt-1 text-muted-foreground">
                  Войдите в свой аккаунт для доступа к дашборду
                </CardDescription>

                <form onSubmit={handleLogin} className="mt-6 space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="login-email" className="text-card-foreground">Email</Label>
                    <Input
                      id="login-email"
                      type="email"
                      placeholder="name@example.com"
                      value={loginEmail}
                      onChange={(e) => setLoginEmail(e.target.value)}
                      className="bg-secondary border-border text-foreground placeholder:text-muted-foreground"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="login-password" className="text-card-foreground">Пароль</Label>
                      <button
                        type="button"
                        className="text-xs text-primary hover:text-primary/80 transition-colors"
                      >
                        Забыли пароль?
                      </button>
                    </div>
                    <div className="relative">
                      <Input
                        id="login-password"
                        type={showPassword ? "text" : "password"}
                        placeholder="Введите пароль"
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        className="bg-secondary border-border text-foreground placeholder:text-muted-foreground pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                      >
                        {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                      </button>
                    </div>
                  </div>

                  {loginError && (
                    <p className="text-sm text-destructive">{loginError}</p>
                  )}

                  <Button type="submit" className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
                    Войти
                  </Button>
                </form>
              </TabsContent>

              {/* Register Tab */}
              <TabsContent value="register" className="mt-0">
                <CardTitle className="text-xl text-card-foreground">Создать аккаунт</CardTitle>
                <CardDescription className="mt-1 text-muted-foreground">
                  Зарегистрируйтесь для 7 дней бесплатного доступа
                </CardDescription>

                <form onSubmit={handleRegister} className="mt-6 space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="reg-name" className="text-card-foreground">Имя</Label>
                    <Input
                      id="reg-name"
                      type="text"
                      placeholder="Ваше имя"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      className="bg-secondary border-border text-foreground placeholder:text-muted-foreground"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reg-email" className="text-card-foreground">Email</Label>
                    <Input
                      id="reg-email"
                      type="email"
                      placeholder="name@example.com"
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                      className="bg-secondary border-border text-foreground placeholder:text-muted-foreground"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reg-password" className="text-card-foreground">Пароль</Label>
                    <div className="relative">
                      <Input
                        id="reg-password"
                        type={showPassword ? "text" : "password"}
                        placeholder="Минимум 8 символов"
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        className="bg-secondary border-border text-foreground placeholder:text-muted-foreground pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                      >
                        {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reg-confirm" className="text-card-foreground">Подтверждение пароля</Label>
                    <div className="relative">
                      <Input
                        id="reg-confirm"
                        type={showConfirmPassword ? "text" : "password"}
                        placeholder="Повторите пароль"
                        value={regConfirm}
                        onChange={(e) => setRegConfirm(e.target.value)}
                        className="bg-secondary border-border text-foreground placeholder:text-muted-foreground pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        aria-label={showConfirmPassword ? "Скрыть пароль" : "Показать пароль"}
                      >
                        {showConfirmPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                      </button>
                    </div>
                  </div>

                  <div className="flex items-start gap-2">
                    <input
                      id="reg-agree"
                      type="checkbox"
                      checked={regAgree}
                      onChange={(e) => setRegAgree(e.target.checked)}
                      className="mt-1 size-4 rounded border-border accent-primary"
                    />
                    <Label htmlFor="reg-agree" className="text-sm leading-relaxed text-muted-foreground cursor-pointer">
                      Я соглашаюсь с{" "}
                      <span className="text-primary hover:underline cursor-pointer">условиями использования</span>
                      {" "}и{" "}
                      <span className="text-primary hover:underline cursor-pointer">политикой конфиденциальности</span>
                    </Label>
                  </div>

                  {regError && (
                    <p className="text-sm text-destructive">{regError}</p>
                  )}

                  <Button type="submit" className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
                    Создать аккаунт
                  </Button>
                </form>
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          {"Продолжая, вы соглашаетесь с условиями использования TeleScope"}
        </p>
      </div>
    </div>
  )
}
