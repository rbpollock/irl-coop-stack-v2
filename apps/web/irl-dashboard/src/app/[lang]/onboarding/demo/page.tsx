"use client"

import { useEffect, useState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Eye,
  HeartHandshake,
  KeyRound,
  Network,
  Sparkles,
  Sprout,
  Users,
} from "lucide-react"

import type { ReactNode } from "react"

// Mocked onboarding flow — the 8-step prototype (docs/design/onboarding-prototype.html)
// as a real dashboard route. All state is in-memory; nothing calls coop-api or deploys
// a Safe. Styling mirrors the design doc's visual system: purple #7C3AED, join-green
// #16A34A, warm #FAF5FF, Cormorant Garamond display + Inter UI.

const ICONS = {
  seed: Sprout,
  people: Users,
  repair: HeartHandshake,
  design: Network,
  eye: Eye,
  key: KeyRound,
  spark: Sparkles,
} as const

type IconKey = keyof typeof ICONS

const serif = {
  fontFamily: '"Cormorant Garamond", "Crimson Pro", Georgia, serif',
}

const VERTICALS: {
  icon: IconKey
  name: string
  desc: string
  fund: string
}[] = [
  {
    icon: "people",
    name: "Facilitation",
    desc: "Run a room where power isn't hidden.",
    fund: "Standing space, roles, a decision log — funded by the room's own pool.",
  },
  {
    icon: "repair",
    name: "Conflict & repair",
    desc: "Mediate a rift and restore trust.",
    fund: "A neutral space, an arbiter you name up front, a fund for repair work.",
  },
  {
    icon: "design",
    name: "Group & org design",
    desc: "Shape a group that doesn't bottleneck.",
    fund: "Blueprints for structure — thresholds, boundaries, exit rights — set before the crisis.",
  },
  {
    icon: "eye",
    name: "Psychodynamics",
    desc: "Read what's beneath the stated agenda.",
    fund: "Practitioner circles, supervision, safe containers — paid, because attention is work.",
  },
]

const SHAPES: { icon: IconKey; name: string; desc: string }[] = [
  { icon: "seed", name: "Circle", desc: "A gathering with rhythm and roles." },
  { icon: "people", name: "Co-op", desc: "Shared ownership, shared work." },
  { icon: "design", name: "Working group", desc: "A team on a mission." },
  {
    icon: "repair",
    name: "Mutual-aid fund",
    desc: "Pool money for hard times.",
  },
]

