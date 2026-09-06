# Match Proposing — anyone can weave, no new role

Status: design · Sep 2026 · Builds on event-bus-and-group-shapes.md (the offers/asks
matcher as a future event source), knowledge-aggregation.md (public/group/private
tiers, the union query), account-and-key-model.md (role/capability matrix,
zk-badges), private-treasury-guards-ledgers.md (guards, project sub-scopes,
investigator selection), published-items-as-groups.md (entitlement tables), and the
companion multi-party trade-chain matching spec (needs-offers-matching.md, this session).

## 0. The model in one paragraph

Proposing a match is an **action**, not a role. Any member who already sees a
need/offer — because it's public tier, or posted in a group they belong to, or
shared with them directly — may propose a `matched-by` relationship-record edge
linking two or more postings into a candidate trade chain. No new grant, no new
scope, no new account type: the raw visibility a proposer needs is exactly the
union their world-doc already computes for them. What gates a proposal is not
*who can see* but *what they've done before* — a bond posted per-proposal and a
decaying zk-badge over track record, both scaled to the size and value of the
chain being proposed.

## 1. Principles

1. **Visibility is already flat — reuse it.** A member's accessible-postings view
   is the same union query knowledge-aggregation.md already computes (public tier
   + every group they hold a seat in + direct grants). Weaving needs nothing this
   query doesn't already return.
2. **Weaving is a verb, not a seat.** Proposing a match is the same class of
   action as proposing a vote — irl-coop-group.md's role/capability matrix already
   grants `propose` to any `member`, with no bespoke grant beyond membership
   itself. Proposing a `matched-by` edge sits at that same level.
3. **Gates live on the action, not the actor.** Bond and badge checks fire at
   propose-time, never as a visibility or grant check. There is no "weaver
   permission" to hold or revoke.
4. **Fault, not failure, is what's punished.** A chain can fail for reasons
   outside anyone's control. Only a fault *ruled* against the proposer — via
   arbitration — counts against their bond or their badge.
5. **Reputation is the scarcer resource than capital.** A proven track record
   should raise the ceiling of what a member may propose; a first proposal should
   cost little to attempt.

## 2. Visibility — nothing new

| tier | can a member propose a match referencing it? |
|---|---|
| public | yes — any authenticated member, by construction |
| group | yes — only if the proposer already holds a seat in that group (falls out of the existing union query, no separate check) |
| private | no, unless the posting was directly granted to the proposer — the existing direct-grant mechanic, unchanged |

There is no weaver bypass of privacy. A member cannot propose a match on a
posting they couldn't otherwise see; deny-by-default holds exactly as it does
everywhere else in the knowledge model.

## 3. The proposal event

`trade.match_proposed` — emitted to the event bus, same pipeline as any other
typed event (event-bus-and-group-shapes.md §2.2):

```
{ proposer: sub, postings: [need/offer id, ...],
  edge: "matched-by" (trust dimension — no control, no funds authority),
  bond: { amount|range-proof, project_scope },
  entitlement_pct: fixed at propose-time, contingent on chain.status == settled }
```

The `matched-by` edge is declared, not inferred — same rule as every relationship
edge in the registry ("ownership implies membership ONLY; every other meaning is
DECLARED"). It carries no authority over the chain's value; the proposer never
signs for funds and never gains governance power over the parties they've linked.

## 4. The bond

Posted into a project sub-scope of the trade chain's own treasury at propose
time — the same "money account as a sub-scope of a treasury" pattern used
elsewhere (private-treasury-guards-ledgers.md §2.1). Bond size may be
self-selected: a proposer willing to stake more signals confidence, and — echoing
the commons-economy's "reveal good citizenship, not means" — the amount can be
shown only as a range proof ("staked ≥ X") rather than the raw figure, so a
proposer's confidence is visible without exposing their total resources.

## 5. Settlement of the proposer's cut

Same entitlement-table mechanism as published items: a percentage fixed at
propose time, released only when the guard condition `chain.status == settled`
fires. If the chain settles via relationship-scoped mutual credit rather than an
escrowed value transfer, the proposer's cut can be issued as a small credit at
settlement instead of a cash fee, keeping it inside the same ledger tier as the
rest of the exchange.

## 6. Fault-attributed slashing via arbitration

A chain that fails does **not** auto-slash the bond. It routes through the same
ArbitrationModule already used for chargeback grievances, including the
investigator-exclusion-by-graph-distance mechanism (nobody too close to the
proposer or the injured party — attested by ZK proof over the relationship
registry — may rule on it). The ruling determines the outcome:

| ruling | bond outcome |
|---|---|
| failure outside anyone's control (e.g. a party's equipment failed) | returned in full |
| proposer's fault (e.g. matched stale or already-fulfilled postings) | partial or full forfeiture to the injured parties |

## 7. The match-quality badge

A zk-badge predicate, same family as the existing quest-board and cooperativeness
scores: `matches_closed ≥ N`, `false_match_rate ≤ X%` (counting only
fault-attributed failures, never outside-control ones). It inherits the settled
badge constraints without modification — holder-bound (no farming on a burner
identity) and decaying (an old good record doesn't provide permanent cover).

## 8. What the badge gates — the one legitimate ceiling

Not visibility. Not who may propose. Only the **size, value, or party-count** of
what a given member may propose — the same shape as the quest-board trust floor.
A first-time proposer can freely attempt a small, bilateral-adjacent match; a
five-party, high-value chain requires a proven `matches_closed` history at a
sufficient badge tier.

## 9. Worked example

Maria (from the farm-coalition example in account-and-key-model.md) is an
ordinary member with no special role. Browsing her world-doc's ordinary union
view, she notices three public postings line up: Farm A's surplus-hay offer,
Cold Storage Co-op's need for labor, and Tractor-Share's offer of machine time.
She proposes a `matched-by` edge referencing all three, posts a small bond sized
to her thin track record, and the entitlement table reserves her a modest
percentage contingent on settlement.

The chain proceeds. Leg two (tractor time) stalls past its window; the bus emits
`trade.stuck`; a Temporal workflow escalates. ArbitrationModule investigates,
excluding anyone too close to Maria or the tractor group by graph distance, and
rules the delay an equipment failure — nobody's fault. Maria's bond is returned
in full; her `false_match_rate` is unaffected.

Contrast: if Maria had instead proposed a match on a posting that was already
fulfilled elsewhere, arbitration would rule that her fault — partial bond
forfeiture, and her `false_match_rate` badge ticks upward, narrowing what she can
propose next time until it decays or she rebuilds it.

## 10. Open questions

1. Is there a bond floor for first-time proposers, or is bond size proposer-
   selected from the first attempt (with a minimum only above some chain-value
   threshold)?
2. Does bond size scale *down* as badge tier rises — lowering the capital cost of
   attempting ambitious chains for proven proposers — or stay flat to avoid a
   rich-get-richer effect? (Flagged as a real tension: flat bonds bias the system
   toward safe, low-value matches and away from the ambitious coalition-scale
   chains a matching layer exists to enable.)
3. If two members propose overlapping matches on the same postings, does
   first-proposed win, or can the referenced parties choose between competing
   proposals?
4. Does `false_match_rate` apply only to the proposer, or is there a mirror badge
   for "reliable settling party" — since a chain's failure isn't always the
   proposer's fault, and the parties themselves may need their own trust signal?
5. Is `trade.match_proposed` itself public (letting other members see and improve
   on a proposed chain before it's accepted) or private to the referenced parties
   until they accept?
