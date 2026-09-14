# The Tier-2 entry model

Status: design (buildable spec) · 2026-09-13 · Robbie + Hermes.
Consolidates: `money-in-and-out.md` §3.1 (what T2 is), §3.2 (who may counter-sign), §3.3 (off-chain +
anchored), `sharded-ledgers-and-anchors.md` (per-group chains, period roots, one anchor stream).

**This is the piece that makes Tier 2 buildable.** Everything else was settled first deliberately.

**Step 1 (§10) is BUILT** — `tier2_entry`, `tier2_signature` and `anchors` are in `db.ts` (DDL, self-provisioning
on boot, idempotent), their RLS policies are in `infra/compose/storage/scripts/coop_rls.sql`, and the append
path with invariants 1–2 (`appendTier2Entry`, `countersignTier2Entry`) is implemented. **Step 3 is BUILT too** — period Merkle trees, inclusion proofs, and the anchor writer
(`tier2MerkleTree`, `tier2InclusionProof`, `tier2VerifyInclusion`, `anchorTier2Period`,
`anchorTier2Federation`), plus the three operator-only SQL functions that let an anchoring job read
entry *ids* and claim an anchor slot without the app role being able to mint a root.

**Verified against the live Citus in a rolled-back transaction (34/34):** the DDL and the RLS/anchor
bootstrap both apply, an append with no membership is refused by policy, the duplicate-`seq` guard fires,
`DELETE` removes **zero** rows, the catalogue holds **no DELETE policy** on the ledger, and the app role can
neither execute `coop_anchor_slot` nor write `anchors` at all. Merkle: deterministic, order-binding, proofs
verify for **every** leaf at sizes 1–17, a tampered entry or root is rejected, and an odd level is promoted
rather than duplicated. Content addressing is key-order independent.

**And the full write path is verified END TO END (14/14), against the deployed schema:** three entries
appended → an idempotent re-append returning the *same* entry → a role-holder counter-signature moving it to
`countersigned`/`attested` → the self-dealing guard refusing a self-counter-signature → the period ids read
through the operator function → **the anchored root equal to an independent client-side recomputation** → a
selective-reveal proof verifying **against the anchored root** → re-anchoring idempotent → a *different* root
for the same period **flagged as a conflict and not overwriting** → the federation root → the anchor readable
by a member through RLS. The test commits real rows and removes only its own afterwards, as the superuser —
the one role RLS cannot stop. **"Nothing persisted" is verified by
*querying* the live catalogue after the rollback, not by trusting that `ROLLBACK` returned** — a stray `END;`
from a mis-split statement (and `END` is a synonym for `COMMIT`) once committed this schema while the
rollback call still reported success.

## 1. The record

```sql
-- sketches, not migrations: the shape is the point
CREATE TABLE tier2_entry (
  entry_id       text PRIMARY KEY,        -- content hash of the signed body: the id IS the hash
  group_id       uuid NOT NULL,           -- THE SHARD KEY (sharded-ledgers-and-anchors.md §1)
  seq            bigint NOT NULL,         -- monotonic per group; gap detection
  prev           text,                    -- hash of the previous entry IN THIS GROUP'S CHAIN
  period         date NOT NULL,           -- derived from recorded_at — see §4, this is forced
  kind           text NOT NULL,           -- see §5
  subject        uuid NOT NULL,           -- the seat/asset credited or described
  counterparty   uuid,                    -- the other party for swaps, checkouts, deliveries
  scope          text,                    -- project / asset / sub-scope (treasury project model)
  quantity       numeric,
  unit           text,                    -- hours | items | kg | …
  happened_at    timestamptz,             -- WHEN IT HAPPENED — a claim by the parties (§4)
  recorded_at    timestamptz NOT NULL,    -- when written; what ordering and periods are built from
  signed_at      timestamptz NOT NULL,    -- when THIS signature was made (§3.2 validity-at-signature)
  payload        jsonb,                   -- plaintext or encrypted per the group's footprint mode
  refs           text[],                  -- other entry_ids: corrections, swap pairs, dispatch↔receipt
  state          text NOT NULL,           -- §6
  basis          text NOT NULL,           -- attested | machine-only  (§3.2 signature classes)
  threshold      jsonb NOT NULL,          -- the policy APPLIED, recorded not re-derived (§7, drift)
  idempotency_key text NOT NULL,          -- a retried write must not double-log
  anchor_id      uuid,                    -- filled when the period root is anchored
  UNIQUE (group_id, seq),
  UNIQUE (group_id, idempotency_key)
);

CREATE TABLE tier2_signature (
  entry_id   text NOT NULL REFERENCES tier2_entry(entry_id),
  group_id   uuid NOT NULL,      -- DENORMALISED so the RLS policy can match the waypoint
                                 -- pattern (a policy cannot reach group_id via entry_id cheaply)          -- seat
  class      text NOT NULL,          -- role-holder | scoped-key | group-vote
  authority  text NOT NULL,          -- WHAT GRANTED THIS POWER: role-grant id | key id | decision id
  valid_from timestamptz NOT NULL,   -- the authority's own window, for validity-at-signature-time
  valid_to   timestamptz,
  signed_at  timestamptz NOT NULL,
  sig        text NOT NULL,
  PRIMARY KEY (entry_id, signer)
);
```

