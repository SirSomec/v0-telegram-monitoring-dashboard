"use client"

import { useMemo, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ChannelsManager } from "@/components/admin/channels-manager"
import { ChannelGroupsManager } from "@/components/admin/channel-groups-manager"
import { AccountsManager } from "@/components/admin/accounts-manager"
import { ParserManager } from "@/components/admin/parser-manager"
import { Shield } from "lucide-react"
import { useAuth } from "@/lib/auth-context"

type AdminTab = "channels" | "groups" | "accounts" | "parser"

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
      case "parser":
        return "Парсер"
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
      <main className="mx-auto w-full max-w-6xl space-y-6 p-4 lg:p-6">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Shield className="size-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Админ-панель</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Управление источниками мониторинга и учётными записями сервиса.
            </p>
          </div>
        </div>

        <Tabs value={tab} onValueChange={(v) => setTab(v as AdminTab)}>
          <TabsList className="bg-secondary">
            <TabsTrigger value="channels">Каналы</TabsTrigger>
            <TabsTrigger value="groups">Группы</TabsTrigger>
            <TabsTrigger value="accounts">Учётки</TabsTrigger>
            <TabsTrigger value="parser">Парсер</TabsTrigger>
          </TabsList>

          <TabsContent value="channels" className="mt-6">
            <h2 className="sr-only">{title}</h2>
            <ChannelsManager userId={userId} />
          </TabsContent>

          <TabsContent value="groups" className="mt-6">
            <h2 className="sr-only">{title}</h2>
            <ChannelGroupsManager userId={userId} />
          </TabsContent>

          <TabsContent value="accounts" className="mt-6">
            <h2 className="sr-only">{title}</h2>
            <AccountsManager />
          </TabsContent>

          <TabsContent value="parser" className="mt-6">
            <h2 className="sr-only">{title}</h2>
            <ParserManager />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

