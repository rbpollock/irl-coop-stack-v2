# Federation encryption & operator access control

Status: design · 2026-09-13 · Robbie + Hermes.
Answers one question: **how do we stop a node operator from having general access to the data they
host?** Builds on `group-secret-vault.md` (settled principles), `group-scoping.md` (§3 tier 2),
`account-and-key-model.md` (Safe as root of trust), `delegation-and-session-keys.md` (granted keys),
`zk-membership-graph-proofs.md`. Companion: `cost-model.md` (federation economics, per-pillar
encryption inventory).

**Hard constraint (AGENTS.md):** pure cryptography only. No TEE, no Lit, no cloud KMS, no
hardware trust. (The `decentralized-authorization` skill's Lit/TEE material is out of scope for
this project — use only its ZK / Merkle / Safe / ERC-4337 parts.)

## 0. The finding that makes this the crux

A node operator occupies **exactly the position the backend occupies today** — and the vault design
already settled what that must mean:

> **"The backend may *censor* (liveness) — never *steal* (confidentiality)."** — `group-secret-vault.md` §2.1

So the operating principle for federation is not new. It is: **an operator may take a node down; it
may never be able to read what is on it.**

But the vault that actually exists is **platform-custodial**:

```
apps/coop-api/src/vault.ts:42
  INSERT INTO group_vault_secrets (group_id, key_name, ciphertext, updated_at)
  VALUES ($1, $2, pgp_sym_encrypt($3, current_setting('app.vault_master_key', true)), now())
```

That is tier 2 — symmetric encryption with a **key the platform holds**. Perfectly fine for one
trusted backend; **worthless for federation**, because a node running coop-api holds the key. The
storage and endpoints exist; the designed k-of-n client-side cryptography does not.

**That is the whole gap.** Not a missing idea — the idea is written down and the code took the
cheaper path.

## 1. Threat model — four adversaries, because they need different answers

| Adversary | Capability | What actually defeats it |
|---|---|---|
| **Curious operator** | reads disks, DB files, backups, and the memory of anything it runs | End-to-end encryption — it never holds the key |
| **Malicious operator** | everything above, plus modifying code, serving a tampered client, replaying, rolling back | Signed/reproducible clients, AEAD integrity, anti-rollback anchors |
| **Compelled operator** (subpoena, seizure, coercion) | must surrender what it holds | Holding **only ciphertext**. This turns *"we can be forced to give you up"* into *"we have nothing to give"* |
| **< k colluding holders** | some members plus the operator cooperate | Shamir threshold — with the settled caveat: *k parties who all collude cannot be stopped by math*, and that set must be the group's legitimate authority, not a hidden backdoor |

Note what changed: the third row is the one a cooperative federation exists to answer, and it is
**not** answered by disk encryption. A seized disk full of LUKS volumes is a seized disk full of
readable data if the operator holds the key.

## 2. The primitive, generalized to bulk data

The vault splits a *secret* (API-key-sized). Group data is bulk. Same ceremony, one indirection:

**Envelope encryption with a per-group Data Encryption Key (DEK):**

1. A group DEK (32 bytes, random) is generated **client-side** — browser or member device.
2. Payloads are encrypted client-side with `AES-256-GCM` under the DEK: per object (files, media,
   attachments) or per row-group (sensitive DB fields).
3. The **DEK itself** is Shamir-split k-of-n, each share wrapped to a holder key via
   `ECDH + AES-GCM` — **exactly the v1 vault ceremony, unchanged**.
4. The node stores ciphertext payloads + encrypted shares + metadata. **It never holds a DEK.**

This is the vault doc's own "future (v3): envelope encryption (SSS a DEK, DEK encrypts the
payload) for bulk secrets" — promoted here from nice-to-have to **the requirement**, because bulk is
now the main case and because rotation becomes cheap: re-wrap the DEK, not the payload.

**Promote threshold decryption (BLS/DKG t-of-n) to a federation requirement.** The vault doc listed
it as v3 ("if *no single reassembly point ever* is required"). In a federation the reassembly point
is precisely the node you do not trust, so it is not optional decoration — it is the difference
between "k members reconstruct the DEK in one place" and "the DEK is never whole anywhere."

