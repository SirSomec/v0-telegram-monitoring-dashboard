"use client"

import { Search, Menu } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"

interface HeaderProps {
  onMobileMenuToggle: () => void
  serviceOnline: boolean
}

export function Header({ onMobileMenuToggle, serviceOnline }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-border bg-background/80 px-4 backdrop-blur-sm lg:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden text-muted-foreground"
        onClick={onMobileMenuToggle}
      >
        <Menu className="size-5" />
        <span className="sr-only">Открыть меню</span>
      </Button>

      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Глобальный поиск..."
          className="pl-9 bg-secondary border-border text-foreground placeholder:text-muted-foreground"
        />
      </div>

      <div className="ml-auto flex items-center gap-4">
        <Badge
          variant="outline"
          className={serviceOnline
            ? "border-success/30 bg-success/10 text-success"
            : "border-destructive/30 bg-destructive/10 text-destructive"
          }
        >
          <span className={`mr-1.5 inline-block size-2 rounded-full ${serviceOnline ? "bg-success" : "bg-destructive"}`} />
          {serviceOnline ? "Сервис онлайн" : "Сервис оффлайн"}
        </Badge>

        <Avatar className="size-8 border border-border">
          <AvatarFallback className="bg-secondary text-foreground text-xs font-medium">
            АП
          </AvatarFallback>
        </Avatar>
      </div>
    </header>
  )
}
