# The declared-binding registry — finalized spec

Status: spec · 2026-09-29 · consolidates `transfer-authority.md` §1, `external-bindings-resilience.md`
§4, and `declared-edges-diagram.html` into one thing to build.
Decided already: **table now → Merkle later**; **guard is authoritative, app-layer is guidance**.

**Decided 2026-09-29 (this round):** one **unified** table; **per-group** roots; **bilateral consent
wherever a binding confers control**; the **immutable `group_id`** in the marker. Authority classes
were left open and are resolved in §0/R5; the mail marker is resolved in §0/R6.

## 0. The four recommendations that resolve the design

### R1 — Repoint, don't build: `CoopRegistry.sol` is already the anchor contract

It holds a `shardRoot` and a `revokedLeaves` mapping, and `_appendMember` is an empty placeholder. It
was *written* as a membership contract and *is* an anchor registry with O(1) revocation. Renaming the
intent costs nothing and saves designing a new contract.

**And make it family-generic, not edge-specific.** `anchors` already carries
`family IN ('tier2','custody','coverage')`. Add a bindings family, and one contract holds roots for
every family. Concretely:

- `anchors.family` gains `'bindings'` (a one-word CHECK change);
- the contract maps `(family, scope, period) → root` rather than `shardRoot` singular;
- `revokedLeaves` becomes `revoked(family, scope, index)`.

That collapses three would-be registries into one.

### R2 — One table for all three binding kinds

`resource_scopes` and `telephony_resources` are the **same shape as an edge** —
`(principal, external resource, terms, provenance, validity)`. Keeping them as separate ad-hoc tables
is what put them in tier 3. Unify:

```sql
CREATE TABLE IF NOT EXISTS declared_binding (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind             text NOT NULL CHECK (kind IN ('relationship','resource','telephony')),
  declared_by      uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,  -- who asserts it
  from_principal   uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,  -- who it binds
  to_ref           text NOT NULL,     -- relationship: the other principal. resource: the resource_key
  app              text,              -- null for relationships; 'plane'|'matrix'|'telnyx'|...
  type             text NOT NULL,     -- member-of|subgroup-of|federated-with|sponsored-by, or resource_type
  terms_hash       text NOT NULL,     -- hash of the off-chain terms document
  marker           text,              -- the in-band marker set in the remote system (resource kinds)
  authority_class  text NOT NULL CHECK (authority_class IN ('role','key','vote')),
  authority_ref    text NOT NULL,     -- role id | key id | decision id  — validity judged at signature time
  valid_from       timestamptz NOT NULL DEFAULT now(),
  valid_to         timestamptz,       -- null = open
  revoked_at       timestamptz,
  nonce            bigint NOT NULL,
  leaf             text,              -- null until committed
  period           date,              -- null until committed
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (kind, from_principal, to_ref, app, nonce)
);
```

Three columns are doing the structural work: **`authority_ref`** (+ the validity window) makes
revocation non-retroactive, **`revoked_at`** makes it O(1) and history-preserving, and
**`marker`** is what makes a resource binding *discoverable* rather than merely remembered.

### R3 — Split the terms: enforceable on-chain, explainable off-chain

This resolves most of the design pressure, and it is the recommendation I'd most insist on.

| | Where | What |
|---|---|---|
| **Enforceable parameters** | **on-chain** | caps, allowlists, expiry, rate limits, thresholds — all small integers and addresses |
| **The agreement document** | off-chain, **hash-committed** | the prose: what is shared, what the parent may do, the purpose |

A guard that runs on-chain cannot read a document. So the terms it enforces **must be** on-chain. What
need not be on-chain is the *explanation* — and its hash is enough to prove the document you hold is
the one that was agreed. **Hash-only for prose, explicit for parameters.**

### R4 — Three readers, deliberately separate

| Reader | Source | Needs the binding record? |
|---|---|---|
| **Access** (who may see/do) | `coop_has_grant` over seats | **No** — already group-scoped |
| **Control** (what the guard enforces) | the on-chain parameters (R3) | Indirectly — set at declaration |
| **Proof** (audit, disputes) | inclusion proof against the anchored root | **Yes** |

The mistake to avoid is making the app query the binding table for everything. Access stays on seats;
control stays on the guard; the binding record exists for **proof and enforcement parameters**.

### R5 — Authority classes: match the class to who is affected

Two axes, not one, and separating them makes the question answerable.

**Axis 1 — who declares?** Some bindings are asserted by the *group* (its own resources, its own
relationships). Others are asserted by the **coop**, because they allocate a scarce asset the coop
holds — a DID, a mail domain. That is why the schema now has `declared_by` distinct from
`from_principal`.

**Axis 2 — what does it affect, and how reversible is it?**

| Regime | Class |
|---|---|
| Machine-declared, routine, reversible | **scoped key** |
| Human judgment, moderate stakes | **role** |
| Confers control over another principal, or allocates a scarce/contested asset | **vote** |

Applied:

| Kind | Declared by | Class | Consent |
|---|---|---|---|
| `resource` (Plane / NocoDB / Matrix) | group, or the provisioning system | **scoped key** | unilateral — the group's own resource |
| `federated-with` | each side, independently | **role** | unilateral each way |
| `sponsored-by` | the sponsor | **role** | unilateral — confers nothing |
| `member-of` | the parent | **role**, or **vote** if the constitution says so | **bilateral** — the member gains a seat in the parent's decisions |
| `subgroup-of` | both parties | **vote** | **bilateral** (decided) |
| `telephony` (DID) | **the coop** | **vote**, at coop level | unilateral, but coop-level — a scarce asset being allocated |

Two consequences worth carrying:

