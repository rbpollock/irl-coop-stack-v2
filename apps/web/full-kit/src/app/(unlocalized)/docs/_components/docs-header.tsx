import Image from "next/image"
import Link from "next/link"

import { ToggleMobileSidebar } from "@/components/layout/toggle-mobile-sidebar"
import { DocsCommandMenu } from "./docs-command-menu"
import { DocsModeDropdown } from "./docs-mode-dropdown"

export function DocsHeader() {
  return (
    <header className="sticky top-0 w-full bg-background z-50 border-b">
      <div className="container flex justify-between items-center gap-2 p-4">
        <Link href="/docs" className="inline-flex text-foreground font-black">
          <Image
            src="/images/icons/shadboard.svg"
            alt=""
            height={24}
            width={24}
            className="dark:invert"
          />
          <span>Shadboard</span>
        </Link>
        <DocsCommandMenu buttonClassName="ms-auto" />
        <DocsModeDropdown />
        <ToggleMobileSidebar />
      </div>
    </header>
  )
}
