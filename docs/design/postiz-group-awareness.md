# Postiz Group-Awareness — Design

Status: fork + sync workflow built + verified (2026-08-22, `irlcoop/postiz:2026.08.2`). Companion to group-scoping.md and
telephony-trunking.md. Postiz becomes a group-scoped social-scheduling surface:
its `Organization` is a group's workspace, its membership is a projection of
`group_members`, and its channels (`Integration`) belong to the group.

## 1. The bridge (already live, proven)

Postiz's generic-OIDC login writes `User.providerId` = the Keycloak realm
subject — the SAME value in `group_members.sub`. Verified against the live DBs:

| irl.coop group | roles | sub | → Postiz org (providerId) |
|---|---|---|---|
| Cold Storage Co-op | [owner] | `17bd43c3…` | e2e-coop (SUPERADMIN) |
| happy days | [owner] | `0970e369…` | my company (SUPERADMIN) |

So "group-aware Postiz" is not a new identity — it is making Postiz's
`Organization` + `UserOrganization` a **Layer-2 projection** of groups (the same
primitive as Plane workspaces, NocoDB bases, Matrix rooms). The link row:

    resource_scopes { group_id, app:'postiz', resource_key:'<postiz org id>' }

## 2. Entity + role mapping

| irl.coop | Postiz |
|---|---|
| `group` | `Organization` |
| `group_members` (seat) | `UserOrganization` (`userId` → `User.providerId`) |
| group roles | `UserOrganization.role` (see §7 for the fork) |
| group → org link | `resource_scopes` (app=postiz) |
| group channels | `Integration` (`organizationId` = group org) |

Postiz's `Role` enum today is `SUPERADMIN | ADMIN | USER`. The group roles are
owner/founder, admin, member, inviter, observer — richer. §7 extends Postiz to
preserve them 1:1; until then the sync uses a 3-tier stopgap mapping.

## 3. Principle — projection, not fork (one bounded exception)

Stock Postiz image; the sync lives OUTSIDE it (a Temporal workflow writing the
projection). The org/membership tables are rebuildable from group state — drop
them and the sync reconstitutes them. The ONE exception is the role model
(§7): Postiz has no tier for inviter/observer, so a bounded fork extends its
`Role` enum and the role-gates that read it. Everything else stays additive.

## 4. Flow 1 — Provision a group's Postiz workspace

Trigger: a group opts into Postiz (or group-create when Postiz is a declared
group app). One event, idempotent, convergent:

1. coop-api enqueues the `postiz-sync` Temporal workflow for the group.
2. The workflow ensures `Organization { id, name = group.name, … }` exists
   (upsert keyed by the `resource_scopes` row — no double-create).
3. Writes `resource_scopes { group_id, app:'postiz', resource_key: org_id }`.
4. Seats the group owner: `UserOrganization { userId: owner's User.id, role:
   SUPERADMIN }`.

The owner's `User` row is created from the Keycloak profile (sub → email) if the
owner has not SSO'd into Postiz yet — so first login lands in the group's org,
not a fresh "company name" registration.

## 5. Flow 2 — Membership sync (Temporal)

Trigger: `group_members` mutation (seat / unseat / role change). coop-api
enqueues the `postiz-sync` workflow on every such write (outbox + a periodic
convergent sweep — the `ensureGroupSeat` "run on every signin" pattern).

Per seat `(sub, roles[])`:
1. Map roles → Postiz role (§7; 3-tier stopgap until the fork).
2. Ensure the `User` row exists (`providerId = sub`; email from the Keycloak
   admin lookup; `providerName = GENERIC`; `activated = true` — the realm
   already verified the email).
3. Upsert `UserOrganization { userId, organizationId, role, disabled=false }`.
   On unseat: `disabled = true` (preserve history, revoke access) or delete —
   decision TBD (see §9).

Convergent + idempotent: re-running the workflow for a group reaches the same
rows, so a missed event self-heals on the next sweep.

## 6. Flow 3 — Authorization + the group selector

Postiz's OWN role checks enforce org-scoped actions (channel add, schedule,
settings) — no fork needed. The sync keeps `UserOrganization.role` correct, so
Postiz "just works".

The group selector already exists: Postiz's org-switcher (the workspace
dropdown) lists `UserOrganization` orgs and tracks the current one via the `org`
cookie (`getOrgFromCookie`). Once groups sync to orgs, the switcher IS the group
selector — "acting as happy days" = selecting the happy-days org. Many groups =
many orgs, which Postiz's many-to-many membership already supports.

## 7. Role extension (the bounded fork)

Postiz `Role` enum → add the irl.coop granularity:

