import Link from "next/link"

import {
  ArrowRight,
  Braces,
  Database,
  FolderKanban,
  HardDrive,
  KeyRound,
  LayoutDashboard,
  Mail,
  MessagesSquare,
  RefreshCw,
  Scale,
  Server,
  ShieldCheck,
  Users,
  Vote,
  Wallet,
  Workflow,
} from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

const APPS = [
  {
    icon: LayoutDashboard,
    title: "Dashboard",
    url: "https://irl.coop",
    description:
      "Your coop's home. Members, safes, shard nodes, and every app in one place.",
  },
  {
    icon: FolderKanban,
    title: "Projects",
    url: "https://app.irl.coop",
    description:
      "Plan and run cooperative projects — tasks, cycles, docs — on your own instance.",
  },
  {
    icon: Database,
    title: "Databases",
    url: "https://nocodb.irl.coop",
    description:
      "Shared tables and records for anything your group tracks. No spreadsheets in the group chat.",
  },
  {
    icon: Mail,
    title: "Webmail",
    url: "https://webmail.irl.coop",
    description:
      "A secure @irl.coop mailbox. One sign-in, no separate passwords, your mail on your servers.",
  },
  {
    icon: HardDrive,
    title: "Mail & Storage",
    url: "https://s3.irl.coop",
    description:
      "Self-hosted mail and S3-compatible file storage — the backbone your group controls.",
  },
  {
    icon: Braces,
    title: "API",
    url: "https://api.irl.coop",
    description:
      "One API for identity and data. Every app connects through it — yours can too.",
  },
]

const PILLARS = [
  { icon: KeyRound, name: "Authentication", live: true, note: "one identity, every login method" },
  { icon: ShieldCheck, name: "Authorization", live: true, note: "one session across every app" },
  { icon: Server, name: "Storage", live: true, note: "Citus Postgres + S3-compatible object storage" },
  { icon: MessagesSquare, name: "Communication", live: true, note: "mail, webmail and Matrix chat" },
  { icon: Workflow, name: "Workflow", live: true, note: "projects and shared databases" },
  { icon: Wallet, name: "Finance", live: false, note: "group treasury — planned" },
  { icon: Scale, name: "Compliance", live: false, note: "governance tooling — planned" },
  { icon: RefreshCw, name: "Lifecycle", live: false, note: "onboarding & offboarding — planned" },
]

