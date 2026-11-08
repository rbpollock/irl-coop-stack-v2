import Markdown from "react-markdown"
import rehypeSlug from "rehype-slug"
import remarkGfm from "remark-gfm"

import { getDesignDoc, readDesignDoc, readRawMarkdown } from "@/lib/design-docs"
import { Mermaid } from "@/components/mermaid"

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

export default async function DocPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const content = readDesignDoc(slug) ?? readRawMarkdown(slug)
  if (content == null) notFound()

  // Render inside the DocsLayout's mdx-content container
  // (DocsLayout wraps this page with DocsHeader, DocsSidebar, DocsBreadcrumb, DocsPagination, DocsToc)
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSlug]}
      components={{
        code({ className, children, ...props }) {
          const isMermaid = /language-mermaid/.test(className || "")
          if (isMermaid) {
            const chart = String(children).replace(/\n$/, "")
            return <Mermaid chart={chart} />
          }
          return (
            <code className={className} {...props}>
              {children}
            </code>
          )
        },
      }}
    >
      {content}
    </Markdown>
  )
}