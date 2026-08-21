# irl.coop — web

The web frontend of the irl.coop sovereign stack: a Next.js 15 (App Router)
dashboard (`irl-dashboard`) plus the sibling backend services that make it a
platform.

## What irl.coop is

irl.coop is a sovereign, member-owned platform for cooperation. Every account
is a Safe, one Keycloak identity spans every app, and groups coordinate through
seats, roles, quorum-gated voting, a shared event bus, and zero-knowledge
proofs.

## Architecture in one screen

- **Identity**: Keycloak on this host (`auth.irl.coop`, realm `irl-coop`) is the
  single OIDC issuer for every app (`web-app`, `coop-api`, `plane`,
  `nocodb-gate`). Google is brokered through Keycloak — no app holds its own
  Google credentials.
- **Edge**: Traefik v3 routes `auth` → Keycloak, `app` → Plane, `mail` →
  Stalwart, `api` → coop-api (host `:3001`), `nocodb` → oauth2-proxy gate,
  `s3`/`s3api` → MinIO, and the apex `irl.coop` → irl-dashboard (host `:3000`).
- **Apps**: irl-dashboard (Next.js), coop-api (Fastify auth bridge + relayer),
  Plane CE, NocoDB (custom Gate-SSO image) — each an OIDC client of the realm.
- **Data**: shared Citus Postgres (`172.17.0.1:5432`), Redis (`:6379`), MinIO
  (`:9000/:9001`).
- **Mail**: Stalwart (SMTP/IMAP 25/587/143/993) with DKIM/SPF/DMARC live at
  Gandi behind the `*.irl.coop` wildcard.

## This workspace

- `irl-dashboard/` — the main web frontend (Next.js 15, Shadcn/ui, Tailwind 4).
- `starter-kit/` — the upstream template's starter kit (kept for reference).
- `apps/coop-api` — auth bridge + relayer (sibling workspace).

## Authentication

Auth is a three-tier chain:

```
NextAuth (frontend) → coop-api (:3001) → Keycloak (:8081, realm irl-coop) → Google
```

- The Next.js app uses a custom OAuth provider (`coop-api`) — it holds **no**
  Keycloak or Google credentials.
- `apps/coop-api` implements `authorize` / `token` / `userinfo` and owns the
  Keycloak client secret; its JWT is also the Bearer credential for the
  auth-to-EVM bridge (`POST /api/onboard`).
- Keycloak (`infra/compose/authentication`) brokers Google via an
  identity-provider alias.

## Getting started

```sh
cd apps/web/irl-dashboard
pnpm install
pnpm dev
```

## Documentation

- **Design docs**: `docs/design/` in the repo root, presented publicly at
  `/design` on the dashboard — groups, identity, treasury, the event bus, group
  shapes, and the commons economy.
- **Operational context**: `AGENTS.md` and `STATUS.md` in the repo root.
- **API**: [`apps/coop-api/README.md`](../coop-api/README.md).

## Attribution

The dashboard UI was built on an open-source Shadcn/ui admin template (Qualiora's
Shadboard). Attribution is kept in the docs' Sources & Credits page; the product
itself is irl.coop.
