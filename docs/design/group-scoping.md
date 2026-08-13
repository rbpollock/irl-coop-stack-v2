# Group Scoping & Privacy Tiers — Spec

Status: design · Aug 2026. Companion to world-doc-and-contacts.md and
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
