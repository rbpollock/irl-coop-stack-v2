import Link from "next/link"
import { ArrowRight, BookOpen } from "lucide-react"

import { DocsSearch } from "@/components/docs-search"
import { getCategories, type DocStatus } from "@/lib/design-docs"

export const metadata = {
  title: { absolute: "Design Docs — irl.coop" },
}

const STATUS_STYLE: Record<DocStatus, string> = {
  design: "bg-primary/10 text-primary",
  live: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  vision: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  note: "bg-muted text-muted-foreground",
}

export default function DesignIndexPage() {
  const categories = getCategories()
  return (
    <div className="container py-16">
      <div className="mx-auto mb-14 max-w-2xl text-center">
        <p className="mb-2 text-xs font-bold tracking-widest text-primary">
          DESIGN DOCS
        </p>
        <h1 className="text-4xl font-black tracking-tight md:text-5xl">
          How irl.coop works
        </h1>
        <p className="mt-3 text-muted-foreground">
          The design documents behind the platform — groups, identity, treasury,
          communications, and the event bus that ties them together. Open for
          review.
        </p>
      </div>

      <div className="mb-14">
        <DocsSearch />
      </div>

      <div className="mx-auto mb-10 flex max-w-2xl flex-col items-center gap-3 rounded-xl border bg-muted/40 p-5 text-center">
        <p className="text-sm text-muted-foreground">
          Looking for the consolidated overview? The group model — Safe-as-group,
          the shared pathways, the ZK treasury, and the glossary — is published as
          a standalone document.
        </p>
        <Link
          href="/group-model.html"
          className="inline-flex items-center gap-1 text-sm font-semibold text-primary"
        >
          Read the group model <ArrowRight className="size-3.5" />
        </Link>
      </div>

      {categories.map((category) => (
        <section key={category.name} className="mb-12">
          <h2 className="mb-4 text-xl font-black tracking-tight">
            {category.name}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {category.docs.map((doc) => (
              <Link
                key={doc.slug}
                href={`/design/${doc.slug}`}
                className="group flex flex-col gap-2 rounded-xl border p-5 transition-colors hover:border-primary/50"
              >
                <div className="flex items-center justify-between">
                  <BookOpen className="size-5 text-primary" />
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wider uppercase ${STATUS_STYLE[doc.status]}`}
                  >
                    {doc.status}
                  </span>
                </div>
                <h3 className="text-base font-bold">{doc.title}</h3>
                <p className="text-sm text-muted-foreground">{doc.description}</p>
                <span className="mt-auto inline-flex items-center gap-1 text-sm font-semibold text-primary">
                  Read{" "}
                  <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
