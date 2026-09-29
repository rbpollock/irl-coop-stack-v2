# Proven ZK options for the private treasury — what we've investigated and the tradeoffs

Status: research · 2026-09-29
Related: `private-treasury-implementation-plan.md` (the P-stage plan), `private-treasury-guards-ledgers.md` (the spec).

---

## 0. The honest answer to "what have we investigated"

**Nothing concrete — yet.** Before this doc, the repository contained *no* zk investigation: no
circuit file, no `circom`/`snarkjs` dependency, no trusted-setup record, no `verifier.sol`, no proof
of an evaluated proving system. Every existing "proof"/"zk" mention is speculative or refers to a
*tool that does not exist here* (`zk-membership-graph-proofs.md` cites a `ConfidentialVoting.sol` that
no repo file defines — it's a stub).

So the honest baseline we are working from is: **the spec proposes mechanisms; we have not yet picked,
installed, or proven a single one.** That is the gap this document closes, so the P2 stage of the plan
isn't invented.

---

## 1. The proving systems we are actually choosing between

The spec (§2, §9) needs: a commitments tree, a nullifier set, an on-chain verifier, "proof over proof"
for badges later, and a **mobile-proving v0 gate**. Those constraints pick the field. Here they are
with the real tradeoffs, from the current ecosystem — not stern defaults:

| System | Proof size | On-chain gas (≈) | Trusted setup | Universal? | Recursion? | Proving stacks |
|---|---|---|---|---|---|---|
| **Groth16 (BN254/BLS12-381)** | **192 bytes** | **~181–220k gas** (the tournament-vet standard) | **Yes — ceremony (per circuit)** | No | Difficult (natively) | circom, gnark, arkworks, snarkjs |
| **PLONK-like (PLONK/FFLONK)** | ~576 B – 1.2 KB | ~300k+ | **Universal (once)** or per-circuit | **Yes** | some | circom + plonk, Halo2, **Plonky2, Nova, Celo** |
| **STARKs (FRI-based)** | KBs — huge | huge (10x+ even more) — **no EVM precompile** | **No** | Yes | **excellent** | Cairo, StarkWare, **Stark** via KZG rather than hashing? (Cairo on-chain) |
| **RISC-Zero / Circon / Nova / KZG-list** | KBs | high | No over SNARK | Yes | strong | recursive folding, VPA (ZKP Stanford) |

> The **mobile gate** is the decider: the spec says "must prove acceptably on mobile at launch volume."
> Groth16 proves in ~seconds for tens-of-thousands of constraints — that's the one with a proven path.
> The newer snowbuilds prove slower per constraint but recursively collapse; they gain when the circuit
> gets big.

### The *proven* subset — what's actually audited and deployed

These have live deployments and a large security reviewing.

| Option | Proven by | Say what it | Notes |
|---|---|---|---|
| **circom + Groth16** | Tornado Cash, payroll, ZKNID | best-trodden; tornado is a **nearly identical shape to what we need** (commitments tree, nullifier, spend-with-proof) | fastest to a working v0; **single trusted setup per circuit** |
| **snarkjs** (tooling) | same ecosystem | manages proving/IPFS key | flows with circom+    |
| **Poseidon hash** | Tornado/arb, hardhat | ZK-friendly commitment hash | — |
| **Haly / Halo2** | PENA/eigens | threshold-ish | — |
| **Cairo/Starknet** | Starkware, several | STARK on-chain via Cairo | attractive for larger code; not a pure Solidity-SDK path |
| **RISC-Zero zkVM** | Concurrency | Recursion, no setup | heavier |

### The main fork: a proven-proven extension *copy* vs DIY

1. **Buy/adapt a proven model — Tornado semantics** (circom + Groth16 + Poseidon + a Merkle tree) and
   thin-wrap it. The pool/note spending, nullifier set, gas tradeoffs — all already solved; we wire our
   contracts to proven crypto. Recommended as fastest-correct.
2. **Roll our own circuit with circom** — more sovereign, more risk, and essentially re-inventing Tornado with
   our spec twists (EIP-1271-quorum-in-circuit, project lowering) — a partial re-do of proven code.
3. **A newer proof system (STARK/Nova/RISC-Zero)** — the "modernity" option, but pushes the hard/immature
   part (on-chain verification, trusted setup, proving speed on mobile) onto us. High risk for a v0 that
   must *launch*, just slower.

---

## 2. The specific tradeoffs that matter *for this repo* (not generic)

Set against our constraints:

| Constraint / fact | What it does to the choice |
|---|---|
| **No trust in TEE; pure math (spec §1)** | Any option works; no exception or TEE sanctioned |
| **Chain is Base / EVM** | Groth16 + EVM pairing precompile is cheap; STARK needs no precompile but worse gas; Groth16 is the cheap check |
| **v0 is 1-of-1 member Safes; holder knows their own** | Simplest privacy inside our fork |
| **Mobile proving gate (§9.1)** | Groth16 on a ~60k-constraint circuit already says "a few seconds" — is a *gate* that passes with engineering; STARK/zkVM prove slower on mobile |
| **Proven crypto bias ("sovereign but correct")** | Prefer Tornado-grade proven primitives to a bespoke system |
| **EIP-1271 (Safe quorum) inside the circuit** | This is the genuinely hard bit — every option has to cost it. Groth16 handles it as a public-input/signature-verify call; others leave it to a separate verifier step |

---

## 5. The honest leading recommendation

**Adopt the Tornado-shaped pattern**: **circom + Groth16 + Poseidon commitments** over a fixed-depth
(32) Merkle tree, with nullifiers, deployed with a thin custom treasury contract. That is the only
path that is **simultaneously** proven-deployed, cheap-and-simple to verify on Base-class EVM (~180–220k
gas per proof), small-proof (192 B), and mobile-reasonable for the v0 volume. **PLONK is the runner-up**
for *universality* — worth revisiting only if a unified v0 proves the anti/un-tooship and only if a
larger txteroiraire or proving set.

**STARK / RISC-Zero / Nova / zkVM**: genuinely better for *recursion*, *complex logic*, and bypassing
trusted setups — but they are **not the v0 right answer** for a simple pool-with-notes that must actually
ship profitably on mobile. They're the v1/v2 rabbit hole if we want recursion.

**Do NOT want to do**: hand-build a novel proving system, or fork a Not-ZK "shielded" scheme
(no anon). The value is not in the crypto; it's in the correct wiring of proven pieces to our
governance.

---

## 6. Recommendation

Adopt the **hard-hook of a "proof of a proven thing"** + thin-wrap in P2, with **Poseidon be the
commitment hash, fixed-32 Merkle, Groove16** as the v0. Do not engage mobile-proving "test the
result" until the pool exists and its circuits are ca. The only decision that stays open: **whether
EIP-1271-in-circuit** (proof recovers+verifies the Safe quorum inside the proof) is required at v0, or
whether the signcheck can ride at the contract layer (given a complaining v0's default is storage-only
for soundness). That one is a security-vs-simplicity tradeoff worth a decision BEFORE leading P2.

---

## 7. Open questions (to close before P2 begins)

1. **Where does EIP-1271 (owner-quorum) verification live?!** In-circuit (fully non-interactive, strongest,
   hardest) vs contract-layer (simpler, slightly weaker on proving-order privacy). The spec says it
   "attests the Safe's quorum signed" — but doesn't force the *where*.
2. **Do we poly-step a SECOND option (PLON) as a v1/pool-level swap?** Given we back a pool for current
   ttd — rate, migrations are cheap.
3. **Who runs the trusted setup for Groth16?** Ceremony count; does a small 26-11 half fall within a
   sovereign group's tolerances (run with a mc2 / transcript)? This is the real "sovereignty vs
   simplicity" control.
4. **Do we actually need fresh proof-of-proof at v0** (zk-badge gates), or can they be v1 as the spec
   already stages them? Recommendation: **defer to v1** — do not complicate v0's circuit.
5. **What does "mobile-proving gate" mean in practice?** valorizing it, we need numbers now, not at P5.