# Infrastructure Deployment Guide

## Configuration flow (declarative, generated)

The **declarative tree is the source of truth** — deployment artifacts are generated, never hand-edited:

```
infra/instances/<name>/       ← edit these
  instance.yaml               ← name, domain, hosts (server roles), app list, enabled pillars
  apps/<app>.yaml             ← per-app spec: pillar, image/source, ports, env, oidc client,
                                data scoping (sub), per-user views, dev overrides
  identity.yaml               ← realm, users, groups (the declared relationship graph)
infra/build/generator.py      ← reads the tree → emits infra/out/<name>/
infra/out/<name>/             ← GENERATED: compose per pillar, ansible inventory,
                                keycloak client registry, plane views, manifest
```

Generate: `uv run --with pyyaml python infra/build/generator.py <name>`
Verify artifacts: `docker compose -f infra/out/<name>/compose/<pillar>/docker-compose.yml config`

Rules the generator enforces:
- App specs carry the OIDC client → the keycloak client registry is derived, not duplicated.
- App pillars → the ansible inventory's per-host pillar lists (README topology below).
- Source-build apps (Plane) ship their own compose; the generator emits their OIDC client, env block and data-scoping view scripts.
- Dev overrides: host paths are relative to the instance dir and absolutized at generation time.
- `${DOMAIN}` in app specs (labels, env, proxy hostnames, web URLs) is substituted with the instance domain at generation time.

### Edge (proxy pillar)

The TLS edge is **Traefik** (file provider — the "dynamic generated configuration"):

- `apps/traefik.yaml` — the edge itself: `traefik:v3.5`, entrypoints web/websecure, docker provider (`exposedbydefault=false`), the wildcard cert mounted from the instance tree.
- Each public app's `proxy:` section (hostname + host-published port) → the generator emits `out/<name>/compose/proxy/dynamic.yml` with the routers/services. Routes target the docker gateway (`172.17.0.1:<port>`) so they work against the running stack; the docker-provider labels in specs become active when the whole stack runs from generated compose.
- `tls.certificates` in dynamic.yml reference the **`*.irl.coop` wildcard** at `instances/<name>/certs/irl.coop/{fullchain,privkey}.pem`.
- **Renewal (automated)**: `infra/scripts/renew-cert.sh` issues/renews via acme.sh (Gandi LiveDNS DNS-01, `dns_gandi_livedns` hook — the image's built-in hook and lego's gandi provider are both broken against Gandi's 40-char v5 keys). A daily cron (`30 3 * * *`, service user) runs it, but the script no-ops outside the **3-day window** (day before / day of / day after) around the next renewal date (expiry − 30 days, matching the CA's ARI window) plus a 10-day emergency catch-up; the edge is restarted only when the cert files actually change. Log: `instances/dev/certs/renew.log`.
- The generated `out/<name>/ansible/playbooks/edge.yml` syncs the proxy compose + dynamic config and copies the cert to `/opt/app/proxy/certs/` on the target host.

Current hostname map (dev instance, domain `irl.coop`): `auth` → keycloak:8081, `mail` → stalwart:8083, `app` → plane:3002, `nocodb` → nocodb-gate:8082, `s3` → minio console:9001, `s3api` → minio API:9000, apex → irl-dashboard:3000.

> ⚠️ Router: 80/443 + mail (25/587/143/993) forward to this host (192.168.18.20) — verified externally (surfy 192.168.18.11 is the retired edge).

## Mail (Communication pillar — Stalwart)

