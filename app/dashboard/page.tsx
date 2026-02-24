"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { SidebarNav } from "@/components/dashboard/sidebar-nav"
import { MobileSidebar } from "@/components/dashboard/mobile-sidebar"
import { Header } from "@/components/dashboard/header"
import { StatsCards } from "@/components/dashboard/stats-cards"
import { KeywordsManager } from "@/components/dashboard/keywords-manager"
import { MentionFeed } from "@/components/dashboard/mention-feed"
import { UserChannelsManager } from "@/components/dashboard/user-channels-manager"
import { ChannelGroupsSection } from "@/components/dashboard/channel-groups-section"
import { NotificationsSettings } from "@/components/dashboard/notifications-settings"
import { SemanticSearchSettings } from "@/components/dashboard/semantic-search-settings"
import { SupportSection } from "@/components/dashboard/support-section"
import { BillingModal } from "@/components/dashboard/billing-modal"
import { apiBaseUrl, apiJson } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import type { ChatOut } from "@/components/dashboard/user-channels-manager"

export default function DashboardPage() {
  const router = useRouter()
  const { user, loading } = useAuth()

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [activeNav, setActiveNav] = useState("Панель")
  const [billingOpen, setBillingOpen] = useState(false)
  const [serviceOnline, setServiceOnline] = useState(false)
  const [channelsRefreshKey, setChannelsRefreshKey] = useState(0)
  const [supportHasUnread, setSupportHasUnread] = useState(false)
  const [hasTrackedChannels, setHasTrackedChannels] = useState<boolean | null>(null)

  async function fetchSupportUnread() {
    try {
      const data = await apiJson<{ hasUnread: boolean }>(`${apiBaseUrl()}/api/support/has-any-unread`)
      setSupportHasUnread(data.hasUnread)
    } catch {
      setSupportHasUnread(false)
    }
  }

  async function fetchTrackedChannelsPresence() {
    try {
      const channels = await apiJson<ChatOut[]>("/api/chats")
      setHasTrackedChannels(channels.length > 0)
    } catch {
      setHasTrackedChannels(null)
    }
  }

  useEffect(() => {
    if (loading) return
    if (!user) {
      router.replace("/auth")
      return
    }
  }, [loading, user, router])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    const check = () =>
      fetch(`${apiBaseUrl()}/health`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data: { parser_running?: boolean } | null) => {
          if (!cancelled) setServiceOnline(Boolean(data?.parser_running))
        })
        .catch(() => {
          if (!cancelled) setServiceOnline(false)
        })
    check()
    const interval = setInterval(check, 15000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [user])

  useEffect(() => {
    if (!user) return
    fetchSupportUnread()
    const interval = setInterval(fetchSupportUnread, 30000)
    return () => clearInterval(interval)
  }, [user])

  useEffect(() => {
    if (!user) return
    fetchTrackedChannelsPresence()
  }, [user, channelsRefreshKey])

  function handleNavigate(item: string) {
    if (item === "Оплата") {
      setBillingOpen(true)
    } else if (item === "Настройки") {
      router.push("/settings")
    } else {
      setActiveNav(item)
    }
  }

  if (loading || !user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Загрузка...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop Sidebar */}
      <div className="hidden lg:block">
        <SidebarNav
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          activeItem={activeNav}
          onNavigate={handleNavigate}
          supportHasUnread={supportHasUnread}
          showGroupsOnboardingHint={activeNav === "Панель" && hasTrackedChannels === false}
        />
      </div>

      {/* Mobile Sidebar */}
      <MobileSidebar
        open={mobileOpen}
        onOpenChange={setMobileOpen}
        activeItem={activeNav}
        onNavigate={handleNavigate}
        supportHasUnread={supportHasUnread}
      />

      {/* Main Content */}
      <main
        className={cn(
          "flex min-h-screen flex-col transition-all duration-300",
          sidebarCollapsed ? "lg:ml-16" : "lg:ml-60"
        )}
      >
        <Header
          onMobileMenuToggle={() => setMobileOpen(true)}
          serviceOnline={serviceOnline}
        />

        <div className="flex-1 space-y-6 p-4 lg:p-6">
          {activeNav === "Группы" ? (
            <>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                  Группы и каналы
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Подпишитесь на группы каналов по тематикам или управляйте своими каналами для мониторинга.
                </p>
              </div>
              <ChannelGroupsSection onSubscribedChange={() => setChannelsRefreshKey((k) => k + 1)} canAddResources={user.plan !== "free"} />
              <UserChannelsManager
                key={channelsRefreshKey}
                canAddResources={user.plan !== "free"}
                onMyChannelsChange={(count) => setHasTrackedChannels(count > 0)}
              />
            </>
          ) : activeNav === "Уведомления" ? (
            <>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                  Уведомления
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Настройте каналы и условия отправки уведомлений о новых упоминаниях.
                </p>
              </div>
              <NotificationsSettings />
            </>
          ) : activeNav === "Поддержка" ? (
            <>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                  Поддержка
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Напишите администратору: создайте обращение или откройте существующую переписку.
                </p>
              </div>
              <SupportSection onTicketViewed={fetchSupportUnread} />
            </>
          ) : (
            <>
              {/* Page Title */}
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                  Панель управления
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Отслеживайте упоминания в Telegram и находите новых лидов.
                </p>
              </div>

              {/* Stats */}
              <StatsCards />

              {/* Keywords + Feed */}
              <div className="grid gap-6 xl:grid-cols-5">
                <div className="xl:col-span-2 space-y-6">
                  <KeywordsManager userId={user.id} canAddResources={user.plan !== "free"} />
                  <SemanticSearchSettings />
                </div>
                <div className="xl:col-span-3">
                  <MentionFeed userId={user.id} />
                </div>
              </div>
            </>
          )}
        </div>
      </main>

      {/* Billing Modal */}
      <BillingModal open={billingOpen} onOpenChange={setBillingOpen} />
    </div>
  )
}
