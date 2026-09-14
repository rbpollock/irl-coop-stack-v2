# Money in and money out

Status: gap map · 2026-09-13 · Robbie + Hermes.
Source of truth for the design: **`private-treasury-guards-ledgers.md`** (the consolidated spec).
This document is the *connectivity* map: what flows, who holds it at each step, what exists, and what
blocks what.

## 0. The finding

**Money is the only pillar with a complete, unusually rigorous design and essentially zero
implementation — and the first thing it needs is a decision, not code.**

`private-treasury-guards-ledgers.md` already specifies: shielded notes/commitments/nullifiers, one
treasury per Safe, project accounts as sub-scopes, three enforcement points, the three ledger tiers,
compliance by viewing key and selective disclosure, a v0/v1/v2 phasing, and a settlement model for
the 130-day chargeback window (§10). It is more complete than most shipped fintech.

**And a founding group today cannot receive or spend a single dollar.** Evidence:

| Evidence | What it means |
|---|---|
| `hievents.yaml:89-96` → `# Stripe — unset (payments off)`, all four keys `""` | Ticketing is **live** but **cannot take payment**. The group's most immediate in-flow is wired to nothing, and the config says so itself |
| `apps/coop-api/src/provisioning.ts:32` → `{ alias: "irl-coop-treasury" }` | "Treasury" exists as a **provisioned resource** (a channel/app), not as a thing that holds funds |
| `hievents.yaml:95-96` → `APP_SAAS_STRIPE_APPLICATION_FEE_PERCENT: "0"`, `..._FIXED: "0"` | **The $0.00 platform fee is CONFIGURED, not merely claimed** — the one money property already true in code |
| `cost-model.data.json` → `revenue.member_monthly` `illustrative: true` | No price has been set. The coop's own income is a governance decision not yet made |
| No treasury contract; §9.2 open | **"Chain choice … This decision blocks the treasury contract and must be made first."** |

**The headline: the blocker is §9.2 — the chain decision — and it is Robbie's call.** Everything
downstream waits on it.

## 1. Money IN

| # | In-flow | Held by | Tier | Status | Blocker |
|---|---|---|---|---|---|
| 1 | **Membership dues** (sliding scale, pay-what-you-can) | coop Safe | T1 | **designed** | no price set (governance); no payment rail |
| 2 | **Group infrastructure contribution** (per group/mo) | coop Safe | T1 | **designed** — modelled at $25/group, 13 groups covers infra + stewardship | rail; and the price is a governance decision |
| 3 | **Event tickets** | group Safe | T1 | **live app, NO PAYMENT** | **`STRIPE_SECRET_KEY` is empty** — the cheapest real fix in this document |
| 4 | Product / marketplace sales (Webstudio store) | group Safe | T1 | app live, payments unset | same rail |
| 5 | **Donations** (one-off, recurring) | fund / coop Safe | T1 | designed | rail; and the 130-day reversal model (§10) |
| 6 | **Grants** | coop / project Safe | T1 | designed (project accounts) | rail; reporting |
| 7 | **Sponsorship bridge** — fiat → group liquidity, per-vertical fund absorbs the reversal window | **vertical fund** (a `subgroup-of` irl.coop with its own Safe) | T1 in, T2-pending on the fiat side | designed (§10) | **needs the fund capitalized** — "donors to irl.coop + coop-member governance decisions" |
| 8 | Inter-group allocation (parent → child group) | child Safe | T1 | designed | treasury contract |
| 9 | **Volunteer hours / labor swaps** | *not money* — Tier-2 credits | T2 | designed | not a money flow; do not conflate (§4) |

## 2. Money OUT

| # | Out-flow | Paid from | Tier | Status | Blocker |
|---|---|---|---|---|---|
| 1 | **Infrastructure** (hosting, DNS, hardware amortization, DIDs) — $73 + $4.50/mo in the model | coop Safe | T1 | **paid today out-of-pocket by Robbie** | the coop has no funds and no rail |
| 2 | **Stewardship labour** ($45/hr × 8 hrs = **$360/mo**) | coop Safe | T1 | **unpaid — subsidised by a volunteer** · **paid roles (`tier2-entry-model.md` §5.2) are the mechanism that makes this payable** | this is the failure mode the platform exists to fix; named in `cost-model.md` |
| 3 | **Distributions / splits** per entitlement table, monthly via the keeper | group distribution fund | T1 | designed (v1 in-circuit) | treasury contract; and a **group must set a split policy** |
| 4 | Worker / volunteer compensation (strike pay, honoraria) | distribution or reserve fund | T1 | designed | treasury contract |
| 5 | Vendor payments (suppliers, carriers, certifiers) | group operating fund | T1 | designed (2-of-3 + per-ledger limits) | treasury contract |
| 6 | **Mutual-aid disbursement** (funds reach aid) | group fund | T1 | designed — and the *coverage proof* is what makes it provable without publishing amounts | proofs |
| 7 | **Refunds** (tickets) | group escrow → group | T2 pending → T1 | designed (§10) | the 130-day model exists precisely because of this |
| 8 | Processing + settlement fees | — | — | designed (terms on the `sponsored-by` edge) | — |
| 9 | Reserves / sink funds (strike fund: 3-of-5 + timelock + circuit-breaker) | group reserve | T1 | designed | treasury contract |
| 10 | Taxes / statutory bookkeeping | operating entity | — | **flagged as unresolved** (§7 legal note) | legal design per jurisdiction |
| 11 | Settlement repayment + fee to the vertical fund (T+130) | fund | T1 | designed | fund capitalization |
| 12 | **Chain transaction costs (gas)** — deposits, withdrawals, transfers, **Tier-2 anchor writes**, timelock upkeep, monthly distribution runs | group / coop | — | **NOT MODELLED** | Base mainnet makes this real; the cost model carries no chain cost at all. **Scales with distribution frequency × groups × members**, so it is the one out-flow that grows with the commons economy working as designed |
| 13 | **Role stipends / paid roles** (market manager, treasurer, node operator) — the general case of row 2 | group / coop Safe | T1 | **designed** (`tier2-entry-model.md` §5.2) | the entitlement path exists and needs no new mechanism; **but it converts a fairness ledger into a payroll ledger** (independent counter-signers, a value threshold, aggregate visibility) **and creates filing/tax duties** that no ledger removes |

