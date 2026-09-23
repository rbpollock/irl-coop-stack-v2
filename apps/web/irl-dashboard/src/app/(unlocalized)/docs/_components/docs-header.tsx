import Link from "next/link"

import { ToggleMobileSidebar } from "@/components/layout/toggle-mobile-sidebar"
import { DocsCommandMenu } from "./docs-command-menu"
import { DocsModeDropdown } from "./docs-mode-dropdown"

export function DocsHeader() {
  return (
    <header className="sticky top-0 w-full bg-background z-50 border-b">
      <div className="container flex justify-between items-center gap-2 p-4">
        <Link
          href="/docs"
          className="inline-flex items-center gap-2 text-foreground font-black"
        >
          <span className="grid size-6 place-items-center rounded-md bg-foreground text-background">
            i
          </span>
          <span>irl.coop</span>
        </Link>
        <DocsCommandMenu buttonClassName="ms-auto" />
        <DocsModeDropdown />
        <ToggleMobileSidebar />
      </div>
    </header>
  )
}
