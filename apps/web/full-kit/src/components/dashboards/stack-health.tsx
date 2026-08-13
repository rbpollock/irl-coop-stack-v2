"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useSession } from "next-auth/react"
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleDashed,
  RefreshCw,
  Server,
} from "lucide-react"

// Stack health — declared-vs-running reconciler fed by coop-api
// (GET /api/v1/stack/status). The tree in infra/instances/dev/ is the
// declared state; docker is the running state; the difference is drift.
const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const POLL_MS = 30_000

type ContainerView = {
  name: string
  state: string
  status: string
  health: string | null
  image: string
  ports: string
}

type ServiceView = {
  service: string
  container: ContainerView | null
}

type PillarView = {
  id: string
  pillar: string
  kind: "tree" | "source"
  compose: string
  declared: number
  up: number
  down: number
  missing: string[]
  services: ServiceView[]
}

type BrowserRunnerView = {
  name: string
  state: string
  status: string
  scenario: string | null
}

type StackStatus = {
  generated_at: string
  stack_root: string
  summary: {
    declared: number
    containers: number
    up: number
    down: number
    healthy: number
    orphans: number
  }
  browser_runners: {
    active: number
    total: number
    instances: BrowserRunnerView[]
  }
  pillars: PillarView[]
  orphans: { name: string; image: string; state: string; project: string }[]
}

