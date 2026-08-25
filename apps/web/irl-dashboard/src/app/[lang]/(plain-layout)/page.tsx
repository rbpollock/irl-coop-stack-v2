import Link from "next/link"
import { ArrowRight, KeyRound, Users, Wallet } from "lucide-react"

import { Logo } from "@/components/layout/logo"

const PILL = {
  light: "inline-flex items-center justify-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-medium text-neutral-950 transition hover:bg-white/90",
  dark: "inline-flex items-center justify-center gap-2 rounded-full bg-neutral-950 px-6 py-3 text-sm font-medium text-white transition hover:bg-neutral-800",
  ghost:
    "inline-flex items-center justify-center gap-2 rounded-full border border-white/20 px-6 py-3 text-sm font-medium text-white transition hover:bg-white/10",
}

const RECIPES = [
  {
    emoji: "🌱",
    name: "Neighborhood growing team",
    line: "Five households share plots, produce, and a season's plan.",
    tools: ["Project management", "Visual database", "Storage"],
  },
  {
    emoji: "🎭",
    name: "Local theater",
    line: "A closed company casts outside actors and runs the show.",
    tools: ["Project management", "Visual database", "Chat"],
  },
  {
    emoji: "🔧",
    name: "Tool library",
    line: "Neighbors share a lawnmower and a nail gun — not each buy one.",
    tools: ["Visual database", "Project management", "Chat"],
  },
  {
    emoji: "🧒",
    name: "Childcare co-op",
    line: "Twenty parents, fourteen kids, three on watch. Everyone gets a turn.",
    tools: ["Project management", "Visual database", "Chat"],
  },
  {
    emoji: "🧶",
    name: "Craft circle",
    line: "Knitters teach, trade, and pool money for materials.",
    tools: ["Visual database", "Website builder", "Chat"],
  },
  {
    emoji: "🔪",
    name: "Food skills",
    line: "Knife skills to tallow. Teach, learn, and keep it fair.",
    tools: ["Visual database", "Chat", "Storage"],
  },
  {
    emoji: "🚜",
    name: "Farmer exchange",
    line: "Manure for hay. Twenty hands to harvest, paid in food.",
    tools: ["Visual database", "Project management", "Chat"],
  },
  {
    emoji: "👕",
    name: "Hand-me-downs",
    line: "Kids a year apart pass along the clothes they've outgrown.",
    tools: ["Visual database", "Chat", "Storage"],
  },
  {
    emoji: "📖",
    name: "Solutions library",
    line: "Anonymized stories of how a need got met, together.",
    tools: ["Visual database", "Chat"],
  },
  {
    emoji: "🎉",
    name: "Gatherings",
    line: "Symposiums and coffee hour — find out what people need.",
    tools: ["Chat", "Live video", "Project management"],
  },
]

const TOOLS = [
  {
    role: "Project management",
    brand: "Plane",
    used: "Run a production, a season, a harvest.",
  },
  {
    role: "Visual database",
    brand: "NocoDB",
    used: "Tools, kids' clothes, offers and needs.",
  },
  {
    role: "Website builder",
    brand: "Webstudio",
    used: "Your group's home — and its store.",
  },
  {
    role: "Chat",
    brand: "Matrix · Element",
    used: "Every room, federated, yours.",
  },
  {
    role: "Email",
    brand: "Roundcube",
    used: "A real @irl.coop mailbox.",
  },
  {
    role: "Storage",
    brand: "MinIO",
    used: "Files, photos, media — on your servers.",
  },
  {
    role: "Social scheduling",
    brand: "Postiz",
    used: "One dashboard for every account.",
  },
  {
    role: "Live video",
    brand: "MediaMTX",
    used: "Broadcast and watch, self-hosted.",
  },
]

const PRINCIPLES = [
  {
    icon: KeyRound,
    title: "One identity",
    line: "Sign in once. Every tool, every group — one account you own.",
  },
  {
    icon: Users,
    title: "Your group, your rules",
    line: "Every group is a real, self-governing entity — not a folder.",
  },
  {
    icon: Wallet,
    title: "Money that stays fair",
    line: "A treasury per group, private by default, provable on demand.",
  },
]

