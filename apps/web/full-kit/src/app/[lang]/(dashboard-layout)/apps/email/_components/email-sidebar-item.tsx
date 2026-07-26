"use client"

import Link from "next/link"

import type { LocaleType } from "@/types"
import type { ParamValue } from "next/dist/server/request/params"
import type { EmailSidebarItemType } from "../types"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn, formatUnreadCount } from "@/lib/utils"

import { useEmailContext } from "../_hooks/use-email-context"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { DynamicIcon } from "@/components/dynamic-icon"

interface EmailSidebarItemProps {
  item: EmailSidebarItemType
  segmentParam: ParamValue
  locale: LocaleType
}

export function EmailSidebarItem({
  item,
  segmentParam,
  locale,
}: EmailSidebarItemProps) {
  const { setIsEmailSidebarOpen } = useEmailContext()

  const unreadCount = formatUnreadCount(item.unreadCount)

  return (
    <li>
      <Link
        href={ensureLocalizedPathname("/apps/email/" + item.name, locale)}
        className={cn(
          buttonVariants({ variant: "ghost" }),
          "w-full justify-start",
          segmentParam === item.name && "bg-accent" // Highlight the current email view
        )}
        onClick={() => setIsEmailSidebarOpen(false)}
        aria-current={segmentParam === item.name ? "true" : undefined}
      >
        <DynamicIcon name={item.iconName} className="me-2 h-4 w-4" />
        <span className="capitalize">{item.name}</span>
        {/* Display the badge only if there is an unread count */}
        {!!unreadCount && <Badge className="ms-auto">{unreadCount}</Badge>}
      </Link>
    </li>
  )
}
