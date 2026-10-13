# Member-scoped app access — Plane, NocoDB, ERPNext, Temporal

Status: design · Oct 2026 · Builds on `group-scoping.md` (the `resource_scopes`
primitive), `byo-inference-and-group-scoped-agents.md` (group principal, the MCP
gateway as the acting surface), and `delegation-and-session-keys.md` §5 (mint a
scoped credential — never hold a blanket one).

## 1. The rule

**A member's access to an app is the set of app resources their groups own.**
coop-api never holds an app credential that can act on its own. Every call is made
as the member, and the app's own permission model is the enforcement point.

Corollary, stated as a prohibition: **no service identity, ever.** *(Not amended — but
narrowed in scope 2026-10-12: this prohibits a credential that can act **on its own** or
**across groups** (a blanket credential). A **group-held service account** is a different
object and is allowed under a three-part test — authority derives from exactly one group's
grants, blast radius is one group, and it is granted/revoked by group acts and logged. See
`group-operated-stack.md` §9 and **D-45**. If it can act for more than one group, it is the
thing this paragraph forbids.)* If an app cannot
be called as the member, it is not wired — it is not wired read-only "for now",
because a read-only blanket credential is still a blanket credential, and the
read-only/write distinction is one config edit away from being wrong.

## 2. The two existing halves

The model is mostly already built; what varies is enforcement.

**The resolver** (who the member is): `coop_my_seats()` → `group_members.roles` →
`roles → role_grants → grants`. Exposed today as the `list_my_groups` /
`list_my_grants` MCP tools. This is the authoritative answer to "which groups does
this member have permissions on".

**The map** (which app resources those groups own): `resource_scopes`
(`group_id`, `app`, `resource_key`, `scoped_by`) — Citus `irlcoop`, one row per
group-owned resource. `app` ∈ `plane | nocodb | docs | files | minio | matrix |
freeswitch | postiz | ...`; `resource_key` is the app's own id (Plane project id,
NocoDB base id, MinIO key prefix). Populated live: `plane` 1, `freeswitch` 4,
`postiz` 3, `matrix` 1, `journey-app` 3.

Together: **member → groups → `resource_scopes` rows for app X → the exact set of
resources the member may touch.** Everything below is about enforcing that set at
each app.

## 3. Runtime identity: no owner connection for member-facing work (BUILT)

**The recipe (verified against the live DB).** coop-api connects as `coop_app`
(LOGIN, `NOBYPASSRLS`, NOT the table owner) and each member-facing transaction does:

```sql
BEGIN;
SET LOCAL ROLE coop_m_<sub8>;                 -- rights: table grants + grp_* USAGE
SELECT set_config('app.sub', '<sub>', true);  -- identity
...
COMMIT;
```

Verified: `coop_app` + `SET LOCAL ROLE coop_m_17bd43c3` → the member sees their 5
Plane resources; a member of no group sees 0; `coop_app` with no role set sees 0
("no identity"). The owner connection is out of the request path.

**Why identity is still `app.sub` and NOT the role — do not "fix" this.** The RLS
helpers (`coop_is_member`, `coop_my_seats`, `coop_can_view_group`) are SECURITY
DEFINER *by design*: they must read `group_members` without re-entering that table's
own policy (which would recurse). Inside a definer function `current_user` aliases to
the DEFINER (`coop_rls`), so a role entered via `SET ROLE` is INVISIBLE, and
`session_user` is `coop_app` (absent from `coop_member_role`). So `coop_role_sub()` —
keyed on `session_user` — returns NULL and `coop_current_sub()` falls back to
`app.sub`. **The ROLE supplies the RIGHTS; the GUC supplies the IDENTITY.**

That is also why the original design used per-member CERTS (a cert makes
`session_user` the member). Worth being clear-eyed: a multi-tenant coop-api would
hold every member's cert, so a compromised app can impersonate either way — the cert
model buys no extra security here while costing per-member key custody.

**What the decision actually enforces** is that the app holds no credential BROADER
than the union of the members': `coop_app` cannot read a row RLS would hide, cannot
bypass RLS, and can only enter member roles. The `coop` owner connection can do all
three, so it is confined to boot DDL/ops.

**AS BUILT (verified live).** `db.ts` now has two pools: `ownerPool` (boot DDL/seed
only, and it is `end()`ed immediately after so nothing owner-level lingers) and
`pool` → `coop_app`. `withIdentity(sub, fn)` does `BEGIN; SET LOCAL ROLE coop_m_<sub8>`
(when `coop_member_role` maps the sub) `; set_config('app.sub', sub, true); … COMMIT`.
Rollback switch: `COOP_DB_MEMBER_USER=coop`.

