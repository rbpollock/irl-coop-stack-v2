# Pathways × irl.coop — run objects, handoff envelopes, risk-priced escrows

Status: design · adopts the HandoffEnvelope discipline, defers the full DSL.
Register: **D-47** (Tentative — pending owner review).
Source (`PATHWAYS_REFERENCE v1.1.0`,
`PATHWAYS_ARCHITECTURE v1.1.0`; `pathways-integration.html` diagram companion).
Related: `sealed-accord-weaving.md` (sister doc — the confidential-negotiation
leg; this one owns the run/envelope/risk leg; they compose), `needs-offers-matching.md`
(the trade-chain projection this becomes a run over), `weavers.md` (the human top
rung of the autonomy ladder), `match-proposing.md` (bond + badge floor at the
launch gate), `private-treasury-guards-ledgers.md` (guard escrow + Reserve pool
the risk engine sizes), `event-bus-and-group-shapes.md` (the lanes the envelope
rides), `tier2-entry-model.md` §5.6 (the attestation-wait-timer durable-workflow
precedent), `delegation-and-session-keys.md` §9.5 (the deterministic → agent →
human escalation ladder that autonomy bands formalize).

## 0. The answer in one line

Adopt Pathways' **gate profile + HandoffEnvelope + provenance record** as the
contract for every multi-step cooperation on the irl.coop bus — a weave *is* a
PathwayRun, Temporal *is* the executor, the bus *is* the HandoffBus — and put a
versioned **risk engine** beside it so a signed chain comes with a priced escrow
profile instead of a shrug.

The rest: the full Pathways DSL (templates, agents, marketplace) is only worth
adopting wholesale if inter-op with djat's ecosystem becomes a requirement; the
three-layer subset (envelope + audit + risk) stands on its own.

## 1. The adaptation table

| Pathways concept | What it does there | irl.coop mapping |
|---|---|---|
| Template (DSL) | Declarative recipe: identity triple `(domain.subdomain.action@vN)`, ordered steps, gate profile | An adopted protocol template: MinIO object, content-hash-adopted by Safe vote (sealed-accord §2.4 convention), cited by hash |
| `PathwayRun` | One execution of a template, status-machine, durable step rows | A **trade chain / weave instance** — declared state as a resource_scopes row, actuals as `trade.*` events, expedited by a Temporal workflow (needs-offers §5) |
| Steps (`order`, `parallel` groups) | Sequenced agent invocations | Leg statuses `proposed/confirmed/in_transit/received/settled` (needs-offers §2) |
| `gate_profile` + registers R1–R6 | Signed manifest of restraint per run | A **policy document the group adopts by Safe vote** (same MinIO-hash convention); registers map onto existing gates (§3.1) |
| Autonomy bands A0–A3 + escalation rule | Per-run supervision level, launch-enforced | The deterministic → agent → human **escalation ladder**, formalized per-run instead of only per-step |
| `HandoffEnvelope` (R3 `HandoffBus`) | Typed, signed, schema-validated, append-audited message crossing a trust seam | **New.** The typed discipline for cross-boundary bus events — adoption, not rebuild (§3) |
| `ToolGateway` (R2/R4/R5) | Single choke point: capability check, budget decrement, halt liveness | A shim in coop-api at the tool-invocation seam; budget = tier2 ledger; allow-list = session-key caps |
| Practice profile (R1) | Tenant-scoped institutional rules, signed, cold-start gated | A group-adopted executable artifact in the group's MinIO bucket — the existing convention, specialized |
| `ProvenanceRecord` per step | Append-only per-step evidence | The hash-chained run record of sealed-accord §2.5, generalized to every run |
| AquaTree binding | Revision DAG binding runs to template lineage | Template lineage preserved by MinIO versioning; root hash carried on the run's event rows |
| Trusted peering (§10) + trust scopes | Per-build, negotiated, scoped cross-tenant trust | **Group-to-group peering edges** — operational, not structural (§6, open question 3) |
| Genesis attestation (two-tier identity) | Build-id + user-id attestation pair | Safe-as-everything: the group's Safe address IS the attested build identity; Keycloak sub IS the member identity |
| Fork-and-disable visibility (§4.8.10) | Gates-removed badge on marketplace forks | Same instinct as bond+badge-gates-action and publish-don't-withhold — make gate-stripping attestable, don't prohibit it |

## 2. What is missing on our side (gaps that change the design)

