# Custody chain & the contest kit

Status: design · 2026-09-13 · Robbie + Hermes.
The first primitive in this cluster that must be **built** rather than productised. Companion to
`adversary-models-and-sector-fit.md` §0.7 (convergent adversaries, contest readiness) and
`federation-encryption-and-access.md` (the confidentiality floor it has to coexist with).

## 0. The problem

The rest of the privacy architecture answers **"can someone read us?"** This answers the opposite
question: **"can we prove what actually happened?"**

Robbie's sabotage case makes it urgent: a food coalition can be discredited, poisoned or shut down,
and **the incident is the attack** — reputational damage persists even after the sabotage is proven.
An inspector, a regulator, a court, an insurer or a journalist will ask *"what did you receive, from
whom, when, and who had custody?"* and a group that cannot answer precisely and verifiably has
already lost, whatever the truth was.

Also note who signs the request: because the state's **instrument mode** (adversary doc §0.5.1) means
the demand often arrives because someone *else* made a plausible complaint — there may be no
opportunity to explain first, only to produce evidence.

## 1. What it is

An append-only, hash-chained, **counter-signed** log of custody events for physical goods — the same
substrate as the designed Tier-2 participation ledger (off-chain, hash-chained), applied to *goods
moving* instead of *people contributing*.

**Tier-2 sibling, not a new tier:** same mechanism, different record family. Participation credits
record contributions; the custody chain records transfers and handling. Both are "append-only signed
facts about the world". Reuse the substrate; do not invent a fourth ledger.

### 1.1 A record

```
custody_record
  seq          uint        -- position in the chain
  prev         hash        -- commits to the previous record; append-only by construction
  asset        bytes32     -- batch/asset commitment (not necessarily a name)
  quantity     encrypted   -- amount + unit, encrypted to the parties
  from / to    seat refs   -- who transferred custody (encrypted where the footprint requires it)
  at           timestamp
  conditions   encrypted   -- seal intact, temperature, packaging state, notes
  evidence     sha256[]    -- photos, lab results, receipts (hashes; blobs stored separately)
  sig_from     sig         -- sender's signature over the record body
  sig_to       sig         -- recipient's COUNTER-signature
```

- **Both parties sign.** A disputed delivery carries two signatures and neither party can alter it
  alone — this is what makes it a *joint* fact rather than one party's assertion.
- **`prev` makes it append-only.** Altering or dropping a record breaks every subsequent link.
- **`asset` is a commitment, not a label.** The chain need not reveal *what* moved in order to prove
  *that something moved and was agreed*.

## 2. The privacy construction — and why it doesn't fight §0.6

A naive custody chain *is* the supply map that E15 wants: names, volumes, dates, in order. So the
chain must obey the same split as everything else:

