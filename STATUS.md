# STATUS.md — irl.coop v2 infrastructure status

Last updated: 2026-08-10 (code-exchange round: per-client id_token iss/alg + nonce echo in coop-api; nocodb PWA behind the gate — skip-auth-route + image 2026.08.2; matrix + nocodb browser E2E green).

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

**Bring the WHOLE stack up (boot / after a reboot / after edits):**
`bash infra/scripts/stack-up.sh` — idempotent `docker compose up -d` for every
generated pillar + source apps (plane) + drifted bootstraps (stalwart16 if its
compose still exists); exits nonzero if any project fails. This is what the
enabled systemd unit `irl-coop-stack.service` runs at boot
(After=docker.service, oneshot, RemainAfterExit; a failed bring-up lands the
unit in a visible `failed` state).

**Status interface (declared-vs-running):**
- `GET /api/v1/stack/status` (coop-api, auth-gated) — reconciles the generated
  tree (compose services per pillar + source-app composes) against `docker
  ps -a` (compose project/service labels). Per-pillar up/down, missing
  services, health, and drift (running-but-undeclared = orphans).
- Dashboard home (`/en/dashboards/overview`) renders it live in the
  "Stack health" section (replaces the old mock vitals / fake shard nodes).
- `infra/scripts/stack-report.py` — stdlib-only twin (no yaml dep: reads
  `docker compose config --services`); prints the same report for login
  motd (`/etc/update-motd.d/99-irl-coop-stack`) and writes the JSON snapshot
  to `/var/lib/irl-coop/stack-status.json` during bring-up.

`enabled: false` on an app spec = declared-but-not-wired: the generator skips
its compose service, edge route, OIDC registry entry and inventory (webstudio,
formbricks, postiz are parked this way — their images aren't deployable).

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
- Plane CE (https://plane.irl.coop, :3002 via Caddy — migrated from
  app.irl.coop 2026-08-12): web/admin/space/live images rebuilt with canonical
  VITE_* args; api runtime APP/ADMIN/SPACE/LIVE_BASE_URL + CORS canonical
  (localhost dev origins kept); live app env canonical.
  **Zero-click SSO**: the sign-in page auto-redirects to the fleet gateway
  (once per browser session; button remains as fallback, relabeled
  "with irl.coop") — an active dashboard session returns an instant code, so
  plane.irl.coop lands logged-in with no interaction. Verified E2E.
  E2E: plane.irl.coop → gateway → Keycloak → Google sign-in verified.
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

## Mail pillar — LIVE (webmail deployed 2026-08-09)

- Stalwart v0.16, container `communication-stalwart-1` (GENERATED — old
  `stalwart16` bootstrap removed 2026-08-12), webadmin :8083; postgres store
  (23 tables in citus); internal directory; permanent admin `admin@irl.coop`.
  Webadmin login = recovery admin `admin` + derived `stalwart.recovery-admin`
  (secrets.env; container env `STALWART_RECOVERY_ADMIN`), via the
  `STALWART_RECOVERY_ADMIN` env; container runs `-p 8083:8080` +
  `--add-host localhost:172.17.0.1`.
- **Store config reconstruction (2026-08-12)**: the old /tmp config.json was
  wiped; the citus store survived, so only the connection file was rebuilt —
  root `@type: PostgreSql` + tagged authSecret (schema from v0.16 source;
  full recipe in the skill reference). `postgres.stalwart` now declared in
  the spec so secrets.env carries POSTGRES_STALWART.
- **Blob store: S3 → MinIO** (DONE 2026-08-08): bucket `stalwart`, endpoint
  http://172.17.0.1:9000, region us-east-1, access key stalwart-s3 (scoped
  bucket policy) — set via x:BlobStore/set (registry singleton).
