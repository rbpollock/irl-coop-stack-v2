# Cooperation Starter Pack — survey templates for groups forming, running, and repairing ventures

Status: design · Sep 2026 · Author: Robbie + Hermes.
Companion: `formbricks-customization-scope.md` (how these get built/skinned),
`onboarding-flow.md` (verticals + voice), `needs-offers-matching.md` (what the
outputs feed), `private-treasury-guards-ledgers.md` (money questions).

Premise: a set of people in a chat — often strangers to each other and to
cooperation — want to figure out whether and how to do something together (start a
tool library, a time-bank, a worker co-op, a mutual-aid pod, a buying club). These
surveys are the *instruments* for that conversation. Short, plain, runnable from a
phone in a chat, and each one produces a **shared artifact** the group can act on.

## Design rules (first-timers, and our own principles)

1. **4–7 minutes, 3–8 questions.** Nobody does a 40-question org-development
   instrument in a group chat. Depth comes from running several short surveys over
   time, not one long one.
2. **One concept per screen, plain language.** No jargon: not "governance", say
   "how we make decisions"; not "stakeholder alignment", say "where we agree and
   where we don't". Voice rules from `onboarding-flow.md` apply.
3. **The output is an artifact, not a score.** Every survey ends with something the
   group can use: a charter seed, an agreement draft, a tensions list, a duty roster.
   **No alignment percentages, no rankings of people, no "you scored 6/10 on
   cooperativeness".** (`badges prove contribution, never worth` — an assessment that
   grades people creates status and kills the honesty we're after.)
4. **Anonymity is a per-survey choice, declared up front.** Sensitive ones (pulse,
   tension, power audit) default to anonymous with a "how results are shown" note;
   the identity-bearing ones (gifts/needs, purpose) are attributed because the group
   needs to know who.
5. **Opt-out and exit are always visible**, and no one is gated from participating
   for skipping a survey. `no shame, ever — a carrot, not a stick.`
6. **Every survey ends with a next step** (one tap): see the combined results, book
   the conversation, invite someone, or start the next survey in the sequence.
7. **Results are conversation scaffolding, not verdicts.** Each template ships with a
   one-paragraph "how to read this together" card for the group.

## The pack (short list — 7 core + 2 optional)

Lifecycle: **orient → inventory → form → decide → operate → diagnose → repair.**

| # | Survey | When | ~Q | Produces | Verticals / docs |
|---|---|---|---|---|---|
| 0 | **Is cooperation for you?** | solo, before any group; public link | 6 | a personal fit reflection + suggested "shape" (self-organising circle / structured coop / worker coop / tool pool) + a next step | onboarding-flow (Step 3–4), the funnel |
| 1 | **What we bring, what we need** | first group activity | 7 | a gifts/needs/capacity ledger — doubles as the needs/offers seeding | needs-offers-matching, time-bank |
| 2 | **Why we're here (purpose & non-negotiables)** | forming | 6 | overlap map: shared purpose statements + each person's deal-breakers and exit conditions → charter seed | group shapes (seed-not-cage) |
| 3 | **How we decide (working agreements)** | forming | 7 | decision method, meeting rhythm, transparency, money handling, conflict path → "rules we can live with" draft | account-and-key-model (constitution), facilitation |
| 4 | **Where we actually differ** | after 2+3 (per pair/whole) | 4 | the divergence view — biggest gaps between answers, and which gaps are fine vs fatal → the agenda for the first real meeting | alignment check (analysis over 2+3, not a new survey) |
| 5 | **Pulse: how are we doing?** | weekly/fortnightly, recurring | 3 | what's working / what's stuck / what I need — trend over time → the diagnosis loop, feeds expediting | event-bus, arbitration/escalation |
| 6 | **Power & participation audit** | every ~3 months, or when it stalls | 6 | who decides what, who's unseen, whose care work is uncounted → concrete rebalancing proposals | psychodynamics, group design |
| 7 | **Money & risk check-in** *(optional)* | when money is pooled | 6 | what we pool, what's owed to whom, what happens if it breaks or someone leaves → treasury terms draft | private-treasury-guards-ledgers §10 |
| 8 | **Tension & repair** *(optional)* | on conflict | 5 | structured: what happened / impact / what I need / what I'll do — with an opt-in path to a facilitated session | conflict & repair, arbitration escalation |

