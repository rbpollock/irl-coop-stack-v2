"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import GitHubSlugger from "github-slugger"
import { useSession } from "next-auth/react"
import { ArrowUpRight, Loader2, Search } from "lucide-react"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const DOCS_AREA_ID =
  process.env.NEXT_PUBLIC_RAG_DOCS_AREA_ID ??
  "e418da84-6d62-4b31-aeff-fb2a5cff63d2"
const GROUPS_AREA_ID =
  process.env.NEXT_PUBLIC_RAG_GROUPS_AREA_ID ??
  "ff498932-aae5-449a-a4db-13432cdf7e2b"

type Context = {
  document_id: string
  document_name: string | null
  heading: string | null
  text: string
  source: string
  /** Reranker relevance (sigmoid, 0..1) when the cross-encoder scored it. */
  score?: number | null
  /** Which signal `score` came from: "rerank" or "rrf". Never mix the scales. */
  score_kind?: string | null
  /** 1-based rank of the best child merged into this passage. */
  score_rank?: number | null
  /**
   * Which area this passage came from. The client knows this because it queries
   * the two areas separately, and it must not be guessed from the file name:
   * design docs are also named `group-*.md`, which previously sent them to
   * /groups/<slug> (a gated page) and filed them under the Groups heading.
   */
  area?: "groups" | "docs"
}

function resolveLink(c: Context): { href: string; label: string } | null {
  const documentName = c.document_name
  if (!documentName) return null
  if (c.area === "groups") {
    const slug = documentName.replace(/^group-/, "").replace(/\.md$/, "")
    return { href: `/groups/${slug}`, label: "View group" }
  }
  const slug = documentName.replace(/\.md$/, "")
  // Anchor to the exact section shown. The corpus heading is a PATH
  // ("Doc Title / 2. Settled principles"), but the page emits ids for the
  // section heading alone ("2-settled-principles-..."), so anchor on the last
  // segment. A fresh slugger per heading: a shared one accumulates, so the
  // SECOND document with a heading like "1. Principles" would anchor to
  // "1-principles-1".
  const section = c.heading
    ? c.heading
        .split("/")
        .map((part) => part.trim())
        .filter(Boolean)
        .pop() ?? c.heading
    : null
  const href = section
    ? `/design/${slug}#${new GitHubSlugger().slug(section)}`
    : `/design/${slug}`
  return { href, label: section ? "Jump to section" : "Read more" }
}

/** Stable identity for a passage, so the same section never fills two slots. */
function contextKey(c: Context): string {
  return `${c.document_name ?? ""}|${c.heading ?? ""}|${c.text.slice(0, 80)}`
}

