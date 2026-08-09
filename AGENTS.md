# AGENTS.md — irl.coop v2 stack (operational context for agents)

This file is the agent-facing context for working on the irl.coop v2 sovereign
stack: Safe-as-everything accounts, one Keycloak identity realm, federated core
services, declarative deployment. Read STATUS.md for the live status of each
pillar.

## Architecture in one screen

- **Identity**: Keycloak on this host — `KC_HOSTNAME=auth.irl.coop`, realm
  `irl-coop`, issuer `https://auth.irl.coop/realms/irl-coop`. Every app is an
  OIDC client of this one realm (`web-app`, `coop-api`, `plane`, `nocodb-gate`).
  Google is brokered via Keycloak (NOT a direct NextAuth GoogleProvider).
- **Edge**: Traefik v3 (`proxy-traefik-1`) on the host, generated file-provider
  config (`infra/out/dev/`). Routes: `auth`→keycloak, `app`→plane (Caddy),
  `mail`→stalwart, `api`→coop-api (host :3001), `nocodb`→oauth2-proxy gate,
  `s3`/`s3api`→minio, apex `irl.coop`→full-kit (host :3000).
- **Apps**: full-kit (Next.js), coop-api (Fastify), Plane CE, NocoDB (custom
  Gate-SSO image), each an OIDC client of the realm.
- **Data**: shared Citus Postgres `172.17.0.1:5432` (roles/dbs: `irlcoop`,
  `nocodb`, `stalwart`), shared Redis `:6379` (prefix all keys; plane uses
  `KEY_PREFIX=plane`; pub/sub `irl:notify:{sub}`), MinIO `:9000/:9001`
  (bucket `stalwart`, user `stalwart-s3`), plane-db `:5434`, keycloak-db `:5433`.
- **Mail**: Stalwart v0.16 (`:8083` webadmin, SMTP/IMAP 25/587/143/993),
  postgres store, internal directory, DKIM selector `dkim`, DNS
  MX/SPF/DMARC/DKIM live at Gandi.
- **DNS**: Gandi LiveDNS → `64.135.141.73` (router) → 80/443 + mail forwards →
  `192.168.18.20` (this host). Wildcard cert `*.irl.coop` (acme.sh + custom
  Gandi DNS-01 hook; daily 03:30 cron, renewal window = expiry−30d ±1d).

## URLs / ports inventory

| Service | URL | Port | Notes |
|---|---|---|---|
| full-kit | https://irl.coop | :3000 | host `npm run dev` |
| coop-api | https://api.irl.coop | :3001 | host dev; canonical issuer + redirects |
| Plane | https://app.irl.coop | :3002 (Caddy) | OIDC client `plane`; god-mode `/god-mode/` |
| NocoDB | https://nocodb.irl.coop | gate→container | custom image (see below) |
| Keycloak | https://auth.irl.coop | :8081 | realm irl-coop; admin console master |
| Stalwart | :8083 | containers | mail; also 25/587/143/993 |
| Citus | 172.17.0.1:5432 | containers | roles: irlcoop, nocodb, stalwart |
| Redis | :6379 | containers | shared; prefix keys |
| MinIO | :9000/:9001 | containers | bucket stalwart, user stalwart-s3 |

LAN: surfy `.11` = retired v1 edge (`ssh service@surfy`); THIS host `.20` = v4 node.
Tailnet `100.122.136.95`.

## Configuration flow — START HERE before touching any running service

The stack is declarative: `infra/instances/dev/` is the source of truth, the
generator emits deployment artifacts, and every change follows the pipeline.
Never hand-edit `infra/out/` and never poke containers directly — add an app by
editing the tree and regenerating.

```
infra/instances/dev/instance.yaml      ← domain, hosts (roles), app list, enabled pillars
infra/instances/dev/apps/<app>.yaml    ← per-app spec (schema below)
infra/build/generator.py               ← reads the tree → writes infra/out/dev/
infra/out/dev/compose/<pillar>/        ← GENERATED compose (+ .override.yml)
infra/out/dev/compose/proxy/dynamic.yml← GENERATED traefik file-provider (LIVE edge)
infra/out/dev/keycloak/clients.yaml    ← GENERATED OIDC client registry
infra/out/dev/MANIFEST.md              ← what was generated from what
```

Generate:  `uv run --with pyyaml python infra/build/generator.py dev`
Validate:  `docker compose -f infra/out/dev/compose/<pillar>/docker-compose.yml config`

### App spec schema (fields the generator consumes — see apps/*.yaml for examples)

| field | meaning |
|---|---|
| `name`, `pillar` | filename = name; pillar = compose grouping (proxy/authentication/cache/storage/communication/workflow/...) |
| `type` | `image` (compose emitted) or `source` (app ships its own compose — plane) |
| `image`, `command`, `ports`, `env`, `volumes`, `depends_on`, `labels`, `healthcheck`, `extra_hosts`, `restart` | passed through to the compose service |
| `sidecars`, `named_volumes` | extra services / named volumes in the same compose file |
| `dev.volumes` | host paths relative to the instance dir — absolutized at generation into the `.override.yml` |
| `proxy` | `{hostname, port, description}` (or a list) → edge route `https://<hostname>` → `172.17.0.1:<port>` |
| `oidc` | `{client_id, redirect \| redirects, public}` → keycloak/clients.yaml registry entry |
| `web` | base URL combined with `oidc.redirect` to form the redirect URI |
| `data` | `{scoped_by: sub, views: [...]}` → plane data-scoping view scripts |
| `routes` | traefik app only — extra file-provider routes (e.g. the apex → full-kit :3000) |

`${DOMAIN}` is substituted with the instance domain at generation time.

### Adding an app (the recipe)

