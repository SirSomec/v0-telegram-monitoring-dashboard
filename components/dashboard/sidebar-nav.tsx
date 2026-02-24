"use client"

import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Settings,
  Users,
  Bell,
  CreditCard,
  MessageCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"

// visible: false — скрыто до реализации фич (ROADMAP: Группы, Уведомления, Оплата)
const allNavItems = [
  { icon: LayoutDashboard, label: "Панель", visible: true },
  { icon: Users, label: "Группы", visible: true },
  { icon: Bell, label: "Уведомления", visible: true },
  { icon: MessageCircle, label: "Поддержка", visible: true },
  { icon: CreditCard, label: "Оплата", visible: true },
  { icon: Settings, label: "Настройки", visible: true },
]
const navItems = allNavItems.filter((item) => item.visible)

interface SidebarNavProps {
  collapsed: boolean
  onToggle: () => void
  activeItem: string
  onNavigate: (item: string) => void
  supportHasUnread?: boolean
  showGroupsOnboardingHint?: boolean
}

export function SidebarNav({
  collapsed,
  onToggle,
  activeItem,
  onNavigate,
  supportHasUnread = false,
  showGroupsOnboardingHint = false,
}: SidebarNavProps) {
  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <div className={cn("flex h-16 items-center border-b border-sidebar-border px-4", collapsed ? "justify-center" : "gap-3")}>
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-primary-foreground">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        {!collapsed && (
          <span className="text-lg font-semibold tracking-tight text-sidebar-foreground">
            TeleScope
          </span>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-3">
        {navItems.map((item) => {
          const isActive = activeItem === item.label
          const showSupportUnread = item.label === "Поддержка" && supportHasUnread
          const showGroupsHint = item.label === "Группы" && showGroupsOnboardingHint && !collapsed
          return (
            <div key={item.label} className="space-y-1">
              <button
                onClick={() => onNavigate(item.label)}
                className={cn(
                  "relative flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  collapsed && "justify-center px-0",
                  isActive
                    ? "bg-sidebar-accent text-primary"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
                )}
              >
                <item.icon className="size-5 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
                {showSupportUnread && (
                  <span
                    className="absolute right-2 top-2 size-2 rounded-full bg-destructive"
                    aria-hidden
                  />
                )}
              </button>
              {showGroupsHint && (
                <div className="relative ml-9 rounded-xl border border-primary/35 bg-primary/10 px-2.5 py-1.5 text-[11px] leading-tight text-primary">
                  <span
                    className="absolute -top-1 left-3 size-2 rotate-45 border-l border-t border-primary/35 bg-primary/10"
                    aria-hidden
                  />
                  добавьте первые каналы для отслеживания
                </div>
              )}
            </div>
          )
        })}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className={cn("size-8 text-muted-foreground hover:text-sidebar-foreground", !collapsed && "ml-auto")}
        >
          {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
          <span className="sr-only">{collapsed ? "Развернуть" : "Свернуть"}</span>
        </Button>
      </div>
    </aside>
  )
}
