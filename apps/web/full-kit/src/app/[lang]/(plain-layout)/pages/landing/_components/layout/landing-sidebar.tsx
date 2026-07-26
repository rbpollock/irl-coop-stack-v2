"use client"

import Image from "next/image"
import Link from "next/link"
import { useParams } from "next/navigation"
import { LogIn, PanelLeft } from "lucide-react"

import type { LocaleType } from "@/types"

import { headerNavigationData } from "../../_data/header-navigation"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { isActivePathname } from "@/lib/utils"

import { Button, buttonVariants } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import {
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export function LandingSidebar({ fullPathname }: { fullPathname: string }) {
  const { openMobile, setOpenMobile, isMobile } = useSidebar()
  const params = useParams()

  const locale = params.lang as LocaleType

  if (!isMobile) return

  return (
    <Sheet open={openMobile} onOpenChange={setOpenMobile}>
      <SheetTrigger asChild>
        <Button
          data-sidebar="trigger"
          variant="ghost"
          size="icon"
          onClick={() => setOpenMobile(!openMobile)}
          aria-label="Toggle Sidebar"
        >
          <PanelLeft className="h-4 w-4" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="p-0" aria-describedby={undefined}>
        <SheetHeader>
          <SheetTitle className="sr-only">Navigation Sidebar</SheetTitle>
          <SidebarHeader>
            <Link
              href="/"
              className="w-fit flex text-foreground font-black p-2 pb-0 mb-2 hover:text-primary/90"
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
            <Link
              href={ensureLocalizedPathname("/register", locale)}
              className={buttonVariants({ size: "lg" })}
            >
              <LogIn className="me-2 h-4 w-4" />
              <span>Register</span>
            </Link>
          </SidebarHeader>
        </SheetHeader>
        <ScrollArea className="p-2">
          <SidebarContent>
            <SidebarMenu>
              {headerNavigationData.map((nav) => {
                const isActive = isActivePathname(nav.href, fullPathname, true)

                if (nav.href) {
                  return (
                    <SidebarMenuItem key={nav.label}>
                      <SidebarMenuButton
                        isActive={isActive}
                        onClick={() => setOpenMobile(!openMobile)}
                        asChild
                      >
                        <Link href={nav.href}>
                          <span>{nav.label}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                }
              })}
            </SidebarMenu>
          </SidebarContent>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
