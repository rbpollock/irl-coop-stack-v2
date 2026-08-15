"use client"

import { CardFooter } from "@/components/ui/card"
import { ChatBoxFooterActions } from "./chat-box-footer-actions"
import { TextMessageForm } from "./text-message-form"

export function ChatBoxFooter() {
  return (
    <CardFooter className="py-3 border-t border-border">
      <ChatBoxFooterActions />
      <TextMessageForm />
    </CardFooter>
  )
}
