"use client"

import { useMemo, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ChannelsManager } from "@/components/admin/channels-manager"
import { ChannelGroupsManager } from "@/components/admin/channel-groups-manager"
import { AccountsManager } from "@/components/admin/accounts-manager"
import { PlanLimitsManager } from "@/components/admin/plan-limits-manager"
import { ParserManager } from "@/components/admin/parser-manager"
import { SupportManager } from "@/components/admin/support-manager"
import { Shield } from "lucide-react"
import { useAuth } from "@/lib/auth-context"

type AdminTab = "channels" | "groups" | "accounts" | "limits" | "parser" | "support"

export default function AdminPage() {
  const router = useRouter()
  const { user, loading } = useAuth()
  const [tab, setTab] = useState<AdminTab>("channels")

  useEffect(() => {
    if (loading) return
    if (!user) {
      router.replace("/auth")
      return
    }
    if (!user.isAdmin) {
      router.replace("/dashboard")
    }
  }, [loading, user, router])

  const title = useMemo(() => {
    switch (tab) {
      case "channels":
        return "Каналы"
      case "groups":
        return "Группы каналов"
      case "accounts":
        return "Учётные записи"
      case "limits":
        return "Лимиты тарифов"
      case "parser":
        return "Парсер"
      case "support":
        return "Поддержка"
    }
  }, [tab])

  if (loading || !user || !user.isAdmin) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Загрузка...</p>
      </div>
    )
  }

  const userId = user.id

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto w-full min-w-0 max-w-[90rem] space-y-4 px-3 py-4 sm:px-4 sm:space-y-6 md:px-6 lg:px-8">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Shield className="size-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">Админ-панель</h1>
            <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
              Управление источниками мониторинга и учётными записями сервиса.
            </p>
          </div>
        </div>

        <Tabs value={tab} onValueChange={(v) => setTab(v as AdminTab)}>
          <TabsList className="flex h-auto flex-wrap gap-1 bg-secondary p-1">
            <TabsTrigger value="channels">Каналы</TabsTrigger>
            <TabsTrigger value="groups">Группы</TabsTrigger>
            <TabsTrigger value="accounts">Учётки</TabsTrigger>
            <TabsTrigger value="limits">Лимиты тарифов</TabsTrigger>
            <TabsTrigger value="parser">Парсер</TabsTrigger>
          <TabsTrigger value="support">Поддержка</TabsTrigger>
          </TabsList>

          <TabsContent value="channels" className="mt-4 min-w-0 sm:mt-6">
            <h2 className="sr-only">{title}</h2>
            <ChannelsManager userId={userId} />
          </TabsContent>

          <TabsContent value="groups" className="mt-4 min-w-0 sm:mt-6">
            <h2 className="sr-only">{title}</h2>
            <ChannelGroupsManager userId={userId} />
          </TabsContent>

          <TabsContent value="accounts" className="mt-4 min-w-0 sm:mt-6">
            <h2 className="sr-only">{title}</h2>
            <AccountsManager />
          </TabsContent>

          <TabsContent value="limits" className="mt-4 min-w-0 sm:mt-6">
            <h2 className="sr-only">{title}</h2>
            <PlanLimitsManager />
          </TabsContent>

          <TabsContent value="parser" className="mt-4 min-w-0 sm:mt-6">
            <h2 className="sr-only">{title}</h2>
            <ParserManager />
          </TabsContent>

          <TabsContent value="support" className="mt-4 min-w-0 sm:mt-6">
            <h2 className="sr-only">{title}</h2>
            <SupportManager />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

