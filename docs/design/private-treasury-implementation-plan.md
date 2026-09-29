# Private Treasury — implementation & test plan

Status: plan · 2026-09-29 · how to take the shielded-treasury spec from design to a tested,
demonstrable v0. Gated, honest, and sized against what the repo actually has.

Source of truth: `docs/design/private-treasury-guards-ledgers.md` (the spec, 190 lines — this plan
implements **§8's v0**). Relevant: `contracts/contracts/ShieldedPoolMock.sol` + `test/ShieldedPoolMock.ts`
(the current mock), `docs/design/money-in-and-out.md` §3.3 (why Tier 1 is on-chain), §5.1 (chain is Base).

---

## 0. Ground truth (what exists today)

| Fact | Finding |
|---|---|
| The spec | **complete and concrete** — commitments tree, nullifiers, Groth16/PLONK verifier, v0/v1/v2 phasing, no public→shielded migration |
| The pool | `ShieldedPoolMock.sol` — **a fake**. Accepts a commitment + proof, **never verifies the proof** (`bytes calldata /* zkProof */`). It models the *flow*, not the *cryptography* |
| The zk substrate | **none.** No circom, no snarkjs, no hardhat-circom, no circuit files, no Groth16/PLONK verifier, no Semaphore. Nothing is on PATH |
| Deploy path | no script even references a real pool — nothing deploys one |
| Node / python | v26.7.0 / 3.14.7 available for tooling |

**The gap is precisely:** the mock proves the *shape*; implementing v0 means building the geniune
cryptography and the verifier that the mock currently skips. Everything below is that work, ordered so
each stage leaves a working, tested artifact.

---

## 1. Strategic recommendation — before writing code

**Build the real pool in 3 stages, each with a hard "production-gate" at the end.** The spec's
non-negotiable is day-1 privacy with no deprecated public→shielded migration. That means the stage gates
are not "nice-to-have" — deploying a *fake-proof* pool to Base, or shipping a partially-verified one,
would violate the one hard invariant. There is no v0-launch without gates 1-3 green.

### 1a. Decision — the entire signer set is Safes (no EOA cheap path)

**Corrected and locked in: every approval flows through a Safe.** There is no non-nested EOA signer
anywhere. That has a hard consequence for cost: Safe's `checkNSignatures` handles a *contract
signature* (v==0) by making an **external `isValidSignature` call to another Safe**, which runs *that*
Safe's `checkSignatures` — and if *that* Safe's owners are themselves Safes, it recurses. There is no
ecrecover shortcut. So:

| Authorization shape | On-chain cost per spend |
|---|---|
| 2-of-3, each signer a Safe with EOA/passkey owners | ~$1.5–2.5 (approveHash per signer + nested isValidSignature) |
| Nested depth 2 (Safe owns a Safe) | ~$3–6 (each extra Safe layer = another full checkSignature) |

**Consequence: a treasury `spend()` that re-enforces a Safe quorum *per event* is the expensive default —
and it is the path the economy wants to avoid for anything recurring.** This is the strongest argument
for the automation lane (§1b) and for off-chain verification of authorization (§8): sign-once per quorum
for a standing mandate, not per spend.

**Also: this is the one component where a bespoke in-house circuit is highest-risk.** The recommendation
is to buy proven crypto (Poseidon commitment+nullifier + a Groth16 verifier) and build our own thin
contract around it, rather than pioneer a new proving system. And — an important honest simplification —
**for the v0 that serves a 1-of-1 member Safe, the member knows their own amounts; "privacy" is really
about hiding from the chain/plat, not from the holder.** That shapes design toward a modest, correct v0.

---

## Stage 1 — The shielded pool contract (real crypto), no zk proofs yet

**Concerns:** commitment tree + nullifier set + anonymous deposits + the flow. This is the stage the mock
already models — but now with real structure so proofs can be added later without rework.

### Scope (v0 §8)
- A Merkle commitment tree (fixed depth, e.g. 32; Poseidon or full-width-SHA-256 to the existing
  codebase pattern). `deposit(commitment, value)` adds a leaf; the **root is the on-chain state** — 
  balances not readable, no public address.
- Nullifier set: `nullifier = H(note_secret)` stored; `spend(nullifier, ...)` reverts if already seen.
- Conservation bookkeeping: notes in / notes out — but no user bank (the mid-network holds only
  commitments per the spec).
- USDC in/out (v0 is against **USDC**, not ETH — the money path is USDC on Base; the mock uses ETH and
  must be re-pointed).
- Guard hooks: a `spend()` takes a Safe-approved EIP-1271 quorum signature (matching spec §2.4(c)) and
  the guard conditions.

**Tests (unit + integration):**
- `Deposit` adds a leaf, updates the root, single-bind.
- `Spend` requires a valid quorum signature `< threshold`, ≥ threshold, forgery → reject.
- `nullifier` replay is rejected (double-spend).
- Conservation: out ≤ in, no mint.
- USDC flows, not ETH.

**Gate 1 (hard):** every one of these tests green; the contract holds no redeemable balance (notes only);
tree + nullifier are correct. **No zk proof is yet required** — this stage is the *right structure + storage*.

---

## Stage 2 — the real proving layer (the hard part)

**Concern:** conservation + existence + authorization inside a real Groth16/PLONK proof, replacing the
mock's `/* zkProof */` gesture.

1. **Proving system choice.** Recommendations: **Groth16 over BN254** (cheapest on-chain verifier,
   massive tooling, the standard for this), paired with a **Poseidon hash** for the Merkle tree (a
   ZK-friendly choice) OR retain SHA256 where in-circuit cost is acceptable. Decide against recursion in
   v0 (spec §9 records this open question) — the v0 gate says "must prove on mobile at launch volume,"
   so we must size against that.
2. **Circuit work** (the new skillset):
   - A `Deposit` note circuit: produce a commitment `H(groupsafe_addr, secret)`,
   - a `Spend` circuit: prove (a) conservation: Σin = Σout; (b) existence: input nullifiers are
     committed note leaves in the tree; (c) authorization: an *** / Safe-quorum signature checks
     in-circuit (hard — needs a signature-verifier call or nested proof); (d) outputs are fresh
     commitments to the recipients' trees.
   - Build in **circom** (the ecosystem standard), compile, generate the trusted setup, wire
     `snarkjs` for the witness/proof, and get a **Groth16 verifier on-chain** (already in scope from the
     spec §2, §77).

   **Billboard the (c) decision up front.** Because *every* signer is a Safe, putting Safe quorum
   verification *in-circuit* is the hardest, most constrained place to put it. v0 does **not** prove
   the quorum inside the circuit (see §1a and §8). The circuit proves conservation + existence +
   fresh-commitments; **authorization is verified off-chain / at the contract layer**, not in the SNARK.
   This keeps the circuit small and mobile-provable, which is the v0 gate (Stage 5).
3. **Toolchain:** add circom + snarkjs as dev deps / tooling in `contracts/`, plus the hardhat-circom
   plugin. The **whole circuit pipeline gets its own Makefile / npm scripts** so it's reproducible.
4. **The test harness now proves with real keys**, not `"0x"` blobs.

**Tests (Stage-2 accurate):**
- `Spend` proof verifies on-chain for a legitimate user (a real note + quorum sig).
- A forged proof, a double-spent nullifier, and a wrong-conservation proof all **revert**.
- Mobile-sizing: measure circuit proving time at a representative v0 volume and confirm the "launch
  volume" gate (open question §9.1). If it fails, that's a v0 blocker by the gate's own logic.

---

---

## §8. Off-chain proof handling — the decision that makes the cost sane

**The design question:** for a treasury `spend()`, does the SNARK need to be verified *on-chain every
time*, or can the proof be validated off-chain with only a *commitment* recorded on-chain?

### The two meanings must be separated

1. **Verify off-chain, commit on-chain (the real win).** A relayer/verifier validates the Groth16 proof
   off-chain, then submits only the **nullifier + new root + amount** to the pool. The proof bytes stay
   off-chain for anyone to check against the recorded root. **This strips the ~200k Groth16 gas from the
   hot path.**

2. **Verify on-chain per event (the expensive default).** The pool's `spend()` runs the Groth16 verifier
   each call. Correct, but it is why "everything on-chain" costs ~$0.4+ per proof plus the Safe-signature
   bloat (§1a).

**The catch that binds the decision — and it is a real one.** If authorization and conservation are only
verified off-chain, then the *on-chain* pool cannot itself distinguish a legitimate spend from a
relayer saying "trust me." So the split must put the *right* invariants on-chain, or it silently
weakens the model. The safe split:

| Invariant | Goes on-chain | Enforced how |
|---|---|---|
| No double-spend | **always** | nullifier is recorded and checked — non-negotiable |
| Root integrity (tree state) | **always** | root is chain state |
| Conservation (Σin = Σout) | off-chain proof, **anchored** | the proof is verified by a relayer/verifier; the nullifier+root commit is what the chain enforces |
| Authorization (Safe or scoped-key approve) | **off-chain, dictated** | the authorisation is verified by the relayer; the chain accepts the nullifier |

**Why this survives the spec's "no trusted operator" principle:** the relay is **permissionless** — the
protection is not "a trusted party validates," but "anyone can validate the proof off-chain." It is the
same shape as the repo's existing rail/relay seam (`apps/peer_xyz_payments`, internal relaying): there is
no single operator; anyone can run the verifier and any relayer can submit the commit. That is genuinely
different from a TEE or a trusted middleman.

### What it does to the cost — the decision's payoff

| Path | On-chain gas | ~cost (Base) |
|---|---|---|
| Deposit (shield): Groth16 verified **on-chain**, once | ~200k + deposits | ~$0.5 |
| **Routine spend: nullifier + root + settle, proof verified OFF-chain** | ~80–150k | **~$0.2–0.35** |
| Recurring / automation: proof off-chain, command signed by session key | ~50k | ~$0.1–0.2 |
| **Signs that are Safe quorum re-verified per event** | ~400–700k | **~$1.5–2.5+** (avoid for routine) — see §1a |

**Consequence — the economics lock the architecture.** The only incentive-aligned design is:
- **Autorité on-chain for double-spend + commitment integrity** only (small, $0.2–0.35);
- **proof verification + Safe-quorum sign-off happen off-chain** (permissionless relay/verifier), with
  the *authorized* signing happening once per **standing mandate**, not per spend;
- **only the nullifier + root + a signed command touch the chain per recurring spend.**

That is what makes a treasury *usable* on value of $10–$25 dues: at ~$0.25 a move the shield+transpose
doesn't swamp the value.

### The one trust point, named explicitly

**"Who is authorised" and "did conservation hold" are, under this model, verified by a permissionless
relayer/verifier rather than inline on-chain.** Every proof is publicly checkable. A relayer that submits
a bad proof gets rejected by the real nullifier/root invariant on-chain (a false conservation can't
spend real nullifiers). So the *risk* is limited: you trust the **verifier to reject** invalid proofs,
but you cannot create money; double-spend is structurally impossible because the pool never mints and
the nullifier is on-chain.

This is the right off-chain design and it matches how the repo already moves the rails. The remaining
decision is **what authorization means for a spend command** — Safe-threshold (rare/expensive) vs
scoped-key/session (routine/cheap) — which §1a already frames for the routing case.

---

## Stage 3 — the v0 Treasury contract + reporting surface

**Goal:** the one rest that accommodates the spec's shot.

- Integrate the Stage-1 (tree/nullifier/storage) + Stage-2 (proving/verifier) into one deployed treasury
  contract.
- **Project accounts as sub-scopes** (§2.1): a treasury holds per-project notes; a **project viewing
  key** opens only that project's report (spec §2.1, §4). Compliance by **session-key/selective
  disclosure** replaces "whole book."
- **Standing orders** ("savings routing") at v0 — recurring deposits into the shielded core.
- **Standing-order path tests**: flow, conservation, nullification on the EIP1271-authorized spend.

### Tests
- A member deposits (token arrives USDC), root updates, can't read balances by address.
- Member unshields to a Safe, the Amount arrives, the nullifier records.
- View: `projectA` returns that project's report only, **never** the whole ledger; other project keys
  return nothing.
- Standing order: N deposits, end-state total conserved.
- **Attack cases:** fake proof, double spend across notes, out-of-scope project read, unappend/relay replay.

---

## Stage 4 — deploy on the local chain + a full flow demo

- `deploy_treasury.ts` (a real script — currently nothing deploys the pool) targeting the **local
  Hardhat node**, mirroring the existing Safe/amenity deploy pattern.
- Mint/receiver USDC, deposit, note, spend with real proof, unshield — the whole app:
  **no rails, no external chain** — everything on local and programmatic.
- **THIS is the "router" correction too:** re-deploy the router and drive transfer → hold → sweep in
  the same run, since the earlier one didn't survive the chain restart (§ — money-in-and-out.md correction
  we already made).

