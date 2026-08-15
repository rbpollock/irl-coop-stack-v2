"use client"

import { useEffect, useMemo, useRef } from "react"
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area"

import type { ChatType, UserType } from "../types"

import { cn } from "@/lib/utils"

import { useChatContext } from "../_hooks/use-chat-context"
import { useSettings } from "@/hooks/use-settings"
import { ScrollBar } from "@/components/ui/scroll-area"
import { MessageBubble } from "./message-bubble"

export function ChatBoxContentList({
  user,
  chat,
}: {
  user: UserType
  chat: ChatType
}) {
  const { chatState, handleSelectChat, handleSetUnreadCount } = useChatContext()
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const { settings } = useSettings()

  // Synchronize chat selection and scroll to the bottom on updates
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }

    if (chat && chat !== chatState.selectedChat) {
      handleSelectChat(chat)
    }

    if (!!chat?.unreadCount) {
      handleSetUnreadCount()
    }
  }, [chat, chatState.selectedChat, handleSelectChat, handleSetUnreadCount])

  // A map of chat users for quick lookup
  const userMap = useMemo(
    () => new Map(chat?.users.map((user) => [user.id, user])),
    [chat?.users]
  )

  return (
    <ScrollAreaPrimitive.Root
      className={cn(
        "relative h-[calc(100vh-16.5rem)]",
        settings.layout === "horizontal" && "md:h-[calc(100vh-20rem)]"
      )}
    >
      <ScrollAreaPrimitive.Viewport
        ref={scrollAreaRef}
        className="h-full w-full"
      >
        <ul className="flex flex-col-reverse gap-y-1.5 px-6 py-3">
          {chat.messages.map((message) => {
            const sender = userMap.get(message.senderId) as UserType
            const isByCurrentUser = message.senderId === user.id

            return (
              <MessageBubble
                key={message.id}
                sender={sender}
                message={message}
                isByCurrentUser={isByCurrentUser}
              />
            )
          })}
        </ul>
      </ScrollAreaPrimitive.Viewport>
      <ScrollBar orientation="vertical" />
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  )
}