**`entry_id` is the content hash of the signed body**, so the id is derivable from the entry and no
minted identifier can be forged independently of the content it names.

## 2. `happened_at` vs `recorded_at` — and why the chain must not pretend they are the same

Labor gets logged late: Tana writes down Saturday's market on Monday. So:

- **The chain attests *record* order.** `seq`/`prev` order the entries as they were written.
- **`happened_at` is a *claim by the parties*.** Anything relying on it relies on the **signatures**, not
  on the chain.

Saying this out loud matters because it names a real attack: **retroactive stuffing** — adding a week of
hours the day before a distribution. Mitigations are in §7 (late-entry marker, higher threshold beyond a
window, and the fact that distributions read ratified entries only).

## 3. Signatures: the authority reference is mandatory

Per `money-in-and-out.md` §3.2, the three classes are one object — a signature from an authority the group
conferred. So **every signature carries its authority reference and that authority's validity window.**

**The check at write time is: was the authority valid at `signed_at`?** Not "is it valid now." That is
what lets a compromised key be revoked instantly **without** invalidating the entries it legitimately
signed, and it stops a role departure from silently rewriting history.

## 4. Anchoring forces periods to be record-time — and forces lateness to be explicit

A period tree is built over a group's entries and its root is **anchored**, i.e. published and immutable.
**Therefore a period cannot be defined by `happened_at`** — a backdated entry would change an
already-anchored tree, which is impossible by construction.

So:

- **Periods are defined by `recorded_at`.**
- **`happened_at` may point anywhere in the past; `period` never moves.**
- **A late entry is a first-class concept**, not a silent backdate: always recorded in the period it was
  written, with an explicit `late: true` marker when `happened_at` falls outside a configured window.

This is a genuine consequence of anchoring rather than a preference, and it is the kind of thing that is
very expensive to discover after entries exist.

## 5. Kinds — each with its own signers, threshold, and T1 relevance

| `kind` | Example | Created by | Counter-signed by | Affects T1? |
|---|---|---|---|---|
| `hours` | 6 h at the market stand | member, or a **scoped key** at the stand | a **role holder** (market manager), or a scoped key | **yes** — feeds entitlements |
| `swap` | childcare ↔ tractor work | either party | **the other party**; a cross-group swap is **two entries with mutual `refs`** | **yes** |
| `custody` | nail gun checked out | scoped key (terminal) | recipient, or a role holder | no (custody chain) |
| `receipt` | mutual-aid delivery received | provider | **the recipient** — never the provider | **yes** — this is "funds reached aid" |
| `in_kind` | vegetables, space, a skill taught | any member | **the recipient** (the group, or a member) | yes (recorded value) |
| `vote` | a decision's outcome | the decision system (`decisions.ts`) | quorum, via EIP-1271 | **yes** |
| `incident` | contamination detected | any member | a role holder, or a vote | no |
| `correction` | fixes a mis-logged entry | anyone | **the same threshold as the target** | inherits the target's |

**A group may always authorize its own exception by vote.** That is the honest escape hatch for any rule
above — including the no-self-dealing rule — and it is why every one of these is a *default*, not a wall.

## 5.1 Dues is NOT an entry — it is a projection, and there are two different "dues"

**`dues_status` was in the kinds table and should not be.** It is not a fact to record; it is a
**predicate computed over records that live in different tiers**. Storing a boolean would create a second
source of truth that will eventually disagree with the first.

**And the reason the word felt confusing: two layers share one name.**

| Layer | What it is | Who sets it | Where it lives today |
|---|---|---|---|
| **Platform dues** | a member's share of the *coop's infrastructure cost* | irl.coop's governance | cost model `revenue.member_monthly` *(illustrative)* |
| **Group dues** | *this group's* own membership obligation | **the group** | the group's shape config |

They were being conflated. The cost model's `$3/member` is platform-side; "what if we mostly trade favors"
on the landing page is group-side. **Naming them separately is most of the fix.**

### The modes a group may accept

| Mode | Source of truth | Tier | What the input reveals |
|---|---|---|---|
| Money | treasury receipts for the period | **T1** | shielded; nobody sees it |
| Participation | `hours` / `swap` entries | **T2** | the counter-signers |
| Stewardship | a **role grant** with a validity window — *holding the role IS the contribution* | authority layer | role visibility is a group setting |
| In-kind | `in_kind` entries | **T2** | the parties |
| Coverage contribution | hosting a node, running an archiver, anchoring | coverage proof (federation) | provable, not readable |
| Waiver | a `vote` decision | **authority act** | the group (a waiver is a group act) |