export default async function LandingPage({
  params,
}: {
  params: Promise<{ lang: string }>
}) {
  const { lang } = await params
  const signIn = `/${lang}/sign-in`

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2 font-black tracking-tight">
            <span className="grid size-8 place-items-center rounded-lg bg-foreground text-background">
              i
            </span>
            irl.coop
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <a href="#apps" className="hover:text-foreground">Apps</a>
            <a href="#identity" className="hover:text-foreground">One identity</a>
            <a href="#network" className="hover:text-foreground">Groups</a>
            <a href="#architecture" className="hover:text-foreground">Architecture</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link href={signIn} className={buttonVariants({ variant: "ghost", size: "sm" })}>
              Sign in
            </Link>
            <Link
              href={signIn}
              className={buttonVariants({ size: "sm" })}
            >
              Join the coop
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="container grid place-items-center gap-y-6 py-24 text-center md:py-32">
        <span className="rounded-full border px-3 py-1 text-xs font-semibold tracking-widest text-muted-foreground">
          COMMUNITY OS · MEMBER-OWNED
        </span>
        <h1 className="max-w-3xl text-5xl font-black leading-[1.05] tracking-tight md:text-7xl">
          We&apos;re here for{" "}
          <span className="text-primary">cooperation.</span>
        </h1>
        <p className="max-w-2xl text-lg text-muted-foreground md:text-xl">
          Share files, tools and spaces. Host events. Communicate securely. Run a
          project, organize a club, build a network — with full control of your
          data. This platform is owned and controlled by its members.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link href={signIn} className={buttonVariants({ size: "lg" })}>
            Sign up / Log in
            <ArrowRight className="size-4" />
          </Link>
          <Link
            href="#apps"
            className={buttonVariants({ variant: "secondary", size: "lg" })}
          >
            Explore the apps
          </Link>
        </div>
        <p className="text-sm text-muted-foreground">
          One identity, every app · Membership on a sliding scale
        </p>
      </section>

      {/* Apps */}
      <section id="apps" className="container py-20">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-2 text-xs font-bold tracking-widest text-primary">
            WHAT&apos;S LIVE
          </p>
          <h2 className="text-3xl font-black tracking-tight md:text-4xl">
            The tools your group actually needs
          </h2>
          <p className="mt-3 text-muted-foreground">
            Every app runs on infrastructure you control and signs in with the
            same identity — no separate accounts, no per-service passwords.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {APPS.map((app) => (
            <Card
              key={app.title}
              className="group flex flex-col gap-3 p-6 transition-colors hover:border-primary/50"
            >
              <div className="grid size-11 place-items-center rounded-lg border bg-muted/50">
                <app.icon className="size-5" />
              </div>
              <h3 className="text-lg font-bold">{app.title}</h3>
              <p className="text-sm text-muted-foreground">{app.description}</p>
              <a
                href={app.url}
                className="mt-auto inline-flex items-center gap-1 text-sm font-semibold text-primary"
              >
                Open <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
              </a>
            </Card>
          ))}
        </div>
      </section>

      {/* One identity */}
      <section id="identity" className="border-y bg-muted/40">
        <div className="container grid items-center gap-10 py-20 md:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-bold tracking-widest text-primary">
              ONE IDENTITY
            </p>
            <h2 className="text-3xl font-black tracking-tight md:text-4xl">
              Every login method, one account
            </h2>
          </div>
          <div className="space-y-4 text-muted-foreground">
            <p>
              Sign in with Google, a passkey, or anything else — every method
              maps to a single canonical identity that you own. Your username
              becomes your @irl.coop address, and your mailbox, projects and
              data follow you across every app.
            </p>
            <p className="flex items-center gap-2 text-sm">
              <KeyRound className="size-4 text-primary" />
              No per-app passwords. Ever.
            </p>
          </div>
        </div>
      </section>

      {/* How groups interconnect */}
      <section id="network" className="border-y bg-muted/40">
        <div className="container py-20">
          <div className="mx-auto mb-12 max-w-2xl text-center">
            <p className="mb-2 text-xs font-bold tracking-widest text-primary">
              HOW GROUPS CONNECT
            </p>
            <h2 className="text-3xl font-black tracking-tight md:text-4xl">
              Groups, not silos.
            </h2>
            <p className="mt-3 text-muted-foreground">
              Every person and every group is a node in one network. Every
              connection is an explicit edge — decisions · space · trust ·
              money — so groups can interlock deeply without losing themselves.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {[
              {
                icon: Users,
                title: "Grouping",
                description:
                  "Groups can hold groups. A regional coalition seats its member farms, and subgroups share its space and services while keeping their own decisions. No silos — nested, not fenced.",
              },
              {
                icon: Vote,
                title: "Voting",
                description:
                  "Every decision runs on a quorum: 1-of-1 for you, N-of-M for a group. No server, operator, or hostile backend can act alone — the math forbids it — and timelocks make big changes reversible.",
              },
              {
                icon: Wallet,
                title: "Money",
                description:
                  "Every group gets a treasury: shared savings, quorum-gated pools, funds with spending rules, automatic distributions. Balances stay private by default, with proofs available on demand.",
              },
            ].map((primitive) => (
              <Card
                key={primitive.title}
                className="flex flex-col gap-3 p-6"
              >
                <div className="grid size-11 place-items-center rounded-lg border bg-background">
                  <primitive.icon className="size-5 text-primary" />
                </div>
                <h3 className="text-lg font-bold">{primitive.title}</h3>
                <p className="text-sm text-muted-foreground">{primitive.description}</p>
              </Card>
            ))}
          </div>
          <div className="mt-8 rounded-xl border border-primary/30 bg-primary/5 p-6 md:p-8">
            <h3 className="text-xl font-black tracking-tight">
              Membership is a set, not a tree.
            </h3>
            <p className="mt-2 max-w-3xl text-muted-foreground">
              You can sit in many groups at once and move between them without
              switching hats. The group you&apos;re acting for is part of the
              action itself: &ldquo;approve as member of Cold Storage Co-op —
              2-of-3&rdquo;. One identity, many seats, one approval inbox — and
              from these three primitives, new cooperation forms emerge on
              their own: labor swaps between farms, joint regional purchasing,
              data-sharing agreements, federated partners who keep their own
              trucks.
            </p>
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section id="architecture" className="container py-20">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-2 text-xs font-bold tracking-widest text-primary">
            ARCHITECTURE
          </p>
          <h2 className="text-3xl font-black tracking-tight md:text-4xl">
            Eight pillars. One ecosystem.
          </h2>
          <p className="mt-3 text-muted-foreground">
            Best-in-class open-source tools, wired together so members hold the
            keys — not a corporation. Live pillars marked, the rest planned.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PILLARS.map((pillar) => (
            <div
              key={pillar.name}
              className={cn(
                "rounded-xl border p-5",
                pillar.live ? "border-primary/40 bg-primary/5" : "border-dashed opacity-60"
              )}
            >
              <div className="mb-3 flex items-center justify-between">
                <pillar.icon className="size-5 text-primary" />
                {pillar.live && (
                  <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-bold tracking-wider text-primary">
                    LIVE
                  </span>
                )}
              </div>
              <h3 className="font-bold">{pillar.name}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{pillar.note}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t">
        <div className="container grid place-items-center gap-y-5 py-20 text-center">
          <h2 className="max-w-2xl text-3xl font-black tracking-tight md:text-4xl">
            Join the coop.
          </h2>
          <p className="max-w-xl text-muted-foreground">
            One identity, your data, your servers. Sign up in under a minute.
          </p>
          <Link href={signIn} className={buttonVariants({ size: "lg" })}>
            Sign up / Log in
            <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-muted/40">
        <div className="container flex flex-col items-center gap-4 py-12 text-center">
          <div className="flex items-center gap-2 font-black tracking-tight">
            <span className="grid size-8 place-items-center rounded-lg bg-foreground text-background">
              i
            </span>
            irl.coop
          </div>
          <p className="max-w-md text-sm text-muted-foreground">
            irl.coop is a member-owned digital platform cooperative — a suite of
            tools for the secure coordination of informal and formal
            organizations.
          </p>
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            All systems operational
          </p>
        </div>
      </footer>
    </div>
  )
}
