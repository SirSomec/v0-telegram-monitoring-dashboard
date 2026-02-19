"use client"

import { useEffect, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { MessageSquare, Hash, UserPlus, CalendarClock, Loader2 } from "lucide-react"
import { apiBaseUrl, apiJson } from "@/lib/api"

type Stats = {
  mentionsToday: number
  keywordsCount: number
  leadsCount: number
}

export function StatsCards() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")

  useEffect(() => {
    let cancelled = false
    apiJson<Stats>(`${apiBaseUrl()}/api/stats`)
      .then((data) => {
        if (!cancelled) setStats(data)
      })
      .catch(() => {
        if (!cancelled) setError("Ошибка загрузки")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const cards = [
    {
      label: "Упоминаний сегодня",
      value: loading ? "—" : error ? "—" : String(stats?.mentionsToday ?? 0),
      change: "",
      icon: MessageSquare,
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    {
      label: "Активных ключевых слов",
      value: loading ? "—" : error ? "—" : String(stats?.keywordsCount ?? 0),
      change: "",
      icon: Hash,
      color: "text-success",
      bgColor: "bg-success/10",
    },
    {
      label: "Новых лидов найдено",
      value: loading ? "—" : error ? "—" : String(stats?.leadsCount ?? 0),
      change: "",
      icon: UserPlus,
      color: "text-warning",
      bgColor: "bg-warning/10",
    },
    {
      label: "Подписка",
      value: "—",
      change: "Не подключено",
      icon: CalendarClock,
      color: "text-chart-4",
      bgColor: "bg-chart-4/10",
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((stat) => (
        <Card key={stat.label} className="border-border bg-card">
          <CardContent className="flex items-center gap-4 p-5">
            {loading && stat.change === "" ? (
              <div className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-muted">
                <Loader2 className="size-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className={`flex size-11 shrink-0 items-center justify-center rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`size-5 ${stat.color}`} />
              </div>
            )}
            <div className="min-w-0">
              <p className="text-xs font-medium text-muted-foreground">{stat.label}</p>
              <div className="flex items-baseline gap-2">
                <p className="text-2xl font-bold tracking-tight text-card-foreground">{stat.value}</p>
                {stat.change ? (
                  <span className="text-xs font-medium text-muted-foreground">{stat.change}</span>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
