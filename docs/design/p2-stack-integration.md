# P2 in the stack — how the proving layer becomes a declared citizen

Status: design · 2026-09-29 · how the P2 (circom/Groth16) proving layer slots into
the declarative stack so it comes up with `stack-up`, shows in the declared-vs-
running report, and never fights the generator's `out/` deletion.
Related: `p2-build-plan.md` (the circuit/toolchain work), `config-flow-generator.md`
(the app spec), `stack-status-and-boot.md` (bring-up), `private-treasury-
implementation-plan.md` (P1 pool + P2 seam).

## 1. The honest framing: P2 is not a service

Every existing app is something you bring up and leave running — it serves a
port, has a health check, and stack-up `up -d`s it. **P2 is not that.** The
proving layer is a **build/bootstrap step whose artifacts plug into the pool**:

```
circuit (.circom)  → circom → r1cs/wasm
powers-of-tau      → groth16 setup → zkey  (the proving key)
zkey              → export → verifier.sol + verification_key.json
verifier.sol      → compiled + linked as the pool's IShieldedPoolVerifier
circle of trust:
  verifier.sol is the ONLY long-lived thing the running stack depends on.
  zkey and the ptau are build inputs (large, one-time, not a service).
```

So "fitting P2 into the stack" is not "add a docker service named zk-server." It is:
1. **Declare the proving toolchain + its artifact home** so the stack knows it exists,
2. **Give it a bring-up path** parallel to how the host-bootstraps run (the way
   `stack-up-hosts.sh` boots hardhat + deploys contracts),
3. **keep the multi-GB proving keys OUT of `infra/out/`** (the generator
   `rmtree`s it every run — a finished zkey there dies silently, exactly the
   `coverage.pmtiles` grief already recorded in AGENTS.md), and
4. **surface it in the declared-vs-running report** so it reads like the rest.

## 2. Two homes for two kinds of state

| Thing | Size | Lives where | Why |
|---|---|---|---|
| toolchain (circom/snarkjs/rustup/cargo) | ~600 MB | `/mnt/storage/zk/{bin,rustup,cargo}` | the persistent repurposed sda1; `/` was 91% full |
| artifacts (zkey, verifier.sol, circuit.compile) | GBs over time | `/mnt/storage/zk/{circuits,keys}` | never in `infra/out/` (pruned) nor `/tmp/zkgate` (24h pruned) |
| the DECLARATION (spec yaml, build recipe, verify-poc) | +few KB | the repo tree `contracts/zk/` + `infra/instances/dev/apps/zk-proving.yaml` | the source of truth; the stack reads it |

The generated `infra/out/` must **only ever hold** a *probeable* command-ready
copy (a `zk-status` marker), never the gigabytes. `out/` is the declared view;
`/mnt/storage/zk` is the artifact home. This is the same ownership split the
stack already uses for certs (`infra/instances/dev/certs/` vs the running edge).

## 3. The declared app — `zk-proving.yaml` (a `type: source` "bootstrap" app)

Declared like any source app, but classed as a **bootstrap** (the stack treats
it as a bring-up step, not a `docker run` service). Sketch:

```yaml
name: zk-proving
pillar: workflow        # or a dedicated `proving` pillar if it ever gets compose
type: source
source: contracts/zk     # the build recipe + circuits live here
enabled: false           # BUILDABLE but NOT yet wired to a deployed pool
toolchain: /mnt/zk/zk    # artifact home — never removed by the generator (see below)
env:
  ZK_KEY_DIR: /mnt/storage/zk/keys
  ZK_CIRCUIT_DIR: contracts/zk
```

**Why `enabled: false`:** the stack is "declared-but-not-wired" until P2 replaces
`NoopVerifier` at the seam and the pool is pointed at the real verifier. `enabled`
keeps it in the intent record (readable, generatored) without making stack-up try
to bring it up as a running service. Flipping to `true` is the gate.

## 4. How stack-up brings it up (idempotently)

Add one parallel step, idempotent like the host-apps boot — **`stack-prove.sh`**
(analogous to `build-images.sh`), invoked when `zk-proving` is `enabled: true`.

The one rule that keeps this honest: **stack-up never rebuilds the zkey.** A
Groth16 key is a trusted-setup article — rebuilding it every boot is not
idempotent (each run changes the setup), and it is actively harmful (a new key
invalidates every existing proof). So the bring-up:

- **checks** whether `verifier.sol` + `verification_key.json` exist in the
  artifact home (and that their circuit digest matches the current circuits);
- if present, **deploys/wires** the verifier (cheap) — and says `OK already` if
  the pool slot is already the real verifier;
