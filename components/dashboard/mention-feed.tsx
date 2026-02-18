"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ExternalLink, UserPlus, Check, MessageSquare } from "lucide-react"

interface Mention {
  id: string
  groupName: string
  groupIcon: string
  userName: string
  userInitials: string
  message: string
  keyword: string
  timestamp: string
  isLead: boolean
}

const sampleMentions: Mention[] = [
  {
    id: "1",
    groupName: "Крипто Трейдинг Сигналы",
    groupIcon: "КТ",
    userName: "Алексей Петров",
    userInitials: "АП",
    message: "Ищу надёжную крипто биржу с низкими комиссиями. Сейчас изучаю разные DeFi протокол варианты для своего портфеля.",
    keyword: "крипто биржа",
    timestamp: "2 мин назад",
    isLead: false,
  },
  {
    id: "2",
    groupName: "Web3 Разработчики",
    groupIcon: "W3",
    userName: "Мария Чен",
    userInitials: "МЧ",
    message: "Кто-нибудь нанимает на web3 вакансии? У меня 3 года опыта с Solidity, ищу удалённую работу в экосистеме ethereum.",
    keyword: "web3 вакансии",
    timestamp: "8 мин назад",
    isLead: true,
  },
  {
    id: "3",
    groupName: "NFT Коллекционеры",
    groupIcon: "НК",
    userName: "Дмитрий Волков",
    userInitials: "ДВ",
    message: "Только что запустили новый NFT маркетплейс на Solana. Более низкие комиссии за газ и быстрые транзакции по сравнению с ETH-платформами.",
    keyword: "NFT маркетплейс",
    timestamp: "15 мин назад",
    isLead: false,
  },
  {
    id: "4",
    groupName: "Bitcoin Ежедневно",
    groupIcon: "БЕ",
    userName: "Сара Ким",
    userInitials: "СК",
    message: "Bitcoin только что пробил уровень сопротивления 100k. Этот бычий забег отличается от 2021. Холдеры наконец вознаграждены!",
    keyword: "bitcoin",
    timestamp: "23 мин назад",
    isLead: false,
  },
  {
    id: "5",
    groupName: "DeFi Инноваторы",
    groupIcon: "ДИ",
    userName: "Джеймс Райт",
    userInitials: "ДР",
    message: "Наш новый DeFi протокол запустил фарминг с 12% APY. Ищем ранних последователей и партнёрские возможности.",
    keyword: "DeFi протокол",
    timestamp: "31 мин назад",
    isLead: false,
  },
  {
    id: "6",
    groupName: "Ethereum Разработчики",
    groupIcon: "ЕР",
    userName: "Лена Иванова",
    userInitials: "ЛИ",
    message: "После обновления ethereum комиссии за газ значительно снизились. Отличное время для деплоя новых смарт-контрактов в мейннет.",
    keyword: "ethereum",
    timestamp: "45 мин назад",
    isLead: true,
  },
]

function highlightKeyword(text: string, keyword: string) {
  const regex = new RegExp(`(${keyword})`, "gi")
  const parts = text.split(regex)
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="rounded bg-primary/20 px-0.5 text-primary font-medium">
        {part}
      </mark>
    ) : (
      part
    )
  )
}

export function MentionFeed() {
  const [mentions, setMentions] = useState(sampleMentions)

  function toggleLead(id: string) {
    setMentions((prev) =>
      prev.map((m) => (m.id === id ? { ...m, isLead: !m.isLead } : m))
    )
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-card-foreground">
            <MessageSquare className="size-4 text-primary" />
            Лента упоминаний
          </CardTitle>
          <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-xs font-mono">
            {mentions.length} результатов
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        {mentions.map((mention) => (
          <div
            key={mention.id}
            className="group rounded-lg border border-border bg-secondary/50 p-4 transition-colors hover:bg-secondary/80"
          >
            <div className="flex items-start gap-3">
              <Avatar className="mt-0.5 size-10 shrink-0 border border-border">
                <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
                  {mention.groupIcon}
                </AvatarFallback>
              </Avatar>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm text-card-foreground">
                    {mention.groupName}
                  </span>
                  <span className="text-muted-foreground">{'/'}</span>
                  <span className="text-sm text-muted-foreground">
                    {mention.userName}
                  </span>
                  <Badge variant="outline" className="ml-auto border-border text-xs text-muted-foreground font-mono">
                    {mention.timestamp}
                  </Badge>
                </div>

                <p className="mt-2 text-sm leading-relaxed text-secondary-foreground">
                  {highlightKeyword(mention.message, mention.keyword)}
                </p>

                <div className="mt-3 flex items-center gap-2 flex-wrap">
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-0 text-xs">
                    {mention.keyword}
                  </Badge>

                  <div className="ml-auto flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="size-3" />
                      К сообщению
                    </Button>
                    <Button
                      variant={mention.isLead ? "default" : "outline"}
                      size="sm"
                      onClick={() => toggleLead(mention.id)}
                      className={
                        mention.isLead
                          ? "h-7 gap-1.5 text-xs bg-success text-success-foreground hover:bg-success/90"
                          : "h-7 gap-1.5 text-xs border-border text-muted-foreground hover:border-success hover:text-success"
                      }
                    >
                      {mention.isLead ? (
                        <>
                          <Check className="size-3" />
                          Лид сохранён
                        </>
                      ) : (
                        <>
                          <UserPlus className="size-3" />
                          Отметить как лид
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
