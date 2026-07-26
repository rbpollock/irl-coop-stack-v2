"use client"

import type { EmailType } from "../types"

import { CardContent } from "@/components/ui/card"
import { EmailViewContentActions } from "./email-view-content-actions"
import { EmailViewContentBody } from "./email-view-content-body"
import { EmailViewContentFooter } from "./email-view-content-footer"
import { EmailViewContentHeader } from "./email-view-content-header"

export function EmailViewContent({ email }: { email: EmailType }) {
  return (
    <CardContent className="p-3 space-y-3 overflow-hidden">
      <EmailViewContentActions />
      <EmailViewContentHeader email={email} />
      <EmailViewContentBody email={email} />
      <EmailViewContentFooter />
    </CardContent>
  )
}
