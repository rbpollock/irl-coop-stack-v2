import { notFound } from "next/navigation"
import Markdown from "react-markdown"
import rehypeSlug from "rehype-slug"
import remarkGfm from "remark-gfm"

import { getDesignDoc, readDesignDoc, readRawMarkdown } from "@/lib/design-docs"

export function generateStaticParams() {
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

  // Render inside the docs layout's mdx-content container
  // (DocsLayout wraps this page with DocsHeader, DocsSidebar, DocsBreadcrumb, DocsPagination, DocsToc)
  return (
    <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}>
      {content}
    </Markdown>
  )
}