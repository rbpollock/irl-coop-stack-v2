"use client"

import dynamic from "next/dynamic"
import { useMemo, useState } from "react"
import { AlertTriangle, BadgeCheck, CheckCircle2, Clock, Handshake, Plus, Repeat } from "lucide-react"

import { buildLinks, buildPostings, REGIONS, type Posting, type Shape } from "@/lib/needs-offers.data"

// Needs/offers — a force-directed "solution space" fed by a generated corpus
// (recipes × regions). Color = shape; line weight = fit; the zone lens decides
// which slice of the ~500 postings is in view.

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

type Zone = "near" | (typeof REGIONS)[number] | "all"

const ZONES: { value: Zone; label: string }[] = [
  { value: "near", label: `Near me (${REGIONS[0]})` },
  ...REGIONS.map((r) => ({ value: r as Zone, label: r })),
  { value: "all", label: "All regions" },
]

type Tab = "weave" | "board" | "loops"

export function NeedsOffersMockup() {
  const [tab, setTab] = useState<Tab>("weave")
  const [zone, setZone] = useState<Zone>("near")
  const [selected, setSelected] = useState<Posting | null>(null)
  const [myWeave, setMyWeave] = useState<string[]>([])

  const allPostings = useMemo(() => buildPostings(), [])
  const allLinks = useMemo(() => buildLinks(allPostings), [allPostings])

  const visiblePostings = useMemo(() => {
    if (zone === "all") return allPostings
    const region = zone === "near" ? REGIONS[0] : zone
    return allPostings.filter((p) => p.location === region)
  }, [zone, allPostings])

  const visibleIds = useMemo(() => new Set(visiblePostings.map((p) => p.id)), [visiblePostings])
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
          <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
            <BadgeCheck className="size-3.5 text-emerald-500" />
            {myWeave.length} in your weave{isMatched && " · matched"}
          </span>
        </div>
      </div>

      {/* how to use it */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border bg-card px-3 py-2 text-xs text-muted-foreground shadow-sm">
        <span className="font-medium text-foreground">How it works</span>
        <span>① pick a zone</span>
        <span>② hover a node to see what someone has or needs</span>
        <span>③ tap → “Weave in” — a linked pair matches right away</span>
      </div>

      {/* shape legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-emerald-500" /> physical (place)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-sky-500" /> remote (skill)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-amber-500" /> funding (project)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full border-2 border-muted-foreground/50" /> need (hollow)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-6 bg-slate-400" /> thicker = better fit
        </span>
        <span className="text-muted-foreground/70">{visiblePostings.length} postings in view</span>
      </div>

      {tab === "weave" && (
        <div className="relative rounded-lg border bg-card shadow-sm">
          <ForceGraph2D
            graphData={{ nodes: graphNodes, links: visibleLinks }}
            nodeId="id"
            linkSource="source"
            linkTarget="target"
            width={760}
            height={440}
            nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
              const r = (node.have ? 5 : 4.5) / globalScale
              const color = SHAPE_COLOR[node.shape as Shape]
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
              ctx.font = `${9 / globalScale}px system-ui, sans-serif`
              ctx.textAlign = "center"
              ctx.textBaseline = "top"
              ctx.fillStyle = "rgba(90,100,120,0.9)"
              ctx.fillText(label, node.x, node.y + r + 2 / globalScale)
            }}
            nodeLabel={(n: any) => nodeLabel(n)}
            linkWidth={(l: any) => 1 + l.weight * 2.5}
            linkColor={(l: any) => `rgba(100,116,139,${0.2 + l.weight * 0.5})`}
            linkLabel={(l: any) => `${Math.round(l.weight * 100)}% fit`}
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
            linkDirectionalParticles={0}
            onNodeClick={(n: any) => setSelected(n as Posting)}
            onBackgroundClick={() => setSelected(null)}
          />
          {selected && (
            <div className="absolute bottom-3 left-3 right-3 rounded-lg border bg-background/95 p-3 shadow-md backdrop-blur sm:left-auto sm:w-80">
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
              {selected.shape === "financial" && (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  A funding ask — it seeks a sponsor (vertical funds), not a give/get loop.
                </p>
              )}
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => toggle(selected.id)}
                  className="flex-1 rounded-md bg-primary px-2 py-1.5 text-xs font-medium text-primary-foreground"
                >
                  {myWeave.includes(selected.id) ? "Remove" : "Weave in"}
                </button>
              </div>
            </div>
          )}
          {isMatched && (
            <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-emerald-500/90 px-3 py-1 text-xs font-medium text-white">
              <CheckCircle2 className="size-3.5" />
              Matched — a give/get pair
            </div>
          )}
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
