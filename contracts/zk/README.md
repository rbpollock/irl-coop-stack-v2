# contracts/zk — the P2 proving layer build home

This is the declared `source` home for the `zk-proving` stack app
(`infra/instances/dev/apps/zk-proving.yaml`). The P2 proving layer is a
**bootstrap**, not a service: it produces the Groth16 verifier + proving key
that plug into the `ShieldedPool`'s `IShieldedPoolVerifier`, replacing P1's
`NoopVerifier`.

```
zk-proving.yaml            → stack-prove.sh  → zk_pipeline.sh → verifier.sol + zkey
  (infra declaration)        (stack bring-up)   (contracts/scripts)
                                                    │
                                            READ ME: circuits live in
                                            contracts/circuits/{merkle,spend,ticket}.circom
```

## The three homes (don't fight the generator)

| State | Where |
|---|---|
| circuits + pipeline (code) | `contracts/circuits/`, `contracts/scripts/zk_pipeline.sh` (committed) |
| build recipe + this home | `contracts/zk/` (committed) |
| artifacts (zkey, verifier.sol, vk.json) | `/mnt/storage/zk/keys/` — **NEVER in `infra/out/`** (the generator `rmtree`s it) |

## One key per pool (current)

Per the 2026-09-29 decision: **one Groth16 key per pool** — start with a single
`spend` key shared by the spend treasury, not a key per circuit family member.
Rationale recorded in `docs/design/p2-stack-integration.md`: it keeps the trusted
setup surface minimal (one ceremony), and a key is the trusted-setup article that
must NOT be rebuilt/rotated casually. As the family (ticket/badge/geolocation)
lands, each new *circuit* gets its own key — but the pool guards against them via
the same seam, so we add keys only when a circuit actually needs its own (e.g.
different proving parameters or a clean endorsement/endowment boundary).

## Missing keys are flagged, not fatal

The bring-up (`infra/scripts/stack-prove.sh`) never rebuilds a zkey. It checks
the key + verifier exist and are current, wires the real verifier into the pool
if so, and **reports `zk: key missing — run the one-time ceremony`** as a WARN
(a flag) — not a failed bring-up. The no-op verifier still lets the P1 flow work;
a missing proof-setup stops being a silent gap by being visible in the report.