| # | Gap | Why it matters | Cost |
|---|---|---|---|
| **G1** | **No run object on the bus.** Events are facts (`match.*`, `trade.*`) but there is no typed, signed, attested execution log a run can be replayed from. | Without a run object a multi-step cooperation is implicit — scattered events, no hash chain, no replay. Arbitration cannot verify "what the agents did" without trusting the operator's runtime memory. | Medium — one projection (run rows claiming event ids into a hash chain) + builder. Signing is Safe EIP-712, exists. |
| **G2** | **No capability profile on steps/agents.** The Safe allow-list gates txs and tier2 caps budgets, but nothing resolves "this agent may call these tools" per step at pre-step time. | The moment group-scoped agents get tool beds, per-step capability resolution is the gap between "honest ceiling set on-chain" and "anything the owner ever allowed." | Medium — a `capability_profile` record per step kind, resolved by the ToolGateway shim (deny-wins ∩ phase profile). |
| **G3** | **No peering protocol between groups.** Relationships (`sponsored-by`) and disclosure scoping exist, but no typed protocol for "group A's run may hand off to group B's run." | Cross-group weaving is where cooperation compounds — and exactly where uncontrolled autonomy is dangerous. Without it, cross-group handoffs are either forbidden (too weak) or ad-hoc (too risky). | Medium-large — a peering-edge record + invitation flow + scope enforcement on the HandoffBus. Partially un-parks federation, only for the typed channel. |
| **G4** | **No risk scoring on weave legs.** Drift is computed but nothing estimates probability-of-failure per leg. | Without risk factors, escrow/insurance can't be priced: over-escrow everything (friction kills participation) or nothing (losses eat the mutual-credit ledger). | Large but bootstrappable — v0 is a deterministic heuristic over existing history (§5.1); the learning loop follows. |

## 3. HandoffEnvelope — the deep integration point

Adopt near-verbatim. The spec's envelope (RIS §4.8.7) is a typed, signed,
append-audited message crossing a trust seam under a closed intent enum, with
upstream free text wrapped as data, never steering. Our seams already exist
separately — the envelope unifies them into one audited object:

| HandoffEnvelope field | irl.coop mapping | New? |
|---|---|---|
| `envelope_version` | enum in payload | 🆕 |
| `intent` (closed enum) | the event `type` namespace (`match.propose`, `trade.settle`, `peering.handoff`) — the intent IS the event type | reuse |
| `target` (typed) | group Safe address / session / peer DID | reuse |
| `params` (JSONSchema-validated) | per-intent schema stored alongside the adopted template in MinIO | 🆕 |
| `event_text` (wrapped as DATA) | only where a handoff feeds an LLM agent: `<handoff source="…" ts="…">…</handoff>` | 🆕 (cheap) |
| `source_run_id`, `source_step_order` | run + step position — needs G1 | depends on G1 |
| `signed_by` (DID) | EIP-712 by the session key acting for the group Safe | reuse |
| append-only handoff audit | `handoff_audit` projection over the event store | 🆕 (thin) |