## 3. The custody structure (settled — build against this)

- **One treasury per Safe.** Person = 1-of-1; group = N-of-M. Nothing is public unless disclosed.
- **The chain stores no balances — only commitments.** Value is in notes
  `commit(amount, owner_key, project_scope, rng)`; spending reveals a nullifier, so double-spend is
  structurally impossible.
- **Three ledger tiers:** T1 money (shielded, on-chain) · T2 participation (off-chain, hash-chained,
  anchored) · T3 badges. **Money is never public, always provable.**
- **Project accounts are sub-scopes, not entities** — same treasury, own keys, own rules, own reports.
  They are *promoted to a child group* only when governance differs.
- **Viewing keys**: a master key for the custodian set; **project viewing keys** open only that
  project's notes. Compliance = a scope-limited report, never the whole book.
- **The only visible crossings are deposits and withdrawals** (§1.9) — inside is shielded.

## 3.1 What the Tier-2 contribution ledger actually IS (plain language)

Added 2026-09-13 because this term got used without being explained. **Tier 2 is the group's record book
for everything that isn't money.** The three tiers exist because three kinds of value need three
different guarantees:

| Tier | What it holds | The guarantee it needs | Why that mechanism |
|---|---|---|---|
| **1** | **Money** | hidden from the world, **provable on demand** | on-chain ZK — the only way to be both at once |
| **2** | **Favors, hours, in-kind contributions** | visible to the group, **impossible to quietly edit** | off-chain storage + hash chain + periodic anchors |
| **3** | **Claims about yourself** | provable **without showing the records** | proofs over Tier 2 |

### What actually goes in it

For a food co-op, concretely:

- Tana worked six hours at the market stand → one entry.
- Devon swapped three hours of childcare for three hours of tractor work → two entries that net.
- Sam has the nail gun, due back Friday → one reservation entry. **No money changes hands** — the
  reservation ledger *is* the economy here.
- Alice paid March dues → **the $25 is Tier 1, and "Alice is current on dues" is neither tier — it is a
  *projection* over T1 + T2 + her role, revealed as a proof that hides which mode satisfied it**
  (`tier2-entry-model.md` §5.1). Corrected 2026-09-13: this example previously called dues status a T2
  entry, which was wrong for the reason §5.1 gives.
- The group splits 60/40 by hours worked → the **entitlement table** is Tier 2.
- "We covered 80% of our infrastructure this year" → a **proof over** Tier 2 records.

**In one line:** Tier 1 is money (hidden but provable). Tier 2 is favors and hours (visible to the
group, impossible to quietly edit). Tier 3 is claims about yourself (provable without the records).

### Why a hash chain and not just database rows

Each entry carries a fingerprint of the previous one. **Change an old entry and every later fingerprint
breaks — so tampering becomes *detectable*.** And because the chain's head is periodically
**anchored on-chain** (a Merkle root to Base), even the person who operates the database cannot
rewrite history without that being visible. Cheap storage (Postgres), cryptographic integrity (the
chain), cheap proof (the anchors).

**Why not on-chain:** every logged hour would cost gas *and be public*. Absurd for "I watched the kids
Tuesday" — and public is the opposite of what a threatened group needs.

### Why it has to exist before the money features

**Everything money-related *reads from it.***

- "Auto-split per the entitlement table" is impossible unless the table itself is trustworthy.
- "Funds reached aid" cannot be proven without a trustworthy record of what was contributed and
  disbursed.
- Dues status — who is current, who is behind — is a Tier 2 record, not a Tier 1 entry.
- The **coverage proof** ("we covered ≥X% of the platform cost") is a proof *over* Tier 2.

**So Tier 2 is the substrate the money layer stands on.** That is why it is step 1: it needs no chain
contract, and it is what makes every later money claim provable rather than asserted.

### It is also already promised to users — and that promise has zero code

The landing page FAQ says:

> *"What if we mostly trade favors — childcare turns, harvests, lessons — not cash?"*
> → *"The platform tracks that too. Hours and contributions are recorded, so 'everyone gets a turn'
> stays fair even when no money changes hands."*

That answer **is** Tier 2, and in user terms. `group-model.html` puts it the same way:

> *"**Tier-2 labor credit** — the in-kind economy (childcare turns, harvest-paid-in-food, teaching
> hours) is off-chain hash-chained, so 'everyone gets a turn' is auditable without forcing money into a
> non-monetary exchange."*

**Status: designed, and not implemented.** Searching `apps/coop-api/src` for
`participation|hash_chain|prev_hash|merkle|anchor|idempotency` returns **zero matches** — no
participation ledger, no hash chain, no anchors. It is a `designed` claim in `claims.data.json` terms:
keep the promise on the site, publish the stage, and build it as step 1.

## 3.2 Who may counter-sign a Tier-2 entry

**DECIDED 2026-09-13 (Robbie): three classes may counter-sign — automated (scoped key) processes, group
votes, and role-based authorized individuals.**

