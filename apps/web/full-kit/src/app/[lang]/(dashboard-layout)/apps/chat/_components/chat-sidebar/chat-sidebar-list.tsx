"use client"

import { cn } from "@/lib/utils"

import { useChatContext } from "../../_hooks/use-chat-context"
import { useSettings } from "@/hooks/use-settings"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ChatSidebarItem } from "./chat-sidebar-item"

export function ChatSidebarList() {
  const { chatState } = useChatContext()
  const { settings } = useSettings()

  const layout = settings.layout

  const chats = chatState.chats

  return (
    <ScrollArea
      className={cn(
        "h-[calc(100vh-5.5rem)] md:h-[calc(100vh-12.5rem)]",
        layout === "horizontal" && "md:h-[calc(100vh-15.825rem)]"
      )}
    >
      <ul className="p-3 space-y-1.5">
        {chats.map((chat) => {
          return <ChatSidebarItem key={chat.id} chat={chat} />
        })}
      </ul>
    </ScrollArea>
  )
}
