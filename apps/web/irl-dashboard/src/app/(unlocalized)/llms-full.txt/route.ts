import { getDesignDocs, readDesignDoc } from "@/lib/design-docs"

// llms-full.txt — every design doc concatenated into one markdown file, for
// agents that want the whole corpus in a single fetch.
export function GET() {
  const parts: string[] = ["# irl.coop — design docs (full corpus)\n"]
  for (const doc of getDesignDocs()) {
    const content = readDesignDoc(doc.slug)
    if (content == null) continue
    parts.push(`\n\n---\n\n${content}\n`)
  }
  return new Response(parts.join("\n"), {
    headers: { "Content-Type": "text/markdown; charset=utf-8" },
  })
}
