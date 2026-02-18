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
    name: "Starter",
    price: "$19",
    period: "/month",
    features: ["5 keywords", "10 groups", "Email notifications", "7-day history"],
    current: false,
  },
  {
    name: "Pro",
    price: "$49",
    period: "/month",
    features: [
      "25 keywords",
      "Unlimited groups",
      "Real-time alerts",
      "30-day history",
      "AI semantic search",
      "Lead tracking",
    ],
    current: true,
  },
  {
    name: "Enterprise",
    price: "$149",
    period: "/month",
    features: [
      "Unlimited keywords",
      "Unlimited groups",
      "Priority support",
      "365-day history",
      "API access",
      "Custom integrations",
      "Dedicated account manager",
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
          <DialogTitle className="text-card-foreground">Subscription Plans</DialogTitle>
          <DialogDescription>
            Choose the plan that fits your monitoring needs.
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
                  Current Plan
                </Badge>
              )}

              <h3 className="font-semibold text-card-foreground">{plan.name}</h3>
              <div className="mt-2 flex items-baseline gap-0.5">
                <span className="text-2xl font-bold text-card-foreground">{plan.price}</span>
                <span className="text-sm text-muted-foreground">{plan.period}</span>
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
                {plan.current ? "Active" : "Upgrade"}
              </Button>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
