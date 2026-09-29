# External bindings — making `resource_scopes` and DIDs survivable

Status: design · 2026-09-29 · the tier-3 fix.
Related: `two-layer-map.html` (why these are tier 3), `chain-risk-and-portability.md` (the same
"unforgeable ≠ recoverable" logic), `transfer-authority.md` §1 (the registry they should ride),
`coop-accounts-and-phone-verification.md` (DIDs), `docs/RISKS.md` R-07.

## 0. The principle

Both tables record the same kind of fact: **a binding between a coop principal and a resource that
lives in someone else's system.** Plane, NocoDB, Matrix, Postiz, FreeSWITCH, Telnyx.

> **A binding is resilient when it can be re-established from at least one end.**

Today these can be re-established from **neither** end, which is what puts them in tier 3:

| | Our side knows | Their side knows |
|---|---|---|
| `resource_scopes` | `(group_id, app, resource_key)` — a bare external id | **nothing.** The Plane project does not know a coop group exists |
| `telephony_resources` | the number in `external_ref`, `config` currently `{}` | the carrier knows the number and that *we* own it — but not which group |

**And the distinction that decides everything here:**

> **Committing a binding makes it unforgeable. It does not make it recoverable.** A Merkle root
> proves the mapping you hold is the mapping you held. It cannot tell you what the mapping *was*.

So integrity and recoverability are two different properties needing two different mechanisms, and
the design must not confuse them — which is exactly the confusion that makes "the projection is
rebuildable" sound true when it isn't.

## 1. The core fix: an in-band marker, so the link is discoverable

Put a **durable, derivable marker in the remote system**, so the mapping can be *reconstructed by
search* rather than merely *remembered*. Then the table becomes a **cache of a discoverable fact**,
and the binding moves from tier 3 to tier 2a.

| App | Marker | Discoverable via |
|---|---|---|
| **Plane** | the project's name carries the group slug (e.g. `Food Co-op — <slug>`) | Plane admin API: enumerate projects, match the marker |
| **Matrix** | the room alias already embeds the slug; add a `topic` marker | Synapse admin API: enumerate rooms |
| **Stalwart / mail** | **already derivable** — the group's mail domain *is* `<slug>.irl.coop` | DNS + Stalwart's domain list |
| **NocoDB** | base title marker | NocoDB API: list bases |
| **Postiz** | channel/account handle carries the slug | Postiz API |
| **FreeSWITCH** | the extension *is* the identifier and the group's number range is allocated — the marker is the range | FusionPBX DB |
| **Telnyx (DID)** | set a **label/nickname on the number itself**, if the carrier supports it | Telnyx API: list numbers + labels |

**Cost and constraint:** a naming convention, enforced at every provisioning path, plus a
reconciliation job. And a marker only works where the remote system *permits naming* — some don't.
Where it doesn't, this layer is unavailable and §3 carries the whole load. Say which apps those are
rather than assuming none.

**Why this is the right core fix:** it converts a *record* into a *derivation*, which is the only
move that actually makes something rebuildable. A backup protects against loss; a marker protects
against loss **and** against the remote system minting new ids when it is itself rebuilt.

## 2. The DID specifically

The sharpest case, and the one where the fix is most concrete.

| Element | Where it lives now | What to do |
|---|---|---|
| The number | `telephony_resources.external_ref` (E.164) | keep — **this is already the carrier's own identifier**, so the carrier's inventory is an external source of truth that survives our loss |
| The carrier's resource id | **nowhere** | add to `config`: `provider`, `provider_resource_id`. The stable handle for API operations, and what lets attribution be recovered from the carrier's side |
| The attribution | only our `group_id` | set the **carrier-side label** to the group slug, and record the marker in `config.label` |
| **Taint / reputation state** | nowhere | **ours, uncommitted, and not recoverable from the carrier.** A number's reputation is an asset — this needs a record, and arguably an anchor |
| The assignment history | lost on any change | **treat the DID↔group assignment as a declared binding** (§4) so its history is provable |