Why *these* seven: they cover the four moves first-time cooperators must make —
**can we? (0–1) → what binds us? (2–3) → is this still alive? (4–6) → how do we
repair it? (8)** — and each one is short enough to actually get answered. Almost
every failure of a young coop shows up as one of: unclear purpose, unspoken
expectations, unexamined power, uncounted labour, or avoided conflict. The pack
targets exactly those five.

## Stage notes (what a first-timer needs)

- **Orient (0):** the only survey that stands alone in public. Its job is *learning
  and reflection first, funnel second* — a person should leave with a clearer picture
  of what they want even if they never sign up. Suggested shape comes from their own
  answers (autonomy↔coordination, capacity, tolerance for slow decisions, appetite
  for money risk), never from a norm.
- **Inventory (1):** the generosity of this one is what makes groups work: people
  discover skills and resources in the room they didn't know about. Include "what I
  can offer once vs ongoing", "what I need", "what I'd like to learn", and capacity
  in hours/energy — deliberately not in money.
- **Form (2–4):** keep 2 and 3 individual-then-shared (everyone answers separately,
  then the group sees the overlap and the gaps). 4 is not a new survey: it's the
  *comparison view* of 2+3, which is why it's cheap and high-leverage.
- **Operate (5–6):** the pulse is the heartbeat — it must be so cheap to answer that
  it survives busy weeks, and anonymous, or people will lie politely. The audit is
  the instrument that catches the slow drift where three people do everything.
- **Resolve (8):** never mandatory, never public by default. Its real output is
  often "we need a third party" — so it ends by offering a facilitated session.

## The funnel (this is where the whole stack clicks)

0 is a **public link survey** on `surveys.irl.coop` (ungated) — exactly the
custom-head-scripts + token path we already built. Its ending card uses the
survey-completed CTA we repointed: **`https://irl.coop/signup?intent=formbricks`**.
So the path is: assessment → reflection → signup → a workspace **born irl.coop-styled**
(auto-skin, §6e) → the rest of the pack as surveys to copy. The learning tool *is*
the acquisition path, and the person arrives already understanding what they're
joining.

## How to build them (implementation options)

1. **Now, cheapest:** create the pack as surveys inside a `Blueprints` workspace in
   our instance and let groups **duplicate** them (Formbricks' duplicate survey works
   today, no fork). Store the reading cards in each survey's welcome/ending screens.
2. **Later, nicer:** add them as a real **template pack** in our fork (upstream
   templates are code-level definitions) so "start from a blueprint" appears in the
   create-survey gallery — bigger patch, better discovery.
3. **Publish:** list the public ones (0, and read-only previews of 2–3) on a
   `blueprint library` page via Webstudio, linking the live survey.

## What I'd build first (highest utility, lowest cost)

1. **0 — Is cooperation for you?** (public, skinned, ends in the signup CTA)
2. **2 — Why we're here** + **3 — How we decide** (the pair that prevents the most
   common failure; 4 comes free as their comparison view)
3. **5 — Pulse** (recurring; proves the loop works and feeds the bus later)

Those four cover orient + form + operate. 1, 6, 7, 8 follow the first time a real
group asks for them.

## Open questions

- Do we hold a canonical **answer key/shape map** (which answer patterns suggest
  which coop shape), or keep shape suggestions purely reflective? (Risk: prescription
  creates a norm; benefit: first-timers want orientation.)
- Anonymity: does the pulse use Formbricks' anonymous links, or per-group policy
  (some groups will want names attached to fix things)?
- Do the artifacts land anywhere durable (a group's Blueprint/notebook, Webstudio
  page) or stay as survey responses to discuss? (Feeds the "blend the docs" question.)
- Naming: "Cooperation Starter Pack" vs tying it to the weaving vocabulary
  (loops/weavings) — the coop's own words might serve better than a borrowed one.
