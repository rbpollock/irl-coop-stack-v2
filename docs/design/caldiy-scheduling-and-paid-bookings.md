# cal.diy + paid bookings — how to add them

Status: plan · 2026-10-04 · Robbie + Hermes.
Reads with: `mautic-calcom-mcp-inference.md` §2 (the cal.diy choice, D-38) · `money-in-and-out.md`
(§3.7 the rail, §4 the platform is not in the money path, §5.2 no BYO, §10 the chargeback window) ·
`PAYMENTS-SETUP.md` (the preflight) · `coop-work-signup-checkoff.md` (a completed booking is the one
work source with a real duration) · the two proven app patterns this reuses — `hievents-gate-sso.md`
(public + gated path split) and `group-app-projection.md` (group → app tenant).

## 0. The ask, split three ways

"Add cal.diy" and "paid bookings" are three separable pieces with very different costs:

| | Piece | Cost | Blocked by |
|---|---|---|---|
| **A** | **Deploy cal.diy** — the scheduling surface | one app + a database + an edge route | nothing |
| **B** | **Identity** — how a member or a group signs in | a source patch, or a gate | a decision (§3) |
| **C** | **Paid bookings** — money lands in a group treasury | the whole payments path | **the payments preflight — not cal.diy** |

And the finding that should shape the whole thing:

> **Paid bookings are not a cal.diy feature to switch on.** They are the stack's missing
> "an outsider pays a group" seam — the same seam paid event tickets need, and the same one
> marketplace sales will need. Build it once, or three times badly.

## 1. What cal.diy actually is (verified from the fork, 2026-10-04)

Checked against the repository itself, not its marketing:

| Fact | How verified |
|---|---|
| MIT, all enterprise code removed, **no hosted version** (self-host only) | README |
| **Removed: Teams, Organizations, Workflows, Insights, SSO/SAML** | `packages/features` has no `team`/`org`/`workflow`/`insight`/`sso`/`oidc`/`saml` directory |
| **Retained: `webhooks`** | `packages/features/webhooks` exists |
| **Retained: API v2** | `docs/api-reference/v2` exists |
| Payment apps retained: stripe, paypal, **btcpayserver**, hitpay, mock | `packages/app-store` |
| Retained: `credits` | `packages/features/credits` |
| Stack: Next.js + tRPC + Prisma; Node ≥18, Postgres ≥13, Yarn; Dockerfile + compose + `deploy/` in-repo; migrations via `prisma db-deploy` | README |

Its own README says *"strictly recommended for personal, non-production use"* and *"for any commercial
and enterprise-ready scheduling infrastructure, use Cal.com, not Cal.diy."* **We should accept that
knowingly or re-open the choice — decision 6.**

Three consequences:

1. **No SSO.** Identity is ours to add, or not at all (§3).
2. **No teams or organizations.** The app's unit is ONE user: no team booking page, no round-robin
   across members. A "group's booking page" must be built as one of three shapes (§2).
3. **Webhooks and the API survived** — the whole integration hinge. We can receive
   `BOOKING_CREATED` / `BOOKING_COMPLETED` and confirm a booking from coop-api. **No fork is needed
   for the event leg.**

## 2. Who books (decision 1)

| Option | Shape | Cost | Honest ceiling |
|---|---|---|---|
| **A — one coop-level page** | `book.irl.coop`, the coop's own account, a handful of event types. **The public page needs no login at all** | cheapest: **no identity work, no payment, no fork** | one page; no per-group separation |
| **B — one page per group** | group ↦ a cal.diy user, synced outside the app (the `group-app-projection` pattern: deterministic link, Temporal sweep, unseat = disable) | needs an identity answer for who administers it | cal.diy has no teams, so the "group" is a single account that members share |
| **C — per-member calendars, the group page as a projection** | each member owns their own cal.diy account; the group's page is a *projection* in our dashboard listing the group's members' slots, and bookings are created through coop-api | most work; coop-api would hold per-member API keys | the faithful shape for Cal.com's model, and closest to "projection, never a store of record" |

**Recommendation: A first.** It proves the deploy, the edge route, the public booking flow and the
webhook leg — with no money and no identity patch. B when a group actually asks for its own page; C
only if member-level calendars are genuinely wanted.

