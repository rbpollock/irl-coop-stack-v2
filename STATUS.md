# STATUS.md — irl.coop v2 infrastructure status

Last updated: 2026-08-08 (config-flow docs; Stalwart webmail/roundcube + blob-store/OIDC work upcoming).

## Configuration flow — how to add an app (START HERE)

The stack is declarative. `infra/instances/dev/` is the source of truth; the
generator emits deployment artifacts into `infra/out/dev/` (gitignored); the
edge (traefik) runs the generated `dynamic.yml` live. Never hand-edit
`infra/out/` — add an app by editing the tree and regenerating.

```
instance.yaml  +  apps/<app>.yaml  →  infra/build/generator.py dev  →  infra/out/dev/
                                                                          ├─ compose/<pillar>/docker-compose.yml (+ .override.yml)
                                                                          ├─ compose/proxy/dynamic.yml   (edge routes — LIVE)
                                                                          ├─ keycloak/clients.yaml      (OIDC registry)
                                                                          └─ MANIFEST.md
```

Recipe: (1) write `apps/<name>.yaml` (copy an existing spec — plane.yaml shows
oidc+proxy+data, stalwart.yaml shows ports/volumes, minio.yaml shows a
multi-entry proxy list + labels; schema table in AGENTS.md), (2) add the name
to `instance.yaml → apps:`,
(3) `uv run --with pyyaml python infra/build/generator.py dev`,
(4) `docker compose -f infra/out/dev/compose/<pillar>/docker-compose.yml -f infra/out/dev/compose/<pillar>/docker-compose.override.yml up -d <service>`,
(5) `docker restart proxy-traefik-1` (file-provider inotify breaks on atomic
rewrites of `infra/out/dev/compose/proxy/dynamic.yml` — expected),
(6) provision the OIDC client in Keycloak from
`infra/out/dev/keycloak/clients.yaml`, (7) DNS is covered by the `*.irl.coop`
wildcard (Gandi → 64.135.141.73), (8) verify through the edge.

Current declared apps (14): traefik, keycloak, citus, irl-redis, minio, nocodb,
stalwart, cryptpad, temporal, formbricks, webstudio, postiz, plane, coop-api.
`enabled_pillars`: proxy, authentication, cache, storage, communication.
Webstudio/postiz are declared with OIDC clients but no redirect URIs yet (not
wired). Known drift: the edge runs generated `out/`; stalwart16 was
bootstrapped from scratch compose (`/tmp/stalwart16`) before the pipeline —
reconcile by applying its generated compose when touching it.

## Identity pillar — LIVE

- Keycloak recreated with `KC_HOSTNAME=auth.irl.coop`; canonical issuer
  `https://auth.irl.coop/realms/irl-coop` verified through the edge
  (X-Forwarded-Proto aware). Admin console on the master realm.
- Realm `irl-coop` clients all canonical: `web-app`, `coop-api`, `plane`,
  `nocodb-gate` — canonical redirect URIs added (localhost forms kept for dev).
- coop-api `ALLOWED_REDIRECTS` fixed (was hardcoded localhost-only; canonical
  callback added). Google broker endpoint is the user's Google Cloud console
  (updated by user; E2E reaches the real Google sign-in).
- Plane OIDC: issuer canonical, client `plane`, default workspace irlcoop
  (coop-test), SSO signups auto-join via OIDC_DEFAULT_WORKSPACE hook,
  workspace creation disabled (DISABLE_WORKSPACE_CREATION).

## Edge pillar — LIVE

- Traefik v3 (`proxy-traefik-1`), generated file-provider config.
- Routes: auth→keycloak, app→plane (Caddy :3002), mail→stalwart,
  api→coop-api (host :3001), nocodb→oauth2-proxy gate, s3/s3api→minio,
  apex→full-kit (host :3000).
- Wildcard cert `*.irl.coop` renewed 2026-08-08 (notBefore Aug 8, notAfter
  **Nov 6 2026**). Renewal: acme.sh (neilpang/acme.sh) + custom Gandi LiveDNS
  v5 hook (`infra/scripts/dns_gandi_livedns.sh` — the image's built-in hook is
  broken against the current API). Cron `30 3 * * *` daily; acts only in the
  renewal window (expiry−30d ±1d → Oct 6–8); 10-day emergency catch-up;
  traefik restarted only when cert sha256 changes. State in
  `instances/dev/certs/lego/`; log `certs/renew.log`.
- Known quirk: generator atomic rewrites of `dynamic.yml` break the file-provider
  inotify — restart traefik after regenerating.
- DNS: Gandi A records (irl.coop/auth/app/mail/api/nocodb/s3 + wildcard) →
  64.135.141.73 (router); router forwards 80/443 + mail (25/587/143/993) →
  192.168.18.20 — all verified externally.

## Apps pillar — LIVE

- full-kit (https://irl.coop, host :3000, `npm run dev`, canonical env:
  NEXTAUTH_URL, COOP_API_URL, NEXT_PUBLIC_COOP_API_URL → api.irl.coop).
- coop-api (https://api.irl.coop, :3001, host dev; canonical issuer +
  ALLOWED_REDIRECTS; edge route live).
