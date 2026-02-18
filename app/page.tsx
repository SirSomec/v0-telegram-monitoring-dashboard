"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { SidebarNav } from "@/components/dashboard/sidebar-nav"
import { MobileSidebar } from "@/components/dashboard/mobile-sidebar"
import { Header } from "@/components/dashboard/header"
import { StatsCards } from "@/components/dashboard/stats-cards"
import { KeywordsManager } from "@/components/dashboard/keywords-manager"
import { MentionFeed } from "@/components/dashboard/mention-feed"
import { BillingModal } from "@/components/dashboard/billing-modal"

export default function DashboardPage() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [activeNav, setActiveNav] = useState("Dashboard")
  const [billingOpen, setBillingOpen] = useState(false)

  function handleNavigate(item: string) {
    if (item === "Billing") {
      setBillingOpen(true)
    } else {
      setActiveNav(item)
    }
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
          serviceOnline={true}
        />

        <div className="flex-1 space-y-6 p-4 lg:p-6">
          {/* Page Title */}
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Dashboard
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Monitor your Telegram mentions and discover new leads.
            </p>
          </div>

          {/* Stats */}
          <StatsCards />

          {/* Keywords + Feed */}
          <div className="grid gap-6 xl:grid-cols-5">
            <div className="xl:col-span-2">
              <KeywordsManager />
            </div>
            <div className="xl:col-span-3">
              <MentionFeed />
            </div>
          </div>
        </div>
      </main>

      {/* Billing Modal */}
      <BillingModal open={billingOpen} onOpenChange={setBillingOpen} />
    </div>
  )
}
