# Needs & Offers Matching — multi-party trade chains with expediting

Status: design · Sep 2026 · Builds on event-bus-and-group-shapes.md (§2.3 the
offers/asks matcher named as a future event source; §3.4 child relationships;
§4 provisioning), account-and-key-model.md (§"Worked example — farm coalition" for
relationship-scoped mutual credit; §"Group relationships & reserved powers" for the
relationship-edge vocabulary; §"zk-badges" for the trust floor), private-treasury-
guards-ledgers.md (guard enforcement points; project sub-scopes; the chargeback/
settlement pattern), regenerative-vision-note.md (the regenerative score),
world-doc-and-contacts.md + world-doc-virtual-workspace.md (projection, never a
store of record), infra-management-monitoring.md (§"declared vs running" reconciler),
published-items-as-groups.md (the promote-to-group ceremony — the heavy path this
spec deliberately does NOT take).

## 0. The model in one paragraph

A member or group posts a **need** ("we need X") or an **offer** ("we have surplus
Y") as a small, disclosed record bound to their group. A **matching service** reads
the disclosed needs/offers and finds **cycles** — not just A↔B pairs but A→B→C→…→A,
where every leg is a real give/get. A matched cycle becomes a **trade chain**: a
short-lived, self-governing arrangement that records the *declared* commitment of
each leg (who owes what to whom), tracks the *actual* status of each leg as events
arrive, and surfaces *drift* (stuck legs) to an **expediting** workflow that nudges
and, failing that, escalates to arbitration. Each leg settles through the existing
**relationship-scoped mutual-credit ledger** — no new money primitive. The chain is
a **projection over events + resource_scopes**, never a new group or a new store of
record, and it can outlive any single member because the commitments, the state, and
the arbitration path all live on the bus and the registry, not in any one person's
head.

## 1. Principles (new — settled ones are referenced, not restated)

1. **A trade is a projection, not a group.** Unlike a published item (which owns a
   file, seats, proceeds, and supply — a full group), a trade chain owns nothing and
   governs nothing. It is a *derived arrangement* over events + resource_scopes,
   rebuildable and droppable, exactly like the world-doc is over its stores of record.
2. **Posting is disclosure consent.** A need/offer is only ever matched from the
   *disclosed* index. The matcher reads what members chose to post — it never reaches
   into a hidden group's internal state (hidden is the norm, §settled).
3. **The chain is the confirmation line, not a new ledger.** The relationship-scoped
   mutual-credit ledger already settles a bilateral give/get (§farm coalition). A
   multi-leg chain *reuses* that per-edge — it does not mint a chain-wide balance.
4. **Declared / actual / drift — the infra reconciler's shape, not a new state idiom.**
   The chain's commitments are `declared`; leg events are `actual`; the gap is `drift`.
   No new state-machine vocabulary beyond those three words.
5. **Lend, don't give.** A chain is an exchange of surplus, not a gift — every leg
   carries a reciprocal obligation, and a broken leg is a *dispute*, not a write-off.
6. **Reputation gates entry, never worth.** The trust floor to propose/join a chain is
   a zk-badge predicate over *completion* history, low and minimal-disclosure — it
   proves reliability, not that anyone is owed anything.

## 2. What is a posted need/offer?

**A `resource_scopes` row — not a group, not a project.** Concretely:

- `resource_scopes`: `app = "needs"`, `resource_key = <need_id>`, `scoped_by = sub`
  (or the group Safe), plus a `kind` (need/offer), a free-text `title`/`description`,
  a `category` (produce, space, labor, tools, transport…), and a `visibility` tier
  that mirrors the group privacy tiers (open / members / hidden).
- The need/offer itself is **bound to a group** (the poster's group Safe is the
  counterparty identity), but it is *not* a group of its own.

Why not a group: a published item is a group because it has ownership, proceeds,
supply, and governance that must persist. A need/offer has none of those — it is a
one-line "I have X / I want Y" that dies when fulfilled or withdrawn. Making it a
group would be the "seed becomes a cage" failure mode this stack explicitly avoids.
It is closer to a **Plane issue** than to a published item: a lightweight, scoped,
post-and-close record.

The **chain** (the matched cycle) is even lighter: it is a `resource_scopes` row
(`app = "trade-chain"`, `resource_key = <chain_id>`) + a stream of events + a
projection. **Promotion to a child group is a possible, out-of-scope future** — if a
triangle turns into an ongoing standing arrangement, it *could* be promoted via the
existing child-relationship ceremony, but v0 never does this.

## 3. Cycle discovery — server-side index vs zk matching

Two candidate shapes, with a real privacy cost each way:

- **Server-side matching** — a service holds the disclosed index and runs cycle
  detection (a graph search for directed cycles across need/offer edges). Fast,
  simple, and it can rank matches by the regenerative score and graph distance. The
  cost: the matcher sees *every disclosed need/offer*, which, if a hidden group posts
  a need, leaks "this hidden group has surplus X." Mitigated only by the fact that
  **posting is itself a disclosure act** (§1.2) — but the correlation is still real.
- **zk / private-set-intersection matching** — a member proves "I hold an offer that
  completes a cycle with your need" without revealing the offer's contents to
  unmatched parties (or to the matcher). Consistent with "hidden is the norm," but
  materially harder: it needs a matching protocol (PSI or a zk circuit over the
  index), and it cannot *rank* matches without more disclosure.

**Decision: both, phased.** v0 is **server-side over the disclosed index** — posting
is explicit disclosure consent, the trust floor gates who may post, and the index is
scoped per visibility tier. The zk path is **v1**, reserved for *hidden-tier* needs
that must match without disclosure; it plugs in as a second matching source behind the
same `match.*` event namespace, so the rest of the design does not change. The two
coexist because a need carries a `visibility` field: `open`/`members` needs are matched
server-side; `hidden` needs wait for the zk matcher.

## 4. Chain state as a reconciler (declared / actual / drift)

Reuse the infra reconciler's exact three-way shape (§infra-management-monitoring):

- **Declared** — the agreed chain. An ordered set of legs `L1..Ln` forming a cycle;
  each leg declares `from`, `to`, `what`, and the agreed terms. Stored as a
  `resource_scopes` row + a hash-anchored commitment list (the "tree" of a trade).
- **Actual** — the live status of each leg, reported as events: `proposed`,
  `confirmed`, `in_transit`, `received`, `settled`, or `disputed`. Actual is the
  "docker ps" of the trade — observed, not assumed.
- **Drift** — any leg where actual lags declared: a leg that is `confirmed` but not
  `in_transit` past its window, or `in_transit` but not `received`, or `disputed`.
  Drift is *computed*, never stored — the reconciler compares declared vs actual and
  emits `trade.stuck` for each drifting leg.

This is deliberately the same shape as the stack reconciler: declared is the source of
truth, actual is observation, drift is the actionable gap. No new state machine —
three words, one comparison.

## 5. Expediting & logistics as bus events

The matcher and the chain both emit into the existing event namespace (the §2.3
`match.*` source, widened — zero bus changes, the point of that section):

| event | meaning | emitted by |
|---|---|---|
| `trade.proposed` | a cycle was detected and proposed to its parties | matcher |
| `trade.leg_confirmed` | a party accepted a leg's terms | the party |
| `trade.leg_received` | a party confirms receipt of a leg | the party |
| `trade.shipped` / `trade.in_transit` | logistics: the good moved | the party / courier hook |
| `trade.stuck` | a leg drifted past its window | the reconciler |
| `trade.disputed` | a party disputes a leg | the party |
| `trade.settled` | a leg's mutual-credit entry was written | the ledger |
| `trade.closed` | the whole cycle settled (or was dissolved) | the reconciler |

**The shepherding workflow (Temporal)** is one workflow per chain, consuming these
events and running durable timers — the same "a workflow is just another channel"
pattern (§event-bus). On a leg's deadline with no `leg_received`: **timeout → nudge**
(notify both parties of the stuck leg, `trade.stuck`) → after N nudges →
**escalate** (`trade.disputed` → ArbitrationModule, §7). The workflow holds no
authority — it only *watches and prompts*; settlement and arbitration re-validate
through the guard/ledger as always.

## 6. Reputation gate (zk-badge predicate)

Mirror the quest-board trust floor (§account-and-key-model §"zk-badges" — "≥3
completed quests to post"). The gate to *propose or join a multi-party chain* is a
zk-badge predicate over completion history, minimal-disclosure:

- **v0 predicate:** `completed ≥ 1 bilateral trade` (any) AND `holds a seat in ≥ 1
  group`. Low floor, no class system — it just excludes fresh throwaway accounts.
- **Future predicates** (same mechanism, higher floor): `completed ≥ N multi-party
  legs`, `no disputed legs in the last K`, `member of some group ≥ 1 year`.

The badge is a (predicate, proof, public-inputs) tuple with decay, holder-bound, and
arbitrable — exactly the existing badge machinery. Enforcement is app-layer (coop-api
verifies and issues a scoped capability) for v0; the on-chain guard form is reserved
for high-value chains.

## 7. Arbitration — reuse, don't fork

A trade dispute is a *lighter* version of the chargeback grievance, not a new
mechanism. Same pieces:

- **Same ArbitrationModule** — the arbiter named at group formation, with the same
  timelock + appeal window + forced-ruling path.
- **Same investigator exclusion** — the arbiter's investigator is excluded by graph
  distance from the disputing parties (`dist(X, G) = K`, bounded K ∈ {1,2,3}), the
  identical mechanism as the chargeback flow (§treasury §settlement).
- **The lighter part:** the ruling is not a money reversal but a **forced leg
  settlement** — "leg L2 was fulfilled / not fulfilled," and the arbiter writes the
  outcome into the relationship-scoped ledger (debit the defaulter, credit the owed
  party). No escrow, no 130-day hold, because a trade leg is surplus, not fiat.

So: one ArbitrationModule, one exclusion rule, two dispute types (chargeback for
money, trade-leg for goods/credit) — the second is a smaller ruling over the same
rails.

## 8. Out of scope for v0 (small, like the treasury's phasing)

- **zk / PSI matching** (hidden-tier needs) — v1.
- **Escrow / value-in-flight** via treasury guards (hold leg 1's value until leg 3
  confirms) — v1, and only for high-value chains; see §4 of the settlement tradeoff.
- **On-chain guard enforcement** of trade state — v0 state is events + projection;
  the on-chain form is only for high-value chains.
- **Promotion of a chain to a child group** — out entirely; the standing-arrangement
  path is a separate design.
- **Federation / cross-domain matching** — parked, like all federation.
- **Real logistics integration** (couriers, tracking) — v0 ships *status events*; the
  courier hooks are an activity interface, not a carrier integration.
- **Automatic settlement** — v0 legs settle when parties confirm + the ledger entry is
  written; standing-order auto-settlement is the treasury keeper's job, not the chain's.

## 9. The shape of a need — physical / remote / financial

A need is not one kind of thing; it has a **shape** that changes everything
downstream. Three shapes, mirroring what the resource is bound to:

| shape | bound to | matches on | graph |
|---|---|---|---|
| **physical** (compost, storage, transport) | a place | semantic + literal distance | range ring |
| **remote** (coaching, VA, marketing) | a skill / deliverable | semantic only | no location |
| **financial** (funding) | a project / group | vertical + purpose | coin |

Location is a **constraint on the physical shape**, not a universal field. Shape
is selected at post time (the "class selection" of the wizard) and drives the
form, the matcher, and the graph encoding (color = shape).

The load-bearing consequence: **physical and remote needs participate in cycles
(give/get); financial needs do not.** A funding ask is a one-way flow — it uses
`sponsored-by` (not `matched-by`) and routes to the vertical funds, whose
priority is *computed, not declared*. A funding node never tries to close a
loop; it seeks a sponsor.

## 10. Coverage — partial matches, surplus, shortfall

A match is a **degree**, not a boolean. A posting carries `quantity` + `unit` +
a `flexible` flag / tolerance, and the matcher computes **coverage**:

- offer ≥ need → covered, with a **surplus** (40 kg vs 20 kg → 100%, +20 spare);
- offer < need → **partial**, with a **shortfall** (20 vs 40 → 50%, −20 short).

Both are surfaced with their coverage, never discarded. The `flexible` flag gates
whether partials surface at all — default is **exact** (only exact/fully-covered
matches), `flexible` opts into "open to partial / will negotiate". Same instinct
as privacy-by-default: don't surface ambiguity to parties who didn't ask for it.

A partial match enters a **`negotiating` leg state** between `proposed` and
`confirmed`: the parties converse to agree the actual quantity and timing, and the
*negotiated* quantity becomes the leg's **declared** state. The conversation is a
scoped thread on the proposal (a per-chain Matrix DM is the escalation), never a
new group, never a standing room.

## 11. Satisfaction — fitness for purpose

Coverage answers "is the amount there?"; **satisfaction** answers "does it
actually work for them?" — condition, timing, fit, quality. A need can be 100%
covered and 0% satisfied: "dry cold room" vs "humid shed" are both storage, same
quantity, wrong thing.

Satisfaction has two sides:

- **At match time** — richer posting attributes (condition, timeframe, hard
  requirements) plus the semantic vectors; the RAG embeddings rank *fit*, not
  just *availability*. This is where the vector-informed graph earns its keep.
- **After settle** — the parties' actual satisfaction is a signal feeding the
  match-quality badge's `false_match_rate` (a closed match that didn't satisfy
  *is* a false match — see match-proposing.md §7).

Satisfaction is the axis that keeps the system honest: it's what the parties
themselves feel, and what separates a good weaver from a prolific one.

## 12. Fan-out / fan-in — matching is a flow, not cycles

Quantity makes surplus and shortfall *routable*:

- **Surplus** → one offer satisfies several needs (40 kg split across 20 + 15).
- **Shortfall** → one need is filled by several offers (20 + 20 = 40).

So the matcher is a **flow assignment** (offers fan out, needs fan in), not a set
of pairwise cycles. The AI's real job here is proposing the *split*: "this 40 kg
offer covers these two needs — 20 + 15, 5 spare."

## 13. The validated story — a loop is a plan, not a hypothesis

A geometric cycle (A→B→C→A) is a *candidate*, not a trade. It must graduate to a
**story**: each leg carries who-gives-what-how-much-when-plus-how, and a
contingency; the loop carries timing and dependencies. The story is a
**machine-checkable plan object** (rendered as a narrative for humans), not free
text — otherwise neither the AI nor the reconciler can use it.

The AI validates the story against concrete **gap types**: transport, timing,
quantity, contingency, availability, commitment. Validation is a state-machine
gate:

```
proposed → validating → confirmed → in-flight → settled
```

The loop cannot confirm until the story is gap-free; gaps stay visible as a
checklist until closed (by the parties, or by the AI proposing fills).

**The story *is* the declared state.** Drift detection is only meaningful against
a rich declared. "Declared: compost arrives by the 12th via the coop truck" →
actual "not arrived by the 14th" → drift, surfaced. Without the story, the
reconciler has nothing to reconcile.

This is the weave, steps 3–4, made explicit and machine-checkable: *determines
any missing gaps and seeks to fill them* + *establishes communication, protection
for the exchange, contingencies*.

## 14. Anonymized story logs — the Solutions library

A settled chain's story, **anonymized**, is logged to a story-log collection —
the "Solutions library" (§landing recipes: "anonymized stories of how a need got
met, together"). Two consumers:

- **Humans browse it** — "how did another coop meet a compost need?" A searchable
  knowledge surface, and the closest thing to a wiki of practice.
- **The AI draws on it** — past stories are precedents the validation step reasons
  over ("last time a compost leg had no transport, they used the coop truck").

This closes the loop of the whole design: **validation stories become the
knowledge for future validation.** Story logs are a RAG area (a knowledge area,
never a store of record) and inherit the visibility tiers — a story is
public / group / private like any knowledge area, so a hidden group's settlement
isn't broadcast.

## 15. The posting form — declare the minimum, infer the rest

§9 gives the dimensions (shape, type, temporality, urgency, location) but
implicitly treats them as fields a poster *declares*. They mostly shouldn't be.
The tension — too many fields and nobody posts, too few and matches are poor —
resolves with a division of labour, not a compromise:

- **Ask (2 things):** `what` (free text) + `shape` (the one genuine fork —
  physical / remote / financial). Every required field costs people who walk
  away; two is the floor.
- **Infer (the AI):** type, quantity, condition — extracted from the free text,
  the same extraction the RAG pipeline already performs. The 15-way type
  taxonomy *stays*, but as an internal prior for the matcher, not a declared
  field — a user should never classify their own need.
- **Default (the source):** temporality and urgency come from the work item the
  posting derives from (a Plane issue's due date, a Matrix thread's season);
  location comes from the group's registered place or the device. Urgency is
  unstable and subjective — it must not be a manual field.
- **Defer (later):** the story details (how, when, transport) surface at
  *match / validation* time, when a concrete leg needs them — never at post time.

**The posting is a derived view of work already in flight.** From a Plane issue
("we need 5 volunteers for the harvest on the 20th") or a Matrix message
("anyone have a truck this weekend?") the posting is *pre-seeded and confirmed*,
not filled in. The wizard is two steps — *"What do you have or need?"* (the AI
reads it) → *"What kind?"* (three shape cards) → done. Fewer fields up front
isn't less data; it's the same five dimensions captured by inference instead of
entry.

## Worked example — the surplus triangle

Three groups in the same region, each with a different surplus (the farm-coalition
cast, extended to a cycle):

- **Cold Storage Co-op (A)** — surplus cold-storage capacity; needs compost.
- **Market Garden Collective (B)** — surplus compost; needs seed.
- **Seed Cooperative (C)** — surplus seed; needs cold-storage for winter.

No pair can trade directly (A wants what C has, C wants what A has — a cycle, not a
pair).

1. **Propose.** Each posts an offer + a need into the disclosed index (A offers
   storage + needs compost; B offers compost + needs seed; C offers seed + needs
   storage). The matcher runs cycle detection and finds A→B→C→A, emits
   `trade.proposed`, and proposes the chain to all three.
2. **Confirm.** Each party sees their own leg(s) and confirms: A agrees to give B
   storage (L1), B agrees to give C compost (L2), C agrees to give A seed (L3).
   Three `trade.leg_confirmed` events. The chain's *declared* state is now the full
   cycle.
3. **Expedite.** L1 (storage) and L3 (seed) move: `trade.in_transit` → `trade.leg_received`.
   L2 (compost) is scheduled but hasn't moved.
4. **Leg 2 stalls.** B's compost window passes. The reconciler compares declared vs
   actual: L1 and L3 are `received`, L2 is still `confirmed`. **Drift on L2.** It
   emits `trade.stuck`, and the Temporal workflow nudges B (and C, who's waiting).
5. **Escalate.** After two nudges with no movement, the workflow emits
   `trade.disputed` → ArbitrationModule. The investigator (excluded by graph distance
   from B and C) rules L2 unfulfilled, and writes the forced settlement: B's
   relationship-scoped ledger is debited, C is credited.
6. **Settle.** L1 and L3 settle via their own mutual-credit edges (A↔B storage-for-credit,
   C↔A seed-for-credit). The chain emits `trade.closed`. A and C keep their goods; B's
   ledger carries the L2 shortfall to be made good — the chain *outlives* B's stall,
   because the commitments and the ruling live on the bus, not in any one member.

What this shows: the chain tracks *three* bilateral edges through one reconciler, a
stall on one leg surfaces as drift without blocking the other two from settling, and
the arbitration path is the same rails as a chargeback — just a lighter ruling.

## Open questions

1. **Matching rank.** When a cycle has multiple candidates (or a need sits in several
   cycles), what orders the proposals — regenerative score, graph distance, offer
   freshness? (Settled principle: sponsorship priority is *computed, not declared* —
   does matching rank follow the same rule, or is a chain small enough to just ask the
   parties?)
2. **Leg window default.** What's the deadline before a leg drifts — a per-chain
   setting, a per-category default, or both? Who sets it?
3. **Hidden-tier matching is a whole protocol.** Is PSI-based matching worth the build
   before the open/members tiers have real volume, or does v1 ship as "hidden needs
   simply don't auto-match (manual introduction only)" for a long time?
4. **Partial-cycle settlement.** If a 4-leg chain has 3 legs settled and 1 disputed,
   do the 3 settle immediately (yes in the example) or does the whole chain hold until
   the dispute resolves? The example assumes settle-as-you-go — is that right for
   value chains where leg 1's value depends on leg 4?
5. **The escrow line.** At what chain value does the per-edge-credit risk (§the
   settlement tradeoff) cross into needing treasury-guard escrow? Who decides — the
   parties, or a declared threshold?
6. **What survives the chain.** If a chain dissolves mid-flight (a party leaves), does
   the projection persist for the audit/arbitration record, and for how long — or is it
   dropped like any projection and rebuilt from events?
7. **Satisfaction vs coverage weighting.** When the matcher ranks candidate matches,
   how much does satisfaction (fit) weigh against coverage (quantity) — and is the
   weight a party preference or a system constant?
8. **Story-log anonymization degree.** How coarse must an anonymized story be before it
   joins the Solutions library — group name stripped? geography coarse-grained? — and
   who redacts, the parties or the system?
9. **Negotiation deadlines.** Does a `negotiating` leg hang until the parties agree, or
   does it also have a window (and if the window lapses, does it dissolve or drift)?
