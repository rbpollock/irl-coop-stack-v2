"use client"

import dynamic from "next/dynamic"
import { useState } from "react"
import { AlertTriangle, BadgeCheck, CheckCircle2, Clock, Handshake, Plus, Repeat } from "lucide-react"

// Needs/offers — a force-directed "solution space". Stress-test data spans
// three shapes (physical / remote / financial) and multiple candidate matches
// per need, weighted by fit. Link distance encodes match strength: a tight link
// is a strong match, a long one a weak one.

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[440px] items-center justify-center text-sm text-muted-foreground">
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
  quantity?: string
  condition?: string
  timeframe?: string
  undeclared?: string[]
  missing?: boolean
}

type GLink = {
  source: string
  target: string
  weight: number // 0–1 match strength (fit)
}

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

// The details a posting may declare. `undeclared` marks the specifics the poster
// hasn't filled in yet — these are exactly the gaps the validation story must
// close before the loop can confirm.
const NODES: GNode[] = [
  // — physical: the surplus triangle —
  { id: "cs-storage", have: true, what: "4 m³ cold storage", group: "Cold Storage Co-op", shape: "physical", km: 12, condition: "dry cold room", timeframe: "frees up by the 12th" },
  { id: "cs-compost", have: false, what: "compost", group: "Cold Storage Co-op", shape: "physical", km: 12, quantity: "2–3 t", timeframe: "for spring beds", undeclared: ["transport", "timing"] },
  { id: "mg-compost", have: true, what: "2 t compost", group: "Market Garden", shape: "physical", km: 9, condition: "organic", timeframe: "by the 18th" },
  { id: "mg-seed", have: false, what: "seed", group: "Market Garden", shape: "physical", km: 9, quantity: "20 kg", timeframe: "by planting" },
  { id: "sc-seed", have: true, what: "40 kg seed", group: "Seed Co-op", shape: "physical", km: 14, condition: "pristine", quantity: "40 kg" },
  { id: "sc-storage", have: false, what: "winter storage", group: "Seed Co-op", shape: "physical", km: 14, condition: "dry + cold, root veg", undeclared: ["timing"] },

  // — physical: contested needs — several candidates, different fit —
  { id: "manure", have: true, what: "composted manure", group: "Meadow Farm", shape: "physical", km: 16, condition: "well-rotted" },
  { id: "leaf-mulch", have: true, what: "leaf mulch", group: "Forest Commons", shape: "physical", km: 11, condition: "autumn leaves" },
  { id: "saved-seed", have: true, what: "20 kg saved seed", group: "Root Cellar", shape: "physical", km: 13, condition: "open-pollinated" },
  { id: "shed", have: true, what: "20 m² shed space", group: "Tool Library", shape: "physical", km: 8, condition: "humid, unheated" },

  // — physical: bilateral pairs —
  { id: "hay", have: true, what: "surplus hay bales", group: "Meadow Farm", shape: "physical", km: 18, condition: "barn-stored" },
  { id: "need-hay", have: false, what: "winter feed", group: "Livestock Co-op", shape: "physical", km: 18, quantity: "2 t" },
  { id: "greenhouse", have: true, what: "winter bench space", group: "Glasshouse Collective", shape: "physical", km: 7, condition: "heated, 6 benches" },
  { id: "need-greenhouse", have: false, what: "winter grow space", group: "Root Cellar", shape: "physical", km: 7, timeframe: "for seedlings" },
  { id: "kiln", have: true, what: "community kiln", group: "Clay Works", shape: "physical", km: 31, condition: "cone 6, 2 firings/mo" },
  { id: "need-kiln", have: false, what: "kiln firing", group: "Potters Guild", shape: "physical", km: 31, timeframe: "bisque + glaze" },

  // — physical: a near-miss gap —
  { id: "tool-truck", have: true, what: "box truck", group: "Tool Share", shape: "physical", km: 22, timeframe: "weekends only" },
  { id: "missing-haul", have: false, what: "hauling help", group: "…", shape: "physical", km: 22, quantity: "one load", missing: true },

  // — remote: skill-bound, no location —
  { id: "marketing", have: true, what: "marketing expertise", group: "Comms Circle", shape: "remote", condition: "co-op launch experience" },
  { id: "need-marketing", have: false, what: "marketing help", group: "Food Co-op", shape: "remote", timeframe: "before autumn" },
  { id: "va", have: true, what: "virtual assistant hours", group: "Admin Co-op", shape: "remote", quantity: "10 h/wk" },
  { id: "need-va", have: false, what: "admin support", group: "Tool Library", shape: "remote", quantity: "5 h/wk" },
  { id: "coaching", have: true, what: "facilitation coaching", group: "Weave Circle", shape: "remote", condition: "conflict + repair" },
  { id: "need-coaching", have: false, what: "facilitation help", group: "Housing Collective", shape: "remote", timeframe: "for a tough AGM" },

  // — financial: funding asks anchored to a project, seeking a sponsor —
  { id: "fund-solar", have: false, what: "solar array · $5k", group: "Energy Co-op · project", shape: "financial" },
  { id: "fund-tools", have: false, what: "tool library seed · $2k", group: "Tool Library · project", shape: "financial" },
  { id: "fund-kitchen", have: false, what: "community kitchen · $8k", group: "Kitchen Collective · project", shape: "financial" },
]