**The group's `dues_policy` defines which modes count and how they convert** — *"$25/mo **or** 4 hours of
participation **or** holding the compost role."* That equivalence **is a governance decision**, not an
implementation detail, and it belongs in the group's shape config. It carries a cadence (monthly, annual,
**seasonal** — a farming co-op thinks in seasons) and a grace period.

### The privacy requirement this creates — and it is the interesting part

**A satisfied-dues readout must not reveal *which mode* satisfied it.** "Paid" leaks financial capacity;
"participated" leaks that they could not pay. Either one turns a sliding scale into a visible status ladder.

So the status is a **proof, not a record read**:

> **"Member M's obligation for period P is satisfied"** — proven over T1 + T2 + authority records,
> revealing a **boolean** (and optionally the satisfied fraction), never the inputs.

This is the coverage-proof pattern applied to membership, and it produces a property worth stating plainly:

> **Money and labour become indistinguishable at the boundary.** Nobody — not the group's officers, not an
> outsider — can tell who pays and who works instead. That is what keeps a sliding scale from becoming a
> hierarchy.

**Honest caveat: the proof only hides what the inputs hide.** If a *visible* mode (holding a role) alone
satisfies dues, then role visibility leaks dues-satisfaction. That is an argument for policies where no
single visible mode is sufficient on its own, and for role visibility remaining a per-group setting.

### Visibility, and the neutral-absence rule

| Readout | Visible to |
|---|---|
| Individual status (boolean / proof) | **the member**, and only the roles that need it for bookkeeping |
| Aggregate ("we are 80% covered this period") | the group |
| Which mode, how much, from whom | **nobody** — proof-only |

**Absence stays neutral and carries no shame flag** (`event-bus-and-group-shapes.md` §7): the status is for
the group's bookkeeping and the member's own view, **never a league table**.

## 5.2 Paid roles — and the two rules they force

**Some members are paid for the roles they perform.** That is not an edge case; it is how the federation's
own dominant cost becomes legitimate rather than donated — the cost model carries stewardship at ~$360/mo
*currently unpaid*, which is Robbie's own subsidy (see `money-in-and-out.md` §2.2).

**Mechanically, paid roles need nothing new.** They reuse the ordinary path:

```
T2 `hours` entries (the work)  →  entitlement table  →  T1 distribution (shielded, on-chain)
                                                        └─ records its `input_root` (§8)
```

So a "stipend" or "shift rate" is an **entitlement kind**, not a new mechanism. Two rules follow, though,
and both are the kind that surface later as bugs if they are not decided now.

### Rule 1 — a compensated role cannot also discharge dues in the same mode

§5.1 makes **stewardship** a mode of dues: *holding the role satisfies the obligation.* But if that role is
**also paid**, the holder is being paid twice for one activity — once in cash, once in obligation-forgiveness.

> **Default: a compensated role does NOT also discharge the holder's dues.**
> The `dues_policy` states, **per role**, whether it does both. A group may deliberately choose "the stipend
> covers your dues *and* pays you" — but as an **explicit line in the policy**, never as an emergent
> side-effect of the two rules both being written down without reference to each other.

### Rule 2 — compensation changes the failure mode, so it changes the required rigor

**Compensating a role turns a fairness ledger into a payroll ledger.** Tamper-evidence is the same
mechanism, but the *incentives* differ in kind: a favor ledger invites sloppiness, a payroll ledger invites
collusion and padding. Three consequences:

1. **Independence.** A paid role's `hours` entries need a counter-signer **who is not paid on the same
   basis** — otherwise two mutually-counter-signing paid members can inflate each other's hours, and every
   signature validates.
