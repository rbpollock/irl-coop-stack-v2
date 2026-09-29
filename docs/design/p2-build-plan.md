## The spend suite — one more than "a spend circuit"

The shielded treasury is not one circuit. It is a **family** of zero-knowledge statements, one per
"badge type" the coop proves about a real event. Plan §8 specifies the spend; this table is the
whole v0/v1 surface:

| Circuit | Proves (in-proof) | Public inputs | Status |
|---|---|---|---|
| `spend` (exists) | a note is in the tree, nullifier fresh, output is a real note | root, nullifierHash | P2 in progress |
| `geolocation` | "someone in region R at time T" without the exact coordinate | region(geohashed) | v1 design |
| `balance` | "balance ≥ X" for a note, without the full amount | X (public), committed balance | v1 |
| `contribution` | "contributed ≥ N hours/" without the ledger | N, tree root | feeds entitlement (§3) |
| `credential` | "holds role/blib + expiry" without the identity | signer root, expiry | v1 |
| `authorship` | "I minted this object" w/out linking wallet  | objectId, nullifier | v1 |
| `badge` | a proof-over-proof (zk-badge gates) | predicate id | v2 (spec §9) |

**Rule:** every statement is a *scoped* minimum-disclosure predicate whose proofs anchor to the
tree/root. These compose; badges are proofs-over-proofs. See `p2-build-plan.md`'s
**member-authorable proof pathway**: (A) a parameterized witness app that lets a member supply their
own inputs to a trusted, known circuit (client-side prover + coop anchors the result), and (B) a
reviewed submission path for a member-authored *new* circuit type, admitted to the family only after
it passes the minimum-disclosure gate. Targeted v1/v2.

**Sequencing:** `spend` is the enabled-P2 core. Geolocation/balance/contribution/credentials/
authorship are a **named v1 family** that rides the same Groth16/Poseidon/prover toolchain this P2
setup installs and proves — so the toolchain work is shared, only the in-circuit claims differ.

## Member-authorable proofs — a pathway, not a feature-flag

Every proof above is worth more if a member of irl.coop — not just a developer with a Rust
toolchain — can **create and submit a new proof type** without asking the coop to write circom.
Two ways to read this, and both are real:

| Pathway | Who | What it needs |
|---|---|---|
| **A. Named / parameterized (v1)** | a member picks a known circuit + supplies a witness (their seat, my geolocation, my contribution) | a **witness-inputs UI + a prover that runs locally/client-side**; the circuit is fixed and trusted; the **coop signs/anchors the result**. Easiest, and probably 90% of the need |
| **B. New circuit type (v2)** | a power-user/member authors a **new predicate** | the circuit gets a **reviewed submission path**: a sandboxed compile → setup → test harness, a gate (does it prove a minimal-disclosure claim under the family rules?), and a registry entry so the public verifier key is committed. **Not self-serve for safety — a member-authored circuit enters the family after review** |

**The invariant:** any member-authored circuit must still satisfy the family rules — a scoped,
minimum-disclosure predicate whose proofs anchor to the tree/root — *before* it's admitted to the
safe registry. The review gate in (B) avoids "anyone can make a circuit that leaks"; the low barrier
of (A) avoids "only devs can make predicates."

