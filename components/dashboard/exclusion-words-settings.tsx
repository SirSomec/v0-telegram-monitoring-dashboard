"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Plus, X, Loader2, ShieldOff } from "lucide-react"
import { apiBaseUrl, apiJson } from "@/lib/api"

type ExclusionWordItem = { id: number; text: string; createdAt: string }

export function ExclusionWordsSettings() {
  const [words, setWords] = useState<ExclusionWordItem[]>([])
  const [loading, setLoading] = useState(true)
  const [newWord, setNewWord] = useState("")
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState("")

  const fetchWords = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<ExclusionWordItem[]>(`${apiBaseUrl()}/api/exclusion-words`)
      setWords(data)
    } catch {
      setError("Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchWords()
  }, [fetchWords])

  async function addWord() {
    const trimmed = newWord.trim()
    if (!trimmed || words.some((w) => w.text === trimmed)) return
    setAdding(true)
    setError("")
    try {
      const created = await apiJson<ExclusionWordItem>(`${apiBaseUrl()}/api/exclusion-words`, {
        method: "POST",
        body: JSON.stringify({ text: trimmed }),
      })
      setNewWord("")
      setWords((prev) => [...prev, created])
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка добавления")
    } finally {
      setAdding(false)
    }
  }

  async function removeWord(item: ExclusionWordItem) {
    setError("")
    try {
      await apiJson<{ ok: boolean }>(`${apiBaseUrl()}/api/exclusion-words/${item.id}`, {
        method: "DELETE",
      })
      setWords((prev) => prev.filter((w) => w.id !== item.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления")
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault()
      addWord()
    }
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <ShieldOff className="size-4" />
          Слова-исключения
        </CardTitle>
        <CardDescription>
          Если в сообщении вместе с ключевым словом есть любое из этих слов, упоминание не создаётся. Регистр не учитывается.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Добавить слово-исключение..."
            value={newWord}
            onChange={(e) => setNewWord(e.target.value)}
            onKeyDown={handleKeyDown}
            className="bg-secondary border-border text-foreground placeholder:text-muted-foreground"
          />
          <Button
            onClick={addWord}
            size="sm"
            disabled={adding || !newWord.trim()}
            className="shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {adding ? <Loader2 className="mr-1 size-4 animate-spin" /> : <Plus className="mr-1 size-4" />}
            Добавить
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {loading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Загрузка...
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {words.map((item) => (
              <Badge
                key={item.id}
                variant="secondary"
                className="gap-1.5 bg-secondary text-secondary-foreground border border-border px-3 py-1.5 text-sm"
              >
                {item.text}
                <button
                  onClick={() => removeWord(item)}
                  className="ml-0.5 rounded-full p-0.5 hover:bg-muted transition-colors"
                  aria-label={`Удалить ${item.text}`}
                >
                  <X className="size-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}

        {!loading && words.length === 0 && (
          <p className="py-2 text-sm text-muted-foreground">
            Слов-исключений пока нет. Добавьте слово выше, чтобы отфильтровать ложные срабатывания.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
