"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Plus, X, Sparkles, Target } from "lucide-react"

const initialKeywords = [
  "bitcoin",
  "крипто биржа",
  "NFT маркетплейс",
  "DeFi протокол",
  "web3 вакансии",
  "solana",
  "ethereum",
]

export function KeywordsManager() {
  const [keywords, setKeywords] = useState(initialKeywords)
  const [newKeyword, setNewKeyword] = useState("")
  const [semanticMode, setSemanticMode] = useState(false)

  function addKeyword() {
    const trimmed = newKeyword.trim()
    if (trimmed && !keywords.includes(trimmed)) {
      setKeywords((prev) => [...prev, trimmed])
      setNewKeyword("")
    }
  }

  function removeKeyword(keyword: string) {
    setKeywords((prev) => prev.filter((k) => k !== keyword))
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault()
      addKeyword()
    }
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold text-card-foreground">
            Управление ключевыми словами
          </CardTitle>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Target className="size-4 text-muted-foreground" />
              <Label htmlFor="search-mode" className="text-xs text-muted-foreground cursor-pointer">
                Точное
              </Label>
              <Switch
                id="search-mode"
                checked={semanticMode}
                onCheckedChange={setSemanticMode}
              />
              <Label htmlFor="search-mode" className="flex items-center gap-1 text-xs text-muted-foreground cursor-pointer">
                <Sparkles className="size-3" />
                ИИ семантика
              </Label>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Добавить ключевое слово..."
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyDown={handleKeyDown}
            className="bg-secondary border-border text-foreground placeholder:text-muted-foreground"
          />
          <Button onClick={addKeyword} size="sm" className="shrink-0 bg-primary text-primary-foreground hover:bg-primary/90">
            <Plus className="mr-1 size-4" />
            Добавить
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          {keywords.map((keyword) => (
            <Badge
              key={keyword}
              variant="secondary"
              className="gap-1.5 bg-secondary text-secondary-foreground border border-border px-3 py-1.5 text-sm"
            >
              {keyword}
              <button
                onClick={() => removeKeyword(keyword)}
                className="ml-0.5 rounded-full p-0.5 hover:bg-muted transition-colors"
                aria-label={`Удалить ${keyword}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>

        {keywords.length === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Ключевые слова не добавлены. Введите слово выше и нажмите Enter для начала мониторинга.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
