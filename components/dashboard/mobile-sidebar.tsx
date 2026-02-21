"use client"

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  LayoutDashboard,
  Settings,
  Users,
  Bell,
  CreditCard,
  MessageCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"

// visible: false — скрыто до реализации фич (ROADMAP)
const allNavItems = [
  { icon: LayoutDashboard, label: "Панель", visible: true },
  { icon: Users, label: "Группы", visible: true },
  { icon: Bell, label: "Уведомления", visible: true },
  { icon: MessageCircle, label: "Поддержка", visible: true },
  { icon: CreditCard, label: "Оплата", visible: true },
  { icon: Settings, label: "Настройки", visible: true },
]
const navItems = allNavItems.filter((item) => item.visible)

interface MobileSidebarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  activeItem: string
  onNavigate: (item: string) => void
  supportHasUnread?: boolean
}

export function MobileSidebar({ open, onOpenChange, activeItem, onNavigate, supportHasUnread = false }: MobileSidebarProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-64 bg-sidebar border-sidebar-border p-0">
        <SheetHeader className="border-b border-sidebar-border p-4">
          <SheetTitle className="flex items-center gap-3 text-sidebar-foreground">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-primary-foreground">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            TeleScope
          </SheetTitle>
        </SheetHeader>

        <nav className="flex flex-col gap-1 p-3">
          {navItems.map((item) => {
            const isActive = activeItem === item.label
            const showSupportUnread = item.label === "Поддержка" && supportHasUnread
            return (
              <button
                key={item.label}
                onClick={() => {
                  onNavigate(item.label)
                  onOpenChange(false)
                }}
                className={cn(
                  "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-primary"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
                )}
              >
                <item.icon className="size-5" />
                <span>{item.label}</span>
                {showSupportUnread && (
                  <span
                    className="absolute right-3 top-2 size-2 rounded-full bg-destructive"
                    aria-hidden
                  />
                )}
              </button>
            )
          })}
        </nav>
      </SheetContent>
    </Sheet>
  )
}
