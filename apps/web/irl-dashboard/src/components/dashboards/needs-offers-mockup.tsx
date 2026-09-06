"use client"

import dynamic from "next/dynamic"
import { useState } from "react"
import { BadgeCheck, CheckCircle2, Clock, Handshake, Plus, Repeat } from "lucide-react"

// Needs/offers — a force-directed "solution space". Stress-test data spans
// three shapes: physical (location-bound), remote (skill-bound), and financial
// (sponsor-bound). Color = shape, fill = have (solid) vs need (hollow).

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] items-center justify-center text-sm text-muted-foreground">
      Laying out the space…
    </div>
  ),
})

type Shape = "physical" | "remote" | "financial"

type GNode = {
  id: string
  have: boolean
  what: string
  group: string
  shape: Shape
  km?: number
  missing?: boolean
}

const SHAPE_COLOR: Record<Shape, string> = {
  physical: "#10b981", // emerald — bound to a place
  remote: "#0ea5e9", // sky — bound to a skill
  financial: "#f59e0b", // amber — bound to a project
}

const SHAPE_LABEL: Record<Shape, string> = {
  physical: "physical",
  remote: "remote",
  financial: "funding",
}

// Offers (have) and needs, grouped by group so the "solution space" reads as
// clusters. `km` is the literal distance for physical items; remote items have
// no place; financial items are funding asks anchored to a project.
const NODES: GNode[] = [
  // — physical: a tight give/get triangle (the canonical closed loop) —
  { id: "cs-storage", have: true, what: "4 m³ cold storage", group: "Cold Storage Co-op", shape: "physical", km: 12 },
  { id: "cs-compost", have: false, what: "compost", group: "Cold Storage Co-op", shape: "physical", km: 12 },
  { id: "mg-compost", have: true, what: "2 t compost", group: "Market Garden", shape: "physical", km: 9 },
  { id: "mg-seed", have: false, what: "seed", group: "Market Garden", shape: "physical", km: 9 },
  { id: "sc-seed", have: true, what: "40 kg seed", group: "Seed Co-op", shape: "physical", km: 14 },
  { id: "sc-storage", have: false, what: "winter storage", group: "Seed Co-op", shape: "physical", km: 14 },

  // — physical: bilateral pairs (offer ↔ need) —
  { id: "hay", have: true, what: "surplus hay bales", group: "Meadow Farm", shape: "physical", km: 18 },
  { id: "need-hay", have: false, what: "winter feed", group: "Livestock Co-op", shape: "physical", km: 18 },
  { id: "greenhouse", have: true, what: "winter bench space", group: "Glasshouse Collective", shape: "physical", km: 7 },
  { id: "need-greenhouse", have: false, what: "winter grow space", group: "Root Cellar", shape: "physical", km: 7 },
  { id: "kiln", have: true, what: "community kiln", group: "Clay Works", shape: "physical", km: 31 },
  { id: "need-kiln", have: false, what: "kiln firing", group: "Potters Guild", shape: "physical", km: 31 },

  // — physical: a near-miss — a truck offer with no matching need yet —
  { id: "tool-truck", have: true, what: "box truck", group: "Tool Share", shape: "physical", km: 22 },
  { id: "missing-haul", have: false, what: "hauling help", group: "…", shape: "physical", km: 22, missing: true },

  // — remote: skill-bound, no location —
  { id: "marketing", have: true, what: "marketing expertise", group: "Comms Circle", shape: "remote" },
  { id: "need-marketing", have: false, what: "marketing help", group: "Food Co-op", shape: "remote" },
  { id: "va", have: true, what: "virtual assistant hours", group: "Admin Co-op", shape: "remote" },
  { id: "need-va", have: false, what: "admin support", group: "Tool Library", shape: "remote" },
  { id: "coaching", have: true, what: "facilitation coaching", group: "Weave Circle", shape: "remote" },
  { id: "need-coaching", have: false, what: "facilitation help", group: "Housing Collective", shape: "remote" },

  // — financial: funding asks anchored to a project — no give/get loop, they
  // seek a sponsor (vertical funds), not a counterparty —
  { id: "fund-solar", have: false, what: "solar array · $5k", group: "Energy Co-op · project", shape: "financial" },
  { id: "fund-tools", have: false, what: "tool library seed · $2k", group: "Tool Library · project", shape: "financial" },
  { id: "fund-kitchen", have: false, what: "community kitchen · $8k", group: "Kitchen Collective · project", shape: "financial" },
]

// Potential matches: an offer that could satisfy a need. Physical edges are
// weighted by km; remote edges have no distance; funding has no edge at all.
const LINKS: { source: string; target: string }[] = [
  { source: "cs-storage", target: "sc-storage" },
  { source: "sc-seed", target: "mg-seed" },
  { source: "mg-compost", target: "cs-compost" },
  { source: "hay", target: "need-hay" },
  { source: "greenhouse", target: "need-greenhouse" },
  { source: "kiln", target: "need-kiln" },
  { source: "tool-truck", target: "missing-haul" },
  { source: "marketing", target: "need-marketing" },
  { source: "va", target: "need-va" },
  { source: "coaching", target: "need-coaching" },
]