### The unification

**These are not three mechanisms. They are one:** a signature from an authority the group has already
granted.

> A counter-signature is valid if it comes from an authority the group conferred — a **seat holding a
> role**, a **scoped session key**, or the **group acting by quorum**. All three are the same object (a
> signature over an entry), distinguished only by how the authority was granted and how it is revoked.

That means **one counter-signing layer, three authority types** — and the same layer serves the
**custody chain** (`custody-chain-and-contest-kit.md`), which has the identical shape for goods. Build
it once.

| Class | What it can honestly attest | Strength | How the authority is scoped | How it is revoked |
|---|---|---|---|---|
| **Role holder** | *"I saw this happen."* A witness claim | human honesty, bounded by their role | the role's grant matrix (a market manager signs market hours, not treasury ops) | remove the role |
| **Scoped key** | *"The system observed this."* A QR scan, a scale reading, a payment webhook, a task completion | strong **if** the source isn't spoofable — otherwise it is a machine repeating what it was told | the ERC-7715 permission grant: bounded actions, caps, recipient allowlists, expiry (`delegation-and-session-keys.md`) | instant, and it expires on its own |
| **Group vote** | *"We accept this."* Ratification | the group's own authority — **the authority of last resort** | the decision's quorum, options and payload | a later decision, never an erasure |

**Use the cheapest one that can honestly attest.** A market-stand QR scan for six hours needs a scoped
key. A disputed "I was there all day" needs a role holder. A batch nobody witnessed needs a vote. **A
vote is the most expensive and should be the rarest** — reaching for it routinely turns governance into
bookkeeping.

### Derived requirements (consequences of the decision, flagged as such)

**1. Validity is judged at signature time.** Revoking a role or a key must **not** invalidate entries
that authority already signed — they *did* have the authority then. So every entry references the
**authority** (role grant id, key id) and the authority carries a validity window. Without this, either
a compromised key can never be cut off without destroying records, or leaving a role silently rewrites
the group's history.

**2. The counter-signer must not be the beneficiary.** The separation-of-interest rule, and it is the
same instinct as the treasury's investigator exclusion (*too close → auto-excluded*) and the recusal
primitive in `adversary-models-and-sector-fit.md` §1.1. **If I can log my own hours unopposed, the
ledger records assertions, not facts.** This is exactly why a **mutual-aid delivery is receipted by the
recipient**, not the provider.

**3. Counter-signing is thresholded per entry class**, mirroring the treasury's per-ledger limits
(`private-treasury-guards-ledgers.md` §3): small and routine → one signature. Large, or
money-affecting, or contested → N-of-M. The rule language is the same; only the target differs.

**4. An entry with no counter-signature still exists — marked.** And a **refusal is a signal**: someone
declined to attest. Both are visible, neither is silently absent or deletable
(`custody-chain-and-contest-kit.md` §7.3, whose open question this partially resolves).

### The part that matters most: a key that signs hours is a MONEY permission

**Tier 2 feeds Tier 1.** Hours and contributions become entitlement tables, and entitlement tables drive
**Tier-1 distributions**. So the ability to counter-sign a Tier-2 entry is **economically meaningful** —
**a scoped key that can sign hours is, indirectly, a money-minter.**

Therefore a T2 counter-signing key must be treated with the same care as a key that moves funds:

- **Capped per entry class** — a market-stand key signs ≤ 8 h/day and ≤ N entries/day, not 400 hours.
- **Expiring** — a season, not indefinitely.
- **Rate- and volume-limited**, with anomalies surfaced rather than silently accepted.
- **Distinguishable at distribution time**: a distribution run should read **ratified** entries only,
  and treat a bare machine-signed entry as *provisional* until a human or a vote accepts it.
- **Blast-radius bounded on theft**: the damage from a stolen stand key should be one day's hours at one
  stand, not the group's whole history of labor credit.

**This is the strongest argument against treating T2 as "just a database table".** The moment it feeds
money, its write path is a financial surface.

### Why this order still holds

None of this needs the chain contract or the shielded treasury. It needs the **authority/grant layer**
that already exists in design (seats, roles, grants, session keys, decisions) plus an **append-only,
counter-signed, hash-chained ledger**. So Tier 2 remains step 1 — and it is now specifiable, because the
counter-signing question is answered.

## 3.3 Should Tier 2 live on a zk chain? — **NO** (and the reason is why the tiers exist)

**Asked by Robbie 2026-09-13. Answer: no.** Tier 2 stays **off-chain, hash-chained, counter-signed, and
periodically anchored to Base.** The load-bearing reason in one line:

> **You do not need the data on-chain to prove things about it — you need its *commitment* on-chain.**

### The five reasons

**1. Proving requires a commitment, not a copy.** Everything anyone wants to prove about Tier 2 —
*"she contributed ≥100 hours"*, *"everyone got a turn"*, *"we covered ≥80% of our infrastructure"* — is a
ZK proof **over off-chain data** whose Merkle root is anchored on Base. The verifier checks the proof
against the anchored root and never needs the entries. That is the same commit-now / prove-later pattern
as selective disclosure (`federation-encryption-and-access.md`), and it gets T2 **ZK-grade provability at
anchor cost rather than per-entry cost.**

**2. The volume is two orders of magnitude apart, and so is the price.**

| | Count (illustrative assumptions stated below) |
|---|---|
| Tier-2 entries | **~120/day/group → ~569,000/year** across 13 groups |
| Counter-signatures, if each were a transaction | up to **~1.14M/year** |
| Tier-2 anchors (one root/group/day) | **13/day → ~4,745/year** |
| **Ratio** | **~120:1 fewer on-chain writes** on the anchor path |