const STEPS: {
  eyebrow: string
  title: ReactNode
  lead: ReactNode
  tagline: string
}[] = [
  {
    eyebrow: "Welcome",
    title: (
      <>
        We were never more connected.{" "}
        <em className="italic text-[#7C3AED]">We were never more alone.</em>
      </>
    ),
    lead: (
      <>
        irl.coop is for people who want to build something together — a circle,
        a co-op, a fund, a team — and keep it theirs. Your rules, your money,
        your people, nobody in the middle. And a library of blueprints, so you
        don&apos;t have to start from scratch.
      </>
    ),
    tagline: "One account. Then a world.",
  },
  {
    eyebrow: "You",
    title: (
      <>
        You are a <em className="italic text-[#7C3AED]">group of one.</em>
      </>
    ),
    lead: (
      <>
        Before you join anyone else, you&apos;re already a group of your own —
        one seat, one voice, fully yours. Every group you join or start after
        this is just another connection to it.
      </>
    ),
    tagline: "",
  },
  {
    eyebrow: "The one idea",
    title: (
      <>
        Your world is a <em className="italic text-[#7C3AED]">graph,</em> not a
        feed.
      </>
    ),
    lead: (
      <>
        You&apos;re a point. Every group is a line between points. And a group
        can live inside another group — a working group inside a co-op, a co-op
        inside a bigger network. That&apos;s what{" "}
        <strong className="font-semibold text-[#4C1D95]">composable</strong>{" "}
        means: what you build can join what others build, and it stays yours.
      </>
    ),
    tagline: "",
  },
  {
    eyebrow: "What you'll build",
    title: (
      <>
        The hard things, made{" "}
        <em className="italic text-[#7C3AED]">startable.</em>
      </>
    ),
    lead: (
      <>
        Some of the most important work — running a room where everyone&apos;s
        heard, mending a rift, shaping a group that doesn&apos;t fall apart,
        noticing what&apos;s going on under the surface — is exactly the work
        that&apos;s hardest to coordinate and hardest to fund. Here, it&apos;s
        where we start.
      </>
    ),
    tagline: "",
  },
  {
    eyebrow: "Your first shape",
    title: (
      <>
        Start from a <em className="italic text-[#7C3AED]">seed,</em> not a
        cage.
      </>
    ),
    lead: (
      <>
        Pick something close to what you have in mind. It&apos;s just a starting
        place — you&apos;ll change it as you go, and nothing is locked in.
      </>
    ),
    tagline: "",
  },
  {
    eyebrow: "Three warm questions",
    title: (
      <>
        Asked early, because it&apos;s{" "}
        <em className="italic text-[#7C3AED]">kinder</em> early.
      </>
    ),
    lead: (
      <>
        These are easier to answer on a calm day than in the middle of something
        hard.
      </>
    ),
    tagline: "",
  },
  {
    eyebrow: "Consent & trust",
    title: (
      <>
        Your rules are yours.{" "}
        <em className="italic text-[#7C3AED]">Here&apos;s how we keep them.</em>
      </>
    ),
    lead: (
      <>
        What&apos;s yours stays yours — your group, your money, your people. If
        an app or a person helps out, they&apos;re borrowing a narrow
        permission, never owning anything, and you can take it back whenever you
        like.
      </>
    ),
    tagline: "",
  },
  {
    eyebrow: "Your world",
    title: (
      <>
        This is your <em className="italic text-[#7C3AED]">world.</em>
      </>
    ),
    lead: (
      <>
        Not a feed, not a profile — a living picture of the people and groups
        around you, and what needs your attention.
      </>
    ),
    tagline: "You're in. Now go find your people.",
  },
]

function Diagram() {
  return (
    <svg
      viewBox="0 0 600 260"
      className="my-6 h-auto w-full"
      role="img"
      aria-label="A diagram of nodes and edges: you connect to groups, and one group contains a smaller group."
    >
      <defs>
        <marker
          id="ob-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="#A78BFA" />
        </marker>
      </defs>
      <g stroke="#A78BFA" strokeWidth="1.6" markerEnd="url(#ob-arrow)">
        <line x1="300" y1="130" x2="150" y2="60" />
        <line x1="300" y1="130" x2="450" y2="60" />
        <line x1="300" y1="130" x2="420" y2="200" />
      </g>
      <g fontFamily="Inter,sans-serif" fontSize="13" fill="#4C1D95">
        <circle
          cx="150"
          cy="60"
          r="26"
          fill="#EDE9FE"
          stroke="#7C3AED"
          strokeWidth="2"
        />
        <text x="150" y="65" textAnchor="middle" fontSize="11">
          co-op
        </text>
        <circle
          cx="450"
          cy="60"
          r="26"
          fill="#DCFCE7"
          stroke="#16A34A"
          strokeWidth="2"
        />
        <text x="450" y="65" textAnchor="middle" fontSize="11">
          circle
        </text>
        <circle
          cx="420"
          cy="200"
          r="34"
          fill="#fff"
          stroke="#A78BFA"
          strokeWidth="2"
        />
        <text x="420" y="196" textAnchor="middle" fontSize="11">
          working
        </text>
        <text x="420" y="210" textAnchor="middle" fontSize="11">
          group
        </text>
        <circle
          cx="420"
          cy="200"
          r="16"
          fill="#EDE9FE"
          stroke="#7C3AED"
          strokeWidth="1.5"
        />
      </g>
      <g>
        <circle cx="300" cy="130" r="30" fill="#7C3AED" />
        <text
          x="300"
          y="136"
          textAnchor="middle"
          fontFamily="Inter,sans-serif"
          fontSize="13"
          fill="#fff"
          fontWeight="600"
        >
          you
        </text>
      </g>
    </svg>
  )
}

