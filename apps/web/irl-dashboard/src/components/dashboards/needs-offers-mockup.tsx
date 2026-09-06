"use client"

import { useState } from "react"
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  CircleDashed,
  Filter,
  Handshake,
  Link2,
  Plus,
  Scale,
  Share2,
  Truck,
  Waypoints,
} from "lucide-react"

// Static mockup of the needs/offers WEAVING interaction — no backend. Mirrors
// the stack-health declared/actual/drift language. The Weave view is the point:
// a weighted network of postings you string into a proposal; gaps are fillable;
// a closed loop becomes a match that rewards the weaver and the counterparties.

type Node = {
  id: string
  group: string
  kind: "need" | "offer"
  title: string
  x: number
  y: number
  location: string
  km: number | null
  missing?: boolean
}

const NODES: Node[] = [
  { id: "cs-storage", group: "Cold Storage Co-op", kind: "offer", title: "4 m³ cold storage", x: 190, y: 66, location: "North barn", km: 12 },
  { id: "cs-compost", group: "Cold Storage Co-op", kind: "need", title: "compost", x: 190, y: 176, location: "North barn", km: 12 },
  { id: "mg-compost", group: "Market Garden", kind: "offer", title: "2 t compost", x: 380, y: 176, location: "East field", km: 9 },
  { id: "mg-seed", group: "Market Garden", kind: "need", title: "seed", x: 380, y: 266, location: "East field", km: 9 },
  { id: "sc-seed", group: "Seed Co-op", kind: "offer", title: "40 kg seed", x: 100, y: 266, location: "South plot", km: 14 },
  { id: "sc-storage", group: "Seed Co-op", kind: "need", title: "winter storage", x: 100, y: 66, location: "South plot", km: 14 },
  { id: "tool-truck", group: "Tool Share", kind: "offer", title: "box truck", x: 520, y: 110, location: "West lot", km: 22 },
  { id: "missing-haul", group: "…", kind: "need", title: "hauling help", x: 520, y: 250, location: "anywhere", km: null, missing: true },
]

type Edge = { from: string; to: string; km: number | null; missing?: boolean }
const EDGES: Edge[] = [
  { from: "cs-storage", to: "sc-storage", km: 12 },
  { from: "sc-seed", to: "mg-seed", km: 14 },
  { from: "mg-compost", to: "cs-compost", km: 9 },
  { from: "tool-truck", to: "missing-haul", km: null, missing: true },
]

// The example cycle — selecting all six closes the loop.
const CYCLE = ["cs-storage", "sc-storage", "sc-seed", "mg-seed", "mg-compost", "cs-compost"]

