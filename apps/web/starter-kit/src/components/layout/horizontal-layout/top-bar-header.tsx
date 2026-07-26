"use client"

import { CommandMenu } from "@/components/layout/command-menu"
import { TopBarHeaderMenubar } from "./top-bar-header-menubar"

export function TopBarHeader() {
  return (
    <div className="container hidden justify-between items-center py-1 lg:flex">
      <TopBarHeaderMenubar />
      <CommandMenu buttonClassName="h-8" />
    </div>
  )
}
