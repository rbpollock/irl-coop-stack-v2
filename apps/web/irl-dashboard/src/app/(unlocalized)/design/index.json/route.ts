import { getCategories, getDesignDocs } from "@/lib/design-docs"

// Machine-readable catalog of the design docs, for agents: the full list plus
// the category grouping. GET /design/index.json
export function GET() {
  return Response.json({
    docs: getDesignDocs(),
    categories: getCategories(),
  })
}
