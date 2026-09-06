import Link from "next/link"
import {
  ArrowRight,
  CalendarDays,
  ClipboardList,
  Database,
  FileText,
  FolderKanban,
  FolderOpen,
  Handshake,
  KeyRound,
  Mail,
  Map,
  Megaphone,
  MessagesSquare,
  Network,
  Palette,
  Phone,
  Sprout,
  Users,
  Video,
  Wallet,
} from "lucide-react"

import { Logo } from "@/components/layout/logo"
import { getCategories } from "@/lib/design-docs"

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
  {
    emoji: "🗳️",
    name: "Civic engagement",
    line: "Voter drives, poll workers, rides to the polls, and know-your-rights.",
    tools: ["Chat", "Visual database", "Project management"],
  },
]

const APPS = [
  {
    icon: FolderKanban,
    name: "Projects",
    brand: "Plane",
    line: "Plan and run work — a harvest, a build, a season.",
    group: "A project per group; tasks scoped to roles.",
    across: "A coalition board composes member projects.",
  },
  {
    icon: Network,
    name: "Groups",
    brand: "Safe",
    line: "The group itself — members, roles, treasury, decisions.",
    group: "A Safe account with seats, roles and a quorum.",
    across: "Groups hold child groups; strip the edge, it stands alone.",
  },
  {
    icon: Handshake,
    name: "Needs & Offers",
    brand: "irl.coop",
    line: "Post what you have or need — and find who fits together.",
    group: "Needs and offers scoped to the group; anyone can weave a match.",
    across: "A loop can span groups — seed, compost, storage, in one circle.",
  },
  {
    icon: MessagesSquare,
    name: "Chat",
    brand: "Matrix · Element",
    line: "Rooms for every need — federated, yours.",
    group: "A room per group; roles decide who's in.",
    across: "Rooms bridge groups into one conversation.",
  },
  {
    icon: Map,
    name: "Maps",
    brand: "OpenMapServer",
    line: "Your places, tracks and tours on a self-hosted map.",
    group: "Markers and tracks scoped by visibility.",
    across: "Explore shows every group's public pins, federation-wide.",
  },
  {
    icon: Sprout,
    name: "Farm",
    brand: "LiteFarm",
    line: "Fields, crops, tasks and sales — your whole farm.",
    group: "A farm per group; members as farm workers.",
    across: "A farm cooperative pools harvests and delivery.",
  },
  {
    icon: Mail,
    name: "Webmail",
    brand: "Roundcube · Stalwart",
    line: "A real @irl.coop mailbox for every member.",
    group: "Shared group addresses route to the right people.",
    across: "One identity, one inbox; aliases span groups.",
  },
  {
    icon: Phone,
    name: "Calls",
    brand: "FreeSWITCH",
    line: "Voice and video on your own switch.",
    group: "A number per group; members as SIP users.",
    across: "One coop domain routes calls across groups.",
  },
  {
    icon: FolderOpen,
    name: "Files",
    brand: "MinIO",
    line: "Files, photos, media — on your servers.",
    group: "A scoped bucket per group; role-gated access.",
    across: "Share between groups by grant, never public.",
  },
  {
    icon: FileText,
    name: "Documents",
    brand: "OnlyOffice",
    line: "Co-edit docs, sheets and decks in real time.",
    group: "Documents scoped to the group; live co-editing.",
    across: "A coalition co-edits via explicit shares.",
  },
  {
    icon: Database,
    name: "Databases",
    brand: "NocoDB",
    line: "A visual database for whatever you track.",
    group: "Tables scoped to the group — tools, clothes, needs.",
    across: "A federation view composes public rows.",
  },
  {
    icon: ClipboardList,
    name: "Surveys",
    brand: "Formbricks",
    line: "Ask your members, then route the answers.",
    group: "Forms to members; anonymization by the source.",
    across: "A federation poll reaches every member group.",
  },
  {
    icon: CalendarDays,
    name: "Events",
    brand: "HiEvents",
    line: "Events and tickets, coffee hour to symposium.",
    group: "Events scoped to the group; tickets and quota.",
    across: "A federation event composes member groups.",
  },
  {
    icon: Palette,
    name: "Studio",
    brand: "Webstudio",
    line: "Build your group's home — and its store.",
    group: "A site per group, edited by role.",
    across: "A coalition site composes member-group pages.",
  },
  {
    icon: Megaphone,
    name: "Social Media",
    brand: "Postiz",
    line: "Schedule and publish across every channel.",
    group: "One dashboard for the group's accounts.",
    across: "A federation account posts for the whole.",
  },
  {
    icon: Video,
    name: "Live Video",
    brand: "MediaMTX",
    line: "Broadcast and watch — self-hosted.",
    group: "Group streams; any member can go live.",
    across: "One stream, many groups watching.",
  },
]