- `apps/stalwart.yaml` — `stalwartlabs/stalwart:v0.16`, webadmin on host port **8083**, SMTP/IMAP on the standard ports: **25** (SMTP, STARTTLS), **587** (submission, STARTTLS), **143** (IMAP, STARTTLS), **993** (IMAPS). The v0.16 defaults only ship 25/465/993/995 — the 587 + 143 listeners were added (admin API) to match the router forwards.
- **Setup**: completed via the admin API (the wizard's secret-reference dropdown is not automatable, and the OIDC-directory step fails server-side validation). Store = the shared Citus Postgres (db/user `stalwart`, 23 tables); directory = internal; permanent admin `admin@irl.coop` (secret in the bootstrap flow / admin console).
- **DNS records** (Gandi LiveDNS, applied + verified via public resolvers):
  | name | type | value |
  |---|---|---|
  | `@` | MX | `10 mail.irl.coop.` |
  | `@` | TXT | `v=spf1 mx ~all` |
  | `@` | TXT | `v=DMARC1; p=none; rua=mailto:admin@irl.coop; adkim=r; aspf=r` |
  | `dkim._domainkey` | TXT | `v=DKIM1; k=rsa; p=<key>` (selector `dkim`, RSA-2048, `Dkim1RsaSha256` — configured via `x:DkimSignature/set`) |
- The SMTP path is externally verified: MX → 64.135.141.73 → router → .20:25 → `220 mail.irl.coop Stalwart ESMTP`.
- Pending: MinIO blob store (currently Default), OIDC directory (Keycloak), DMARC policy hardening (`p=none` → `quarantine`).

## Topology
- **server1** (`identity-data`): Authentication, Authorization, Compliance, Finance, Storage, Communication.
- **server2** (`workflow-ops`): Workflow, Lifecycle.

## Pillar-Tool Mapping
| Pillar | Tools |
|---|---|
| Authentication | Keycloak (Stubs) |
| Authorization | Custom (Reserved) |
| Compliance | Postgres/Citus/Temporal Logs |
| Finance | Firefly III |
| Storage | Postgres/Citus, Redis, MinIO, NocoDB, CryptPad |
| Communication | Stalwart, Matrix, Jitsi, Element, Cal.com, FusionPBX/Asterisk |
| Workflow | Temporal, OpenProject, Formbricks, Postiz, Webstudio |
| Lifecycle | Hi.Events |

## Deployment
1. Update `infra/ansible/inventory/hosts.yml` with real host IPs.
2. Ensure you have SSH key access to both hosts.
3. Run bootstrap: `ansible-playbook -i infra/ansible/inventory/hosts.yml infra/ansible/playbooks/bootstrap.yml`
4. Run deploy: `./infra/scripts/deploy.sh`

## Local authentication stack (dev)

The Keycloak stack lives in `infra/compose/authentication/docker-compose.yml`:

```bash
docker compose -f infra/compose/authentication/docker-compose.yml up -d
```

- **Keycloak** — `quay.io/keycloak/keycloak:24.0.4` (`start-dev`) on host port **8081**, admin `admin` / `admin`, realm **irl-coop** (data persists in the `keycloak_db_data` volume).
- **postgres** — keycloak's database on host port **5433**.

### OIDC clients in the `irl-coop` realm

| clientId   | type         | used by                                                        | redirect URI                          |
|------------|--------------|----------------------------------------------------------------|---------------------------------------|
| `web-app`  | confidential | starter-kit (NextAuth KeycloakProvider, legacy)                | `http://localhost:3000/api/auth/callback/keycloak` |
| `coop-api` | confidential | coop-api auth bridge (`apps/coop-api`)                         | `http://localhost:3001/api/auth/keycloak/callback` |
| `admin-cli`| public       | Keycloak admin API                                             | —                                     |

### Google identity broker

The realm has an enabled **Google** identity-provider alias (`http://localhost:8081/realms/irl-coop/broker/google/endpoint`). Google client credentials are configured **only** in the broker — no frontend project holds them.

> ⚠️ The Google OAuth client must list `http://localhost:8081/realms/irl-coop/broker/google/endpoint` in **Google Cloud Console → Authorized redirect URIs**. If it is missing, logins fail with `Error 400: redirect_uri_mismatch` on Google's page (the error details dialog shows the exact URI Google received).

### Auth chain overview

```
NextAuth (frontend :3000) → coop-api (:3001) → Keycloak (:8081) → Google
```

Full details: [`apps/coop-api/README.md`](../apps/coop-api/README.md).
