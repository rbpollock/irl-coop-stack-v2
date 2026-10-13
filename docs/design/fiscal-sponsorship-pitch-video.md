# Fiscal-sponsorship pitch — video plan

Status: plan · 2026-09-30 · audience = 501(c)(3) orgs working in the solidarity
economy, cooperative economics, and sustainable economics (New Economy
Coalition network, USSEN, USFWC/DAWI, SELC, regional networks, and
values-aligned fiscal sponsors like the Movement Sustainability Commons).

Ask: **become our fiscal sponsor** — collect tax-deductible donations on
irl.coop's behalf and pass them through a transparent, governance-controlled
rail into the group's Safe.

**Planning context (2026-09-30):** we are planning our own Wyoming nonprofit
("duna") to be the operating entity — draft bylaws and operating agreements
already exist. It is **structured exactly like the co-op**, with one exception:
a rotating board that **ratifies on-chain governance from irl.coop members as a
formality**. That inversion is the point — the nonprofit does not *govern* the
co-op; it provides the legal/tax wrapper and formally stamps what the members
already decided on-chain.

This changes the pitch's *character* but not its structure: fiscal sponsorship
is the **bridge** to that formation — the values-aligned, tax-deductible lane
for the movement to fund us **now**, while the entity finishes standing up. The
honesty line ("we have no operating entity yet") stays on screen and carries
its own resolution: entity drafted, in formation. And when the bridge becomes
unnecessary, the allocation won't have been wrong — the sponsor's role was a
temporary lane, explicitly stated. See §4a.

This is a *different* piece from the intro series
(`intro-video-series.md`, audience = prospective member groups). This is an
**institutional partner pitch** to mission-holder organizations about how the
movement funds its own infrastructure. It shares the same DNA — honesty rules,
the "sponsorship, not investment" line (`capital-campaign-subgroup.md` §5), the
coverage-proof primitive, the cooperative spine — but it argues for **funding**
rather than **running cost**.

## Anchoring inputs (read these before producing anything)