2. **A value threshold.** Above a per-period amount, the entry set needs **vote ratification**, not just a
   role-holder signature (§3.2's thresholding, now with money attached).
3. **The aggregate is the control.** Individual amounts may be shielded; **the period aggregate is visible
   to the group** ("we paid $4,000 in stipends this month"). A payroll that doubles is visible even when no
   single line is — that is the same privacy/audit trade as the coverage proof, applied to spending.

### Rule 3 — and this one is not technical

**Paying members for work creates filing and tax obligations that no ledger design removes.** The moment a
group compensates a member, most jurisdictions attach some duty — withholding, contractor vs employee,
an annual filing — and the money doc already notes that **the legal entity does not exist yet, and that is
what statutory bookkeeping attaches to** (`money-in-and-out.md` §7). The ledger makes the flow *provable*;
it does not make it *compliant*.

> This is a flag, not legal advice. The design should surface it at the point a group first sets a
> compensated role, rather than let a group discover it at year end.

### Waiver, bounded

**Decided: a vote OR a role may grant a waiver.** Both are legitimate, and the difference is cost:

| Path | Cost | Risk it carries |
|---|---|---|
| **Role** | cheap, immediate | **one person becomes the arbiter of who owes what** |
| **Vote** | slow, expensive | none beyond the group's own judgement — and it is the **override** for the role path |

So a role-granted waiver must be **bounded and reviewable**, or it is a standing power:

1. **Bounded** — a term, a period count, or a maximum. Otherwise the role can waive indefinitely.
2. **Aggregate-visible** — the group's coverage math must reflect waivers, so the *count* of waivers is
   visible even where the individual reason is private.
3. **Overridable by vote** — the group is sovereign over the role it granted. A vote can reverse a
   role-granted waiver; nothing can reverse a waiver the group itself granted except the group.
4. **Never self-granted** — the role holder cannot waive their **own** dues (§3.2's no-self-dealing rule,
   which needs no exception here because the vote path exists for exactly that case).

## 5.3 Expressing `dues_policy` — a table, not a language

**Robbie's worry (2026-09-13): *"it can get very very convoluted with rules."* Correct, and the answer is not
to build a better rules engine — it is to deliberately under-power the policy.**

**The governing constraint is not expressiveness, it is legibility.** A dues policy is a *governance*
artifact: members must be able to read it and agree to it. **A policy that requires an expert to interpret
is a policy nobody consented to.** And if the only way to answer *"does Sam owe anything this month?"* is to
run the engine, the group has delegated its own rule to the implementation.

### The shape: two flat lists, and one connective

```yaml
dues_policy:                        # versioned + append-only; a change needs a VOTE (§5.3.6)
  version: 7
  grace_days: 14                    # the ONE global concession knob (§5.3.3)
  obligations:
    - id: core                      # a group needing "pay $25 AND work 4h" writes TWO obligations
      cadence: monthly              # fixed vocabulary: weekly|monthly|quarterly|seasonal|annual
      satisfied_if: any             # the ONLY connective. ever.
      modes:
        money:         { min: 25, currency: USD }
        participation: { min_hours: 4 }
        stewardship:   { roles: [compost] }
        coverage:      { min: covers_self }
        in_kind:       { min_equivalent: 25 }
    - id: shifts
      cadence: weekly
      modes:
        participation: { min_hours: 3 }
  waiver:
    by: [vote, treasurer-role]
    max_periods: 3
```

**Obligations are a list. Each obligation is satisfied by *any* of its modes.** No nesting, no `and`/`or`
trees, no negation. The whole policy is a table two levels deep, and any member can check a case by hand.

### The five anti-convolution rules

**1. If you need `and`, you have two obligations.** *"Pay $25 AND do 4 hours"* becomes two obligation rows,
each independently satisfied. This is not a workaround — it is better, because the readout becomes
**"1 of 2 satisfied, you still owe the shifts"** instead of a single opaque boolean. Members want to know
*what is left*, not pass/fail.

**2. No arithmetic between modes.** The moment *"2 hours = $10, cash covers the rest"* is legal, you have
built a **currency exchange with a rate table the group must maintain and keep honest.** Modes are
**alternatives, not components.**

**3. Exactly one concession knob: `grace_days`.** Not proration, not carry-over, not tiered hardship bands.
Partial payment is a *ledger* fact; satisfaction is a *policy* fact — a member who paid half has done
something real that a grace period plus a waiver path already covers.

**4. Bounded vocabularies everywhere.** Cadences, units, and role names come from **fixed lists**. Free text
is how "the policy" becomes a paragraph nobody can parse.

**5. Every edge case becomes a DECISION, not a rule.** This is the load-bearing one:

> **The escape hatch is a vote, not a rule.** Anything the table cannot express is handled by *"the group
> waived it"* — a decision, which is **naturally dated, bounded, attributable, and reviewable** — rather
> than by growing the policy.

**That is what stops the convolution.** Complexity accumulates in decisions instead of in the rule, and
decisions do not compose with each other.

### 5.3.6 Change control — the line that prevents capture

**A general rule needs a vote; a specific exception may be granted by a role** (§5.2's waiver decision,
applied one level up).

| Artifact | Changed by | Why |
|---|---|---|
| The **policy** (thresholds, modes, cadence) | **a vote** | a treasurer who can edit the policy can change what *everyone* owes |
| A **waiver** for one member, one period | **a vote, or a bounded role grant** | cheap for the common case, bounded so it cannot become a standing power |

This is the same shape as the constitutional-vs-ordinary distinction already in the design, and it means
**no single role can move the goalposts** unilaterally.

### 5.3.7 Two things the policy must carry

**Versioning, and the version recorded per period.** A policy change must never retroactively re-judge an
already-satisfied period (§7 invariant 5). The readout cites the version that applied, so *"why was this
satisfied?"* has a dated answer.

**A preview — the policy's consequences before the group adopts it.**

> **You cannot agree to a policy whose consequences you cannot see.**

So adopting a policy shows the *distribution of outcomes* under it against the current membership —
"34 satisfied by money, 4 by participation, 2 by coverage, 3 waived" — **before** the vote. Note this is a
*count-only* preview: it respects §5.1 by never revealing which member used which mode.

### A worked pair, to show the ceiling is high enough

```
Food co-op:   core = $25/mo | 4h/mo | [compost, market] | covers_self      + shifts = 3h/week
Tool library: core = $20/yr | 2h/mo | [repair-night]                       (one obligation)
```

Both read in one screen, both auditable by hand. **If a group's real policy cannot be written this way, the
system is telling them to discuss it at a meeting** — which is the correct outcome, not a limitation.

## 5.4 The dues model is BUILT — and here is exactly what it does not do

`apps/coop-api/src/dues.ts` + `dues_policy` / `dues_waiver`. **Verified 40/40** against the deployed
schema: the validator refuses every shape that would make a policy a language, the evaluation resolves four
of the six modes from real records, the redacted readout carries no mode and no amount, and RLS keeps a
waiver private to the member it concerns.

**Four honest limits, stated before they are discovered:**

1. **Two of the six modes are `unavailable`, and an unavailable mode is never "not satisfied".** `money`
   needs Tier 1 (the treasury is unbuilt) and `coverage` needs a proof verifier. A money-only obligation
   returns **`undetermined`** — never `false`. Consequence: **dues works today for groups whose dues are
   non-monetary** (the food co-op and barter case) and is honestly incomplete for money. Reporting an
   uncheckable obligation as unmet would tell a member they owe something on the strength of a system that
   cannot see.
2. **Mode-hiding is access control plus redaction, NOT zero-knowledge.** The member sees their own modes; a
   third party gets a boolean. But **a party that can read the rows — an operator, anyone with database
   access — can see the mode.** That is strictly weaker than the proof §5.1 describes, and it is the same
   distinction as disk encryption versus the compelled case: the honest claim is "the *readout* does not
   disclose the mode", not "the mode is unknowable".
3. **The `dues.bookkeep` grant is not in the grants catalogue yet**, so the bookkeeper path is inert: today
   only the member can see a waiver, which means **the group's aggregate count is not yet available.** That
   is the missing half of "the group sees the count, nobody sees the mode".
4. **The statement is UNSIGNED and says so.** An unsigned boolean proves nothing to anyone who does not
   already trust the holder; `duesStatement` carries the canonical form so a group-key signature can attach
   to exactly that form — which is the next step, not this one.

## 5.5 Routes and UI — built

**API** (`dues.ts`, registered in `server.ts`, verified live through the edge: an unauthenticated
call returns **401 `invalid_token`** while a nonsense path returns **404**, so the handlers are
registered and reachable):

| Route | Who | Notes |
|---|---|---|
| `GET /groups/:id/dues/policy` | member | active version + drafts + history |
| `PUT /groups/:id/dues/policy` | `dues.policy.write` | **always a draft**; the response names the validation violation |
| `POST /groups/:id/dues/policy/:v/adopt` | `dues.policy.write` | **requires a passed decision**; supersedes the old active in one transaction |
| `GET /groups/:id/dues/me` | member | **the only place `reveal` is true** — your own modes are yours |
| `POST /groups/:id/dues/waiver` | `dues.bookkeep` | bounded by `max_periods`, **never self-granted** |
| `GET /groups/:id/dues/summary` | member | counts only, via a membership-guarded function |

**UI** (`dues-panel.tsx` + `/dashboards/dues`, a tile on the coop home) — previewed against seeded
data and showing all three states: `core` **satisfied by participation**, `annual_fee` not satisfied,
and `land_dues` **"cannot be checked yet — no Tier-1 source"**. Plus the statement (2/4, *unsigned*),
the group's count-only view, and the bookkeeper section.

**Two authorization rules carry the surface**, and one caught a real leak: the aggregate count was
guarded with `coop_can_view_group`, which is true for **anyone** on a group with `privacy='open'` —
so an outsider could read a group's waiver count. It is now `coop_is_member`. *The aggregate is for
the group.*

**Honest limits of this step:**

1. **The HTTP layer is not exercised with a real JWT** — it needs a Keycloak session, so what is
   verified here is route registration (through the edge), the DB logic the handlers delegate, and the
   rendered page. End-to-end click-through belongs to the browser-journey suite.
2. **There is no policy-authoring form.** Drafting and adopting go through the API; the panel shows the
   version, the draft count, and an adopt field for a decision id. A form is UI work with no new model.
3. **`via` is deterministic only because of §5.4's fix** — jsonb sorts keys by length, so storage order
   would otherwise decide which satisfying mode gets reported. It now follows the mode vocabulary order.

## 5.6 Where entries COME FROM — the durable lane (Robbie, 2026-09-13)

**Robbie's call: *"tier-2 entries should come from the event-bus/temporal."* Correct — and it is
already the chosen architecture, not a new one.**

| Already in the tree | What it gives the ledger |
|---|---|
| `events` table = the outbox, with **`source` + `source_event_id`** | exactly the idempotency material §7.2 needs, already modelled |
| `temporal/worker.ts` — *"the delivery worker: the durable lane of the event bus (option A)"* | the durable consumer |
| `deliverySweep` → **one child workflow per undelivered event** | the existing fan-out shape |
| `ensureSweep(...)` with **idempotent workflow ids** | a restarted worker resumes instead of duplicating |

So the Tier-2 leg is **a new event type and a new consumer**, not new infrastructure:

```
contribution.logged {sub, source, source_event_id, task_id, done_at}
      ↓  (outbox row, committed with whatever caused it)
  tier2Sweep  →  one child workflow per event  →  activity
      ↓
  appendTier2Entry(...)      ← the ONLY writer, invariants 1–8 intact
      ↓
  attestation workflow: notify eligible counter-signers → wait → attested | expired
```

### One refinement, and it matters: the transactional outbox

**The ledger row and its event must be able to commit together — so the system of record never
depends on the messaging layer's availability.** If the *only* way to record an hour were a
workflow, then Temporal being down would mean a coop cannot log the day's work, and the record is
more important than the notification.

That splits by who initiates:

| Initiated by | Path | Why |
|---|---|---|
| **A machine** (Plane/LiteFarm/cal.diy webhook) | emit the outbox row only; the lane materialises the entry | the source is *already* async and has its own retry expectations |
| **A human** (a member taps "log 3 hours") | `appendTier2Entry` **and** the outbox row in ONE transaction | they must see their own entry; a queue delay is indistinguishable from a failure |

Both end at the same writer, so the invariants stay in one place. The difference is *who calls it*,
not what it does. **Read-your-writes is not negotiable for the member, and it is irrelevant for a
webhook** — which is the whole reason the split is worth making.

### What Temporal should own, where durable timers genuinely pay

1. **The attestation lifecycle** — `proposed → notify → wait (days) → attested | expired`. A
   human-in-the-loop wait with reminders and an expiry timer is a workflow's sweet spot, and the
   `expired` state (§6) is the timer. This is the strongest case in the whole system.
2. **The anchor runs** — daily period roots and the federation root (`sharded-ledgers-and-anchors.md`),
   scheduled and retried, already idempotent by `UNIQUE (family, scope_id, period)`.
3. **Later, the T1 distribution runs** — with their `input_root` (§8).
4. The existing delivery / digest / postiz sweeps, unchanged.

**Not:** the entry append itself, per the availability argument above.

### Concurrency: per-group ordering must be preserved, not raced

**Corrected 2026-09-13 while building it.** The first draft said the child workflow id should carry
the shard (`tier2-{group_id}`). That is wrong, and the reason is worth keeping: a shared per-group
id means a second start *while the first is running* fails as already-started, and that event is then
**skipped silently**. The implementation instead goes **one child workflow per event**
(`tier2-{event_id}`) and processes the batch **serially, in `occurred_at` order** — order is preserved
by construction rather than by id, and the advisory lock (§7.1) remains the backstop that stops a fork.
A retry storm is not a queue: concurrency here is the thing to avoid, not to manage.

**Reads never depend on the engine** — dues and proofs are queries.

### Two things the build taught, recorded because both cost real time

**1. `startChild` takes a child WORKFLOW, not an activity.** Passing the activity proxy made every
workflow task fail with `Failed to initialize workflow of type 'activityProxyFunction': no such
function is exported by the workflow bundle` — **and the failure mode was a silent retry storm**: the
event sat untouched, the entry never appeared, and nothing surfaced where you would look first. The
wrapper is the same shape as the existing lane: `deliverNotification` is a workflow around the
`markDelivered` activity, and `materializeContributionWorkflow` is a workflow around
`materializeContribution`.

**2. The event pool must be PARTITIONED, or the delivery lane eats the work.** Both lanes claim from
`events` and both mark rows delivered, so `coop_sweep_undelivered` now **excludes `contribution.%`**.
Without it the delivery lane — whose activity is a stub that stamps `delivered_at` — wins the race and
the ledger never sees the work. One pool, two disjoint consumers.

### The failure discipline, and what the machine lane's signature is

A **transient** error (database down) is re-thrown so Temporal retries. A **permanent** one — a
malformed payload, or a `sub` who is not a member — can never succeed, so the event is
**dead-lettered** (marked delivered, logged loudly) rather than stalling the lane forever. The log IS
the dead-letter record today; a table for it is a follow-on.

And the append runs under **`app.sub = payload.sub`** — the member the work is *about*. That is not a
shortcut: it means the RLS insert policy (`coop_is_member`) does the authorization, so a compromised
source can only create entries for people who really are in that group. The `sig` on a machine entry
is a **provenance marker, not a cryptographic signature** — there is no key material for a source yet
(that arrives with scoped source keys, §3.2), and nothing Tier-1-eligible depends on it because the
basis stays `machine-only`.

## 5.7 The member-facing write path — built

| Route | Who | What |
|---|---|---|
| `POST /groups/:id/contributions` | member | log work about **yourself**; `sub` may name someone else only with `tier2.attest` |
| | same route, `countersign: true` | an organizer recording on another member's behalf **and confirming it in the same request** — allowed precisely because the counter-signer is not the beneficiary. This is the clipboard case from `coop-work-signup-checkoff.md` |
| `POST /groups/:id/entries/:entryId/countersign` | `tier2.attest`, or a **passed `decision_id`** | an attestation: *"I saw this happen"*, or the group accepting it by quorum |
| `GET /groups/:id/entries` | member | your own; `?pending=1` needs `tier2.attest` (other people's *unattested* claims, which a group may see — §9 open question 3's instinct) |

**Verified 13/13 at the DB level** (the HTTP layer needs a real Keycloak JWT, so it is exercised
through the edge: unauthenticated calls return **401** where a nonsense path returns **404**).

### Four things the build taught

**1. `events` has NO user INSERT policy.** Ingestion is a system write, so the human path's
transactional emit failed RLS on the first run — caught by the test, not by reading. The fix is
`coop_emit_contribution`: the narrow sibling of `coop_ingest_event`, differing in that the event
belongs to **the group the work belongs to** (so the group sees it and the Tier-2 lane shards by
it) rather than the sender's personal group, and it **refuses a caller who is not a member of that
group**. It is also itself idempotent on `(source, source_event_id)` via `events_dedup_idx`.

**2. A signature class was missing.** A member logging their own hours is a **`member`**: not a
witness (`role-holder`), not a machine (`scoped-key`), not the group (`group-vote`). Self-assertion
was not one of the three classes §3.2 named. Added, with an idempotent `ALTER TABLE ... DROP
CONSTRAINT IF EXISTS / ADD CONSTRAINT` migration, since `CREATE TABLE IF NOT EXISTS` could never
have added it.

**3. `basis` was computed as "anything that is not a `scoped-key`".** The moment `member` existed,
that rule would have promoted **a peer's own account of the work to `attested`** — an independent
attestation that isn't one. It is now an explicit allowlist, defined once:

> `isAttestingClass(cls)` — **`role-holder` | `group-vote` attest. `scoped-key` and `member` do
> not.** A machine observation and the person speaking about themselves are both *claims*.

**4. The DDL and SEED are template literals; a backtick in a comment CLOSES them.** One backtick in
a new comment broke `db.ts` with `TS1005` — the module would not parse. The DDL extractor's own
guard (it refuses a DDL containing a backtick) caught it before the server restarted onto it. The
lesson is narrower than "avoid backticks": **do not discard the output of the step you depend on**
— that guard had already reported the reason and I had piped it away.

### Honest limits of this step

1. **`sig` is a SESSION MARKER, not a signature over the body** — a hash of the bearer token. It
   attributes an entry to a session; it does not prove the contents. Verifiable signatures
   (EIP-191 over `tier2EntryBody`, which already emits a canonical form) are the follow-on, and
   nothing Tier-1-eligible rests on the weaker version because the basis is `machine-only`.
2. **Validity-at-signature-time needs grant HISTORY, which does not exist.** Roles are current
   state, so the system cannot yet answer *"did this person hold `tier2.attest` when they signed?"*
   The signature records `valid_from`/`valid_to`, so the data is there; the check is not. Until
   then a revoked role cannot be distinguished from one that never existed.
3. **The attestation TIMER — `proposed → notify → wait → expired` — is not built.** Attestation is
   manual. That wait is the Temporal workflow §5.6 anticipated, and it is the next piece.

## 6. The state machine — and `basis` is not a state

```
                          ┌──────────────► rejected      (counter-party refused; a signal, kept)
                          │
proposed ──countersign──► countersigned ──ratify──► ratified ──► superseded   (by a correction)
   │                          │
   └──timeout──► expired      └── T1 eligibility: basis = attested | machine-only
```

- `proposed` → `countersigned` on collecting the required signatures.
- `countersigned` → `ratified` **automatically** for routine kinds, or **by vote** for kinds whose policy
  requires it (`dues_status`, disputes, anything above a value threshold).
- `rejected` and a bare **refusal** are both recorded — never a silent absence
  (`custody-chain-and-contest-kit.md` §7.3).
- `superseded` is reached **only** by a `correction` entry that `refs` the original. **Entries are never
  edited and never deleted.**

**`basis` is a *property*, not a state** — and conflating them is the easy mistake:

> An entry can be `countersigned` **and** `machine-only` at the same time. `machine-only` means every
> signature came from a scoped key. It is **visible and usable for display**, but it must never affect a
> Tier-1 outcome until a role holder or a vote touches it.

(That is the §3.2 rule "distributions read ratified entries only" made concrete.)

## 7. Write-time invariants (the ones worth enforcing hard)

1. **`prev` must equal the current head of the group's chain**, and `seq` must be `head + 1`. Enforce by
   **serialising writes per group** — a group's chain is single-writer-at-a-time, which is cheap because
   groups are small. A losing writer gets a conflict, not a fork.
2. **`idempotency_key` unique per group** — a retried submit must not double-log an hour.
3. **Every signature's authority was valid at its `signed_at`.**
4. **The counter-signer is not the beneficiary** — unless a `vote` signature is present.
5. **The threshold applied is recorded on the entry** (`threshold` jsonb), not re-derived at read time.
   **Policy changes must not retroactively re-judge old entries.**
6. **Only `ratified` entries may be read by a T1 process.**
7. **A `late` entry beyond the configured window needs a higher threshold** than a same-period one.
8. **A `correction` cannot alter the target** — it only adds, and the target moves to `superseded`.

## 8. The T1 bridge — and the one field that makes it auditable

When a distribution runs:

1. It selects **`ratified`** entries for the period window, for the kinds that affect T1.
2. It computes the entitlement table from them.
3. It executes the **Tier-1** distribution (on-chain, shielded).
4. **The Tier-1 event records the Merkle root of exactly the T2 entry set it consumed** (`input_root`).

That last step is the important one:

> **The T1 event commits to the T2 input root.** So later, anyone can prove that *this* distribution was
> computed from *those* records — and a distribution cannot silently use a different set than the one it
> claims.

Without it, the T1/T2 boundary is where auditability quietly dies. With it, the whole path is checkable
end to end: entries → period root → anchored root → distribution's `input_root`.

## 9. Open questions (for Robbie, and they are small)

1. **Unit vocabulary** — is `unit` a fixed platform list (`hours`, `items`, `kg`) or free text per group?
   Fixed is queryable across groups; free text is more honest to how groups actually count things.
2. **Threshold policy: platform defaults + per-group overrides** (the `config` axis of a shape), or
   per-group from scratch? The shape system argues for defaults-with-overrides.
3. **Are `machine-only` entries visible to all members?** Instinct: **yes** — hide nothing *within* a
   group; the restriction is on T1 eligibility, not on visibility.
4. **Leaf retention** — keep detail forever, or keep roots permanently and let groups agree to prune leaf
   detail (`sharded-ledgers-and-anchors.md` §6.5)?
5. **The `dues_policy` preview is not a simple query — it is PROOF AGGREGATION.** To say
   "34 satisfied by money, 4 by participation" the preview must touch all three tiers **at once** while
   still hiding which mode each member used (§5.1). A read over records cannot do that; it has to be a
   **count over proofs**. Flagged as an open BUILD question (2026-09-13), not yet designed.
6. ~~Does `dues_status` belong in T2 at all?~~ **ANSWERED 2026-09-13 (Robbie): no — dues has multiple
   modes beyond money (participation, stewardship, in-kind, coverage, waiver), so it is a *projection
   across tiers* under a group-set policy, and the status is revealed as a proof that hides the mode.**
   See §5.1. **Waiver: DECIDED 2026-09-13 (Robbie) — a vote OR a role may grant one**, both paths
   legitimate (§5.2). *Remaining:* how `dues_policy` mode weights are expressed.

## 10. Build order within Tier 2

| Step | What | Depends on |
|---|---|---|
| 1 | The two tables + the per-group serialised append (invariants 1–2) — **BUILT** | nothing |
| 2 | The signature/authority layer (invariant 3) — the same layer the custody chain needs | the grant matrix (seats/roles/grants already designed) |
| 3 | Period trees + the shared `anchor` record (`sharded-ledgers-and-anchors.md` §5) — **BUILT** | nothing blocking; anchors are cheap on any live chain |
| 4 | The state machine + thresholds (invariants 5, 7) | steps 1–2 |
| 5 | The T1 bridge with `input_root` | step 3, and the treasury when it exists |

**Steps 1–4 need no treasury contract and no chain switch.** That is the whole reason Tier 2 is step 1 of
the money work.
