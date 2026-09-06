// llms.txt — machine-readable entry point for agents visiting the bare domain.
// The convention agents check first; points at the catalog, the raw markdown,
// the full corpus, and the knowledge-search MCP.
export function GET() {
  const content = `# irl.coop

> Sovereign cooperative platform — groups, identity, treasury, and knowledge on a self-hosted stack (Keycloak, Safe-as-everything, shared Citus, Matrix, RAG knowledge base).

## Design docs

- [Catalog (JSON)](/design/index.json) — every doc: slug, title, category, status, description
- [Human-readable](/design) — the same docs rendered as HTML
- [Raw markdown](/design/<slug>.md) — any doc as markdown, e.g. /design/irl-coop-group.md
- [Full corpus](/llms-full.txt) — all design docs concatenated into one file

## Knowledge search

- [MCP endpoint](https://api.irl.coop/mcp) — JSON-RPC tools: rag.list_areas, rag.retrieve_area_contexts (cited retrieval over the docs and public group profiles)
`
  return new Response(content, {
    headers: { "Content-Type": "text/markdown; charset=utf-8" },
  })
}