| Layer | Visibility | Purpose |
|---|---|---|
| **Record commitment + chain links** | publishable / anchorable | provable existence, order, and non-alteration. **Once sharded by group, provenance crosses shards — see `sharded-ledgers-and-anchors.md`** |
| **Record content** (parties, quantity, conditions) | **encrypted to the parties** (and the group's DEK) | readable by those entitled; invisible to everyone else |
| **Selective reveal** | chosen at disclosure time | show one record + its inclusion proof, not the chain |

**How a later proof works:** reveal the record, its ciphertext, the parties' signatures, and the
Merkle inclusion proof against an **anchored root**. The verifier checks that the record is the one
committed at that time and that both parties signed it — **without seeing any other record in the
chain.**

**This is the design's whole trick: the chain is publicly verifiable and privately readable.** It
proves facts about the past while keeping the network illegible, so it *extends* the footprint axis
(§0.6) rather than undermining it. A co-op can prove a specific clean delivery without exposing who
supplies it.

### 2.1 Anchoring — the part that must not be ours

Alteration-detection is worth nothing if the log's own custodian can rewrite it. So:

- **Periodic Merkle roots are anchored outside the operator's control** — the existing Base/Safe
  stack is the obvious anchor, with member devices able to co-sign an anchor (the same "nothing
  depends on one party" rule as the vault, `federation-encryption-and-access.md` §2).
- Anchor cadence is a per-group setting; daily is plenty for agriculture, hourly for cash-in-transit.
- **An operator can refuse to anchor** — that is the liveness limit again, and it is *visible*, which
  is the point. A group whose anchor stream stops can see it stop.

## 3. Independent verification — what turns a log into evidence

A chain of self-signed records proves only that the group was consistent with itself. What makes it
*evidence* is that **third parties sign their own records into it**:

- a certifier's inspection, signed by the **inspector** (not the inspected);
- a lab result, signed by the **laboratory**;
- a buyer's QA acceptance, signed by the **buyer**;
- a seed line's provenance, counter-signed along the exchange.

Their signatures sit in the same chain, so a claim is backed by someone with no incentive to lie on
the group's behalf. **This is also what makes the certification burden pay off twice:** the
traceability records a certified operation is *obliged* to keep (`adversary-models-and-sector-fit.md`
§5.9) become the co-op's own defence kit, rather than living only in the certifier's file.

## 4. What it proves — and what it does not

| Proves | Does **not** prove |
|---|---|
| A record existed at a time and has not been altered since (with an anchor) | that the goods were what the record says — **a signed lie is still a lie** |
| Both parties agreed to a transfer | that either was honest at signing, or not coerced |
| The order of custody, and where a chain demonstrably broke | that nothing happened off-chain |
| That a named third party (inspector, lab) attested a fact | that the attestation was correct |

**Say this out loud in any pitch.** The strongest false claim available here is "we can prove our
food is safe". The true claim is narrower and better: *"we can prove our records are real, and that
we can show you exactly where custody was held if something goes wrong."*

## 5. Where it earns its keep

- **Inputs and produce** — the sabotage case: prove custody held, seals intact, and the break point
  if contamination is found.
- **Seed provenance** — the sharpest case, and it maps directly onto the no-GMO / no-commercial-input
  coalition: a **signed lineage** proves a seed line's origin and handling *without publishing the
  exchange network* that produced it. Provenance without disclosure.
- **Cash / treasury in transit**, tools and equipment loans, medicine and herbal preparations, art and
  cultural objects.
- **Incident logs** — the evidence-shaped record of a contamination, theft or damage event: when it
  was detected, who was notified, what was quarantined. It will be read by an insurer or a regulator.
- **Federation-level** — a node's own custody handovers (backups, erasure shares, key ceremonies) get
  the same treatment for free.

## 6. Work item

**Build #4 in the universal core** (`adversary-models-and-sector-fit.md` §8), the substrate for
contest readiness:

1. **Record type + hash-chain substrate** — reuse the Tier-2 ledger mechanism; add the record family.
   Small, because the shape already exists.
2. **Counter-signature flow** — two-party signing with a dispute/amend path (never edit; append a
   correction that references the record it corrects).
3. **Encrypted content + commitment structure** — the split of §2, using the same per-group DEK and
   selective-reveal machinery as everything else.
4. **Anchoring** — periodic roots to Base, with optional member co-signature.
5. **Third-party signing** — the inspector/lab/buyer side, which is a UX problem more than a crypto one.

**Off by default, per group.** A two-person tool library does not need a custody chain; a farming
coalition with certified inputs and a sabotage risk does. Which is another instance of the same rule:
the platform offers profiles, not one posture.

## 7. Open decisions

1. **Who hosts the chain?** The group's own node (obvious, but then the group's operator can drop
   records — detectable via anchors, not preventable), or sharded/replicated across the federation?
   Replication is cheap for this data size and removes the single-custodian rewrite risk.
2. **Anchor cadence and cost** — Base transactions are cheap but not free; batch anchors are obvious,
   and the group pays or the federation subsidises.
3. **Who may counter-sign** — **ANSWERED 2026-09-13 (Robbie), in `money-in-and-out.md` §3.2: three
   classes, one object** — a **role holder** (witness), a **scoped key** (machine observation), or the
   **group by vote** (ratification). All three are a signature from an authority the group conferred,
   so **one counter-signing layer serves both this chain and the Tier-2 ledger.** Derived requirements
   recorded there: validity judged **at signature time**, the counter-signer **must not be the
   beneficiary**, **thresholded per record class**, and a **refusal stays visible**. Still open here:
   the authority-reference format on a record, and whether an uncounter-signed record can ever affect a
   Tier-1 outcome. **And what happens when a counterparty refuses?** A refusal is itself a
   signal, and the design should let a one-sided record exist *marked as uncounter-signed* rather
   than silently missing.
4. **Does the platform ever hold the plaintext?** No — by the same rule as the vault. The chain must
   be operable by the group, with the platform as an optional relay.