function dedupe(list: Context[]): Context[] {
  const seen = new Set<string>()
  return list.filter((c) => {
    const key = contextKey(c)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function isGroupContext(c: Context): boolean {
  return c.area === "groups"
}

/** Words that carry no retrieval signal, so highlighting them is noise. */
const STOP_WORDS = new Set([
  "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
  "was", "were", "be", "been", "do", "does", "did", "how", "what", "when",
  "where", "which", "who", "why", "that", "this", "these", "those", "it",
  "its", "as", "at", "by", "from", "with", "without", "into", "can", "could",
  "should", "would", "my", "our", "your", "their", "his", "her", "them", "they",
  "we", "you", "us", "him", "she", "if", "not",
  "no", "any", "all", "each", "there", "here", "than", "then", "so", "but",
  "about", "over", "under", "between", "get", "got", "make", "made",
  "also", "some", "such", "more", "most", "other", "others", "many", "much",
  "very", "just", "only", "same", "own", "after", "before", "during", "while",
  "because", "another", "every", "either", "neither", "both", "being", "been",
])

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

/**
 * Query words worth looking for in a passage. A trailing suffix is tolerated so
 * "secret" also lights up "secrets"/"secretly" — the corpus is prose, and exact
 * singular matches alone would miss most of the evidence.
 */
function queryTerms(query: string): string[] {
  const words = query.toLowerCase().match(/[a-z0-9]{3,}/g) ?? []
  return [...new Set(words)].filter((w) => !STOP_WORDS.has(w))
}

function matchPattern(terms: string[]): RegExp | null {
  if (terms.length === 0) return null
  const alternation = terms
    .slice()
    .sort((a, b) => b.length - a.length)
    .map(escapeRegExp)
    .join("|")
  return new RegExp(`\\b(?:${alternation})[a-z]{0,2}\\b`, "gi")
}

function countMatches(text: string, pattern: RegExp): number {
  return [...text.matchAll(new RegExp(pattern.source, "gi"))].length
}

/**
 * How good a window is as evidence: how many DIFFERENT query terms it contains
 * first, total occurrences second. Ranking by total occurrences alone let a
 * link-heavy preamble ("Builds on: … secret … secret …") outscore the actual
 * paragraph answering the question, which repeatedly won because one word
 * recurred.
 */
function windowScore(
  text: string,
  terms: string[]
): { distinct: number; total: number } {
  let distinct = 0
  let total = 0
  for (const term of terms) {
    const occurrences = countMatches(
      text,
      new RegExp(`\\b${escapeRegExp(term)}[a-z]{0,2}\\b`, "gi")
    )
    if (occurrences > 0) {
      distinct += 1
      total += occurrences
    }
  }
  return { distinct, total }
}

const SNIPPET_CHARS = 320
const SNIPPET_LEAD = 90

/**
 * Choose the window of a passage to show. The first N characters of a design
 * doc are usually a status header ("Status: design. Author: …") with none of
 * the answer in them, so center the snippet on the densest cluster of matched
 * terms instead and trim to word boundaries.
 */
function bestWindow(
  text: string,
  pattern: RegExp | null,
  terms: string[]
): { body: string; head: boolean; tail: boolean } {
  if (text.length <= SNIPPET_CHARS) return { body: text, head: false, tail: false }
  if (!pattern) return { body: text.slice(0, SNIPPET_CHARS), head: false, tail: true }

  const hits = [...text.matchAll(new RegExp(pattern.source, "gi"))].map(
    (m) => m.index ?? 0
  )
  if (hits.length === 0) {
    return { body: text.slice(0, SNIPPET_CHARS), head: false, tail: true }
  }

  let start = 0
  let best = { distinct: -1, total: -1 }
  for (const hit of hits) {
    let candidate = Math.max(0, hit - SNIPPET_LEAD)
    if (candidate > 0) {
      const space = text.lastIndexOf(" ", candidate)
      if (space > candidate - 40) candidate = space + 1
    }
    const score = windowScore(text.slice(candidate, candidate + SNIPPET_CHARS), terms)
    if (
      score.distinct > best.distinct ||
      (score.distinct === best.distinct && score.total > best.total)
    ) {
      best = score
      start = candidate
    }
  }

  let end = Math.min(text.length, start + SNIPPET_CHARS)
  if (end < text.length) {
    const space = text.lastIndexOf(" ", end)
    if (space > start + SNIPPET_CHARS - 40) end = space
  }
  return { body: text.slice(start, end), head: start > 0, tail: end < text.length }
}

function Highlighted({ text, terms }: { text: string; terms: string[] }) {
  const pattern = matchPattern(terms)
  if (!pattern) return <>{text}</>
  const parts = text.split(new RegExp(`(${pattern.source})`, "gi"))
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark
            key={i}
            className="rounded bg-primary/15 px-0.5 font-medium text-foreground"
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

/**
 * How close this result is, from the score the retrieval runtime computes and
 * used to throw away. Two signals reach us and their scales are NOT comparable
 * — a sigmoid reranker probability vs an RRF fusion score — so each is labelled
 * for what it is rather than dressed up as one "match %".
 */
function ScoreBadge({ context: c }: { context: Context }) {
  if (c.score == null) return null
  if (c.score_kind === "rrf") {
    return (
      <span
        title={`Matched by keyword and rank fusion; the reranker never scored this passage (RRF ${c.score.toFixed(4)}).`}
        className="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        related
      </span>
    )
  }
  const pct = Math.max(0, Math.min(1, c.score)) * 100
  const label = pct >= 1 ? `${Math.round(pct)}%` : "<1%"
  const tone =
    pct >= 50
      ? "border-primary/40 bg-primary/10 text-primary"
      : pct >= 5
        ? "border-border bg-muted text-foreground/80"
        : "border-border text-muted-foreground"
  return (
    <span
      title={`Reranker relevance: the model's confidence that this passage answers your search — ${c.score.toFixed(3)}${c.score_rank ? `, rank ${c.score_rank}` : ""}.`}
      className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold tabular-nums ${tone}`}
    >
      {label}
    </span>
  )
}

function ResultCard({ context: c, query }: { context: Context; query: string }) {
  const link = resolveLink(c)
  const terms = queryTerms(query)
  const pattern = matchPattern(terms)
  const window = bestWindow(c.text, pattern, terms)
  const inner = (
    <>
      <div className="mb-1 flex items-start justify-between gap-3">
        {c.heading ? (
          <p className="text-xs font-semibold text-primary">{c.heading}</p>
        ) : (
          <span />
        )}
        <ScoreBadge context={c} />
      </div>
      <p className="text-sm leading-relaxed text-foreground/85">
        {window.head && "…"}
        <Highlighted text={window.body} terms={terms} />
        {window.tail && "…"}
      </p>
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

/**
 * Inline "still working" cue. The docs leg is the slow one, so results must
 * arrive progressively with a visible pulse rather than a silent gap where the
 * user cannot tell whether the search finished.
 */
function PendingCards({ label, rows = 2 }: { label: string; rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite">
      <div className="flex items-center gap-2.5 rounded-xl border border-dashed bg-card/40 px-4 py-3">
        <span className="flex items-center gap-1" aria-hidden="true">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="size-1.5 animate-pulse rounded-full bg-primary"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-xl border bg-card p-4">
          <div className="mb-2 h-3 w-36 animate-pulse rounded bg-muted" />
          <div
            className="mb-2 h-3 w-full animate-pulse rounded bg-muted"
            style={{ animationDelay: `${i * 150}ms` }}
          />
          <div
            className="h-3 w-2/3 animate-pulse rounded bg-muted"
            style={{ animationDelay: `${i * 150 + 75}ms` }}
          />
        </div>
      ))}
    </div>
  )
}

async function queryArea(
  token: string | undefined,
  areaId: string,
  question: string
): Promise<Context[]> {
  const doFetch = async (withToken: boolean): Promise<Context[]> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    }
    if (withToken && token) headers.Authorization = `Bearer ${token}`
    const res = await fetch(`${COOP_API_URL}/mcp`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "tools/call",
        params: {
          name: "rag.retrieve_area_contexts",
          arguments: { area_id: areaId, question, rerank: true },
        },
      }),
    })
    // A stale/expired session token is rejected (401) — fall back to the
    // anonymous principal, which can still search anything public.
    if (res.status === 401 && withToken) return doFetch(false)
    const data = await res.json()
    const text = data?.result?.content?.[0]?.text
    if (!text) return []
    try {
      return (JSON.parse(text).contexts ?? []) as Context[]
    } catch {
      return []
    }
  }
  return doFetch(Boolean(token))
}

export function DocsSearch({
  className = "",
  prioritizeGroups = false,
}: {
  className?: string
  prioritizeGroups?: boolean
}) {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [docsPending, setDocsPending] = useState(false)
  const [contexts, setContexts] = useState<Context[]>([])
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The query the current results answer — not the live input box, which the
  // user may keep typing into. Highlights must match what was searched.
  const [asked, setAsked] = useState("")
  // Guards against a slower earlier search landing after a newer one.
  const runRef = useRef(0)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    const run = ++runRef.current
    setLoading(true)
    setError(null)
    setSearched(true)
    setContexts([])
    setDocsPending(true)
    setAsked(q)

    // Groups first (fast area) — render immediately so the search feels
    // responsive, then let the design-doc half (the slow, reranked leg) merge in.
    const groupCtx = await queryArea(token, GROUPS_AREA_ID, q).catch(() => [])
    if (run !== runRef.current) return
    setContexts(dedupe(groupCtx.map((c) => ({ ...c, area: "groups" as const }))))
    setLoading(false)

    const docCtx = await queryArea(token, DOCS_AREA_ID, q).catch(() => [])
    if (run !== runRef.current) return
    setDocsPending(false)
    // Cap the merged list per source: slicing the union silently dropped doc
    // passages whenever the group half returned anything.
    setContexts((prev) =>
      dedupe([
        ...prev.filter(isGroupContext),
        ...docCtx.map((c) => ({ ...c, area: "docs" as const })),
      ]).slice(0, 12)
    )
  }

  const groups = contexts.filter(isGroupContext)
  const docs = contexts.filter((c) => !isGroupContext(c))
  const busy = loading || docsPending
  const pendingLabel = loading
    ? "Searching groups and docs…"
    : "Still loading design docs…"

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

      {error && (
        <p className="mt-4 text-center text-sm text-muted-foreground">
          {error}
        </p>
      )}

      {searched && !busy && contexts.length === 0 && !error && (
        <p className="mt-4 text-center text-sm text-muted-foreground">
          No matching passages.
        </p>
      )}

      {(contexts.length > 0 || busy) && (
        <div className="mt-6 space-y-4">
          {prioritizeGroups ? (
            <>
              {groups.length > 0 && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
                  Groups
                </h3>
              )}
              <div className="space-y-3">
                {groups.map((c, i) => (
                  <ResultCard key={`g-${i}`} context={c} query={asked} />
                ))}
              </div>

              {docs.length > 0 && (
                <h3 className="flex items-center gap-2 pt-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
                  Docs
                  {docsPending && (
                    <span
                      className="size-1.5 animate-pulse rounded-full bg-primary"
                      aria-hidden="true"
                    />
                  )}
                </h3>
              )}
              <div className="space-y-3">
                {docs.map((c, i) => (
                  <ResultCard key={`d-${i}`} context={c} query={asked} />
                ))}
              </div>
              {docsPending && <PendingCards label={pendingLabel} />}
            </>
          ) : (
            <>
              <div className="space-y-3">
                {contexts.map((c, i) => (
                  <ResultCard key={i} context={c} query={asked} />
                ))}
              </div>
              {docsPending && <PendingCards label={pendingLabel} />}
            </>
          )}
        </div>
      )}

      {!token && (
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Just browsing —{" "}
          <Link
            href="/sign-in"
            className="font-semibold text-primary hover:underline"
          >
            sign in
          </Link>{" "}
          to ask follow-ups and see your group&apos;s knowledge.
        </p>
      )}
    </div>
  )
}