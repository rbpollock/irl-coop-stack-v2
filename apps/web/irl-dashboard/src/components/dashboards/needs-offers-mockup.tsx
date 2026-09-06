"use client"

import dynamic from "next/dynamic"
import { useCallback, useMemo, useRef, useState } from "react"
import { BadgeCheck, CheckCircle2, ChevronDown, ChevronRight, Clock, Handshake, Plus, Repeat, X } from "lucide-react"
import { forceLink } from "d3-force-3d"

import { buildLinks, buildPostings, REGIONS, type Posting, type Shape } from "@/lib/needs-offers.data"

// Needs/offers — a force-directed "solution space". Color = shape; line length =
// fit (shorter = stronger); dashed links are loose connections. Selecting nodes
// outlines them and pulls them together (gravity); "Connect" ties them into a
// dashed weave.

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[440px] items-center justify-center text-sm text-muted-foreground">
      Laying out the space…
    </div>
  ),
})

const SHAPE_COLOR: Record<Shape, string> = {
  physical: "#10b981",
  remote: "#0ea5e9",
  financial: "#f59e0b",
}

const SHAPE_LABEL: Record<Shape, string> = {
  physical: "physical",
  remote: "remote",
  financial: "funding",
}

const URGENCY_LABEL: Record<string, string> = {
  high: "urgent",
  medium: "soon",
  low: "anytime",
}

// A force that pulls selected nodes toward their shared centroid — the "gravity"
// that keeps the pieces you've chosen near each other.
function makeGravityForce(getIds: () => Set<string>) {
  let nodes: any[] = []
  function force(alpha: number) {
    const ids = getIds()
    if (ids.size < 2) return
    const sel = nodes.filter((n) => ids.has(n.id))
    if (sel.length < 2) return
    const cx = sel.reduce((s, n) => s + n.x, 0) / sel.length
    const cy = sel.reduce((s, n) => s + n.y, 0) / sel.length
    const g = alpha * 0.5
    for (const n of sel) {
      n.vx += (cx - n.x) * g
      n.vy += (cy - n.y) * g
    }
  }
  force.initialize = (ns: any[]) => {
    nodes = ns
  }
  return force
}

type Zone = "near" | (typeof REGIONS)[number] | "all"

const ZONES: { value: Zone; label: string }[] = [
  { value: "near", label: `Near me (${REGIONS[0]})` },
  ...REGIONS.slice(0, 12).map((r) => ({ value: r as Zone, label: r })),
  { value: "all", label: "All regions" },
]

type Tab = "weave" | "board" | "loops"