*Assumptions: 40 members × 3 entries/day (a shift, a swap, a tool checkout); 13 groups; daily anchors.*
**No gas price is asserted** — the point is the ratio, and it holds for any price. T1 writes are
*gate-shaped* (a distribution, a deposit, a withdrawal); T2 writes are *frequent and trivial*.

**3. Your own counter-signing decision is an argument for off-chain.** §3.2 made counter-signatures
central, and it wants them **cheap and plentiful** — a scan at the market stand, a witness signature, a
batch ratification. A signature is just a signature off-chain; on-chain, **every one is a transaction**
(see the 1.14M/year row above). The design you just chose is only workable off-chain.

**4. Consensus buys T2 nothing it needs.** Tier 1 needs consensus because **value must not be
double-spent by anyone, including the operator** — that is what nullifiers plus chain state provide.
Tier 2 has no equivalent risk: a doubly-logged hour is a **data error corrected by a counter-signature**,
not a theft. What T2 needs is **tamper-detection**, i.e. "history cannot be silently rewritten" — and a
hash chain plus a published root delivers exactly that at a fraction of the cost. **Using one substrate
for both would erase the distinction the tiers were drawn to make.**

**5. Metadata leaks even when contents are hidden.** A shielded entry still puts a **timestamp and a
nullifier** on a transparent chain. A group's *labor activity pattern* — how many entries, how often,
when — is a footprint signal, and for the groups in `adversary-models-and-sector-fit.md` "this co-op
logged 400 entries last week" is precisely the wrong thing to publish. **An anchor leaks a root; n
entries leak a rhythm.**

Plus two practical ones: T2 is **relational and constantly queried** (joined against members, roles,
entitlements, events), so on-chain-first would mean an indexer **and** a Postgres copy — two sources of
truth and a sync problem, where off-chain-first makes the queryable copy *the* system of record. And
**corrections and personal data** are far simpler off-chain: hours-per-person *is* personal data, and
append-only-on-chain makes erasure and correction permanently public.

### What *does* go on-chain — the rule

| Thing | Where | Why |
|---|---|---|
| **A Tier-2 entry** (hours, swaps, checkouts) | **off-chain**, hash-chained, counter-signed | cheap, queryable, correctable; integrity comes from the chain + anchors |
| **The period's Merkle root** | **on Base** (anchored) | this is what makes rewriting history detectable |
| **A Tier-2 proof** (*"covered ≥X%"*, a badge) | verified **on Base** against the anchored root | ZK over off-chain data — commitment, not copy |
| **A ratified distribution or any value movement** | **on Base** — it is Tier 1 by definition | value must not be double-spendable; that is what consensus is for |
| **A governance act** (a vote) | already attested on-chain (`decisions.ts` + EIP-1271) | it *is* the authority, and it authorizes value |

**The clean rule:** *the decision goes on-chain; the thousand hours that led to it do not.* Put another
way — **on-chain is for what must not be forgeable by the operator; off-chain is for what must be
provable.** Tier 2 is the second kind until the moment it becomes value, and that moment is a Tier-1
event.

### Note on "zk chain" for Tier 1 too

Even Tier 1 is **not** a "zk chain" in the purpose-built sense: `private-treasury-guards-ledgers.md` §9.2
chose **Base mainnet with an on-chain verifier** — shielded *state* (commitments, nullifiers) with proofs
verified on a transparent chain. A purpose-built shielded chain was the rejected alternative. So putting
Tier 2 on a zk chain would introduce a **third** mechanism for the **lowest-value** data — inconsistent as
well as more complex.

## 3.4 Where the entries physically live (sharding across nodes)

**Answered in `sharded-ledgers-and-anchors.md`.** Short version: **shard by `group_id`** — each group's
ledger is its own append-only chain — and commit **per-group period roots** into one **federation root**
anchored to Base once per period. Storage shards trivially; **write ordering does not shard at all**, so
the design keeps per-group order plus period batching instead of one global sequence. Cross-group entries
are **two mutually-referencing entries**, one per shard. And the anchor is what makes it safe to put a
ledger on someone else's hardware: a host can drop or withhold, but it cannot alter.

## 3.5 The entry model — specified

**`tier2-entry-model.md`** is the buildable spec: the two tables (`tier2_entry`, `tier2_signature`), the
entry `kind` taxonomy with its signers and T1 relevance, the state machine, the write-time invariants, and
**the `input_root` field that makes the T1/T2 boundary auditable end to end.** It settles the two things
this section left implicit: `happened_at` vs `recorded_at` (the chain attests *record* order; `happened_at`
is a claim by the parties) and the fact that **anchoring forces periods to be record-time**, which makes
lateness explicit rather than retroactive.

## 3.6 Dues is implemented

The projection §5.1 specifies now exists: `apps/coop-api/src/dues.ts` (`validateDuesPolicy`,
`evaluateDues`, `duesStatement`) over `dues_policy` + `dues_waiver`. **`money` and `coverage` are the two
modes with no source of truth yet and report `unavailable`** — an obligation resting only on them is
`undetermined`, never `unmet`. Routes and UI are the next step. Limits are enumerated in
`tier2-entry-model.md` §5.4.

### 3.7 The Peer.xyz (zkp2p) fiat rail — VERIFIED IN SANDBOX 2026-09-13

A fiat to USDC checkout rail: the payer uses Venmo, Cash App, PayPal or Wise, a P2P
counterparty receives the fiat, and USDC is released on **Base** to a destination address.
This is the implementation of the on-ramp already designed in `MASTER_PLAN.md` section D
("Provisional Peer.xyz Escrow"), and it is the fiat bridge in the ordered money path
(section 9) — money in, without the platform ever holding it.

