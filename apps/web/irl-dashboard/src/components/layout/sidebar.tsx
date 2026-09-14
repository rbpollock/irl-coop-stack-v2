"use client"

import Link from "next/link"
import { useParams, usePathname } from "next/navigation"
import { ChevronDown } from "lucide-react"

import type { DictionaryType } from "@/lib/get-dictionary"
import type {
  LocaleType,
  NavigationNestedItem,
  NavigationRootItem,
} from "@/types"

import { i18n } from "@/configs/i18n"
import { ensureLocalizedPathname } from "@/lib/i18n"
import {
  getDictionaryValue,
  isActivePathname,
  titleCaseToCamelCase,
} from "@/lib/utils"

import { navigationsData } from "@/data/navigations"
import { useGroups } from "@/hooks/use-groups"
import { Logo } from "./logo"
import { useSettings } from "@/hooks/use-settings"
import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  Sidebar as SidebarWrapper,
  useSidebar,
} from "@/components/ui/sidebar"
import { DynamicIcon } from "@/components/dynamic-icon"
import { CommandMenu } from "./command-menu"

export function Sidebar({ dictionary }: { dictionary: DictionaryType }) {
  const pathname = usePathname()
  const params = useParams()
  const { openMobile, setOpenMobile, isMobile } = useSidebar()
  const { settings } = useSettings()
  const groups = useGroups()

  const locale = params.lang as LocaleType
  const direction = i18n.localeDirection[locale]
  const isRTL = direction === "rtl"
  const isHoizontalAndDesktop = settings.layout === "horizontal" && !isMobile

  // If the layout is horizontal and not on mobile, don't render the sidebar. (We use a menubar for horizontal layout navigation.)
  if (isHoizontalAndDesktop) return null

  const renderMenuItem = (item: NavigationRootItem | NavigationNestedItem) => {
    const titleKey = titleCaseToCamelCase(item.title)
    // Dynamic titles (e.g. plane project names) are not dictionary keys —
    // fall back to the raw title instead of throwing.
    const title =
      titleKey in dictionary.navigation
        ? getDictionaryValue(titleKey, dictionary.navigation)
        : item.title
    const label =
      item.label &&
      (titleCaseToCamelCase(item.label) in dictionary.label
        ? getDictionaryValue(titleCaseToCamelCase(item.label), dictionary.label)
        : item.label)

    // If the item has nested items, render it with a collapsible dropdown.
    if (item.items) {
      return (
        <Collapsible className="group/collapsible">
          <CollapsibleTrigger asChild>
            <SidebarMenuButton className="w-full justify-between [&[data-state=open]>svg]:rotate-180">
              <span className="flex items-center">
                {"iconName" in item && (
                  <DynamicIcon name={item.iconName} className="me-2 h-4 w-4" />
                )}
                <span>{title}</span>
                {"label" in item && (
                  <Badge variant="secondary" className="me-2">
                    {label}
                  </Badge>
                )}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200" />
            </SidebarMenuButton>
          </CollapsibleTrigger>
          <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
            <SidebarMenuSub>
              {item.items.map((subItem: NavigationNestedItem) => (
                <SidebarMenuItem key={subItem.title}>
                  {renderMenuItem(subItem)}
                </SidebarMenuItem>
              ))}
            </SidebarMenuSub>
          </CollapsibleContent>
        </Collapsible>
      )
    }

    // Otherwise, render the item with a link.
    if ("href" in item) {
      const localizedPathname = ensureLocalizedPathname(item.href, locale)
      const isActive = isActivePathname(localizedPathname, pathname)

      return (
        <SidebarMenuButton
          isActive={isActive}
          onClick={() => setOpenMobile(!openMobile)}
          asChild
        >
          <Link href={localizedPathname}>
            {"iconName" in item && (
              <DynamicIcon name={item.iconName} className="h-4 w-4" />
            )}
            <span>{title}</span>
            {"label" in item && <Badge variant="secondary">{label}</Badge>}
          </Link>
        </SidebarMenuButton>
      )
    }
  }

  // The "Surveys" nav item becomes a per-group submenu — clickthrough to each
  // group's Formbricks workspace (forms.irl.coop/?group=<slug>, resolved by the
  // gate-SSO route). Falls back to the plain link until the groups claim loads.
  const navData = navigationsData.map((nav) => ({
    ...nav,
    items: nav.items.map((item) => {
      if (item.title === "Surveys" && groups.length > 0) {
        return {
          title: item.title,
          iconName: item.iconName,
          items: groups.map((g) => ({
            title: g.name,
            href: `https://forms.irl.coop/?group=${g.slug}`,
          })),
        }
      }
      // Same for "Events" — each group has its OWN Hi.Events workspace (account),
      // so the link asks the app's SSR to switch the session to that group before
      // rendering the admin (the ?group= param is consumed and dropped).
      if (item.title === "Events" && groups.length > 0) {
        return {
          title: item.title,
          iconName: item.iconName,
          items: groups.map((g) => ({
            title: g.name,
            href: `https://events.irl.coop/manage/events?group=${g.slug}`,
          })),
        }
      }
      return item
    }),
  }))

  return (
    <SidebarWrapper side={isRTL ? "right" : "left"}>
      <SidebarHeader>
        <Link
          href={ensureLocalizedPathname("/", locale)}
          className="w-fit flex text-foreground font-black p-2 pb-0 mb-2"
          onClick={() => isMobile && setOpenMobile(!openMobile)}
        >
          <Logo className="h-6 text-primary" />
        </Link>
        <CommandMenu dictionary={dictionary} buttonClassName="max-w-full" />
      </SidebarHeader>
      <ScrollArea>
        <SidebarContent className="gap-0">
          {navData.map((nav) => {
            const title = getDictionaryValue(
              titleCaseToCamelCase(nav.title),
              dictionary.navigation
            )

            return (
              <SidebarGroup key={nav.title}>
                <SidebarGroupLabel>{title}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {nav.items.map((item) => (
                      <SidebarMenuItem key={item.title}>
                        {renderMenuItem(item)}
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            )
          })}
        </SidebarContent>
      </ScrollArea>
    </SidebarWrapper>
  )
}