- **Directory: OIDC → fleet gateway** (DONE 2026-08-09, was Keycloak): Directory
  object `i10l3erdksaa` (issuer https://api.irl.coop, requireAudience
  `irl-coop`, claimUsername email, usernameDomain irl.coop, claimName name,
  claimGroups groups); Authentication singleton directoryId pointed at it
  (defaultUserRoleIds `{b: true}` intact). OIDC-caveat handled: accounts
  pre-created (e2e-test, gate-sso-test, robertbrucepollockjr + admin) so
  inbound mail isn't rejected before first auth.
- **Webmail `roundcube`** (LIVE 2026-08-09): image `irlcoop/roundcube-oidc:1.6`,
  edge https://webmail.irl.coop → :8084; OIDC client `roundcube` on the
  gateway (confidential, PKCE S256, redirect /index.php/login/oauth; the coop
  JWT aud is `irl-coop` — roundcube passes the token through as a bearer
  credential and stalwart's OIDC directory validates it);
  Citus DB `roundcube` (pgsql env, schema initialized); IMAP/SMTP legs
  tls://172.17.0.1:143/:587 with peer-verify off (bridge IP can't match the
  wildcard cert). Browser E2E PASSED 2026-08-09: SSO → mailbox → compose →
  send → delivered to inbox (IMAP + SMTP XOAUTH2 both authenticate through
  the OIDC directory).
- **Stalwart OIDC-directory gotchas** (root causes of the 2026-08-09 auth saga):
  (1) accounts must resolve to roles or every protocol rejects the
  otherwise-valid token (IMAP kills the connection, SMTP 550, JMAP 403). Fix:
  Authentication singleton `defaultUserRoleIds = {"b": true}` (User role, Map
  syntax `{roleId: true}`) — applied in the webadmin API. Config changes only
  take effect on a FULL container restart (`x:Action ReloadSettings` skips the
  security/role config); after every restart there is a 5-minute JWKS
  cold-cache window where OIDC auths fail ("Unknown key id" — the cache only
  refetches after 300s). (2) **A full-object update that CARRIES the `id`
  field clobbers the singleton**: the rebuild's Authentication update included
  `id: "singleton"` from the GET copy → after a reload/restart `directoryId`
  was `None` → bearer tokens fell to the internal OAuth path (`auth.error`
  "Failed to decode token… make sure it is configured as the default directory
  under the Authentication object", SMTP 454, IMAP NO [AUTHENTICATIONFAILED]).
  Fix: strip `id` from the update payload, then restart. (3) **The coop JWT
  must carry a `scope` claim**: with the directory live, auth moved to 535
  "Missing required scope 'openid', present scopes: []" — the minted JWT had
  no scope. Fix: `scope: "openid profile email"` added to mintCoopJwt
  (auth.ts). The stdout tracer (`@type: Stdout`, level debug → docker logs)
  is what surfaced these — the file tracer wrote nothing.
- **full-kit embed** (DONE 2026-08-09): nav item "Webmail" (Apps section) →
  /apps/webmail — full-height iframe of webmail.irl.coop + "Open full screen"
  button; roundcube `x_frame_options = false` to allow framing; auto-login in
  the iframe works via the shared Keycloak realm session (verified in browser).
- **Canonical-identity provisioning** (DONE 2026-08-09): accounts are
  decoupled from login method (Google/web3auth/passkeys/… all map to one
  canonical user). The mailbox is `<username>@irl.coop`, claimed on first
  webmail use: the full-kit webmail page gates on the session email — if it
  isn't @irl.coop it shows the claim panel → coop-api `POST /api/v1/me/username`
  (coop JWT auth, service account + manage-users) sets the Keycloak email →
  stalwart self-provisions the mailbox on first auth (the OIDC directory
  creates the account when the email claim is @irl.coop). Browser E2E passed
  (foreign-domain test user → claim → mailbox). Robbie's canonical identity:
  robertbrucepollockjr@irl.coop (gmail kept as the login/federated identity).
- **Chat widget SSO: frame policy fixed** (DONE 2026-08-09): the widget's
  in-iframe SSO showed "auth.irl.coop refused to connect" — the realm's
  `browserSecurityHeaders.xFrameOptions: SAMEORIGIN` blocked the frame
  despite the CSP. Fixed both layers: realm xFrameOptions → NONE (admin API)
  and the keycloak spec's `KC_XFRAMEOPTIONS: "NONE"` env (declarative — the
  realm setting wins at runtime, the env documents the intent). Live-verified:
  the login page now sends `x-frame-options: NONE` + the CSP
  `frame-ancestors 'self' https://*.irl.coop` — the frame control is the CSP
  alone. The in-iframe click itself is unverifiable by the automation
  (synthetic clicks don't drive the cross-origin iframe's React handlers).