**Why the DID deserves the registry treatment more than anything else here:** a number's assignment
is *contestable* and its reputation is *an asset*. "This number belongs to this group" and "this
number was not used for signup spam" are claims other parties may rely on — which is precisely what
the unforgeable tier is for.

**Also worth noting:** `coop-accounts-and-phone-verification.md` states the table holds *"zero `did`
rows"*. It holds **two**. Documentation drift, flagged because that document is otherwise used as
the record of whether a number exists.

## 3. The layers that are not the fix

**Commitment (integrity only).** Once the registry lands (`transfer-authority.md` §1), the binding
set can be Merkle-committed and anchored, exactly like edges. **This makes tampering detectable and
gives a provable inventory — and it recovers nothing.** Do it, for the integrity, but never as the
answer to this question.

**Backup (the floor).** The scope and telephony tables go into the backup set. R-07 says no backup
exists anywhere, so this layer is currently **absent**, which is why tier 3 is load-bearing today.
And the honest test for a backup is a *restore*, not a dump.

**A copy held by the party that owns the fact.** The group should know its own number and its own
app bindings — in the group's own record (a profile field, a group document), not only in the
platform's table. This is the sovereignty shape: *the group holds its own facts, and the platform
holds a cache of them.* It also survives the platform entirely.

## 4. The synthesis: these are declared bindings, and they should ride the registry

`resource_scopes` and `telephony_resources` are the **same shape as an edge**:

```
(principal, external resource, terms, provenance, validity)
```

So they should not be ad-hoc tables with their own conventions. They belong to the **declared-binding
registry**, which means:

- **table now, Merkle later** — the same staging already agreed for edges, inherited for free;
- **O(1) revocation** — a DID retired, a Plane project detached, without rewriting a root;
- **history** — assignment and release become provable events rather than row overwrites;
- **and one place to look** for "what does this group externally depend on", which is also the
  readiness surface `provider-seams.md` §6 asks for.

**And each binding must name which side is authoritative.** The codebase already does this for SIP
credentials — *"the user Vault becomes the source of truth; `v_extensions` is the enforcement copy"* —
and that instinct generalizes:

| Binding | Authoritative for | Copy |
|---|---|---|
| DID | **carrier** — the number exists | ours: attribution, taint, history |
| Plane / NocoDB / Matrix | **the remote app** — the resource exists | ours: the group link |
| Mail domain | **DNS + the mail server** | ours: the slug registry |

Naming it turns "whose data is this?" from an argument into a field.

## 5. The reconciliation job

A marker convention is only real if something checks it. A periodic job that, per app:

1. **enumerates** the remote system;
2. **matches** the marker convention;
3. **diffs** against the projection — missing rows, orphaned rows, marker mismatches;
4. **reports** drift, and repairs only what is unambiguous.

This is the enforcement, and it is also the *proof* that the binding is recoverable — because a job
that rebuilds the table from discovery demonstrates the property rather than asserting it. Same
standard as `provider-seams.md` §4: **an untested recovery is not a recovery.**

## 6. Open questions

- **Which apps refuse naming?** The marker layer is unavailable wherever a remote system will not
  let us set a human-readable identifier. That list decides where backup is the only answer, and it
  should be discovered by trying, not assumed.
- **Does Telnyx support a per-number label?** The whole carrier-side attribution plan rests on it.
  If not, the carrier id in `config` plus our own backup is the fallback.
- **Is a taint/reputation state worth anchoring?** It is ours, it is uncommitted, and other parties
  may rely on it. That is the same test the edge registry was written for.
- **Should the group's own copy be canonical?** If the group holds its DID and bindings in its own
  record, the platform's table becomes a pure cache — which is more consistent with the design's
  posture, and means the platform losing its copy is an inconvenience rather than a loss.
- **How is a marker kept in sync when a group renames itself?** The slug is in the marker, and slugs
  can change. Either the marker uses the immutable `group_id`, or a rename becomes a migration —
  and the immutable id is the safer default even though it is less readable.