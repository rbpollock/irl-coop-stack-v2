"use client"

import type { ChatType, UserType } from "../types"

import { CardContent } from "@/components/ui/card"
import { ChatBoxContentList } from "./chat-box-content-list"

export function ChatBoxContent({
  user,
  chat,
}: {
  user: UserType
  chat: ChatType
}) {
  return (
    <CardContent className="p-0">
      <ChatBoxContentList user={user} chat={chat} />
    </CardContent>
  )
}