## 3. Per pillar: what changes, what it costs, what still leaks

| Pillar | Today | Federation target | Residual leak (state it) |
|---|---|---|---|
| **Object store** (MinIO: files, media, attachments, avatars, webstudio assets) | plaintext — SSE switched off (`apps/minio.yaml:21-23`) | client-side AES-GCM before PUT; node holds ciphertext names + bytes | object size, timing, access pattern; filenames unless encrypted too |
| **Documents** (OnlyOffice) | server-readable (collaborative editing requires plaintext) | **move federation-hosted docs to CryptPad** (CRDT-in-client, already in the stack) or keep docs on the owning group's own node | server-side keystroke timing if kept on OnlyOffice; CryptPad leaks little beyond edit sizes |
| **Mail** (Stalwart) | server-readable — structural: SMTP/IMAP must read to deliver, index, scan | **no honest full fix.** Either a *trusted node*, or mail local to the owning group's node; PGP/S-MIME as a per-user opt-in that costs server-side search and most clients | envelope metadata: from/to/when/size are unavoidably visible to the relaying node |
| **Chat** (Matrix) | E2EE bodies ✓ | force E2EE on group rooms; client-side encrypt **attachments** (non-E2EE rooms and media are the hole) | room metadata, membership, message timing and sizes |
| **Postgres / Citus** (seats, memberships, events, tickets, ledgers) | plaintext at rest — the design doc says so (`group-scoping.md:61-63`) | **split**: non-sensitive stays (titles, counts, public listings); sensitive moves to **commitments** (`group-scoping.md` §3 tier 2 "hidden-from-platform", already designed, deferred) plus **blind indexes** where equality search must survive | commitment sets and blind-index frequency are queryable; row counts leak |
| **Public assets** (basemap, glyphs, static JS/CSS) | public by design (ODbL) | **no change** — this is why federation phase 1 is free | none that matters |
| **Treasuries** | ZK commitments + nullifiers on-chain ✓ | no change | transaction graph (already shielded by design) |

## 4. Preventing general access — the mechanisms, in the order they earn their keep

1. **Ciphertext-only hosting.** The floor. Without it, nothing else matters.
2. **DEK sharding to holder keys.** No single member, and no operator, can decrypt alone.
3. **Erasure-coded sharding of the ciphertext across nodes.** No single operator holds a *whole*
   object. 2-of-3 erasure coding costs 1.5× storage — for the measured 11.25 GB of shared assets
   that is ~17 GB federation-wide, i.e. pennies (§`cost-model.md`). Combined with (1) and (2), a
   single-node compromise yields **neither the key nor a complete object**. *This is the mechanism
   that makes "operators can't get general access" structural rather than promised* — and it is the
   real reason to run a node rather than to rent one.
4. **Threshold decryption (BLS/DKG).** Removes the single reassembly point (§2).
5. **Client-side verification of stored bytes.** AEAD tags plus a member-held Merkle root over their
   own objects: a member can check that the node is still holding *their exact ciphertext*, so
   substitution and silent re-encryption are detectable rather than invisible.
6. **Canaries.** Each member plants a unique, plaintext marker inside their own stored data. If the
   marker is ever observed elsewhere — a leak, a sale, a disclosure — that node exfiltrated. This
   converts trust into a **testable** property and needs no TEE. Cheap to plant, cheap to check,
   impossible to detect by the operator without reading the data it is supposed to be unable to read.
7. **Signed, reproducible clients + client/data host separation** — see §5; without this, the rest
   is theatre.
8. **Blind indexes** — `HMAC(normalise(token), per-group search key)` lets the DB answer equality
   queries over ciphertext. Leakage is frequency and access pattern: fine for high-entropy lookups
   (emails, ids), **unacceptable** for low-entropy fields (booleans, statuses, small enums).
9. **Proactive re-split.** Periodically re-share the DEK so a single long-lived share compromise has
   a bounded window rather than an open one.

## 5. The client-integrity problem — the one that quietly breaks everything above

If the node serves the web app, **a malicious node serves a backdoored client that exfiltrates the
DEK at unlock.** All the cryptography in §4 is then decoration. Answers in order of strength:

1. **Separate the client from the data** — the member's browser loads the app from *their own* node
   (or from a signed release), and only the *data* comes from another org's node. Mostly a routing
   decision, cheap, and it closes the easy attack.
2. **Signed + reproducible builds**, verified in-browser (a build manifest signed by the project
   key, SRI over assets). Tampering becomes *detectable* — not impossible.
3. **A native client** with its own update channel. The strongest option, and the real reason a
   desktop/mobile client matters specifically for the federation tier.

**Honest conclusion:** for a *browser* client served by a node you do not trust, "the operator can't
read your data" holds **only if the client is delivered over a channel the operator does not
control.** Say that sentence out loud rather than implying it away.

## 6. What cannot be solved — state it, don't paper it

- **Endpoint compromise.** If the member's own device is owned, everything they can see is lost.
- **Metadata.** Who talks to whom, when, how much, object sizes. Padding and timing tricks reduce it;
  nothing eliminates it.
- **Availability and freshness.** Encryption buys confidentiality and integrity — **not liveness**.
  An operator can refuse, censor, or serve stale data. Replicas answer availability; anti-rollback
  needs monotonic counters anchored *outside* the operator's control (member devices, on-chain
  anchors).
- **k-of-k collusion.** By design that is the group acting, not an attack.
- **Key loss.** If live shares drop below k, the data is gone — no backend recovery exists *by
  construction*. Recovery must be pre-committed (the vault's re-split rule); the honest cost is that
  a careless group can destroy its own data.
- **Migration.** Everything already stored plaintext — the 11.25 GB of live data, every DB row —
  needs a re-encryption pass on a cutover the group controls. Not free; scope it explicitly.

## 7. Sequencing — cheapest first, and the first step is a principle not a feature

1. **Make the vault non-custodial.** Replace `pgp_sym_encrypt(app.vault_master_key)` with the
   designed client-side SSS envelope. Smallest change, biggest principle: the platform stops holding
   a key it has no business holding. Everything else inherits the shape.
2. **Client-side encryption for the files/docs panel** with a per-group DEK — makes the largest live
   data class federation-safe.
3. **Erasure-coded replication of ciphertext across nodes** — the actual access-control mechanism, and
   it doubles as the phase-1 edge-node work in `cost-model.md`.
4. **Signed client + client/data host separation** — required *before* any node hosts another org's
   data at all.
5. **Sensitive DB fields → commitments**, with blind indexes for queries that must survive
   (reuses `group-scoping.md` tier 2, already designed).
6. **Mail decision** — the only pillar with no full fix (§3).
7. **Re-encryption cutover** for existing plaintext.

## 8. Open decisions for Robbie

**Before these: the adversary analysis in `adversary-models-and-sector-fit.md` determines *which*
adversary each profile is even for.** It splits the four in §1 into internal (11) and external (14),
maps them onto nine cooperative sectors, and proposes four group modes — Open, Guarded,
Compartmented, Deniable. Read it alongside this document: this one says what can be protected, that
one says from whom.

1. **What is k for a *federation* DEK — and who holds shares?** The group's own threshold only, or
   group + peer-node operators (so the *federation* can help recover)? These are two very different
   trust stories and the answer decides whether a group can ever lose its data, and whether peer
   operators ever hold decrypting capability at all.
2. **Do peer nodes ever hold shares?** If yes, erasure coding alone is insufficient; shares need
   sharding too. Default instinct: **no** — nodes hold ciphertext, members hold capability.
3. **CryptPad as the federation-safe document path** — accept the feature trade against OnlyOffice?
4. **Mail**: trusted node for the federation, or group-local only?
5. **Is "no backend recovery, ever" a hard rule?** It is the source of the strongest claim and also
   the reason a group can lose its own data. Worth being deliberate about.

## 9. The claim this lets us make — and the one it forbids

**Forbidden:** *"your data is safe on any node."* Untrue of availability, metadata, clients, and
endpoints.

**Available:** *"an operator can take your data offline. It cannot read it, and it cannot hand over
what it cannot read."* That is a different claim, it survives the threat model in §1, and — unlike
the first one — it is one a cooperative can actually keep.
