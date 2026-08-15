"use client"

import { useState } from "react"
import { ListFilter, MoreVertical, SquarePen } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChatSidebarNotificationDropdown } from "./chat-sidebar-notification-dropdown"
import { ChatSidebarStatusDropdown } from "./chat-sidebar-status-dropdown"

export function ChatSidebarActionButtons() {
  const [notifications, setNotifications] = useState<string>("ALL_MESSAGES")
  const [status, setStatus] = useState<string>("ONLINE")

  return (
    <div className="flex gap-1">
      <Button variant="ghost" size="icon" aria-label="New chat or group">
        <SquarePen className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" aria-label="Filter chat list">
        <ListFilter className="h-4 w-4" />
      </Button>

      {/* More Actions Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="More actions">
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-40">
          <ChatSidebarNotificationDropdown
            notifications={notifications}
            setNotifications={setNotifications}
          />
          <ChatSidebarStatusDropdown status={status} setStatus={setStatus} />
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
