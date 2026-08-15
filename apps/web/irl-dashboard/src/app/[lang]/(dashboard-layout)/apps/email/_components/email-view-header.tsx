"use client"

import type { EmailType } from "../types"

import { CardHeader, CardTitle } from "@/components/ui/card"
import { EmailMenuButton } from "./email-menu-button"

export function EmailViewHeader({ email }: { email: EmailType }) {
  return (
    <CardHeader className="flex-row items-center gap-x-1.5 space-y-0 border-b">
      <div className="flex items-center gap-1.5">
        <EmailMenuButton isIcon />
        <CardTitle className="line-clamp-2 break-all">
          {email.subject}
        </CardTitle>
      </div>
    </CardHeader>
  )
}
