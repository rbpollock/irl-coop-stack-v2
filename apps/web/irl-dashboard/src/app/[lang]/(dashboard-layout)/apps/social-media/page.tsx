"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useSession } from "next-auth/react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Megaphone, Plus, RefreshCw, Send, Vote } from "lucide-react"

import type { Group } from "../groups/_lib/groups"
import type { SocialSummary } from "./_lib/social"

import { ensureLocalizedPathname } from "@/lib/i18n"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { listGroups, scopeResource } from "../groups/_lib/groups"
import { getSocialSummary, proposeConnectPostiz } from "./_lib/social"

const STATE_COLORS: Record<string, string> = {
  POSTED: "var(--accent)",
  QUEUE: "var(--muted-foreground)",
  DRAFT: "var(--border)",
  FAILED: "var(--destructive)",
}

function stateColor(state: string): string {
  return STATE_COLORS[state] ?? "var(--muted-foreground)"
}

function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })
}

export default function SocialMediaPage() {
  const { data: session } = useSession()
  const params = useParams()
  const locale = (params.lang as string) ?? "en"

  const [summaries, setSummaries] = useState<SocialSummary[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [connectOpen, setConnectOpen] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const token = session?.accessToken as string | undefined

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    setError(null)
    Promise.all([getSocialSummary(token), listGroups(token)])
      .then(([ss, gs]) => {
        setSummaries(ss)
        setGroups(gs)
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  async function connect(g: Group) {
    if (!token) return
    setBusy(g.id)
    setError(null)
    try {
      await scopeResource(token, g.id, { app: "postiz", resource_key: g.id })
      setConnectOpen(false)
      load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  async function propose(g: Group) {
    if (!token) return
    setBusy(g.id)
    setError(null)
    try {
      await proposeConnectPostiz(token, g.id, g.name)
      setConnectOpen(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  if (!token) return null

  const optedIds = new Set(summaries.map((s) => s.group_id))
  const available = groups.filter((g) => !optedIds.has(g.id))

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Social Media</h1>
          <p className="text-xs text-muted-foreground">
            Scheduling + analytics across social channels, per group
          </p>
        </div>
        <Button size="sm" onClick={() => setConnectOpen(true)}>
          <Plus className="me-2 h-3.5 w-3.5" />
          Connect Postiz to a group
        </Button>
      </div>

      <div className="flex-1 space-y-4 overflow-auto p-4">
        {error && (
          <div className="flex items-center gap-3 rounded border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw className="me-2 h-3.5 w-3.5" />
              Retry
            </Button>
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : summaries.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <Megaphone className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              No groups connected to Postiz yet.
            </p>
            <Button size="sm" onClick={() => setConnectOpen(true)}>
              <Plus className="me-2 h-3.5 w-3.5" />
              Connect a group
            </Button>
          </div>
        ) : (
          summaries.map((s) => (
            <Card key={s.group_id}>
              <CardHeader className="flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm">{s.group_name}</CardTitle>
                  <CardDescription>
                    {s.integrations} channel{s.integrations === 1 ? "" : "s"} ·{" "}
                    {s.members} member{s.members === 1 ? "" : "s"}
                  </CardDescription>
                </div>
                <Button asChild size="sm" variant="outline">
                  <Link href={ensureLocalizedPathname("/apps/postiz", locale)}>
                    Open Postiz
                    <Megaphone className="ms-2 h-3.5 w-3.5" />
                  </Link>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded border p-3">
                    <div className="text-2xl font-semibold">
                      {s.total_posts}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Posts (30d)
                    </div>
                  </div>
                  <div className="rounded border p-3">
                    <div className="text-2xl font-semibold">
                      {s.integrations}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Channels
                    </div>
                  </div>
                  <div className="rounded border p-3">
                    <div className="text-2xl font-semibold">{s.members}</div>
                    <div className="text-xs text-muted-foreground">Members</div>
                  </div>
                </div>

                {s.posts_by_day.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-medium text-muted-foreground">
                      Posts per day (last 30 days)
                    </div>
                    <div className="h-32">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={s.posts_by_day}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                          <XAxis
                            dataKey="day"
                            tickFormatter={shortDate}
                            fontSize={10}
                            tickLine={false}
                          />
                          <YAxis
                            allowDecimals={false}
                            fontSize={10}
                            width={24}
                            tickLine={false}
                          />
                          <Tooltip />
                          <Line
                            type="monotone"
                            dataKey="n"
                            stroke="var(--accent)"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {s.posts_by_state.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-medium text-muted-foreground">
                      Posts by status
                    </div>
                    <div className="h-28">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={s.posts_by_state}>
                          <XAxis
                            dataKey="state"
                            fontSize={10}
                            tickLine={false}
                          />
                          <YAxis
                            allowDecimals={false}
                            fontSize={10}
                            width={24}
                            tickLine={false}
                          />
                          <Tooltip />
                          <Bar dataKey="n" radius={[3, 3, 0, 0]}>
                            {s.posts_by_state.map((st) => (
                              <Cell
                                key={st.state}
                                fill={stateColor(st.state)}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {s.recent_posts.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground">
                      Recent posts
                    </div>
                    {s.recent_posts.map((p) => (
                      <div
                        key={p.id}
                        className="flex items-start justify-between gap-3 rounded border p-2 text-xs"
                      >
                        <span className="line-clamp-2 flex-1 text-muted-foreground">
                          {p.content || "—"}
                        </span>
                        <Badge variant="secondary" className="shrink-0">
                          {p.state}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={connectOpen} onOpenChange={setConnectOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Connect Postiz to a group</DialogTitle>
            <DialogDescription>
              Provision a Postiz workspace (org + synced membership) for a
              group. Owners connect directly; others propose it for a group
              vote.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-80 space-y-2 overflow-auto">
            {available.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Every group you belong to is already connected.
              </p>
            ) : (
              available.map((g) => {
                const isOwner = !!g.roles?.includes("owner")
                return (
                  <div
                    key={g.id}
                    className="flex items-center justify-between rounded border p-2.5"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">
                        {g.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {isOwner
                          ? "You are an owner"
                          : "Member — propose a vote"}
                      </div>
                    </div>
                    {isOwner ? (
                      <Button
                        size="sm"
                        onClick={() => connect(g)}
                        disabled={busy === g.id}
                      >
                        <Send className="me-2 h-3.5 w-3.5" />
                        {busy === g.id ? "Connecting…" : "Connect"}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => propose(g)}
                        disabled={busy === g.id}
                      >
                        <Vote className="me-2 h-3.5 w-3.5" />
                        Propose
                      </Button>
                    )}
                  </div>
                )
              })
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConnectOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
