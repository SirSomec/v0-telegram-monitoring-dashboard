"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Plus, X, Sparkles, Target, Loader2, RotateCcw, Trash2, Info } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { apiBaseUrl, apiJson } from "@/lib/api"

type KeywordItem = { id: number; text: string; useSemantic: boolean; enabled: boolean }

export function KeywordsManager({ userId = 1, canAddResources = true }: { userId?: number; canAddResources?: boolean }) {
  const [keywords, setKeywords] = useState<KeywordItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")
  const [newKeyword, setNewKeyword] = useState("")
  const [semanticMode, setSemanticMode] = useState(false)
  const [adding, setAdding] = useState(false)

  const fetchKeywords = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<KeywordItem[]>(`${apiBaseUrl()}/api/keywords`)
      setKeywords(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchKeywords()
  }, [fetchKeywords])

  async function addKeyword() {
    const trimmed = newKeyword.trim()
    if (!trimmed || keywords.some((k) => k.enabled && k.text === trimmed)) return
    setAdding(true)
    setError("")
    try {
      await apiJson<KeywordItem>(`${apiBaseUrl()}/api/keywords`, {
        method: "POST",
        body: JSON.stringify({ text: trimmed, useSemantic: semanticMode }),
      })
      setNewKeyword("")
      await fetchKeywords()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка добавления")
    } finally {
      setAdding(false)
    }
  }

  async function removeKeyword(item: KeywordItem) {
    setError("")
    try {
      await apiJson<{ ok: boolean }>(`${apiBaseUrl()}/api/keywords/${item.id}`, { method: "DELETE" })
      setKeywords((prev) => prev.map((k) => (k.id === item.id ? { ...k, enabled: false } : k)))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления")
    }
  }

  async function restoreKeyword(item: KeywordItem) {
    setError("")
    try {
      const restored = await apiJson<KeywordItem>(`${apiBaseUrl()}/api/keywords/${item.id}/restore`, { method: "PATCH" })
      setKeywords((prev) => prev.map((k) => (k.id === item.id ? restored : k)))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка восстановления")
    }
  }

  async function permanentDeleteKeyword(item: KeywordItem) {
    setError("")
    try {
      await apiJson<{ ok: boolean }>(`${apiBaseUrl()}/api/keywords/${item.id}?permanent=1`, { method: "DELETE" })
      setKeywords((prev) => prev.filter((k) => k.id !== item.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления")
    }
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
        {!canAddResources && (
          <p className="text-xs text-amber-600 bg-amber-500/10 border border-amber-500/30 rounded-md px-3 py-2 mb-2">
            Тариф «Без оплаты»: добавление ключевых слов недоступно. Доступны только просмотр и выгрузка. Раздел «Оплата» → назначение тарифа администратором.
          </p>
        )}
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
        <Alert className="mt-3 border-primary/20 bg-primary/5 text-sm">
          <Info className="size-4 text-primary" />
          <AlertTitle className="text-foreground font-medium">Как работает поиск</AlertTitle>
          <AlertDescription asChild>
            <div className="mt-1 space-y-2 text-muted-foreground">
              <p>
                <strong>Точное</strong> — в ленту попадают только сообщения, где есть подстрока ключевого слова. Например, слово «доставка» найдёт «доставка пиццы», «бесплатная доставка».
              </p>
              <p>
                <strong>ИИ семантика</strong> — модель понимает смысл: ключевое слово сопоставляется с текстом по смыслу. Например, ключ «доставка заказа» может совпасть с сообщениями «привезём ваш заказ», «курьер приедет через час», «самовывоз в пункте выдачи». В ленте отображается процент совпадения с темой.
              </p>
            </div>
          </AlertDescription>
        </Alert>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Добавить ключевое слово..."
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!canAddResources}
            className="bg-secondary border-border text-foreground placeholder:text-muted-foreground"
          />
          <Button
            onClick={addKeyword}
            size="sm"
            disabled={!canAddResources || adding || !newKeyword.trim()}
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
          <>
            <div className="flex flex-wrap gap-2">
              {keywords.filter((k) => k.enabled).map((item) => (
                <Badge
                  key={item.id}
                  variant="secondary"
                  className="gap-1.5 bg-secondary text-secondary-foreground border border-border px-3 py-1.5 text-sm"
                >
                  {item.useSemantic ? (
                    <Sparkles className="size-3 shrink-0" aria-label="Семантика" />
                  ) : (
                    <Target className="size-3 shrink-0" aria-label="Точное" />
                  )}
                  {item.text}
                  <button
                    onClick={() => removeKeyword(item)}
                    className="ml-0.5 rounded-full p-0.5 hover:bg-muted transition-colors"
                    aria-label={`Удалить ${item.text}`}
                  >
                    <X className="size-3" />
                  </button>
                </Badge>
              ))}
            </div>

            {keywords.some((k) => !k.enabled) && (
              <div className="space-y-2 pt-4 border-t border-border">
                <p className="text-xs font-medium text-muted-foreground">Неиспользуемые (можно восстановить)</p>
                <div className="flex flex-wrap gap-2">
                  {keywords.filter((k) => !k.enabled).map((item) => (
                    <Badge
                      key={item.id}
                      variant="outline"
                      className="gap-1.5 border-dashed bg-muted/50 text-muted-foreground px-3 py-1.5 text-sm"
                    >
                      {item.useSemantic ? (
                        <Sparkles className="size-3 shrink-0 opacity-60" aria-label="Семантика" />
                      ) : (
                        <Target className="size-3 shrink-0 opacity-60" aria-label="Точное" />
                      )}
                      {item.text}
                      <button
                        onClick={() => restoreKeyword(item)}
                        className="ml-0.5 rounded-full p-0.5 hover:bg-muted transition-colors"
                        aria-label={`Восстановить ${item.text}`}
                        title="Восстановить"
                      >
                        <RotateCcw className="size-3" />
                      </button>
                      <button
                        onClick={() => permanentDeleteKeyword(item)}
                        className="rounded-full p-0.5 hover:bg-destructive/20 text-muted-foreground hover:text-destructive transition-colors"
                        aria-label={`Удалить навсегда ${item.text}`}
                        title="Удалить навсегда"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {!loading && keywords.filter((k) => k.enabled).length === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Ключевые слова не добавлены. Введите слово выше и нажмите Enter для начала мониторинга.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