function PillarChip({ pillar }: { pillar: PillarView }) {
  const allUp = pillar.down === 0
  const drifted = pillar.missing.length > 0
  const dot = allUp ? (
    <CheckCircle2 className="size-3.5 text-emerald-500" />
  ) : (
    <AlertTriangle className="size-3.5 text-red-500" />
  )
  return (
    <div className="rounded-lg border bg-card p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {dot}
          <span className="text-sm font-medium">
            {pillar.pillar}
            {pillar.kind === "source" && (
              <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                · source
              </span>
            )}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          {pillar.up}/{pillar.declared} up
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {pillar.services.map((s) => {
          const st = s.container?.state ?? "missing"
          const ok = st === "running"
          return (
            <span
              key={s.service}
              title={
                s.container
                  ? `${s.container.name} · ${s.container.status}`
                  : `${s.service}: declared, not running`
              }
              className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] ${
                ok
                  ? "bg-emerald-500/10 text-emerald-700"
                  : "bg-red-500/10 text-red-700"
              }`}
            >
              <span
                className={`size-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`}
              />
              {s.service}
            </span>
          )
        })}
      </div>
      {drifted && (
        <div className="mt-1.5 text-[11px] text-amber-600">
          missing: {pillar.missing.join(", ")}
        </div>
      )}
    </div>
  )
}

export default function StackHealth() {
  const { data: session } = useSession()
  const [status, setStatus] = useState<StackStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const token = session?.accessToken as string | undefined

  const runRunner = async (scenario: string) => {
    if (!token) return
    try {
      const res = await fetch(`${COOP_API_URL}/api/v1/stack/browser/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ scenario }),
      })
      if (!res.ok) throw new Error(`Failed to start runner (${res.status})`)
      refresh()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const res = await fetch(`${COOP_API_URL}/api/v1/stack/status`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      })
      if (!res.ok) throw new Error(`status failed (${res.status})`)
      setStatus((await res.json()) as StackStatus)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    refresh()
    timer.current = setInterval(refresh, POLL_MS)
    return () => {
      if (timer.current) clearInterval(timer.current)
    }
  }, [refresh])

  const s = status?.summary

  return (
    <div className="grid grid-cols-1 gap-4 md:col-span-full">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Stack health</h3>
        <div className="flex items-center gap-2">
          <a
            href="https://temporal.irl.coop"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent"
          >
            <Activity className="size-3.5 text-muted-foreground" />
            Temporal Dashboard
          </a>
          <button
            onClick={refresh}
            className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent"
          >
            <RefreshCw
              className={`size-3.5 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {error && !status && (
        <div className="rounded-lg border border-amber-300/50 bg-amber-500/5 p-4 text-sm text-amber-700">
          Stack status unavailable — {error}
        </div>
      )}

      {status && s && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Server className="size-3.5" /> Services up
              </div>
              <div className="mt-1 text-2xl font-semibold">{s.up}</div>
              <div className="text-xs text-muted-foreground">
                of {s.declared} declared
              </div>
            </div>
            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <AlertTriangle className="size-3.5" /> Services down
              </div>
              <div
                className={`mt-1 text-2xl font-semibold ${s.down > 0 ? "text-red-600" : ""}`}
              >
                {s.down}
              </div>
              <div className="text-xs text-muted-foreground">
                stopped, exited, missing
              </div>
            </div>
            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <CheckCircle2 className="size-3.5" /> Healthy
              </div>
              <div className="mt-1 text-2xl font-semibold">{s.healthy}</div>
              <div className="text-xs text-muted-foreground">
                healthchecks passing
              </div>
            </div>
            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <CircleDashed className="size-3.5" /> Drift
              </div>
              <div
                className={`mt-1 text-2xl font-semibold ${s.orphans > 0 ? "text-amber-600" : ""}`}
              >
                {s.orphans}
              </div>
              <div className="text-xs text-muted-foreground">
                undeclared containers
              </div>
            </div>
          </div>

          {status.browser_runners && (
            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Bot className="size-3.5" /> Browser runners
                <span className="ml-auto text-xs">
                  <span
                    className={
                      status.browser_runners.active > 0
                        ? "font-medium text-emerald-600"
                        : "text-muted-foreground"
                    }
                  >
                    {status.browser_runners.active} active
                  </span>{" "}
                  · {status.browser_runners.total} total
                </span>
              </div>
              {status.browser_runners.instances.length > 0 ? (
                <div className="mt-2 flex flex-col gap-1">
                  {status.browser_runners.instances.map((r) => (
                    <div
                      key={r.name}
                      className="flex items-center justify-between gap-2 text-xs"
                    >
                      <span className="flex min-w-0 items-center gap-1.5">
                        <span
                          className={`size-1.5 shrink-0 rounded-full ${
                            r.state === "running"
                              ? "bg-emerald-500"
                              : "bg-muted-foreground/40"
                          }`}
                        />
                        <span className="truncate font-mono">
                          {r.scenario ?? "run"}
                        </span>
                      </span>
                      <span className="truncate text-muted-foreground">
                        {r.name} · {r.status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs text-muted-foreground">
                  No instances — the fleet spins them up on demand.
                </p>
              )}
              <div className="mt-3 flex gap-2 border-t pt-3">
                <button
                  onClick={() => runRunner("files-flow")}
                  className="inline-flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Run files-flow
                </button>
                <button
                  onClick={() => runRunner("linking-flow")}
                  className="inline-flex items-center gap-1 rounded border bg-background px-2.5 py-1 text-[11px] font-medium hover:bg-accent"
                >
                  Run linking-flow
                </button>
              </div>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {status.pillars.map((p) => (
              <PillarChip key={p.id} pillar={p} />
            ))}
          </div>

          {status.orphans.length > 0 && (
            <div className="rounded-lg border border-amber-300/50 bg-amber-500/5 p-3 text-xs text-amber-700">
              <div className="mb-1 flex items-center gap-1.5 font-medium">
                <Activity className="size-3.5" /> Orphaned containers (running,
                not declared in the tree)
              </div>
              {status.orphans.map((o) => (
                <div key={o.name} className="flex justify-between gap-2 py-0.5">
                  <span className="font-mono">{o.name}</span>
                  <span className="text-muted-foreground">
                    {o.image} · {o.state}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!status && !error && (
        <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
          Loading stack status…
        </div>
      )}
    </div>
  )
}
