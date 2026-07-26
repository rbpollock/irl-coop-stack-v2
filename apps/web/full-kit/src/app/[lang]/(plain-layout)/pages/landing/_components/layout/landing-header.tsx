"use client"

import { useEffect, useState } from "react"
import Image from "next/image"
import Link from "next/link"
import { useParams, usePathname } from "next/navigation"
import { LogIn } from "lucide-react"

import type { DictionaryType } from "@/lib/get-dictionary"
import type { LocaleType } from "@/types"

import { headerNavigationData } from "../../_data/header-navigation"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn, isActivePathname } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"
import { LanguageDropdown } from "@/components/language-dropdown"
import { ModeDropdown } from "@/components/mode-dropdown"
import { LandingSidebar } from "./landing-sidebar"

export function LandingHeader({ dictionary }: { dictionary: DictionaryType }) {
  const pathname = usePathname()
  const params = useParams()
  const [fullPathname, setFullPathname] = useState("")

  const locale = params.lang as LocaleType

  useEffect(() => {
    setFullPathname(pathname + window.location.hash)
  }, [params, pathname])

  return (
    <header className="sticky top-0 z-50 w-full bg-background border-b border-sidebar-border">
      <div className="container grid grid-cols-3 items-center gap-2 py-2.5">
        <LandingSidebar fullPathname={fullPathname} />
        <Link
          href="/"
          className="place-self-center w-fit flex text-foreground font-black hover:text-primary/90 lg:place-self-auto"
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
        <nav className="hidden lg:block">
          <ul className="place-self-center flex gap-2">
            {headerNavigationData.map((nav) => {
              const isActive = isActivePathname(nav.href, fullPathname, true)
              return (
                <li key={nav.href}>
                  <Link
                    href={nav.href}
                    className={buttonVariants({
                      variant: isActive ? "secondary" : "ghost",
                    })}
                  >
                    {nav.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
        <div className="place-self-end flex gap-x-2">
          <ModeDropdown dictionary={dictionary} />
          <LanguageDropdown dictionary={dictionary} />
          <Link
            href={ensureLocalizedPathname("/register", locale)}
            className={cn(buttonVariants(), "hidden lg:flex")}
          >
            <LogIn className="me-2 h-4 w-4" />
            <span>Register</span>
          </Link>
        </div>
      </div>
    </header>
  )
}
