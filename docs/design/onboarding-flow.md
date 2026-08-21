# Onboarding Flow — Design

Status: design · Aug 2026 · Author: Robbie + Hermes.
Sources: regenerative-vision-note.md · account-and-key-model.md · irl-coop-group.md ·
event-bus-and-group-shapes.md · private-treasury-guards-ledgers.md ·
world-doc-and-contacts.md · delegation-and-session-keys.md.

Companion prototype: `onboarding-prototype.html` (same directory).

---

## 1. What this is

irl.coop's first impression. It has to do three jobs at once:

1. **Teach the one idea** — groups are the primitive; a person is a "group of
   one"; groups connect into a graph. Everything else (composability,
   interoperability, sovereignty) falls out of that.
2. **Make building feel inevitable and exciting** — the verticals (facilitation,
   conflict & repair, group design, psychodynamics) are the hard things, the ones
   that usually can't be coordinated or funded. Onboarding shows they're *startable*.
3. **Set up the account invisibly** — a user should leave onboarding fully
   provisioned (own Safe, a seat in irl.coop, passkey, succession registered,
   a first shape or an empty group) having never seen a key, a threshold, or the
   word "Safe".

This document records *what a user needs to know* and *what they need to set up*,
distilled from the design docs, and the flow that delivers both.

---

## 2. Design principles (non-negotiable)

1. **Groups are the primitive, not the user.** We never introduce "your account"
   as separate from "a group." You are a group of one; a co-op is the same thing
   with more seats. (account-and-key-model.md §1.2)
2. **Simplicity first — sovereignty invisible.** Members never see keys,
   thresholds, or "Safe." Passkey-first; recovery feels like a normal web reset;
   group membership is invisible ownership math. (account-and-key-model.md §1.4)
3. **Seed, not cage.** A shape is a starting point, not a destiny. Copy-then-modify.
   (event-bus-and-group-shapes.md §3.1)
4. **Lend, don't give.** Every grant of power is scoped and revocable. This is the
   trust model in one line. (delegation-and-session-keys.md)
5. **Privacy by default, provable when it matters.** We show proofs, never raw
   internals. "Coverage, not clout." (event-bus-and-group-shapes.md §6–7)
6. **Eager to build.** Every screen ends with a next step that moves toward other
   people — invite, pick a shape, fund something. Onboarding never dead-ends in a
   profile.
7. **Pre-commitment is care.** The hard questions (who recovers this? how do we
   leave?) are asked at formation, framed as kindness, not bureaucracy.
   (account-and-key-model.md §4 "boundary conditions")

---

## 3. What a user needs to KNOW (concepts → plain language)

| Concept (doc) | Plain language for onboarding | Where it lands |
|---|---|---|
| Groups are Safe-accounts; a person is a 1-of-1 group (account-and-key-model §1) | "You are a group of one. A co-op is the same thing with more seats." | Step 1, 2 |
| Composability: a Safe can be an owner of another Safe (account-and-key-model §1) | "A group you build can be a member of another group — like you are. Nothing is a silo." | Step 2 |
| Nodes + edges = cooperative graph (irl-coop-group §1.1) | "Your world is a graph, not a feed." | Step 2, 7 |
| Shape = roles/apps/config/governance/proofs, seed-not-cage (event-bus §3) | "Start from a blueprint, then make it yours. It's a seed, not a cage." | Step 4 |
| Event/notification bus, one source → any channel (event-bus §2) | "One place to hear from every group — on your terms." | Step 7 (world-doc) |
| Private ZK treasury; project sub-scopes; capital pools (treasury §2) | "Money that's yours to move, private until you choose to show it." | Step 3, 5 |
| Commons economy — pay-what-you-want, coverage proofs (event-bus §7) | "Keep the lights on. Reveal good citizenship, not your means." | Step 3 |
| Delegation — scoped, revocable permits (delegation doc) | "Lend power to an app, a schedule, a person — take it back anytime." | Step 6 |
| Succession / every Safe has a will (account-and-key-model §4) | "If something happens to you, who carries this forward?" | Step 5 |
| Seats — one persona per group, presentation attached (world-doc §4) | "Be 'Coordinator' at the co-op and 'Robert' with family — without switching hats." | Step 7 |
| Regenerative score — proof of contribution, never worth (vision + event-bus §6) | "A score that proves you showed up — without revealing how much you have." | Step 3 (soft) |