**And note what a scheduler must never own.** Scoped availability — the member's time budgets and the
per-audience disclosure of them — lives in coop-api, not in the scheduling app
(`scoped-availability.md`), because a booking link reveals free/busy to anyone holding it and the fork
has no scope concept. That is a further argument for C whenever member-level availability is wanted: the
group's page is then a projection over figures the coop already owns.

### 2.1 Group-awareness and permissioning: **not retrofitted** (answered 2026-10-04)

The question was whether to make cal.diy *itself* group-aware and permissioned. **No**, for two reasons:

1. **The features that would do it were deliberately stripped.** Group-awareness in Cal.com means
   *Teams* (member lists, roles, round-robin); permissioning means team roles. Both are EE, both were
   removed in the fork. Retrofitting them means re-implementing code upstream deleted, on a fork whose
   own README says *"strictly recommended for personal, non-production use"*, and re-applying the patch
   on every upstream bump. High cost, high drift, maintenance for a feature the project rejects.
2. **It is now the wrong owner.** The coop owns scopes, disclosure and permissioning
   (`scoped-availability.md`): a group's page is a projection over coop data, and who sees what is
   decided by RLS and definer projections. Teaching the app about groups would duplicate that in a
   second, weaker place — exactly the mistake §5.2 names for money.

**What cal.diy is for instead — the calendar engine, headless.** Keep the parts that are genuinely hard
and already written: **busy-time computation across connected calendars** (Google / CalDAV / iCal), ICS,
conferencing links, reschedule/cancel. Drop the parts we replace: its booking **pages**, its session
model, and its notion of who may see what.

Two shapes follow, and both avoid a fork:

| Shape | What it is | When |
|---|---|---|
| **Headless** | coop-api drives it over API v2 and receives its webhooks; the app is **internal-only** — no proxy route, no OIDC client, no nav entry, exactly like the rail app (`peer_xyz_payments`) | the target shape once scoped availability ships |
| **One page, single purpose** | one coop-level booking page; no tenancy, no permission model | the cheap slice 1, unchanged |

**And give the seam a name.** Under `provider-seams.md` the scheduler becomes a **seam**: coop-api holds
a scheduler URL + id and **no vendor noun**, so the engine is replaceable by configuration and a cutover
is a policy edit. That also makes it a candidate for the first **seam drill** that document says has
never been run.

**One unknown this creates, flagged rather than assumed:** driving bookings *per member* requires knowing
how the v2 API authenticates on a member's behalf — an **API key per user** (a credential store per
member) versus **an OAuth client the member grants once**. That decides whether members' own calendars
can be served by a shared engine, and it must be verified before the headless shape is adopted.

## 3. Identity (decision 2)

Google login inside cal.diy would break the fleet rule (**Google is brokered via Keycloak, never a
direct provider**), so:

| Route | What it is | Cost | Keeps |
|---|---|---|---|
| **1. Patch OIDC into its NextAuth** | a Keycloak provider added to cal.diy's auth config + a Keycloak client for it | a **source fork** of a heavy monorepo, re-applied on every upstream bump | real SSO, one login |
| **2. Gate-SSO** (the Hi.Events / NocoDB shape) | public pages direct; `/settings` behind an oauth2-proxy gate that forwards `x-forwarded-email`; a small patch mints the app session from that header | one distinct patch + a gate sidecar (unique `--cookie-name`) | identity stays in ONE place; proven twice already in this stack |
| **3. None** | one local admin account per page, credential shared with the group | cheapest | nothing — a shared password is what §5.2 exists to prevent |

**Recommendation: none for slice 1** (the public page needs no auth). Decide 1 vs 2 when the first
group wants its own page — route 1 buys real SSO; route 2 keeps identity where the rest of the fleet
keeps it.

**If the app goes headless (§2.1), this decision collapses.** There are no member-facing pages to sign
into, so the only credential that matters is the engine's own — a service credential held the way the
rail token is held, not an identity route.

## 4. Paid bookings — the honest shape

**The finding:** a paid booking, a paid event ticket and a paid marketplace order are the same missing
thing — *an outsider pays money that must land in a group's treasury, provably, without the platform
touching it.*

**Where that path actually stands:**

| Piece | State |
|---|---|
| The contract (`payment_intent`, statuses, idempotency) + policy in coop-api | **built** |
| The rail app (`peer_xyz_payments`, own process, neutral contract) | **built, sandbox-verified** |
| The webhook receiver (HMAC, 300s window, idempotent by event id) | **built, verified 14/14** |
| The preflight (6 gates; `ready` only when all pass) | **built** |
| **A route that creates a payment** | **does not exist** |
| **Any money ever moved** | **no — 4 `payment_intent` rows, all `failed`; 23 `rail_event` rows** |
| The router deployed anywhere | **no — the local chain was restarted; `eth_getCode` returns `0x`** |
| Something that sweeps deposits | **no production caller exists** |
| A live merchant account | **no (sandbox only)** |

