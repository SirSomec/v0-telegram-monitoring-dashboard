/**
 * Базовый URL бэкенда (FastAPI).
 * В разработке: http://localhost:8000
 * В проде (Nginx проксирует /api на бэкенд): пустая строка = same origin.
 */
function getApiUrl(): string {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_URL ?? ""
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
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
