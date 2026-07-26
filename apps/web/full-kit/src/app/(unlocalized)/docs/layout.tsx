import type { Metadata } from "next"
import type { ReactNode } from "react"

import { DocsBreadcrumb } from "./_components/docs-breadcrumb"
import { DocsHeader } from "./_components/docs-header"
import { DocsPagination } from "./_components/docs-pagination"
import { DocsSidebar } from "./_components/docs-sidebar"
import { DocsToc } from "./_components/docs-toc"
import { Footer } from "@/components/layout/footer"

// Define metadata for the application
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Documentation",
}

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="w-screen">
      <DocsHeader />
      <div className="relative grid lg:grid-cols-[auto_1fr_auto]">
        <DocsSidebar />
        <main className="grid bg-muted/40">
          <div className="justify-self-center p-4 z-10">
            <DocsBreadcrumb />
            <div
              id="mdx-content"
              className="min-h-[calc(100svh-16rem)] max-w-prose w-[calc(100vw-3.2rem)] prose prose-headings:mt-8 prose-headings:font-semibold prose-headings:text-foreground prose-h1:text-5xl prose-h2:text-4xl prose-h3:text-3xl prose-h4:text-2xl prose-h5:text-xl prose-h6:text-lg prose-strong:text-foreground prose-code:text-foreground prose-a:text-foreground prose-pre:bg-muted text-foreground"
            >
              {children}
            </div>
            <DocsPagination />
          </div>
        </main>
        <DocsToc />
      </div>
      <Footer />
    </div>
  )
}