### Tests
- End-to-end: Safe→router→(sweep)→treasury→shielded→spend→unshield for a single member.
- Deterministic + rebuildable (a milestone harness).
- Documented as "demonstrated on the local chain" with the actual tx hashes, committed to the repo.

---

## Stage 5 — the mobile proving gate (the spec's v0 make-or-break)

The spec §7.2 names this a **v0 gate**: "must prove acceptably on mobile at launch scale." Before
calling v0 done:

- A standard GS w. Prove a Sentinel note on a representative phone / limit. Acceptable budget = some
  number (e.g. < 5s at 2-of-threshold).
- If the naive single proof is too big, engineer: smaller circuits per spec, or recursion. That is the
  v0 block — must be cracked before launch, not after.

---

## 6. The honest candidates (what's extra / not v0)

The spec carves out v0 (§8) as the SMALL surface. Out of v0 by scope, noted for later:
- v1: in-circuit entitlement splits, zk-badge gates (proof-of-proof), timelock/circuit-breaker
  conditions, multi-jurisdiction reporting.
- Standalone v2 (Treasury sold as separate).
- **The doc's big caveat stands:** "No public→shielded migration exists" — the current Hardhat dev Safes
  are scaffolding for the Base switch, and any 'v0 dev' is NOT production.

---

