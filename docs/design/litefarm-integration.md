# LiteFarm integration (irl.coop)

Status: design · Aug 2026. Fork: `github.com/rbpollock/LiteFarm` (tracks upstream
`LiteFarmOrg/LiteFarm`; top commit `58d434d`).

LiteFarm is an open-source **farm-management** platform (GPL-3): fields, crops,
tasks, animals, expenses, sales, certifications, sensors. It becomes the coop's
**agriculture/food-sovereignty vertical** — a first-class group app like Plane or
NocoDB, but with the richest domain model (a farm already *is* a cooperative
unit).

## 1. What LiteFarm is (architecture, from the fork)

- Monorepo, pnpm/lerna: `packages/api` (Express + Objection/Knex, entry
  `src/server.ts`), `packages/webapp` (React SPA), `packages/shared`,
  `packages/end-to-end`.
- **Data model**: `farm` (tenant: `farm_id`, `farm_name`, `grid_points` {lat,lng},
  `country_id`, `units`, `utc_offset`) + `userFarm` (user↔farm membership:
  `role_id`, `status`, consent). ~60 Objection models, ~50 route modules.
- **Auth**: `checkJwt` = `expressjwt` **HS256** with `JWT_SECRET` (minted by
  `/login`), applied to everything except a small `.unless` list. `services/
  keycloak.ts` is a *separate* webhook helper (client-credentials token + JWKS
  verify) — NOT user auth.
- **Deployment**: the repo's `docker-compose.yml` is dev deps only
  (postgres:13, minio, redis, imaginary). The API + webapp run as Node
  processes; there is **no published runtime image** — we must build one (the
  NocoDB-custom-image pattern).

## 2. The one decision: farm = group

LiteFarm's `farm` is already a multi-tenant boundary (`userFarm` = seats). Map it
1:1 onto the coop's group primitive:

- **`farm.farm_id` ↔ `groups.id`** — a farm is a group resource. Provisioning
  writes a `resource_scopes` row (`app='litefarm'`, `resource_key=farm_id`) and
  a `farm.group_id` column, so the farm is resolvable group→farm and farm→group.
- **`userFarm` ↔ `group_members`** — a seat in the farm = a seat in the group.
  Membership is *authoritative in coop-api*; LiteFarm syncs it on login (see §4).
