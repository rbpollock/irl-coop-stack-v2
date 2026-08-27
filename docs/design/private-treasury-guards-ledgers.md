# Private ZK Treasury, Guards & Ledgers — Spec

Status: design · Aug 2026 · Supersedes the scattered ledger/guard notes in account-and-key-model.md (this is the consolidated spec)

## 1. Principles

1. **Privacy by default.** Balances and flows are private to the account (Safe) that owns them. Nothing is publicly visible unless disclosed.
2. **Private from day 1.** The shielded treasury is core infrastructure, not an upgrade: nothing ever ships public-then-private. Privacy is a one-way door — once leaked, never un-leaked.
3. **Pure math, no TEE.** All hiding and proving is zero-knowledge cryptography (commitments, proofs, nullifiers). No trusted hardware, no trusted operator, no Lit.
4. **One treasury per Safe.** Every account — person (1-of-1), group (N-of-M), DAO — holds exactly one private treasury, bound to its Safe but kept logically separate from Safe governance state.
5. **Project accounts are sub-scopes, not entities — until they become groups.** A project/money account lives INSIDE a Safe's treasury as a scoped ledger: same treasury, own keys, own rules, own reports. When a project needs its own allocation or autonomous decisions, it is **promoted to a child group** — its own Safe (the flat funding pool) + its own treasury + sub-accounts — bound to the parent by a **child relationship** (a set of rights, not a flag; see event-bus-and-group-shapes.md §3.4). The parent's own Safe *is* the flat funding pool; there is no separate "funding pool" entity.
6. **Compliance on demand, not by default.** The treasury can produce verifiable reports (tax, compliance, arbitration) via selective disclosure — never by publishing the whole book.
7. **Money auditable; participation cheap.** Money = shielded on-chain. Participation credits = off-chain hash-chained. Badges = off-chain commitments.
8. **Guards gate everything.** Three enforcement points — on-chain Safe guard, in-circuit conditions, app-layer pre-validation — and no single component can create or move value alone.
9. **Settlement rails are the only visible points.** Inbound deposits and outbound withdrawals cross legal rails (stablecoin/bank) and may be visible to the operator; everything INSIDE the treasury — balances, project accounts, distributions, holdings — is shielded from that point.

## 2. The private treasury (shielded state model)

Reference architecture: the shielded value pool (Zcash/Penumbra lineage; Aztec for EVM-embedded variants). The chain stores NO balances — it stores commitments.