const FAQ = [
  {
    q: "What does it cost?",
    a: "Membership runs on a sliding scale — pay what you can, so cost never keeps a neighbor out. Groups cover their own infrastructure at cost.",
  },
  {
    q: "Who owns my data?",
    a: "You do. Your files, messages and records live on infrastructure the coop controls — never resold, never used to sell you anything.",
  },
  {
    q: "Do I need to be technical?",
    a: "No. If you can use a phone, you can run a group. The tools are self-hosted but the sharp edges are already handled.",
  },
  {
    q: "Is this a company?",
    a: "No. It's a cooperative — owned and run by its members, with every decision on a quorum, not a boardroom.",
  },
]

export default async function LandingPage({
  params,
}: {
  params: Promise<{ lang: string }>
}) {
  const { lang } = await params
  const signIn = `/${lang}/sign-in`

  return (
    <div className="min-h-screen bg-background font-switzer text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2"
            aria-label="irl.coop home"
          >
            <Logo className="h-6 text-foreground" />
            <span className="text-base font-semibold tracking-tight">
              irl.coop
            </span>
          </Link>
          <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
            <a href="#recipes" className="hover:text-foreground">
              Recipes
            </a>
            <a href="#tools" className="hover:text-foreground">
              Tools
            </a>
            <a href="#how" className="hover:text-foreground">
              How it works
            </a>
            <a href="#faq" className="hover:text-foreground">
              FAQ
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <Link
              href={signIn}
              className="hidden text-sm font-medium text-muted-foreground hover:text-foreground sm:block"
            >
              Sign in
            </Link>
            <Link href={signIn} className={PILL.dark}>
              Join the coop
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-neutral-950 text-white">
        <video
          className="absolute inset-0 h-full w-full object-cover"
          autoPlay
          muted
          loop
          playsInline
          aria-hidden="true"
        >
          <source src="/videos/hero-bg.mp4" type="video/mp4" />
        </video>
        <div
          className="absolute inset-0 bg-neutral-950/55"
          aria-hidden="true"
        />
        <div className="container relative flex flex-col items-center gap-6 py-28 text-center md:py-40">
          <span className="rounded-full border border-white/15 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-white/60">
            Member-owned · Community OS
          </span>
          <h1 className="max-w-4xl text-5xl font-normal leading-[0.95] tracking-[-0.03em] sm:text-6xl md:text-7xl lg:text-8xl">
            We&apos;re here for{" "}
            <em className="font-serif italic">cooperation.</em>
          </h1>
          <p className="max-w-xl text-base text-white/70 md:text-lg">
            Share tools, time, skills and space. The apps your community
            already needs — project management, visual databases, websites,
            chat — under one identity you own. No platform in the middle.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link href={signIn} className={PILL.light}>
              Join the coop <ArrowRight className="size-4" />
            </Link>
            <a href="#recipes" className={PILL.ghost}>
              Browse the recipes
            </a>
          </div>
        </div>
      </section>

      {/* Principles */}
      <section className="border-b">
        <div className="container grid gap-10 py-20 md:grid-cols-3 md:gap-6">
          {PRINCIPLES.map((p) => (
            <div
              key={p.title}
              className="flex flex-col items-center gap-3 text-center"
            >
              <div className="grid size-11 place-items-center rounded-full border">
                <p.icon className="size-5" />
              </div>
              <h3 className="text-lg font-medium">{p.title}</h3>
              <p className="max-w-xs text-sm text-muted-foreground">{p.line}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Recipes */}
      <section id="recipes" className="container py-24 md:py-32">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Cooperative playbooks
          </p>
          <h2 className="text-4xl font-normal leading-tight tracking-tight md:text-5xl">
            Ways people already <em className="font-serif italic">do it.</em>
          </h2>
          <p className="mt-4 text-muted-foreground">
            Real groups, real needs — captured as recipes you can copy and make
            your own.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {RECIPES.map((r) => (
            <div
              key={r.name}
              className="flex flex-col gap-3 rounded-2xl border p-6 transition hover:-translate-y-0.5 hover:shadow-sm"
            >
              <span className="text-2xl">{r.emoji}</span>
              <h3 className="text-base font-medium leading-snug">{r.name}</h3>
              <p className="text-sm text-muted-foreground">{r.line}</p>
              <div className="mt-auto flex flex-wrap gap-1.5 pt-2">
                {r.tools.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Tools */}
      <section id="tools" className="border-y bg-muted/40">
        <div className="container py-24 md:py-32">
          <div className="mx-auto mb-14 max-w-2xl text-center">
            <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              One toolbox
            </p>
            <h2 className="text-4xl font-normal leading-tight tracking-tight md:text-5xl">
              General tools, <em className="font-serif italic">every kind of group.</em>
            </h2>
            <p className="mt-4 text-muted-foreground">
              You shouldn&apos;t need to know the name of the software. You
              should need to know what it does.
            </p>
          </div>
          <div className="grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-2 lg:grid-cols-4">
            {TOOLS.map((t) => (
              <div
                key={t.role}
                className="flex flex-col gap-2 bg-background p-6"
              >
                <h3 className="text-lg font-medium">{t.role}</h3>
                <span className="text-xs uppercase tracking-wider text-muted-foreground">
                  {t.brand}
                </span>
                <p className="text-sm text-muted-foreground">{t.used}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="container py-24 md:py-32">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            How it works
          </p>
          <h2 className="text-4xl font-normal leading-tight tracking-tight md:text-5xl">
            Groups, <em className="font-serif italic">not silos.</em>
          </h2>
          <p className="mt-4 text-muted-foreground">
            Every person and every group is a node in one network. Connections
            are explicit — so groups interlock without losing themselves.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              icon: Users,
              title: "Groups hold groups",
              body: "A coalition seats its member farms. A tool library spins off a maintenance group with its own budget. Nested, never fenced.",
            },
            {
              icon: KeyRound,
              title: "Every decision on a quorum",
              body: "1-of-1 for you, N-of-M for a group. No server or operator can act alone — the math forbids it.",
            },
            {
              icon: Wallet,
              title: "A treasury per group",
              body: "Shared savings, quorum-gated pools, automatic splits. Private by default, provable on demand.",
            },
          ].map((f) => (
            <div
              key={f.title}
              className="flex flex-col gap-3 rounded-2xl border p-6"
            >
              <div className="grid size-11 place-items-center rounded-full border">
                <f.icon className="size-5" />
              </div>
              <h3 className="text-lg font-medium">{f.title}</h3>
              <p className="text-sm text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t">
        <div className="container max-w-3xl py-24 md:py-32">
          <div className="mb-12 text-center">
            <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              FAQ
            </p>
            <h2 className="text-4xl font-normal leading-tight tracking-tight">
              Questions, <em className="font-serif italic">answered.</em>
            </h2>
          </div>
          <div className="divide-y border-y">
            {FAQ.map((f) => (
              <details key={f.q} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 text-base font-medium">
                  {f.q}
                  <span className="text-muted-foreground transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="pb-5 text-sm text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-neutral-950 text-white">
        <div className="container flex flex-col items-center gap-6 py-24 text-center md:py-32">
          <h2 className="max-w-2xl text-4xl font-normal leading-tight tracking-tight md:text-6xl">
            Cooperation, <em className="font-serif italic">on your terms.</em>
          </h2>
          <p className="max-w-md text-white/70">
            One identity, your data, your servers. Join in under a minute.
          </p>
          <Link href={signIn} className={PILL.light}>
            Join the coop <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-background">
        <div className="container flex flex-col items-center gap-4 py-12 text-center">
          <Link href="/" className="flex items-center gap-2">
            <Logo className="h-5 text-foreground" />
            <span className="text-sm font-semibold tracking-tight">
              irl.coop
            </span>
          </Link>
          <p className="max-w-md text-sm text-muted-foreground">
            A member-owned digital cooperative — tools for neighbors to share,
            decide, and build together.
          </p>
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
            <Link href="/design" className="hover:text-foreground">
              Design docs
            </Link>
            <Link href={signIn} className="hover:text-foreground">
              Sign in
            </Link>
          </div>
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            All systems operational
          </p>
        </div>
      </footer>
    </div>
  )
}
