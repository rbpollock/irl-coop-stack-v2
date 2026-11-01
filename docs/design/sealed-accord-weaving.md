# Sealed Accord Adaptation — sealed negotiation for weaving

Status: design · Oct 2026 · Source:
[`djat/sealed-accord-demo`](https://github.com/djat/sealed-accord-demo) (partner
spec `djat-lit-20260704`). Builds on needs-offers-matching.md (the trade-chain
projection, cycle discovery, and expediting workflow), match-proposing.md (bond,
badge, and arbitration routing), declared-binding-registry.md (commitment leg:
filled shift, booked resource, matched ride), account-and-key-model.md
(relationship-scoped mutual credit, Safe-as-everything, role/capability matrix),
private-treasury-guards-ledgers.md (project sub-scopes, guard enforcement,
escrow/settlement pattern), group-shape-scenarios.md (capability × scenario
matrix — weaving is the `supply → demand → match → commitment → fulfilment`
shape), and event-bus-and-group-shapes.md (event pipeline, `match.*` namespace).

## 0. What this document does

Sealed Accord is a confidential multi-party negotiation protocol for 3+
institutional parties with private reservation values. Each party encrypts its
true bounds and term constraints to an attested execution boundary; only overlap
/ feasibility signals exit. A human neutral presides over phased adoption
(intake → structure → facts → brackets → accord), with deterministic settlement
math (ZOPA + equal-concession midpoint), per-party signing, and an append-only
hash-chained run record. The original demo is a static reference app; production
intent uses Lit Chipotle (TEE) for the sealed boundary.

This document is a **working plan to adapt five of its concepts** into the
irl.coop weaving layer, replacing the TEE dependency with the stack's existing
threshold-crypto and ZK primitives.

## 1. The adaptation table

| Sealed Accord concept | What it does in the original | How it maps to irl.coop weaving |
|---|---|---|
| **Four-class term sheet** (`must_have`, `must_not_have`, `like_to_have`, `prefer_not`) | Hard constraints vs. tradeable preferences over non-numeric terms (payment timing, release language, confidentiality). | A weaving chain's **leg manifest** carries this vocabulary per term, so the system can reject packages that violate hard constraints before any Safe tx is drafted. |
| **Sealed bracket rounds (ZOPA + term feasibility)** | Encrypted bounds decrypted inside an enclave; the enclave emits only `feasible / not yet` and coarse distance bands. No positions leak on impasse. | Replace TEE with **threshold decryption** (Shamir shares to group Safe signers or a neutral committee) or **ZK feasibility proof** (prove overlap exists without revealing bounds). The "enclave" becomes the protocol itself. |
| **Equal-concession split rule** | When overlap exists, settle at the midpoint of the overlap range — deterministic, order-free, replay-verifiable. | A default **settlement rule for barter/value loops** when multiple feasible packages exist. Removes the "who proposes first" advantage and gives the neutral an unbiased anchor. |
| **Protocol adoption by CID** | The negotiation template compiles to a content-addressed hash. Parties adopt by signing the hash. | Templates stored in the irl-coop-group's **MinIO bucket**; group adopts by Safe vote on the object's content hash, with bus-level enforcement. |
| **Append-only hash-chained run record** | Every step appends to a SHA-256 chain with boundary-class labels and reproducibility signatures. | Aligns with the **event bus + commitment ledger** already in the stack. Dispute audit trails should be verifier-portable without trusting the operator's database. |

## 2. The five work items

### 2.1 Four-class constraint vocabulary for weaving chains

**What:** Add `must_have`, `must_not_have`, `like_to_have`, `prefer_not` to the
need/offer posting schema.

**Where:** `resource_scopes` row (`app = "needs"`) already carries `kind`,
`title`, `description`, `category`, `scope`, and `visibility`. Extend it with a
`constraints` JSONB field shaped to the four-class vocabulary:

```
constraints: {
  terms: [
    { id: "payment_timing", class: "like_to_have", prefer: "net_30" },
    { id: "mutual_release", class: "must_have" },
    { id: "admission_of_liability", class: "must_not_have" }
  ]
}
```

