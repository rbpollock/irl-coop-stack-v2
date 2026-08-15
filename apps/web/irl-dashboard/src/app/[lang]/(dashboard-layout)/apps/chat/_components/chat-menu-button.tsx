"use client"

import { Menu } from "lucide-react"

import type { ComponentProps } from "react"

import { useChatContext } from "../_hooks/use-chat-context"
import { Button } from "@/components/ui/button"

interface ChatMenuButtonProps extends ComponentProps<typeof Button> {
  isIcon?: boolean
}

export function ChatMenuButton({
  isIcon = false,
  ...props
}: ChatMenuButtonProps) {
  const { setIsChatSidebarOpen } = useChatContext()

  if (isIcon) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={() => setIsChatSidebarOpen(true)}
        aria-label="Menu"
        {...props}
      >
        <Menu className="h-4 w-4" />
      </Button>
    )
  }

  return (
    <Button
      size="lg"
      className="md:hidden"
      onClick={() => setIsChatSidebarOpen(true)}
      {...props}
    >
      Menu
    </Button>
  )
}