- **Notes (UTXOs).** Value lives in notes: `commit(amount, owner_key, project_scope, rng)`. A note is an asset of exactly one project account inside one treasury.
- **Commitments tree.** Each treasury's note commitments form a Merkle tree; the root is the chain state. Balances are not readable from the chain — only commitments.
- **Nullifiers.** Spending a note reveals its nullifier `nullifier = H(note_secret)`. The chain checks "nullifier unseen" — a note can be spent exactly once. Double-counting is structurally impossible (same mechanism as all shielded chains).
- **Transfers as ZK proofs.** A transfer is a proof that: (a) the sum of input notes equals the sum of output notes (conservation, in-circuit), (b) every input nullifier corresponds to a committed note in the tree (existence), (c) the spender is authorized — the proof attests the Safe's quorum signed (EIP-1271 from the Safe) and the guard conditions held (below), (d) outputs are new commitments to the recipients' trees.
- **Viewing keys.** Each treasury has a master viewing key (held by the Safe's custodian set). Project accounts get PROJECT VIEWING KEYS — a sub-key that opens only that project's notes. Compliance = the authority (or the project lead) receives a scope-limited report: opened amounts for a period, or ZK proofs over them (total received ≥ X, net position, tax basis) — WITHOUT the rest of the treasury.
- **Logical separation, one binding.** Project accounts are sub-scopes in the one treasury: same Safe, same chain binding, separate keys/rules/reports. Splitting into a NEW Safe happens only when governance differs — and the mechanism is **promotion to a child group**: the project becomes a group with its own Safe (flat funding pool) + treasury + budget, bound by a child-relationship rights set (allocation caps, veto, reporting), not a new treasury type.

### 2.1 Project-based money accounts

The "logical treasury accounts" from the project-lifecycle design become first-class:

| Account | Scope | Typical rules (guard conditions) |
|---|---|---|
| Savings goal (solar fund) | personal | standing order routing, target cap, withdraw only by owner |
| Capital-raising pool | group | quorum-gated, no single withdrawal, per-member contribution sub-ledger |
| Operating fund | group | 2-of-3, per-ledger limit, expense categories |
| Distribution fund | group | auto-split per entitlement table, monthly via keeper |
| Reserve | group | 3-of-5, timelock on outflow, circuit-breaker freeze |
| DAO treasury | DAO | full constitution: budgets, grants, veto paths |

## 3. Guard integration — three enforcement points

The guard logic (reserved-powers spec) is distributed across three layers. The same rule language is compiled to all three targets.

1. **In-circuit conditions (the new point).** The transfer proof itself attests the policy: per-ledger limits, required seats (encoded as the Safe's signature being part of the circuit's public inputs), timelock windows, zk-badge gates (badges are already ZK — a gate is a proof-over-proof). A tx that violates policy cannot even be CONSTRUCTED as a valid proof. This is the strongest form: policy violations are computationally impossible, not merely blocked.
2. **On-chain Safe guard (TransactionGuard).** Still authoritative for governance-adjacent actions the circuit doesn't cover: owner-set changes, module installs, relationship-record edits, seat protection. Runs in Solidity, reads the registry, gates the Safe's execTransaction.
3. **App-layer pre-validation (coop-api policy engine).** The same rules evaluated cheaply before submission — UX (reject early), gas savings, and a belt for anything in-circuit can't yet express. Never authoritative alone.

Guards are data-driven (terms from the relationship registry), versioned, and upgradeable only through the guarded path.

## 4. Ledger taxonomy (the hybrid, now explicit)

| Tier | What | Where | Integrity |
|---|---|---|---|
| 1 | Money: savings, shares, capital, distributions, DAO funds | **Shielded on-chain** (ZK treasury) | conservation in-circuit + nullifiers + chain consensus |
| 2 | Participation: time-bank hours, labor swaps, quest credits | Off-chain (Postgres), hash-chained, periodically anchored | double-entry invariant + idempotency keys + sequence numbers + hash chain + Merkle anchors on-chain |
| 3 | Badges/stats: zk-badge predicates | Off-chain commitments | proof binds to Tier-2 hash chain / provenance hashes |

Rule unchanged: **money stays auditable — Tier 1 is never public, but it is always provable.** ZK covers everything; cash flows are never invisible to the OWNER or to authorized reporters, only to third parties.

## 5. Double-counting & security analysis

| Attack | Defense |
|---|---|
| Double-spend / double-count | Tier 1: nullifiers (chain-enforced). Tier 2: idempotency keys + conservation invariant + serializable writes. Tier 3: proof binds to anchored hashes |
| Replay of a transfer | Tier 1: nullifier uniqueness. Tier 2: idempotency keys. Tier 3: nonce in badge proof |
| Retroactive tampering | Tier 2: append-only hash chain; anchors expose any edit. Tier 1: consensus |
| Minting / negative balances | Tier 1: conservation in-circuit (inputs = outputs; no free creation). Tier 2: invariant + guard bounds. Keeper cannot exceed rule bounds |
| Compromised coop-api | Mechanical signer; can only submit txs the guard allows; cannot create value; Tier-2 mints detectable at next anchor |
| Compromised Postgres | Read model + Tier-2 ledger: tampering detectable via hash chain/anchors; Tier-1 not affected (chain state) |
| Compromised Temporal | Can trigger workflows, but every trigger re-validates through guard + circuit; no authority to authorize |
| Malicious quorum member | Threshold + seat protection + timelocks (existing reserved-powers design); circuit attests quorum signature |
| Correlation of flows | Shielded by default; viewing keys are scoped; minimal-disclosure reporting proofs (never a fingerprint) |

## 6. Architecture placement

- **Chain** (Base-class EVM; local Hardhat today): Safe contracts, guard modules, shielded-treasury contract (commitment tree, nullifier set, Groth16/PLONK verifier), registry, relationship records, anchors.
- **Prover**: client-side / at the user's site (the sovereignty pattern). Notes and secrets never leave home; proofs are the only thing that moves. **v0 gate: must prove acceptably on mobile at launch scale.**
- **coop-api**: JWT bridge, provisioning, the policy engine (app-layer pre-validation), submission path.
- **Temporal**: the keeper — standing orders, monthly distributions (split per entitlement table), timelock racing, badge decay refresh, dead-man's-switch countdowns. Durable timers; correctness always re-checked by guard/circuit.
- **Postgres (Citus)**: read model — profiles, projects, registry materialized views, Tier-2 ledger log (append-only, hash-chained), event log.

## 7. Compliance & reporting (the "reporting capabilities" ask)

- **Entity books exist.** The Safe's custodian set holds the master viewing key — the cooperative's own books are complete and current, just not public.
- **Selective disclosure proofs.** To a tax authority, auditor, or arbitrator: prove "received exactly $X from these sources in this period", "net position = Y", "no distributions above limit", or any audit predicate — with a ZK proof, no whole-book exposure. Report = opened notes for a period OR proofs over commitments; the authority can verify without the treasury's other accounts.
- **Project-scoped reports.** A project lead (viewing-key holder for that project account) can report on the project alone — payroll, grant drawdowns — without seeing the rest of the Safe's treasury.
- **Legal note (flagged).** Statutory bookkeeping obligations fall on the operating entity (the legal wrapper the Safe governs). The shielded treasury is designed to satisfy them through the reporting function; jurisdiction-specific legal design is required before production — the DAO's compliance workstream.

## 8. Phasing (private from day 1)

Privacy is non-negotiable, so the phasing question is scope, not whether. The v0 feature surface is kept SMALL so the shielded core can ship first.

- **v0 — shielded core (launch):** the treasury contract (commitment tree + nullifier set + verifier), personal + group treasuries, savings routing (standing orders), project sub-scopes with project viewing keys, selective-disclosure reporting (tax/compliance from day 1), and Tier-2 participation credits (hash-chained). Small predicate set: conservation + authorization (quorum signature) + per-ledger scope + limits. In-circuit guards carry the day-one policy.
- **v1:** distribution automation in-circuit (entitlement splits), zk-badge gates as proof-over-proof, timelock/circuit-breaker conditions, multi-jurisdiction reporting pack.
- **v2:** DAO treasury, recursive proofs, cross-treasury flows (group-to-group in one proof), advanced compliance tooling.
- **Settlement rails from day 1:** deposits/withdrawals cross a stablecoin or bank rail (visible crossings, legal entity); everything inside the treasury is shielded from the moment value enters.
- **No public→shielded migration exists** — that is the point of day-1 privacy. v0 dev-stage contracts (current Hardhat Safe deploys) are scaffolding, not production state; production launches shielded.

## 9. Open questions

1. **Mobile proving at launch scale (now a v0 gate):** circuit size vs. latency on phones for 1-of-1 Safes; recursive proofs if needed. The prover runs client-side by principle — v0 must prove at v0 transaction volume.
2. **Chain choice under the day-1 constraint:** Base-class EVM with on-chain verifier vs. a purpose-built shielded chain — costs, finality, tooling. This decision blocks the treasury contract and must be made first.
3. Note encryption & receive UX: stealth addresses, encrypted note delivery without exposing the whole balance.
4. Recovery: how the custodian/recovery path interacts with shielded notes (viewing-key custody in the threshold vault; note secrets recoverable by custodian quorum?).
5. Legal: which jurisdictions accept ZK-verified books; statutory escheatment interactions (residual-heir default must still work over shielded state).
6. Timelock visibility: circuit-breaker freezes must be provable to everyone WITHOUT revealing amounts — freeze = nullifier set toggle, not balance disclosure.
7. Scaffolding status: current dev-stage contracts are scaffolding, not production state — production launches shielded, and no public→shielded migration exists by design.

## 10. Settlement & sponsorship — chargeback protection

**The problem (one line).** Fiat is reversible for ~130 days (Visa/MC/ACH dispute
windows); a group's Safe (crypto) is final. A group must not wait out the window
to spend its contribution revenue — and settled Safe funds can never be clawed
back, so chargeback risk must be resolved *before* value crosses into crypto.

**The model.** The "sponsor" is not a third party: it is a **vertical fund** — a
`subgroup-of` irl.coop (the root group) whose Safe *is* the fund's crypto treasury
(the flat funding pool). One fund per vertical.

- A group in a vertical is **`sponsored-by`** its vertical fund — the economics
  edge from account-and-key-model.md (one-way flow, recognition, **no control**).
  The underwriting **cap**, settlement fee, and repayment schedule are **terms on
  this edge**, not a governance relationship.
- **Contributor fiat** → group escrow (Tier-2 pending-liability ledger), held the
  130-day window. Chargeback-exposed.
- **Fund crypto** → group liquidity (Tier-1 inbound), instant and final. The fund
  is the fiat→crypto bridge: it absorbs the reversibility window so the group
  never waits for its revenue.
- **T+130 settlement** (the only visible crossing, per §9): fiat repays the fund's
  principal, the settlement fee is taken, and the **remainder goes to the fund,
  always** (the fund may remit some to irl.coop's general funds).
- **Chargeback losses** are absorbed by the fund up to the per-vertical cap — the
  fund's "Reserve" sub-account (§2.1) is the chargeback-protection pool.

**Risk is bounded by the cap, not by control.** Because `sponsored-by` is
"no control," the fund cannot micromanage the group's spending; its exposure is
bounded by the cap term on the edge. Governance stays separate (`subgroup-of`).

**Decided (Aug 2026):**

1. **Capitalization** — donors to irl.coop + coop-member governance decisions on
   allocation, informed by member surveys (Formbricks).
2. **Settlement remainder** — always to the fund; the fund may remit some to
   irl.coop general funds.
3. **Sponsorship priority is computed, not declared.** Cooperativeness is a
   *measured* score, not a static form label. Inputs: the regenerative score
   (ZK-metric), communication patterns, internal payouts, transaction types,
   events, livestreams, chats — the operational signals the event bus + ledgers
   already ingest. Prioritize cooperativeness; de-prioritize bad actors. A group
   that scores highly but fits no standard cooperative form still qualifies —
   the matrix is a seed, not a cage (composition-not-inheritance).
4. **Cap** — set by a per-vertical policy, voted by that vertical sub-group's
   members.

**Purpose categories (the organizing axis).** The people-facing verticals —
food sovereignty, civic engagement, infrastructure, … — are **purpose**
categories, not sectors. They are **multi-valued** (a group may sit in several),
exist to organize people around shared ends, and each is maintained by a
vertical sub-group that sets and maintains its rules + funds.

**Out of scope.** Mutuals / nonprofits / associations typically BYO their own
Stripe and do not consume central chargeback protection — they sit outside the
sponsorship rails, not in a middle priority tier.

**Bad-actor signal — reputation-derived, human-gated.** De-prioritization is
reputation-derived (member/contributor grievances), but every grievance is
investigated by an irl.coop representative before it affects standing. The
investigation is the anti-gaming + due-process layer: reputation is not applied
algorithmically, a human rules on each case. This is the "arbitration" primitive
from account-and-key-model.md's Trust dimension (on-chain arbitration records).
Open: the investigator role, grievance admission criteria, the consequence
ladder, appeal/due-process, and grievance privacy.

**Conflict-of-interest exclusion (investigator selection).** Investigators are
drawn by random quorum from the vertical, but a candidate who is "too close" to
the accused group is auto-excluded. Closeness is the candidate's extended graph
distance / connection weight over the relationship registry (member-of,
subgroup-of, sponsored-by, …), attested by a ZK proof — so a hidden conflict (a
relationship inside a hidden group) cannot be omitted. If excluding the too-close
leaves too few candidates to form a quorum, they are included anyway but their
weights are revealed to all (privacy by default, transparency on failure). Open:
the exact distance/weight metric, the threshold, quorum size, and what the
fallback reveals.

**Open:**
- The **purpose-category catalog** (multi-valued, people-facing) is undecided.
- The **cooperativeness score's** inputs/weights/thresholds are set by each
  vertical sub-group; the platform supplies the measurable-signal substrate
  (event store, ledgers), not the formula.