function Weave() {
  const [selected, setSelected] = useState<string[]>(["cs-storage", "sc-storage", "sc-seed", "mg-seed", "mg-compost"])
  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const linkedEdges = EDGES.filter((e) => selected.includes(e.from) && selected.includes(e.to))
  const closed = CYCLE.every((id) => selected.includes(id))
  const missingSelected = selected.includes("missing-haul") || selected.includes("tool-truck")

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Network space */}
        <div className="lg:col-span-2 rounded-lg border bg-card p-3 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Waypoints className="size-3.5" /> Solution space — string postings into a loop
            </div>
            <button className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent">
              <Share2 className="size-3.5" /> Share &amp; partner
            </button>
          </div>

          <svg viewBox="0 0 600 330" className="mt-2 w-full">
            {/* edges */}
            {EDGES.map((e) => {
              const a = NODES.find((n) => n.id === e.from)!
              const b = NODES.find((n) => n.id === e.to)!
              const active = selected.includes(e.from) && selected.includes(e.to)
              return (
                <g key={`${e.from}-${e.to}`}>
                  <line
                    x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                    stroke={e.missing ? "var(--muted)" : active ? "var(--primary)" : "var(--border)"}
                    strokeWidth={active ? 2.5 : 1.5}
                    strokeDasharray={e.missing || active ? "" : "4 4"}
                    opacity={e.missing ? 0.6 : 1}
                  />
                  {e.km != null && (
                    <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} textAnchor="middle" className="fill-muted-foreground" fontSize="9">
                      {e.km} km
                    </text>
                  )}
                </g>
              )
            })}
            {/* nodes */}
            {NODES.map((n) => {
              const on = selected.includes(n.id)
              const fill = n.missing ? "var(--card)" : n.kind === "offer" ? "var(--emerald-500, #10b981)" : "var(--sky-500, #0ea5e9)"
              return (
                <g key={n.id} onClick={() => toggle(n.id)} className="cursor-pointer">
                  {n.missing ? (
                    <circle cx={n.x} cy={n.y} r={22} fill={fill} stroke="var(--border)" strokeWidth={1.5} strokeDasharray="4 4" />
                  ) : (
                    <circle cx={n.x} cy={n.y} r={22} fill={fill} opacity={on ? 1 : 0.55} />
                  )}
                  {on && <circle cx={n.x} cy={n.y} r={27} fill="none" stroke="var(--primary)" strokeWidth={2} />}
                  <text x={n.x} y={n.y + 3} textAnchor="middle" fontSize="9" fill={n.missing ? "var(--muted-foreground)" : "white"} fontWeight={600}>
                    {n.kind === "offer" ? "+" : "−"}
                  </text>
                  <text x={n.x} y={n.y + 40} textAnchor="middle" fontSize="9" className="fill-foreground" fontWeight={500}>
                    {n.title}
                  </text>
                  <text x={n.x} y={n.y + 52} textAnchor="middle" fontSize="8" className="fill-muted-foreground">
                    {n.group} · {n.location}
                  </text>
                </g>
              )
            })}
          </svg>

          <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-emerald-500" /> offer</span>
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-sky-500" /> need</span>
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full border border-dashed border-muted-foreground" /> missing part</span>
            <span className="ml-auto">tap nodes to string them</span>
          </div>
        </div>

        {/* Compose / status rail */}
        <div className="space-y-3">
          <div className="rounded-lg border bg-card p-4 shadow-sm">
            <SectionLabel>Your proposal</SectionLabel>
            <div className="mt-2 text-sm">
              <span className="font-semibold">{selected.length}</span> pieces ·{" "}
              <span className="font-semibold">{linkedEdges.length}</span> links
            </div>
            <div className={`mt-2 rounded-md px-2.5 py-2 text-xs font-medium ${closed ? "bg-emerald-500/10 text-emerald-700" : "bg-amber-500/10 text-amber-700"}`}>
              {closed
                ? "✓ Loop closed — a 3-leg cycle. Propose it."
                : linkedEdges.length === 0
                  ? "No matches yet — string an offer to a need."
                  : `Open loop — ${CYCLE.length - selected.length} piece${CYCLE.length - selected.length === 1 ? "" : "s"} missing to close.`}
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <button disabled={!closed} className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground disabled:opacity-40 hover:bg-primary/90">
                <Link2 className="size-3.5" /> Propose this match
              </button>
              <button className="inline-flex items-center justify-center gap-1.5 rounded-md border bg-background px-3 py-2 text-xs font-medium hover:bg-accent">
                <Handshake className="size-3.5" /> Respond with a simple match
              </button>
            </div>
          </div>

          {missingSelected && (
            <div className="rounded-lg border border-dashed bg-card p-4 shadow-sm">
              <SectionLabel>Fill the gap yourself</SectionLabel>
              <p className="mt-2 text-xs text-muted-foreground">
                “hauling help” has no offer yet. You can post your own offer to close this loop — no permission needed.
              </p>
              <button className="mt-2 inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-[11px] font-medium hover:bg-accent">
                <Plus className="size-3.5" /> Post an offer for hauling
              </button>
            </div>
          )}

          {closed && (
            <div className="rounded-lg border border-emerald-300/50 bg-emerald-500/5 p-4 shadow-sm">
              <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
                <CheckCircle2 className="size-4" /> Reward on settle
              </div>
              <p className="mt-1 text-xs text-emerald-700/80">
                irl.coop rewards everyone on a settled match: <span className="font-medium">you (weaver)</span>,{" "}
                <span className="font-medium">Cold Storage Co-op</span>, <span className="font-medium">Market Garden</span>,{" "}
                <span className="font-medium">Seed Co-op</span>.
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-lg border bg-card p-3 shadow-sm">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <BadgeCheck className="size-3.5 text-emerald-500" /> Your match badge — “≥3 closed · 0% false” (zk-proof over track record)
          <span className="ml-auto text-[11px]">ceilings: 4-party · 3 legs · up to 5,000 value</span>
        </div>
      </div>
    </div>
  )
}

type NeedOffer = { id: string; kind: "need" | "offer"; title: string; group: string; category: string; badge: string; visibility: "open" | "members" }

const NEEDS_OFFERS: NeedOffer[] = [
  { id: "n1", kind: "offer", title: "4 m³ cold storage — 30 days", group: "Cold Storage Co-op", category: "space", badge: "≥3 trades", visibility: "open" },
  { id: "n2", kind: "need", title: "Compost for spring beds", group: "Cold Storage Co-op", category: "produce", badge: "≥3 trades", visibility: "open" },
  { id: "n3", kind: "offer", title: "2 t finished compost", group: "Market Garden Collective", category: "produce", badge: "≥1 trade", visibility: "members" },
  { id: "n4", kind: "need", title: "Open-pollinated seed", group: "Market Garden Collective", category: "produce", badge: "≥1 trade", visibility: "members" },
  { id: "n5", kind: "offer", title: "40 kg seed (veg + cover crop)", group: "Seed Cooperative", category: "produce", badge: "≥3 trades", visibility: "open" },
  { id: "n6", kind: "need", title: "Winter cold storage", group: "Seed Cooperative", category: "space", badge: "≥3 trades", visibility: "open" },
  { id: "n7", kind: "offer", title: "Box truck — weekend hauling", group: "Tool Share", category: "transport", badge: "≥1 trade", visibility: "open" },
]

