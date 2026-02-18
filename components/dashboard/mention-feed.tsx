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
    groupName: "Crypto Trading Signals",
    groupIcon: "CT",
    userName: "Alex Petrov",
    userInitials: "AP",
    message: "Looking for a reliable crypto exchange with low fees. Currently exploring different DeFi protocol options for my portfolio.",
    keyword: "crypto exchange",
    timestamp: "2 min ago",
    isLead: false,
  },
  {
    id: "2",
    groupName: "Web3 Developers Hub",
    groupIcon: "W3",
    userName: "Maria Chen",
    userInitials: "MC",
    message: "Anyone hiring for web3 jobs? I have 3 years of Solidity experience and looking for remote opportunities in the ethereum ecosystem.",
    keyword: "web3 jobs",
    timestamp: "8 min ago",
    isLead: true,
  },
  {
    id: "3",
    groupName: "NFT Collectors",
    groupIcon: "NC",
    userName: "Dmitry Volkov",
    userInitials: "DV",
    message: "Just launched our new NFT marketplace on Solana. Lower gas fees and faster transactions compared to ETH-based platforms.",
    keyword: "NFT marketplace",
    timestamp: "15 min ago",
    isLead: false,
  },
  {
    id: "4",
    groupName: "Bitcoin Daily",
    groupIcon: "BD",
    userName: "Sarah Kim",
    userInitials: "SK",
    message: "Bitcoin just broke the 100k resistance level. This bull run is different from 2021. HODLers are being rewarded finally!",
    keyword: "bitcoin",
    timestamp: "23 min ago",
    isLead: false,
  },
  {
    id: "5",
    groupName: "DeFi Innovators",
    groupIcon: "DI",
    userName: "James Wright",
    userInitials: "JW",
    message: "Our new DeFi protocol just launched yield farming with 12% APY. Looking for early adopters and partnership opportunities.",
    keyword: "DeFi protocol",
    timestamp: "31 min ago",
    isLead: false,
  },
  {
    id: "6",
    groupName: "Ethereum Developers",
    groupIcon: "ED",
    userName: "Lena Ivanova",
    userInitials: "LI",
    message: "Post ethereum merge the gas fees have dropped significantly. Great time to deploy new smart contracts on mainnet.",
    keyword: "ethereum merge",
    timestamp: "45 min ago",
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
            Mention Feed
          </CardTitle>
          <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-xs font-mono">
            {mentions.length} results
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
                      Go to Message
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
                          Lead Saved
                        </>
                      ) : (
                        <>
                          <UserPlus className="size-3" />
                          Mark as Lead
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