**Sequencing:** (A) ships alongside the spend circuit — the pipeline is proven, so a member-facing
witness app is the bridge. (B) is the "proof-authoring" pathway this note stands in for: when a
co-op member has a genuinely new claim ("we raised X for Y", "worked in this field", "this is our
object"), there is a **known route from idea → circom → reviewed → registered**, with the knotty zk
work handled and expected.

The spend circuit initially rejected with `T3001: Non quadratic constraints` because the Merkle-path
combine used a ternary (`sides==0 ? a : b`) / `(1-s)*hash + s*path` — not accepted in circom 2.x
metadata in the direct form. The PROVEN patterns are circomlib primitives (`Mux1`/`Mux4`,
`IsZero`) or a explicit `sides*(sides-1)==0` boolean check + quaternary-select. That is the fix P2
uses — not hand-rolled ternary.

Status: P2 kickoff · 2026-09-29 · toolchain target `/mnt/storage` (surfy-backed event)
Related: `private-treasury-implementation-plan.md` §Stage 2, `proven-zk-options.md` (Groth16/Poseidon
selected), `docs/design/private-treasury-implementation-plan.md` §8 (off-chain verify).

## Pre-req: the disk

`/dev/sda1` → `ext4`, mounted `/mnt/storage`, owned `service:service`. This is the zk toolchain +
proof + `.zkey` store. The toolchain lives on `/mnt/storage/zk` so the 91%-full NVMe `/` does not
absorb the build. (Do it at the console:

```
sudo mkfs.ext4 /dev/sda1
sudo mkdir -p /mnt/storage
sudo mount /dev/sda1 /mnt/storage
sudo chown -R service:service /mnt/storage
echo '/dev/sda1 /mnt/storage ext4 defaults 0 0' | sudo tee -a /etc/fstab
```

)

## The toolchain (fresh, on /mnt/storage)

- rustup (for circom build), circom (cargo install), snarkjs (npm -g or local)
- Set `CARGO_HOME=/mnt/storage/zk/cargo` and `RUSTUP_HOME=/mnt/storage/zk/rustup` so the hundreds
  of MB of rust compile land on the big disk, not `/`.
- Verify in order: `circom --version`, `snarkjs --version`.

## Sanity gate (before the real circuit)

Prove the toolchain end to end with a trivial circuit (e.g. `x*x == y`) even before the spend
circuit — confirms compile → setup → witness → prove → verify all work on this host, so the real
circuit build starts from a known-good pipeline.

## The spend circuit (deployed vs the seam P1 proved)

We already proved **the pool-plus-verifier seam works** (P1: RejectingVerifier blocks spend, Noop
admits). P2's job is to replace the Noop with a real Groth16 verifier whose proof the pool verifies.
Circuit must attest, against public `oldRoot`:

- (a) existence: the input nullifier's commitment is a leaf in the Merkle tree at `oldRoot`
- (b) conservation: Σ(in amounts) == Σ(out amounts), all values >= 0
- (c) fresh commitments: outputs are new notes, `hash(secret, owner, value)`
- (not in-circuit: Safe-mandate authorization is off-chain — plan §1a/§8)

Poseidon (recommended) or Sha256 Merkle. Fixed `TREE_DEPTH=32` to match the pool.

## Wiring (the seam）

The verifier must call `IShieldedPoolVerifier.verifySpend(oldRoot, outCommitments, inputNullifiers, proof)` — the exact shape P1 already fixed. So the Groth16 verifier.sol is wrapped:

```solidity
contract Groth16PoolVerifier is IShieldedPoolVerifier {
  function verifySpend(bytes32 oldRoot, bytes32[] calldata out, bytes32[] calldata ins, bytes calldata proof)
      external view override returns (bool) {
    // decode proof (a,b,c) + public inputs [oldRoot, ...out, ...ins]
    return Groth16Verifier.verifyProof(elements(a,b,c), inputs);
  }
}
```

Then point the pool's `setVerifier(address(Groth16PoolVerifier))`. No pool byte change.

## Test — the off-chain seam honoured

With the real verifier: a legitimate spend (real note + real proof) passes; a forged
proof / wrong conservation / double-nullifier reverts. This is the P2 hard gate (plan P2).

## Deliverables

- `contracts/circuits/spend.circom` (deposit + spend)
- `contracts/test/Groth16PoolVerifier.ts` (integration vs the pool)
- a `contracts/scripts` zkey/proof pipeline (snarkjs) — reproducible
- pool wrong-proof reverts; real-proof passes
- `.zkey`/`verifier.sol` stored under `/mnt/storage/zk`

## The P2 gate is closed.

The mount happened, the toolchain is on `/mnt/storage/zk` (built from source),
and the ceremony ran. A real spend witness verifies against the ceremony key:

- `snarkjs groth16 prove` + `verify` → **`[INFO] snarkJS: OK!`** (exit 0); the
  witness satisfies all 17,674 constraints (`wtns check` clean).
- Artifacts in `/mnt/storage/zk/keys/`: `spend_final.zkey`, `spend_vk.json`,
  `spend_Verifier.sol` (the seam contract), the r1cs/wasm intermediates.

What remains is **not a build step** — it's the deliberate `setVerifier` wiring
(flip `zk-proving` to `enabled: true`, deploy real verifier, `setVerifier`) to
replace the P1 `NoopVerifier`. The ceremony doc (`groth16-ceremony.md`) governs
that as the honest single-operator launch tier with the member attestation
rotation path.