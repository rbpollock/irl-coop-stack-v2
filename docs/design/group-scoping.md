# Group Scoping & Privacy Tiers — Spec

Status: implemented (first slice) · Aug 2026. Companion to world-doc-and-contacts.md and
world-doc-virtual-workspace.md. Builds on the on-chain Safe-as-everything model
(account-and-key-model.md).

## 1. The one primitive

A **group is a Safe**. Individual = 1-of-1; group = N-of-M. `apps/coop-api/src/safe.ts`
already deploys Safes (`/api/safe/deploy`), so "create a group" and "deploy the
account Safe" are the SAME event — there is no second concept.

Two layers (per account-and-key-model.md):

- **Layer 1 (truth)** — the Safe's owner set + threshold. On-chain. Who can act.
- **Layer 2 (projection)** — a queryable registry in Citus `irlcoop` (empty today)
  that mirrors what apps need to render: members, seats, scoped resources.
  Rebuildable from Layer 1; dies nothing when dropped.

## 2. Three tables (Citus `irlcoop`, projection only)

```
groups
  id            uuid pk
  safe_address  text      -- the Safe IS the group's account
  name, description
  privacy       enum(open | members | hidden)
  created_at, updated_at

group_members                      -- one row = a seat
  group_id      → groups.id
  sub           text              -- Keycloak realm subject (private, never rendered)
  roles         text[]
  alias         text              -- presentation name in THIS group
  visibility    enum(role-only | alias | canonical)
  created_at, updated_at

resource_scopes                    -- a resource belongs to a group
  group_id      → groups.id
  app           text              -- plane | nocodb | docs | files | ...
  resource_key  text              -- plane project id, nocodb base id, minio key prefix, ...
  scoped_at, scoped_by (sub)
```

The plane `projects` table already carries `group_id`, `safe_address`, and
`network` (visibility) — the hooks exist in the app schema; this registry is what
joins them across apps.

## 3. Privacy tiers (enforced at the projection)

| tier | what a view returns |
|---|---|
| open    | member list + resources directory-public |
| members | members see everything; outsiders see count only |
| hidden  | nobody enumerates; a member can *prove* "I belong, role Y" (zk-badge, later) |

Same rule as world-doc-and-contacts.md §3: flipping `privacy` narrows the view,
zero data migration, zero re-encryption.

## 4. API surface (coop-api, `groups.ts`)

- `POST /api/v1/groups`            → deploy the member's Safe (wrap `safe.ts` deploySafe) + insert `groups`. Returns group + safe_address.
- `GET  /api/v1/groups`            → groups I belong to, with my seat.
- `POST /api/v1/groups/:id/members` → invite/seat (alias, roles, visibility).
- `POST /api/v1/groups/:id/resources` → scope a resource (app + key).
- `GET  /api/v1/groups/:id/resources` → scoped resources, filtered by privacy + my seat.
- `PATCH /api/v1/groups/:id`       → name/description/privacy.

## 5. Consumers

- **NocoDB**: `world_doc__<sub>` becomes a join over `group_members →
  resource_scopes → per-app projections` — group-scoped, not just per-user.
- **Plane**: `plane_user_view.sql` already selects `group_id`/`safe_address`/`network`;
  scoping resolves them through `resource_scopes` to the group's privacy tier.

## 6. First slice (build this, nothing more)

Greenfield today: Citus `irlcoop` is empty, no builder, `profile-store.ts` is a
JSON file marked "swap for Postgres when coop-api gets a real database." This IS
that database. Minimal vertical slice:

1. Citus `irlcoop`: create `groups`, `group_members`, `resource_scopes` (§2).
2. coop-api: `groups.ts` route module (6 endpoints), Postgres-backed.
3. Wire `POST /api/v1/groups` to the existing `safe.ts` deploySafe (the group row
   is created from the deploy result — single event, no divergence).
4. A `world_doc__<sub>` view in Citus joining the three tables (proves the
   projection end-to-end).
5. Verify: deploy a group as e2e-test → scope the plane "Cold Storage Co-op"
   project → read it back filtered by privacy tier.

Out of scope for this slice: zk-badges for hidden groups, on-chain membership
registry sync, UI polish, the full world-doc builder service.

## 7. Group ↔ Matrix rooms (design)

A Matrix room is a group resource — the same primitive as a Plane project or a
NocoDB base. The mapping is a `resource_scopes` row:

    app = 'matrix', resource_key = room_id

The appservice resolves `room_id → group_id` through this row, so events in the
room are scoped to the *room's* group (RLS) instead of the sender's personal
group.

### 7.1 Two ways a room gets scoped

- **Provisioned** — declared in the group template; the provisioning workflow
  creates the room AND writes the scope row in one event.
- **Adopted** — a member creates a room ad-hoc, then
  `POST /groups/:id/resources {app:'matrix', resource_key:room_id}` scopes it.

### 7.2 Privacy → room access

The group's `privacy` tier maps to Matrix room access at provisioning:

| privacy | visibility | join_rule | directory |
|---|---|---|---|
| open    | public     | public    | listed    |
| members | private    | invite    | unlisted  |
| hidden  | private    | invite    | unlisted  |

Federation is OFF on this homeserver, so "public" today means "any irl.coop
account" (itself open to join), not the wider Matrix federation. Enabling
federation later widens "public" with no room-config change.

### 7.3 Room creation keeps the appservice invisible

The appservice never joins or sends. To create a room without making
`@coop-api` the creator, the provisioning workflow uses the AS API with
`?user_id=<group-owner>` — impersonating the owner via `as_token` (the AS→HS
direction) — so the owner is the room's creator.

### 7.4 The irl.coop root group

`irl.coop` is the platform's root group — the "group of the whole." It is a
group like any other (same provisioning path), with one exception:

- **Deterministic Safe.** User-created groups use a random `saltNonce`
  (`freshSalt()`); the personal account uses a sub-derived deterministic salt.
  The root group uses a **fixed well-known salt** (`keccak256("irl.coop")`),
  so its Safe address is a stable platform constant that configs and contracts
  can reference — and it survives a `master.key` rotation (the salt is not
  derived from the secret).
- **Open by default** → its room is `visibility: public` + `join_rule: public`
  (visible and joinable by any irl.coop account).
