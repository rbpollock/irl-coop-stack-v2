# World-Doc & the Group-Aware Contact Model — Spec

Status: design · Aug 2026 · Conversation-derived (Robbie + agent, 2026-08-10). Companion
to account-and-key-model.md and private-treasury-guards-ledgers.md.

## 1. The world-doc (what it is)

The **world-doc is what you can see and do** — one per-user document, aggregated
from every app and group the user touches, cached so any app can answer "what
does this person's world look like?" without fanning out to a dozen services.
It is a **projection, never the store of record**: rebuildable, filtered by the
user's seats, and migratable with the user.

**The boundary rule:** the world-doc holds projections, pointers, and proofs.
Anything authoritative lives in a store of record (on-chain registry, Safe,
per-app DBs). The doc is derived from those sources and dies nothing when
dropped — it is rebuilt from surviving sources.

| Is world-doc | Never world-doc |
|---|---|
| Seats/memberships/roles/aliases (projection) | On-chain relationship registry (truth) |
| Contact edges (explicit, user-owned) | Safe governance state |
| Financial VIEW: proofs, pending approvals, timelocks, entitlements | Balances/ledgers (Safe holds the truth) |
| Capability state: "what can I approve right now" | Keys, secrets, seed material |
| Lifecycle state: recovery, inheritance, abandonment timers | Blobs/files (pointers only) |
| Attestations/badges the user holds | Ephemeral presence (Redis pub/sub, not the doc) |
| Activity / central notifications | Telemetry |

## 2. Contacts: derived, not stored

A "contact" is usually just *a person you share a group with*. Three sources:

1. **Canonical person record** — one per realm `sub`: canonical email, display
   name, avatar, verified handles. Keycloak is the identity *anchor* (source of
   truth); a **Citus directory projection** makes it queryable by apps.
2. **Group membership index** — derived from the relationship registry
   (on-chain per account-and-key-model); a Citus projection makes it queryable.
3. **Explicit contacts** — the only truly stored part: user-initiated edges
   ("these are my people") + labels/notes. Per-user, small, private, owned by
   the user — part of their world-doc, encrypted at rest with the user's key,
   migratable.

**Authorization falls out of the group model.** No global contacts table with
row-level ACLs. Contact visibility = *group membership + that group's own
governance*. Email sees the people in your mail groups, chat sees chat groups,
projects see project members — one filter rule, no per-app contact sync.

## 3. Privacy tiers (the group setting)

Privacy lives on the **group**, not on the contact record:

| Tier | Visibility | What apps render |
|---|---|---|
| open | member list is directory-public | full member list in the Citus projection |
| members | only members see the member list | members see members; outsiders see nothing/count |
| hidden | membership *provable but not enumerable* | nobody can list; a member can prove "I belong, role Y" |

The projection is a filtered view of the same registry — flip the setting, the
view narrows. No data migration, no re-encryption. The **Safe's governance is
the ACL**, everywhere, automatically.

**Enumeration vs verification (the crypto point).** Email doesn't need to
enumerate your group — it needs to verify "this sender is a member of group X
with role Y" (a predicate). Hidden groups commit member **zk-badges** on-chain
(existing pattern); anyone can *verify* a claimed membership while nobody can
*list* the membership. No FHE, no vaults, no merkle forest of contacts.

## 4. Seats: the universal membership primitive

Every membership carries presentation:

```
seat = { sub (private, never rendered),
         alias: "Harvest Coordinator" | "Robert",
         roles: [...],
         visibility: "role-only" | "alias" | "canonical" }
```

Email, chat, projects, video calls render the **same persona** because they
read the same seat record — "approve as member of Cold Storage Co-op — 2-of-3"
works identically in a mail group, a Matrix room, and a project. The same
person is "Robert" in the family group and "Coordinator" in the farm group;
groups never see each other's aliases unless a seat is shared. A seat *is* a
membership, with presentation attached. (Stalwart's role mapping
`defaultUserRoleIds`, roles b/c/d/e, is the precedent already live.)

## 5. Finance through the rule

The Safe holds money truth on-chain (see private-treasury-guards-ledgers.md).
The world-doc holds the **experience** of finance, filtered by seat:

- **Views** of each group treasury — member-only balances stay member-only;
  hidden groups show nothing (the doc stores *nothing*, renders
  "balance: private" from a predicate)
- **Pending approvals** — the cross-group "needs your signature" inbox
- **Timelocks in flight** — "this withdrawal becomes effective in 6 days"
- **Entitlements** — what you're entitled to see/claim across groups
- **Proofs, not balances** — cached zk-proofs / signed statements so the UI
  shows *verified* numbers without re-querying the chain per render

## 6. Composition & lifecycle

- **Sources:** Keycloak (identity), on-chain registry (relationships, seats),
  app DBs (plane, nocodb, stalwart, matrix...), the treasury chain (finance
  proofs), the user's explicit-contact store
- **Builder:** a world-doc service (new; coop-api is the natural aggregator
  today) recomputes each user's doc on deltas; apps push "your base list
  changed" events via the event bridge
- **Filter:** the doc only contains what the user's group settings allow —
  hidden groups never leak into it
- **Survival:** contacts recompute from surviving sources after app death or a
  split; explicit edges + seat presentation travel with the user's doc

## 7. Open decisions

1. **Seat as universal primitive vs opt-in layer** — seats on every membership
   (aliases automatic everywhere) vs personas retrofit later. Recommendation:
   universal; it's the same data shape either way.
2. **Finance store of record** — Safe on-chain as the sole truth with the doc
   100% derived, vs some per-user financial state (entitlements, personal
   allowances) living off-chain too.
3. **World-doc builder placement** — new service vs coop-api module; the
   first consumer (contacts) decides.