- Plane CE (https://app.irl.coop, :3002 via Caddy): web/admin/space/live images
  rebuilt with canonical VITE_* args; api runtime APP/ADMIN/SPACE/LIVE_BASE_URL
  + CORS canonical (localhost dev origins kept); live app env canonical.
  E2E: app.irl.coop → Keycloak → Google sign-in verified.
- NocoDB (https://nocodb.irl.coop, oauth2-proxy gate → custom image):
  - Image `irlcoop/nocodb-gate-sso:2026.08.1` = 2026.08.0 base + rebuilt server
    bundle (source at /tmp/nocodb-src, develop; build in the nocodb-custom-build
    skill; Dockerfile.irlcoop).
  - Patches in the bundle: Gate-SSO auto-login (x-forwarded-email →
    user+JWT+cookie, token seeded into the SPA shell), workspaces read API
    (`GET /api/v1/workspaces` w/ nested bases, `/:id`, `/:id/bases` —
    Enterprise-only upstream, ported OSS), enterprise-op stubs
    (listScripts/dashboardList/workflowList/listSync/baseSchema/documentList/
    workflowNodes — prevents the 404/403 error toasts), `/404` → SPA shell (200)
    so the PWA precache succeeds (workbox warning fix).
  - Data: citus db `nocodb`; Default Workspace `wqvc1f4e` (owner
    usysbq274yiq07kv = e2e-test); bases: Getting Started (`p7csm3t0ugiv0dw`,
    1 table "Features"), Plane Groups (`puwfq9lvb9ztkzh`, 0 tables).
  - `nc_store` row `NC_DEFAULT_WORKSPACE_ID` = `wqvc1f4e` (inserted manually —
    the boot-time verify helper silently bails pre-migration; without it the UI
    falls back to workspace 'nc' and the base list renders empty).
  - Gate: oauth2-proxy v7.6, canonical issuer/redirect; PWA files
    (manifest.webmanifest, sw.js, favicon, robots) skip auth so the manifest
    doesn't CORS-fail pre-login; everything else stays gated (verified 302).

## Data pillar — LIVE

- Citus `172.17.0.1:5432` (0.0.0.0): roles/dbs `irlcoop`, `nocodb`, `stalwart`.
- Shared Redis `:6379` — prefix all keys (`KEY_PREFIX=plane` for plane cache);
  pub/sub `irl:notify:{sub}`.
- MinIO `:9000/:9001` (root minioadmin/minioadmin123, bucket `stalwart`, user
  `stalwart-s3`) — blob store wiring for Stalwart PENDING.
- plane-db `:5434`; keycloak-db `:5433`.

## Mail pillar — LIVE (setup complete, two follow-ups pending)

- Stalwart v0.16, container `stalwart16`, webadmin :8083; postgres store
  (23 tables in citus); internal directory; permanent admin `admin@irl.coop`.
- Root cause of the "mail refused" mystery: stalwart was stuck in bootstrap mode
  (recovery listener only) — setup completed via the admin API, not the wizard
  (the secret-reference dropdown is un-drivable; the OIDC step had a validation
  bug). Listener recipe: webui PKCE flow → JSON authCode POST to `/api/auth`;
  `authSecret {"@type":"Value","secret":…}`; timeout as plain ms.
- Listeners live: 25 (SMTP), 587 (submission STARTTLS — created via API,
  id i1xyqo0jkrqa), 143 (IMAP STARTTLS — created via API, id i1xyuatgaaqa),
  993 (IMAPS). All four answer externally (`220 mail.irl.coop Stalwart ESMTP…`).
- DKIM: selector `dkim`, RSA-2048, Dkim1RsaSha256 relaxed/relaxed; key held in
  stalwart, public key in DNS.
- DNS: MX `10 mail.irl.coop.`; SPF `v=spf1 mx ~all`; DMARC
  `v=DMARC1; p=none; rua=mailto:admin@irl.coop; adkim=r; aspf=r`; DKIM
  `dkim._domainkey v=DKIM1; k=rsa; p=…` — all propagated on public resolvers.

## Completed this arc (2026-08-08)

1. Cert renewal: lego → acme.sh (lego's gandi provider hard-codes the old
   24-char key format; the key is 40-char) + custom LiveDNS v5 hook + daily cron
   with the renewal-window guard.
2. Mail DNS at Gandi + Stalwart bootstrap-mode root cause + API-driven setup +
   missing listeners (587/143) created.
3. Canonical identity switch: KC_HOSTNAME, api.irl.coop route, coop-api
   ALLOWED_REDIRECTS, realm-client redirects, plane/gate issuers — 15/15 ad-hoc
   checks + browser E2E.
4. Plane canonicalization: VITE_* build args + api BASE_URLs + CORS; E2E to
   Google sign-in.
5. NocoDB: Gate-SSO + workspaces API ported to source; custom image rebuilt
   (2026.08.1); enterprise-op stubs; default-workspace store row; /404 SPA fix.
   Browser E2E: login → workspace → bases → base views, console clean of the
   functional errors.

## Pending / open

- Stalwart: MinIO blob store wiring + Keycloak OIDC directory (postgres done).
- DMARC hardening: p=none → quarantine after real volume.
- Federation + takedown-resilient DNS/edge design session — PARKED (do nothing
  until Robbie raises it). Fragility points to weigh then: single Gandi account,
  single router WAN IP, one wildcard cert, surfy/this-host split.
- Not in final form: Temporal, Formbricks, Webstudio, Postiz, CryptPad.
- NocoDB cosmetic console noise (not errors, no toasts): `maintenance_staging`
  config probe 404 (OSS baseline), workbox precache /404 (now served as the SPA
  shell), chatwoot iframe refusal, browser-extension content-script chatter.

## Test accounts / credentials locations

- Keycloak realm user `e2e-test@irl.coop` (password resettable via the admin
  API; also the NocoDB super user usysbq274yiq07kv — NocoDB-side password is
  empty from Gate-SSO provisioning, so signin API rejects it; use the gate E2E).
- `gate-sso-test@irl.coop` and `robertbrucepollockjr@gmail.com` (Google-linked)
  exist in the realm.
- Secret VALUES are intentionally not recorded — grep old project versions
  (v1 kept Google creds in .env.example); this repo's .env files hold the live
  values on the host.
