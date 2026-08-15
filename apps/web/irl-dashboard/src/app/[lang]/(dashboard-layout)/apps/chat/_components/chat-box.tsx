"use client"

import { useMemo } from "react"
import { useParams } from "next/navigation"

import type { UserType } from "../types"

import { useChatContext } from "../_hooks/use-chat-context"
import { Card } from "@/components/ui/card"
import { ChatBoxContent } from "./chat-box-content"
import { ChatBoxFooter } from "./chat-box-footer"
import { ChatBoxHeader } from "./chat-box-header"
import { ChatBoxNotFound } from "./chat-box-not-found"

export function ChatBox({ user }: { user: UserType }) {
  const { chatState } = useChatContext()
  const params = useParams()

  const chatIdParam = params.id?.[0] // Get the chat ID from route params

  const chat = useMemo(() => {
    if (chatIdParam) {
      // Find the chat by ID
      return chatState.chats.find((c) => c.id === chatIdParam)
    }

    // Return null if not found
    return null
  }, [chatState.chats, chatIdParam])

  // If chat ID exists but no matching chat is found, show a not found UI
  if (!chat) return <ChatBoxNotFound />

  return (
    <Card className="grow grid">
      <ChatBoxHeader chat={chat} />
      <ChatBoxContent user={user} chat={chat} />
      <ChatBoxFooter />
    </Card>
  )
}
