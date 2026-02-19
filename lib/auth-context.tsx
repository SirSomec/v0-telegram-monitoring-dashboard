"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import { apiBaseUrl, apiJson } from "@/lib/api"

const TOKEN_KEY = "telescope_token"

export type UserMe = {
  id: number
  email: string | null
  name: string | null
  isAdmin: boolean
  createdAt: string
}

type AuthContextValue = {
  token: string | null
  user: UserMe | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name?: string) => Promise<void>
  logout: () => void
  setUser: (u: UserMe | null) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<UserMe | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const loadUser = useCallback(async (t: string) => {
    try {
      const u = await apiJson<UserMe>(`${apiBaseUrl()}/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      })
      setUser(u)
    } catch {
      logout()
    }
  }, [logout])

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null
    if (!stored) {
      setLoading(false)
      return
    }
    setToken(stored)
    loadUser(stored).finally(() => setLoading(false))
  }, [loadUser])

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiJson<{ token: string; user: UserMe }>(`${apiBaseUrl()}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
    if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, res.token)
    setToken(res.token)
    setUser(res.user)
  }, [])

  const register = useCallback(async (email: string, password: string, name?: string) => {
    const res = await apiJson<{ token: string; user: UserMe }>(`${apiBaseUrl()}/auth/register`, {
      method: "POST",
      body: JSON.stringify({ email, password, name: name || null }),
    })
    if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, res.token)
    setToken(res.token)
    setUser(res.user)
  }, [])

  const value: AuthContextValue = {
    token,
    user,
    loading,
    login,
    register,
    logout,
    setUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(TOKEN_KEY)
}
