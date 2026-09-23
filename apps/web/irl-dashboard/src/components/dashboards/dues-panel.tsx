"use client"

import { useCallback, useEffect, useState } from "react"
import {
  adoptDuesPolicy,
  getDuesPolicy,
  getDuesSummary,
  getMyDues,
  grantWaiver,
  listMyGroups,
} from "@/app/[lang]/(dashboard-layout)/dashboards/dues/_lib/dues"
import { useSession } from "next-auth/react"
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Coins,
  MinusCircle,
  RefreshCw,
  Scale,
  Users,
} from "lucide-react"

import type {
  DuesPolicyView,
  DuesSummary,
  Group,
  MyDues,
} from "@/app/[lang]/(dashboard-layout)/dashboards/dues/_lib/dues"

// Dues — "dues satisfied" is a PROJECTION over records in different tiers, not a stored
// fact (docs/design/tier2-entry-model.md §5.1). Three things the UI must get right:
//
//   1. THREE STATES, NOT TWO. An obligation resting on a mode with no source of truth yet
//      (money / coverage) renders as "undetermined" with the reason. Showing it as unmet
//      would tell a member they owe something on the strength of a system that cannot see.
//   2. A MEMBER SEES THEIR OWN MODES; nobody else does. `via` arrives only on /dues/me, and
//      even here the copy never frames a mode as a standing — "satisfied via participation"
//      states a fact about this period, it does not rank anyone.
//   3. THE GROUP GETS A COUNT. There is no roster to render, and the panel says so rather
//      than leaving a suspicious gap.

const gradient = "from-amber-500 to-orange-600"