// The six nodes that close the canonical triangle loop.
const LOOP_NODES = ["cs-storage", "sc-storage", "sc-seed", "mg-seed", "mg-compost", "cs-compost"]

type Tab = "weave" | "board" | "loops"

export function NeedsOffersMockup() {
  const [tab, setTab] = useState<Tab>("weave")
  const [selected, setSelected] = useState<GNode | null>(null)
  const [myMatch, setMyMatch] = useState<string[]>([])

  const loopClosed = LOOP_NODES.every((id) => myMatch.includes(id))

  const toggle = (id: string) =>
    setMyMatch((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const nodeLabel = (n: GNode) => {
    const verb = n.have ? "We have" : "We need"
    const place = n.km != null ? ` · ${n.km} km` : ""
    return `${verb} ${n.what} · ${n.group}${place}`
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
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
        <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
          <BadgeCheck className="size-3.5 text-emerald-500" />
          {myMatch.length} in your match{loopClosed && " · loop closed"}
        </span>
      </div>

      {/* shape legend — the stress-test key */}
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
          <span className="size-2.5 rounded-full border-2 border-dashed border-muted-foreground/50" /> missing (gap)
        </span>
      </div>

      {tab === "weave" && (
        <div className="relative rounded-lg border bg-card shadow-sm">
          <ForceGraph2D
            graphData={{ nodes: NODES, links: LINKS }}
            nodeId="id"
            linkSource="source"
            linkTarget="target"
            width={760}
            height={420}
            nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
              const r = (node.missing ? 4.5 : node.have ? 6.5 : 5.5) / globalScale
              const color = node.missing ? "#9ca3af" : SHAPE_COLOR[node.shape as Shape]
              ctx.beginPath()
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
              if (node.have) {
                ctx.fillStyle = color
                ctx.fill()
              } else {
                ctx.strokeStyle = color
                ctx.lineWidth = 2 / globalScale
                if (node.missing) ctx.setLineDash([3 / globalScale, 2.5 / globalScale])
                ctx.stroke()
                ctx.setLineDash([])
              }
            }}
            nodeLabel={(n: any) => nodeLabel(n)}
            linkColor={() => "rgba(148,163,184,0.35)"}
            linkWidth={1.5}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkDirectionalParticles={0}
            onNodeClick={(n: any) => setSelected(n as GNode)}
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
              {selected.shape === "financial" && (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  A funding ask — it seeks a sponsor (vertical funds), not a give/get loop.
                </p>
              )}
              {selected.missing && (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  No offer matches this yet — you could be the one to fill it.
                </p>
              )}
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => toggle(selected.id)}
                  className="flex-1 rounded-md bg-primary px-2 py-1.5 text-xs font-medium text-primary-foreground"
                >
                  {myMatch.includes(selected.id) ? "Remove" : "Add to my match"}
                </button>
                {selected.missing && (
                  <button className="flex-1 rounded-md border px-2 py-1.5 text-xs font-medium">
                    I can fill this
                  </button>
                )}
              </div>
            </div>
          )}
          {loopClosed && (
            <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-emerald-500/90 px-3 py-1 text-xs font-medium text-white">
              <CheckCircle2 className="size-3.5" />
              Loop closed — everyone gets rewarded
            </div>
          )}
        </div>
      )}

      {tab === "board" && (
        <div className="grid gap-2 sm:grid-cols-2">
          {NODES.filter((n) => !n.missing).map((n) => (
            <button
              key={n.id}
              onClick={() => toggle(n.id)}
              className={`rounded-lg border bg-card p-3 text-left shadow-sm transition hover:border-primary/40 ${
                myMatch.includes(n.id) ? "border-primary/60 ring-1 ring-primary/30" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  {n.have ? "We have" : "We need"} {n.what}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    n.shape === "physical"
                      ? "bg-emerald-500/10 text-emerald-700"
                      : n.shape === "remote"
                        ? "bg-sky-500/10 text-sky-700"
                        : "bg-amber-500/10 text-amber-700"
                  }`}
                >
                  {SHAPE_LABEL[n.shape]}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {n.group}
                {n.km != null && ` · ${n.km} km`}
              </p>
            </button>
          ))}
        </div>
      )}

      {tab === "loops" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-lg border bg-card p-3 shadow-sm">
            <CheckCircle2 className="size-4 text-emerald-500" />
            <div className="flex-1">
              <p className="text-sm font-medium">The surplus triangle</p>
              <p className="text-xs text-muted-foreground">
                Cold Storage → Seed Co-op → Market Garden → back. Settled.
              </p>
            </div>
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
              done
            </span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border bg-card p-3 shadow-sm">
            <Clock className="size-4 text-amber-500" />
            <div className="flex-1">
              <p className="text-sm font-medium">Kiln firing</p>
              <p className="text-xs text-muted-foreground">
                Clay Works offers a kiln; Potters Guild needs a firing — waiting on a pickup leg.
              </p>
            </div>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700">
              stuck
            </span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-dashed bg-card p-3 shadow-sm">
            <Handshake className="size-4 text-muted-foreground" />
            <div className="flex-1">
              <p className="text-sm font-medium">Solar array · $5k</p>
              <p className="text-xs text-muted-foreground">
                A funding ask — seeking a sponsor, not a loop.
              </p>
            </div>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700">
              funding
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default NeedsOffersMockup
