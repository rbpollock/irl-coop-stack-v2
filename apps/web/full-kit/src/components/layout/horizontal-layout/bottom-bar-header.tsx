"use client"

import Image from "next/image"
import Link from "next/link"
import { useParams } from "next/navigation"

import type { DictionaryType } from "@/lib/get-dictionary"
import type { LocaleType } from "@/types"

import { ensureLocalizedPathname } from "@/lib/i18n"

import { LanguageDropdown } from "@/components/language-dropdown"
import { FullscreenToggle } from "@/components/layout/full-screen-toggle"
import { NotificationDropdown } from "@/components/layout/notification-dropdown"
import { UserDropdown } from "@/components/layout/user-dropdown"
import { ModeDropdown } from "@/components/mode-dropdown"
import { ToggleMobileSidebar } from "../toggle-mobile-sidebar"

export function BottomBarHeader({
  dictionary,
}: {
  dictionary: DictionaryType
}) {
  const params = useParams()
  const locale = params.lang as LocaleType

  return (
    <div className="container flex h-14 justify-between items-center gap-4">
      <ToggleMobileSidebar />
      <Link
        href={ensureLocalizedPathname("/", locale)}
        className="hidden text-foreground font-black lg:flex"
      >
        <Image
          src="/images/icons/shadboard.svg"
          alt=""
          height={24}
          width={24}
          className="dark:invert"
        />
        <span>Shadboard</span>
      </Link>
      <div className="flex gap-2">
        <NotificationDropdown dictionary={dictionary} />
        <FullscreenToggle />
        <ModeDropdown dictionary={dictionary} />
        <LanguageDropdown dictionary={dictionary} />
        <UserDropdown dictionary={dictionary} locale={locale} />
      </div>
    </div>
  )
}
