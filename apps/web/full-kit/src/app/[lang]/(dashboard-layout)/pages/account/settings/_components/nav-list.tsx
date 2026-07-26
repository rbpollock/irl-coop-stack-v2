"use client"

import Link from "next/link"
import { useParams, usePathname } from "next/navigation"

import type { LocaleType } from "@/types"

import { linksData } from "../../_data/nav-list-links"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn } from "@/lib/utils"

export function NavList() {
  const params = useParams()
  const pathname = usePathname()

  const locale = params.lang as LocaleType

  return (
    <nav className="flex flex-wrap gap-4 text-sm text-muted-foreground md:flex-col">
      {linksData.map((link) => {
        const localizedPathname = ensureLocalizedPathname(link.href, locale)

        return (
          <Link
            key={link.title}
            href={localizedPathname}
            className={cn(
              pathname === localizedPathname && "font-semibold text-primary" // Highlight the current page
            )}
            aria-current={pathname === localizedPathname ? "page" : undefined}
          >
            {link.title}
          </Link>
        )
      })}
    </nav>
  )
}
