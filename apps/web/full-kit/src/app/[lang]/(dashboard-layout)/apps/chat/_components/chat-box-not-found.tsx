import { MessageCircleX } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { ChatMenuButton } from "./chat-menu-button"

export function ChatBoxNotFound() {
  return (
    <Card className="grow h-[calc(100vh-8.78rem)] md:h-auto">
      <CardContent className="size-full flex flex-col justify-center items-center gap-2 p-0">
        <MessageCircleX className="size-24 text-primary/50" />
        <p className="text-muted-foreground">
          No chat found. Please select an existing chat or start a new
          conversation.
        </p>
        <ChatMenuButton />
      </CardContent>
    </Card>
  )
}
