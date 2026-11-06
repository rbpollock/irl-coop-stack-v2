import { getDesignDoc, readDesignDoc } from "@/lib/design-docs"

// Raw markdown of a single design doc, for agents. GET /docs/design/raw/<slug>
// (also reachable as /docs/design/<slug>.md via the middleware rewrite).
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params
  const doc = getDesignDoc(slug)
  const content = readDesignDoc(slug)
  if (!doc || !content) {
    return new Response("Not found", { status: 404 })
  }
  return new Response(content, {
    headers: { "Content-Type": "text/markdown; charset=utf-8" },
  })
}