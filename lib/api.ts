/**
 * Базовый URL бэкенда (FastAPI).
 * В браузере:
 * - NEXT_PUBLIC_API_URL задан — запросы на этот URL (прямо на бэкенд).
 * - Пусто или не задан — запросы на тот же origin (/auth/*, /api/*), Next.js проксирует на бэкенд (нет CORS, один порт).
 * - "." или "same_origin" — явно тот же origin (прокси).
 * На сервере (SSR): для Route Handlers.
 */
function getApiUrl(): string {
  if (typeof window !== "undefined") {
    const env = (process.env.NEXT_PUBLIC_API_URL ?? "").trim()
    if (env === "." || env.toLowerCase() === "same_origin") return ""
    if (env) return env
    // Не задан: используем тот же origin — запросы идут на /auth/* и /api/*, Next.js проксирует на бэкенд
    return ""
  }
  return process.env.NEXT_PUBLIC_API_URL ?? process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000"
}

export function apiBaseUrl(): string {
  return getApiUrl()
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {}
  const t = localStorage.getItem("telescope_token")
  return t ? { Authorization: `Bearer ${t}` } : {}
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : `${getApiUrl()}${path}`
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    let message = text || `HTTP ${res.status}`
    try {
      const json = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> }
      if (json.detail) {
        message = typeof json.detail === "string"
          ? json.detail
          : (json.detail as Array<{ msg?: string }>).map((d) => d.msg || "").filter(Boolean).join(". ") || message
      }
    } catch {
      /* use raw text */
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

/** URL для WebSocket упоминаний. Требуется токен (передаётся в query). */
export function wsMentionsUrl(token: string | null): string {
  let base = getApiUrl()
  // Когда API через тот же origin (base пустой) — WS тоже через тот же хост, Nginx проксирует /ws
  if (typeof window !== "undefined" && !base) {
    base = window.location.origin
  }
  const wsBase = base.replace(/^http/, "ws")
  if (!token) return `${wsBase}/ws/mentions`
  return `${wsBase}/ws/mentions?token=${encodeURIComponent(token)}`
}

export type ExportMentionsParams = {
  keyword?: string
  leadsOnly?: boolean
  dateFrom?: string
  dateTo?: string
}

/** Скачивает CSV экспорт упоминаний (с текущими заголовками авторизации). */
export async function downloadMentionsCsv(params: ExportMentionsParams = {}): Promise<void> {
  const search = new URLSearchParams()
  if (params.keyword?.trim()) search.set("keyword", params.keyword.trim())
  if (params.leadsOnly) search.set("leadsOnly", "true")
  if (params.dateFrom) search.set("dateFrom", params.dateFrom)
  if (params.dateTo) search.set("dateTo", params.dateTo)
  const url = `${getApiUrl()}/api/mentions/export${search.toString() ? `?${search}` : ""}`
  const res = await fetch(url, { headers: getAuthHeaders() })
  if (!res.ok) throw new Error(await res.text().catch(() => `HTTP ${res.status}`))
  const blob = await res.blob()
  const u = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = u
  a.download = "mentions.csv"
  a.click()
  URL.revokeObjectURL(u)
}
