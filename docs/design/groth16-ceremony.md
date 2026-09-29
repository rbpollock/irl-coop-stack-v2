# The Groth16 ceremony — launch honesty, member attestation, rotation

Status: design · 2026-09-29 · how irl.coop earns a trusted setup from a **single
operator at launch with no guaranteed members**, and how that key is later
rotated by **casual, non-technical** members without either over-claiming what
anyone did.

Related: `p2-stack-integration.md` (the declared `zk-proving` app + key-check),
`private-treasury-implementation-plan.md` (§8 authz, §9 trusted setup), and the
pool + `IShieldedPoolVerifier` seam (already tested in P1).

## 0. Two launch facts that reshape everything

1. **At launch there are not yet N coop members** — so a multi-party ceremony is
   architecturally impossible at bootstrap. A ceremony that *requires* N members
   to stand up the treasury is a chicken-and-egg: members need a treasury to
   join, treasury needs a ceremony with members.
2. **The members who will exist must rotate the key later, and they are casual,
   non-technical people** — none of them will hold a snarkjs prompt.

Both together force the ceremony model below: a single-party launch key with an
honest label, and a member-rotation path that never asks a nonexpert to do
crypto.

## 1. Why a ceremony at all

A Groth16 key is a **trusted-setup article**: its soundness rests on *at least
one party's entropy being honestly generated and never revealed*. If a malicious
party learns the secret they can forge proofs — for a treasury that is fatal. A
real ceremony makes that "at least one honest party" claim **public and
verifiable** instead of an act of faith in a single person.

For irl.coop that means the proving key must have a **known provenance**:
everyone who matters can see how the key was made, who stood behind it, and can
re-verify it from a public transcript.

## 2. Bootstrap tier (launch, zero members)

At launch we do **NOT** run a multi-party ceremony. We run a **single-operator
ceremony that is honest about being single-party**, because there are no members
yet (by design), the launch treasury is a pilot/closed-scope instrument (D‑16
seats, a live demo — not yet real coop funds), and a single operator is sound
enough for that scope. The bootstrap ceremony:

- one trusted operator (the host/admin);
- entropy from `/dev/urandom`, **pre-committed** — a hash is published before
  the reveal, so the operator cannot later "pick" favorable entropy;
- a transcript of every step kept and made publicly re-verifiable;
- sized for the real circuit family (the powersOfTau bound must fit `spend` and
  the family margins — larger than the pilot's `2^14`);
- **labeled honestly** — `KEY TRUST: 1-operator`. A launch single-party key must
  never be mistaken for a multi-party one.

The launch gate is **not** "sound multi-party setup." The launch gate is:
(a) the pool's integrity holds regardless of key soundness (no-mint, no
double-spend — the P1 tests), and (b) a **rotation path** to a stronger tier
exists. Both are true with zero members.

## 3. The sovereignty tier — members never touch the ceremony tooling

When real members arrive and the treasury holds real funds, the key rotates to a
multi-party *provenance*. But the members are casual. The hard rule:

> **Casual members never touch the crypto ceremony tooling.** They participate
> through the one thing they already know: **acting on the group's Safe.**

The square-peg problem disappears because a nonexpert is never handed the square
tool.

### The co-sign attestation ceremony

- **One operator runs the actual crypto** — every ptau/zkey step, sealed
  entropy, signed transcript — and publishes a **public audit trail** (transcript
  hashes on a declared registry / dashboard card).
- **Casual members attest, they don't compute.** Each designated member, from
  their own device via the existing group Safe/co-sign flow (the exact
  interaction they already use to authorize any group action) approves a single
  payload: **"Rotate the coop proving key to audited setup X (transcript 0x…)".**
- The member's identity (their Safe account) signs the attestation. They are
  **vouching for the public record**, not "sealing entropy I don't understand."
- The group's threshold (n-of-m Safe require) is reached → the rotation
  authorizes `setVerifier(newKey)` on the pool.

What this honestly buys:
- at-least-one-honest-**attestor** plus one **operator** — a real N>1 spirit in
  the ceremony without a nonexpert ever holding ceremony tooling;
- **legitimacy and accountability**: an operator cannot silently swap keys; the
  members *see* and *sign* the public record;
- rotation = one Safe-style action a member already knows.

What it does **not** buy, and must be said plainly:
- It is **NOT** N independent *crypto-secret* holders. Real secrecy still rests
  on the single operator. Members add **providence + attestation**, not
  independent entropy-holding. The sealed key's secrecy is 1-operator; the
  attestation layer makes that one point *legitimate and public* and defends
  against a silent key swap — it does **not** make the secrecy "N-party."

Both lines must be stated in any ceremony summary, never blurred:
> The key's secrecy rests on the operator's honest entropy. The member coalition
> makes that single point *legitimate and audited* — it does not turn secrecy
> into N-party. Claiming otherwise would be dishonest.

## 4. The casual member's actual UX

What a casual member physically does, end to end:

1. A pending card in the group dashboard: **"Approve rotating the treasury
   key."** It shows public info only — who ran the ceremony, the transcript
   hash, when, old → new key, and a plain-language line: *"you approve and watch
   an audited operation; you do not hold the key yourself."*
2. One tap → signs via the co-op Safe flow (the same screen as any group fund
   approval).
3. A confirmation: "you approved key rotation 0x…" — kept in group history.

No hash, no shell, no crypto vocabulary. The crypto is either operator-side (the
build) or publicly observable (the card). This meets "casual non-technical
designated member" without pretending otherwise.

## 5. Rotation mechanics

- Rotation is additive-safe: the old verifier remains until the pool's notes
  are re-proofed under the new key, then `setVerifier(new)` is called.
- A key-provenance journal in `keys/` + `.circuits-digest`: every rotation
  appends a signed line — transcript hash, operators, member attestations,
  timestamp. `stack-report` reads it so the status line can say "key rotated on
  <date> by <N> attestations."
- Key rotation can ride the same Safe/edge machinery as any other group decision
  — it is a declared action the group authorizes.

## 6. Zero-member launch line and the trigger

At launch: no members, so the ceremony is single-operator, the attestation tier
is **dormant**, the pool is sound-under-single-op, and the docs say so. The
rotation *upgrade* trigger is designed in — **"first real funds, or first N
members"** — so the single-op key never silently ossifies into the production
key. The launch is not a member gate; the *upgrade* is.

## 7. Stack consequences

- `zk-proving` stays declared, `enabled: false` at launch;
- `contracts/zk/build.sh` = the single-operator bootstrap ceremony (the upgrade
  changes only how entropy/transcripts are gathered, not the key I/O);
- member rotation = a "rotate key" group action, identical in shape to Safe group
  approvals;
- the audit trail is a new declared surface — a treasury-key / rotation-log card,
  integrateable with the dashboard and campaign surface.

## 8. Open items

- Whether the operator must be a member (first/co-founder, or the first member
  cohort to title them) is a governance decision.
- Whether "at least one honest attestor" needs a strength parameter — e.g. the
  attestor being a real established member versus a freshly-joined account —
  is worth an attestation-weighting. Recorded open; revisit when the member
  anthology exists.