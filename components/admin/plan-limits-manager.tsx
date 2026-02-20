"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { RefreshCw, Save } from "lucide-react"
import { apiJson } from "@/components/admin/api"

const PLAN_LABELS: Record<string, string> = {
  free: "Без оплаты",
  basic: "Базовый",
  pro: "Про",
  business: "Бизнес",
}

export type PlanLimitRow = {
  planSlug: string
  label: string
  maxGroups: number
  maxChannels: number
  maxKeywordsExact: number
  maxKeywordsSemantic: number
  maxOwnChannels: number
  canTrack: boolean
}

export function PlanLimitsManager() {
  const [rows, setRows] = useState<PlanLimitRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")
  const [savingSlug, setSavingSlug] = useState<string | null>(null)
  const [dirty, setDirty] = useState<Record<string, PlanLimitRow>>({})

  const fetchLimits = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<PlanLimitRow[]>("/api/admin/plan-limits")
      setRows(data)
      setDirty({})
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLimits()
  }, [fetchLimits])

  function getRow(slug: string): PlanLimitRow {
    return dirty[slug] ?? rows.find((r) => r.planSlug === slug) ?? {
      planSlug: slug,
      label: PLAN_LABELS[slug] ?? slug,
      maxGroups: 0,
      maxChannels: 0,
      maxKeywordsExact: 0,
      maxKeywordsSemantic: 0,
      maxOwnChannels: 0,
      canTrack: false,
    }
  }

  function setField(slug: string, field: keyof PlanLimitRow, value: number | string | boolean) {
    const current = getRow(slug)
    setDirty((prev) => ({
      ...prev,
      [slug]: { ...current, [field]: value },
    }))
  }

  async function save(slug: string) {
    const row = getRow(slug)
    setSavingSlug(slug)
    setError("")
    try {
      await apiJson<PlanLimitRow>("/api/admin/plan-limits", {
        method: "PATCH",
        body: JSON.stringify({
          planSlug: row.planSlug,
          label: row.label,
          maxGroups: row.maxGroups,
          maxChannels: row.maxChannels,
          maxKeywordsExact: row.maxKeywordsExact,
          maxKeywordsSemantic: row.maxKeywordsSemantic,
          maxOwnChannels: row.maxOwnChannels,
          canTrack: row.canTrack,
        }),
      })
      setDirty((prev) => {
        const next = { ...prev }
        delete next[slug]
        return next
      })
      await fetchLimits()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения")
    } finally {
      setSavingSlug(null)
    }
  }

  if (loading && rows.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-8">Загрузка лимитов…</div>
    )
  }

  return (
    <div className="space-y-6">
      <Card className="border-border bg-card">
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base font-semibold text-card-foreground">
            Лимиты тарифных планов
          </CardTitle>
          <Button size="sm" variant="outline" onClick={fetchLimits} disabled={loading}>
            <RefreshCw className={`mr-2 size-4 ${loading ? "animate-spin" : ""}`} />
            Обновить
          </Button>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Измените лимиты для каждого тарифа. После изменения нажмите «Сохранить» у нужного плана.
            Тариф «Без оплаты» обычно имеет нулевые лимиты и can_track = false (только просмотр и выгрузка).
          </p>
          {error && <p className="text-sm text-destructive mb-4">{error}</p>}
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {(["free", "basic", "pro", "business"] as const).map((slug) => {
              const r = getRow(slug)
              const isDirty = !!dirty[slug]
              const saving = savingSlug === slug
              return (
                <Card key={slug} className="border-border bg-secondary/30">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold">{r.label}</CardTitle>
                    <p className="text-xs text-muted-foreground font-mono">{slug}</p>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Название</Label>
                      <Input
                        value={r.label}
                        onChange={(e) => setField(slug, "label", e.target.value)}
                        className="h-8 text-sm bg-background border-border"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Групп каналов</Label>
                      <Input
                        type="number"
                        min={0}
                        value={r.maxGroups}
                        onChange={(e) => setField(slug, "maxGroups", parseInt(e.target.value, 10) || 0)}
                        className="h-8 text-sm bg-background border-border"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Каналов (всего)</Label>
                      <Input
                        type="number"
                        min={0}
                        value={r.maxChannels}
                        onChange={(e) => setField(slug, "maxChannels", parseInt(e.target.value, 10) || 0)}
                        className="h-8 text-sm bg-background border-border"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Ключевых слов (точное)</Label>
                      <Input
                        type="number"
                        min={0}
                        value={r.maxKeywordsExact}
                        onChange={(e) => setField(slug, "maxKeywordsExact", parseInt(e.target.value, 10) || 0)}
                        className="h-8 text-sm bg-background border-border"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Ключевых слов (семантика)</Label>
                      <Input
                        type="number"
                        min={0}
                        value={r.maxKeywordsSemantic}
                        onChange={(e) => setField(slug, "maxKeywordsSemantic", parseInt(e.target.value, 10) || 0)}
                        className="h-8 text-sm bg-background border-border"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Своих каналов</Label>
                      <Input
                        type="number"
                        min={0}
                        value={r.maxOwnChannels}
                        onChange={(e) => setField(slug, "maxOwnChannels", parseInt(e.target.value, 10) || 0)}
                        className="h-8 text-sm bg-background border-border"
                      />
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-border bg-background/50 px-3 py-2">
                      <Label className="text-xs cursor-pointer">Участвует в мониторинге</Label>
                      <Switch
                        checked={r.canTrack}
                        onCheckedChange={(v) => setField(slug, "canTrack", v)}
                      />
                    </div>
                    <Button
                      size="sm"
                      className="w-full"
                      disabled={saving}
                      onClick={() => save(slug)}
                    >
                      {saving ? <RefreshCw className="mr-2 size-4 animate-spin" /> : <Save className="mr-2 size-4" />}
                      {saving ? "Сохранение…" : "Сохранить"}
                    </Button>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