export default function DuesPanel() {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined

  const [groups, setGroups] = useState<Group[]>([])
  const [groupId, setGroupId] = useState<string>("")
  const [mine, setMine] = useState<MyDues | null>(null)
  const [policy, setPolicy] = useState<DuesPolicyView | null>(null)
  const [summary, setSummary] = useState<DuesSummary | null>(null)
  const [state, setState] = useState<
    "idle" | "loading" | "nopolicy" | "ready" | "error"
  >("idle")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [showWaiver, setShowWaiver] = useState(false)
  const [waiver, setWaiver] = useState({ sub: "", obligation: "", period: "" })
  const [decisionId, setDecisionId] = useState("")

  useEffect(() => {
    if (!token) return
    listMyGroups(token)
      .then((g) => {
        // /api/v1/groups returns groups you can SEE, which includes open groups you are not
        // a member of — and dues require membership. A seat (a non-empty `roles`) is the
        // signal; picking g[0] blindly lands on a group and then 403s.
        const seated = g.filter((x) => (x.roles?.length ?? 0) > 0)
        setGroups(seated)
        if (seated.length && !groupId) setGroupId(seated[0].id)
      })
      .catch((e) => {
        setError(e.message)
        setState("error")
      })
  }, [token, groupId])

  const load = useCallback(async () => {
    if (!token || !groupId) return
    setState("loading")
    setError(null)
    try {
      const [m, p] = await Promise.all([
        getMyDues(token, groupId),
        getDuesPolicy(token, groupId),
      ])
      setMine(m)
      setPolicy(p)
      getDuesSummary(token, groupId)
        .then(setSummary)
        .catch(() => setSummary(null))
      setState("ready")
    } catch (e) {
      const err = e as Error & { status?: number }
      // 404 is not a failure here: it means the group has not set a policy yet
      if (err.status === 404) {
        setState("nopolicy")
        setError(null)
      } else {
        setError(err.message)
        setState("error")
      }
    }
  }, [token, groupId])

  useEffect(() => {
    void load()
  }, [load])

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label)
    setFlash(null)
    try {
      const out = await fn()
      setFlash(
        typeof out === "object" && out && "next" in out
          ? String((out as { next: string }).next)
          : "Done."
      )
      await load()
    } catch (e) {
      setFlash((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  if (!token) {
    return (
      <Shell>
        <p className="text-sm text-muted-foreground">
          Sign in to see your dues.
        </p>
      </Shell>
    )
  }

  return (
    <Shell>
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={groupId}
          onChange={(e) => setGroupId(e.target.value)}
          className="rounded-md border border-border bg-card px-3 py-2 text-sm"
        >
          {groups.length === 0 && <option value="">No groups yet</option>}
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
        <button
          onClick={() => void load()}
          className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-2 text-sm"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
        {policy?.active && (
          <span className="text-xs text-muted-foreground">
            policy v{policy.active.version} · {policy.active.cadence} · grace{" "}
            {policy.active.grace_days}d
            {policy.active.decided_by
              ? " · adopted by decision"
              : " · adopted before decisions were linked"}
          </span>
        )}
        {policy?.drafts?.length ? (
          <span className="text-xs text-muted-foreground">
            v{policy.drafts[0].version} drafted, awaiting a decision
          </span>
        ) : null}
      </div>

      {state === "loading" && (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}

      {state === "idle" && groups.length === 0 && (
        <p className="text-sm text-muted-foreground">
          You are not seated in any group yet, so there is nothing owed either
          way. Start or join a group and its dues policy will appear here.
        </p>
      )}

      {state === "nopolicy" && (
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm font-medium">
            This group has not set a dues policy yet.
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Nothing is owed and nothing is owed <em>to</em> you until it does. A
            policy is a short table — obligations, each satisfied by any of
            several modes — and adopting one takes a decision.
          </p>
        </div>
      )}

      {state === "error" && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {state === "ready" && mine && (
        <>
          <section className="rounded-lg border border-border">
            <header className="flex items-center gap-2 border-b border-border px-4 py-3">
              <Scale className="h-4 w-4" />
              <h3 className="text-sm font-semibold">Your dues</h3>
              <span className="ml-auto text-xs text-muted-foreground">
                {mine.periods[0]?.start} → {mine.periods[0]?.end}
              </span>
            </header>
            <ul className="divide-y divide-border">
              {mine.obligations.map((o) => (
                <li key={o.id} className="flex items-start gap-3 px-4 py-3">
                  {o.satisfied ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                  ) : o.undetermined ? (
                    <CircleDashed className="mt-0.5 h-4 w-4 text-amber-500" />
                  ) : (
                    <MinusCircle className="mt-0.5 h-4 w-4 text-muted-foreground" />
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{o.id}</p>
                    {o.satisfied && o.via && (
                      <p className="text-xs text-muted-foreground">
                        satisfied by {o.via} this period
                      </p>
                    )}
                    {o.satisfied && !o.via && (
                      <p className="text-xs text-muted-foreground">satisfied</p>
                    )}
                    {o.undetermined && (
                      <p className="text-xs text-amber-600">
                        cannot be checked yet —{" "}
                        {o.modes
                          .map((m) => ("detail" in m ? m.detail : null))
                          .filter(Boolean)[0] ??
                          "no source of truth for this mode"}
                      </p>
                    )}
                    {!o.satisfied && !o.undetermined && (
                      <p className="text-xs text-muted-foreground">
                        not satisfied this period
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            {mine.note && (
              <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
                {mine.note}
              </p>
            )}
          </section>

          <section className="rounded-lg border border-border p-4">
            <h3 className="text-sm font-semibold">
              What you can show someone else
            </h3>
            <p className="mt-1 text-2xl font-semibold">
              {mine.statement.obligations_satisfied}
              <span className="text-base font-normal text-muted-foreground">
                {" "}
                / {mine.statement.obligations_total} obligations
              </span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              A statement for policy v{mine.statement.policy_version},{" "}
              {mine.statement.period_start} → {mine.statement.period_end}. It
              carries a count and nothing else — not which mode, not an amount —
              so a sliding scale cannot become a visible ladder.
            </p>
            <p className="mt-2 flex items-center gap-2 text-xs text-amber-600">
              <AlertTriangle className="h-3.5 w-3.5" />
              {mine.statement.signed
                ? "Signed by the group."
                : "Unsigned today — a record of status, not yet a proof anyone can verify."}
            </p>
          </section>

          <section className="rounded-lg border border-border p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Users className="h-4 w-4" /> The group
            </h3>
            {summary ? (
              <>
                <p className="mt-1 text-sm">
                  {summary.waivers_total === 0
                    ? "No waivers this period."
                    : `${summary.waivers_total} waiver${summary.waivers_total === 1 ? "" : "s"} this period`}
                  {summary.waivers.length > 0 && (
                    <span className="text-muted-foreground">
                      {" "}
                      (
                      {summary.waivers
                        .map((w) => `${w.obligation} ×${w.n}`)
                        .join(", ")}
                      )
                    </span>
                  )}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Counts only. Which mode satisfied which member is not exposed
                  to the group — including to you.
                </p>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">
                No summary available — dues are visible to members of the group.
              </p>
            )}
          </section>

          {mine.can_bookkeep && (
            <section className="rounded-lg border border-border p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <Coins className="h-4 w-4" /> Bookkeeping
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                You hold <code>dues.bookkeep</code>. Waivers are bounded by the
                policy, and you cannot grant one to yourself.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => setShowWaiver((v) => !v)}
                  className="rounded-md border border-border px-3 py-2 text-sm"
                >
                  {showWaiver ? "Cancel" : "Record a waiver"}
                </button>
              </div>

              {showWaiver && (
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  <input
                    placeholder="member sub"
                    value={waiver.sub}
                    onChange={(e) =>
                      setWaiver({ ...waiver, sub: e.target.value })
                    }
                    className="rounded-md border border-border bg-card px-3 py-2 text-sm"
                  />
                  <select
                    value={waiver.obligation}
                    onChange={(e) =>
                      setWaiver({ ...waiver, obligation: e.target.value })
                    }
                    className="rounded-md border border-border bg-card px-3 py-2 text-sm"
                  >
                    <option value="">obligation…</option>
                    {mine.obligations.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.id}
                      </option>
                    ))}
                  </select>
                  <input
                    placeholder="period (YYYY-MM-DD, blank = today)"
                    value={waiver.period}
                    onChange={(e) =>
                      setWaiver({ ...waiver, period: e.target.value })
                    }
                    className="rounded-md border border-border bg-card px-3 py-2 text-sm"
                  />
                  <button
                    disabled={
                      busy !== null || !waiver.sub || !waiver.obligation
                    }
                    onClick={() =>
                      void run("waiver", () =>
                        grantWaiver(token, groupId, {
                          sub: waiver.sub,
                          obligation: waiver.obligation,
                          period: waiver.period || undefined,
                        })
                      )
                    }
                    className="rounded-md bg-foreground px-3 py-2 text-sm text-background disabled:opacity-50"
                  >
                    {busy === "waiver" ? "Recording…" : "Grant waiver"}
                  </button>
                </div>
              )}

              <div className="mt-4 border-t border-border pt-3">
                <p className="text-xs text-muted-foreground">
                  Adopting a drafted policy needs a decision that has passed.
                  Paste its id:
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <input
                    placeholder="decision id"
                    value={decisionId}
                    onChange={(e) => setDecisionId(e.target.value)}
                    className="min-w-64 rounded-md border border-border bg-card px-3 py-2 text-sm"
                  />
                  <button
                    disabled={
                      busy !== null || !decisionId || !policy?.drafts?.length
                    }
                    onClick={() =>
                      void run("adopt", () =>
                        adoptDuesPolicy(
                          token,
                          groupId,
                          policy!.drafts[0].version,
                          decisionId
                        )
                      )
                    }
                    className="rounded-md border border-border px-3 py-2 text-sm disabled:opacity-50"
                  >
                    {busy === "adopt"
                      ? "Adopting…"
                      : `Adopt v${policy?.drafts?.[0]?.version ?? "—"}`}
                  </button>
                </div>
              </div>
            </section>
          )}

          {flash && <p className="text-sm text-muted-foreground">{flash}</p>}
        </>
      )}
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={`space-y-4 rounded-xl border border-border bg-gradient-to-br ${gradient} p-[1px]`}
    >
      <div className="space-y-4 rounded-[11px] bg-card p-4">
        <header className="flex items-center gap-2">
          <Scale className="h-5 w-5" />
          <h2 className="text-base font-semibold">Dues</h2>
        </header>
        {children}
      </div>
    </div>
  )
}
