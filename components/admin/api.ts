import { apiBaseUrl, apiJson as libApiJson } from "@/lib/api"

/** Вызов API бэкенда с учётом base URL и токена авторизации. */
export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : `${apiBaseUrl()}${path}`
  return libApiJson<T>(url, init)
}