const APP_GRADIENTS: Record<string, string> = {
  Projects: "from-indigo-500 to-blue-600",
  Groups: "from-fuchsia-500 to-pink-600",
  "Needs & Offers": "from-teal-500 to-emerald-600",
  Chat: "from-violet-500 to-purple-600",
  Maps: "from-teal-500 to-cyan-600",
  Farm: "from-emerald-500 to-green-600",
  Webmail: "from-sky-500 to-blue-600",
  Calls: "from-rose-500 to-red-600",
  Files: "from-amber-500 to-orange-600",
  Documents: "from-zinc-500 to-slate-600",
  Databases: "from-cyan-500 to-sky-600",
  Surveys: "from-orange-500 to-amber-600",
  Events: "from-lime-500 to-emerald-600",
  Studio: "from-purple-500 to-violet-600",
  "Social Media": "from-pink-500 to-fuchsia-600",
  "Live Video": "from-red-500 to-rose-600",
}

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

const FAQ_GROUPS = [
  {
    title: "Getting started & structure",
    items: [
      {
        q: "Do I need to be technical?",
        a: "No. If you can use a phone, you can run a group. The tools are self-hosted but the sharp edges are already handled.",
      },
      {
        q: "Is this a company?",
        a: "No. It's a cooperative — owned and run by its members, with every decision on a quorum, not a boardroom.",
      },
      {
        q: "Can I just start a group, or do I have to join the coop first?",
        a: "Just start. Sign up and your group is yours from day one. Joining the coop is optional — it's how you get a say in how the whole thing runs, and you're welcome to it whenever you're ready.",
      },
      {
        q: "How do we make decisions without endless meetings?",
        a: "Put it up as a proposal and members sign off. Nothing happens without the group agreeing — no single person, and no platform, can decide for you.",
      },
      {
        q: "Which tools does my group get?",
        a: "You pick. Projects, a database, chat, files, events, a website — turn on what you need, leave the rest off.",
      },
    ],
  },
  {
    title: "Money",
    items: [
      {
        q: "What does it cost?",
        a: "Membership runs on a sliding scale — pay what you can, so cost never keeps a neighbor out. Groups cover their own infrastructure at cost.",
      },
      {
        q: "How do we split money fairly when everyone contributes different amounts?",
        a: "You set the split once, up front, and the platform pays it out for you on a schedule. No single person holds the purse strings.",
      },
      {
        q: "Can we pool money for something shared — a cold frame, materials, a printer?",
        a: "Yes. Every group has its own money pot, and spending from it takes the group's sign-off, not any one person's.",
      },
      {
        q: "What if we mostly trade favors — childcare turns, harvests, lessons — not cash?",
        a: "The platform tracks that too. Hours and contributions are recorded, so 'everyone gets a turn' stays fair even when no money changes hands.",
      },
      {
        q: "Can we sell things, or charge for events?",
        a: "Yes. Whatever the group earns — tickets, sales, dues — lands in the group's own pot and is split the way the group decided.",
      },
    ],
  },
  {
    title: "Membership & privacy",
    items: [
      {
        q: "Who owns my data?",
        a: "You do. Your files, messages and records live on infrastructure the coop controls — never resold, never used to sell you anything.",
      },
      {
        q: "Who gets to be in the group, and what can they do?",
        a: "You decide. Members hold roles — one plans, one spends, one's just along — and your group sets the rules for each role.",
      },
      {
        q: "Can we keep our membership or our records private?",
        a: "Yes. A group can be private, so only members see who's in it. And sensitive things — who gave what, who attended — stay hidden unless you choose to show them.",
      },
      {
        q: "What if we're organizing something sensitive and people don't want their names on a list?",
        a: "There's a setting for that. Members can prove to each other that they belong, without any public roster an outsider could read.",
      },
    ],
  },
  {
    title: "Trust",
    items: [
      {
        q: "How do we know someone actually has the skills they claim — a trained poll worker, a certified kayaker?",
        a: "People can hold verifiable credentials and show them when needed — proof without oversharing.",
      },
      {
        q: "What happens to our data if the platform disappears?",
        a: "You can take it with you. Everything lives in open formats on the coop's own servers, and a group can walk away with its files, records, and money intact. Nothing is held hostage, and nothing vanishes because one company closed.",
      },
      {
        q: "How do I know this won't just vanish like other platforms?",
        a: "Because it isn't one company's product — it's a cooperative owned by its members, running open code on its own servers. There's no owner who can switch it off, and your data stays yours, in formats you can always take elsewhere.",
      },
      {
        q: "Can we prove the things we claim — who wrote it, how the food was grown, how the money was split?",
        a: "Yes, in a way that's hard to fake. A group can back a claim with a checkable proof — this author wrote this, this farm raised it this way, the funds went where they were meant to — without handing over anything private.",
      },
      {
        q: "How do we know a group is trustworthy before we join or work with them?",
        a: "Groups earn a reputation through what they actually do — recorded in a way that can be checked, not just claimed. You can see whether a group shares fairly and shows up, and that record is hard to game.",
      },
      {
        q: "Why should I care about proofs and badges if I'm not technical?",
        a: "You don't have to understand how they work — you just get to trust without taking anyone's word. A badge is like a receipt that can be checked but not forged: proof the food was really grown that way, the author really wrote it, the money really was shared fairly.",
      },
    ],
  },
  {
    title: "Growing & winding down",
    items: [
      {
        q: "We're several small groups on one block — can we share a website but keep our own money and people?",
        a: "Yes. Groups can join together — share a site, a name, a fund — while each keeps its own money, members, and rules.",
      },
      {
        q: "Can a group grow into something bigger — chapters, a network — without losing itself?",
        a: "Yes. Groups can hold other groups, and a group that joins a bigger one can step back out later with its money and members intact.",
      },
      {
        q: "What happens to our stuff if the group winds down?",
        a: "It stays yours. The group's own rules decide how things are divided — the platform never holds your things hostage.",
      },
    ],
  },
]