**Integration:** At match-proposal time, the `termPackageCheck` function
(adapted from Sealed Accord's deterministic `termPackageCheck`) runs against the
union of all parties' constraint sets. A hard constraint violation kills the
proposal before it reaches the event bus — no bond posted, no neutral time
burned. This is the **early-ruling pass**.

**Decision deferred and reversible:** whether to store the raw `constraints`
JSONB in `resource_scopes` or in a dedicated `weaving_terms` table. Default:
JSONB in `resource_scopes` (no new table), reversible by migration if indexing
becomes necessary.

### 2.2 Sealed feasibility rounds (threshold / ZK, not TEE)

**What:** Replace Sealed Accord's encrypted-bounds + enclave-computation with
crypto the stack already uses.

**Two candidate paths:**

| Path | Mechanism | Cost | Verdict |
|---|---|---|---|
| **A. Threshold decryption** | Bounds are Shamir-secret-shared to the neutral committee (or the group Safe signers). ZOPA math runs in a cooperative script that assembles shares, computes, then emits signals only. | Committee must be online; plaintext exists at computation time inside the script. | **v0 default.** Simpler, uses existing vault primitives. |
| **B. ZK feasibility proof** | A circuit proves `payer_max ≥ payee_min` and `termPackageCheck` passes, without revealing the four values. | Requires a new circuit family (`weave_overlap`) in the existing Groth16 stack. | **v1.** Plugs into `p2-build-plan.md`'s `spend`/`contribution`/`credential` family as a new predicate. |

**Protocol flow:**
1. Each party posts their bounds + term constraints, encrypted to the
   **instrument key** — a Safe-derived key or a committee public key.
2. The matching service (for threshold path) or the proof verifier (for ZK path)
   runs the feasibility check.
3. Only signals exit: `feasible: true/false`, `band: narrow/moderate/wide`,
   `bindingTerms: [...]`.
4. If infeasible, parties revise and re-submit. If feasible, the split rule
   produces the settlement allocation.

**Neutral scope (R100 equivalent):** The neutral (arbitration committee) sees
convergence structure (which terms are binding) and distance bands, never the raw
bounds or party-specific constraints.

### 2.3 Equal-concession split rule as mediation default

**What:** When overlap exists, settle at `(payer_max + payee_min) / 2` —
deterministic, order-free.

**Where:** This becomes the **default split rule** in the `trade_chain` event
schema when no party proposes an alternative and the neutral does not override.
The rule is recorded in the adopted mediation template (see §2.4), not chosen
mid-dispute.

**Why it's safe:** It is provably symmetric — neither party gains from revealing
first. A party that inflates its `payer_max` or deflates its `payee_min` to
manipulate the midpoint still faces the **final-offer arbitration** backstop (see
§2.5).

### 2.4 Protocol adoption by hash via MinIO under the irl-coop-group

**What:** A group adopts a mediation template by storing it in the
irl-coop-group's MinIO bucket and signing its hash via Safe `execTransaction`.

**How:**
1. The template is authored as a document (e.g.,
   `mediation-templates/weaving-v1.md`) and uploaded to the irl-coop-group's
   MinIO bucket at a deterministic path (`buckets/irl-coop/templates/`).
2. The object's ETag (or a SHA-256 computed at upload) becomes its **content
   hash / CID**.
3. The group votes (via Safe `execTransaction`) to adopt the template by hash
   and version.
4. The adoption event is emitted to the bus as
   `protocol_adopted { group, template_hash, template_path, vote_tx_hash }`.
5. Any later deviation from the adopted template produces a **detectably
   different hash** — the event bus rejects steps that don't match the signed
   CID.
6. MinIO versioning preserves the object history so prior adopted templates are
   recoverable and auditable without trusting the operator's database.

**Why MinIO instead of design-docs.json:**
- The irl-coop-group already owns a MinIO bucket for group-scoped objects
  (published items, maps, media, attachments).
- Templates are large artifacts (markdown + embedded schemas, not just a JSON
  row). Object storage is the natural home.
- The same bucket already enforces group-scoped access via `_irlminio` SSO
  gating; no new permission model is needed.
- Template lineage is preserved by MinIO versioning, not by git history, which
  is consistent with the stack's "no data lives only in git" principle.

**Cross-reference:** This extends the existing object-store conventions
(`app-admission-audit.md` MinIO row, `published-items-as-groups.md` §2 for
per-group bucket storage). The only new behavior is **group-level adoption by
Safe vote on an object hash** and **bus-level hash enforcement**.

### 2.5 Hash-chained run records with deterministic replay

**What:** Every step of a weaving dispute (adoption → intake → bracket → accord
→ signature) appends to an append-only hash chain, same shape as Sealed Accord's
`RunRecord`.

**Stack mapping:** The event bus already writes `match.*` and `trade.*` events.
Extend the `trade_chain` projection with a **chain-local revision tree**:

```
revisions: [
  { kind: "protocol_adopted", payload_hash, boundary_class: "deterministic",
    prev: "GENESIS", revision_hash, t },
  { kind: "intake_sealed", payload_hash, boundary_class: "deterministic",
    prev: <prev_hash>, revision_hash, t },
  ...
]
```

**Reproducibility:** Deterministic steps (ZOPA math, term package check, split
rule) carry `inputs_hash` and `output_hash`. An auditor can re-run the same
function over the same inputs and verify the hash matches — no operator trust
required.

**Arbitration backstop:** If bracket rounds exhaust `maxRounds` without
feasibility, the chain routes to **final-offer arbitration**: each party submits
a sealed last position; the neutral selects one in its entirety. This makes
manufactured impasse expensive (Sealed Accord's structural incentive for honesty).
The arbitration module is the existing `ArbitrationModule`
(`match-proposing.md` §6), with investigator exclusion by graph distance.

## 3. Integration with existing primitives

| Existing primitive | How this plan uses it |
|---|---|
| `needs-offers-matching.md` | Cycle discovery, trade-chain projection, declared/actual/drift expediting. |
| `match-proposing.md` | Bond per proposal, zk-badge trust floor, arbitration routing, investigator exclusion. |
| `declared-binding-registry.md` | The commitment leg — a matched cycle is a declared binding; fulfilment updates the registry. |
| `account-and-key-model.md` | Safe-as-everything for instrument keys; relationship-scoped mutual credit for settlement. |
| `private-treasury-guards-ledgers.md` | Project sub-scope for escrowed bonds; guard conditions for proposer-cut release. |
| `event-bus-and-group-shapes.md` | `match.*` and `trade.*` event namespaces; the event pipeline that feeds the chain projection. |
| `p2-build-plan.md` | ZK circuit family (`spend`/`contribution`/`credential`/`geolocation`/`badge`) — `weave_overlap` is a new predicate. |
| MinIO object store (`app-admission-audit.md`) | Template storage in the irl-coop-group's bucket; content-hash adoption via Safe vote; bus-level enforcement. |

## 4. Status per primitive

| Primitive | Status in this plan | Existing status in stack |
|---|---|---|
| Four-class constraint vocabulary | 🆕 designed | Not present |
| Threshold decryption for bounds | 🆕 designed | Vault exists; weaving integration not wired |
| ZK feasibility proof (`weave_overlap`) | 🆕 not designed | Circuit family exists; new predicate undesigned |
| Equal-concession split rule | 🆕 designed | Not present |
| Protocol adoption by Safe vote + CID | 🆕 designed | MinIO bucket + `_irlminio` SSO gate exist; group vote + bus enforcement not wired |
| Hash-chained run record per trade chain | 🆕 designed | Event bus exists; chain-local revision tree not wired |
| Final-offer arbitration backstop | ⛔ parked | ArbitrationModule exists; final-offer shape not specified |

## 5. The one decision that gates the rest

**Which path for the sealed boundary: threshold decryption (v0) or ZK proof
(v1)?**

- Threshold is the cheap reversible test: it uses the existing vault and a
  committee script. It proves the concept without a new circuit.
- ZK is the durable answer: it removes the need for any party to assemble
  plaintext bounds, even inside a script. But it needs the `weave_overlap`
  predicate designed, trusted-setup'd, and integrated into the existing P2
  proving pipeline.

**Recommended:** Start with **threshold (v0)** as the default, design the ZK path
in parallel as a v1 circuit, and switch only after the ZK predicate is proven in
the harness. The two paths share the same event schema, bus integration, and
arbitration backstop — only the feasibility-check implementation differs.

## 6. Attribution

This plan is derived from the Sealed Accord demonstration protocol by
[@djat](https://github.com/djat), published as
[`djat/sealed-accord-demo`](https://github.com/djat/sealed-accord-demo) and the
accompanying `djat-lit-20260704` collaboration bundle. The original protocol
uses Pathways orchestration, Lit Chipotle confidential execution, and Aqua
attestation. The adaptation here replaces the TEE execution layer with irl.coop's
existing threshold-crypto and ZK primitives, preserving the procedure-design,
adoption-by-hash, and hash-chained record concepts unchanged.
