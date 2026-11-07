# Privacy-First Relationship Graphs and Finance

Status: design · 2026-10-04.

irl.coop knows who is in which group. It does **not** know who owes whom, who paid for what, or
who is related to whom — unless those people choose to reveal it. Relationship graphs and financial
records are encrypted, compartmentalized, and shared only within the scope the member chooses.

---

## What already works (live)

| Primitive | How it works | Where to read more |
|---|---|---|
| **RLS at the database** | Every query is scoped to `app.sub`; no cross-member reads. | [`group-scoping.md`](/design/group-scoping) |
| **Tier-2 ledger** | Contribution records are hash-chained and counter-signed, but the *content* is encrypted. The chain proves tamper-evidence; the content is private. | [`tier2-entry-model.md`](/design/tier2-entry-model) |
| **Zero-knowledge proofs** | Groth16 ceremony complete. Spend proofs verify without revealing balances. | [`groth16-ceremony.md`](/design/groth16-ceremony) · [`proven-zk-options.md`](/design/proven-zk-options) |
| **Disclosure dial** | Every piece of member data carries a granularity setting: `count` / `bucket` / `exact`. Default is the least revealing. | [`scoped-availability.md`](/design/scoped-availability) |

---

## What is designed, not yet built

| Feature | Status | Where to read more |
|---|---|---|
| **Shielded treasury** | Private notes, commitments, nullifiers. Design complete; pending `setVerifier` wiring. | [`private-treasury-guards-ledgers.md`](/design/private-treasury-guards-ledgers) · [`private-treasury-implementation-plan.md`](/design/private-treasury-implementation-plan) |
| **Custody chain** | Append-only signed log for physical goods. Proves transfer without revealing the network. | [`custody-chain-and-contest-kit.md`](/design/custody-chain-and-contest-kit) |
| **Availability proofs** | Prove "I committed N hours this week" without revealing when. Circuit design based on proven `contribution` shape. | [`scoped-availability.md`](/design/scoped-availability) · [`p2-build-plan.md`](/design/p2-build-plan) |
| **Needs/offers matching** | `match.*` event family designed; board is a mockup. Sector-scoped visibility. | [`needs-offers-matching.md`](/design/needs-offers-matching) · [`match-proposing.md`](/design/match-proposing) |
| **Sealed accord** | Encrypted group compacts with selective revelation. | [`sealed-accord-weaving.md`](/design/sealed-accord-weaving) |

---

## Open questions

- **Availability ceremony**: The `contribution` circuit pattern is proven, but a new Groth16 key
  must be generated for the availability predicate. This invalidates all prior proofs if rebuilt.
- **Proof cost**: Every new proof type adds a circuit, a ceremony, and a verifier deployment.
  The platform must decide which predicates are worth the permanent key commitment.

---

## Honest limits

- The payment rail is sandboxed. 4 `payment_intent` rows, all failed. The router is undeployed on
  mainnet. See [`payment-stub-and-handoff.md`](/design/payment-stub-and-handoff).
- The ZK verifier is deployed but not wired to the API. No production proof has been verified
  end-to-end.

See [`irl-coop-overview.md`](/design/irl-coop-overview) for how this pillar fits into the whole platform.
