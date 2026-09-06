"use client"

import { useState } from "react"
import {
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  Clock,
  Plus,
  Repeat,
} from "lucide-react"

// Needs/offers — three plain ideas, nothing else:
//   1. what people have & need  2. put them together  3. did it happen
// The machinery (bond, badge ceilings, arbitrar) stays in the spec, off-screen.

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
  const [mine, setMine] = useState<string[]>([])
  const toggle = (id: string) => setMine((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90">
          <Plus className="size-3.5" /> Post something
        </button>
        <span className="ml-auto text-xs text-muted-foreground">
          {mine.length > 0 ? `${mine.length} in your match` : "tap things to build a match"}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {ITEMS.map((it) => (
          <button
            key={it.id}
            onClick={() => toggle(it.id)}
            className={`rounded-lg border bg-card p-3 text-left shadow-sm transition-colors ${
              mine.includes(it.id) ? "border-primary ring-1 ring-primary/30" : "hover:bg-accent/40"
            }`}
          >
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
            <p className="mt-1 text-xs text-muted-foreground">
              {it.group} · {it.km} km
            </p>
          </button>
        ))}
      </div>
    </div>
  )
}

function Match() {
  const [missing, setMissing] = useState(false)
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={() => setMissing(false)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${!missing ? "bg-primary text-primary-foreground" : "border bg-background text-muted-foreground hover:bg-accent"}`}>
          It fits
        </button>
        <button onClick={() => setMissing(true)} className={`rounded-md px-2.5 py-1 text-xs font-medium ${missing ? "bg-primary text-primary-foreground" : "border bg-background text-muted-foreground hover:bg-accent"}`}>
          Something's missing
        </button>
      </div>

      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">The loop</h3>
          <button className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent">
            <Repeat className="size-3.5" /> Simple 1-to-1 instead
          </button>
        </div>

        {!missing ? (
          <svg viewBox="0 0 600 180" className="mt-3 w-full">
            <g>
              <line x1="300" y1="40" x2="520" y2="130" stroke="var(--primary)" strokeWidth="2" />
              <line x1="520" y1="130" x2="80" y2="130" stroke="var(--primary)" strokeWidth="2" />
              <line x1="80" y1="130" x2="300" y2="40" stroke="var(--primary)" strokeWidth="2" />
              <text x="420" y="80" textAnchor="middle" fontSize="9" className="fill-muted-foreground">gives</text>
              <text x="300" y="150" textAnchor="middle" fontSize="9" className="fill-muted-foreground">gives</text>
              <text x="180" y="78" textAnchor="middle" fontSize="9" className="fill-muted-foreground">gives</text>
              {[
                ["Cold Storage Co-op", "has storage", 300, 28],
                ["Market Garden", "has compost", 540, 160],
                ["Seed Co-op", "has seed", 60, 160],
              ].map(([g, s, x, y]) => (
                <g key={g as string}>
                  <circle cx={x as number} cy={y as number} r={26} fill="var(--emerald-500, #10b981)" />
                  <text x={x as number} y={y as number} textAnchor="middle" fontSize="9" fill="white" fontWeight={600}>{g as string}</text>
                  <text x={x as number} y={(y as number) + 38} textAnchor="middle" fontSize="9" className="fill-foreground">{s as string}</text>
                </g>
              ))}
            </g>
          </svg>
        ) : (
          <div className="mt-3 rounded-md border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Something's missing</p>
            <p className="mt-1">Tool Share has a truck, but nobody needs hauling yet.</p>
            <button className="mt-3 inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-xs font-medium hover:bg-accent">
              <Plus className="size-3.5" /> I can fill this
            </button>
          </div>
        )}

        {!missing && (
          <div className="mt-3 rounded-lg border border-emerald-300/50 bg-emerald-500/5 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
              <CheckCircle2 className="size-4" /> Everyone gets rewarded
            </div>
            <p className="mt-1 text-xs text-emerald-700/80">
              When this closes, all three groups — and you for putting it together — get a reward from irl.coop.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function Track() {
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
              <span
                className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${
                  l.status === "done" ? "bg-emerald-500/10 text-emerald-700" : l.status === "stuck" ? "bg-red-500/10 text-red-700" : "bg-amber-500/10 text-amber-700"
                }`}
              >
                {l.status === "done" ? <CheckCircle2 className="size-3" /> : l.status === "stuck" ? <Clock className="size-3" /> : <Clock className="size-3" />}
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
  const [view, setView] = useState<"board" | "match" | "track">("board")
  const tabs = [
    { id: "board", label: "Have & need" },
    { id: "match", label: "Match" },
    { id: "track", label: "Track" },
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
      {view === "board" && <Board />}
      {view === "match" && <Match />}
      {view === "track" && <Track />}
    </div>
  )
}
