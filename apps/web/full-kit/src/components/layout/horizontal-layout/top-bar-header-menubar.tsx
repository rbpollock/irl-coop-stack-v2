"use client"

import { Fragment } from "react"
import Link from "next/link"
import { useParams, usePathname } from "next/navigation"

import type { DictionaryType } from "@/lib/get-dictionary"
import type {
  LocaleType,
  NavigationNestedItem,
  NavigationRootItem,
} from "@/types"

import { navigationsData } from "@/data/navigations"

import { ensureLocalizedPathname } from "@/lib/i18n"
import {
  cn,
  getDictionaryValue,
  isActivePathname,
  titleCaseToCamelCase,
} from "@/lib/utils"

import { Badge } from "@/components/ui/badge"
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarSub,
  MenubarSubContent,
  MenubarSubTrigger,
  MenubarTrigger,
} from "@/components/ui/menubar"
import { DynamicIcon } from "@/components/dynamic-icon"

export function TopBarHeaderMenubar({
  dictionary,
}: {
  dictionary: DictionaryType
}) {
  const pathname = usePathname()
  const params = useParams()

  const locale = params.lang as LocaleType

  const renderMenuItem = (item: NavigationRootItem | NavigationNestedItem) => {
    const title = getDictionaryValue(
      titleCaseToCamelCase(item.title),
      dictionary.navigation
    )
    const label =
      item.label &&
      getDictionaryValue(titleCaseToCamelCase(item.label), dictionary.label)

    // If the item has nested items, render it with a MenubarSub.
    if (item.items) {
      return (
        <MenubarSub>
          <MenubarSubTrigger className="gap-2">
            {"iconName" in item && (
              <DynamicIcon name={item.iconName} className="me-2 h-4 w-4" />
            )}
            <span>{title}</span>
            {"label" in item && <Badge variant="secondary">{label}</Badge>}
          </MenubarSubTrigger>
          <MenubarSubContent className="max-h-[90vh] flex flex-col flex-wrap gap-1">
            {item.items.map((subItem: NavigationNestedItem) => {
              return (
                <MenubarItem key={subItem.title} className="p-0">
                  {renderMenuItem(subItem)}
                </MenubarItem>
              )
            })}
          </MenubarSubContent>
        </MenubarSub>
      )
    }

    // Otherwise, render the item with a link.
    if ("href" in item) {
      const localizedPathname = ensureLocalizedPathname(item.href, locale)
      const isActive = isActivePathname(localizedPathname, pathname)

      return (
        <MenubarItem asChild>
          <Link
            href={localizedPathname}
            className={cn("w-full gap-2", isActive && "bg-accent")}
          >
            {"iconName" in item ? (
              <DynamicIcon name={item.iconName} className="h-4 w-4" />
            ) : (
              <DynamicIcon name="Circle" className="h-2 w-2" />
            )}
            <span>{title}</span>
            {"label" in item && <Badge variant="secondary">{label}</Badge>}
          </Link>
        </MenubarItem>
      )
    }
  }

  return (
    <Menubar className="border-0">
      {navigationsData.map((nav) => {
        const title = getDictionaryValue(
          titleCaseToCamelCase(nav.title),
          dictionary.navigation
        )
        return (
          <MenubarMenu key={nav.title}>
            <MenubarTrigger>{title}</MenubarTrigger>
            <MenubarContent className="space-y-1">
              {nav.items.map((item) => (
                <Fragment key={item.title}>{renderMenuItem(item)}</Fragment>
              ))}
            </MenubarContent>
          </MenubarMenu>
        )
      })}
    </Menubar>
  )
}
