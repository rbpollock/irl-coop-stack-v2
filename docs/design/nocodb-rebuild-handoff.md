# NocoDB rebuild — handoff state (2026-09-16)

**Purpose:** pick-the-thread state for the next session. Everything verified is here; do not re-derive.
(The plan itself lives in `nocodb-rebuild-plan.md`; this is the *state*. The settled model is in
`nocodb-one-base-per-group.md`.)

## Settled architecture (north star — DO NOT re-litigate)

**One base per group; a person IS a group.** Every group (personal + collective) has exactly one base.
A member's "lens" *is* their `personal` group's base, which federates-reads across the bases of the
groups they belong to. "Focus one / pick / see all" = a scope dial (which group's base you're in, plus
cross-group federation). No "coop" category is ever asked.

## Visibility model — members see ONLY their own group bases (2026-09-18)

NocoDB's base list (`BaseUser.getProjectsList`) has TWO access paths:
1. explicit per-base grant (`nc_base_users_v2.roles`) — what `sync-base-members` maintains from group membership; and
2. a **workspace-level-role fallback** — any user whose `workspace_user.roles != 'workspace-level-no-access'` sees EVERY base in the workspace.

The fallback is the cross-tenant leak: at bootstrap (2026-08-13) three accounts were minted with workspace `owner` (legacy string), so their canonical member identities saw all 18 bases regardless of membership.

**Correct state (enforced by `infra/scripts/enforce-nocodb-visibility.sh`, idempotent):**
- members (canonical identities, org-level `viewer`/etc, NOT `%super%`) → `workspace-level-no-access`
- the super admin (broker identity `robertbrucepollockjr@gmail.com`, org-level `super`) → `workspace-level-owner`

Run the script after any bootstrap that mints workspace roles. Note the legacy value is bare `owner` (not `workspace-level-owner`); both demote to no-access under the `NOT LIKE '%super%'` rule and normalize the super to `workspace-level-owner`.

## DONE (verified + committed)

### Step A1 — role-as-identity (COMMITTED `cdcdfe3`)
`coop_member_role` + `coop_role_sub()` + `coop_current_sub()` in
`infra/compose/storage/scripts/coop_rls.sql`. **Role wins over `app.sub`.**

- `coop_member_role(role_name name PK, sub text, created_at, revoked_at)` — a Postgres ROLE that IS a
  member, revocable via `revoked_at`.
- `coop_role_sub()` = `SELECT sub FROM coop_member_role WHERE role_name = current_user AND revoked_at IS NULL`,
  **NOT SECURITY DEFINER** (a definer owned by coop_rls aliases `current_user`→coop_rls and never matches
  the caller). The table GRANTs `SELECT TO PUBLIC` (read-only role→sub metadata, no secret).
- `coop_current_sub()` = `COALESCE(coop_role_sub(), NULLIF(current_setting('app.sub',true),'')::text)`.
- **PROVEN live:** mapped role resolves to member-1 even when `app.sub` spoofed to member-2; revoked
  mapping falls back to `app.sub`. Three tests green.

### Fact-finding (same session) — NocoDB is NOT broken, it's built and wired
- `irlcoop` external source exists in `nc_integrations_v2` (connects as `coop` role → `irlcoop`).
- Bases render: "Coop Groups", "Projects", "Coop", "my base", "Base" — the confusing names the new model REPLACES.
- Identity-injection patch (image 2026.08.4+) is live (`x-forwarded-user` → `app.sub`).
- RLS scopes correctly ("4 rows no identity" = `privacy='open'` groups, by design). `coop` is non-superuser/non-BYPASSRLS.
- "List of errors" = 3 classes, NONE needs the rebuild: (1) 403 on orphaned bases ("my base"/"Base" lack
  `nc_base_users_v2` rows); (2) dashboard next-auth `client_fetch_error` on `/api/auth/session`; (3)
  Chatwoot 404 + iframe refusal — **FIXED (image 2026.08.11)**: the Chatwoot Nuxt plugin loads its SDK
  unconditionally, so `NC_DISABLE_SUPPORT_CHAT` was a no-op for the widget itself (it only gates the
  user-attribute init). Surgically removed the `loadScript(…/packs/js/sdk.js).then(…chatwootSDK.run…)`
  statement from the nc-gui chunk (was `B3Y9luKo.js`). Browser E2E: authenticated app has zero
  `chatwoot|X-Frame|sameorigin|woot-widget` console errors. If a chat is ever needed, it goes in Cinny
  (Matrix), not Chatwoot.

## DONE (this session) — A2 + A3 as ONE unit: cert + per-user connection

**Proven end-to-end (browser E2E + Postgres connection log + psql cert contrast).**

