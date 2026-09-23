import Link from "next/link"

import type { ReactNode } from "react"

export default function DesignLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 font-black tracking-tight"
          >
            <span className="grid size-8 place-items-center rounded-lg bg-foreground text-background">
              i
            </span>
            irl.coop
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <Link href="/#apps" className="hover:text-foreground">
              Apps
            </Link>
            <Link href="/#identity" className="hover:text-foreground">
              One identity
            </Link>
            <Link href="/#network" className="hover:text-foreground">
              Groups
            </Link>
            <Link href="/#architecture" className="hover:text-foreground">
              Architecture
            </Link>
            <Link href="/design" className="font-semibold text-foreground">
              Design docs
            </Link>
          </nav>
        </div>
      </header>
      {children}
    </div>
  )
}
