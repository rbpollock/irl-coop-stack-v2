"use client"

import Link from "next/link"
import { useParams } from "next/navigation"

import type { LocaleType } from "@/types"

import { ensureLocalizedPathname } from "@/lib/i18n"

import { useEmailContext } from "../_hooks/use-email-context"
import { Button } from "@/components/ui/button"

export function EmailSidebarHeader() {
  const { setIsEmailSidebarOpen } = useEmailContext()
  const params = useParams()

  const locale = params.lang as LocaleType

  return (
    <div className="p-3">
      <Button className="w-full" size="lg" asChild>
        <Link
          href={ensureLocalizedPathname("/apps/email/compose", locale)}
          onClick={() => setIsEmailSidebarOpen(false)}
        >
          Compose
        </Link>
      </Button>
    </div>
  )
}
