import { notFound } from "next/navigation"
import Markdown from "react-markdown"
import rehypeSlug from "rehype-slug"
import remarkGfm from "remark-gfm"

import { getDesignDoc, readDesignDoc, readRawMarkdown } from "@/lib/design-docs"
import { cn } from "@/lib/utils"

export function generateStaticParams() {
  // Lazy-load to avoid importing in client context
  const { getDesignDocs } = require("@/lib/design-docs")
  return getDesignDocs().map((doc: { slug: string }) => ({ slug: doc.slug }))
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
      absolute: doc
        ? `${doc.title} — irl.coop`
        : "Design Docs — irl.coop",
    },
  }
}

export default async function DesignDocPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const content = readDesignDoc(slug) ?? readRawMarkdown(slug)
  if (content == null) notFound()

  return (
    <article
      className={cn(
        "prose max-w-3xl prose-headings:mt-8 prose-headings:font-semibold",
        "prose-headings:text-foreground prose-strong:text-foreground",
        "prose-code:text-foreground prose-a:text-foreground",
        "prose-pre:bg-muted prose-blockquote:text-foreground",
        "prose-em:text-foreground text-foreground",
      )}
    >
      <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
        {content}
      </Markdown>
    </article>
  )
}