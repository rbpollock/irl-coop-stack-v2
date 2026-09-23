import {
  Activity,
  Bell,
  FilePen,
  Gift,
  Scale,
  Search,
  Sprout,
  Waypoints,
} from "lucide-react"

import type { LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

// The action-oriented coop dashboard, three tiers:
//   1. Needs my attention — the inbox (notifications, governance, weaves, edits)
//   2. My situation — at-a-glance status (regenerative score, group health)
//   3. The commons — supply & demand (needs + offers)
// Most of the underlying data isn't wired yet, so each card is an intentional
// empty state — the shape is right, the data lands one card at a time.

function Soon() {
  return (
    <Badge
      variant="outline"
      className="text-[10px] font-normal text-muted-foreground"
    >
      soon
    </Badge>
  )
}

function EmptyState({
  icon: Icon,
  title,
  hint,
  soon = false,
}: {
  icon: LucideIcon
  title: string
  hint: string
  soon?: boolean
}) {
  return (
    <div className="flex flex-col items-center justify-center py-9 text-center">
      <div className="flex size-11 items-center justify-center rounded-full bg-muted/70 ring-1 ring-border">
        <Icon className="size-5 text-muted-foreground" />
      </div>
      <p className="mt-3 text-sm font-medium text-foreground/85">{title}</p>
      <p className="mt-1 max-w-[26ch] text-xs leading-relaxed text-muted-foreground">
        {hint}
      </p>
      {soon && (
        <div className="mt-3">
          <Soon />
        </div>
      )}
    </div>
  )
}

function AttentionCard({
  icon: Icon,
  title,
  emptyTitle,
  hint,
  soon,
}: {
  icon: LucideIcon
  title: string
  emptyTitle: string
  hint: string
  soon?: boolean
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <EmptyState icon={Icon} title={emptyTitle} hint={hint} soon={soon} />
      </CardContent>
    </Card>
  )
}

function TierHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h2>
  )
}

export function CoopDashboard() {
  return (
    <div className="space-y-6">
      {/* Tier 1 — needs my attention */}
      <section className="space-y-3">
        <TierHeading>Needs your attention</TierHeading>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <AttentionCard
            icon={Bell}
            title="Notifications"
            emptyTitle="Nothing needs you right now"
            hint="Mentions, decisions and group activity will land here."
          />
          <AttentionCard
            icon={Scale}
            title="Governance"
            emptyTitle="No open votes"
            hint="Choices your groups are asking you to weigh in on, sorted by urgency."
            soon
          />
          <AttentionCard
            icon={Waypoints}
            title="Weaves"
            emptyTitle="No pending weaves"
            hint="Needs and offers you're helping connect, waiting on you."
            soon
          />
          <AttentionCard
            icon={FilePen}
            title="Edited by others"
            emptyTitle="Nothing new to review"
            hint="Shared documents and projects changed since you last looked."
            soon
          />
        </div>
      </section>

      {/* Tier 2 — my situation */}
      <section className="space-y-3">
        <TierHeading>Your situation</TierHeading>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Regenerative score
              </CardTitle>
              <Sprout className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="flex items-center gap-6">
              <div className="relative shrink-0">
                <svg className="size-24 -rotate-90" viewBox="0 0 36 36">
                  <circle
                    cx="18"
                    cy="18"
                    r="16"
                    fill="none"
                    stroke="var(--muted)"
                    strokeWidth="3"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-semibold text-muted-foreground">
                    —
                  </span>
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-xs leading-relaxed text-muted-foreground">
                  A private ZK-metric of the care you give and receive — not a
                  leaderboard.
                </p>
                <Soon />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Group health
              </CardTitle>
              <Activity className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <EmptyState
                icon={Activity}
                title="No groups yet"
                hint="Each group will show a quick status — pending decisions, stalled weaves, unread docs."
                soon
              />
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Tier 3 — the commons */}
      <section className="space-y-3">
        <TierHeading>The commons</TierHeading>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Needs</CardTitle>
              <Search className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <EmptyState
                icon={Search}
                title="No open needs"
                hint="What your community is asking for — delivery, skills, hands."
                soon
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Offers</CardTitle>
              <Gift className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <EmptyState
                icon={Gift}
                title="No offers yet"
                hint="What you and your groups can give. Add yours from onboarding."
                soon
              />
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  )
}