- if missing, **reports `zk: key missing — run the one-time ceremony`** and
  exits non-zero (the way the systemd unit treats a real failure). It does not
  fabricate a key.

The trusted setup is a *one-shot ceremony*, deliberately out of the idempotent
up-path — the routine bring-up deploys the verifier that *exists*; the trusted
setup is a separate, human-gated act. That is also what a "trusted setup"
means: it must NOT auto-run on every boot.

## 5. stack-report / status

`stack-report.py` reads the declared tree (instance.yaml + apps/*.yaml) and
reports declared-vs-running. Add `zk-proving` as a declared item with a real
probe: status = **whether `/$KEY_DIR/verifier.sol` (+ zip) exist** and whether
the running pool's `verifier()` points at the real verifier (not Noop). So:

```
zk-proving        declared  ├ buildable (toolchain present)
                              ├ keys: present (sha256 …) → verifier deployed
                              └ keys: MISSING → "run the ceremony" (note)
```

This makes a missing zkey **visible** in the status report — it stops being a
silent stack gap and becomes a declared, gated failure the operator sees. That
is the "fits the scheme" property: it reads like the rest (declared-vs-running,
a missing boot item is a red row, not an invisible /tmp path).

## 6. The seam — why this needs zero pool changes

The pool's `setVerifier(addr)` already exists (`ShieldedPool.sol`). P1 ships
`NoopVerifier`. P2's job is **one transaction**: deploy the real
`Groth16(pool)Verifier` + `pool.setVerifier(realAddr)`. The `IShieldedPoolVerifier`
interface already matches the circuit's public inputs (`oldRoot,
newCommitments, inputNullifiers, proof`). So stack-up's zk step is: *ensure the
real verifier is deployed and pointed-at*. That's a small, idempotent-when-already-set
step (if the slot already points at the real verifier, skip).

- The **pool does not change**. P2 lands entirely as: circuits + ceremony output +
  a verifier contract + one `setVerifier`. So the stack change is "how the zk
  artifacts get built and the verifier gets wired", which is the part this doc
  sizes.

## 7. Build order

| Step | What lands | Declared? |
|---|---|---|
| 1. Toolchain, fixed at /mnt/storage/zk (done) | circom/snark/rust | no — host infra like node |
| 2. `contracts/zk/` — circuits + Makefile/npx pipeline | spend/ticket/merkle compile | yes (repo tree) |
| 3. `zk-proving.yaml` declared (enabled:false) | the intent record | yes |
| 4. `stack-prove-zk.sh` + stack-up hook | idempotent verifier-asm + zkey-missing failure | yes |
| 5. stack-report row | declared-vs-running visibility | yes |
| 6. One-shot setup ceremony: build zkey for spend/ticket | the actual key + verifier.sol | the gate |
| 7. Deploy + setVerifier(real) on the local chain; full P1→P2 test | pool now rejects forged proofs | the P2 gate |

Steps 2-5 are buildable and testable NOW (the toolchain exists; the circuits
compile; the pool + seam exist). Step 6 is the trusted setup — the deliberate
human act. Step 7 is the P2 gate (a real proof verifies; a forged one reverts),
which is what the plan's P2 "does green."

## 8. Do nots (the traps learned)

- **Do NOT store zkeys/ptau in `infra/out/`** — the generator `rmtree`s it. That
  is a silent GB-deleting footgun (already cost the stack a 9.9GB basemap).
  Storage = `/mnt/storage/zk/keys` (host, persistent, gitignored).
- **Do NOT auto-rebuild the zkey on bring-up** — it's a trusted-set article,
  not a deploy artifact. Stack-up *checks* and reports, *never* rebuilds.
- **Do NOT treat P2 as a docker service.** It's a bootstrap that emits an
  artifact the pool wires; a container implies a ping-able server that doesn't
  exist.
- Keep `enabled: false` until the real verifier is meant to replace the no-op —
  the moment it replaces `Noop`, the stack-up/status gate for it becomes
  authoritative.

## 9. Open questions

- Do the *circuits* get committed (they're deterministic, correct-place in
  repo) but the *zkey* never? Yes — circuit = code, key = secret-setup (never
  git). Probably: commit circuits, gitignore keys.
- One custom app per pool key, or a single pool key shared? Start single-key
  (spend); the family (ticket/badge) is separate circuits each with their own
  key/verifier — so it's a *set* of proving apps, a namespace, not one.
- stack-report: should a missing spend-zkey block the whole health check, or
  just flag it? Not a blocker (the no-op still flows P1), report it as a row.
- Is the one-shot ceremony multi-party worthy? This is the repo's first — likely
  a documented single-party, and multi-party is a future (v1) gate per the plan §9.