1. **Mint CA + per-member certs** — `infra/scripts/mint-member-cert.sh <role> [days]`.
   EC P-256 keys (the member's vault/passkey key class), cert CN = role name. Layout
   `infra/instances/dev/secrets/pg-client-certs/{ca,members}/` (gitignored). Minted for the
   two A1 test roles: `coop_test_rolemember1` → `17bd43c3…` (e2e-test), `coop_test_r1` →
   `e1f4489a…`.
2. **`coop_role_sub()` fix** — reads `session_user` (NOT `current_user`). Rationale proven live:
   the RLS helpers (`coop_is_member`/`coop_can_view_group`/…) are SECURITY DEFINER owned by
   `coop_rls`; inside them `current_user` aliases to `coop_rls`, so a cert-authenticated member
   never resolved. `session_user` is fixed at login (cert CN → role) and SURVIVES definer context.
3. **`coop_member` grant group** — NOLOGIN group holding the projection table grants (broad by
   design; FORCE RLS is the real gate) + SELECT on the catalog tables. Member roles get
   `GRANT coop_member TO <role>`; pg_hba matches `+coop_member`, so no per-member pg_hba edit.
4. **pg_hba + CA trust** — added `hostssl irlcoop +coop_member 172.21.0.0/16 cert` BEFORE the
   scram catch-all (scram fallback kept). `ssl_ca_file = pg-client-ca.crt` (copied into PGDATA,
   `ALTER SYSTEM SET`). `SELECT pg_reload_conf()`.
5. **NocoDB per-request cert** (image `2026.08.9`) — `CustomKnex.ts` now dispatches `irlcoop`
   queries to a per-role CERT-authenticated pool (`coopRolePools`, keyed by role; cert read from
   `NC_COOP_PG_CERT_DIR`). The wrapper resolves sub→role via `coop_member_role` (cached per
   request on the ALS store), then runs the query on that role's pool so `session_user == role`.
   Fallback: members without a cert, and transaction/write queries (pinned to one connection),
   keep the app.sub GUC injection. Idempotent prototype wrap (guard `__coopInjected`).
   Deploy: cert dir mounted ro into the container (`dev.volumes`) + `NC_COOP_PG_CERT_DIR` env.

**Proof (measured):**
- psql cert contrast — `coop_test_rolemember1` sees "Cold Storage Co-op" (NOT member-2's
  "Derived Slug Test"); `coop_test_r1` sees the inverse; `SET app.sub=<other>` ignored (role wins).
- Browser E2E (e2e-test via reset password) reads the `irlcoop` source → 6 groups.
- Postgres log: `connection authorized: user=coop_test_rolemember1 database=irlcoop SSL enabled
  (TLSv1.3)` from `host=172.21.0.4` (NocoDB) — the cert pool fired, distinct from the `coop`
  scram connections.

## Still on the plan (B and C, after A)

- **B1:** re-orient bases to one-base-per-group (replace the 5 confusing names).
- **B2:** federation read across a member's group-bases (the lens).
- **C1:** governed shape-migration (personal base → group base via proposal + threshold).

### Step B substrate — narrowed RLS views (DONE, this session)

Added to `coop_rls.sql` + applied live: 13 `security_invoker = true` views over the
projection (`groups_view`, `group_members_view`, `resource_scopes_view`, `events_view`,
`notification_reads_view`, `notification_digests_view`, `profiles_view`, `dues_policy_view`,
`dues_waiver_view`, `tier2_entry_view`, `tier2_signature_view`, `payment_intent_view`,
`telephony_resources_view`). Explicit column lists (no bare `SELECT *`); SELECT granted to
`coop_member`. `security_invoker` makes RLS fire under the viewer's cert role — this is the
correct answer to the spike's "naive view defeats RLS" lesson (member-1 sees 6 rows, not all 17).

**Proof (psql cert contrast):** member-1 sees "Cold Storage Co-op" (NOT member-2's
"Derived Slug Test"); member-2 the inverse; `SET app.sub=<other>` ignored through the views too.

**Next (B1, DONE this session):** re-oriented to one-base-per-group. Scaffold cleanup done
("Coop Groups" + "Projects" deleted; "Base" + "my base" are NocoDB's protected meta bases,
403 on delete by design). **Robbie picked A: one NocoDB base PER group.** Provisioned live:

- `infra/compose/storage/scripts/coop_group_base.sql` — `coop_provision_group_base(uuid)`:
  idempotent, SECURITY DEFINER, creates schema `grp_<uuid-hex>` + narrowed `security_invoker`
  views (groups/group_members/resource_scopes/events/dues_policy/dues_waiver/tier2_entry/
  tier2_signature/payment_intent/telephony_resources), each `WHERE group_id=<this group>` so a
  base shows ONLY its group; `security_invoker` means RLS still fires (a non-member sees nothing).
  Granted to coop/coop_ops for the group-create hook.
- `infra/scripts/provision-group-bases.mjs` — NocoDB-side: one base per group (external source,
  `searchPath: [schema, public]` — public MUST be in the path or the inlined RLS helpers
  `coop_role_sub()`/`coop_current_sub()` don't resolve under the group schema's search_path).
  Sanitizes titles to NocoDB's validator charset (group names with em-dash/"!!" 400 otherwise).
- Backfilled all 9 collective groups. VERIFIED (browser E2E): e2e-test reads "Cold Storage Co-op"
  base → 1 row (own group); "derived-slug-test" base → **0 rows** (members-only, other's group);
  "The Food Coop" base → 1 row (open). Cross-group isolation proven through NocoDB.

**Next (B2, DONE this session):** personal-group bases + federation (the lens). Added
`coop_provision_personal_base(uuid)` to `coop_group_base.sql`: a personal group's base is the
member's LENS — federated views re-projecting the global `*_view` relations with NO group WHERE,
so RLS (cert role) is the only scoping and the member sees their slice ACROSS all their groups.
(Distinct from `coop_provision_group_base`, whose views narrow to one group — wrong for personal,
which owns no events/dues/resources of its own.) Drop-and-recreate of stale narrowed views first
(CREATE OR REPLACE can't rename/reorder columns). Backfilled all 8 personal groups + provisioned
8 personal NocoDB bases (titles = display_name || email || "Member <sub8>"). VERIFIED (browser
E2E): e2e-test's "E2E Tester" lens = 6 groups across memberships; own "Cold Storage Co-op" base =
1 row; other's "Derived Slug - Test" base = 0 rows. All three settled objects now live:
personal base (lens) + group base (narrowed) + the RLS wall between them.

**Remaining after B2:** the scope dial (focus one / pick / see all) is dashboard UI, not NocoDB
provisioning — it just navigates between the bases above. Then **C1** governed shape-migration.

## Flags / items needing a human decision

- **NocoDB connection exhaustion (53300 "reserved for SUPERUSER") — FIXED this session.** Root
  cause: NocoDB opens ONE knex pool per external source (default max 10); one-base-per-group
  created ~18 sources → up to 180 potential conns against max_connections=100 (shared with temporal
  25+, matrix, formbricks, etc.). Fix: `NC_DB_POOL_MAX: "2"` in nocodb.yaml (min:0 so idle pools
  hold nothing; bounds NocoDB worst case to ~36). Verified: 0 new errors, `coop` down from 7 to 1
  idle conn, browser E2E renders all 20 bases cleanly. NOTE for later fleet headroom: raise
  max_connections via `command: postgres -c max_connections=200` (full restart) — the stock
  entrypoint ignores a POSTGRES_MAX_CONNECTIONS env var.

- **`e2e-test@irl.coop` Keycloak password RESET** to `E2e-Reset-2026-Temp!` (via admin API). It's a
  password+passkey hybrid (1 `password` cred + 2 `webauthn-passwordless` passkeys, TEST AAGUID
  `01020304-0506-0708-0102-030405060708`). Decide keep vs change. **NOTE:** `infra/scripts/journeys.sh`
  derives the OLD password from master.key (`keycloak.e2e-test`), so `make test`'s sign-in/groups/membership
  journeys fail until the derived secret matches the reset — this is pre-existing, NOT the cert work.
  Also: the `identity-isolation` "anonymous sees 0 groups" check expects 0 but the live policy returns the
  4 `privacy='open'` groups by design (pre-existing; the handoff's own fact-finding noted this).
- **Settlement-webhook harness (`/tmp/hermes-verify-webhook.js`) pre-existing flake** (`admin is not
  iterable`), NOT from this work; recurs even after rebuilding `/tmp/paymentsbuild/`. Root cause not
  found. Product code healthy (worker alive, rail+api 200).
- **Keycloak admin**: username=`admin`, password = derived `KEYCLOAK_ADMIN` in `infra/out/dev/secrets.env`.
- **`coop_member_role` role names are the A1 test roles** (`coop_test_rolemember1`, `coop_test_r1`).
  The mapping is arbitrary; production minting will use real member roles via `mint-member-cert.sh`.

## Design docs added this session (all registered + committed)

`coop-accounts-and-phone-verification.md`, `group-account-resource.md`, `group-who-picker.md`,
`nocodb-integration.md`, `nocodb-one-base-per-group.md`, `nocodb-rebuild-plan.md`,
`sharing-nocodb-interfaces.md`.
