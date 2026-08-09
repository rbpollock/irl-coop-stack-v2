# irl.coop full-kit (web dashboard)

Next.js 15 (App Router) dashboard for irl.coop, built on the Shadboard template (Shadcn/ui, Tailwind 4, i18n). This is the main web frontend of the monorepo.

## Authentication

Login flows through the **coop-api auth bridge** — the frontend never talks to Keycloak or Google directly:

```
NextAuth (this app) → coop-api (:3001) → Keycloak (:8081, realm irl-coop) → Google
```

- `src/configs/next-auth.ts` defines a custom OAuth provider (`id: "coop-api"`) whose `authorization` / `token` / `userinfo` endpoints point at coop-api.
- The sign-in button (`src/components/auth/sign-in.tsx`) calls `signIn("coop-api")`; users still see "Continue with Google" because Keycloak brokers Google behind the bridge.
- The access token NextAuth receives is coop-api's own JWT; it is exposed on the session as `session.accessToken` so the UI can call `POST /api/onboard` (and future API endpoints) with `Authorization: Bearer <jwt>`.
- Account linking: `allowDangerousEmailAccountLinking: true` on the provider joins accounts that share a verified email (Google-verified via Keycloak) — no more `OAuthAccountNotLinked`.
- Onboarding: coop-api is the authority (`GET/POST /api/auth/onboarding*`); the dashboard layout's `OnboardingGuard` sends new users to `/[lang]/onboarding` until they've set a display name.

See [apps/coop-api/README.md](../../coop-api/README.md) for the bridge internals, endpoint table, and security properties.

## Environment variables (`.env.local`)

| Variable                    | Purpose                                                     |
|-----------------------------|-------------------------------------------------------------|
| `NEXTAUTH_URL`              | `http://localhost:3000`                                     |
| `NEXTAUTH_SECRET`           | NextAuth session signing secret                             |
| `COOP_API_URL`              | `http://localhost:3001` — base URL of the auth bridge       |
| `COOP_API_CLIENT_ID`        | `nextauth` — client id presented to coop-api                |
| `COOP_API_CLIENT_SECRET`    | Shared secret with coop-api (must match its `OAUTH_CLIENT_SECRET`) |
| `DATABASE_URL`              | Prisma/Postgres connection                                  |
| `BASE_URL` / `API_URL`      | App base URL / internal API base                            |
| `HOME_PATHNAME`             | Post-login landing path (must be multi-segment, e.g. `/dashboards/analytics`) |

> Note: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are intentionally **not** in this project anymore — Google credentials live only inside Keycloak's identity broker.

## Local run

```bash
# 1. Keycloak stack (see infra/README.md)
docker compose -f infra/compose/authentication/docker-compose.yml up -d

# 2. coop-api (see apps/coop-api/README.md)
npm run dev --workspace=apps/coop-api

# 3. This app
cd apps/web/full-kit && npx next dev --turbopack --port 3000
```

Open http://localhost:3000 — sign in via "Continue with Google".

## Project management (Plane)