- **Chat widget SSO: zero-password** (DONE 2026-08-09): the element-web
  config gained `sso_immediate_redirect: true` and the `matrix` client's
  `consentRequired` is false — the widget's SSO now auto-authenticates from
  the realm session (no credentials; browser-E2E: the Keycloak redirect
  logged in as E2E Tester with no password). Remaining first-run friction is
  element-web's own E2EE device-verification flow (one-time, product-level);
  after it, the matrix session persists in the widget origin and the widget
  opens directly into the chat. The sso_immediate_redirect option did not
  visibly auto-bounce the welcome page in testing — possibly needs a
  companion setting in element-web 1.12.
- **Chat widget LIVE** (DONE 2026-08-09): the dashboard's bottom-right
  "Coop chat" button opens an Element Web panel (iframe of element.irl.coop,
  NEXT_PUBLIC_ELEMENT_URL, i18n en/ar). The realm's `browserSecurityHeaders`
  contentSecurityPolicy now sets `frame-ancestors 'self' https://*.irl.coop`
  so the SSO completes inside the widget iframe (admin API PUT on the realm —
  the Keycloak container untouched). In-iframe SSO chain browser-proven
  top-level; the frame policy verified live via the response headers.
- **Matrix stack LIVE** (DONE 2026-08-09): Synapse (federation disabled,
  `matrix.irl.coop`), Element Web (`element.irl.coop` — also the dashboard
  widget source), Element Call (`call.irl.coop`), coturn (host network, TURN
  3478). One Keycloak client `matrix` (confidential) — the web clients ride
  the homeserver SSO; the localpart derives from the EMAIL claim
  (`{{ user.email.split('@')[0] }}` — the gmail-username trap avoided again).
  Shared Citus postgres (matrix db, C collation) + MinIO media (matrix-media/
  matrix-s3). Custom images: irlcoop/synapse-s3 (S3 media provider) +
  irlcoop/element-web (official tarball v1.12.18); element-call is the
  official GHCR image. Browser-E2E: Element Web → SSO → Keycloak → room list
  (@e2e-test:matrix.irl.coop). Pitfalls learned: the element-call image's
  nginx listens on 8080 (not 80); single-file bind mounts hold the OLD inode
  after an atomic write_file replace (recreate the container); config files
  written 0600 403 the nginx (chmod 644); the generator needed a network_mode
  passthrough; a zombie docker-proxy held host 8084 (needs a manual sudo
  pkill — port moved to 8086). Pending: the dashboard side-chat widget;
  router forwards for the TURN range (WAN calls).
- **Robbie's webmail fixed** (DONE 2026-08-09): the last roundcube login
  blocker was the OIDC directory's `claimUsername: preferred_username` — the
  Google broker sets the Keycloak username to the gmail address
  (`robertbrucepollockjr@gmail.com`), and account resolution split at the last
  `@` → domain `gmail.com` → "Account domain does not exist" even for the
  existing account. Directory switched to `claimUsername: email` (accounts
  derive from the canonical email claim) + full restart; verified via raw
  IMAP probe and the browser (full mailbox for robertbrucepollockjr@irl.coop).
  This also makes future Google users immune to the username quirk.
