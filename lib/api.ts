/**
 * Базовый URL бэкенда (FastAPI).
 * В браузере: NEXT_PUBLIC_API_URL, иначе тот же хост и порт 8000 (деплой на одном сервере).
 * На сервере (SSR): для Route Handlers.
 */
function getApiUrl(): string {
  if (typeof window !== "undefined") {
    const env = (process.env.NEXT_PUBLIC_API_URL ?? "").trim()
    if (env === "." || env.toLowerCase() === "same_origin") return ""
    if (env) return env
    const { hostname, protocol } = window.location
    return `${protocol}//${hostname}:8000`
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
