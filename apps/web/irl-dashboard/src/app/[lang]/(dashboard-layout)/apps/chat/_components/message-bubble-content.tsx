import type { ReactNode } from "react"
import type { MessageType } from "../types"

import { cn } from "@/lib/utils"

import { MessageBubbleContentFiles } from "./message-bubble-content-files"
import { MessageBubbleContentImages } from "./message-bubble-content-images"
import { MessageBubbleContentText } from "./message-bubble-content-text"

export function MessageBubbleContent({
  message,
  isByCurrentUser,
}: {
  message: MessageType
  isByCurrentUser: boolean
}) {
  let content: ReactNode

  // Handle different types of message content
  if (message.text) {
    content = <MessageBubbleContentText text={message.text} />
  } else if (message.images) {
    content = <MessageBubbleContentImages images={message.images} />
  } else if (message.files) {
    content = (
      <MessageBubbleContentFiles
        files={message.files}
        isByCurrentUser={isByCurrentUser}
      />
    )
  } else if (message.voiceMessage) {
    content = <audio controls src={message.voiceMessage.url} />
  }

  return (
    <div
      className={cn(
        "text-sm text-accent-foreground bg-accent p-2 space-y-2 rounded-lg break-all",
        isByCurrentUser
          ? "bg-primary text-primary-foreground rounded-se-none"
          : "rounded-ss-none"
      )}
    >
      {content}
    </div>
  )
}
