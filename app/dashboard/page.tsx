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
import { BillingModal } from "@/components/dashboard/billing-modal"
import { apiBaseUrl } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"

export default function DashboardPage() {
  const router = useRouter()
  const { user, loading } = useAuth()

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [activeNav, setActiveNav] = useState("Панель")
  const [billingOpen, setBillingOpen] = useState(false)
  const [serviceOnline, setServiceOnline] = useState(false)

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
    fetch(`${apiBaseUrl()}/health`)
      .then((r) => r.ok)
      .then((ok) => {
        if (!cancelled) setServiceOnline(ok)
      })
      .catch(() => {
        if (!cancelled) setServiceOnline(false)
      })
    return () => {
      cancelled = true
    }
  }, [user])

  function handleNavigate(item: string) {
    if (item === "Оплата") {
      setBillingOpen(true)
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
        />
      </div>

      {/* Mobile Sidebar */}
      <MobileSidebar
        open={mobileOpen}
        onOpenChange={setMobileOpen}
        activeItem={activeNav}
        onNavigate={handleNavigate}
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
            <div className="xl:col-span-2">
              <KeywordsManager userId={user.id} />
            </div>
            <div className="xl:col-span-3">
              <MentionFeed userId={user.id} />
            </div>
          </div>
        </div>
      </main>

      {/* Billing Modal */}
      <BillingModal open={billingOpen} onOpenChange={setBillingOpen} />
    </div>
  )
}