**Verified against the live sandbox** (not read from docs — called):

| Fact | Value |
|---|---|
| merchant | `Indefatigable (Sandbox)` |
| environment | `SANDBOX` (asserted by asking, see below) |
| integration path | `CUSTOM_API` |
| destination chain / token | `8453` (**Base**) / `USDC` |
| rails | `venmo`, `cashapp`, `paypal`, `wise` |
| fee payer | **`MERCHANT`** — irl.coop pays the fee, not the payer |
| an order | created successfully: `status CREATED`, checkout URL returned |
| order statuses | `CREATED` / `PARTIALLY_FULFILLED` / `FULFILLED` / `CANCELLED` |

**Sandbox is MERCHANT-level, not URL-level.** The SDK's base URL is production
(`https://api.pay.peer.xyz`) and there is no sandbox URL. So the environment is a property
of the key. **Rule: a code path must assert `environment === "SANDBOX"` by calling
`getMerchant`, and must never infer it from a config flag or a URL.** A "sandbox mode"
env var that disagrees with the key is the failure that spends real money.

**The destination invariant.** `destinationAddress` is supplied *per order*, and the
merchant carries a default wallet (`v1EvmWalletAddress`). In the sandbox that default is
the merchant's own wallet — so a naive integration would send member payments to a wallet
the group does not control. There is no villain required for that to happen; it is the
default. Therefore:

> **The destination is read from the group's Safe, server-side, and is never accepted from
> a request and never left to the merchant default.** The member must be able to see the
> destination before paying, because anyone holding the merchant key can point an order
> anywhere — so the key is a redirect surface even though it never custodies funds.

**API contract, including two traps that cost a debugging cycle each:**

- `createCheckout` takes `requestedUsdcAmount` (+ the destination triple);
  `checkQuoteAvailability` takes **`amount`** and a **required `quoteMode`**
  (`"exact-token"` | `"exact-fiat"`). Same concepts, different field names.
- `checkQuoteAvailability` is **server-side only** — it sends the merchant key. And its
  `available: true` is **advisory**: it probes live liquidity and reserves nothing, so
  order creation can still fail. A P2P rail has no guaranteed counterparty, which means
  "pay by card" is never a guaranteed path and the UI must be able to say so.
- `PARTIALLY_FULFILLED` exists. **"The money arrived" is not boolean.** A partially filled
  order is a real state, which is why the Tier-2 `receipt` kind and coverage proofs matter
  more here than a checkout flag.

**Architecture, 2026-09-13: the rail is its own app.** Direct wiring into coop-api was
reversed the same day it was built, for two reasons — one regulatory, one that only showed up
by looking: installing the SDK put it in `apps/coop-api/package.json` and dragged a **native**
dependency tree (`secp256k1`, `sharp`) into the process that serves members' requests. A
provider's build failure or a provider's takedown should kill one container, not the API.

```
coop-api  ── HTTP + derived bearer token ──▶  apps/peer_xyz_payments  ──▶  provider
 owns the POLICY:                             owns the VENDOR:
   PAYMENTS_DESTINATION                         the SDK, its deps, its vocabulary
   PAYMENTS_CHAIN_ID / CURRENCY                 the status mapping
 owns the CONTRACT (neutral):                 owns NOTHING about the coop:
   payment_intent, statuses, idempotency        stateless; only translates
```