Result: `pg_stat_activity` on `irlcoop` shows **only `coop_app`** — the owner
connection no longer exists at runtime, including the Temporal worker's sweep query.

Three things the narrower role exposed, all fixed:

1. **~22 tables had implicit owner access.** The grants are split by RLS status,
   because the safety argument differs: FORCE RLS tables get broad grants to
   `coop_member` (the policies are the real gate, so an over-grant cannot leak a
   row), catalogue tables get SELECT only, and **`proposals` / `votes` carry NO RLS
   — so they are granted to the APP ROLE ONLY.** Granting them to `coop_member`
   would let any member's *direct* connection (members hold LOGIN roles for cert
   auth, used by NocoDB) write another group's governance rows. **TODO: give
   proposals/votes RLS like the rest.**
2. **The Temporal worker is a SECOND host process importing the same `db.ts`**
   (`npm run worker` → `ts-node src/temporal/worker.ts`, started by
   `stack-up-hosts.sh`). Restarting coop-api alone leaves the worker holding an
   owner connection — it must be restarted too, or the owner connection only
   *appears* gone.
3. New members must be granted into `coop_app`
   (`infra/scripts/provision-member-certs.sh`), or the app cannot enter their role.

Provisioning by superuser is fine and established (`psql_super() → docker exec -u
postgres`); it is the RUNTIME identity that must be the member.

## 4. No mirrors of app data (decided)

A coop-side mirror of an app's data would have to be filled by a privileged read
of that app's database — a blanket credential in disguise — and it silently goes
stale behind the app. **The app is modded to accept the member's identity
instead** (the NocoDB gate-SSO pattern), so the app reads its OWN data and scopes
it to the member. `coop_my_resources(app)` remains the single resolution function
for "which resources do this member's groups own"; it is a resolver, not a copy.

## 5. Per-app enforcement

