"use client"

import { useMedia } from "react-use"

import { useChatContext } from "../../_hooks/use-chat-context"
import { Card } from "@/components/ui/card"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { ChatSidebarHeader } from "./chat-sidebar-header"
import { ChatSidebarList } from "./chat-sidebar-list"

export function ChatSidebar() {
  const { isChatSidebarOpen, setIsChatSidebarOpen } = useChatContext()
  const isMediumOrSmaller = useMedia("(max-width: 767px)")

  // Content to display in the chat sidebar
  const content = (
    <div className="md:w-72">
      <ChatSidebarHeader />
      <ChatSidebarList />
    </div>
  )

  // Render a persistent sidebar for larger screens
  if (!isMediumOrSmaller) {
    return (
      <aside>
        <Card>{content}</Card>
      </aside>
    )
  }

  // Render a sheet sidebar for smaller screens
  return (
    <Sheet open={isChatSidebarOpen} onOpenChange={setIsChatSidebarOpen}>
      <SheetContent side="start" className="p-0">
        <SheetHeader className="sr-only">
          <SheetTitle>Chat Sidebar</SheetTitle>
          <SheetDescription>
            Access your recent chats and conversations here. Use this panel to
            navigate or start a new chat.
          </SheetDescription>
        </SheetHeader>
        {content}
      </SheetContent>
    </Sheet>
  )
}