The rule: **one concept per screen, in one sentence, then move.** The deep version
lives in the docs; onboarding only needs the felt sense.

---

## 4. What a user needs to SET UP (steps → what it really creates)

| Step | User action | What actually happens (stack) |
|---|---|---|
| 0. Arrive | Read the promise | — |
| 1. You | Sign in (Google/passkey) + name + avatar | Keycloak login → person provisioning → own Safe (CREATE2 from passkey material) → profile (onboarding.ts) |
| 2. The idea | Understand "you are a group of one" | (no new state — comprehension gate) |
| 3. Vertical pick | Choose what you want to do first | Seeds an intent → the shape picker (Step 4) filters to it |
| 4. First shape | Pick a blueprint + name + slug | `POST /api/group/*` → group Safe deploy → deterministic subdomain + mail domain + Matrix space/rooms (one name drives all) |
| 5. Warm questions | People to invite · recovery contact · first fund | Explicit contacts (world-doc) · succession registration · treasury project-scope intent |
| 6. Consent | Agree to terms (hashed) | Consent hash on-chain · entitlements granted (Keycloak groups/roles) |
| 7. Land | See "your world" | World-doc projection: seats, rooms, treasury view, approval inbox (empty) — rebuilt, never stored |

Everything after Step 1 is **lazy and idempotent** — onboarding never blocks on a
downstream service being up (account-and-key-model §"JIT-first + lazy
materialization"). A skip anywhere still lands the user in a working world.

---

## 5. The flow (step-by-step with copy)

### Step 0 — Arrival ("the world is atomized; the fix is cooperation")
- Headline: **"We were never more connected. We were never more alone."**
- Body: "irl.coop is for people who want to build something together — a circle, a
  co-op, a fund, a team — and keep it theirs. Your rules, your money, your people,
  nobody in the middle. And a library of blueprints, so you don't start from scratch."
- CTA: "Start — it takes a minute." / "Read the story" (secondary).

### Step 1 — You
- Headline: **"You are a group of one."**
- Body: "Before you join anyone else, you're already a group of your own — one seat,
  one voice, fully yours. Every group you join or start after this is just another
  connection to it."
- Fields: name, avatar (reuse onboarding.ts).
- Micro-copy: "This quietly sets up your own account underneath. You'll never have to
  think about keys or wallets."

### Step 2 — The one idea
- Headline: **"Your world is a graph, not a feed."**
- Body: "You're a point. Every group is a line between points. And a group can live
  inside another group — a working group inside a co-op, a co-op inside a bigger
  network. That's what *composable* means: what you build can join what others build,
  and it stays yours."
- A small animated diagram: one node → edges → nested groups.

### Step 3 — What you'll build (the verticals)
- Headline: **"The hard things, made startable."**
- Lead: "Some of the most important work — running a room where everyone's heard,
  mending a rift, shaping a group that doesn't fall apart, noticing what's going on
  under the surface — is exactly the work that's hardest to coordinate and hardest
  to fund. Here, it's where we start."
- Four cards (vertical + working-capital line):
  1. **Facilitation** — "Run a room where power isn't hidden." → "Standing space, roles, a decision log — funded by the room's own pool."
  2. **Conflict & repair** — "Mediate a rift and restore trust." → "A neutral space, an arbiter you name up front, a fund for repair work."
  3. **Group & org design** — "Shape a group that doesn't bottleneck." → "Blueprints for structure — thresholds, boundaries, exit rights — set before the crisis."
  4. **Psychodynamics** — "Read what's beneath the stated agenda." → "Practitioner circles, supervision, safe containers — paid, because attention is work."
- Micro-copy: "Healing and cooperation are different muscles. Both are built by
  practice, not reading — that's what these are for."

### Step 4 — Your first shape
- Headline: **"Start from a seed, not a cage."**
- Body: "Pick something close to what you have in mind. It's just a starting place —
  you'll change it as you go, and nothing is locked in."
- Picker: Circle · Co-op · Working group · Mutual-aid fund · Empty (start from scratch).
- Then: name + one-word slug. Micro-copy: "One name drives your group's home, its
  inbox, and its shared spaces."

### Step 5 — Three warm questions
- Headline: **"Asked early, because it's kinder early."**
- Lead: "These are easier to answer on a calm day than in the middle of something hard."
  1. "Who are your people?" (invite 1–3 now, or skip)
  2. "If something happens to you, who carries this forward?" — **skippable, explained.**
     Hint: "You can skip this — we'll ask again later, gently. We only ask because every
     group should have a will, and it's kinder to name someone before you need to."
  3. "What do you want to fund first?" (optional — seeds a treasury project-scope)

### Step 6 — Consent & trust
- Headline: **"Your rules are yours. Here's how we keep them."**
- Body: "What's yours stays yours — your group, your money, your people. If an app or
  a person helps out, they're borrowing a narrow permission, never owning anything,
  and you can take it back whenever you like."
- A clear "Agree" (terms hash recorded on-chain) + a "learn more" link.

### Step 7 — Your world
- Headline: **"This is your world."**
- Body: "Not a feed, not a profile — a living picture of the people and groups around
  you, and what needs your attention."
- Show: the group (with its rooms), the treasury view (proofs, not balances),
  the "needs your signature" inbox (empty), and:
- CTA: **"Invite your people"** (primary) · "Browse the blueprint library" (secondary).

---

## 6. Voice & tone

- **Warm and direct — a conversation between people who care about each other.** Short
  sentences, plain contractions ("you're", "it's"), "we" and "you" instead of the
  royal "the platform". If a line reads like a landing page, rewrite it the way you'd
  say it to a friend across a table. No crypto jargon, no "empower/leverage/unlock."
- **Hopeful, not utopian.** Acknowledge the problem (atomization) honestly, then
  answer it. Never overpromise — "built in" only when it is.
- **Plain where possible, poetic once per screen.** One memorable line per step
  ("you are a group of one", "seed, not cage", "lend, don't give").
- **Human-first.** The verticals are about *people* — facilitation, repair, design,
  reading a room — before they're about software.
- **No shame, ever.** The commons economy is a carrot, not a stick (event-bus §7).

## 7. Visual system (from ui-ux-pro-max)

- **Colors:** primary purple `#7C3AED`, join-green accent `#16A34A`, warm
  background `#FAF5FF`, ink `#4C1D95`, muted `#475569`.
- **Type:** Cormorant Garamond / Crimson Pro (serif, warm, "library of blueprints"
  mood) for display; a clean humanist sans for UI/labels.
- **Layout:** block-based, generous spacing (48px+), large type (32px+), soft hover
  color-shifts, 200–300ms transitions, reduced-motion respected.
- **Icons:** line SVG (Lucide), never emoji.

## 8. What to decide before building

1. **Gate the verticals now or show all four?** Recommend: show all four, let
   intent filter the shape picker — the verticals *are* the pitch.
2. ~~Step 5 succession question — required or skippable?~~ **Decided: skippable and
   explained.** Asked warm ("who carries this forward?"), with an honest hint that you
   can skip and we'll ask again later, gently. Never a blocker.
3. **Skip-to-world escape hatch** on every step (JIT-first principle).
4. **Where the prototype ships** — as a real route in irl-dashboard, or as a
   standalone flow under `/welcome`.
