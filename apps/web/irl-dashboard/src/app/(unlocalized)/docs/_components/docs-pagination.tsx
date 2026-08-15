"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import type { DocNav } from "../types"

import { sidebarNavigationData } from "../_data/sidebar-navigation"

import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"

function flattenSidebarNavigation(navs: DocNav[]): DocNav[] {
  return navs.flatMap(({ items, ...rest }) => {
    if (items) {
      return rest.href
        ? [rest, ...flattenSidebarNavigation(items)]
        : flattenSidebarNavigation(items)
    }
    return rest.href ? [rest] : []
  })
}

function getPreviousNext(pathname: string, navs: DocNav[]) {
  const index = navs.findIndex((section) => section.href === pathname)
  return {
    previous: navs[index - 1] || null,
    next: navs[index + 1] || null,
  }
}

export function DocsPagination() {
  const pathname = usePathname()
  const navs = flattenSidebarNavigation(sidebarNavigationData)
  const { previous, next } = getPreviousNext(pathname, navs)

  return (
    <article className="grid grid-cols-2 gap-4 mt-16">
      {previous && (
        <Link
          className={cn(
            buttonVariants({ variant: "outline" }),
            "w-full flex flex-col items-start gap-1 px-4 py-16 no-underline"
          )}
          href={previous.href as string}
        >
          <div className="flex items-center gap-1 text-muted-foreground">
            <ChevronLeftIcon
              className="h-3.5 w-3.5 rtl:-scale-x-100"
              aria-hidden
            />
            <span className="me-px">Previous</span>
          </div>
          <span className="text-xl font-semibold ms-1">{previous.title}</span>
        </Link>
      )}
      {next && (
        <Link
          className={cn(
            buttonVariants({ variant: "outline" }),
            "col-start-2 w-full flex flex-col items-end gap-1 px-4 py-16 no-underline"
          )}
          href={next.href as string}
        >
          <div className="flex items-center gap-1 text-muted-foreground">
            <span className="me-px">Next</span>
            <ChevronRightIcon
              className="h-3.5 w-3.5 rtl:-scale-x-100"
              aria-hidden
            />
          </div>
          <span className="text-xl font-semibold me-1">{next.title}</span>
        </Link>
      )}
    </article>
  )
}
