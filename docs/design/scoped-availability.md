# Scoped availability — a member's time, disclosed by audience

Status: design · 2026-10-04 · Robbie + Hermes. **Proof-first** (decision 5).
Answers the open question in `group-app-integrations.md` §5 ("group-aware availability: a group can
see *when* someone is free without seeing *what* they are doing") and its cross-cutting note that
"the privacy dial … is a cross-cutting concern, not per-app."
Composes with: `caldiy-scheduling-and-paid-bookings.md` (the scheduler is a **consumer** of this, never
its owner) · `p2-build-plan.md` (the circuit family + the `contribution` predicate this follows) ·
`contracts/zk/README.md` + `groth16-ceremony.md` (the key is a ceremony article) · `money-in-and-out.md`
§3.2/§3.3 (counter-signature classes; off-chain data, anchored commitment) · `sharded-ledgers-and-anchors.md`
§5 (one anchor stream) · `account-and-key-model.md` (§ zk-badges) · `adversary-models-and-sector-fit.md`
(availability is **not** a cryptographic property) · `coop-work-signup-checkoff.md` (availability is not
work done).

## 0. The goal, restated as one rule

Three things must be separated, because conflating them is exactly where the privacy breaks:

1. **Budget** — "3 hours a week for civic engagement". A **number**.
2. **Slots** — "Thursday 18:00–21:00". The **sensitive** part.
3. **The rest of the calendar** — **never** disclosed, not even as free/busy.

> **The rule: a scope sees its own slots; the world sees a count; nobody sees the calendar.**

## 1. The model

Availability is the member's **own declaration**, partitioned by scope:

| Scope | Who sees it | Example budget |
|---|---|---|
| `open` | any group the member is in, **and the public web** (unauthenticated) — decision 3 | 1 h/wk |
| `group:<uuid>` | that group's members | 1 h/wk — food coop |
| `sector:<key>` | members of the groups tagged with that sector | 3 h/wk — civic engagement |
| `self` | nobody but the member | 3 h/wk — their own enterprise |

Per scope: a **budget** (hours per period, a **soft target** — decision 4) and **slots** (recurring
windows) at a chosen **granularity** (§4).

### Sector is a *tag* with visible provenance (decision 1)

`sector` is a **tag on groups**, not a first-class shape axis. A group can carry several. The audience
for `sector:<key>` = the members of the groups carrying that tag. Two levels, and **the level must be
visible** wherever the tag is shown:

| Level | Who set it | What it means |
|---|---|---|
| `self-declared` | a group seat holding the role | a label the group chose. Anyone can claim it |
| **`attested`** | the **irl.coop group** counter-signed it | a claim with an authority behind it |

The attestation is the same object as everywhere else in the stack — a counter-signature from an
authority the coop conferred (a role holder, a scoped key, or the group acting by quorum:
`money-in-and-out.md` §3.2). It matters because **a self-declared sector tag is unverifiable by
construction**, and the moment sector membership unlocks an audience it becomes a forgery surface.
Show the distinction; never render an unattested tag as if it were attested.

## 2. Why not in cal.diy (the honest bit)

cal.diy / Cal.com models availability as a schedule attached to a user, and a booking link reveals
free/busy to **anyone holding the link**. There is no scope, no count-only disclosure, no per-audience
dial — and the fork has **no teams**, so a group page cannot be a team page either.

A scheduler therefore *cannot* be the source of truth here: by construction it would leak the calendar
to the public link. **cal.diy stays a booking surface; the availability record lives in coop-api.**
This strengthens `caldiy-scheduling-and-paid-bookings.md` §2 option C — a group's page is a projection
in our dashboard over figures the coop already owns.

## 3. Disclosure is a projection, computed server-side

- **Stored**: the member's declarations, RLS-scoped to them (`app.sub`), FORCE RLS like every other
  table.
- **Read by an audience**: `SECURITY DEFINER` projections — the stack's standing rule, because a
  system caller has no RLS identity and every cross-cutting read is a definer function (the shape of
  `coop_group_member_subs`):
  - `coop_availability_for_group(g)` → that group's own scope, plus `open`, plus `sector` slots of its
    members;
  - `coop_availability_for_member_public(ref)` → the **anonymous** view (§3.1).
- **Never filter a viewer's slice in the client.** The slice is decided in the database, not in a
  React component.

### 3.1 The public, unauthenticated view (decision 3)

`open` reaches **the public web** — a non-signed-in visitor on the member's own site. So there is an
anonymous read path, and it must be safe *by construction* rather than by policy:

| Property | Why |
|---|---|
| Keyed by the member's **public ref** (their slug), never an id you can enumerate | otherwise "who is available?" becomes a scrape |
| **Never** serves an individual's slots below their chosen granularity — for a public caller that means **count only**, or `bucket` at most | the audience with no relationship gets the least |
| No listing endpoint | no "all members with availability" query exists at all |
| Rate-limited + cacheable at the edge | it is a public page view, not an API for the world |
| Carries no PII beyond the member's already-public identity | the world-doc projection rule: publish the projection, never the record |
| Presents the budget as a **declaration** ("declares ~3 h/wk"), not a guarantee | decision 4 — it is a soft target |

The member controls per scope whether `open` is visible to the public at all: **anonymous visibility is
opt-in, and the default is off.**

## 4. Granularity — the dial that actually protects

Publishing "I'm free Thu 18:00–21:00" also says *"and not the rest of the week"* — **the complement
leaks.** So granularity is a per-scope choice:

| Granularity | Discloses | Who gets it |
|---|---|---|
| **count** | "3 h this week" | the public / world view — **always** |
| **bucket** | "weekday evenings" | **the default** for group + sector audiences |
| **exact** | "Thu 18:00–21:00" | **opt-in only**, by the member, per scope |

**Recommended defaults (decision 2 — his call, my recommendation):**

- the **budget is always shown as a count** inside its scope;
- **slots default to `bucket`** for group and sector audiences, because a count alone cannot serve
  "my groups can see *when* I'm available to the group" — bucket is the minimum that does;
- **`exact` is opt-in per scope**, and it is what a *self-serve* booking page needs;
- **the public/anonymous view never gets below count**;
- **disclosure only goes up by explicit choice.** A member opts *up*; nothing ever opts them down, and
  no default is ever the most revealing one.

The booking tension this resolves: publishing exact slots is not required for booking. Publish buckets,
and let a **booking request** resolve to an exact slot when the member accepts it — the exact time
becomes visible bilaterally, at the moment it is needed. Turn `exact` on per scope only where a
self-serve booking page is wanted.

## 5. Availability is a declaration, not a record (the guard)

Slots are forward-looking **offers** the member owns, scoped to one audience, and **revocable at
will**. This is why it does not contradict `coop-work-signup-checkoff.md` rule 4 ("a tracker emits
shift totals, never raw intervals"): that rule forbids recording what a person **did**; this records
what a person **offers**. Keep the two apart — never write a completed shift back as an availability
slot, and never treat declared availability as work done.

**And because the budget is a soft target (decision 4):**

- it is a statement of intent, **not a rail** — nothing refuses a booking for exceeding it;
- the surface shows the delta honestly ("declared 3 h · 4 h booked this week"), rather than implying a
  promise;
- **no obligation may rest on it.** Obligations live in the dues/obligation modes, not here. A soft
  target that gates anything has become a hard cap with worse manners.

## 6. The proof — planned first, because it shapes the data (decision 5)

The proof is **not an add-on at the end**. Its requirements decide how the record is written on day
one, because retrofitting them is a migration over a per-member history.

### 6.1 What is proven

> **"This member declared ≥ N hours of availability to scope S in period P"** — verifiable without
> revealing a single slot.

Public inputs: `period`, `scope_key`, `N` (minutes), `root`. Private witness: the member's own
availability entries for that scope and period, their Merkle path, and the sum. That is the **same
shape as the family's `contribution` circuit** already named in `p2-build-plan.md` ("contributed ≥ N
hours … without the ledger", public inputs `N` + tree root). So this is a **new instance of a proven
shape**, not a novel circuit — and the toolchain work (circom → setup → prove → verify on
`/mnt/storage/zk`) is already done: the P2 gate is closed and a real spend proof verifies against a
ceremony key.

### 6.2 The record must be built to be provable

| Requirement | Why it must be now |
|---|---|
| Entries are **hash-chained** per member (own table — *not* `tier2_entry`, see §5) | the chain is what makes the committed history tamper-evident |
| **Member-level trees**, batched into one family root per period | a per-member on-chain anchor would be one write per member per period; member trees + a single batched family root keeps it one anchor per period (`sharded-ledgers-and-anchors.md` §5) |
| An `anchors` row per period with `family = 'availability'`, `scope_id = <member sub>` | the substrate exists (`apps/coop-api/src/db.ts`: `family / group_id / scope_id / period / root / leaf_count / chain / tx_hash`, `UNIQUE(family, scope_id, period)`); it needs **one CHECK widening** |
| `quantity` in minutes + the scope key + the period, as first-class columns | they are the circuit's public inputs — a proof over re-derived data is a proof of nothing |
| The scope key is in the leaf | otherwise a member could prove a civic-engagement claim against a food-coop record |

### 6.3 What the proof costs, honestly

- **One more circuit + one more key.** Per the 2026-09-29 "one key per pool" decision, each new
  *circuit* gets its own key — and a Groth16 proving key is a **trusted-setup article that must not be
  rebuilt or rotated casually** (`contracts/zk/README.md`). So this is a **ceremony**
  (`groth16-ceremony.md`, the single-operator launch tier with the member attestation rotation path),
  not a build step.
- Artifacts live in `/mnt/storage/zk/keys/` — **never** in `infra/out/` (the generator `rmtree`s it).
- Bring-up **checks** the key exists and reports `key missing — run the one-time ceremony`; it must
  never rebuild one, because a new key invalidates every proof already issued.
- Plus: the verifier, a registry entry for the public verifier key, and the off-chain verify path
  (snarkjs verify + anchor cross-check, the pattern the treasury relayer already uses).
- Proving runs **on the member's device** where possible (the family's pathway A: a parameterized
  witness app + a local prover, with the coop anchoring the result).

### 6.4 The honest limit — and what makes the claim worth anything

A proof over self-declared availability proves **the commitment, not the truth**. A member can declare
40 hours and prove it perfectly. Availability is not a cryptographic property
(`adversary-models-and-sector-fit.md`), and no circuit changes that.

So the proof is only half the claim. The other half is **attestation**, and that is where decision 1
lands: an **attested** sector tag, or a counter-signature on the availability commitment itself (a role
holder, a scoped key, or a group vote — §3.2's three classes), is what turns "committed" into
"witnessed". **Prefer the surface to say which one it is:** *"declared ≥3 h/wk · attested by irl.coop"*
is a different sentence from *"declared ≥3 h/wk"*, and the design should never blur them.

### 6.5 Tiers, for the record

| Tier | Claim | State |
|---|---|---|
| **0** | scoped projections: a group sees its slots, the world sees counts | **buildable now** — a coop-api resource + RLS + definer projections |
| **1** | the count is **verifiable** (§6.1–6.3) | **planned first** — new instance of the proven `contribution` shape; needs the widening, the circuit, and one ceremony |
| **2** | **overlap proofs** — "we can meet" without either party revealing slots | **research.** Private-set-intersection over time intervals. **Do not promise it in product copy** |

## 7. Sequencing

1. **The record, built for the proof** — `availability_entry` (hash-chained, member-scoped), the scope
   key + period + minutes columns, the `anchors` family widening, RLS, and the two projections
   (group + public). Slice 0 behaviour is already delivered here; nothing is wasted on the proof path.
2. **The dashboard surface** — "my availability": declare budgets and slots per scope, choose
   granularity, opt into public visibility; and the group/public views that read the projections.
3. **The ceremony + circuit** — the `availability` predicate, its key, the verifier, the registry
   entry, and the member-side prover; the surface then shows *verified* alongside the count.
4. **Attestation** — the irl.coop group's attestation of sector tags (and optionally of an
   availability commitment), reusing the §3.2 counter-signature layer.
5. **Booking consumes it** — a booking drawn against a scope (`caldiy-scheduling-and-paid-bookings.md`).

## 8. Decisions — recorded

| # | Decision | Answer |
|---|---|---|
| 1 | Sector: first-class axis or tag? | **Tag on groups**, optionally **attested by the irl.coop group** — provenance must be visible (§1) |
| 2 | Default granularity | **count for the public view; `bucket` for group + sector; `exact` opt-in only** — recommended, flagged for his nod (§4) |
| 3 | What `open` means | **any group the member is in, *or* anyone at all — including non-signed-in visitors** on their public site (§3.1) |
| 4 | Budget: hard cap or soft target? | **Soft target** — no gate, show the delta, no obligation rests on it (§5) |
| 5 | Sequence | **Plan around the proof** — structure the record for it now (§6) |

## 9. Where this generalizes — the four shared-scheduling cases

**The honest frame: availability is one leg of three.** Every shared-scheduling case is:

1. **Supply** — who (or what) can, when. This doc.
2. **Demand + match** — what needs filling, and the routing. The `match.*` events are *designed*
   (`event-bus-and-group-shapes.md`); the needs/offers board is a **mockup with no table**, so it does
   not yet save. This is the missing middle.
3. **The commitment** — once matched, the promise. **Already spec'd**:
   `declared-binding-registry.md` (finalized 2026-09-29) — one table, authority classes
   `role`/`key`/`vote` matched to stakes, bilateral consent wherever a binding confers control,
   per-group roots, append-and-revoke. A filled shift, a booked resource and a matched ride are all
   *declared bindings*; no new mechanism is needed for the lock.

Plus **fulfilment** — the checkoff into the Tier-2 ledger (`coop-work-signup-checkoff.md`).

| Case | Supply leg | What is missing | Status |
|---|---|---|---|
| **Asset distribution** (tool library, depot pickup, box packing) | works for the *person* side — "I can staff Sat 9–12" | the **thing** side: inventory + a checkout/reservation/return **state machine** | 🆕 **not designed** — named as a gap in `group-shape-scenarios.md` |
| **Staffing / volunteers** | the case this design was aimed at | a **shift spec** (the demand object) and a **coverage floor** — "3 on duty" constrains the *aggregate*, not one person's predicate | 🆕 **partial** — "Plane has cycles/issues but not a coverage-guaranteed rotation" |
| **Ride-sharing** | availability ∩ geography (corridor + window) | bilateral **overlap matching**, and where a corridor is disclosed | **undesigned** — no doc; the overlap proof is §6.5 tier 2 |
| **Anything else shared** | — | a slot inventory + who can fill it + what is disclosed to whom + a commitment + a fulfilment record | the recurring shape |

### 9.1 Asset distribution — the subject is not always a person

The person side is ours already. The gap is the resource side, and **one generalization closes it**:
let the **subject** of an availability declaration be a **member *or* a resource** — a van, a tool, a
room, a depot window, a church hall. Then a *reservation* is simply a binding between a person and a
resource slot, and it inherits everything: the same scope rules, the same granularity dial, the same
anchoring, the same proofs. Without this, assets need a parallel model; with it, they are one column.

**The resource side now has a model: `resource-model.md`** — identity plus axes (location kind,
engagement mode, contention, custodian, obligations, provenance, disclosure), with each of tools, land,
structures, maintenance and routes placed on it.

Two things the tool-library scenario adds that are *not* scheduling and must not be smuggled into it:
**storage as a contribution** (providing space counts like labour — the Tier-2 ledger's job), and
**maintenance as a child group** (rights-set relationship, own Safe and budget).

### 9.2 Staffing — availability alone cannot run a roster

Two additions, both recorded gaps rather than new inventions:

- **The shift spec** is the demand object: 2 people, 3 h, Sat 09:00–12:00, needs a food-safety cert.
  Filling it consumes availability, then creates a binding.
- **The coverage floor** — "3 on duty" is a constraint on the *set*, not a per-person predicate. A
  matcher must satisfy a floor, and a plain signup cannot: this is why the capability table calls
  rotation "partial".
- **Constraints** (skill, cert, vehicle) are *disclosed attributes* on a declaration, so a matcher can
  filter without seeing the calendar. The family already has the shape for proving them later — the
  `credential` circuit ("holds role + expiry without the identity").

And the fairness leg is already designed: the Tier-2 time-bank ("you watch → you get time"). **Signup
is not fairness**; the ledger closes that loop, not the calendar.

### 9.3 Ride-sharing — where the proof actually earns its place

Undesigned, and structurally the hardest of the four, because the match is **bilateral**: a driver's
corridor + window must overlap a rider's. That is precisely the **overlap proof** (§6.5 tier 2) — so
rides are the strongest argument for that research, and the reason not to promise it.

The privacy primitive for it, though, **already exists in the family**: the `geolocation` circuit —
*"in region R at time T without the exact coordinate"* — is exactly what a corridor needs, so a driver
can prove they pass nearby without publishing where they live. A ride also carries a binding (the
driver commits) and often a payment (the rail).

### 9.4 What generalizes unchanged — and is the real contribution here

The **disclosure model**, more than the availability record. Every case leaks in the same shape: a
roster reveals who is free; a corridor reveals where someone lives; a checkout log reveals habits; a
volunteer history reveals availability as a surveillance surface. So *scope + granularity +
never-the-complement + computed server-side* is the reusable part — and it applies whether the subject
is a person or a thing.

### 9.5 The one change this forces on slice ①, now

Nothing above pulls slice ① forward. It does mean the record must carry **`subject_kind` / `subject_ref`
from day one** — member today, resource later. A nullable column now, versus a migration over a
per-member history later.

## 10. Do not

- **Do not assume the subject is only a person** — a resource declares availability too (§9.1).
- **Do not store availability in the scheduler.** It leaks by design.
- **Do not filter a viewer's slice in the client.**
- **Do not let availability become a record of work done** (§5).
- **Do not default to exact-slot granularity**, and never give the anonymous view below a count (§4).
- **Do not render a self-declared sector tag as attested** (§1).
- **Do not let the soft target gate anything** (§5).
- **Do not rebuild the proving key** — a new key invalidates every proof already issued (§6.3).
- **Do not promise overlap proofs** (§6.5).

## Cross-references

- `group-app-integrations.md` §5 — the recorded intent this specifies.
- `caldiy-scheduling-and-paid-bookings.md` — the booking surface; why the scheduler is a consumer.
- `p2-build-plan.md` — the circuit family, the `contribution` predicate, the member-authorable
  pathway; `contracts/zk/README.md` — one key per pool, keys are ceremony articles;
  `groth16-ceremony.md` — the ceremony's launch tier.
- `money-in-and-out.md` §3.2 (the three counter-signature classes) / §3.3 (off-chain data, anchored
  commitment).
- `sharded-ledgers-and-anchors.md` §5 — the single anchor stream this family joins.
- `account-and-key-model.md` (§ zk-badges) · `needs-offers-matching.md` (availability as a matching
  dimension) · `adversary-models-and-sector-fit.md` (the honest limit).