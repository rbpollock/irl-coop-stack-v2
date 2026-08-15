import Link from "next/link"
import { useParams } from "next/navigation"

import type { LocaleType } from "@/types"
import type { ChatType } from "../../types"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn, formatDistance, getInitials } from "@/lib/utils"

import { useChatContext } from "../../_hooks/use-chat-context"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { ChatAvatar } from "../chat-avatar"

export function ChatSidebarItem({ chat }: { chat: ChatType }) {
  const { setIsChatSidebarOpen } = useChatContext()
  const params = useParams()

  const chatIdParam = params.id?.[0]
  const locale = params.lang as LocaleType

  const handleOnCLick = () => {
    // Close the sidebar when a chat is selected
    setIsChatSidebarOpen(false)
  }

  return (
    <Link
      href={ensureLocalizedPathname(`/apps/chat/${chat.id}`, locale)}
      prefetch={false}
      className={cn(
        buttonVariants({ variant: "ghost" }),
        chatIdParam === chat.id && "bg-accent", // Highlight the current chat box
        "h-fit w-full"
      )}
      aria-current={chatIdParam === chat.id ? "true" : undefined}
      onClick={handleOnCLick}
    >
      <li className="w-full flex items-center gap-2">
        <ChatAvatar
          src={chat.avatar}
          fallback={getInitials(chat.name)}
          status={chat.status}
          size={1.75}
          className="shrink-0"
        />
        <div className="h-11 w-full grid grid-cols-3 gap-x-4">
          <div className="col-span-2 grid">
            <span className="truncate">{chat.name}</span>
            <span className="text-xs text-muted-foreground font-semibold truncate">
              {chat.lastMessage?.content || "No messages yet..."}
            </span>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className="text-xs text-muted-foreground font-semibold">
              {formatDistance(chat.lastMessage?.createdAt ?? new Date())}
            </span>
            {/* Display unread count if available */}
            {!!chat?.unreadCount && (
              <Badge className="hover:bg-primary">{chat.unreadCount}</Badge>
            )}
          </div>
        </div>
      </li>
    </Link>
  )
}