- **Dashboard/nav persona redesign** (DONE 2026-08-09): sidebar reorganized by
  member personas — Coop (Home, Projects/Plane, Databases/NocoDB, Webmail),
  Administration (Shard Nodes, Members, Safes), Account (Profile, Settings),
  Build (API); the template Pages group, demo apps and Design System library
  removed from the nav (routes stay reachable). Home page
  (/dashboards/overview): time-of-day greeting with the member's name +
  status-tailored banner (the canonical-identity claim CTA for non-@irl.coop
  emails), a quick-access hub (one hop to every important subject), then the
  coop vitals. Verified 18/18 + browser.
- **Landing page as the default homepage** (DONE 2026-08-09): the root (/)
  serves a redesigned irl.coop landing (data from irlcoop.vercel.app + the
  live stack config). Hero "We're here for cooperation." + prominent
  Sign up / Log in → /sign-in; apps grid (Dashboard, Projects/Plane,
  Databases/NocoDB, Webmail, Mail & Storage, API) with user-friendly copy
  from the app specs; one-identity section; the eight pillars with LIVE
  markers. The former root dashboard moved to /dashboards/overview
  (auth-gated); the template landing deleted; middleware HOME_PATHNAME
  default → /dashboards/overview. Verified 21/21 + browser.
- **coop-api as the fleet OIDC issuer** (SLICE 1 DONE 2026-08-09, Robbie's
  Shape-2 decision): the fleet stops showing the Keycloak page. coop-api
  serves discovery + `/jwks` at https://api.irl.coop; the coop JWT is now
  RS256 (keypair in the gitignored .env `COOP_JWT_PRIVATE_KEY_B64`); client
  registry `OIDC_CLIENTS` env (plane/nocodb-gate/roundcube/web-app/nextauth —
  existing secrets + redirect URIs); `coop_session` cookie (HttpOnly, Secure,
  SameSite=Lax, .irl.coop, 30d) — authorize issues a code directly from the
  session (no Keycloak redirect); `POST /api/auth/login` = password
  direct-grant (zero redirect). Verified: 12/12 ad-hoc + full-kit login green.
  SLICE 2 DONE 2026-08-09 (see below): roundcube → plane → nocodb-gate →
  matrix → stalwart all on the gateway. Remaining: the full-kit sign-in page
  switching to the password-login endpoint, and (later) the coop-owned
  interactive ceremony for Google/passkey/QR (one flow, then cookie-everywhere).
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

## Fleet session-gateway migration (slice 2) — COMPLETE (2026-08-09)

Goal: every app's "Sign in with irl.coop" answers from the `coop_session`
cookie via coop-api's authorize — instant, no Keycloak page, no credentials,
after the dashboard login. The gateway (slice 1) is live and **curl-proven**:
`POST /api/auth/login` (e2e-test direct-grant) → `coop_session` cookie →
`GET /api/auth/authorize?client_id=matrix…` → **instant code** to
`https://matrix.irl.coop/_synapse/client/oidc/callback?code=…` (no Keycloak).

- **DONE — matrix/element-web:** `matrix` added to coop-api `OIDC_CLIENTS`
  (apps/coop-api/.env, gitignored — secret = the homeserver.yaml's
  `client_secret`, redirect `https://matrix.irl.coop/_synapse/client/oidc/callback`);
  `infra/instances/dev/config/matrix/homeserver.yaml` OIDC provider →
  `issuer: https://api.irl.coop`, `idp_id: coop-gateway`; coop-api restarted
  (proc — `/tmp/coop-api-dev.log`), matrix container recreated, healthy.
  **Verified 2026-08-09:** authorize?client_id=matrix with the session cookie
  → 302 instant code to the Synapse callback (no Keycloak).