export function NeedsOffersMockup() {
  const [tab, setTab] = useState<Tab>("weave")
  const [zone, setZone] = useState<Zone>("near")
  const [selected, setSelected] = useState<Posting | null>(null)
  const [myWeave, setMyWeave] = useState<string[]>([])
  const [postOpen, setPostOpen] = useState(false)
  const [postText, setPostText] = useState("")
  const [postShape, setPostShape] = useState<Shape>("physical")
  const [search, setSearch] = useState("")
  const [expanded, setExpanded] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(true)
  const [urgentOpen, setUrgentOpen] = useState(true)

  const myWeaveRef = useRef<Set<string>>(new Set())
  myWeaveRef.current = new Set(myWeave)

  const appliedRef = useRef(false)

  const applyForces = useCallback((fg: any) => {
    const fitDistance = (l: any) => 24 + (1 - (l.weight ?? 0.5)) * 320
    fg.d3Force("link", forceLink().distance(fitDistance))
    fg.d3Force("weave-gravity", makeGravityForce(() => myWeaveRef.current))
    fg.d3ReheatSimulation()
  }, [])

  const allPostings = useMemo(() => buildPostings(), [])
  const allLinks = useMemo(() => buildLinks(allPostings), [allPostings])

  const visiblePostings = useMemo(() => {
    if (zone === "all") return allPostings
    const region = zone === "near" ? REGIONS[0] : zone
    return allPostings.filter((p) => p.location === region)
  }, [zone, allPostings])

  const visibleIds = useMemo(() => new Set(visiblePostings.map((p) => p.id)), [visiblePostings])
  const searchResults = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return []
    return visiblePostings
      .filter(
        (p) =>
          p.what.toLowerCase().includes(q) ||
          p.group.toLowerCase().includes(q) ||
          p.type.toLowerCase().includes(q) ||
          p.location.toLowerCase().includes(q),
      )
      .slice(0, 6)
  }, [search, visiblePostings])
  const highPriorityNeeds = useMemo(
    () => visiblePostings.filter((p) => !p.have && p.urgency === "high").slice(0, 8),
    [visiblePostings],
  )
  const visibleLinks = useMemo(
    () => allLinks.filter((l) => visibleIds.has(l.source) && visibleIds.has(l.target)),
    [allLinks, visibleIds],
  )

  // Seed positions grouped by shape so the layout starts spatially organized.
  const graphNodes = useMemo(
    () =>
      visiblePostings.map((p, i) => ({
        ...p,
        x: p.shape === "physical" ? 160 + (i % 5) * 40 : p.shape === "remote" ? 520 + (i % 3) * 40 : 340 + (i % 3) * 60,
        y: p.shape === "physical" ? 120 + Math.floor((i % 15) / 5) * 60 : p.shape === "remote" ? 140 + (i % 4) * 55 : 400,
      })),
    [visiblePostings],
  )

  // Solid links between the selected nodes (in selection order) — the weave.
  const weaveLinks = useMemo(() => {
    const links: { source: string; target: string; weight: number; connected: boolean }[] = []
    for (let i = 0; i < myWeave.length - 1; i++) {
      links.push({ source: myWeave[i], target: myWeave[i + 1], weight: 1, connected: true })
    }
    return links
  }, [myWeave])

  const graphLinks = useMemo(() => [...visibleLinks, ...weaveLinks], [visibleLinks, weaveLinks])

  const isMatched =
    myWeave.length >= 2 && visibleLinks.some((l) => myWeave.includes(l.source) && myWeave.includes(l.target))

  const toggle = (id: string) =>
    setMyWeave((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const nodeLabel = (n: Posting) => {
    const verb = n.have ? "We have" : "We need"
    const place = n.km != null ? ` · ${n.km} km` : ""
    return `${verb} ${n.what} · ${n.group}${place}`
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1 rounded-lg border bg-card p-1 shadow-sm">
          {(
            [
              ["weave", "Weave", Repeat],
              ["board", "Have & need", Plus],
              ["loops", "Loops", CheckCircle2],
            ] as const
          ).map(([id, label, Icon]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition ${
                tab === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPostOpen(!postOpen)}
            className="flex items-center gap-1.5 rounded-md border bg-card px-3 py-1.5 text-sm font-medium shadow-sm transition hover:border-primary/40"
          >
            <Plus className="size-4" />
            Post
          </button>
          <label className="text-xs text-muted-foreground">Zone</label>
          <select
            value={zone}
            onChange={(e) => setZone(e.target.value as Zone)}
            className="h-8 rounded-md border bg-card px-2 text-xs shadow-sm"
          >
            {ZONES.map((z) => (
              <option key={z.value} value={z.value}>
                {z.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {postOpen && (
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Post a need or offer</p>
            <button onClick={() => setPostOpen(false)} className="text-muted-foreground transition hover:text-foreground">
              ✕
            </button>
          </div>
          <label className="mt-3 block text-xs font-medium text-muted-foreground">What do you have or need?</label>
          <input
            value={postText}
            onChange={(e) => setPostText(e.target.value)}
            placeholder="e.g. 20 kg seed for spring, or five volunteers for the harvest"
            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm shadow-sm"
          />
          <label className="mt-3 block text-xs font-medium text-muted-foreground">What kind?</label>
          <div className="mt-1 flex gap-2">
            {(
              [
                ["physical", "📍", "something physical"],
                ["remote", "🌐", "help or expertise"],
                ["financial", "⚖️", "funding"],
              ] as const
            ).map(([s, emoji, label]) => (
              <button
                key={s}
                onClick={() => setPostShape(s)}
                className={`flex-1 rounded-md border p-2 text-xs font-medium transition ${
                  postShape === s ? "border-primary bg-primary/5" : "hover:border-primary/40"
                }`}
              >
                <span className="block text-base">{emoji}</span>
                {label}
              </button>
            ))}
          </div>
          <div className="mt-3 rounded-md border border-dashed bg-muted/40 p-2.5 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">The AI fills the rest</p>
            <p className="mt-0.5">
              type · temporality · urgency · location — read from your words, your group, and your device.
            </p>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Or start from a Plane issue or Matrix message — the posting is pre-seeded from work you&apos;re already doing.
          </p>
          <button className="mt-3 w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground">
            Post it
          </button>
        </div>
      )}

      {/* the weave view — the graph fills the page, controls float on top */}

      {tab === "weave" && (
        <div className="relative h-[calc(100vh-8rem)] overflow-hidden [&_canvas]:touch-none">
          <ForceGraph2D
            ref={(fg: any) => {
              if (fg && !appliedRef.current) {
                appliedRef.current = true
                applyForces(fg)
              }
            }}
              graphData={{ nodes: graphNodes, links: graphLinks }}
              nodeId="id"
              linkSource="source"
              linkTarget="target"
              nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
                const inWeave = myWeave.includes(node.id)
                const r = (node.have ? 7 : 6) / globalScale
                const color = SHAPE_COLOR[node.shape as Shape]
                if (inWeave) {
                  ctx.beginPath()
                  ctx.arc(node.x, node.y, r + 6 / globalScale, 0, 2 * Math.PI)
                  ctx.strokeStyle = "rgba(79,70,229,1)"
                  ctx.lineWidth = 3.5 / globalScale
                  ctx.stroke()
                }
                ctx.beginPath()
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
                if (node.have) {
                  ctx.fillStyle = color
                  ctx.fill()
                } else {
                  ctx.strokeStyle = color
                  ctx.lineWidth = 1.8 / globalScale
                  ctx.stroke()
                }
                const label = node.what.length > 14 ? `${node.what.slice(0, 13)}…` : node.what
                ctx.font = `${11 / globalScale}px system-ui, sans-serif`
                ctx.textAlign = "center"
                ctx.textBaseline = "top"
                ctx.fillStyle = "rgba(255,255,255,0.95)"
                ctx.fillText(label, node.x, node.y + r + 2 / globalScale)
              }}
              nodeLabel={(n: any) => nodeLabel(n)}
              nodePointerAreaPaint={(node: any, color: string, ctx: any) => {
                ctx.beginPath()
                ctx.arc(node.x, node.y, 12, 0, 2 * Math.PI)
                ctx.fillStyle = color
                ctx.fill()
              }}
              linkWidth={(l: any) => (l.connected ? 1 : 0.6 + l.weight * 1.8)}
              linkColor={(l: any) =>
                l.connected ? "rgba(99,102,241,0.7)" : `rgba(100,116,139,${0.18 + l.weight * 0.5})`
              }
              linkLineDash={(l: any) => (l.connected ? null : [3, 3])}
              linkLabel={(l: any) => (l.connected ? "weave" : `${Math.round(l.weight * 100)}% fit`)}
              linkDirectionalParticles={0}
              onNodeClick={(n: any) => {
                setSelected(n as Posting)
                toggle(n.id)
              }}
              onBackgroundClick={() => setSelected(null)}
            />
            {selected && (
              <div className="absolute bottom-10 left-3 right-3 rounded-lg border bg-background/95 p-3 shadow-md backdrop-blur">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium">
                      {selected.have ? "We have" : "We need"} {selected.what}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {selected.group}
                      {selected.km != null && ` · ${selected.km} km`}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      selected.shape === "physical"
                        ? "bg-emerald-500/10 text-emerald-700"
                        : selected.shape === "remote"
                          ? "bg-sky-500/10 text-sky-700"
                          : "bg-amber-500/10 text-amber-700"
                    }`}
                  >
                    {SHAPE_LABEL[selected.shape]}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[11px]">{selected.type}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[11px]">{selected.temporality}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                      selected.urgency === "high"
                        ? "bg-red-500/10 text-red-600"
                        : selected.urgency === "medium"
                          ? "bg-amber-500/10 text-amber-600"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {URGENCY_LABEL[selected.urgency]}
                  </span>
                </div>
              </div>
            )}
            {isMatched && (
              <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-emerald-500/90 px-3 py-1 text-xs font-medium text-white">
                <CheckCircle2 className="size-3.5" />
                Matched
              </div>
            )}

          {/* how-it-works floating chip */}
          <div className="absolute left-3 top-3 rounded-lg border bg-background/85 px-2.5 py-1.5 text-[11px] text-muted-foreground shadow-sm backdrop-blur">
            ① pick a zone · ② tap a node · ③ Connect
          </div>

          {/* drawer toggle — summon the drawer when closed */}
          {!drawerOpen && (
            <button
              onClick={() => setDrawerOpen(true)}
              className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md border bg-background/85 px-2.5 py-1.5 text-xs font-medium shadow-sm backdrop-blur"
            >
              <ChevronRight className="size-3.5" />
              Weave
            </button>
          )}

          {/* the drawer */}
          <div
            className={`absolute bottom-9 right-0 top-0 flex w-80 transform flex-col border-l bg-background/95 shadow-xl backdrop-blur transition-transform duration-200 ${
              drawerOpen ? "translate-x-0" : "translate-x-full"
            }`}
          >
            <div className="flex items-center justify-between border-b p-3">
              <span className="text-sm font-medium">Your weave</span>
              <button
                onClick={() => setDrawerOpen(false)}
                className="rounded-md border p-1 text-muted-foreground transition hover:text-foreground"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="flex-1 overflow-auto border-b p-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search the space…"
              className="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs shadow-sm"
            />
            {search.trim() && (
              <div className="mt-2 space-y-1">
                {searchResults.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No matches in this zone.</p>
                ) : (
                  searchResults.map((p) => (
                    <div key={p.id} className="rounded-md border p-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <button
                          onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                          className="min-w-0 flex-1 truncate text-left hover:text-foreground"
                        >
                          <span className="text-muted-foreground">{p.have ? "have" : "need"}</span> {p.what}
                        </button>
                        <button
                          onClick={() => toggle(p.id)}
                          className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary transition hover:bg-primary/20"
                        >
                          {myWeave.includes(p.id) ? "remove" : "weave in"}
                        </button>
                      </div>
                      {expanded === p.id && (
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {p.group} · {p.type} · {p.temporality}
                          {p.km != null ? ` · ${p.km} km` : ""}
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
            <p className="mt-3 text-xs font-medium text-muted-foreground">In your weave</p>
            {myWeave.length === 0 ? (
              <p className="mt-1 text-xs text-muted-foreground">
                Tap nodes on the left — they&apos;ll outline and draw together here.
              </p>
            ) : (
              <div className="mt-2 space-y-1.5">
                {myWeave.map((id) => {
                  const p = visiblePostings.find((x) => x.id === id)
                  if (!p) return null
                  return (
                    <div key={id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-xs">
                      <span className="truncate">
                        <span className="text-muted-foreground">{p.have ? "have" : "need"}</span> {p.what}
                      </span>
                      <button onClick={() => toggle(id)} className="shrink-0 text-muted-foreground hover:text-foreground">
                        ✕
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
            {myWeave.length >= 2 && (
              <p className="mt-2 text-[11px] text-indigo-600">
                {myWeave.length - 1} solid link{myWeave.length > 2 ? "s" : ""} drawn — ✕ a card to unlink.
              </p>
            )}
            </div>

            {/* urgent needs in this zone — collapsible */}
            <div className={`overflow-auto border-t ${urgentOpen ? "flex-1" : ""}`}>
              <button
                onClick={() => setUrgentOpen(!urgentOpen)}
                className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground transition hover:text-foreground"
              >
                <span className="flex items-center gap-2">
                  Urgent in this zone
                  <span className="rounded-full bg-amber-500/10 px-1.5 text-[10px] font-medium text-amber-700">
                    {highPriorityNeeds.length}
                  </span>
                </span>
                <ChevronDown className={`size-3.5 transition-transform ${urgentOpen ? "" : "-rotate-90"}`} />
              </button>
              {urgentOpen && (
                <div className="px-3 pb-3">
                  {highPriorityNeeds.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Nothing urgent here.</p>
                  ) : (
                    <div className="space-y-1">
                      {highPriorityNeeds.map((p) => (
                        <div key={p.id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-xs">
                          <span className="truncate">{p.what}</span>
                          <button
                            onClick={() => toggle(p.id)}
                            className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary transition hover:bg-primary/20"
                          >
                            {myWeave.includes(p.id) ? "remove" : "weave in"}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* legend — bottom edge */}
          <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-x-4 gap-y-1 border-t bg-background/85 px-3 py-1.5 text-[11px] text-muted-foreground backdrop-blur">
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full bg-emerald-500" /> physical
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full bg-sky-500" /> remote
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full bg-amber-500" /> funding
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full border-2 border-muted-foreground/50" /> need
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-6 border-t-2 border-dashed border-slate-400" /> fit
            </span>
            <span className="ml-auto">{visiblePostings.length} postings in view</span>
          </div>
        </div>
      )}

      {tab === "board" && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {visiblePostings.map((p) => (
            <button
              key={p.id}
              onClick={() => toggle(p.id)}
              className={`rounded-lg border bg-card p-3 text-left shadow-sm transition hover:border-primary/40 ${
                myWeave.includes(p.id) ? "border-primary/60 ring-1 ring-primary/30" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium">
                  {p.have ? "We have" : "We need"} {p.what}
                </span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    p.shape === "physical"
                      ? "bg-emerald-500/10 text-emerald-700"
                      : p.shape === "remote"
                        ? "bg-sky-500/10 text-sky-700"
                        : "bg-amber-500/10 text-amber-700"
                  }`}
                >
                  {SHAPE_LABEL[p.shape]}
                </span>
              </div>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {p.group}
                {p.km != null && ` · ${p.km} km`}
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">{p.type}</span>
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">{p.temporality}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] ${
                    p.urgency === "high" ? "bg-red-500/10 text-red-600" : p.urgency === "medium" ? "bg-amber-500/10 text-amber-600" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {URGENCY_LABEL[p.urgency]}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {tab === "loops" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-lg border bg-card p-3 shadow-sm">
            <CheckCircle2 className="size-4 text-emerald-500" />
            <div className="flex-1">
              <p className="text-sm font-medium">A matched pair</p>
              <p className="text-xs text-muted-foreground">
                When an offer and a need link up, it closes right away — no ceremony.
              </p>
            </div>
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
              matched
            </span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border bg-card p-3 shadow-sm">
            <Clock className="size-4 text-amber-500" />
            <div className="flex-1">
              <p className="text-sm font-medium">A three-party loop</p>
              <p className="text-xs text-muted-foreground">
                Compost → seed → storage, closing back on itself. Needs its story validated.
              </p>
            </div>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700">
              validating
            </span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-dashed bg-card p-3 shadow-sm">
            <Handshake className="size-4 text-muted-foreground" />
            <div className="flex-1">
              <p className="text-sm font-medium">Material-pooling fund</p>
              <p className="text-xs text-muted-foreground">
                A funding ask — seeking a sponsor, not a loop.
              </p>
            </div>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700">
              funding
            </span>
          </div>
          {isMatched && (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3">
              <CheckCircle2 className="size-4 text-emerald-500" />
              <p className="text-xs text-emerald-700">
                You&apos;ve woven {myWeave.length} pieces into a match.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default NeedsOffersMockup
