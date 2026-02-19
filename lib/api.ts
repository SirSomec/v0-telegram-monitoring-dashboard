/**
 * Базовый URL бэкенда (FastAPI).
 * В браузере: NEXT_PUBLIC_API_URL, иначе при открытии с порта 3000 — тот же хост:8000 (прямой запрос к бэкенду).
 * На сервере (SSR/proxy): для Route Handlers.
 */
function getApiUrl(): string {
  if (typeof window !== "undefined") {
    const env = process.env.NEXT_PUBLIC_API_URL ?? ""
    if (env) return env
    // Тот же хост, порт 8000 — типичный деплой (фронт :3000, бэкенд :8000)
    const { hostname, port, protocol } = window.location
    if (port === "3000" || port === "") return `${protocol}//${hostname}:8000`
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
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

/** URL для WebSocket упоминаний. Требуется токен (передаётся в query). */
export function wsMentionsUrl(token: string | null): string {
  const base = getApiUrl()
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