- `money-in-and-out.md` §6 — the missing operating legal entity (decision #5).
  This is the honest, concrete reason fiscal sponsorship exists for us.
- `capital-campaign-subgroup.md` — the `sponsored-by` edge, no-control
  contributor pattern, "contribution ≠ investment."
- `fundraising-programmable-transfers.md` — campaign surface + coverage proof.
- `cost-model.md` — why the commercial stack fails the movement (the numbers
  behind "the wall").
- `digest-group-shapes-event-bus-proofs-economy.md` — the commons economy and
  vertical funds.

**Honesty baseline: the fundraising surface, campaign Safe, and coverage
endpoint are DESIGN, not built. The pitch must never present them as shipped.**
This is non-negotiable, because the premise of the pitch is "we prove our
spending" — faking the proof would kill the pitch (§5).

---

## 1. The organizations — missions, in their own words

Researched 2026-09-30 from the orgs' own sites; founding facts cross-checked
against Wikipedia.

### New Economy Coalition (NEC) — ~200-300 member orgs, US/Canada
Founded 2012 (out of the Great Recession, from the E.F. Schumacher Society
lineage). A worker self-directed nonprofit (WSDN) since 2021: **no Executive
Director**, a General Circle of elected staff + member-elected board runs
personnel, finance, and program decisions. North star: a future where "people,
communities, and ecosystems thrive **capital is a tool of the people, not the
other way around**." Mission centers BIPOC and working-class communities and a
"just transition from an extractive to a regenerative economy." Maintains the
**Solidarity Economy Funding Library** (foundations, fiscal sponsors, credit
unions, non-extractive investors), whose resources explicitly document fiscal
sponsorship. **NEC's own members live the fiscal-sponsor model.**

### U.S. Solidarity Economy Network (USSEN)
A catalyst/umbrella connecting SE projects regionally → nationally →
internationally (member of RIPESS). Governed sociocratically — volunteer
rotating board, consent-based, with board seats for aligned national
coalitions (NEC, MayFirst, USFWC). Mission: replace "extractive economic models
with [practices] that center equity and liberation for all."

### US Federation of Worker Cooperatives (USFWC) + Democracy at Work Institute (DAWI)
Membership + advocacy for worker coops; "connect worker co-op members to
benefits, to each other, to the larger cooperative and economic justice
movement." DAWI focuses on ensuring co-op development in economically and
socially marginalized communities is "adequately supported, effective, and
strategically directed."

### Sustainable Economies Law Center (SELC)
Wrote the fiscal-sponsorship resources that NEC's Funding Library cites: "How
to Receive Grants and Donations through a Fiscal Sponsor", "Funding Economic
Democracy: A Legal Toolkit." **Our most literate possible audience** — they carry
the book we are pitching; we are not teaching them a model.

### Movement Sustainability Commons / Resist
Exists to "support community organizers and solidarity-economy practitioners
to align drawing with movement values." Runs fiscal sponsorship under Resist's
grant-review frameworks, explicitly reviewing projects for mission alignment
first, legal fit second. **This is an org whose whole filter is our exact
pitch.**

### Regionals (NEC member list, thematically representative)
Co-op Cincy, MadWorC, Cooperation New Orleans, Solidarity Economy St. Louis,
Cleveland Owns, VA/MA networks, etc. The repeating language across all of them:
economic democracy, community control of resources, cooperative ownership,
closing the wealth gap, mutualism/reciprocity, place-based power, BIPOC and
working-class community leadership.

---

## 2. The themes that repeat across every one of them

1. **Transition: extractive → regenerative.** The economic system itself, not
   pocketbook fixes.
2. **Democratic governance is the instrument.** Their own structures (worker
   co-dir, sociocracy, member-elected boards) are the seal — governance and
   mission are the same sentence.
3. **Power rooted in place and community.** Local control of resources; BIPOC,
   working-class, immigrant, and other excluded communities centered.
4. **Mutualism / reciprocity / care** — the loop, the gift that returns.
5. **Network over silo.** Regional ↔ national ↔ international connection
   (RIPESS everywhere in the source language). Not merely "we reach each
   other" — **federate and interconnect**: the same software, data models, and
   resource-sharing between groups, now easy to implement on common tech, so
   the network isn't a directory of silos but an actual interoperating mesh.
6. **Money aligned with values.** Non-extractive capital, trust-based funding,
   "align fundraising with movement values" (Resist verbatim).
7. **Self-determination and exit.** Each org chooses its own model, owns its
   tools and its money, and can leave — no lock, no vendor veto.
8. **No single point of control in the tools.** The tooling must not force the
   group to choose its own weakness — either *every organizer holds the admin
   key* (a security sieve, no accountability) or *one person holds it* (that
   person becomes the whole group's authority — and its single point of
   failure). Cooperation needs per-member, scoped, revocable access, so a
   group is never governed by whoever happens to hold the password.

---

## 3. What irl.coop delivers per theme — the match thesis

| Their theme | What irl.coop delivers | Proof status |
|---|---|---|
| 1. Extractive → regenerative | Regenerative score (ZK-composed); the commons economy; funding as a *flow* not a market | design + live primitives |
| 2. Democratic governance | Safe seats, no hidden hierarchy, quorum votes, thresholds; grants scoped **by the seat's group** (`coop_has_grant`) | **live** (roles/seats/votes) |
| 3. Place & community power | Geo is core ("irl" = real life); own map app; hyperlocal ↔ global; DIY node = real local ownership | **live** (mapping) |
| 4. Mutualism / reciprocity / care | needs/offers "weaving"; reciprocity → regenerative score | live + design |
| 5. Network over over silo | The federation is the network's **own** infrastructure — the rails a network points at | thesis (this is the pitch) |
| 6. Values-aligned money | No take-rate, cooperative parent, **coverage proof** ("raised ≥ X…"), proving spend not books | design |
| 7. Autonomy + exit | **Export everything and leave**; governance custody — the group remains sovereign | design + live primitives |
| 8. No single point of control | Per-member Safe seats, roles, votes — scoped, revocable access; the group is never governed by whoever holds one admin password | **live** (roles/seats/votes, per-member identity) |

**The single thesis that packages all of it:**
> The solidarity economy already moves the things that matter — generosity,
> skill, reciprocity, mutual care. What still holds it back is the money
> movement and the record-keeping. Those still run on tools whose cost
> scales with each person you add — a fee on every transfer, a seat for
> every member, a record for every donor — and where no accountable rail
> exists at a small group's size, the work leaks into channels that leave no
> trace and smolder trust. The movement that exists to build a different
> economy keeps paying the one it is leaving — not because it is fooled, but
> because there were no rails sized for it. irl.coop is the stack made for
> that size: infrastructure a community owns and runs itself, so the money
> and the record keep returning to the loop — and the loop is the point, not
> the tool.

## 4. The fiscal-sponsorship ask, framed honestly

**The real incentive: `money-in-and-out.md` §6 lists decision #5 — the legal
entity doesn't exist yet.** "Statutory bookkeeping falls on an operating entity
that does not exist yet: taxes, and the whole compliance story." This is not a
warm-feelings ask; it's a structural gap that fiscal sponsorship is exactly the
answer to. **Plan in progress, not a hole:** the line is now paired with its own
resolution on screen — a Wyoming nonprofit is being planned as the operating
entity, so the ask is time-boxed. Fiscal sponsorship is the *now* lane, not a
permanent custodial role for the sponsor.

**What we're asking — direction is exact:** *the sponsor accepts the donation
on irl.coop's behalf.* We are the **sponsored project**, not the immediate
donee. Concretely: a donor gives **to the 501(c)(3) sponsor** (that's who
receives the money and issues the tax receipt — the IRS-recognized donee); the
sponsor then passes it through, per the stated purpose and its own compliant
process, into irl.coop's rail and on to the group's Safe. The `sponsored-by`
edge (economics + recognition, **no control**, no equity) — the exact semantics
already designed in `capital-campaign-subgroup.md` §1 — records that the money
is *recognized*, not that the sponsor owns any of it.

So the relationship is always and only: **donor → sponsor (IRS donee) →
irl.coop (project) → Safe**. The sponsor is not merely forwarding mail; they
are the organization that makes the gift deductible and takes on the
compliance duty of receiving it — which is precisely the licence they already
hold and the skill from the fiscal-sponsorship toolkits (SELC) they already
practise.

**Why this is mission fulfillment for them, not charity:**
- They already do this. NEC's Funding Library lists fiscal sponsors; the SELC
  wrote the legal toolkit. We aren't teaching the model — we're offering a
  project whose values and accounting make this the cleanest sponsorship they
  could take on.
- It's direct mission fulfillment: "align fundraising with movement values"
  (Resist), "build the movement's own infrastructure." We're not a foreign
  charity on their list; we're the movement's plumbing, asking for a
  recognized due lane.
- We carry our own compliance surface — a publicly disclosed purpose, preset
  rules, and coverage proofs. They file the standard sponsor overhead, not a
  trust-in-visibility operation.
- **The sponsor's fee is 10% of everything donated, stated plainly** (§4a) —
  not free, not below-market, not hidden. "We're not claiming admin-free; we're
  saying the admin is values-aligned and legible at a price we name."
- irl.coop publishes coverage proofs, not books: "raised ≥ X, routed ≥ Y, paid
  ≥ Z" against an anchored root. The sponsor doesn't need to defend a story; we
  show a receipt chain that stays private.
- **Exit is built in**: if a member group or the whole cooperative leaves, the
  funds follow to the Safe that already holds them. `sponsored-by` + Safe means
  the sponsor is a *channel that has a practice*, not a looming controller.

**§4a — The sponsor takes 10% of everything donated.** That is the deal, real
and pre-negotiated. It is NOT hidden, NOT "below-market," NOT waived. We say it
out loud because the whole pitch is "we prove our spend" — a hidden fee would
poison it. Two honest consequences the film must hold:

- 10% is the cost of the tax-deductible lane. Donors get the deduction; the
  coop pays a tenth of every dollar raised for the compliance wrapper. That is
  a reasonable and disclosed price — the plan does not spin it as a favor.
- It shapes the *ask*: because a tenth of every dollar leaves, the pitch
  should be honest that we're not maximizing the take, we're choosing the
  movement-aligned sponsor over a generic one at the same rate. The difference
  is *whose* 10% and what it pays the movement for.

## 5. The video — format, beats, evidence

**Format** (matches the established pipeline — no faces; voiceover with
NeuTTS/humanized track; screens are receipts, animation is claims only,
`intro-video-series.md` §2). **Length 2–3 minutes** — an institutional pitch
that's meant to be paused and rewritten by the viewer.

**Beat sheet (full VO to be written in a later pass):**

| # | Time | Beat | On screen | Status |
|---|---|---|---|---|
| 1 | 0:00–0:25 | **The two worlds**: value circulates (a co-op) / value exits (the rented stack). | value-flow split diagram | live/diagram |
| 2 | 0:25–0:45 | **The movement's own words** — "extractive → regenerative", "people before profit", "trust-based funding". Let the audience recognise its own language. | fade their own quotes, attributed | factual, their words |
| 3 | 0:45–1:20 | **The reason we ask:** there is no operating legal entity yet — the honest admission. *This is why we need you.* It's a gap the movement's own licensing already documents. | `money-in-and-out.md` §6 line shown; then "entity drafted, in formation" (duna) | the real open problem + resolution |
| 4 | 1:20–2:00 | **The direction, made exact**: the donor gives **to you**; you are the IRS donee and issue the receipt; you pass it through, and it lands in the group's Safe. Nobody gets control. | the `donor → sponsor → project → Safe` flow with the `sponsored-by` edge labelled "no control" | designed (semantics coded) |
| 5 | 2:00–2:40 | **Proof, not faith**: coverage proves "raised ≥ X, routed ≥ Y"; the ledger stays the group's. And the deal, named: **the sponsor takes 10% of everything donated** — that's the price of the lane. "We prove the spending, not the books, at a fee we name." | the proof frame + the 10% stated on screen | frank (design proof) |
| 6 | 2:40–3:00 | **The ask, plainly:** "Act as the lane the gift is made through — you receive it for the coop the way you receive the mission." | a concrete, dated ask | honest |

**A subject we must not put on screen as shipped:** the fundraising surface,
the campaign Safe, the coverage endpoint, the edge registry. Those are
`design`. Screen them only as "how it's designed to work" — or cut them. What
we *can* screen as real is the direction itself: **the sponsor accepts the
gift, the project receives it** — that is the fiscal-sponsorship model, not a
feature.

## 6. Honesty constraints (the paid for the whole thing)

The audience is the orgs most able to catch a platform pitch, so honesty is the
format:

1. **"We're a co-op" only where true.** Safe/roles/votes are live; the
   WSDN/co-directorate forms are vision, not status. Don't claim governance
   structures that are plans.
2. **Never demo an unbuilt feature.** The entire pitch stands on "we prove our
   spend" — and a faked demo of coverage kills it in the first org that looks.
3. **No price evolution outside the cost model.** Numbers to say screen; any
   price claim comes from the verified `cost-model.data.json` (re-verify at
   record time). Never quote a new price from memory.
4. **Don't argue "zero admin burden."** Sponsorship carries real compliance for
   them — we say it plainly and present ourselves as the lower-friction, not
   frictionless, partner.
5. **Don't lecture them on their own rhetoric.** They wrote the theory; assume
   their authority. Invite them to see irl.coop as *their* story made operable,
   not as a foreign project that noticed them.
6. **No version of "it's the donors who pay, not our sponsor."** The composer
   rail is real. Money lands in the Safe; the sponsor is a mapper.

## 7. Placement & reuse

Not an intro-series episode (no — *different audience, different job*). An
**institutional partner / funding pitch** that belongs alongside
`intro-video-series.md` and the cost model; the natural home is a `/stories`-type
surface the org reads, not a social serial. Reuses the cost charts (funder
side) and the value-flow/graphics.

Production order for assets this pass: (1) write the VO script verbatim
(humanized + Neu-TTS), (2) build the `sponsored-by` diagram + coverage-proof
clip, (3) assemble.

## 9. Sharper beat spine (2026-10-01, supersedes §5's table)

A later planning pass distilled the film to one mechanic + a set of
**concrete-sentence gems**. Supersedes the older §5 beat sheet: it is newer and
holds the sharp rule (below). Kept in one structural thread:

**The one mechanic every visual serves:** the dollar-as-particle travels a
**loop** — Fund → Organization → Community → back around → Fund. The platform
era punctures the circle (the leak); the coop stack seals it. Each beat is a
*state of the loop*, never a new graphic.

### Beat 0 — Title card (0–6s)
A luminous ring of coordinated dots (the community) orbiting a dim
"marketplace" to the right. Type: `irl.coop`. Kicker: **"the circulation
economy."** *Circulation, not circular — it moves, it lives.*

### Beat 1 — The promise (6–18s)
A gift enters the ring; it lights up in a wave; people turn to one another.
VO: *When you give to a movement, you're not buying a service. You're
investing in a circulation.*

### Beat 2 — The leak, generalized (18–40s) ★ gem-center
The ring tears; a linear drain runs off to a dim "for-profit map" that never
returns. **Generalizable to any vertical — food dropped as the lead.** The
claim is about moveable/holdable money and the rails to move it, stated as
three concrete, nameable things (all real, all any sector):

1. **Every transfer costs a fee** — payment processors take a cut of each
   donation and ticket. Literally *gas* on the move.
2. **Some moves aren't even possible** — a small org literally cannot route
   funds to a member today; the safe rail doesn't exist at its size. The move
   cannot be done at all.
3. **The fallback kills trust** — when there's no accountable rail, people
   coordinate funds on CashApp etc. That workaround removes the paper trail
   (no receipt, no transparency, no accountability), raises fraud, **and erodes
   the very trust the org's donations depend on.**

**The one true sentence (the gem):** *A small org can't route money safely,
so it routes it any way.* The sharpened claim: money moving costs, money
moving *through the handmade channel* costs transparency and trust, and a
lot of money moves that way *because* the proper rail doesn't exist at size.
Still screen the honest source footnotes (GiveDirectly / WFP) and the
"derived, sourced" label — the *claim* is general, the *figure* stays tied
to a named example.

### Beat 3 — Why small orgs can't escape (40–60s) ★ the sting
A small circle inside a huge fixed one; the same bill (rent, books, insurance,
software, connectors) drawn as a fixed wall around the small circle; the ring
tries to grow but the wall doesn't move. **The gem here is the single
concrete line:**
> **"Every volunteer who joins makes the tools cost more."**
That's the whole truth of the beat — a license per person you organize, a
record per donor you count, success billed against you. No metaphor needed.

**A second root connects to the same wall — *how the tools are held.***
Any third-party tool forces the group to pick a failure: hand the admin key to
every organizer and it's a **security sieve** — no one can be held accountable,
anyone can walk away with everything; hand it to one person and that person
becomes the whole group's **gate** — a de facto boss, and a single point the
movement freezes on if they leave or go quiet. Cooperation can't happen on a
password. It needs per-person, scoped, revocable access — so the group is never
governed by whoever happens to hold the key.

**What the group's infrastructure has to be, versus what it usually is.**
A movement's website, member list, money, and records are a *shared asset* —
so they need four things: **group-controlled** (the group decides, not an
individual), **permissioned** (everyone has their role, no one has all of it),
**durable past any member** (outlives whoever builds or pays for it), and
**owned by the group** (it belongs to the collective, not to a wallet). That's
what cooperation actually demands of its tools. But in practice it's usually
the exact inverse: **concentrated** in one person, who happens to be the one
who pays the card and holds the admin key. The website, the social accounts,
the event and donor tools — a single organizer both pays from a personal debit
card and administers with the admin key. That person leaves, goes quiet, or
their card lapses, and the movement goes dark — by no one's decision, but
because a shared asset lived inside one person's wallet and one person's
access. That's not cooperation; it's a dependency dressed as one. Power
follows the card and the key, not the group. Concentration isn't the
exception-we-live-with; it's the norm that cooperation has to undo.

**The gem (Beat 3, second):**
> **What the movement needs to hold, the group should hold — not one
> person's card, not one person's key.**

### Beat 4 — The cooperative stack (60–82s) ★ the second gem
The fixed wall shatters into a grid of small tiles (containers) that spread
across half-a-dozen little boxes — **not one machine**. Each tile holds a
service: identity, chat, member list, donor record, calendar, map. The wall
has become the floor. The leak-stream thins; a back-arc closes, money returns
to the ring.

**On the coop stack, the four demands of Beat 3 are met — one by one:**

| Beat 3 demanded… | The coop stack delivers… |
|---|---|
| group-controlled | the group's own Safe & seats decide — no individual has the deciding vote |
| permissioned | per-member roles, scoped + revocable — each does their part, nobody holds all of it |
| durable past any member | a containerized stack any member can stand up again — no one person is the hinge |
| owned by the group | the group pays once as a group; no personal card is the bill |

**The gem:**
> **Their profit scales with your size. Our cost doesn't.**

Self-hosted, owned once as a group: the 41st volunteer costs nothing to join,
not priced per person or per donation — and because the group holds the asset
itself, no one's departure (card or key) can end it.

### Beat 5 — A person becomes a voice (82–104s) ★ the emotional
The "person" dot that was served at the edge now moves inward among the
people — neighbor, not client. Label shifts **RECIPIENT → NEIGHBOR →
CO-AUTHOR.** The claim, concrete: *treated as files → treated as neighbors.*
Close credit line (small type): *A global network of locally governed,
regenerative, skill-sharing communities — framing from Nicole Hemingway.*
This is a designed property, not shipped — footnote it.

### Beat 6 — The ask / the fiscal rail (104–120s) ★ the close
The rail: **donor → sponsor (IRS donee, issues receipt) → irl.coop (sponsored
project) → the group's Safe.** 10% named plainly. `sponsored-by` = recognition,
**no control.** **The gem:** *Act as the lane the gift is made through — you
receive it for the coop the way you receive the mission.*

### Beat 7 — Outro (120s+)
`irl.coop — circulate.` A network of locally governed, regenerative,
skill-sharing communities. No product list — just the loop, still turning.

### The sharp rule (holds every word on screen)
A gem must (1) be true in isolation, (2) name a concretely purchasable, real
thing (a seat, a fee, a receipt, a record, a license), and (3) never be the
empty abstraction a SaaS would also print. If a line needs explanation to
hold weight, it doesn't land — cut it. **Deliberately removed** under this
rule: "keep vs. leak," "the floor is a wall," "the shared node," "crossing
the organization," any "62¢" headline.

---

## 9b. Corrected film spine (2026-10-02 — supersedes §9's "loop/dollar" framing)

The dollar was a symptom, not the star. The film's actual subject, corrected:

> **The vision** is a global network of locally-governed, regenerative, skill-sharing
> communities. **The tool** (irl.coop) helps make that network real by **adding an
> interconnection layer that was never possible before** — a shared, self-hosted,
> open-source app suite (identity · chat · mail · docs · projects · maps · events ·
> ERP · telephony) that the community **owns** and that lets the thousands of small
> autonomous communities actually interoperate, share, and federate.

Framing rules (hard won):
1. **Affirmative, additive, never subtractive.** irl.coop adds interconnection that
   didn't exist — it does *not* "remove blockers" or "tear down" anything. No
   feature-subtraction language anywhere in the film.
2. **Not "the three things."** Cost/scale, siloed-systems, privacy/shutdown are
   *three places irl.coop helps* — illustrative, explicitly non-exhaustive.
3. **Honour the competitive field.** Many apps solve parts of this. irl.coop's honest
   stance: those (Symphony, Macro, Kinetic-OS — best-in-class open-source suites) run
   on infrastructure **not owned by the community**, are **focused on an atomic unit**
   where organizations are kept separate, and it is *hard to team up*. irl.coop is
   open-source, community-owned, and **built so separate groups can interoperate.**
4. **Vision-first, one continuous scene.** Not seven title cards. The film is a single
   unfolding network — communities that begin scattered and separate, then connect as
   the shared layer settles under them. The dollar barely appears, if at all.

**The weighted ask (1–2 slides at the end), for the orgs already identified:**
- **Leadership / members.** Join the cooperative as members and help *steward* the
  verticals and how the platform itself runs.
- **Fiscal sponsors** — the accepted-on-behalf-of lane (10%, named).
- **Connectors** — people who can put the thing into the hands of groups that would
  use it.

**Grounding in the feature set** (so the film shows real things, per `intro-video-series.md`
§2): one login, every tool (V2); the open-source suite being comparable to best-in-class
(Symphony/Macro/Kinetic); self-hosted and community-owned; shared infra so the marginal
group costs near-nothing to add; export-and-leave autonomy; nothing on screen that is
designed-but-not-built passed off as shipped.

## 10. Decisions — resolved + open

**Resolved (2026-09-30):**
- **Scope — WHOLE solidarity sector**, not named recipients. Broad, invitational,
  statement-led: "an org like yours."
- **The "no operating entity yet" line — SHOWN on screen**, and paired with the
  resolution: a Wyoming nonprofit is being planned. Honesty read as forward
  motion, not a gap.
- Sponsor's role framed as a **temporary bridge** to that entity.
- **duna governance — RESOLVED:** nonprofit structured like the coop (draft
  bylaws + operating agreements exist); a rotating board **ratifies** on-chain
  governance from irl.coop members as a formality — it does not govern the
  coop, it stamps it. The honesty line the film can hold: *"the board never
  votes, the members did; the board ratifies."*

**Open for Robbie / the coop:**
1. **Single sponsor vs. a network of sponsors, per region/vertical?** The
   federation could need more than one. The ask's shape depends on it.
2. **Build the surface now?** The campaign surface + coverage endpoint are
   design; the pitch is *stronger with an established proof*. Either build a
   minimum version (campaign + one coverage, honest) before the film, or keep
   the pitch in the "how it's built to work" frame.
3. **VO voice:** Neu-TTS deck vs. humanized narration. For an institutional
   pitch start humanized; offer the Neu-TTS variant.
4. **Wyoming entity timing/content:** whether the formation is announced in the
   film as "planned," and whether the nonprofit's own governance should mirror
   the co-op's (e.g. worker self-direction) — worth deciding before any legal
   drafting.