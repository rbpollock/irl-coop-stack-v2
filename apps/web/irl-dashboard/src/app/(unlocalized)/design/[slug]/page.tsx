import Link from "next/link"
import { notFound } from "next/navigation"
import Markdown from "react-markdown"
import rehypeSlug from "rehype-slug"
import remarkGfm from "remark-gfm"
import { ArrowLeft } from "lucide-react"

import {
  getCategories,
  getDesignDoc,
  getDesignDocs,
  readDesignDoc,
} from "@/lib/design-docs"
import { cn } from "@/lib/utils"

export function generateStaticParams() {
  return getDesignDocs().map((doc) => ({ slug: doc.slug }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const doc = getDesignDoc(slug)
  return {
    title: {
      absolute: doc ? `${doc.title} — irl.coop` : "Design Docs — irl.coop",
    },
  }
}

export default async function DesignDocPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const doc = getDesignDoc(slug)
  const content = readDesignDoc(slug)
  if (!doc || content == null) notFound()

  const categories = getCategories()

  return (
    <div className="container flex gap-10 py-12">
      <aside className="hidden w-60 shrink-0 lg:block">
        <nav className="sticky top-24 space-y-7">
          {categories.map((category) => (
            <div key={category.name}>
              <p className="mb-2 text-xs font-bold tracking-widest text-muted-foreground uppercase">
                {category.name}
              </p>
              <ul className="space-y-1">
                {category.docs.map((d) => (
                  <li key={d.slug}>
                    <Link
                      href={`/design/${d.slug}`}
                      className={cn(
                        "block rounded-md px-3 py-1.5 text-sm transition-colors",
                        d.slug === slug
                          ? "bg-primary/10 font-semibold text-primary"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      )}
                    >
                      {d.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 flex-1">
        <Link
          href="/design"
          className="mb-8 inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          All design docs
        </Link>
        <article className="prose max-w-3xl prose-headings:font-bold prose-headings:tracking-tight prose-headings:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-a:text-primary prose-pre:bg-muted text-foreground">
          <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
            {content}
          </Markdown>
        </article>
      </div>
    </div>
  )
}
