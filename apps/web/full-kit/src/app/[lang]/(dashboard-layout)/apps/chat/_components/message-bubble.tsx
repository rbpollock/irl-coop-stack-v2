import { EllipsisVertical } from "lucide-react"

import type { MessageType, UserType } from "../types"

import { cn, formatDistance, getInitials } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChatAvatar } from "./chat-avatar"
import { MessageBubbleContent } from "./message-bubble-content"
import { MessageBubbleStatusIcon } from "./message-bubble-status-icon"

export function MessageBubble({
  sender,
  message,
  isByCurrentUser,
}: {
  sender: UserType
  message: MessageType
  isByCurrentUser: boolean
}) {
  return (
    <li className={cn("flex gap-2", isByCurrentUser && "flex-row-reverse")}>
      <ChatAvatar
        src={sender.avatar}
        fallback={getInitials(sender.name)}
        status={sender.status}
        size={1.75}
        className="shrink-0"
      />
      <div className="flex flex-col gap-1 w-full max-w-[320px]">
        <span
          className={cn(
            "text-sm font-semibold text-foreground",
            isByCurrentUser && "text-end"
          )}
        >
          {sender.name}
        </span>
        <MessageBubbleContent
          message={message}
          isByCurrentUser={isByCurrentUser}
        />
        <div className="flex items-center gap-1">
          <span className="text-sm font-normal text-muted-foreground">
            {formatDistance(message.createdAt)}
          </span>
          {isByCurrentUser && (
            <MessageBubbleStatusIcon status={message.status} />
          )}
        </div>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger className="mt-8" asChild>
          <Button variant="ghost" size="icon" aria-label="More actions">
            <EllipsisVertical className="size-4 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align={isByCurrentUser ? "start" : "end"}>
          <DropdownMenuItem>Edit</DropdownMenuItem>
          <DropdownMenuItem>Reply</DropdownMenuItem>
          <DropdownMenuItem>Forward</DropdownMenuItem>
          <DropdownMenuItem>Copy</DropdownMenuItem>
          <DropdownMenuSeparator />
          {/* Show 'Report' only if the message is not sent by the current user */}
          {!isByCurrentUser && (
            <DropdownMenuItem className="text-destructive focus:text-destructive">
              Report
            </DropdownMenuItem>
          )}
          {/* Show 'Delete' only if the message is sent by the current user */}
          {isByCurrentUser && (
            <DropdownMenuItem className="text-destructive focus:text-destructive">
              Delete
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  )
}
