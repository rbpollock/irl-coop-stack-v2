"use client"

import { Menu } from "lucide-react"

import type { ComponentProps } from "react"

import { useEmailContext } from "../_hooks/use-email-context"
import { Button } from "@/components/ui/button"

interface EmailMenuButtonProps extends ComponentProps<typeof Button> {
  isIcon?: boolean
}

export function EmailMenuButton({
  isIcon = false,
  ...props
}: EmailMenuButtonProps) {
  const { setIsEmailSidebarOpen } = useEmailContext()

  if (isIcon) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={() => setIsEmailSidebarOpen(true)}
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
      onClick={() => setIsEmailSidebarOpen(true)}
      {...props}
    >
      Menu
    </Button>
  )
}
