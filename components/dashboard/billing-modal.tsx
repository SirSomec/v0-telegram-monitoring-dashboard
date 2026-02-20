"use client"

import { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { apiJson } from "@/lib/api"
import { cn } from "@/lib/utils"

const PLAN_LABELS: Record<string, string> = {
  free: "Без оплаты",
  basic: "Базовый",
  pro: "Про",
  business: "Бизнес",
}

type PlanLimits = {
  maxGroups: number
  maxChannels: number
  maxKeywordsExact: number
  maxKeywordsSemantic: number
  maxOwnChannels: number
  label: string
}

type PlanUsage = {
  groups: number
  channels: number
  keywordsExact: number
  keywordsSemantic: number
  ownChannels: number
}

type PlanData = {
  plan: string
  planExpiresAt: string | null
  limits: PlanLimits
  usage: PlanUsage
}

function usePercent(used: number, max: number): number {
  if (max <= 0) return 0
  return Math.min(100, Math.round((used / max) * 100))
}

interface BillingModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function BillingModal({ open, onOpenChange }: BillingModalProps) {
  const [data, setData] = useState<PlanData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError("")
    apiJson<PlanData>("/api/plan")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [open])

  const isFree = data?.plan === "free"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">Тариф и лимиты</DialogTitle>
          <DialogDescription>
            Текущий тариф, использование и ограничения. Тариф и срок действия назначает администратор.
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <p className="text-sm text-muted-foreground py-4">Загрузка…</p>
        )}
        {error && (
          <p className="text-sm text-destructive py-2">{error}</p>
        )}
        {data && !loading && (
          <div className="space-y-4 mt-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-muted-foreground">Текущий тариф</span>
              <Badge variant={isFree ? "secondary" : "default"} className="text-sm">
                {PLAN_LABELS[data.plan] ?? data.limits.label}
              </Badge>
            </div>
            {data.planExpiresAt && (
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="text-muted-foreground">Действует до</span>
                <span className="text-foreground">
                  {new Date(data.planExpiresAt).toLocaleDateString("ru-RU", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}
                </span>
              </div>
            )}

            {isFree && (
              <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-foreground">
                Тариф «Без оплаты» позволяет только просмотр ранее сохранённых упоминаний и их выгрузку в CSV.
                Добавление ключевых слов, каналов и групп недоступно. Обратитесь к администратору для назначения платного тарифа.
              </div>
            )}

            {!isFree && (
              <div className="space-y-3 pt-2">
                <p className="text-sm font-medium text-foreground">Использование</p>
                <UsageRow
                  label="Группы каналов"
                  used={data.usage.groups}
                  max={data.limits.maxGroups}
                />
                <UsageRow
                  label="Отслеживаемые каналы"
                  used={data.usage.channels}
                  max={data.limits.maxChannels}
                />
                <UsageRow
                  label="Ключевые слова (точное совпадение)"
                  used={data.usage.keywordsExact}
                  max={data.limits.maxKeywordsExact}
                />
                <UsageRow
                  label="Ключевые слова (семантика)"
                  used={data.usage.keywordsSemantic}
                  max={data.limits.maxKeywordsSemantic}
                />
                <UsageRow
                  label="Своих каналов"
                  used={data.usage.ownChannels}
                  max={data.limits.maxOwnChannels}
                />
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function UsageRow({
  label,
  used,
  max,
}: {
  label: string
  used: number
  max: number
}) {
  const pct = usePercent(used, max)
  const atLimit = max > 0 && used >= max
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn(atLimit && "text-amber-600 font-medium")}>
          {used} / {max}
        </span>
      </div>
      <Progress value={pct} className="h-1.5" />
    </div>
  )
}
