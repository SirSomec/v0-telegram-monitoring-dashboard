"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Search, Loader2 } from "lucide-react"
import { apiBaseUrl, apiJson } from "@/lib/api"

const DEFAULT_THRESHOLD_PERCENT = 60
const DEFAULT_MIN_TOPIC_PERCENT = 70

type SemanticSettings = {
  semanticThreshold: number | null
  semanticMinTopicPercent: number | null
}

export function SemanticSearchSettings() {
  const [semantic, setSemantic] = useState<SemanticSettings>({
    semanticThreshold: null,
    semanticMinTopicPercent: null,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiJson<SemanticSettings>(`${apiBaseUrl()}/api/settings/semantic`)
      .then((data) => {
        if (!cancelled)
          setSemantic({
            semanticThreshold: data.semanticThreshold ?? null,
            semanticMinTopicPercent: data.semanticMinTopicPercent ?? null,
          })
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSave() {
    setSaving(true)
    try {
      const res = await apiJson<SemanticSettings>(`${apiBaseUrl()}/api/settings/semantic`, {
        method: "PATCH",
        body: JSON.stringify({
          semanticThreshold: semantic.semanticThreshold ?? DEFAULT_THRESHOLD_PERCENT / 100,
          semanticMinTopicPercent: semantic.semanticMinTopicPercent ?? DEFAULT_MIN_TOPIC_PERCENT,
        }),
      })
      setSemantic(res)
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Card className="border-border bg-card">
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Search className="size-4" />
          Семантический поиск
        </CardTitle>
        <CardDescription>
          Порог срабатывания и минимальный % совпадения с темой. При пустых значениях используются стандартные: 60% и
          70%.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <Label htmlFor="semantic-threshold" className="text-muted-foreground text-xs">
              Порог срабатывания, %
            </Label>
            <Input
              id="semantic-threshold"
              type="number"
              min={0}
              max={100}
              step={1}
              value={semantic.semanticThreshold != null ? Math.round(semantic.semanticThreshold * 100) : ""}
              placeholder={String(DEFAULT_THRESHOLD_PERCENT)}
              onChange={(e) => {
                const v = e.target.value
                setSemantic((s) => ({
                  ...s,
                  semanticThreshold: v === "" ? null : Math.min(100, Math.max(0, Number(v))) / 100,
                }))
                setDirty(true)
              }}
              className="mt-1 w-24 bg-secondary border-border"
            />
          </div>
          <div>
            <Label htmlFor="semantic-min-topic" className="text-muted-foreground text-xs">
              Мин. % совпадения с темой
            </Label>
            <Input
              id="semantic-min-topic"
              type="number"
              min={0}
              max={100}
              step={1}
              value={semantic.semanticMinTopicPercent ?? ""}
              placeholder={String(DEFAULT_MIN_TOPIC_PERCENT)}
              onChange={(e) => {
                const v = e.target.value
                setSemantic((s) => ({
                  ...s,
                  semanticMinTopicPercent: v === "" ? null : Math.min(100, Math.max(0, Number(v))),
                }))
                setDirty(true)
              }}
              className="mt-1 w-24 bg-secondary border-border"
            />
          </div>
          {dirty && (
            <Button type="button" size="sm" disabled={saving} className="gap-2" onClick={handleSave}>
              {saving && <Loader2 className="size-4 animate-spin" />}
              Сохранить
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
