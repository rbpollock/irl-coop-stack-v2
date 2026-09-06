"use client"

import Link from "next/link"
import { useSession } from "next-auth/react"
import { useState } from "react"
import { ArrowUpRight, Loader2, Search } from "lucide-react"

const COOP_API_URL = process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const DOCS_AREA_ID = process.env.NEXT_PUBLIC_RAG_DOCS_AREA_ID ?? "e418da84-6d62-4b31-aeff-fb2a5cff63d2"
const GROUPS_AREA_ID = process.env.NEXT_PUBLIC_RAG_GROUPS_AREA_ID ?? "ff498932-aae5-449a-a4db-13432cdf7e2b"

type Context = {
  document_id: string
  document_name: string | null
  heading: string | null
  text: string
  source: string
}

function resolveLink(documentName: string | null): { href: string; label: string } | null {
  if (!documentName) return null
  if (documentName.startsWith("group-")) {
    const slug = documentName.slice("group-".length).replace(/\.md$/, "")
    return { href: `/groups/${slug}`, label: "View group" }
  }
  const slug = documentName.replace(/\.md$/, "")
  return { href: `/design/${slug}`, label: "Read more" }
}

function ResultCard({ context: c }: { context: Context }) {
  const link = resolveLink(c.document_name)
  const inner = (
    <>
      {c.heading && <p className="mb-1 text-xs font-semibold text-primary">{c.heading}</p>}
      <p className="text-sm leading-relaxed text-foreground/85">{c.text.slice(0, 300)}</p>
      <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
        {link ? (
          <>
            {link.label} <ArrowUpRight className="size-3" />
          </>
        ) : (
          <>via {c.source}</>
        )}
      </p>
    </>
  )
  if (!link) {
    return <div className="rounded-xl border bg-card p-4">{inner}</div>
  }
  return (
    <Link
      href={link.href}
      className="block rounded-xl border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-accent/40"
    >
      {inner}
    </Link>
  )
}

async function queryArea(token: string | undefined, areaId: string, question: string): Promise<Context[]> {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${COOP_API_URL}/mcp`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: "rag.retrieve_area_contexts", arguments: { area_id: areaId, question } },
    }),
  })
  const data = await res.json()
  const text = data?.result?.content?.[0]?.text
  if (!text) return []
  try {
    return (JSON.parse(text).contexts ?? []) as Context[]
  } catch {
    return []
  }
}

export function DocsSearch({ className = "", prioritizeGroups = false }: { className?: string; prioritizeGroups?: boolean }) {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [contexts, setContexts] = useState<Context[]>([])
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    setLoading(true)
    setError(null)
    setSearched(true)
    setContexts([])
    // Groups first (fast area) — render immediately so the search feels responsive.
    const groupCtx = await queryArea(token, GROUPS_AREA_ID, q).catch(() => [])
    setContexts(groupCtx)
    setLoading(false)
    // Docs (slower — CPU rerank over the full corpus) merge in when ready.
    const docCtx = await queryArea(token, DOCS_AREA_ID, q).catch(() => [])
    setContexts((prev) => [...prev, ...docCtx].slice(0, 8))
  }

  return (
    <div className={`mx-auto w-full max-w-2xl ${className}`}>
      <form onSubmit={onSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search docs, groups and rooms…"
            className="h-11 w-full rounded-xl border bg-background pl-10 pr-3 text-sm shadow-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : "Search"}
        </button>
      </form>

      {loading && (
        <div className="mt-6 flex justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && <p className="mt-4 text-center text-sm text-muted-foreground">{error}</p>}

      {searched && !loading && contexts.length === 0 && !error && (
        <p className="mt-4 text-center text-sm text-muted-foreground">No matching passages.</p>
      )}

      {!loading && contexts.length > 0 && (
        <div className="mt-6 space-y-4">
          {prioritizeGroups ? (
            <>
              {contexts.some((c) => c.document_name?.startsWith("group-")) && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">Groups</h3>
              )}
              <div className="space-y-3">
                {contexts.filter((c) => c.document_name?.startsWith("group-")).map((c, i) => (
                  <ResultCard key={`g-${i}`} context={c} />
                ))}
              </div>
              {contexts.some((c) => !c.document_name?.startsWith("group-")) && (
                <h3 className="pt-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">Docs</h3>
              )}
              <div className="space-y-3">
                {contexts.filter((c) => !c.document_name?.startsWith("group-")).map((c, i) => (
                  <ResultCard key={`d-${i}`} context={c} />
                ))}
              </div>
            </>
          ) : (
            <div className="space-y-3">
              {contexts.map((c, i) => (
                <ResultCard key={i} context={c} />
              ))}
            </div>
          )}
        </div>
      )}

      {!token && (
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Just browsing —{" "}
          <Link href="/sign-in" className="font-semibold text-primary hover:underline">
            sign in
          </Link>{" "}
          to ask follow-ups and see your group&apos;s knowledge.
        </p>
      )}
    </div>
  )
}
