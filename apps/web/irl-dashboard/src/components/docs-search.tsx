"use client"

import Link from "next/link"
import { useSession } from "next-auth/react"
import { useState } from "react"
import { ArrowUpRight, Loader2, Search } from "lucide-react"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
// The coop-wide public knowledge area (the design docs), queryable by anyone.
const DOCS_AREA_ID =
  process.env.NEXT_PUBLIC_RAG_DOCS_AREA_ID ??
  "e418da84-6d62-4b31-aeff-fb2a5cff63d2"

type Context = {
  document_id: string
  document_name: string | null
  heading: string | null
  text: string
  source: string
}

// file name → design-doc slug, so a result can link to its source doc.
export function DocsSearch({ docs }: { docs: Record<string, string> }) {
  const { data: session } = useSession()
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [contexts, setContexts] = useState<Context[]>([])
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const token = session?.accessToken as string | undefined

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    setLoading(true)
    setError(null)
    setSearched(true)
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (token) headers.Authorization = `Bearer ${token}`
      const res = await fetch(`${COOP_API_URL}/mcp`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "tools/call",
          params: {
            name: "rag.retrieve_area_contexts",
            arguments: { area_id: DOCS_AREA_ID, question: q },
          },
        }),
      })
      const data = await res.json()
      const text = data?.result?.content?.[0]?.text
      if (!text) {
        setError(data?.error?.message ?? "No matches found.")
        setContexts([])
      } else {
        setContexts((JSON.parse(text).contexts ?? []).slice(0, 6))
      }
    } catch {
      setError("Search failed — try again.")
      setContexts([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <form onSubmit={onSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask the docs — e.g. “how does a group Safe work?”"
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
        <div className="mt-8 flex justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && <p className="mt-4 text-center text-sm text-muted-foreground">{error}</p>}

      {searched && !loading && contexts.length === 0 && !error && (
        <p className="mt-4 text-center text-sm text-muted-foreground">No matching passages.</p>
      )}

      {!loading && contexts.length > 0 && (
        <div className="mt-6 space-y-3">
          {contexts.map((c, i) => {
            const slug = c.document_name ? docs[c.document_name] : undefined
            const card = (
              <div className="group rounded-xl border bg-card p-4 transition-colors hover:border-primary/50">
                {c.heading && (
                  <p className="mb-1 text-xs font-semibold text-primary">{c.heading}</p>
                )}
                <p className="text-sm leading-relaxed text-foreground/85">
                  {c.text.slice(0, 420)}
                </p>
                <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
                  via {c.source}
                  {slug && (
                    <>
                      <span aria-hidden>·</span>
                      <span className="inline-flex items-center gap-0.5 font-medium text-primary group-hover:underline">
                        Read more <ArrowUpRight className="size-3" />
                      </span>
                    </>
                  )}
                </p>
              </div>
            )
            return slug ? (
              <Link key={i} href={`/design/${slug}`} className="block">
                {card}
              </Link>
            ) : (
              <div key={i}>{card}</div>
            )
          })}
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
