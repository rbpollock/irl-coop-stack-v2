import type { ChatType } from "../types"

import { getInitials } from "@/lib/utils"

import { CardTitle } from "@/components/ui/card"
import { ChatAvatar } from "./chat-avatar"

export function ChatHeaderInfo({ chat }: { chat: ChatType }) {
  return (
    <>
      <ChatAvatar
        src={chat.avatar}
        fallback={getInitials(chat.name)}
        status={chat.status}
        size={2}
      />
      <CardTitle>{chat.name}</CardTitle>
    </>
  )
}
