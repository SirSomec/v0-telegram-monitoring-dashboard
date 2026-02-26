export type ChatGroup = {
  id: number
  name: string
  description: string | null
  userId: number
  createdAt: string
}

export type Chat = {
  id: number
  identifier: string
  title: string | null
  description: string | null
  groupIds: number[]
  enabled: boolean
  userId: number
  isGlobal?: boolean
  isOwner?: boolean
  hasLinkedChat?: boolean
  bundleSize?: number
  createdAt: string
}

export type UserAccount = {
  id: number
  email: string | null
  name: string | null
  isAdmin: boolean
  createdAt: string
  plan: string
  planSlug: string
  planExpiresAt: string | null
}

export type ParserStatus = {
  running: boolean
  multiUser: boolean
  userId: number | null
  maxRunning?: boolean
}

export type ParserSettings = {
  TG_API_ID: string
  TG_API_HASH: string
  TG_SESSION_STRING: string
  TG_SESSION_NAME: string
  TG_BOT_TOKEN: string
  TG_CHATS: string
  TG_PROXY_HOST: string
  TG_PROXY_PORT: string
  TG_PROXY_USER: string
  TG_PROXY_PASS: string
  AUTO_START_SCANNER: string
  MULTI_USER_SCANNER: string
  TG_USER_ID: string
  MAX_ACCESS_TOKEN: string
  MAX_BASE_URL: string
  MAX_POLL_INTERVAL_SEC: string
  AUTO_START_MAX_SCANNER: string
  SEMANTIC_PROVIDER: string
  SEMANTIC_SERVICE_URL: string
  SEMANTIC_MODEL_NAME: string
  SEMANTIC_SIMILARITY_THRESHOLD: string
  MESSAGE_CONCURRENCY: string
  SEMANTIC_EXECUTOR_WORKERS: string
}

export type ParserSettingsUpdate = Partial<{
  TG_API_ID: string
  TG_API_HASH: string
  TG_SESSION_STRING: string
  TG_SESSION_NAME: string
  TG_BOT_TOKEN: string
  TG_CHATS: string
  TG_PROXY_HOST: string
  TG_PROXY_PORT: string
  TG_PROXY_USER: string
  TG_PROXY_PASS: string
  AUTO_START_SCANNER: boolean
  MULTI_USER_SCANNER: boolean
  TG_USER_ID: number
  MAX_ACCESS_TOKEN: string
  MAX_BASE_URL: string
  MAX_POLL_INTERVAL_SEC: number
  AUTO_START_MAX_SCANNER: boolean
  SEMANTIC_PROVIDER: string
  SEMANTIC_SERVICE_URL: string
  SEMANTIC_MODEL_NAME: string
  SEMANTIC_SIMILARITY_THRESHOLD: string
  MESSAGE_CONCURRENCY: number
  SEMANTIC_EXECUTOR_WORKERS: number
}>

export type EmailStatus = {
  configured: boolean
  smtpHost: string
  smtpPort: number
  smtpFrom: string
}

export type ParserChannelDiagnostics = {
  identifier: string
  userId: number | null
  parserRunning: boolean
  parserMode: string
  parserUserId: number | null
  parsedUsername: string | null
  parsedTgChatId: number | null
  parsedInviteHash: string | null
  candidates: string[]
  inActiveFilter: boolean
  activeFilterSize: number
  queueSize: number | null
  queueMax: number | null
  droppedMessages: number | null
  dbMatches: number
  enabledMatches: number
  keywordEnabledCount: number | null
  reasons: string[]
}

