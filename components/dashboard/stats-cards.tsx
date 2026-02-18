"use client"

import { Card, CardContent } from "@/components/ui/card"
import { MessageSquare, Hash, UserPlus, CalendarClock } from "lucide-react"

const stats = [
  {
    label: "Total Mentions Today",
    value: "1,284",
    change: "+12%",
    icon: MessageSquare,
    color: "text-primary",
    bgColor: "bg-primary/10",
  },
  {
    label: "Active Keywords",
    value: "23",
    change: "+3",
    icon: Hash,
    color: "text-success",
    bgColor: "bg-success/10",
  },
  {
    label: "New Leads Found",
    value: "47",
    change: "+8",
    icon: UserPlus,
    color: "text-warning",
    bgColor: "bg-warning/10",
  },
  {
    label: "Subscription Days Left",
    value: "18",
    change: "Pro Plan",
    icon: CalendarClock,
    color: "text-chart-4",
    bgColor: "bg-chart-4/10",
  },
]

export function StatsCards() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.label} className="border-border bg-card">
          <CardContent className="flex items-center gap-4 p-5">
            <div className={`flex size-11 shrink-0 items-center justify-center rounded-lg ${stat.bgColor}`}>
              <stat.icon className={`size-5 ${stat.color}`} />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-muted-foreground">{stat.label}</p>
              <div className="flex items-baseline gap-2">
                <p className="text-2xl font-bold tracking-tight text-card-foreground">{stat.value}</p>
                <span className="text-xs font-medium text-primary">{stat.change}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
