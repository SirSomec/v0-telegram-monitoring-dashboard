"use client"

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Check } from "lucide-react"
import { cn } from "@/lib/utils"

const plans = [
  {
    name: "Стартовый",
    price: "1 490",
    currency: "\u20BD",
    period: "/мес",
    features: ["5 ключевых слов", "10 групп", "Email-уведомления", "История за 7 дней"],
    current: false,
  },
  {
    name: "Про",
    price: "3 990",
    currency: "\u20BD",
    period: "/мес",
    features: [
      "25 ключевых слов",
      "Безлимит групп",
      "Уведомления в реальном времени",
      "История за 30 дней",
      "ИИ семантический поиск",
      "Трекинг лидов",
    ],
    current: true,
  },
  {
    name: "Бизнес",
    price: "9 990",
    currency: "\u20BD",
    period: "/мес",
    features: [
      "Безлимит ключевых слов",
      "Безлимит групп",
      "Приоритетная поддержка",
      "История за 365 дней",
      "API-доступ",
      "Кастомные интеграции",
      "Персональный менеджер",
    ],
    current: false,
  },
]

interface BillingModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function BillingModal({ open, onOpenChange }: BillingModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">Тарифные планы</DialogTitle>
          <DialogDescription>
            Выберите план, который подходит для ваших задач мониторинга.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-3 mt-4">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={cn(
                "relative flex flex-col rounded-lg border p-4",
                plan.current
                  ? "border-primary bg-primary/5"
                  : "border-border bg-secondary/50"
              )}
            >
              {plan.current && (
                <Badge className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground text-xs">
                  Текущий план
                </Badge>
              )}

              <h3 className="font-semibold text-card-foreground">{plan.name}</h3>
              <div className="mt-2 flex items-baseline gap-0.5">
                <span className="text-2xl font-bold text-card-foreground">{plan.price}</span>
                <span className="text-sm text-muted-foreground">{" "}{plan.currency}{plan.period}</span>
              </div>

              <ul className="mt-4 flex-1 space-y-2">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2 text-sm text-secondary-foreground">
                    <Check className="size-3.5 shrink-0 text-primary" />
                    {feature}
                  </li>
                ))}
              </ul>

              <Button
                className={cn(
                  "mt-4 w-full text-sm",
                  plan.current
                    ? "bg-secondary text-secondary-foreground hover:bg-secondary/80 cursor-default"
                    : "bg-primary text-primary-foreground hover:bg-primary/90"
                )}
                disabled={plan.current}
              >
                {plan.current ? "Активен" : "Перейти"}
              </Button>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
