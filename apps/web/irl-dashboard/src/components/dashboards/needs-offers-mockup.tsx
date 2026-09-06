"use client"

import dynamic from "next/dynamic"
import { useState } from "react"
import { BadgeCheck, CheckCircle2, Clock, Plus, Repeat } from "lucide-react"

// Needs/offers — a force-directed "solution space" + click popups. The layout
// explains the shape (a loop emerges); text stays out of the graph and lives in
// hover tooltips and the click popup that moves the action forward.

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[380px] items-center justify-center text-sm text-muted-foreground">
      Loading the space…
    </div>
  ),
})

type GNode = { id: string; have: boolean; what: string; group: string; missing?: boolean }

const NODES: GNode[] = [
  { id: "cs-storage", have: true, what: "4 m³ cold storage", group: "Cold Storage Co-op" },
  { id: "cs-compost", have: false, what: "compost", group: "Cold Storage Co-op" },
  { id: "mg-compost", have: true, what: "2 t compost", group: "Market Garden" },
  { id: "mg-seed", have: false, what: "seed", group: "Market Garden" },
  { id: "sc-seed", have: true, what: "40 kg seed", group: "Seed Co-op" },
  { id: "sc-storage", have: false, what: "winter storage", group: "Seed Co-op" },
  { id: "tool-truck", have: true, what: "box truck", group: "Tool Share" },
  { id: "missing-haul", have: false, what: "hauling help", group: "…", missing: true },
]

const LINKS = [
  { source: "cs-storage", target: "sc-storage" },
  { source: "sc-seed", target: "mg-seed" },
  { source: "mg-compost", target: "cs-compost" },
  { source: "tool-truck", target: "missing-haul" },
]

const LOOP = ["cs-storage", "sc-storage", "sc-seed", "mg-seed", "mg-compost", "cs-compost"]

