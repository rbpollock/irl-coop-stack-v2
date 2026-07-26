"use client"

import Image from "next/image"
import Link from "next/link"
import { usePathname } from "next/navigation"

import type { NavigationRootItem } from "@/types"

import { sidebarNavigationData } from "../_data/sidebar-navigation"

import { isActivePathname } from "@/lib/utils"

import { Badge } from "@/components/ui/badge"
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
  Sidebar as SidebarWrapper,
  useSidebar,
} from "@/components/ui/sidebar"

export function DocsSidebar() {
  const pathname = usePathname()
  const { openMobile, setOpenMobile, isMobile } = useSidebar()

  return (
    <SidebarWrapper
      className="sticky top-[4.25rem] h-svh border-e border-sidebar-border"
      collapsible="none"
    >
      <SidebarHeader className={openMobile && isMobile ? "" : "hidden"}>
        <Link
          href="/"
          className="w-fit flex text-foreground font-black p-2 pb-0 mb-2"
          onClick={() => isMobile && setOpenMobile(!openMobile)}
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
      </SidebarHeader>
      <ScrollArea className="h-[calc(100svh-4.25rem)]">
        <SidebarContent className="gap-0">
          {sidebarNavigationData.map((nav) => (
            <SidebarGroup key={nav.title}>
              <SidebarGroupLabel>{nav.title}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {nav.items.map((item: NavigationRootItem) => {
                    if (item.href) {
                      const isActive = isActivePathname(item.href, pathname)

                      return (
                        <SidebarMenuItem key={item.title}>
                          <SidebarMenuButton
                            isActive={isActive}
                            onClick={() => setOpenMobile(!openMobile)}
                            asChild
                          >
                            <Link href={item.href}>
                              <span>{item.title}</span>
                              {"label" in item && (
                                <Badge variant="secondary">{item.label}</Badge>
                              )}
                            </Link>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      )
                    }
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>
      </ScrollArea>
    </SidebarWrapper>
  )
}
