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
  createdAt: string
}

export type UserAccount = {
  id: number
  email: string | null
  name: string | null
  isAdmin: boolean
  createdAt: string
}