function Weave() {
  const [selected, setSelected] = useState<GNode | null>(null)
  const [mine, setMine] = useState<string[]>([])
  const toggleMine = (id: string) => setMine((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]))
  const closed = LOOP.every((id) => mine.includes(id))

  return (
    <div className="space-y-3">
      <div className="relative overflow-hidden rounded-lg border bg-card shadow-sm">
        <ForceGraph2D
          graphData={{ nodes: NODES, links: LINKS }}
          nodeId="id"
          linkSource="source"
          linkTarget="target"
          width={760}
          height={380}
          nodeColor={(n: any) => (n.missing ? "#9ca3af" : n.have ? "#10b981" : "#0ea5e9")}
          nodeVal={(n: any) => (n.missing ? 4 : 7)}
          nodeLabel={(n: any) => `${n.have ? "We have" : "We need"} ${n.what} · ${n.group}`}
          nodeRelSize={4}
          linkColor={() => "rgba(148,163,184,0.35)"}
          linkWidth={1.5}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkDirectionalParticles={0}
          onNodeClick={(n: any) => setSelected(n as GNode)}
          onBackgroundClick={() => setSelected(null)}
        />

        {/* click popup — the only text, and it moves the action forward */}
        {selected && (
          <div className="absolute bottom-3 left-3 max-w-[260px] rounded-lg border bg-card/95 p-3 shadow-md backdrop-blur">
            <p className="text-sm font-medium">
              {selected.missing ? "Who can" : selected.have ? "We have" : "We need"} {selected.what}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">{selected.group}</p>
            <div className="mt-2 flex gap-2">
              {selected.missing ? (
                <button className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90">
                  <Plus className="size-3" /> I can fill this
                </button>
              ) : (
                <button
                  onClick={() => toggleMine(selected.id)}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium ${
                    mine.includes(selected.id) ? "bg-primary text-primary-foreground" : "border bg-background hover:bg-accent"
                  }`}
                >
                  {mine.includes(selected.id) ? "Added" : "Add to my match"}
                </button>
              )}
              <button className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-[11px] font-medium hover:bg-accent">
                <Repeat className="size-3" /> 1-to-1
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs text-muted-foreground">{mine.length > 0 ? `${mine.length} in your match` : "tap nodes — hover to peek, click to add"}</span>
        {closed && (
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-700">
            <CheckCircle2 className="size-3.5" /> Loop closed — everyone gets rewarded
          </span>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-emerald-500" /> have</span>
        {" · "}
        <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-sky-500" /> need</span>
        {" · "}
        <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-gray-400" /> gap</span>
      </p>
    </div>
  )
}

type Item = { id: string; have: boolean; what: string; group: string; km: number; trusted: boolean }
const ITEMS: Item[] = [
  { id: "a", have: true, what: "4 m³ cold storage", group: "Cold Storage Co-op", km: 12, trusted: true },
  { id: "b", have: false, what: "compost", group: "Cold Storage Co-op", km: 12, trusted: true },
  { id: "c", have: true, what: "2 t compost", group: "Market Garden", km: 9, trusted: false },
  { id: "d", have: false, what: "seed", group: "Market Garden", km: 9, trusted: false },
  { id: "e", have: true, what: "40 kg seed", group: "Seed Co-op", km: 14, trusted: true },
  { id: "f", have: false, what: "winter storage", group: "Seed Co-op", km: 14, trusted: true },
  { id: "g", have: true, what: "box truck", group: "Tool Share", km: 22, trusted: false },
]

function Board() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90">
          <Plus className="size-3.5" /> Post something
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {ITEMS.map((it) => (
          <div key={it.id} className="rounded-lg border bg-card p-3 shadow-sm">
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${it.have ? "bg-emerald-500/10 text-emerald-700" : "bg-sky-500/10 text-sky-700"}`}>
                {it.have ? "have" : "need"}
              </span>
              {it.trusted && <BadgeCheck className="size-3.5 text-emerald-500" />}
            </div>
            <p className="mt-2 text-sm font-medium">
              {it.have ? "We have " : "We need "}
              <span className="font-semibold">{it.what}</span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{it.group} · {it.km} km</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function Loops() {
  const legs = [
    { who: "Cold Storage → Market Garden", what: "cold storage", status: "done" },
    { who: "Market Garden → Seed Co-op", what: "compost", status: "stuck" },
    { who: "Seed Co-op → Cold Storage", what: "seed", status: "done" },
  ]
  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Where things stand</h3>
        <div className="mt-3 space-y-2">
          {legs.map((l, i) => (
            <div key={i} className="flex items-center gap-2 rounded-md border p-2.5">
              <span className="flex-1 text-xs font-medium">{l.who}</span>
              <span className="text-xs text-muted-foreground">{l.what}</span>
              <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${l.status === "done" ? "bg-emerald-500/10 text-emerald-700" : l.status === "stuck" ? "bg-red-500/10 text-red-700" : "bg-amber-500/10 text-amber-700"}`}>
                {l.status === "done" ? <CheckCircle2 className="size-3" /> : <Clock className="size-3" />}
                {l.status}
              </span>
            </div>
          ))}
        </div>
        {legs.some((l) => l.status === "stuck") && (
          <div className="mt-3 rounded-md border border-red-300/50 bg-red-500/5 p-3 text-xs text-red-700">
            <span className="font-medium">Compost is stuck.</span> We've nudged Market Garden twice. If it doesn't move, it goes to arbitration.
          </div>
        )}
      </div>
    </div>
  )
}

export default function NeedsOffersMockup() {
  const [view, setView] = useState<"board" | "weave" | "loops">("weave")
  const tabs = [
    { id: "weave", label: "Weave" },
    { id: "board", label: "Have & need" },
    { id: "loops", label: "Loops" },
  ] as const
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 rounded-lg border bg-card p-1 shadow-sm">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setView(t.id)} className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium ${view === t.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"}`}>
            {t.label}
          </button>
        ))}
      </div>
      {view === "weave" && <Weave />}
      {view === "board" && <Board />}
      {view === "loops" && <Loops />}
    </div>
  )
}