export default async function LandingPage({
  params,
}: {
  params: Promise<{ lang: string }>
}) {
  const { lang } = await params
  const signIn = `/${lang}/sign-in`
  const categories = getCategories()
    .map((c) => ({ ...c, docs: c.docs.filter((d) => d.status !== "note") }))
    .filter((c) => c.docs.length > 0)

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
            <a href="#apps" className="hover:text-foreground">
              Apps
            </a>
            <a href="#how" className="hover:text-foreground">
              How it works
            </a>
            <a href="#faq" className="hover:text-foreground">
              FAQ
            </a>
            <Link href="/design" className="hover:text-foreground">
              Docs
            </Link>
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

      {/* Group model */}
      <section className="border-b">
        <div className="container py-12">
          <div className="flex flex-col gap-5 rounded-2xl border bg-muted/40 p-6 md:flex-row md:items-center md:justify-between md:p-8">
            <div className="max-w-2xl">
              <p className="mb-1 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                The full design
              </p>
              <h2 className="text-xl font-semibold tracking-tight">
                The group, from first principles
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                The group is the primitive: a Safe smart contract members hold
                together — seats, roles, a private treasury, and nine shared
                pathways that compose into every shape, from a tool library to
                a worker union. With diagrams, schemas, and a glossary.
              </p>
            </div>
            <Link
              href="/group-model.html"
              className="inline-flex shrink-0 items-center gap-2 rounded-full bg-neutral-950 px-6 py-3 text-sm font-medium text-white transition hover:bg-neutral-800"
            >
              Read the group model <ArrowRight className="size-4" />
            </Link>
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

      {/* Apps */}
      <section id="apps" className="border-y bg-muted/40">
        <div className="container py-24 md:py-32">
          <div className="mx-auto mb-12 max-w-2xl text-center">
            <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              The toolbox, in full
            </p>
            <h2 className="text-4xl font-normal leading-tight tracking-tight md:text-5xl">
              Every app, <em className="font-serif italic">inside and across.</em>
            </h2>
            <p className="mt-4 text-muted-foreground">
              Every app is scoped to your group first — then composes across
              groups when you federate. Nothing is merged or exposed unless you
              say so.
            </p>
          </div>

          {/* composition diagram */}
          <div className="mx-auto mb-12 flex max-w-2xl flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-8">
            <div className="flex flex-col items-center gap-1.5">
              <svg viewBox="0 0 96 96" className="h-20 w-20" aria-hidden="true" fill="none">
                <circle cx="48" cy="48" r="38" className="stroke-neutral-400" strokeWidth="2" />
                <rect x="36" y="36" width="8" height="8" rx="2" className="fill-neutral-500" />
                <rect x="52" y="36" width="8" height="8" rx="2" className="fill-neutral-500" />
                <rect x="36" y="52" width="8" height="8" rx="2" className="fill-neutral-500" />
                <rect x="52" y="52" width="8" height="8" rx="2" className="fill-neutral-500" />
              </svg>
              <span className="text-sm font-medium">One group</span>
              <span className="text-xs text-muted-foreground">and its apps</span>
            </div>
            <svg
              viewBox="0 0 40 24"
              className="h-6 w-10 shrink-0 text-muted-foreground"
              aria-hidden="true"
              fill="none"
            >
              <path d="M4 12 H32" className="stroke-neutral-400" strokeWidth="2" strokeDasharray="3 3" />
              <path d="M28 6 L36 12 L28 18" className="stroke-neutral-400" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <div className="flex flex-col items-center gap-1.5">
              <svg viewBox="0 0 96 96" className="h-20 w-20" aria-hidden="true" fill="none">
                <circle cx="48" cy="48" r="38" className="stroke-neutral-400" strokeWidth="2" strokeDasharray="4 3" />
                <circle cx="30" cy="40" r="12" className="stroke-neutral-400" strokeWidth="1.75" />
                <circle cx="66" cy="40" r="12" className="stroke-neutral-400" strokeWidth="1.75" />
                <circle cx="48" cy="62" r="12" className="stroke-neutral-400" strokeWidth="1.75" />
              </svg>
              <span className="text-sm font-medium">Groups of groups</span>
              <span className="text-xs text-muted-foreground">a composition</span>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {APPS.map((app) => (
              <div
                key={app.name}
                className="flex flex-col gap-3 rounded-2xl border bg-background p-5 transition hover:-translate-y-0.5 hover:shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br shadow-sm ${APP_GRADIENTS[app.name] ?? "from-zinc-500 to-slate-600"}`}
                  >
                    <app.icon className="size-5 text-white" strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-base font-medium leading-tight">{app.name}</h3>
                    <span className="text-[11px] tracking-wide text-muted-foreground">
                      {app.brand}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{app.line}</p>
                <div className="mt-auto flex flex-col gap-2 border-t pt-3">
                  <div className="flex items-start gap-2">
                    <span className="mt-px shrink-0 rounded-full bg-neutral-950 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-white">
                      In a group
                    </span>
                    <p className="text-xs text-muted-foreground">{app.group}</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="mt-px shrink-0 rounded-full border border-neutral-300 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Groups of groups
                    </span>
                    <p className="text-xs text-muted-foreground">{app.across}</p>
                  </div>
                </div>
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

      {/* Design docs */}
      <section id="docs" className="border-t">
        <div className="container py-24 md:py-32">
          <div className="mb-14 flex flex-col items-start justify-between gap-6 md:flex-row md:items-end">
            <div>
              <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                Design docs
              </p>
              <h2 className="text-4xl font-normal leading-tight tracking-tight md:text-5xl">
                How it&apos;s all <em className="font-serif italic">designed.</em>
              </h2>
              <p className="mt-4 max-w-xl text-muted-foreground">
                The settled design decisions — the group primitive, the treasury,
                the shapes, and the open questions — written for anyone to read
                and challenge.
              </p>
            </div>
            <Link
              href="/design"
              className="group inline-flex shrink-0 items-center gap-2 text-sm font-medium"
            >
              View all docs
              <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
            </Link>
          </div>
          <div className="space-y-16">
            {categories.map((category) => (
              <div key={category.name}>
                <h3 className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  {category.name}
                </h3>
                <div className="-mx-1 flex gap-4 overflow-x-auto px-1 pb-2 [scrollbar-width:thin]">
                  {category.docs.map((doc) => (
                    <Link
                      key={doc.slug}
                      href={`/design/${doc.slug}`}
                      className="group flex w-72 shrink-0 flex-col justify-between gap-3 rounded-2xl border p-6 transition hover:border-foreground/20"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="font-medium leading-snug">{doc.title}</h4>
                          <span className="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {doc.status}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {doc.description}
                        </p>
                      </div>
                      <span className="inline-flex items-center gap-1 text-sm font-medium">
                        Read
                        <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" />
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
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
          <div className="space-y-12">
            {FAQ_GROUPS.map((group) => (
              <div key={group.title}>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  {group.title}
                </h3>
                <div className="divide-y border-y">
                  {group.items.map((f) => (
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
            <Link href="/group-model.html" className="hover:text-foreground">
              Group model
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