**The key insight:** events today are typed *facts* ("trade.disputed happened").
Handoffs are *signed commands with schemas* ("invoke this sub-workflow under this
intent, on these params, recorded and priced"). A typed event with an `intent`
enum and a schema-validated payload IS a HandoffEnvelope. The bus doesn't change
— the event payload discipline tightens. `events.ts` needs no new lane; the
live/durable/digested lanes stay as-is.

### 3.1 The three enforcement choke points → our three seams

| Pathways choke point | irl.coop seam | Today | What tightens |
|---|---|---|---|
| Launch (R1 cold-start, autonomy minimums) | Run start: propose chain, start weave, launch agent | zk-badge floor + bond per proposal (match-proposing §4) | + resolve gate_profile against the adopted practice profile; no profile → `BLOCKED_CONFIGURATION` |
| Pre-step / pre-tool (R2/R4/R5/R6) | Each step's tool invocation or Safe tx | Safe allow-list + session-key caps + tier2 budget | + capability_profile resolution (G2), budget decrement per call, halt-flag liveness check |
| Seam (R3) | Sub-run launch, external action, peer fetch | RLS scoping + Safe threshold | + envelope validation: intent allowlist, JSONSchema params, signature, audit append |

### 3.2 Autonomy bands → the escalation ladder, unified

| Band | Stack equivalent | Gate requirement at launch |
|---|---|---|
| A0 Assisted | Human-only UI actions | R1 — adopted practice profile |
| A1 Supervised async | Match proposals, quest applications | + R6 `human_gate` on commit steps — the bond acceptance IS the human gate |
| A2 Headless | tier2Sweep, digestSweep, postizSync | + R2 capability profiles + R3 HandoffBus + R4 tier2 budget cap + R5 halt switch |
| A3 Cross-boundary | A weaver spanning peered groups | all of A2 + phase-scoped capability narrowing (R6) |

**Rule:** a run's band is set at proposal and can only be lowered mid-run, never
raised. Same instinct as immutable chains — drift is computed, never patched; a
run can't edit itself headless, it dissolves and re-proposes.

## 4. Temporal as the Pathways executor

The stack's Temporal worker already IS a durable step-iterator with timers and
waits; the fit maps requirement-for-requirement:

| Pathways runtime requirement (RIS §4.6) | Current Temporal analogue | Change |
|---|---|---|
| Iterate steps in order | workflow bodies | none |
| Persist per-step record | activity writes to the event store | add run/step rows (G1) |
| Progress events on a defined channel | deliverySweep + PUBLISH lane | runs emit `run.step.completed` — new types, zero bus changes (the §2.3 precedent: new sources, no bus change) |
| Cancellation between steps | `TerminateWorkflow` | none |
| No mutation of terminal step rows | append-only event store | none — same invariant |
| R5 halt switch before every tool call | — | a `run/{id}/halt` row the gateway reads; workflows check it as each step's first activity |
| `human_gate` (A1+ commit steps) | — | `waitForSignal('approve')` with TTL; timeout → escalate. Precedent: tier2-entry §5.6's attestation wait timer — the durable-workflow case, proven once |

**The real addition generalizes the wait-timer pattern.** tier2 has ONE wait
(attestations before finalizing a contribution); Pathways runs need *many* (one
per gated step). Same Temporal shape: `waitForSignal` plus a timeout branch. G1's
run/step rows make each wait addressable. Minimal shape:

- `runs` — `id, template_hash, group_id, autonomy_band, gate_profile (resolved), status, created_by_session, created_at`
- `run_steps` (append-only) — `run_id, order, agent_id, status, inputs_hash, outputs_hash, provenance_event_id, started_at, finished_at`
- `handoff_audit` (append-only) — `accepted, rejection_reason?, intent, target, params_keys, run_id, step_order, signed_by, signature, event_id`
- One workflow `pathwayRun` for all templates; template resolved from its MinIO hash at launch; activities = tool invocations + guard checks

## 5. Risk-scored escrow — the insurance profile on a signed weave

(The user ask: *can a signed weave generate an insurance/contingency profile that
suggests how much to escrow, and estimate — and learn from — the risk factors of
each settlement point?*)

**Yes — and Pathways is what makes it a priced product instead of a fuzz.** The
signed chain is the right underwriting document because it is:

1. **typed and dated** — every leg's parties, terms, and windows are structured;
2. **hash-anchored** — the priced input can't silently change after assessment;
3. **provenance-carrying** — pricing can discount runs under strict gate profiles
   versus audit-only ones, using the spec's own escalation semantics;
4. **history-fed** — the Solutions story logs (needs-offers §14) are per-category
   leg-outcome history; that IS the training set.

### 5.1 The v0 risk model — deterministic, no ML yet

`riskProfile(chain) → { per_leg: {p_failure, p_delay, expected_shortfall}, chain_p_failure, recommended_escrow_per_leg, recommended_pool_contribution }`, over:

- **counterparty completion rate** — the zk-badge completion predicates
  (match-proposing / needs-offers §6) reused as *features*, not gates
- **category priors** — leg drift/age distributions from story logs (produce legs
  drift in season; transport legs in weather)
- **graph depth** — cascade risk grows with parties; base shape `1 − Π(1−p_i)`
  under independence, then corrected for correlation
- **exposure concentration** — leg value vs the counterparty's ledger history
- **gate strictness** — strict-gated runs price lower than audit-only ones

Output lands as an ordinary event: `chain.risk_assessed { chain_id, model_version, per_leg, computed_at }`.

### 5.2 Where escrow lives

Treasury-guard escrow for high-value chains was already staged as v1
(needs-offers §8); the risk profile supplies the *amount*:

| Risk tier | Escrow policy | Pool |
|---|---|---|
| Low | none — counterparty reputation suffices | none |
| Mid | partial escrow staged per settlement point; released on `trade.leg_received` | optional contribution to a coop-wide risk pool (the vertical-fund Reserve shape — weavers.md's insurance row, private-treasury §10) |
| High | full escrow on the high-value legs, or underwritten by an insurance group ("insurance is itself a group offer" — weavers.md) | required |

Guard hold-and-release already exists (private-treasury-guards-ledgers §10). The
ONLY new piece is sizing, attached as guard parameters at escrow creation.

### 5.3 The learning loop

Every `trade.settled` / `trade.disputed` and every arbitration outcome against a
prior risk assessment is training data: predicted vs actual, per leg, per
category. The model is a versioned MinIO artifact adopted by group vote (the
§2.4 sealed-accord convention — executable artifacts adopt by hash, not by drift),
so improving the model is an auditable governance act. **Guard rail:** the risk
model prices *legs*, never *people* — the badge floor still gates entry, the
regenerative score stays a social signal, and risk-pricing never becomes a moral
score. That separation is itself a decision this doc takes (§7).

## 6. What the architecture is still missing (the honest answer)

Envelope + audit + risk delivers: signed, typed, priced, attested multi-party runs
across group boundaries with graded autonomy. For "cooperation as a superpower"
the remaining honest gaps:

1. **Counterfactual testing of populations.** We price individual legs but cannot
   ask "what breaks if the top three weaving hubs fail" — a simulation layer over
   the trade-graph. The run projection is its data source; the layer itself is
   out of scope here.
2. **Coverage as a matching signal.** An insured chain is more matchable, but the
   matcher doesn't yet read "has active coverage" when ranking cycles. One line
   in the ranking, once volume exists.
3. **The weaver upgrade path.** weavers.md makes the weaver the human top of the
   escalation ladder. With the envelope + peering, a weaver could be a *group
   agent* running A1/A2 across peer groups. The seam exists; G3 is the only gate.

## 7. DECISIONS this doc takes (and which Robbie owns)

- **DECIDED (agent-authored, pending review):** adopt the HandoffEnvelope +
  append-only audit as the schema standard for cross-boundary handoffs; NOT the
  full DSL. Reversal cost: low — it's a payload schema on the bus.
- **DECIDED:** risk prices legs, never people; reputation gates entry, the risk
  model prices transactions.
- **Robbie owns:** build the full Pathways DSL/executor, or envelope+audit+risk on
  the existing Temporal/bus. **Recommended:** the subset first — it lands exactly
  where autonomy danger lives; full conformance only if inter-op with djat's
  ecosystem becomes a requirement.

## 8. Open questions

1. Run object (G1): own table, or projection over event rows with a `run_id`
   claim? Default: projection — one store of record, cheap reversal later.
2. v0 risk feature set: the five in §5.1, or fewer? Cutline: counterparty
   completion + category priors carry most of the signal; the rest ride the
   learning loop.
3. Peering edges (G3): beside `subgroup-of`/`sponsored-by` in the relationship
   registry, or a distinct primitive? Leaning distinct — peering is operational,
   not structural. Robbie's call.
4. Practice-profile granularity: one per group (versioned, domains as sections),
   or per-domain? Leaning one per group — mirrors "the Safe deploys the contracts."
5. Agent-bound handoffs: is the `<handoff>…</handoff>` data-wrap required at
   in-coop seams too, or only cross-group (A3)? Leaning A3-only — in-coop agents
   run under one RLS identity.

## 9. Attribution

Engages **Pathways Reference Implementation Specification v1.1.0** and
**PATHWAYS_ARCHITECTURE v1.1.0** by David J. Thomson
([@djat](https://github.com/djat)),
[`djat/djat_x_burin`](https://github.com/djat/djat_x_burin). Concepts adopted:
HandoffEnvelope + HandoffBus audit (RIS §4.8.7), the gate-profile register map and
autonomy bands (§4.8), the three enforcement choke points (§4.8.6),
fork-and-disable visibility (§4.8.10), trusted peering (§10). irl.coop's existing
primitives (Safe-as-everything, session-key sponsorship, tier2 ledger, trade-chain
projection, Solutions story logs) supply the substrate; Pathways supplies the
discipline above it. Distinct from the TEE-replacement work in
`sealed-accord-weaving.md` — the two compose: that doc owns the confidential
negotiation leg, this one owns the run/envelope/risk leg.