**The contract is in the coop's vocabulary, not the provider's.** `payment_intent` carries
`rail`, `provider_ref` (the vendor's id) and — the part that makes a swap possible —
`provider_payload` as the ONLY home for vendor detail, with statuses that are ours:
`pending | partial | settled | cancelled | failed`. `partial` is first-class because a P2P
rail settles partially. Nothing else in coop-api names a provider: verified by asserting the
module contains no vendor term at all.

**The rail declares its own limits, and the seam checks them.** `GET /rails` returns
`directToDestination` — a rail that would hold funds itself is refused by the seam, so the
invariant "the platform never intermediates" is enforced rather than documented — and
`canObserve`, which for Peer is **false with the reason**: the SDK exposes exactly six
functions and none looks up an order, so settlement **cannot be polled**. Reporting
`pending` there would be a fabricated status, and a settled payment would sit looking unpaid
forever.

**Swapping the provider, when it is taken down:** implement the interface in a new app (or
add it to the rail service), deploy, point `RAIL_URL` at it. coop-api's routes, table
and status vocabulary do not change. Two rails could even run at once, which is the resilience
argument for naming the app after the provider.

**Verified 19/19 through both processes** (`/tmp/hermes-verify-payments.js`): the rail's
capabilities arrive over HTTP; the destination is the coop's policy, echoed by the rail and
asserted against the order; the stored status is the coop's; the payer sees their payment and
another member sees nothing; the rail refuses a missing destination, a wrong token and an
unsupported chain; and confirming emits an event the live Temporal lane materialises into a
`receipt` entry keyed `peer:<provider_ref>`.

**The rail's cost is borne by the MEMBER, and it is capped at 20%.** The merchant config's
`maxFeeConfig.valuePercentage = 20` is the cap on the provider's markup on the fiat -> USDC
swap (confirmed by Robbie 2026-09-13). This is not our fee — `feePayer: MERCHANT` covers that —
it is **the price of an untraced, non-exchange, non-KYC settlement**, and it is the honest cost
of the rail's entire value proposition.

Three consequences that shape the product, not just the ledger:

1. **Show the real number before someone pays.** The provider's quote API returns actual quotes,
   so the UI can state the markup instead of burying it. A member discovering a 20% haircut on
   their dues *after* paying has been misled by omission.
2. **20% is large.** On a $25 dues payment that is up to $5 — a fifth of the obligation. The rail
   is therefore for **access** (people with no on-chain funds), not for routine payment, and the
   money-or-labour equivalence becomes more important, not less: paying by card is the *expensive*
   way to discharge dues, and the design says so out loud.
3. **Direct on-chain USDC stays available and cheaper.** A rail that costs a fifth is a reason to
   keep a path that costs cents, and to say which is which.

**The USDC router: deployed on the local chain 2026-09-13.**

`contracts/contracts/CoopUsdcRouter.sol` — the address a rail sends to, and a **one-way
forwarder** to a single immutable destination. It is deliberately *not* a swap router: the
rail delivers a plain ERC-20 `transfer`, **USDC has no transfer hook, so no code of ours runs on
arrival** — the tokens sit in the router until somebody calls `sweep()`. That is inherent to
ERC-20, so the contract does not pretend otherwise; what it guarantees is that the balance can
only ever go to one address.

| Property | Why |
|---|---|
| **No admin** — no owner, no setter, no upgrade path | an admin is a party a state can compel, which is the threat the design exists to survive |
| **Immutable destination** | `sweep` cannot be aimed anywhere else, so a transient balance is a message in flight, not custody |
| **Permissionless `sweep()`** | anyone may forward, nobody may redirect: no keeper to compel or to lose |
| **No `receive`/`fallback`** | ETH cannot be trapped here |
| **The deposit event names an OBSERVER, not a payer** | the depositor is unknowable on-chain; a field called `from` would be read as "the payer" by any indexer |

**It supersedes `CoopBatchRouter.sol`, which MASTER_PLAN.md names as the destination and which is
unusable:** it is `Ownable` (an admin), it takes **native ETH** rather than USDC, and
`routeDeposit()` accepts value and **keeps it with no withdrawal function at all** — money sent
there is gone. Recorded rather than silently replaced.

**On "use Uniswap":** we want its **shape**, not its logic. A Uniswap-style router is a *swap*
router, and there is no swap here — the proven-thing to borrow is the stateless, no-admin,
non-custodial router pattern, plus **OpenZeppelin's `SafeERC20`** for the transfer itself (which
already handles non-standard ERC-20 return values). If percentage splits are wanted later, the
proven contract is **0xSplits**, not a hand-rolled splitter.

**A fork this exposes, unresolved on purpose.** A *shared* coop-wide destination leaks nothing
about which group paid — but a plain ERC-20 transfer carries **no calldata**, so a shared router
**cannot know which group a deposit belongs to**. A *per-group* router attributes naturally but
tells the provider and the P2P counterparty which group paid. **The pool is what resolves this**:
one shared destination, batched, then shielded withdrawals into per-group/per-member value with
no public link — which is step 2. Until then, a shared destination means the coop pools, and
attribution stays off-chain.

**Unverified, and it matters:** the sandbox cannot move real funds, so it is **not confirmed that
the provider delivers by plain ERC-20 `transfer`**. If it delivers by calling a contract method,
the router could act on receipt instead of waiting for a sweep. To check before relying on it.

**Deployed on the local chain:** token `0x5FC8d32690cc91D4c39d9d3abcBD16989F875707` (a LOCAL
stand-in — on Base the token address must be **read from the chain**, never typed from memory),
router `0x0165878A594ca255338adfa4d48449f69242Eb8F`, destination a real provisioned group Safe
`0x3848b3479BD55B93E497ed6eaDd33B0b18Ac655c`. Driven end to end on-chain: transfer -> held ->
swept -> the Safe received it, router left at 0.

**Settlement arrives by webhook, and so do REVERSALS** (verified 14/14, 2026-09-13).

The provider's own types carry nineteen event types, and the two that matter most are not
"fulfilled": `PAYMENT_CHARGEBACKED`, `ORDER_PARTIALLY_CHARGEBACKED` and the `REFUND_*` family.
That is section 10's T+130 window arriving as data, and it fixes the meaning of a `receipt`
entry: **"funds arrived", not "funds are final."**

- **Authenticity.** The provider's types expose **no signature scheme** — `Webhook` carries only
  `customHeaders`. So authenticity comes from a custom header carrying a **derived secret**,
  configured on the merchant as a customHeaders entry, and the endpoint fails closed without it.
  A webhook is untrusted input from outside; it is validated, not believed.
- **Narrow exposure.** Only `Host(pay.<domain>) && PathPrefix(/webhooks)` is routed. Verified:
  `pay.irl.coop/webhooks/peer` answers 401 while `/intents` and `/rails` 404 through the edge —
  a payment provider cannot reach the rail's control plane.
- **Translation stays behind the seam.** A small explicit event map, in the rail app: an
  unrecognised event produces **no state change** rather than an assumed one (a 500 on an event
  we merely do not act on would look like an outage to the provider). `partial` is *derived* —
  `requested − remaining` — rather than taken on faith.
- **Retries are harmless.** `rail_event` is unique on `(rail, event_id)`, so a repeated delivery
  is a no-op; providers retry, and W4 asserts a retry changes nothing.