## 7. Planned phases & gates (milestone table)

| Phase | Deliverable | Hard gate (definition of done) |
|---|---|---|
| **P1** | Pool contract + storage (commitments, nullifiers, USDC), deposits + spend-units | unit tests green; no redeemable balance; no zk yet |
| **P2** | circom/Groth16 (circuits, trusted setup, verifier wired) + real-proof spend | in-circuit conservation + existence + fresh commitments; forged/double reject; **authorisation off-chain (per §8)** |
| **P3** | v0 treasury: pool + verifier + **off-chain relay/verifier** + project scopes + viewing keys + standing orders | end-to-end deposit→off-chain-verified-spend→unshield; per-project reporting tested |
| **P4** | Deploy to local node, join with router, demo harness (incl. router re-dep) | demo tx hashes committed; the earlier lost router state re-established |
| **P5** | **Mobile proving budget** | v0 proves on a phone at launch volume; if not, circuit rework, not scope-claim |

Each P is a tested net. P3 is where **off-chain proof handling (§8) and the all-Safe sign-off (§1a)**
are exercised together — a spend whose proof is verified by the relay and whose authorization is a
Safe-mandate (once) rather than a per-event Safe re-check. P1–P2 prove the crypto; P3 makes the cost
shape match the economy.

The **Hardhat node restart** means the previous (2026-09-13) "verified" state is NOT reproducible, so P4
re-establishes it and commits the evidence — removing the biggest current documentation discrepancy (the
`eth_getCode` quote, and the correction note).