export default function OnboardingPage() {
  const [step, setStep] = useState(0)
  const [vertical, setVertical] = useState<string | null>(null)
  const [shape, setShape] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [people, setPeople] = useState("")
  const [recovery, setRecovery] = useState("")
  const [fund, setFund] = useState("")

  const total = STEPS.length
  const isLast = step === total - 1
  const go = (n: number) => setStep(Math.max(0, Math.min(total - 1, n)))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") go(step + 1)
      if (e.key === "ArrowLeft") go(step - 1)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [step])

  const inputCls =
    "w-full max-w-[460px] rounded-xl border border-[#DDD6FE] bg-white px-4 py-3 text-base text-[#4C1D95] transition focus:border-[#7C3AED] focus:shadow-[0_0_0_3px_#EDE9FE] focus:outline-none"
  const labelCls = "mt-4 mb-1.5 block text-[13px] font-semibold text-[#4C1D95]"

  const s = STEPS[step]

  function renderContent() {
    switch (step) {
      case 1:
        return (
          <div>
            <div className="mt-2 flex items-center gap-4">
              <div
                className="flex h-14 w-14 items-center justify-center rounded-full text-2xl font-semibold text-white"
                style={{
                  background: "linear-gradient(135deg,#7C3AED,#A78BFA)",
                  fontFamily: serif.fontFamily,
                }}
              >
                {(name.trim()[0] ?? "R").toUpperCase()}
              </div>
              <div className="flex-1">
                <label htmlFor="ob-name" className={labelCls}>
                  What should we call you?
                </label>
                <input
                  id="ob-name"
                  className={inputCls}
                  placeholder="Your name"
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
            </div>
            <div className="mt-4 flex items-start gap-2 text-[13px] text-[#64748B]">
              <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-[#A78BFA]" />
              <span>
                <em>
                  This quietly sets up your own account underneath. You&apos;ll
                  never have to think about keys or wallets.
                </em>
              </span>
            </div>
          </div>
        )
      case 2:
        return <Diagram />
      case 3:
        return (
          <div>
            <div className="mt-5 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
              {VERTICALS.map((v) => {
                const Icon = ICONS[v.icon]
                const selected = vertical === v.name
                return (
                  <button
                    key={v.name}
                    type="button"
                    onClick={() => setVertical(selected ? null : v.name)}
                    className={`rounded-2xl border p-4 text-left transition hover:-translate-y-0.5 hover:border-[#A78BFA] hover:shadow-[0_10px_30px_-18px_rgba(76,29,149,0.35)] ${
                      selected
                        ? "border-[#7C3AED] bg-[#EDE9FE] shadow-[0_0_0_3px_#EDE9FE]"
                        : "border-[#DDD6FE] bg-white"
                    }`}
                  >
                    <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-[11px] bg-[#EDE9FE] text-[#7C3AED]">
                      <Icon className="h-5 w-5" />
                    </span>
                    <h3
                      className="mb-1.5 text-[20px] font-semibold text-[#2E1065]"
                      style={serif}
                    >
                      {v.name}
                    </h3>
                    <p className="text-[13.5px] leading-snug text-[#475569]">
                      {v.desc}
                    </p>
                    <span className="mt-2.5 block text-[12.5px] font-semibold text-[#16A34A]">
                      {v.fund}
                    </span>
                  </button>
                )
              })}
            </div>
            <div className="mt-4 flex items-start gap-2 text-[13px] text-[#64748B]">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[#A78BFA]" />
              <span>
                <em>
                  Healing and cooperation are different muscles — both built by
                  practice, not reading.
                </em>
              </span>
            </div>
          </div>
        )
      case 4:
        return (
          <div>
            <div className="mt-5 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
              {SHAPES.map((sh) => {
                const Icon = ICONS[sh.icon]
                const selected = shape === sh.name
                return (
                  <button
                    key={sh.name}
                    type="button"
                    onClick={() => setShape(selected ? null : sh.name)}
                    className={`rounded-2xl border p-4 text-left transition hover:-translate-y-0.5 hover:border-[#A78BFA] hover:shadow-[0_10px_30px_-18px_rgba(76,29,149,0.35)] ${
                      selected
                        ? "border-[#7C3AED] bg-[#EDE9FE] shadow-[0_0_0_3px_#EDE9FE]"
                        : "border-[#DDD6FE] bg-white"
                    }`}
                  >
                    <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-[11px] bg-[#EDE9FE] text-[#7C3AED]">
                      <Icon className="h-5 w-5" />
                    </span>
                    <h3 className="mb-1.5 text-base font-semibold text-[#2E1065]">
                      {sh.name}
                    </h3>
                    <p className="text-[13.5px] leading-snug text-[#475569]">
                      {sh.desc}
                    </p>
                  </button>
                )
              })}
            </div>
            <label htmlFor="ob-slug" className={labelCls}>
              What&apos;s one word for it?
            </label>
            <input
              id="ob-slug"
              className={inputCls}
              style={{ maxWidth: 260 }}
              placeholder="e.g. riverside"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
            />
            <p className="mt-1.5 text-[12.5px] text-[#64748B]">
              One name drives your group&apos;s home, its inbox, and its shared
              spaces.
            </p>
          </div>
        )
      case 5:
        return (
          <div>
            <label htmlFor="ob-people" className={labelCls}>
              Who are your people?
            </label>
            <input
              id="ob-people"
              className={inputCls}
              placeholder="Invite 1–3 emails (or skip)"
              value={people}
              onChange={(e) => setPeople(e.target.value)}
            />
            <label htmlFor="ob-recovery" className={labelCls}>
              If something happens to you, who carries this forward?
            </label>
            <input
              id="ob-recovery"
              className={inputCls}
              placeholder="A person you trust"
              value={recovery}
              onChange={(e) => setRecovery(e.target.value)}
            />
            <p className="mt-1.5 max-w-[460px] text-[12.5px] text-[#64748B]">
              You can skip this — we&apos;ll ask again later, gently. We only
              ask because every group should have a will, and it&apos;s kinder
              to name someone before you need to.
            </p>
            <label htmlFor="ob-fund" className={labelCls}>
              What do you want to fund first?{" "}
              <span className="font-normal text-[#64748B]">(optional)</span>
            </label>
            <input
              id="ob-fund"
              className={inputCls}
              placeholder="e.g. a roof, a stipend, a retreat"
              value={fund}
              onChange={(e) => setFund(e.target.value)}
            />
          </div>
        )
      case 6:
        return (
          <div>
            <div className="mt-5 max-w-[560px] rounded-2xl border border-[#DDD6FE] bg-white p-5">
              <h3 className="mb-1.5 text-base font-semibold text-[#2E1065]">
                Lend, don&apos;t give.
              </h3>
              <p className="text-[13.5px] leading-snug text-[#475569]">
                Letting an app post a message or make a scheduled payment means
                lending it one narrow permission — scoped, revocable, and yours
                to take back anytime.
              </p>
            </div>
            <div className="mt-4 flex items-start gap-2 text-[13px] text-[#64748B]">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[#A78BFA]" />
              <span>
                <em>
                  Agreeing records a cryptographic receipt of your consent — on
                  the record, never a secret.
                </em>
              </span>
            </div>
          </div>
        )
      case 7:
        return (
          <div className="mt-5 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            {[
              {
                h: "Your group",
                p: `${slug.trim() || "your group"} — with its shared spaces ready.`,
              },
              {
                h: "Treasury",
                p: "Private until you choose to show it. Proofs, not balances.",
              },
              { h: "Needs your signature", p: "Nothing yet. It'll find you." },
              {
                h: "Your people",
                p: "Ready to invite — one link, one sign-in.",
              },
            ].map((c) => (
              <div
                key={c.h}
                className="rounded-2xl border border-[#DDD6FE] bg-white p-5"
              >
                <h3 className="mb-1.5 text-base font-semibold text-[#2E1065]">
                  {c.h}
                </h3>
                <p className="text-[13.5px] leading-snug text-[#475569]">
                  {c.p}
                </p>
              </div>
            ))}
          </div>
        )
      default:
        return null
    }
  }

  return (
    <>
      <main
        className="flex min-h-screen items-center justify-center p-6"
        style={{
          background:
            "radial-gradient(1200px 600px at 80% -10%, #EDE9FE 0%, transparent 60%), radial-gradient(900px 500px at -10% 110%, #DCFCE7 0%, transparent 55%), #FAF5FF",
        }}
      >
        <div className="relative flex min-h-[600px] w-full max-w-[960px] flex-col overflow-hidden rounded-[28px] border border-[#DDD6FE] bg-white shadow-[0_30px_80px_-30px_rgba(76,29,149,0.35)]">
          {/* top bar */}
          <div className="flex items-center gap-3.5 border-b border-[#DDD6FE] px-7 py-5">
            <div
              className="flex items-baseline gap-1 text-[22px] font-bold tracking-tight text-[#2E1065]"
              style={serif}
            >
              irl<span className="text-[#16A34A]">.</span>coop
            </div>
            <div className="ml-2 h-1 flex-1 overflow-hidden rounded-full bg-[#EDE9FE]">
              <div
                className="h-full rounded-full transition-all duration-[400ms]"
                style={{
                  width: `${((step + 1) / total) * 100}%`,
                  background: "linear-gradient(90deg,#7C3AED,#A78BFA)",
                }}
              />
            </div>
            <div className="whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              {step + 1} / {total}
            </div>
            <button
              type="button"
              onClick={() => go(total - 1)}
              className="hidden whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[13px] font-medium text-[#475569] transition hover:bg-[#EDE9FE] hover:text-[#4C1D95] sm:block"
            >
              Skip to your world →
            </button>
          </div>

          {/* body */}
          <div className="flex flex-1 flex-col justify-center px-12 py-10 max-sm:px-6">
            <div key={step}>
              <div className="mb-3.5 text-xs font-bold uppercase tracking-[0.16em] text-[#16A34A]">
                {s.eyebrow}
              </div>
              <h1
                className="mb-4 text-[clamp(30px,5vw,46px)] font-semibold leading-[1.08] tracking-tight text-[#2E1065]"
                style={serif}
              >
                {s.title}
              </h1>
              <p className="max-w-[58ch] text-[17px] leading-relaxed text-[#475569]">
                {s.lead}
              </p>
              {renderContent()}
            </div>
          </div>

          {/* controls */}
          <div className="flex items-center justify-between gap-4 border-t border-[#DDD6FE] px-7 py-4 pb-6">
            <button
              type="button"
              onClick={() => go(step - 1)}
              className="inline-flex items-center gap-2 rounded-xl px-5 py-3 text-[15px] font-semibold text-[#475569] transition hover:bg-[#EDE9FE] hover:text-[#4C1D95] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7C3AED]"
              style={{ visibility: step === 0 ? "hidden" : "visible" }}
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <button
              type="button"
              onClick={() =>
                isLast
                  ? alert("Demo — in the real flow this sends invitations.")
                  : go(step + 1)
              }
              className={
                isLast
                  ? "inline-flex items-center gap-2 rounded-xl bg-[#16A34A] px-5 py-3 text-[15px] font-semibold text-white shadow-[0_10px_24px_-10px_rgba(22,163,74,0.55)] transition hover:bg-[#15803D] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16A34A]"
                  : "inline-flex items-center gap-2 rounded-xl bg-[#7C3AED] px-5 py-3 text-[15px] font-semibold text-white shadow-[0_10px_24px_-10px_rgba(124,58,237,0.6)] transition hover:bg-[#6D28D9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7C3AED]"
              }
            >
              {isLast ? "Invite your people" : "Continue"}
              {!isLast && <ArrowRight className="h-4 w-4" />}
            </button>
          </div>

          {/* tagline */}
          <div
            className="pb-5 text-center text-[15px] italic text-[#64748B]"
            style={serif}
          >
            {s.tagline}
          </div>
        </div>
      </main>
    </>
  )
}
