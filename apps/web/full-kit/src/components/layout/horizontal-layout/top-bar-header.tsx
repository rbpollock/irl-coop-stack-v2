"use client"

import type { DictionaryType } from "@/lib/get-dictionary"

import { CommandMenu } from "@/components/layout/command-menu"
import { TopBarHeaderMenubar } from "./top-bar-header-menubar"

export function TopBarHeader({ dictionary }: { dictionary: DictionaryType }) {
  return (
    <div className="container hidden justify-between items-center py-1 lg:flex">
      <TopBarHeaderMenubar dictionary={dictionary} />
      <CommandMenu dictionary={dictionary} buttonClassName="h-8" />
    </div>
  )
}