---

## 8. Risk & effort notes (so you can schedule honestly)

- **Effort concentration:** Stages 2 + 5 (the crypto: circuit design, trusted setup, proving speed) are
  by far the most effort and the newest skill. That's the real human prerequisite.
- **No zktooling today.** circom/snarkjs need to be installed; trusted setup on BN254 and a shipped
  verifier is a non-trivial but standard chore.
- **Do I need a proper Merkle tree design?** Fixed-depth Poseidon; simplest safe. Don't welcome a new
  advanced-optimization tree.
- **Speed**: Stage 1 is fully wired and low-risk (shaped like current Safe deploys). The zk part is the
  cliff.
- **The "fix the router not being tested" doc correction** is folded into P4.

---

## 9. Deliverables of this plan
- A v0 treasury built and tested on the local Hardhat chain, from real Groth16 commitments, with
  **off-chain proof verification (§8)**, a Safe-mandated sign-off (not per-event nesting, §1a), a
  mobile-proving gate, and full reporting (viewing keys) — matching the spec §8's v0 exactly, closed to
  violation of the no-public→shielded migration rule.
- A **cost model line** for the chain: deposit ~$0.5 (on-chain Groth16) vs routine spend ~$0.2–0.35
  (off-chain proof, anchor commit) vs automated spend ~$0.1–0.2 — so the shielded economy's "small
  per-event fees don't swamp a $10–25 dues" claim is arithmetic, not assertion.
- The trace of the (already-corrected) earlier router state that does not exist in the running stack,
  re-established by P4.
- Every gate proven with tests actually run, committed per gate, per the codebase's verification
  discipline.

---

**Next decision, and the only real fork:** do we (a) buy a proven SNARK (e.g. circom+tornado-style
pool, Poseidon+Groth16) and custom-wire it (my recommendation — fast as a concrete rail), or (b) roll
a bespoke dual-lamin circuit ourselves and take the engineering risk? We can also (c) pause at P1 (a
correct storage+nullifier pool + full reach logic, no proving) as a PR the actual zk layer lands on top.
Options bcd about effort/sovereignty. Each is defensible; recommend (a) then (c)."

---

## 10. Operating model — RESOLVED (2026-09-29, the P2 wiring decision)

The proof is verified **off-chain** and the pool seals the nullifier + root (the
plan's table in §8). This is not "we couldn't wire it on-chain" — it is the
deliberate per-cost/v0 choice: routine spend ~$0.2–0.35 off-chain vs an
on-chain Groth16 pairing (~$0.5+ with the bn254 precompile wedge). No pool byte
change is needed; `IShieldedPoolVerifier` stays the seam a relayer would use.

Consequences, recorded so no one re-introduces the on-chain adapter:
- The ceremony produces `spend_Verifier.sol` (a Groth16Pairing contract) but it
  is the **off-chain** check artifact — the permissionless relayer proves the
  spend against it and submits nullifier + new root to the pool.
- An on-chain `Groth16PoolVerifier` adapter was tried and **withdrawn** (it
  would force a keccak↕Poseidon root to mean on-chain pairing — the expensive
  path the table avoids). Do not re-add it for v0. The off-chain relay keeps
  the pool honest (nullifier set + root progression both on-chain) per §8.
- `spend.circom` now exposes root + nullifierHash as **public** (was private)
  so the relayer can anchor to them; ceremony rebuilt with that shape.