| app | resource identity | enforcement seam | state |
|---|---|---|---|
| **NocoDB** | base id | `app.sub` identity injection per query → Postgres RLS (reads **and** writes; the 2026.08.5 prototype-level fix is what made writes carry the identity) | **seam exists.** Per-user base visibility must be enforced (`nc_base_users_v2` grants, else the workspace `roles != 'no-access'` fallback leaks every base) |
| **Plane** | project id | `projects.group_id` (now SET for the group-owned projects) + per-member scoped **VIEWS** in the plane DB (`plane_projects__<sub>`, provisioned by `infra/scripts/provision-plane-views.sh`). The view is a WHERE clause on Plane's own rows — no mirror, no copy — and the member's group list is baked in at creation, exactly like `%SUB%`. **Data path BUILT + verified** (e2e 5 / project-member 1 / no-group 0). The **app-side** filter (Plane's own UI/API refusing non-group projects to a member) is still to build — see §8 item 1 | data scoping done; app-side mod pending |
| **ERPNext** | Frappe company / doc | Frappe's own users + roles. **A direct Postgres source BYPASSES RLS** (already flagged for Frappe Insights) — so ERPNext must be reached through its API, never through a DB source | not started |
| **Temporal** | workflow run | **no group dimension exists**: workflows are system sweeps (`deliverySweep`, `digestSweep`, `postizSyncSweep`, `tier2Sweep`, `materializeContributionWorkflow`) taking `eventId`/`batchSize`/`olderThan`, never a group. Scoping "Temporal info by group" requires adding a group identifier to each workflow at start (a search attribute, or a workflow-per-group shape) | needs building first |
| **TwentyCRM** | — | — | **NOT DEPLOYED** — parked intent only (`local-ai-chat.md`), no container exists |

## 6. Temporal: what "scoped to groups" requires

Today there is no group-scoped Temporal *info* to expose — the workflows are
coop-wide sweeps, and only `postizReconcileGroup` even receives a group id, as an
internal loop step. Two shapes, in preference order:

1. **Search attribute** — attach `GroupId` (and probably `Sub`) when starting a
   workflow, then list/query by it. Cheap, keeps the sweep shape, and makes the
   existing runs scoped retroactively only where the attribute was set.
2. **Workflow per group** — start `postizReconcileGroup`-style workflows per group
   so the workflow id itself carries the scope. Cleaner tenancy, more workflow
   objects, and each still needs the attribute for querying.

Either way the exposure surface is a read tool that lists runs filtered to the
caller's groups — never a raw Temporal UI handed to members.

## 7. The acting surface

Access is exposed through coop-api's MCP gateway, so the standing invariants apply:

- **Grant-gated**: a tool declares `grant` and is hidden *and* refused without it.
- **Upstreams are default-deny**: an upstream must declare `public: true` to be
  visible to an anonymous caller, and is otherwise member-only (and optionally
  grant-gated). Listing and calling enforce the same policy — hiding a tool is not
  access control.
- **Anonymous callers get no member-local tools** at all.

## 8. Build order

0. **Runtime identity FIRST** — coop-api stops using the `coop` owner connection for
   member-facing work; member-facing queries authenticate as `coop_m_<sub8>` so
   `coop_role_sub()` supplies the identity. Every later item inherits whatever
   identity the request runs as, so this comes before any app work.
1. **Plane** — **DONE, both halves.** Data scoping (`projects.group_id` set,
   per-member views provisioned, group-owned projects made `network=0`) and the
   app-side filter (BUILT + verified through Plane's own project-list view).
   REMAINING: nothing but a browser E2E on a fresh coop login.

   **The seam is proven end-to-end (no Keycloak work needed).** Plane's OIDC does
   NOT point at Keycloak — `apps/api/.env` sets `OIDC_ISSUER=https://api.irl.coop`,
   i.e. Plane authenticates against **coop-api**, whose `userinfo` already returns
   the member's seats `{id, slug, name, roles}` re-resolved live from the DB on
   every call. Keycloak holds zero groups and the plane client has no protocol
   mappers; none of that matters, because the token Plane reads is ours. `g.id` was
   added to `getGroupSeats` (`apps/coop-api/src/db.ts`) so the seats carry the UUID
   that matches `projects.group_id` — verified through the edge (Cold Storage
   Co-op = `5e69dbfd-…` present in e2e's seats).

   **Because the access token is NOT persisted** (the OIDC callback only opens a
   Django session — `authentication/views/app/oidc.py`), Plane cannot call userinfo
   per request. So the ids are captured **at login**, from the userinfo response the
   provider already fetches (`authentication/provider/oauth/oidc.py`), and refreshed
   on each login — staleness bounded to the session. The patch (BUILT):

   - `db/models/user.py` — `coop_group_ids` (JSONField) + `db/migrations/0124_user_coop_group_ids.py`.
   - `authentication/provider/oauth/oidc.py` — parses `groups` from the userinfo
     response into the group IDs and persists them next to the existing `user.sub` write.
   - `app/views/project/base.py` — `coop_group_scope(user)` helper applied at all
     THREE sites: `list_detail` (guest + member branches), `list` (same two), and
     `retrieve`'s membership check (a group-owned project is readable without a
     ProjectMember row).
   - Rebuilt `plane-api` + `plane-migrator` (they are SEPARATE images — building
     only `api` leaves the migrator on stale code, which then reports "No
     migrations to apply"), migrated, recreated the api container.

   **VERIFIED** through Plane's real project-list view (`/api/workspaces/coop-test/projects/`):
   with the group → 5 projects, without → 4. The extra one (`TestProj1`) is a
   project the member has NO ProjectMember row for and sees only because their group
   owns it. **Browser E2E DONE** — `infra/scripts/journeys/journeys/plane-scope.mjs`
   (in `run.mjs`'s `browserJourneys`) signs in at the fleet gateway, rides Plane's
   zero-click SSO, and asserts the scoped list both through the in-page API and the
   rendered DOM: 5 projects, `TestProj1` among them, 5/5 rendered.

   **Plane as an MCP upstream — feasibility PROVEN.** No new infrastructure is
   needed: Plane's image already ships `cryptography` + `PyJWKClient`, `User.sub`
   maps the member, and `coop_group_scope` is reusable — a coop JWT verified against
   coop-api's JWKS resolves to the member and yields the identical scoped list
   (probe: kid `2yMKHsAb8U…`, sub → `e2e-test`, `coop_group_ids` 8, 5 projects).
   coop-api's MCP gateway already **forwards the member's `Authorization` header
   upstream**, so a Plane MCP server receives the member's own token. Needed:
   (1) a `CoopJWTAuthentication` DRF class (modeled on the existing 52-line
   `APIKeyAuthentication`) in the app API's `authentication_classes`; (2) a small
   `POST /mcp` JSON-RPC service (in-stack pattern: rag-api's `routes/mcp.py`)
   exposing Plane tools and passing the token through; (3) register it in
   `MCP_UPSTREAMS` non-public, so the gateway's default-deny requires an
   authenticated member. **Rejected**: Plane's v1 API (`APIKeyAuthentication` — a
   service credential, and it would NOT apply `coop_group_scope`), and holding
   per-member Plane sessions server-side (custody). The auth class makes the whole
   app API member-addressable, not just MCP, and can refresh `coop_group_ids` live
   from userinfo per request — which also removes the login-time staleness above.

   **AS BUILT + VERIFIED.** (a) `apps/api/plane/authentication/coop_jwt.py` —
   `CoopJWTAuthentication`: verifies the coop JWT against coop-api's JWKS, maps
   `User.sub`, refreshes `coop_group_ids` from userinfo through a 60s TTL cache, and
   returns `None` for tokens that are not ours so browser sessions still work. Wired
   as `[CoopJWTAuthentication, BaseSessionAuthentication]` on `BaseViewSet` and
   `BaseAPIView`; `api` image rebuilt. Verified through the edge: `GET
   /api/workspaces/coop-test/projects/` with ONLY a coop JWT → 200, the same 5
   projects; no token → 401 (no hole opened). (b) `infra/build/images/plane-mcp/`
   (Dockerfile + `server.mjs`, Node stdlib — no deps) → `irlcoop/plane-mcp:0.1.0`,
   app spec `plane-mcp.yaml` (host bridge :8003, `role: support`), registered in
   `instance.yaml`, and added to `MCP_UPSTREAMS` in `apps/coop-api/.env` as
   **non-public**. Verified through the gateway: a member's `tools/list` exposes
   `plane.list_projects` + `plane.list_work_items`; an anonymous `tools/list`
   exposes NEITHER (default-deny holds); `plane.list_projects` as the member returns
   the same 5; an anonymous call is refused `-32002`; `plane.list_work_items` returns
   real work items. Cosmetic gaps: `group_id`/`visibility` come back null (Plane's
   `ProjectListSerializer` doesn't carry them) and work-item `state` is null (field
   name differs).

   **Writes (`create_issue`) — and the permission fix they required.** Plane's
   PROJECT-level `allow_permission` gate (`app/permissions/base.py`) admits only a
   `ProjectMember` row, so a group-scoped member could SEE a group's project but be
   403'd acting on it — reads and writes disagreed. Fixed by adding a clause: a
   project owned by a coop group the member holds a seat in confers **MEMBER-level**
   rights, and only when `MEMBER` is among the action's allowed roles, so
   admin-only actions stay admin-only. Verified both directions: `create_issue` in
   TestProj1 (group-owned; the member has NO ProjectMember row) → created OK; the
   same call with the member's `coop_group_ids` emptied → **403**, restored → **201**.
2. **NocoDB** — **leak found and fixed; enforcement is now self-verifying and runs
   at bring-up.** NocoDB has no group concept (unlike Plane's `projects.group_id`):
   access is per-base explicit grants (`nc_base_users_v2`, maintained from group
   membership by `sync-base-members`) **plus a workspace-role fallback that includes
   EVERY base** for any user whose `workspace_user.roles != 'workspace-level-no-access'`.
   That fallback is the leak. `enforce-nocodb-visibility.sh` normalizes members to
   no-access and the super admin to owner — but it had **drifted**: a real member
   (`emmydeeznutz@irl.coop`) sat at `workspace-level-creator`, so every base was
   visible to them despite holding one legitimate explicit grant. Re-running closed
   it (all members no-access, one owner). The script now ends with an assertion that
   exits non-zero if any non-super user holds a workspace role, and `stack-up.sh`
   runs it as step 1.5 (`fail` on drift, so it surfaces in the boot state rather
   than silently in a member's base list). **Remaining**: prove the isolation
   end-to-end through the app (a member cannot reach a base their groups don't own)
   rather than only at the DB-role layer.
3. **Temporal** — add the group dimension first (§6), then a read tool.
4. **ERPNext** — API-only, per-member Frappe identity; never a DB source.
5. **TwentyCRM** — deploy first; nothing to scope until then.

## 9. Open questions

- Does a group own a *Plane project* 1:1, or can two groups share one project? The
  `resource_scopes` shape allows N, and Plane's `projects.group_id` allows 1 —
  pick one, or keep both (scope row = authoritative, column = cached).
- For hidden groups (`group-scoping.md` §3), the member list is commitment-based,
  so resource resolution must read through proofs rather than enumerate seats.
  Membership-scoped app access inherits that constraint.
- NocoDB's group→base shape is already designed in `nocodb-one-base-per-group.md`
  — that doc, not this one, is authoritative for the NocoDB base model.