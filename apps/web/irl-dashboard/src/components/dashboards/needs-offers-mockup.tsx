"use client"

import { useState } from "react"
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  CircleDashed,
  Filter,
  Plus,
  Scale,
  Truck,
} from "lucide-react"

// Static mockup of the needs/offers matching interaction model — no backend.
// Mirrors the stack-health component's declared/actual/drift language and card
// patterns. Data is illustrative only.

type NeedOffer = {
  id: string
  kind: "need" | "offer"
  title: string
  group: string
  category: string
  badge: string
  visibility: "open" | "members"
}

const NEEDS_OFFERS: NeedOffer[] = [
  { id: "n1", kind: "offer", title: "4 m³ cold storage — 30 days", group: "Cold Storage Co-op", category: "space", badge: "trusted · ≥3 trades", visibility: "open" },
  { id: "n2", kind: "need", title: "Compost for spring beds", group: "Cold Storage Co-op", category: "produce", badge: "trusted · ≥3 trades", visibility: "open" },
  { id: "n3", kind: "offer", title: "2 t finished compost", group: "Market Garden Collective", category: "produce", badge: "≥1 trade", visibility: "members" },
  { id: "n4", kind: "need", title: "Open-pollinated seed", group: "Market Garden Collective", category: "produce", badge: "≥1 trade", visibility: "members" },
  { id: "n5", kind: "offer", title: "40 kg seed (veg + cover crop)", group: "Seed Cooperative", category: "produce", badge: "trusted · ≥3 trades", visibility: "open" },
  { id: "n6", kind: "need", title: "Winter cold storage", group: "Seed Cooperative", category: "space", badge: "trusted · ≥3 trades", visibility: "open" },
  { id: "n7", kind: "offer", title: "Box truck — weekend hauling", group: "Tool Share", category: "transport", badge: "≥1 trade", visibility: "open" },
]

type Leg = {
  from: string
  to: string
  what: string
  declared: string
  status: "received" | "in_transit" | "confirmed" | "stuck"
}

const CHAIN: { id: string; legs: Leg[] } = {
  id: "chain-9f3a",
  legs: [
    { from: "Cold Storage Co-op", to: "Market Garden Collective", what: "4 m³ cold storage · 30 days", declared: "storage for 10 credit", status: "received" },
    { from: "Market Garden Collective", to: "Seed Cooperative", what: "2 t finished compost", declared: "compost for 8 credit", status: "stuck" },
    { from: "Seed Cooperative", to: "Cold Storage Co-op", what: "40 kg seed", declared: "seed for 10 credit", status: "received" },
  ],
}

const TIMELINE = [
  { at: "Mon 09:12", event: "trade.proposed", note: "Matcher found the A→B→C→A cycle" },
  { at: "Mon 09:40", event: "trade.leg_confirmed", note: "L1 · Cold Storage → Market Garden" },
  { at: "Mon 10:02", event: "trade.leg_confirmed", note: "L2 · Market Garden → Seed Co-op" },
  { at: "Mon 10:15", event: "trade.leg_confirmed", note: "L3 · Seed Co-op → Cold Storage" },
  { at: "Tue 08:30", event: "trade.in_transit", note: "L1 · storage keys handed over" },
  { at: "Tue 14:05", event: "trade.leg_received", note: "L1 · confirmed by Market Garden" },
  { at: "Wed 11:20", event: "trade.leg_received", note: "L3 · seed delivered to Cold Storage" },
  { at: "Thu 09:00", event: "trade.stuck", note: "L2 · compost window passed — nudge 1 sent" },
]

const STATUS_STYLES: Record<Leg["status"], { dot: string; label: string; chip: string }> = {
  received: { dot: "bg-emerald-500", label: "received", chip: "bg-emerald-500/10 text-emerald-700" },
  in_transit: { dot: "bg-amber-500", label: "in transit", chip: "bg-amber-500/10 text-amber-700" },
  confirmed: { dot: "bg-sky-500", label: "confirmed", chip: "bg-sky-500/10 text-sky-700" },
  stuck: { dot: "bg-red-500", label: "stuck", chip: "bg-red-500/10 text-red-700" },
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">{children}</h2>
}

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
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium ${
              filter === k ? "bg-primary text-primary-foreground" : "border bg-background text-muted-foreground hover:bg-accent"
            }`}
          >
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
              <span
                className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${
                  n.kind === "offer" ? "bg-emerald-500/10 text-emerald-700" : "bg-sky-500/10 text-sky-700"
                }`}
              >
                {n.kind === "offer" ? "offer" : "need"}
              </span>
              {n.visibility === "members" && (
                <span className="text-[11px] text-muted-foreground">members</span>
              )}
            </div>
            <p className="mt-2 text-sm font-medium">{n.title}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{n.category}</p>
            <div className="mt-3 flex items-center justify-between border-t pt-2">
              <span className="truncate font-mono text-[11px] text-muted-foreground">{n.group}</span>
              <span className="inline-flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground">
                <BadgeCheck className="size-3.5 text-emerald-500" />
                {n.badge}
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-muted-foreground">
        The badge is a zk-proof over completion history — it shows the trust floor met, never the raw record.
      </p>
    </div>
  )
}