- **A vote-declared binding needs the decision machinery** — quorum, deadline, supersede-not-erase.
  That exists (`proposals`/`votes`) and is unexercised, so a coop-level DID allocation would be its
  first real use.
- **Coop-declared bindings need a coop-level authority** — the coop's own group, not a member group.
  Without one, "the coop allocates the DID" has no signer.

### R6 — Put the marker in the system that is externally authoritative

Generalising from the DID: **each binding nominates the system that is authoritative for its own
existence, and the marker goes there.** Ours is rebuildable, so a marker stored only with us dies
with us.

| Binding | Externally authoritative | Marker lives in |
|---|---|---|
| `telephony` / DID | the carrier (Telnyx) | the number's carrier-side label + `provider_resource_id` |
| mail domain | **DNS (Gandi)** | a TXT record |
| `resource` / Plane, NocoDB, Matrix | the remote app | the app's own name/description field |

**The mail marker, resolved.** The carrier exists and is already in the repo: the acme.sh hook does
`PUT /v5/livedns/domains/<zone>/records/<name>/TXT` and **merges into an existing TXT rrset**, so the
marker needs no new tooling:

```
TXT  <slug>.irl.coop   "irl-coop-group=<group_id>"
```

Then `GET /v5/livedns/domains/<zone>/records` enumerates every group subdomain **and** its
`group_id` — which rebuilds the mail bindings *and* the **slug registry**, since slugs live in
`groups` and are otherwise tier 3. **One marker fixes two tier-3 items.**

Three details that decide whether it works:

1. **Use an explicit TXT, not the wildcard.** `*.irl.coop` covers A lookups; a TXT lookup is a
   different rrset. So each group's TXT is an explicit record and *is* enumerable — but only because
   it is explicit. Relying on the wildcard would make the scheme find nothing.
2. **DNS is public.** The plain `group_id` becomes enumerable by anyone. The subdomain's existence
   already discloses the group, so the increment is modest — but it is a decision, not an accident.
   A *hashed* marker would be quieter and unmatchable after losing the group list, which defeats the
   purpose; plain is the recovery-capable choice.
3. **Stalwart's own field is a convenience copy at best.** Stalwart is ours, so a marker stored only
   there is lost when Stalwart is rebuilt. DNS is authoritative; **the reconciler should enumerate
   DNS.**

## 2. The leaf

Domain-separated and versioned, mirroring the discipline already in `db.ts` for Tier 2
(`sha256("tier2|" ‖ scope_id ‖ "|" ‖ root)`):

```
leaf = sha256( "irl:binding:v1|" ‖ kind ‖ "|" ‖ from_principal ‖ "|" ‖ to_ref
                             ‖ "|" ‖ type ‖ "|" ‖ terms_hash ‖ "|" ‖ nonce )
```

The `v1` prefix is load-bearing: a future format change keeps old proofs verifiable instead of
invalidating them, and a binding leaf can never collide with a Tier-2 leaf.

**Amendments are append + revoke, never update.** A terms change is a new leaf plus `revoked_at` on the
old one — which keeps `revokedLeaves` the mechanism for change as well as for revocation, and means
history is preserved by construction.

## 3. What to do, in order

| When | Do |
|---|---|
| **Now** | Create `declared_binding` (R2) and migrate the existing `resource_scopes` + `telephony_resources` rows into it. Add `config.provider` / `provider_resource_id` to telephony and set the **carrier-side label**. |
| **Now** | Adopt a **marker convention** per app and build the **reconciler** — this is the resilience fix and it does not depend on the Merkle work at all |
| **Now** | Split terms per R3: put enforceable parameters on-chain, keep prose off-chain |
| **When a binding is genuinely worth proving** | Extend `anchors.family` with `'bindings'`, repoint `CoopRegistry`, compute period roots, start anchoring. The migration is additive — `nonce`/`leaf`/`period` backfill with no on-chain state to reconcile |
| **Never** | Commit terms wholesale. Hash-only, unless a specific term must be public |

**The trigger for the Merkle step should be a real one**: a capital campaign whose contributors need to
verify the terms, or a DID assignment someone might contest. Not before — a root over bindings nobody
disputes is ceremony.

## 4. Decisions

| # | Decision | State |
|---|---|---|
| 1 | Unified table, or keep resource bindings separate? | **DECIDED — one table with a `kind` discriminator.** One registry, one reconciler, one proof path |
| 2 | Per-group roots, or one global root? | **DECIDED — per group, sharded by `group_id`**, matching how Tier 2 already shards (`sharded-ledgers-and-anchors.md`) |
| 3 | Which authority class may declare which kind? | **RESOLVED — §0/R5.** Match the class to who is affected: scoped key for machine/routine/reversible, role for human judgment, vote where control is conferred or a scarce asset allocated |
| 4 | Bilateral consent? | **DECIDED — bilateral wherever a binding confers control** (`member-of`, `subgroup-of`), unilateral otherwise |
| 5 | Marker content? | **DECIDED — the immutable `group_id`.** A slug-based marker becomes a migration on every rename |

**One decision that arrived with the resolution rather than being asked:** `declared_by` is now a
column, because some bindings are asserted by the **coop** (a DID, a mail domain) rather than by the
group they bind. That is a real distinction and it needed somewhere to live.

## 5. Open questions

- **Does an amendment need the same authority as the original?** Tightening should. Loosening should
  probably need more.
- **What happens to bindings when a group dissolves?** Cascade (the current FK behaviour) loses the
  history; `revoked_at` preserves it. Probably `revoked_at` for relationships, cascade for resources.
- **Can a binding outlive its authority?** A role that declared a binding is later removed — the
  binding should survive (`validity at signature time`), which the `authority_ref` + validity window
  already encode.
- **Who may read the terms document?** The hash commits it; the document still needs an access
  rule, and for a group under threat that may be a narrow one.