The dashboard deep-links to a self-hosted [Plane](https://plane.so) Community Edition instance for project work (projects, issues, cycles, docs) — identity, governance and treasuries stay in irl.coop; Plane is the collaboration surface.

- **Tile**: dashboard → *Project Tools → Projects* opens `http://localhost:3002` (new tab). URL from `NEXT_PUBLIC_PLANE_URL`, fallback `http://localhost:3002`.
- **Instance**: docker compose source build at `/home/service/plane` (web/space/admin/live behind a Caddy proxy; API + worker/beat + postgres/redis/rabbitmq/minio). Proxy entry `LISTEN_HTTP_PORT=3002`; Caddy routes `/auth/*` → API (OIDC callback path), `/god-mode/*` → admin, `/spaces/*` → space, `/*` → web.
- **Auth — OIDC via Keycloak (ported, verified)**: Plane CE has no OIDC upstream (Pro/Business feature), so the repo at `/home/service/plane` carries a **generic OIDC provider port** — `apps/api/plane/authentication/provider/oauth/oidc.py` (discovery-driven, Keycloak-compatible; `email_verified` enforced for parity with the GitLab ATO fix), `/auth/oidc/` + `/auth/oidc/callback/` routes, a "Sign in with Keycloak" button on the login page, and the `is_oidc_enabled` instance flag. Configured via env: `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER` (the api CONTAINER reaches the host's Keycloak via the docker bridge gateway `http://172.17.0.1:8081/realms/irl-coop` — not `localhost`), `IS_OIDC_ENABLED=1`. Keycloak client `plane` (confidential, redirect `http://localhost:3002/auth/oidc/callback/`) — Caddy already routes `/auth/*` → API. Verified: full SSO round-trip (button → Keycloak → token exchange → workspace), email-matched to the existing Plane account.
- **Cache — shared irl.coop Redis (migrated, verified)**: Plane's Django cache now lives on the co-op-level Redis pillar (`infra/compose/cache`, host `:6379`; the api container reaches it via `redis://172.17.0.1:6379/0` — bridge gateway, same trick as Keycloak). Keys namespaced via `REDIS_KEY_PREFIX=plane` (settings/common.py). `plane-redis` is now idle (kept in compose, unused). Sessions stay in-memory (restarts still log everyone out — accepted for now).
- **Structure-aware (irl.coop identity native to Plane's data, verified)**: `users.sub` — the Keycloak realm subject — is a first-class User field, promoted on every OIDC login (`authenticate()` override in `provider/oauth/oidc.py`); null for password/local users. `projects.group_id` + `projects.safe_address` carry the irl.coop group link (backfilled: each existing project IS its own group). User-scoping is now a WHERE clause on the data, not a mirror artifact. Per-user views for DB consumers: `infra/compose/storage/scripts/plane_user_view.sql` (sub-scoped, sanitized view name; public projects + private-project membership semantics) — NocoDB connects its external source straight to plane-db and reads the user's view. No mirror, no duplication.
- **Main database live (dev)**: storage pillar `citusdata/citus:12.1` (`infra/compose/storage`, dev override publishes 127.0.0.1:5432, data under `./data/postgres`). Role/db `irlcoop` (dev password). Citus ready for per-user distributed tables. OpenProject removed from the workflow pillar (superseded by Plane).
- **Instance admin**: `admin@irl.coop` (dev password — rotate before anything real).
- **Shape 2 — groups as private projects (LIVE demo)**: one union workspace ("irlcoop", slug `coop-test`) holds one project per group, each PRIVATE (lock icon — visible only to invited members). A member's project list IS their "all groups pertaining to me" view. Demo projects: Farm Coalition, Cold Storage Coop, Regional Working Group, Community Fund. Group isolation = private project + per-project member roles (guest/member/admin); the workspace itself is the member's one-big-world context. **SSO signups auto-join the union workspace** (OIDC port hook: `ensure_default_workspace` in `views/app/oidc.py`, driven by `OIDC_DEFAULT_WORKSPACE=coop-test` in apps/api/.env) — new members land in the shared workspace after onboarding, NEVER the create-workspace wizard. Verified live: fresh user new-member@irl.coop signed in via OIDC → onboarding → /coop-test/ with the private group projects correctly invisible.
- **Shape 3 — coop-api aggregator (future)**: for a more in-app feel, coop-api will call the Plane REST API across the user's workspaces and render a unified "my groups" list in the irl.coop dashboard (deep-links into each group's project). Plane has no native cross-workspace aggregation (entire API is `/api/workspaces/{slug}/...`).
- **Name-validation gotcha (found live)**: Plane silently refuses workspace/project names containing `.` or `-` (e.g. "irl.coop", "Cold Storage Co-op" — the form just won't submit, no error). The provisioning engine MUST sanitize group names → alphanumeric + spaces ("Cold Storage Co-op" → "Cold Storage Coop").
- **Keycloak Google IdP gotcha (found live)**: the Google broker was created programmatically and shipped with NO mappers — so `emailVerified` wasn't synced from Google and broker users landed unverified, which the Plane OIDC port (correctly) rejects with 5124 OAUTH_PROVIDER_UNVERIFIED_EMAIL. Fix: Google IdP → Mappers → add "Email Verified" mapper (OIDC attribute importer: claim `email_verified` → attribute `emailVerified`, sync FORCE) + Trust Email ON; re-flag existing users. Any programmatic IdP creation must add the default mappers.