- **A reversal is a CORRECTION, not a deletion.** The intent goes to `reversed` (a new status in
  the coop's vocabulary) and the ledger gets a `correction` entry whose `refs` point at the
  original receipt. **The receipt itself stays exactly as it was** — entries are never deleted,
  and the money is accounted for rather than rewritten. The correction is keyed by the *event*
  id, not the order, so two different chargebacks are two facts.
- **The system write goes through a definer function.** An RLS-guarded UPDATE correctly refuses
  a system write with no member identity, so settlement runs inside `coop_rails_settle` (owned
  by `coop_rls`), and the contribution event is then emitted **as the payer**, so RLS admits the
  entry on its own merits instead of by exemption.

**One property worth knowing:** the outbox dedupes on `(source, source_event_id)` **globally**,
not per group — so if a provider ever *reuses* an event id, the second event is silently treated
as a retry and no entry appears. Peer's ids are its own and unique, and `rail_event` already
dedupes per `(rail, event_id)`, so this is a property rather than a bug; but a rail added later
whose ids are only unique per day would need the rail to namespace them before emitting.

`rail_event` carries FORCE RLS with **no user policies**: the provider's own words about a
payment are not something an application role reads. The trap worth remembering is that a
`SECURITY DEFINER` function runs as its **owner**, so it needs an explicit GRANT on every table
it touches — the settlement path failed 100% of the time until `rail_event` was granted to
`coop_rls`, and the log said exactly that.

**The boundary taught one thing the hard way:** the first version serialised the rail's
response by spreading its internal object, so the wire shipped `camelCase` while coop-api read
`snake_case` — a **200 that failed**. The contract is now serialised explicitly at the
boundary, so internal TypeScript names can never become the wire format.

**Limits, stated before they are discovered:** no route exists (this is a verified sandbox
call, not an integration); the merchant fee is **NOT MODELLED** (see the cost-model
caveat); `apiKeyIpAllowlist` is empty; the key lives in the ansible vault as
`peerpay.api_key` and is referenced as `${VAULT:peerpay.api_key}`, never in the tree.

## 4. The platform is NOT in the money path (and that is regulatory, not just values)

`cost-model.md` claims a **$0.00 platform fee**, tickets land in the group's own pot, and the fiat
bridge is a *vertical fund that is itself a group* — not the platform. That is an architectural
position with a legal consequence:

> **The platform never holds, moves, or intermediates member funds. Therefore it is not a money
> transmitter.** The moment it holds funds "just to make payouts easier," that changes — and it takes
> the whole shielded-treasury design with it, because a custodian platform is a party the state can
> compel (see `adversary-models-and-sector-fit.md` §0.5.1, the state as a permanent constraint).

**Record this as a design invariant, not a preference.** It is the single decision that keeps every
other money property intact.

## 5. The ordered path — after the decisions of 2026-09-13

### 5.1 DECIDED: chain = Base mainnet, Hardhat in dev

Recorded in `private-treasury-guards-ledgers.md` §9.2. Three consequences:

1. The treasury contract targets **Base** with an on-chain verifier. §8's "production launches shielded,
   and no public→shielded migration exists" now has a target environment.
2. **Any group created before the switch is scaffolding and will be REDEPLOYED.** Size this honestly —
   it is smaller than it sounds, because the two stores hold different things:

   | Store | Holds | Survives the switch? |
   |---|---|---|
   | **Postgres/Citus** | the group's *records*: `group_members`, roles, `resource_scopes`, seats, events, documents, the Tier-2 ledger | **Yes** — content and membership are not on-chain |
   | **Chain** | *authority and value*: the Safe, owner set, threshold, treasury, notes | **No** — re-established at redeploy |

   So redeployment means re-founding the *authority* (a new Safe, owners re-seated, treasury re-created
   and re-funded), not rebuilding the group. **The group's work survives; its keys and money do not.**
3. **Gas becomes a real out-flow** (§2.12) — the cost model carries no chain cost today.

**Sequencing consequence, and it matters:** the **Base switch must come BEFORE the coop's own group is
created** (`coop-launch-and-roadmap-handoff.md` item 2). Otherwise the coop's founding Safe — with real
members, real governance and real funds — is itself a throwaway. That is a new ordering constraint on a
parked item, and it is cheap to respect now and expensive to discover later.

### 5.2 DECIDED: no BYO rails

**Robbie, 2026-09-13: BYO is removed — it breaks governance-controlled finance, because the account
holder/creator has all the control.** The first draft of this document offered BYO as a v0 shortcut
past the treasury contract. **That was a governance regression, not a shortcut**, and the reasons are
worth keeping because they generalise:

| BYO breaks | How |
|---|---|
| **Quorum** | one person's Stripe account has one owner. There is no 2-of-3, no seat protection, no threshold — the control model reverts to single-person custody |
| **The guards** | all three enforcement points (in-circuit, `TransactionGuard`, app-layer) apply to Safe transactions. Money outside the Safe is governed by nothing |
| **The ledgers** | the group's books become incomplete: Tier-1 value exists off-system, so distributions, coverage proofs and "funds reached aid" cannot be computed |
| **§10's chargeback model** | the 130-day reversal window is what the vertical fund *exists* to absorb. BYO pushes that risk onto an individual member |
| **The internal adversary** | "the creator has all the control" is `adversary-models-and-sector-fit.md` §1.1 (**the founder**, and **I7 the steward**) at its purest — the exact tension the threshold design removes |

**Consequence: the treasury and its rails are on the critical path for money. There is no bypass, and
that is the correct property.** It also means the empty `STRIPE_SECRET_KEY` in `hievents.yaml` must not
be "fixed" by pointing groups at personal payment accounts — ticket money should land in a **group
treasury**, which is a step-3 dependency, not a config line.

### 5.2b Migrating off Hardhat — Base Sepolia first (2026-09-13)

**Yes, and what it can prove is specific.** Base Sepolia is a real network with real gas, a real
Safe, real deployment verification and a real explorer. It is a rehearsal for the **chain** side.
It **cannot** test the payment rail: the provider declares `chains: ["8453"]` and its merchant
config carries `destinationChainId: 8453`, so **USDC is delivered on Base mainnet only**. A
Sepolia router can never receive a Peer payment. A real payment test is a mainnet test.

**Two things must change before ANY non-local chain, and one is a standing hazard:**

1. **`SAFE_BACKEND_SIGNER_KEY` is Hardhat account #0's published private key, in plaintext in
   `apps/coop-api.yaml`.** Correct for a throwaway local chain; disqualifying anywhere else. On a
   real network it becomes a fresh key in the **ansible vault**, referenced as
   `${VAULT:...}` — never in the tree. Note what that key *is*: a signer that deploys group
   Safes, so it is a privileged role, and the smaller what it holds and can do, the better.
2. **`SAFE_SINGLETON_ADDRESS` / `SAFE_PROXY_FACTORY_ADDRESS` must point at that chain's
   deployments** (`deploy_local.ts` is chain-agnostic and deploys the Safe singleton, the proxy
   factory, and the coop's modules — passkey validator, sovereign-evolution, session-key).

**Key handling, as a rule rather than a habit:** a deploy key is read from a **0600 file** by
`scripts/deploy_router_testnet.sh`, which refuses a group/world-readable key file, refuses an
account with no gas money, and never prints the key. The key never enters a transcript, a shell
history, or the tree. This is the pattern for every future deployment.

**Sepolia is a REHEARSAL, not a destination.** The recorded constraint is that the chain switch
must come *before* the coop's own group is created, because authority and value live on the chain
and do not survive a move: **do not create real groups on Sepolia** — they would be throwaway in
exactly the way a mainnet group is not.

**Addresses, verified on-chain rather than taken from a document** (a token address on trust
sends funds nowhere), recorded in `contracts/networks.json` with the how and the date:

| chain | id | USDC | verified how |
|---|---|---|---|
| Base | 8453 | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | `eth_chainId` 0x2105; `symbol()` = USDC; `decimals()` = 6 |
| Base Sepolia | 84532 | `0x036CbD53842c5426634e7929541eC2318f3dCF7e` | same three facts, plus `5c60da1b` (`implementation()`) = Circle's proxy |

**The kit** (`contracts/`): `networks.json` (per-chain facts); `scripts/verify_deployment.ts` —
a **read-only** post-deploy verifier that asserts the chain, that the address is a *contract*
(not an EOA and **not an EIP-7702 delegation**, which is the false green the payments preflight
hit), that the token really answers USDC/6, that `destination()` is the expected address, and that
the deployed ABI exposes **no admin surface**. Proven 6/6 against the local deployment before
being pointed anywhere real. Plus `scripts/whoami.ts` (who pays, and can they) and the wrapper.

**Order:** Sepolia rehearsal → mainnet contracts → then the rail's live test → and only then the
coop's own group, so the founding Safe is not a throwaway.

### 5.3 The path, revised

| Step | What | Depends on |
|---|---|---|
| **0** | ~~chain choice~~ **DONE — Base mainnet** | — |
| **1** | **The Tier-2 contribution ledger** — off-chain, hash-chained, periodically anchored to Base. Dues records, contribution records, entitlement tables, coverage proofs | nothing blocking; buildable now. Anchors need Base (cheap) |
| **2** | **The shielded treasury contract on Base** — notes, commitment tree, nullifier set, verifier, viewing keys, selective-disclosure reporting | step 0 ✅ |
| **3** | **The rails — the only visible crossings.** Deposit (fiat/stablecoin → shielded) and withdrawal (shielded → fiat), with the vertical fund as the fiat→crypto bridge and §10's T+130 settlement | step 2; and the vertical fund must be **capitalized** |
| **4** | **v1 automation** — in-circuit distributions, zk-badge gates, timelock/circuit-breaker | step 2 |
| — | ~~BYO rails~~ | **removed by decision (§5.2)** |

**Why step 1 is still first:** it needs no chain work, it is what makes a group's contribution history
*provable* (the coverage proof is the whole commons economy), and it is a prerequisite for distributions
in step 4 rather than an alternative to them.

## 6. Decisions needed (all Robbie's / the coop's)

| # | Decision | Blocks |
|---|---|---|
| 1 | ~~**Chain choice**~~ — **DECIDED: Base mainnet, Hardhat in dev** | §5.1 |
| 2 | ~~**Is BYO-rails the v0?**~~ — **DECIDED: no**, it breaks governance-controlled finance | §5.2. The treasury is now on the critical path for money |
| 3 | **Pricing**: member dues and group contribution (both still `illustrative`) | the coop's own revenue; the landing FAQ's "sliding scale" |
| 4 | **Who is the vertical fund, and who capitalizes it?** | sponsorship, chargeback protection, the fiat bridge |
| 5 | **The legal entity** — statutory bookkeeping falls on an operating entity that does not exist yet | taxes, and the whole compliance story |
| 6 | **Stewardship compensation** — is the $360/mo paid, deferred, or volunteered? **Partly answered 2026-09-13: paid roles are the mechanism (`tier2-entry-model.md` §5.2); whether to use it is still open** | whether "self-sustaining" is honest |

## 7. Do not

- Do not build a treasury contract before the chain decision (it will be rebuilt).
- Do not let the platform ever hold member funds — §4.
- Do not publish a price before the coop sets one (the FAQ's "sliding scale" is aspirational, and the
  registry already says so).
- Do not treat the empty `STRIPE_SECRET_KEY` as cosmetic: it is the difference between a live ticketing
  app and a live ticketing *business*.