- **DONE — nocodb-gate:** `apps/nocodb.yaml`
  `--oidc-issuer-url=https://api.${DOMAIN}` (+ removed the now-unused
  `extra_hosts` auth entry); regenerated + `up -d --force-recreate nocodb-gate`
  applied. **Verified:** `/oauth2/start` 302s to
  `api.irl.coop/api/auth/authorize?client_id=nocodb-gate…`; cookie flow →
  instant code to the gate callback.
- **DONE — roundcube:** the baked `infra/compose/communication/roundcube/config.inc.php`
  oauth2 URIs → the gateway (`oauth_auth_uri/token_uri/identity_uri` →
  `api.irl.coop/api/auth/*`), image `irlcoop/roundcube-oidc:1.6` rebuilt,
  container recreated, webmail 200 through the edge. **Verified 2026-08-09:**
  cookie flow → instant code to `/index.php/login/oauth`. (Container boots with
  a wait-for-it DB delay — the edge 502s until apache is up; the callback URL
  returns 200 with the login flow, not a redirect — neither is a failure.)
- **DONE — plane:** OIDC config lives in `/home/service/plane/apps/api/.env`
  (env_file on the compose api service — NOT the DB). `OIDC_ISSUER` flipped to
  `https://api.irl.coop`; coop-api registry plane redirects fixed to the HTTPS
  form (`https://app.irl.coop/auth/oidc/callback/` — was `http://`, which the
  gateway's exact-match rejects); api container recreated. **Required gateway
  change:** the minted coop JWT + userinfo now carry `email_verified: true`
  (plane's OIDC adapter hard-rejects userinfo without a truthy email_verified)
  and userinfo gained `picture` (plane reads `picture`, coop emits `avatar`).
  **Verified:** `https://app.irl.coop/auth/oidc/` → 302 to
  `api.irl.coop/api/auth/authorize?client_id=plane…`; full SSO chain
  (initiate → instant code → plane callback → app) lands on app.irl.coop with
  no Keycloak and no error page.
- **Fleet-wide instant-path verification PASSED 2026-08-09** (one cookie,
  four apps): `POST /api/auth/login` (e2e-test) → authorize for
  plane/roundcube/matrix/nocodb-gate → each returns **302 + instant code** to
  its own callback, no auth.irl.coop anywhere. Browser E2E of the instant path
  (fresh login → each app) still TODO — the automation's browser predates the
  gateway restart; the user's real browser gets the cookie at dashboard login.
- **DONE — stalwart** (2026-08-09): the webadmin 500s were the shared Citus
  postgres (`storage-postgres-1`, 172.17.0.1:5432) being DOWN with an EMPTY
  data dir (recreated 14:33 with POSTGRES_PASSWORD unset → boot refused) —
  not a stale-pw trap. The data was unrecoverable (no backups; volume sweeps
  denied), so the reset was **additive**: fresh citus up (compose storage
  pillar; `POSTGRES_PASSWORD` env restored), roles/dbs provisioned
  (irlcoop/matrix/nocodb/roundcube/stalwart; matrix db recreated with C
  collation for synapse), all fleet containers recreated, and stalwart's
  entire config rebuilt from the admin API (domain irl.coop, OIDC directory
  → **https://api.irl.coop** — the queued fleet-gateway flip landed — aud
  `irl-coop`, claimUsername email, accounts admin/e2e-test/gate-sso-test/
  robertbrucepollockjr, blob store S3→MinIO, listeners 587+143 STARTTLS,
  DKIM, SystemSettings defaultHostname mail.irl.coop). Citus port publishing
  fixed in `apps/citus.yaml` (`0.0.0.0:5432:5432` — was 127.0.0.1, the reason
  every fleet container lost postgres). **OIDC auth verified 2026-08-09:**
  IMAP :143 `OK … Authentication successful`, SMTP :587 `235 2.7.0
  Authentication succeeded.`, webmail edge 200 — all from a coop JWT
  (issuer api.irl.coop, aud irl-coop). Full rebuild procedure in the
  `citus-postgres-reset` + `stalwart-registry-config` skill references;
  original setup scripts survive at /tmp/hermes-stalwart-*.py.
- **DONE — code-exchange round (2026-08-10, browser E2E):** the instant-code
  first hop was never the whole story — the CALLBACKS 500'd once a real
  browser exchanged the code. Two gateway fixes in `apps/coop-api/src/auth.ts`:
  (1) **id_token issuer/algorithm per client** — strict OIDC consumers
  (oauth2-proxy, Synapse) validate the id_token against the DISCOVERED issuer
  via /jwks; the token endpoint now mints RS256/iss=`https://api.irl.coop`/
  aud=`<client_id>` for every client except `nextauth` (which keeps its
  HS256/iss:`coop-api` shape for the NextAuth provider config). Was: one
  HS256/iss:coop-api id_token for all → gate 500 "id token issued by a
  different provider, expected https://api.irl.coop got coop-api".
  (2) **nonce echo** — Synapse requires the id_token to carry the nonce it
  sent at authorize (`missing_claim: Missing "nonce" claim`); the authorize
  handler now captures `nonce` (instant path + Keycloak-bounce state) and the
  token endpoint echoes it. **Browser E2E 2026-08-10:** nocodb (gate) →
  dashboard + workspace render, console ZERO errors; element/matrix → logged
  in as @e2e-test:matrix.irl.coop, sync live, crypto keys created. Ad-hoc
  verified: id_token RS256/iss/aud + nonce echo (matrix + nocodb-gate paths).
- **DONE — nocodb PWA behind the gate (2026-08-10):** the browser's first-load
  `/manifest.webmanifest` fetch is no-credentials → the gate 302'd it to
  authorize → cross-origin redirect CORS-blocked (manifest never installs),
  and workbox `bad-precaching` on `/200` killed the SW install. Fixes:
  (1) `apps/nocodb.yaml` gate gained `--skip-auth-route` for
  `/manifest.webmanifest`, `/sw.js`, `/favicon.ico`, `/robots.txt` (data
  paths stay gated); (2) image rebuilt `2026.08.0` → **`2026.08.2`** —
  `gui.middleware.ts` answers BOTH `/404` and `/200` with the SPA shell
  (workbox precaches both; 2026.08.1 only did /404), and the spec had drifted
  to the pre-workspaces-API `.0` (the `/api/v1/workspaces` 404s). Verified:
  pre-login files 200 unauthenticated, `/` still 302, `/api/v1/workspaces`
  401 (registered, was 404), browser console clean.
- **TODO:** fleet browser E2E from a FRESH coop_session login (dashboard →
  each app instant) once the user's browser picks up a fresh gateway session;
  the automation browser completes the full flow but through the Keycloak
  bounce (no stored cookie).

## Pending / open

- DMARC hardening: p=none → quarantine after real volume.
- Federation + takedown-resilient DNS/edge design session — PARKED (do nothing
  until Robbie raises it). Fragility points to weigh then: single Gandi account,
  single router WAN IP, one wildcard cert, surfy/this-host split.
- Not in final form: Temporal, Formbricks, Webstudio, Postiz, CryptPad.
- NocoDB cosmetic console noise (not errors, no toasts): `maintenance_staging`
  config probe 404 (OSS baseline), chatwoot iframe refusal, browser-extension
  content-script chatter. (The workbox precache /404 + /200 warnings are FIXED
  in 2026.08.2 — both serve the SPA shell.)

## Test accounts / credentials locations

- Keycloak realm user `e2e-test@irl.coop` (password resettable via the admin
  API; also the NocoDB super user usysbq274yiq07kv — NocoDB-side password is
  empty from Gate-SSO provisioning, so signin API rejects it; use the gate E2E).
- `gate-sso-test@irl.coop` and `robertbrucepollockjr@gmail.com` (Google-linked)
  exist in the realm.
- Secret VALUES are intentionally not recorded — grep old project versions
  (v1 kept Google creds in .env.example); this repo's .env files hold the live
  values on the host.