function Board() {
  const [filter, setFilter] = useState<"all" | "need" | "offer">("all")
  const items = NEEDS_OFFERS.filter((n) => filter === "all" || n.kind === filter)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent">
          <Filter className="size-3.5" /> All groups
        </button>
        {(["all", "need", "offer"] as const).map((k) => (
          <button key={k} onClick={() => setFilter(k)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${filter === k ? "bg-primary text-primary-foreground" : "border bg-background text-muted-foreground hover:bg-accent"}`}>
            {k === "all" ? "All" : k === "need" ? "Needs" : "Offers"}
          </button>
        ))}
        <button className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90">
          <Plus className="size-3.5" /> Post a need / offer
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((n) => (
          <div key={n.id} className="rounded-lg border bg-card p-3 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${n.kind === "offer" ? "bg-emerald-500/10 text-emerald-700" : "bg-sky-500/10 text-sky-700"}`}>
                {n.kind}
              </span>
              {n.visibility === "members" && <span className="text-[11px] text-muted-foreground">members</span>}
            </div>
            <p className="mt-2 text-sm font-medium">{n.title}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{n.category}</p>
            <div className="mt-3 flex items-center justify-between border-t pt-2">
              <span className="truncate font-mono text-[11px] text-muted-foreground">{n.group}</span>
              <span className="inline-flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground">
                <BadgeCheck className="size-3.5 text-emerald-500" /> {n.badge}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

type Leg = { from: string; to: string; what: string; declared: string; status: "received" | "in_transit" | "confirmed" | "stuck" }
const CHAIN: { id: string; legs: Leg[] } = {
  id: "chain-9f3a",
  legs: [
    { from: "Cold Storage Co-op", to: "Market Garden Collective", what: "4 m³ cold storage · 30 days", declared: "storage for 10 credit", status: "received" },
    { from: "Market Garden Collective", to: "Seed Cooperative", what: "2 t finished compost", declared: "compost for 8 credit", status: "stuck" },
    { from: "Seed Cooperative", to: "Cold Storage Co-op", what: "40 kg seed", declared: "seed for 10 credit", status: "received" },
  ],
}
const STATUS_STYLES: Record<Leg["status"], { dot: string; label: string; chip: string }> = {
  received: { dot: "bg-emerald-500", label: "received", chip: "bg-emerald-500/10 text-emerald-700" },
  in_transit: { dot: "bg-amber-500", label: "in transit", chip: "bg-amber-500/10 text-amber-700" },
  confirmed: { dot: "bg-sky-500", label: "confirmed", chip: "bg-sky-500/10 text-sky-700" },
  stuck: { dot: "bg-red-500", label: "stuck", chip: "bg-red-500/10 text-red-700" },
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">{children}</h2>
}

function ChainView() {
  const settled = CHAIN.legs.filter((l) => l.status === "received").length
  const inFlight = CHAIN.legs.filter((l) => l.status === "in_transit" || l.status === "confirmed").length
  const drift = CHAIN.legs.filter((l) => l.status === "stuck").length
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border bg-card p-4 shadow-sm"><div className="flex items-center gap-2 text-xs text-muted-foreground"><CheckCircle2 className="size-3.5" /> Declared legs</div><div className="mt-1 text-2xl font-semibold">{CHAIN.legs.length}</div><div className="text-xs text-muted-foreground">the agreed cycle</div></div>
        <div className="rounded-lg border bg-card p-4 shadow-sm"><div className="flex items-center gap-2 text-xs text-muted-foreground"><CheckCircle2 className="size-3.5" /> Settled</div><div className="mt-1 text-2xl font-semibold">{settled}</div><div className="text-xs text-muted-foreground">received + ledger written</div></div>
        <div className="rounded-lg border bg-card p-4 shadow-sm"><div className="flex items-center gap-2 text-xs text-muted-foreground"><Truck className="size-3.5" /> In flight</div><div className="mt-1 text-2xl font-semibold">{inFlight}</div><div className="text-xs text-muted-foreground">confirmed / in transit</div></div>
        <div className="rounded-lg border bg-card p-4 shadow-sm"><div className="flex items-center gap-2 text-xs text-muted-foreground"><CircleDashed className="size-3.5" /> Drift</div><div className={`mt-1 text-2xl font-semibold ${drift > 0 ? "text-amber-600" : ""}`}>{drift}</div><div className="text-xs text-muted-foreground">actual lags declared</div></div>
      </div>
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <SectionLabel>The cycle — A → B → C → A</SectionLabel>
        <div className="mt-3 space-y-2">
          {CHAIN.legs.map((l, i) => {
            const s = STATUS_STYLES[l.status]
            return (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-md border p-2.5">
                <span className="inline-flex items-center gap-1 text-xs font-medium"><span className={`size-1.5 rounded-full ${s.dot}`} />{l.from}</span>
                <ArrowRight className="size-3.5 text-muted-foreground" />
                <span className="text-xs font-medium">{l.to}</span>
                <span className="mx-1 text-xs text-muted-foreground">{l.what}</span>
                <span className={`ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${s.chip}`}>{s.label}</span>
                <span className="w-full text-[11px] text-muted-foreground">declared: {l.declared}</span>
              </div>
            )
          })}
        </div>
        {drift > 0 && (
          <div className="mt-3 rounded-lg border border-amber-300/50 bg-amber-500/5 p-3 text-xs text-amber-700">
            <div className="mb-1 flex items-center gap-1.5 font-medium"><AlertTriangle className="size-3.5" /> Drift — L2 (Market Garden → Seed Co-op) is stuck past its window</div>
            <p>Actual (confirmed) lags declared (compost delivered). Reconciler emitted trade.stuck; the workflow is nudging.</p>
          </div>
        )}
      </div>
    </div>
  )
}

const TIMELINE = [
  { at: "Mon 09:12", event: "trade.match_proposed", note: "Maria proposed the matched-by edge" },
  { at: "Mon 09:40", event: "trade.leg_confirmed", note: "L1 · Cold Storage → Market Garden" },
  { at: "Mon 10:02", event: "trade.leg_confirmed", note: "L2 · Market Garden → Seed Co-op" },
  { at: "Mon 10:15", event: "trade.leg_confirmed", note: "L3 · Seed Co-op → Cold Storage" },
  { at: "Tue 14:05", event: "trade.leg_received", note: "L1 · confirmed by Market Garden" },
  { at: "Wed 11:20", event: "trade.leg_received", note: "L3 · seed delivered to Cold Storage" },
  { at: "Thu 09:00", event: "trade.stuck", note: "L2 · compost window passed — nudge 1 sent" },
]

function TradeDetail() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg border bg-card p-3 shadow-sm">
        <div><span className="font-mono text-sm font-medium">chain-9f3a</span><span className="ml-2 text-xs text-muted-foreground">weaver: Maria · 3 counterparties</span></div>
        <button className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent"><Scale className="size-3.5" /> Escalate to arbitration</button>
      </div>
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <SectionLabel>Timeline — leg events</SectionLabel>
        <div className="mt-3 space-y-0">
          {TIMELINE.map((t, i) => (
            <div key={i} className="relative flex gap-3 pb-4 last:pb-0">
              <div className="flex flex-col items-center"><span className={`mt-1 size-2 rounded-full ${t.event === "trade.stuck" ? "bg-red-500" : "bg-emerald-500"}`} />{i < TIMELINE.length - 1 && <span className="w-px flex-1 bg-border" />}</div>
              <div className="min-w-0"><div className="flex items-center gap-2"><span className="font-mono text-xs">{t.event}</span><span className="text-[11px] text-muted-foreground">{t.at}</span></div><p className="mt-0.5 text-xs text-muted-foreground">{t.note}</p></div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-red-300/50 bg-red-500/5 p-3 text-sm">
        <div className="flex items-center gap-2 font-medium text-red-700"><AlertTriangle className="size-4" /> Leg 2 is stuck</div>
        <p className="mt-1 text-xs text-red-700/80">Market Garden Collective hasn't shipped 2 t compost to Seed Cooperative. Nudge 1 of 2 sent — after the next nudge the workflow escalates to arbitration automatically.</p>
        <div className="mt-3 flex gap-2"><button className="rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90">Nudge parties</button><button className="rounded-md border bg-background px-2.5 py-1 text-[11px] font-medium hover:bg-accent">Mark as received</button></div>
      </div>
    </div>
  )
}

export default function NeedsOffersMockup() {
  const [view, setView] = useState<"weave" | "board" | "chain" | "detail">("weave")
  const tabs = [
    { id: "weave", label: "Weave" },
    { id: "board", label: "Needs & offers" },
    { id: "chain", label: "Trade chain" },
    { id: "detail", label: "Detail / expediting" },
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
      {view === "chain" && <ChainView />}
      {view === "detail" && <TradeDetail />}
    </div>
  )
}