1. Write `infra/instances/dev/apps/<name>.yaml` — copy the closest existing spec (plane.yaml shows oidc+proxy+data; stalwart.yaml shows ports+volumes+env; minio.yaml shows a multi-entry proxy list + labels).
2. Append `<name>` to `apps:` in `infra/instances/dev/instance.yaml`.
3. Regenerate (`generator.py dev`). `infra/out/` is gitignored — never commit it.
4. Apply: `docker compose -f infra/out/dev/compose/<pillar>/docker-compose.yml -f infra/out/dev/compose/<pillar>/docker-compose.override.yml up -d <service>`
5. Restart the edge: `docker restart proxy-traefik-1` — the file-provider inotify breaks on atomic rewrites of `dynamic.yml`; this restart is a known, expected step.
6. Provision the OIDC client in Keycloak from `out/dev/keycloak/clients.yaml` (client id, redirect URIs, public/confidential; secret via the admin console for confidential clients).
7. DNS: the Gandi wildcard `*.irl.coop` → 64.135.141.73 already covers any new subdomain — only add an A record for non-wildcard needs.
8. Verify through the edge (`https://<hostname>.irl.coop` / browser E2E for SSO), never bare `docker exec curl/printenv`.

### Known quirks

- `type: source` apps (plane) ship their own compose; the generator only emits their OIDC client, env block and data-scoping views.
- Generated-vs-running drift: the edge (traefik) runs generated `out/` (dynamic.yml + instance-tree certs mounted); some containers (stalwart16) were bootstrapped from scratch compose at `/tmp/stalwart16` before the pipeline existed. When touching a drifted pillar, reconcile by applying its generated compose.
- Stalwart-internal config (datastore, blob store, OIDC directory, accounts) is stored in its postgres DB and managed via the webadmin/admin API — the declarative layer only deploys the container/ports/env/edge.
- Secrets never enter the tree: `.env*` files and `infra/instances/dev/certs/` (wildcard privkey + ACME state) are gitignored. Renewed certs land under `infra/instances/dev/certs/` (privkey 0600); renewal is acme.sh + Gandi DNS-01 (daily cron, renewal-window guarded).

## Key operational facts

- **Verification convention (Robbie)**: ad-hoc `/tmp/hermes-verify-*.py` scripts
  run in the same turn as edits; browser E2E is authoritative for SSO/UI; no
  canonical test suite. Bare `docker exec curl/printenv` is denied — use the
  edge, the browser, or inspect.
- **Approvals**: terminal commands are approval-gated. A denied command is never
  retried or rephrased.
- **Secrets**: values are intentionally not preserved in notes. Grep old project
  versions for creds (irl.coop v1 kept Google creds in `.env.example`). The
  Gandi API key is 40-char; lego's provider rejects that format — acme.sh with
  the custom `infra/scripts/dns_gandi_livedns.sh` hook is the renewer.
- **NocoDB custom image** `irlcoop/nocodb-gate-sso:2026.08.1` = stock image +
  rebuilt server bundle carrying: Gate-SSO auto-login (reads
  `NC_GATE_SSO_EMAIL_HEADER` = x-forwarded-email), the workspaces read API
  (`GET /api/v1/workspaces` + `/:id` + `/:id/bases`), enterprise-op stubs
  (listScripts/dashboardList/workflowList/listSync/baseSchema/documentList/
  workflowNodes — the OSS frontend toasts on 404/403 otherwise), and the `/404`
  → SPA-shell (200) response so the PWA precache succeeds. Full rebuild
  procedure in the `nocodb-custom-build` skill (`/tmp/nocodb-src` checkout,
  Dockerfile.irlcoop layers the bundle over the base tag).
- **NocoDB data quirk**: the frontend's active workspace id comes from
  `appInfo.defaultWorkspaceId`, which reads the `nc_store` row
  `NC_DEFAULT_WORKSPACE_ID` — if missing, the UI falls back to the fake
  workspace 'nc' and the base list renders empty.
- **Stalwart**: v0.16 default listeners are 25/465/993/995 — 587 (submission)
  and 143 (IMAP) were created via the admin API to match the router forwards.
  Setup (bootstrap mode → postgres store + internal directory) was done via the
  admin API (webui PKCE flow), not the wizard (its secret-reference dropdown is
  un-drivable and the OIDC step had a validation bug).

## Recent completed (see STATUS.md for the full picture)

- Canonical identity switch (KC_HOSTNAME, api.irl.coop route, ALLOWED_REDIRECTS,
  realm-client redirects, plane/gate issuers) — browser-E2E verified.
- Cert renewal pipeline (acme.sh + custom Gandi hook; renewed Aug 8 → notAfter
  Nov 6 2026; cron daily 03:30; window Oct 6–8).
- Mail DNS (MX/SPF/DMARC/DKIM) written + propagated; Stalwart setup completed;
  all four mail ports answering externally.
- Plane canonicalization (VITE_* build args + api runtime BASE_URLs + CORS).
- NocoDB: workspaces API port, enterprise-op stubs, /404 SPA-shell fix,
  default-workspace store row.

## Pending

- Stalwart MinIO blob store (S3 172.17.0.1:9000, bucket `stalwart`) + Keycloak
  OIDC directory.
- DMARC hardening p=none → quarantine (after real volume is observed).
- Federation / takedown-resilient DNS+edge design session — PARKED; do not
  design/build until Robbie raises it.
- Not in final form: Temporal, Formbricks, Webstudio, Postiz, CryptPad.

## Do not

- Do NOT use TEEs/Lit/cloud KMS anywhere — pure-crypto only.
- Do NOT touch another Hermes profile's skills/plugins/cron/memories.
- Do NOT design the federation/DNS-resilience architecture until asked.