function ChainView() {
  const settled = CHAIN.legs.filter((l) => l.status === "received").length
  const inFlight = CHAIN.legs.filter((l) => l.status === "in_transit" || l.status === "confirmed").length
  const drift = CHAIN.legs.filter((l) => l.status === "stuck").length
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs text-muted-foreground"><CheckCircle2 className="size-3.5" /> Declared legs</div>
          <div className="mt-1 text-2xl font-semibold">{CHAIN.legs.length}</div>
          <div className="text-xs text-muted-foreground">the agreed cycle</div>
        </div>
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs text-muted-foreground"><CheckCircle2 className="size-3.5" /> Settled</div>
          <div className="mt-1 text-2xl font-semibold">{settled}</div>
          <div className="text-xs text-muted-foreground">received + ledger written</div>
        </div>
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs text-muted-foreground"><Truck className="size-3.5" /> In flight</div>
          <div className="mt-1 text-2xl font-semibold">{inFlight}</div>
          <div className="text-xs text-muted-foreground">confirmed / in transit</div>
        </div>
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs text-muted-foreground"><CircleDashed className="size-3.5" /> Drift</div>
          <div className={`mt-1 text-2xl font-semibold ${drift > 0 ? "text-amber-600" : ""}`}>{drift}</div>
          <div className="text-xs text-muted-foreground">actual lags declared</div>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <SectionLabel>The cycle — A → B → C → A</SectionLabel>
        <div className="mt-3 space-y-2">
          {CHAIN.legs.map((l, i) => {
            const s = STATUS_STYLES[l.status]
            return (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-md border p-2.5">
                <span className="inline-flex items-center gap-1 text-xs font-medium">
                  <span className={`size-1.5 rounded-full ${s.dot}`} />
                  {l.from}
                </span>
                <ArrowRight className="size-3.5 text-muted-foreground" />
                <span className="text-xs font-medium">{l.to}</span>
                <span className="mx-1 text-xs text-muted-foreground">{l.what}</span>
                <span className={`ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${s.chip}`}>
                  {s.label}
                </span>
                <span className="w-full text-[11px] text-muted-foreground">declared: {l.declared}</span>
              </div>
            )
          })}
        </div>
        {drift > 0 && (
          <div className="mt-3 rounded-lg border border-amber-300/50 bg-amber-500/5 p-3 text-xs text-amber-700">
            <div className="mb-1 flex items-center gap-1.5 font-medium">
              <AlertTriangle className="size-3.5" /> Drift — L2 (Market Garden → Seed Co-op) is stuck past its window
            </div>
            <p>Actual (confirmed) lags declared (compost delivered). Reconciler emitted trade.stuck; the workflow is nudging.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function TradeDetail() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg border bg-card p-3 shadow-sm">
        <div>
          <span className="font-mono text-sm font-medium">chain-9f3a</span>
          <span className="ml-2 text-xs text-muted-foreground">Cold Storage Co-op · Market Garden Collective · Seed Cooperative</span>
        </div>
        <button className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent">
          <Scale className="size-3.5" /> Escalate to arbitration
        </button>
      </div>

      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <SectionLabel>Timeline — leg events</SectionLabel>
        <div className="mt-3 space-y-0">
          {TIMELINE.map((t, i) => (
            <div key={i} className="relative flex gap-3 pb-4 last:pb-0">
              <div className="flex flex-col items-center">
                <span className={`mt-1 size-2 rounded-full ${t.event === "trade.stuck" ? "bg-red-500" : "bg-emerald-500"}`} />
                {i < TIMELINE.length - 1 && <span className="w-px flex-1 bg-border" />}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs">{t.event}</span>
                  <span className="text-[11px] text-muted-foreground">{t.at}</span>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{t.note}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-red-300/50 bg-red-500/5 p-3 text-sm">
        <div className="flex items-center gap-2 font-medium text-red-700">
          <AlertTriangle className="size-4" /> Leg 2 is stuck
        </div>
        <p className="mt-1 text-xs text-red-700/80">
          Market Garden Collective hasn't shipped 2 t compost to Seed Cooperative. Nudge 1 of 2 sent Thu 09:00 —
          after the next nudge the workflow escalates to arbitration automatically.
        </p>
        <div className="mt-3 flex gap-2">
          <button className="rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90">Nudge parties</button>
          <button className="rounded-md border bg-background px-2.5 py-1 text-[11px] font-medium hover:bg-accent">Mark as received</button>
        </div>
      </div>
    </div>
  )
}

export default function NeedsOffersMockup() {
  const [view, setView] = useState<"board" | "chain" | "detail">("board")
  const tabs = [
    { id: "board", label: "Needs & offers" },
    { id: "chain", label: "Trade chain" },
    { id: "detail", label: "Detail / expediting" },
  ] as const
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 rounded-lg border bg-card p-1 shadow-sm">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setView(t.id)}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium ${
              view === t.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {view === "board" && <Board />}
      {view === "chain" && <ChainView />}
      {view === "detail" && <TradeDetail />}
    </div>
  )
}
