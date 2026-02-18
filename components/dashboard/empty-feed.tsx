"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { SearchX, Plus } from "lucide-react"

interface EmptyFeedProps {
  onAddKeyword: () => void
}

export function EmptyFeed({ onAddKeyword }: EmptyFeedProps) {
  return (
    <Card className="border-border bg-card">
      <CardContent className="flex flex-col items-center justify-center py-16 px-6 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-secondary">
          <SearchX className="size-8 text-muted-foreground" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-card-foreground">
          Упоминаний пока нет
        </h3>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
          Добавьте ключевые слова для начала мониторинга Telegram-групп. Упоминания будут появляться здесь по мере обнаружения в реальном времени.
        </p>
        <Button
          onClick={onAddKeyword}
          className="mt-6 bg-primary text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="mr-2 size-4" />
          Добавить первое ключевое слово
        </Button>
      </CardContent>
    </Card>
  )
}
