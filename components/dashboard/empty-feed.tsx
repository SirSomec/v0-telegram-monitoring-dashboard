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
          No mentions yet
        </h3>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
          Add some keywords to start monitoring Telegram groups. Mentions will appear here as they are detected in real-time.
        </p>
        <Button
          onClick={onAddKeyword}
          className="mt-6 bg-primary text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="mr-2 size-4" />
          Add Your First Keyword
        </Button>
      </CardContent>
    </Card>
  )
}