So: **paid bookings are blocked behind `PAYMENTS-SETUP.md`'s nine steps, not behind cal.diy.** Time
spent on the booking side of paid bookings before that path is green buys nothing.

**And the decisive rule — do not switch on cal.diy's Stripe or PayPal app.** `money-in-and-out.md`
§5.2: a payment account has one owner, so there is no 2-of-3, no seat protection and no threshold; the
money sits outside the Safe, outside all three guards and off the group's books; and the T+130
chargeback window lands on an individual. That is a governance regression — the same one that must not
"fix" the empty `STRIPE_SECRET_KEY` in `hievents.yaml`.

**The design that avoids a fork entirely** (cal.diy stays a dumb scheduler; the money is ours):

1. The event type is created with **requires confirmation** → a booking lands **pending**.
2. cal.diy's **`BOOKING_CREATED` webhook** → coop-api (bearer + **group target baked into the URL**,
   the Hi.Events receiver shape).
3. coop-api creates a **`payment_intent`** (amount from the price we set on the event type) → rail →
   checkout URL → the payer gets **our** pay page (Cal.com's redirect-on-booking, or our own link).
4. The **rail's** webhook (HMAC, two checks) marks the intent settled/partial → coop-api **confirms
   the booking through cal.diy's API v2**.
5. Reversals (`PAYMENT_CHARGEBACKED`, `REFUND_*`) revise the payment state. The calendar was already
   kept — that is §10's T+130 window arriving as data, and why a receipt means *"funds arrived"*,
   never *"funds are final"*.

**Destination (the §3.7 invariant, now with a second consumer).** The destination is read from the
**group's Safe, server-side — never from a request, never left to the merchant default.** The recorded
fork sharpens here: a *per-group* destination attributes naturally but tells the provider and the P2P
counterparty which group paid; a *shared* coop destination pools and keeps attribution off-chain.
Decide it once — bookings and tickets both inherit it.

**Cost honesty.** The Peer rail's markup is up to **20%, borne by the payer** — on a $40 booking, up to
$8. That is the price of untraced, non-KYC settlement. Direct on-chain USDC stays the cheap path, and
the fork **retains a BTCPayServer app** (self-hostable, no proprietary dependency) — a real candidate
for a **second rail adapter** under `provider-seams.md`, and for the first seam *drill* that document
says has never been run.

## 5. The second leg — a booking is work (Tier 2)

A *completed* booking is the one work source that carries a **real duration**
(`coop-work-signup-checkoff.md`), so the long-run shape is `BOOKING_COMPLETED` → `contribution.logged`
→ the Tier-2 ledger → badges.

But the ledger's write path **does not exist yet** — `appendTier2Entry` is callable only from a script —
and that doc's order is explicit: **① the entry route + check-off → ② ONE source as a proposer → ③ the
rest.** cal.diy waits behind ①. Building the booking→ledger leg first would multiply producers of a
record whose shape has never been exercised end to end.

Bus hygiene when it comes: one webhook per event type with the **group target baked in** (the Hi.Events
`CoopEventBusWebhookProvisioner` shape), and compose the dedupe id **with the target** — the bus
dedupes on `(source, source_event_id)` globally, so two groups' bookings can collide.

## 6. The coop's fee on bookings (decision 5)

The recorded intent is that a paid booking is *"one of the fee levers the coop could take a percentage
on … percentages decided by members."* Two things are already settled and constrain it:

- **The platform never intermediates** (§4 of the money doc) — so the fee cannot be a skim on the way
  through. It must be a **group → coop transfer the group's own governance authorizes**.
- If percentage splits are wanted later, the proven contract is **0xSplits**, not a hand-rolled splitter.

The percentage itself is a governance decision, and **no price gets published before the coop sets one**.

## 7. Staged path

| # | Slice | Depends on | Reversible |
|---|---|---|---|
| **1** | **Deploy cal.diy** — app + `caldiy` database + edge route + **one coop-level booking page**. No money, no identity patch. Prove: the public page renders through the edge, a test booking creates a row, a webhook reaches our bus | a free host port; derived secrets; the runtime-URL answer (§8) | yes — remove the app; nothing else touched |
| **2** | **The booking → bus leg** — a receiver route + a per-event webhook provisioner | slice 1 | yes |
| **3** | **Identity** — the chosen route, patched and verified | a group that wants its own page (decision 1 → B) | yes |
| **4** | **Paid bookings** — the paid flow on top of a **live** rail | the whole payments preflight; the destination decision; risk bounds, an amount cap, a named accountable person, a backup | **no — not reversible once real** |

Slice 1 is genuinely cheap, and that is the point: it proves the integration hinge (webhooks + API)
before anyone spends on identity or money.

## 8. Verify before each slice (honest unknowns)

| Unknown | Why it matters | How to check |
|---|---|---|
| Published image name/tag; can `NEXT_PUBLIC_WEBAPP_URL`/`NEXTAUTH_URL` be set at **runtime**? | Cal.com self-hosting historically bakes the URL at **build** time | pull the fork's image and read its entrypoint; else build a derived image with the URL as a build arg |
| Is **requires confirmation** retained? | it is the hinge of the paid-booking design | the event-type schema + a live create |
| The **API v2 endpoint** that confirms a booking, and its auth | step 4 of §4 | the in-repo v2 reference, then a call against slice 1 |
| cal.diy's **webhook signature scheme** | never trust a receiver we have not verified — *"the docs are the contract, not the types"* cost a cycle in the Peer arc | read the docs, then assert a real signature |
| Does the fork's main branch build and run? | 16.5k commits, last commit ~2 weeks old — active, but young | build it in slice 1 |
| A **free port** | the Hi.Events lesson: 8091 looked free and onlyoffice held it | `ss -ltnp` before assigning |

## 9. Decisions needed (Robbie)

1. **Who books** — one coop-level page / one per group / per member (§2).
2. **Identity route** — patch OIDC / gate-SSO / none (§3) — **collapses to a service credential if the
   app goes headless (§2.1)**.
3. **Paid bookings** — accept "cal.diy stays dumb, the money is ours" (no Stripe/PayPal app)? (§4)
4. **Destination** — per-group router, or one shared coop destination? (§4)
5. **Fee on bookings** — whether the coop takes a percentage, and who decides (§6).
6. **The fork's warning** — accept "personal, non-production use" knowingly, or re-open the
   scheduler choice? (§1)

**Answered 2026-10-04:**

- **Retrofit cal.diy to be group-aware and permissioned? — No.** Keep the calendar engine headless behind
  coop-api and drop its pages, its session model and its permission model (§2.1). Two reasons: the
  features that would implement it (Teams, team roles) are EE and were *deliberately removed* from the
  fork, so the retrofit is re-implementing deleted code and re-applying it on every upstream bump; and
  it is now the wrong owner — the coop owns scopes, disclosure and permissioning
  (`scoped-availability.md`), and a second weaker copy of that in an app is the §5.2 mistake.
- **Except for slice 1**, which stands unchanged: one single-purpose coop-level page, no tenancy, no
  permission model, no retrofit.

## 10. Do not

- **Do not enable cal.diy's Stripe/PayPal payment apps for group money** — §5.2, and the same reason
  `hievents.yaml`'s keys stay empty.
- **Do not let a paid booking land in a member's account, or the platform's.** Group treasury or nothing.
- **Do not build the booking→ledger leg before the Tier-2 entry route exists.**
- **Do not fork for the event leg** — webhooks + API v2 already carry it.
- **Do not publish a fee or a price before the coop decides one.**
- **Do not treat a sandbox order as proof** — the first real payment *is* preflight gate 5.

## Cross-references

- `mautic-calcom-mcp-inference.md` §2 — the cal.diy choice (D-38) and the Mautic/MCP siblings.
- `money-in-and-out.md` §3.7 (the rail, verified), §4 (the platform is not in the money path),
  §5.2 (no BYO), §10 (the T+130 window).
- `PAYMENTS-SETUP.md` — the nine steps and the six gates.
- `coop-work-signup-checkoff.md` — a completed booking is the duration source; the
  source / ledger / counter-signature rules.
- `provider-seams.md` — the second rail, and the drill nobody has run.
- Skill refs `hievents-gate-sso.md` + `group-app-projection.md` — the two proven app patterns.
- `docs/DECISIONS.md` D-32, D-38.