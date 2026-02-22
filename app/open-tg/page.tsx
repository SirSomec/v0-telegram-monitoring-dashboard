"use client"

import { useSearchParams } from "next/navigation"
import { useRouter } from "next/navigation"
import { useEffect, useState, Suspense } from "react"
import Link from "next/link"

/** Страница-редирект: открывает tg:// ссылку (чат с пользователем и т.д.).
 * Используется для ссылок вида tg://user?id=... из ленты — так браузер надёжнее передаёт открытие в приложение Telegram.
 */
function OpenTgContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const [fallback, setFallback] = useState(false)
  const u = searchParams.get("u")

  useEffect(() => {
    if (!u) {
      router.replace("/dashboard")
      return
    }
    let decoded: string
    try {
      decoded = decodeURIComponent(u)
    } catch {
      router.replace("/dashboard")
      return
    }
    if (!decoded.startsWith("tg://")) {
      router.replace("/dashboard")
      return
    }
    // Сначала пробуем редирект — ОС откроет Telegram, если установлен
    window.location.href = decoded
    // Если через 1.5 с мы всё ещё на странице, показываем подсказку
    const t = setTimeout(() => setFallback(true), 1500)
    return () => clearTimeout(t)
  }, [u, router])

  if (!u) return null

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4 text-center">
      {!fallback ? (
        <p className="text-muted-foreground">Открываем Telegram…</p>
      ) : (
        <div className="flex max-w-sm flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Если чат не открылся, нажмите кнопку ниже — откроется в приложении Telegram, если оно установлено.
          </p>
          <Link
            href={decodeURIComponent(u)}
            className="rounded-md border bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Открыть чат в Telegram
          </Link>
          <Link href="/dashboard" className="text-sm text-muted-foreground underline hover:text-foreground">
            Вернуться в дашборд
          </Link>
        </div>
      )}
    </div>
  )
}

export default function OpenTgPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Загрузка…</div>}>
      <OpenTgContent />
    </Suspense>
  )
}
