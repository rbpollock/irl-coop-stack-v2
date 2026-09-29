# Seat holder is a Safe — D-16 as implemented

Status: sprint spec · 2026-09-29 · implements tentative decision D-16.
Supersedes the "a seat's holder is a Keycloak subject" assumption throughout the
group model. Companion to `account-and-key-model.md` (the relationship framework) and
`group-scoping.md` (the projection).

## 1. The decision

A seat's holder is **a Safe**, not a person:

- a **person's** seat is held by that person's **1-of-1 Safe**;
- a **group's** seat is held by **another group's Safe**.

One mechanism covers both. A collective containing several farm coops is therefore not
a special case: it is a group in which several groups' Safes hold seats.

## 2. Why this is the right key

The model already said every actor is a Safe (`group-scoping.md` §1: "a group is a
Safe. Individual = 1-of-1; group = N-of-M"), and that relationships are declared rather
than inherited. Keying seats to a Keycloak subject contradicted both: it made the
person — not their account — the unit of membership, which is precisely why
group-of-groups was not representable.

Keying seats to a Safe makes the group graph a graph of Safes, which is what the
on-chain truth layer and the (unbuilt) edge registry both assume.

## 3. Schema

`group_members` gains two columns. `sub` is **kept** — it is the identity that
*exercises* a person seat, and it remains the resolution fallback (§4.3).

| Column | Meaning |
|---|---|
| `holder_kind` | `'person'` or `'group'`. Default `'person'` (so existing rows are valid). |
| `holder_safe` | The holder's Safe address. Nullable — see §4.3. |
| `sub` | Unchanged. The Keycloak subject for a person seat; `NULL` for a group seat. |

Index: `group_members (holder_safe) WHERE holder_safe IS NOT NULL`.

**Backfill:** every existing person seat gets `holder_safe` from that member's 1-of-1
Safe (`groups.safe_address WHERE kind='personal' AND created_by = sub`), where it exists.

## 4. Resolution rules

### 4.1 What may the caller act as

`coop_current_safes()` returns the set of Safe addresses the caller may act as:

1. their own 1-of-1 Safe, then
2. transitively, the Safe of any group whose seat is held by a Safe already in the set
   — bounded to a depth of 8, which both terminates legitimate nesting and stops a
   cycle (A seats B, B seats A) from recursing forever.

This is what lets a member co-op's people act in the collective their co-op joined.

### 4.2 Access flows from a declared seat; rights do not

This is the point that keeps D-16 consistent with *"nothing is inherited, everything is
declared"*:

- **Access** flows from the seat, because the seat **is** the declaration. A co-op
  holding a seat in a collective is the declared fact; acting-as the co-op follows from it.
- **Governance and economics rights** (veto, reserved powers, funding allocations) do
  **not** flow. They are terms on the relationship record and must be declared
  separately. A collective does not acquire authority over a member co-op by that co-op
  holding a seat.

**How that splits in the schema — two predicates, deliberately:**

| Predicate | Traverses a group seat? | Used for |
|---|---|---|
| `coop_is_member(gid)`, `coop_my_seats()`, `coop_current_safes()` | **Yes** | visibility — reading a group, listings, the OIDC `groups` claim |
| `coop_is_owner(gid)` and every write policy | **No** — direct person seats only (`coop_own_safe()`) | administration — seating, scoping resources, settings, proposals, votes, dues |

Concretely: a member of a co-op that holds a seat in a collective can **see** the
collective; they cannot **administer** it, and they do not thereby gain a vote in it. A
co-op's representatives act through their own person seats carrying explicit roles.

The application's own membership gates (`isOwner`/`isMember` in `groups.ts`, and the
gates in `decisions.ts` and `dues.ts`) are **direct-seat by design** and were left
unchanged for exactly this reason. A future reader must not "fix" them by pointing them
at the traversing helper.

### 4.3 The bootstrap hole, and the stated rule

`coop_ensure_personal_group()` creates a member's personal group with `safe_address`
**NULL**; the personal Safe is deployed and stamped later. So a seat cannot always be
keyed to a Safe that exists yet.

**Rule:** a person seat whose `holder_safe` is NULL resolves through `sub` — today's
behaviour, unchanged. The backfill (§3) fills `holder_safe` once the Safe exists.

Consequence, stated plainly: until a member's own Safe is deployed, their membership is
enforced by the older person-keyed path. That is a deliberate, temporary accommodation,
not a second model. **The durable fix is to deploy the personal Safe at signup rather
than later** — recorded as follow-up work, not done here.

## 5. Enforcement

`coop_is_member(gid)` is true when a seat exists on that group held by a Safe the caller
may act as, **or** a person seat with a NULL `holder_safe` whose `sub` is the caller.
`coop_is_owner` is the same predicate with an `owner` role on the seat. `coop_is_creator`
and `coop_can_view_group` are unchanged.

These functions stay `SECURITY DEFINER` owned by a BYPASSRLS role, as before — the
recursive walk reads `groups` and `group_members` and must not re-enter the policies it
implements.

## 6. API surface

| Endpoint | Change |
|---|---|
| `POST /api/v1/groups/:id/members` | Accepts either `{ sub }` (a person) or `{ group_id }` / `{ holder_safe }` (a group). A group holder is stored with `holder_kind='group'`, `holder_safe` set, `sub` NULL. |
| `GET /api/v1/groups/:id/members` | Returns `holder_kind` and `holder_safe`, and the held group's name/slug for group holders — so a collective can list its member co-ops. |
| `GET /api/v1/groups` | Unchanged shape; now also returns groups the caller reaches through a group seat. |

## 7. What this does not do

- It does **not** build the on-chain edge registry. Relationship *types*
  (`subgroup-of`, `sponsored-by`, `federated-with`) remain declared-only.
- It does **not** implement the ZK proof layer for hidden groups.
- It does **not** give a collective any authority over a member co-op (§4.2).
- It does **not** deploy personal Safes at signup (§4.3, follow-up work).

## 8. Definition of done

- [ ] Schema columns exist and the backfill has run.
- [ ] `coop_current_safes()` resolves the acting set, bounded, with a cycle to prove the bound.
- [ ] `coop_is_member` / `coop_is_owner` rewritten; RLS contrast test still passes.
- [ ] A group's Safe can hold a seat in another group via the API.
- [ ] A member of a co-op that holds a seat in a collective can read the collective.
- [ ] A co-op that holds **no** seat cannot read the collective; a cycle does not hang.
- [ ] Existing person-seat behaviour is unchanged (the journeys still pass).
- [ ] `REALITY.md` and `DECISIONS.md` updated to reflect the implemented state.