// Potential matches with a fit weight. Contested needs carry several candidates
// at different weights so the graph shows *distance of likely weights*, not one
// possible match each.
const LINKS: GLink[] = [
  // compost — three candidates, from strong to weak
  { source: "mg-compost", target: "cs-compost", weight: 0.92 },
  { source: "manure", target: "cs-compost", weight: 0.62 },
  { source: "leaf-mulch", target: "cs-compost", weight: 0.38 },

  // seed — right quantity beats pristine-but-surplus
  { source: "sc-seed", target: "mg-seed", weight: 0.82 },
  { source: "saved-seed", target: "mg-seed", weight: 0.95 },

  // storage — dry cold room beats a humid shed
  { source: "cs-storage", target: "sc-storage", weight: 0.95 },
  { source: "shed", target: "sc-storage", weight: 0.44 },

  // bilateral pairs
  { source: "hay", target: "need-hay", weight: 0.9 },
  { source: "greenhouse", target: "need-greenhouse", weight: 0.86 },
  { source: "kiln", target: "need-kiln", weight: 0.8 },
  { source: "tool-truck", target: "missing-haul", weight: 0.7 },

  // remote
  { source: "marketing", target: "need-marketing", weight: 0.9 },
  { source: "va", target: "need-va", weight: 0.85 },
  { source: "coaching", target: "need-coaching", weight: 0.8 },
]

const LOOP_NODES = ["cs-storage", "sc-storage", "sc-seed", "mg-seed", "mg-compost", "cs-compost"]

type StoryLeg = { from: string; to: string; what: string; how: string; coverage: string; gap?: string }

const STORY_LEGS: StoryLeg[] = [
  { from: "Cold Storage Co-op", to: "Seed Co-op", what: "winter storage", how: "frees up by the 12th", coverage: "covered" },
  { from: "Seed Co-op", to: "Market Garden", what: "40 kg seed", how: "no transport yet", coverage: "50% surplus", gap: "transport" },
  { from: "Market Garden", to: "Cold Storage Co-op", what: "2 t compost", how: "coop truck · by the 18th", coverage: "covered" },
]

const GAPS = [
  "Leg 2 (seed) has no transport — who moves it?",
  "40 kg offered, 20 kg needed — route the surplus.",
]

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
    const cond = n.condition ? ` · ${n.condition}` : ""
    return `${verb} ${n.what} · ${n.group}${cond}${place}`
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
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-6 bg-slate-400" /> stronger match = tighter link
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
            height={440}
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
            linkWidth={(l: any) => 1 + l.weight * 2.5}
            linkColor={(l: any) => `rgba(100,116,139,${0.25 + l.weight * 0.55})`}
            linkLabel={(l: any) => `${Math.round(l.weight * 100)}% fit`}
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
              {(selected.quantity || selected.condition || selected.timeframe) && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {selected.quantity && <span className="rounded bg-muted px-1.5 py-0.5 text-[11px]">{selected.quantity}</span>}
                  {selected.condition && <span className="rounded bg-muted px-1.5 py-0.5 text-[11px]">{selected.condition}</span>}
                  {selected.timeframe && <span className="rounded bg-muted px-1.5 py-0.5 text-[11px]">{selected.timeframe}</span>}
                </div>
              )}
              {selected.undeclared && (
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  <span className="text-amber-600">not declared yet:</span> {selected.undeclared.join(" · ")}
                </p>
              )}
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
            <>
              <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-amber-500/90 px-3 py-1 text-xs font-medium text-white">
                <Clock className="size-3.5" />
                Validating — {GAPS.length} gaps
              </div>
              <div className="absolute inset-x-3 bottom-3 rounded-lg border bg-background/95 p-3 shadow-md backdrop-blur">
                <p className="text-sm font-medium">The surplus triangle — does it hold?</p>
                <div className="mt-2 space-y-1.5">
                  {STORY_LEGS.map((leg) => (
                    <div key={leg.from} className="flex items-center justify-between gap-2 text-xs">
                      <span className="truncate text-muted-foreground">
                        {leg.from} → {leg.to} · <span className="text-foreground">{leg.what}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1.5">
                        <span className="text-emerald-600">{leg.coverage}</span>
                        {leg.gap && <span className="text-amber-600">· {leg.gap}</span>}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="mt-2 space-y-1 border-t pt-2">
                  {GAPS.map((g) => (
                    <p key={g} className="flex items-center gap-1.5 text-xs text-amber-700">
                      <AlertTriangle className="size-3.5 shrink-0" />
                      {g}
                    </p>
                  ))}
                </div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <p className="text-[11px] text-muted-foreground">
                    On settle, the anonymized story joins the Solutions library.
                  </p>
                  <button className="shrink-0 rounded-md bg-primary px-2 py-1.5 text-xs font-medium text-primary-foreground">
                    Close the gaps
                  </button>
                </div>
              </div>
            </>
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
                {n.quantity && ` · ${n.quantity}`}
              </p>
              {n.undeclared && (
                <p className="mt-1 text-[11px] text-amber-600">not declared: {n.undeclared.join(" · ")}</p>
              )}
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
