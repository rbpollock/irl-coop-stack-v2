# Sharded ledgers & one anchor stream

Status: design · 2026-09-13 · Robbie + Hermes.
Answers: **"how do I shard the Merkle entries across nodes?"**
Serves: the Tier-2 ledger (`money-in-and-out.md` §3.2–3.3), the custody chain
(`custody-chain-and-contest-kit.md`), and the coverage proofs (`event-bus-and-group-shapes.md` §7).

## 0. The question splits in two, and only one of them shards

**Sharding a hash chain is two different problems, and conflating them is why it looks impossible:**

| | Shards? | Why |
|---|---|---|
| **Storage / availability** | **Yes, trivially** | the chain is just bytes. Erasure-code it, replicate it, move it. This is already designed (`federation-encryption-and-access.md` §3) |
| **Write ordering** | **No — not at all** | an append-only chain *is* a total order. Every entry needs a predecessor. Two nodes appending concurrently cannot both be "next" |

So there is no way to shard a single global sequence. The real choice is:

> **Keep one logical order and shard only its availability** — or **shard the writes and give up the
> global total order** in exchange for per-shard order plus a periodic commitment across shards.

**For this stack the second is right, and the shard key is already in the data: `group_id`.**

## 1. Shard by group — the boundary the design already has

A Tier-2 entry belongs to a group. A custody record belongs to a group. So:

- **Each group's ledger is its own append-only chain.** An entry commits to the previous entry *in that
  group's chain*.
- **Nothing needs a cross-group total order.** The commons economy needs *period* commitments
  ("we covered ≥X% this month"), not a global sequence.
- **One key choice serves three purposes:** the group is simultaneously the **shard key** (scale), the
  **privacy boundary** (who may read), and the **replication unit** (what a peer hosts for you).

**Cross-group entries are two entries with mutual references, not one entry in two shards.** A swap —
Group A's 3 hours ↔ Group B's 3 hours — is logged twice, once per shard, each side counter-signed by its
own group (per `money-in-and-out.md` §3.2, the counter-signer must not be the beneficiary, which makes
this the natural shape anyway).

## 2. Two levels of root, and the proof path

```
Base anchor  ←  federation root            committed once per period, over ALL shard heads
                     │
                     ├── (group A, period_root_A)
                     ├── (group B, period_root_B)
                     └── (group C, period_root_C)
                              │
                              └── Merkle root over that group's entries for the period
                                       │
                                       └── the entry itself
```

**A three-level inclusion proof answers "is entry E in Group A's record, as of period P?":**

1. E's Merkle path within Group A's **period tree** → `period_root_A`
2. `period_root_A`'s place in the **federation root** → the anchored root
3. the **Base anchor** for period P (an on-chain transaction, so nobody can backdate it)

**Each level is verifiable independently, and none of them requires trusting a host.** That is the whole
point: a node can serve the wrong bytes, but it cannot make a proof verify against a root it does not
control.

## 2.5 The tree construction, and who may write a root

**Two bytes close a classic hole.** Leaves hash as `sha256(0x00 || entry_id)` and interior nodes as
`sha256(0x01 || left || right)` — RFC-6962-style **domain separation**. Without the prefixes a promoted
interior node and a leaf are both 32 bytes, so a 32-byte value is ambiguous as to which it is, which is the
second-preimage opening in the Bitcoin-style trees.

**An odd node is promoted, never duplicated.** The common `h(dup(last))` scheme is what created that
ambiguity in the first place; with domain separation, promotion is safe and the tree stays unbalanced.

**Order is part of the commitment.** Leaves are laid out in `seq` order, so reordering the same entries
yields a different root — the tree attests a **sequence**, not a set. That matters precisely because the
Tier-2 chain's whole job is to order records.