- **Access control stays LiteFarm's** — every LiteFarm query already filters by
  `userFarm` (the user's farms). We don't re-express 60 models in RLS; we keep
  the group→farm mapping authoritative and make the SSO/sync path enforce that
  a user can only be a member of farms whose group they belong to. (RLS on the
  `farm.group_id` column is a later hardening, not a day-one requirement.)

This is **composition, not inheritance**: a farm is a full group that happens to
use the LiteFarm app — strip the binding and it's an independent group.

## 3. SSO — fleet gate + Gate SSO (the NocoDB/Webstudio pattern)

LiteFarm has no generic OIDC login (its `/login` is email/Google via its own
JWT). Same fix as NocoDB's `gate-sso`: put an oauth2-proxy **fleet gate** in
front, and teach LiteFarm to auto-login from the forwarded identity.

```
browser → farm.irl.coop → litefarm-gate (oauth2-proxy, coop-api OIDC)
        → X-Forwarded-User (sub) + X-Forwarded-Email (canonical)
        → LiteFarm /gate_sso → create-or-login user → mint HS256 JWT → webapp
```

- **Gate** (`litefarm-gate`): `--provider=oidc --oidc-issuer-url=https://api.${DOMAIN}
  --client-id=litefarm-gate --pass-user-headers=true`, upstream = LiteFarm API.
  Client registered in coop-api `OIDC_CLIENTS` (same as nocodb-gate/webstudio-gate).
  The `coop_session` cookie makes authorize instant (no Keycloak page).
- **`/gate_sso`** (new, pre-auth): reads `x-forwarded-user` (Keycloak `sub`) +
  `x-forwarded-email`, create-or-logins the LiteFarm `user` (keyed by `sub`), then
  mints the existing HS256 JWT and returns `{ token }`. Idempotent.
- **Group→farm sync** in the same call: `GET https://api.irl.coop/api/internal/groups?sub=<sub>`
  (shared `KEYCLOAK_GROUPS_TOKEN`) → for each group, ensure a `farm` row
  (`farm_id = group_id`) and a `userFarm` seat (role from the group seat's roles).
- **Webapp**: on boot, if no token, `fetch('/gate_sso', {credentials:'include'})`
  → store token. Add a "Log in with irl.coop" button (branded SSO entry/recovery);
  dev-login stays as fallback.
- `checkJwt`'s `.unless` list gains `/gate_sso`.

## 4. Postgres — shared Citus

- New **role + db `litefarm`** on the shared Citus `172.17.0.1:5432` (sibling of
  `nocodb`, `stalwart`). LiteFarm is coordinator-local (non-distributed) — it
  does not shard; the coop's distributed story is the *device-sharded group
  projection*, not LiteFarm's own tables.
- `util/knex.js` already reads env via `.knex/knexfile.js` → point
  `DATABASE_URL` at the shared Citus. Run LiteFarm's Knex migrations against
  `litefarm` (they target PG13; validate against PG16/Citus — the SQL is
  ordinary DDL and should port, but `CREATE DATABASE` needs the coordinator note
  like Webstudio's).
- Secrets: `${SECRET:postgres.litefarm}` (derived key), injected like the other
  role passwords.

## 5. Events — LiteFarm as a bus source

LiteFarm domain events fan into the coop event store (source → gateway → store),
reusing the `coop_ingest_event` SECURITY-DEFINER path:

- Add a coop-api **server-to-server ingest** endpoint
  `POST /api/internal/events/ingest` (Bearer `KEYCLOAK_GROUPS_TOKEN`, like
  `/api/internal/groups`) that calls `ingestEvent(sub, 'litefarm', …)`.
- LiteFarm emits on the meaningful moments: `farm.created`, `task.completed`,
  `harvest.logged`, `sale.recorded`, `animal.moved`, `certification.changed`.
  `source_event_id` = LiteFarm's row id (idempotent).
- Delivery is then the bus's job (Temporal `deliverySweep` + `irl:notify:{sub}`
  live lane): a harvest can page the group's Matrix room, mail the owner, or roll
  into the digest — **without LiteFarm knowing any channel**.

## 6. Feature weaving (the investigation)

One principle: LiteFarm stays the *domain engine* (crops/tasks/animals/finance);
every other app reaches it through the **event bus + `resource_scopes`**, never
by embedding LiteFarm's UI.

| App | How it weaves with LiteFarm |
|---|---|
| **Plane** | Farm field-work is tasks. `task.created/updated` → Plane issues on the group's project (or a dedicated "Farm" project) via Plane's API/webhook; a Plane task marked "field work" writes back a LiteFarm task. The `resource_scopes` row links them (one farm ⇄ one Plane project). |
| **HiEvents** | Farm lifecycle = events: harvest day, field day, CSA pickup, workshop. `farm` produce/inventory → HiEvents "products" for market signups. A `harvest.logged` event can seed a "come pick" event. |
| **Matrix** | The group's room is a notification *channel*. `task.due`, `frost.risk`, `harvest.ready` → rendered notification → room message via the bus (source anonymization owned by LiteFarm). Frost alerts become actionable in the room. |
| **Event/notification bus** | LiteFarm is a **source** (`source='litefarm'`). Temporal workflows are consumers: e.g. `harvest.logged` → schedule next planting → reminder; `task.overdue` → daily digest. Group delivery prefs (which events → which channels) govern it, not LiteFarm. |
| **NocoDB** | The "visual database" for non-technical members: farm inventory, sales ledger, member roles as NocoDB tables synced from LiteFarm (via the workspaces API / a sync job), so a food-coop's catalog is editable without touching LiteFarm. |
| **Webstudio** | The group's public site: a "Farm" page showing produce, certifications, CSA signup (LiteFarm read surface via coop-api session auth) — an HtmlEmbed widget like the world-doc. |
| **Maps (OpenMapServer)** | `farm.grid_points` {lat,lng} is a **marker** (`source='litefarm'`) on the sovereign map. Federation explore shows every group's farm; a farm's fields could become polygon tracks later. |

## 7. Surfaces (the pattern)

- **Subdomain** `farm.irl.coop` → the `litefarm-gate` (proxy entry, like nocodb).
- **Sidebar**: internal iframe route `/apps/farm` (the Plane pattern) — a manual
  `navigations.ts` entry ("Farm", icon `Sprout`), NOT a `nav:` block (that would
  make an external link, not an iframe).
- **Landing page**: add a Farm card to the `APPS` array.
- **Dashboard iframe**: `apps/farm/page.tsx` frames `https://farm.irl.coop`.

## 8. Deployment (recipe)

1. Build the runtime image `irlcoop/litefarm:<tag>` (API + built webapp in one
   container — a Dockerfile layering the pnpm build, mirroring the NocoDB
   custom-image build).
2. `infra/instances/dev/apps/litefarm.yaml` (image + `litefarm-gate` sidecar +
   `proxy: farm.irl.coop` + env for `DATABASE_URL`, `JWT_SECRET`, gate keys).
3. Add `litefarm` to `instance.yaml` apps + `enabled_pillars`.
4. Create `litefarm` DB + role on Citus; run migrations.
5. Register `litefarm-gate` in coop-api `OIDC_CLIENTS`; restart coop-api.
6. Regenerate; `docker compose up -d litefarm litefarm-gate`; `docker restart
   proxy-traefik-1`.
7. Fork patches: `/gate_sso` + checkJwt unless-list + webapp auto-login +
   `POST /api/internal/events/ingest` (coop-api side).

## 10. Fork patch inventory (API side — written, ready to build)

Concrete changes to apply to `rbpollock/LiteFarm` (all under `packages/api`):

| File | Change |
|---|---|
| `db/migration/20260830000000_add_group_id_to_farm.js` | **new** — `farm.group_id` (indexed), the farm↔group link. |
| `src/controllers/gateSsoController.js` | **new** — `gateSsoLogin()`: reads `x-forwarded-user`/`email`, create-or-logins the `users` row (keyed by sub, fallback email), syncs `userFarm` seats for provisioned farms, mints `createToken('access', {user_id})`. |
| `src/routes/gateSsoRoute.js` | **new** — `POST /gate_sso` (mounted before `checkJwt`). |
| `src/services/eventEmit.js` | **new** — `emitEvent({sub, sourceEventId, type, payload})` → `POST https://api.irl.coop/api/internal/events/ingest` (Bearer `KEYCLOAK_GROUPS_TOKEN`), fire-and-forget. |
| `src/middleware/acl/checkJwt.js` | add `/gate_sso` to the `.unless` list. |
| `src/server.ts` | import + mount `gateSsoRoute` before `checkJwt`. |

Still to write (webapp side, next): the SPA auto-login (fetch `/gate_sso` on boot when
no token) + a "Log in with irl.coop" button; and a `farm.group_id` backfill for the
`resource_scopes` provisioning write.

**Build + push — done (2026-08-30).** The API-side patches plus the coop webapp build
files (`nginx.irlcoop.conf`, `prod.irlcoop.Dockerfile`) are committed and pushed to the
fork as branch `irl-coop-integration` (`7c0639f4e38b2290ddc85a5c491bd6d3b4215402`).
`infra/build/images/litefarm/build.sh` (wired into `build-images.sh`) clones the fork @
that SHA and builds `irlcoop/litefarm-api:2026.08.30` + `irlcoop/litefarm-web:2026.08.30`.

**Deploy + surfaces + auto-login — done (2026-08-30).** `litefarm` role/db provisioned on
Citus, 454 migrations (163 tables), `litefarm-gate` registered in OIDC_CLIENTS (redirects
farm + farmapi), services up (`litefarm`, `litefarm-web`, `litefarm-gate`,
`litefarm-api-gate`), edge restarted. Webapp gate-SSO auto-login (GateSSO saga, boot
`/gate_sso` fetch + nginx proxy) pushed (`ef5f31e`) + `litefarm-web` rebuilt. Surfaces
live: sidebar "Farm" (`Sprout`), landing card, `/apps/farm` iframe. **Deploy gotchas hit
live:** LiteFarm needs **six** JWT secrets (`JWT_SECRET` + `JWT_INVITE/RESET/FARM/
SCHEDULER/DASHBOARD_SECRET`) or `express-jwt` throws at boot; and the knex `production`
env forces TLS, so we run `NODE_ENV=development` + `DEV_DATABASE_*` (no SSL). Remaining:
a real-browser E2E (fresh coop session → farm.irl.coop → auto-login → farm dashboard).


## 9. Open questions / risks

- **Image build size/time** — LiteFarm's pnpm build is heavy (~10+ min, large
   node_modules). Build once, bump the tag.
- **PG13 → PG16/Citus** — migrations are plain DDL; watch for `CREATE DATABASE`
  coordinator behavior and any extension use (sensors use PostGIS-ish types?).
- **The fork has no visible irl.coop commits yet** — all coop changes go on top;
  push access to `rbpollock/LiteFarm` needed to persist them (past Webstudio push
  was denied — confirm).
- **SSO migration** — existing LiteFarm users (email/password) are out of scope
  for the coop instance; everyone signs in via irl.coop.