| irl.coop role | Postiz role | stopgap (pre-fork) |
|---|---|---|
| owner / founder | SUPERADMIN | SUPERADMIN |
| admin | ADMIN | ADMIN |
| member | USER | USER |
| inviter | INVITER (new) | ADMIN |
| observer | OBSERVER (new) | USER |

Decision (built 2026-08-22): **additive, not rename** — `SUPERADMIN`/`USER` stay
as-is (no data migration, upgrade-safe); `INVITER` + `OBSERVER` are added to the
enum. The member-management level map (`organization.service.ts`) treats
INVITER≈ADMIN (level 1) and OBSERVER≈USER (level 0). OBSERVER read-only
enforcement + UI role labels are follow-ons. The fork also adds the S3/MinIO
storage backend (see §7b).

Fork scope (kept minimal, additive, upgradeable):
1. Prisma enum migration + the `role`-gated guards in the backend that read
   `SUPERADMIN`/`ADMIN`/`USER` — extend to the new values.
2. Rebuild a custom `irlcoop/postiz` image (the `nocodb-custom-build` recipe:
   stock base + layered bundle), NOT a wholesale fork.
3. UI: role labels + any role-gated affordances.

The stopgap lets Phase 1 ship group-aware scheduling end-to-end while the role
fork lands separately.

## 7b. Storage fork (S3/MinIO)

Stock Postiz only ships `local` and Cloudflare R2; R2's endpoint is hardcoded
(`https://${accountID}.r2.cloudflarestorage.com`). The fork adds a
`STORAGE_ENDPOINT` override (path-style + configurable region) in
`cloudflare.storage.ts` + `r2.uploader.ts`. Declarative wiring:
`STORAGE_PROVIDER=cloudflare`, `STORAGE_ENDPOINT=http://172.17.0.1:9000`,
`CLOUDFLARE_ACCESS_KEY=postiz-s3` (derived `minio.postiz-s3`), public media URL
`https://s3api.<domain>/postiz`. Bucket + user are provisioned idempotently by
the `postiz-minio-init` sidecar (public-read via `mc anonymous set download`).

## 8. Build order

- **Phase 1 — sync + provisioning**: ✅ DONE (2026-08-22). `postizSyncSweep`
  Temporal workflow in the coop-api worker (self-scheduling, 30s): opts-in via a
  `resource_scopes` row `(group_id, 'postiz', group_id)` — the group UUID IS the
  Postiz Organization id (deterministic link). Reconciles org + seats (1:1 role
  mapping, email from profiles → Keycloak admin fallback) and disables stale seats
  on unseat. SECURITY DEFINER readers `coop_postiz_opted_groups` /
  `coop_postiz_seats` in coop_rls.sql. Verified: opt-in → org + SUPERADMIN seat;
  seat → USER; unseat → disabled=true.
- **Phase 2 — role fork**: ✅ DONE (2026-08-22). `Role` enum + guards extended
  (INVITER/OBSERVER), `irlcoop/postiz:2026.08.1` image built + deployed, S3/MinIO
  storage wired (bucket `postiz`, user `postiz-s3`). Verified: 5-role enum in DB,
  edge/OAuth regression, S3 write path. Remaining: OBSERVER read-only enforcement
  + UI role labels.
- **Phase 3 — zero-click SSO + skip onboarding**: ✅ DONE (2026-08-22).
  `irlcoop/postiz:2026.08.2` auto-redirects the login/register pages straight to
  the OIDC provider (zero-click) and makes GENERIC (SSO) users skip the
  `/launches` onboarding wizard — their group org + seat come from the coop-api
  sync. Synced users already skipped onboarding (`User.providerId` = Keycloak
  `sub`); this closes the brand-new-user gap.

## 9. Open decisions

1. **Unseat semantics**: `disabled=true` (revoke access, keep history) vs delete
   the `UserOrganization` row. Rec: disable — CDR/audit keeps the member's
   history.
2. **Personal group**: does the personal (self) group get its own Postiz org,
   or is the personal account Postiz-native (no org)? Rec: personal group →
   personal org, 1:1, for symmetry (the "group is the primitive" rule).
3. **User pre-provisioning**: create the Postiz `User` row eagerly (from the
   Keycloak profile) vs lazily (on first SSO). Eager matches auto-provisioning
   but couples the sync to Keycloak admin lookups; confirm the User table's NOT
   NULL columns before writing eager rows.
4. **Channels ownership**: when a member leaves, do their personal social tokens
   (Integrations) stay with the group org or leave with them? Rec: integrations
   are group-owned; tokens rotate on unseat.