**And the root is the only thing that leaves the node.** Leaves are entry ids — commitments, never content —
so a verifier (or a member's device) can rebuild a tree from ids alone.

**Who may write a root: the operator, and only the operator.** `anchors` carries **no user write policy at
all**, so neither the app role nor a member can insert one; the three functions that read entry ids, list a
period's roots, and claim a slot are `SECURITY DEFINER`, owned by `coop_rls`, `REVOKE`d from `PUBLIC` and
granted only to `coop_ops` — the same least-privilege shape as the telephony provisioning bridge. **A root
cannot be forged from the application.** Claiming a slot is idempotent and **first-writer-wins**: re-anchoring
the same root is a no-op, while a *different* root for the same `(family, scope, period)` comes back flagged
`conflict` — an alarm, not a race.

## 3. Why the anchor is what makes distributed custody safe at all

Without an outside commitment, **a host can simply show you a different chain.** You have no way to tell
a rewritten history from the real one if the only copy is on the node you are asking.

> **The anchor is not merely tamper-detection. It is the thing that makes it safe to put a ledger on
> somebody else's hardware.**

That is a stronger claim than "we detect tampering," and it is the reason the anchor must be
**impossible for the operator to omit silently** — which is the same property as the federation doc's
"nothing depends on one party" (§2).

## 4. The operational shape (what actually runs)

| Concern | Answer |
|---|---|
| **Shard key** | `group_id` — the group's node(s) hold that group's log |
| **Replication** | ≥3 across peers for a group that matters; a deleted node must not end the history. T2 is tiny (kilobytes/entry), so full copies or erasure-coding both work |
| **What a hostile host can do** | **Drop** (liveness — detectable, the "stale coverage proof" early warning from `cost-model.md`'s federation failure modes) and **withhold**. It **cannot alter**, because alteration breaks the chain against an anchored root |
| **Anchoring** | **Must not be single-party.** Rotate the anchorer per period, or allow anyone to anchor with **conflict detection**: two different roots for the same `(group, period)` is an alarm, not a race |
| **Anchor cadence** | Daily per group is ample for labor and goods. Batch many groups into one Base transaction where signatures allow — the point is the ratio (~120:1 fewer on-chain writes, `money-in-and-out.md` §3.3) |
| **Verification without any node** | The federation design already has **member-held Merkle roots** (`federation-encryption-and-access.md` §3). Members holding period roots means verification depends on *no* node — which is what closes this loop |
| **What the log carries** | entry payload (encrypted where needed), `prev` (in-shard), the authority reference, both signatures, and a `period` marker. The inclusion path is derived from the period boundary, not stored per entry |

**This composes with — and is not the same as — ciphertext sharding.** Already designed: erasure-coding an
*object's ciphertext* so no node holds a whole object (confidentiality + availability). This document is
about partitioning *ordered log entries* by group (scale + ownership). They stack: **each group's log is
itself erasure-coded across peers.**

## 5. One anchor stream, not three

Three things now want periodic roots: the **Tier-2 ledger**, the **custody chain**, and **coverage
proofs**. They should share **one `anchor` record type** that batches roots from any chain-family for a
period:

```
anchor_record
  period        -- e.g. 2026-09-13
  federation_root
  shards[]      -- {group_id, family: "tier2" | "custody", period_root}
  tx            -- the Base transaction that inscribes federation_root
```

Otherwise you pay for three sets of anchor transactions, you cannot correlate them, and a verifier has to
know which of three schemes produced a given root. **One stream, many families.**

## 6. The honest limits

1. **No global total order.** You get per-group order plus period batching. Anything needing a true
   global sequence — a federation-wide money ledger, a single "who acted first" — is **Tier 1**, i.e. the
   chain, and it is **not sharded**.
2. **No cross-shard atomicity.** A two-group swap cannot be made atomic across two shards in general. It
   needs a two-phase/escrow pattern — and the design already has one: the mutual reference plus the
   existing escrow/fund primitive (the vertical fund, `private-treasury-guards-ledgers.md` §10). State
   the timeout explicitly rather than assuming atomicity.
3. **A period is a window of vulnerability in the sense of *ordering disputes*.** Two entries in the same
   period have no provable order between them across shards — only a shared anchor. For labor credit that
   is fine; it would not be fine for double-spend, which is why this is Tier 2 and not Tier 1.
4. **Anchor liveness is the new single point.** If nobody anchors for a period, later verification can
   still work against the last good anchor, but the gap is visible and must be treated as an incident.
5. **Chain length per group grows forever.** Append-only means the period trees are permanent; plan for
   pruning *trees* (keep roots, drop leaf detail where the group agrees) rather than truncating the chain.

## 7. What this means for the build

- **The shard key needs no new concept:** `group_id` is already on every row.
- **The chain, per-group period trees, and the shared anchor record are the three new structures.**
- **The anchor stream should be built once**, before the custody chain and coverage proofs each grow their
  own.
- **Nothing here needs the treasury contract or the chain switch** — anchors are cheap transactions on
  whatever chain is live, so this is buildable before Base migration (and must survive the migration,
  which the anchors do trivially: they are just roots).
