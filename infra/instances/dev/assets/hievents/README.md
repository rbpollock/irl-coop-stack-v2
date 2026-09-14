# Hi.Events Gate SSO patch (durable source of truth)

The custom image `irlcoop/hievents-gate-sso` (referenced in
`infra/instances/dev/apps/hievents.yaml`) is upstream
[HiEventsDev/Hi.Events](https://github.com/HiEventsDev/Hi.Events) at tag
`v1.11.1-beta` — the version this stack runs (`VERSION` says `1.11.0-beta`) —
with one patch on top: **`irlcoop-gate-sso.patch`**.

The stack owns no push access to upstream and the working clone
(`/home/service/build/hievents-src`, persistent — not tmpfs) is a build scratch
dir, so this directory is the durable copy of the patch.

## Why a patch at all

Hi.Events 1.11.x has native email/password auth only — no OIDC/Socialite
anywhere in the backend — while every other coop app joins the fleet identity
through the **oauth2-proxy gate → coop-api OIDC → `x-forwarded-email`** pattern
(nocodb-gate, webstudio-gate, formbricks-gate, fusionpbx-gate, s3-gate). So
Hi.Events joins the same way, with the "Log in with irl.coop" door on its own
auth screen (the webstudio shape) rather than a bare bounce.

## What the patch does

| File | Change |
|---|---|
| `backend/app/Http/Actions/Auth/GateSsoAction.php` | NEW — `GET /api/auth/gate-sso`: find-or-create the member + account from the forwarded address and mint a Hi.Events JWT (`JWTAuth::claims(['account_id' => …, 'role' => …])->fromUser()`), returning it as JSON and as the `token` cookie. |
| `backend/routes/api.php` | registers that route in the unauthenticated `/auth` group. |
| `backend/config/app.php` | `coop_gate_sso_enabled` / `coop_gate_sso_email_header` / `coop_gate_sso_secret` (env: `GATE_SSO_ENABLED`, `GATE_SSO_EMAIL_HEADER`, `COOP_GATE_SSO_SECRET`). |
| `backend/app/Services/Application/Handlers/Account/CreateAccountHandler.php` | `handle(CreateAccountDTO, bool $bypassRegistrationCheck = false)` — gate provisioning passes `true`, so a closed native signup can never lock a fleet member out of their own account. |
| `frontend/server.js` | the SSR exchanges `x-forwarded-email` for the `token` cookie on gated document requests (`GATE_SSO_ENABLED=true`): no live session → mint server-to-server → set the cookie → 302 back. |
| `frontend/src/components/routes/auth/Login/index.tsx` | the primary **"Log in with irl.coop"** button (`/oauth2/sign_in?rd=/manage/events`) above the native form, which stays as the fallback; the "Sign up" link is replaced by "Access is through your irl.coop account" when gate SSO is on. |
| `frontend/src/router.tsx` | `/auth/register` → loader `redirect("/auth/login")` (a real SSR 302) — native signup is retired, not left as a dead end. |
| `frontend/src/types.ts` | the `VITE_GATE_SSO_ENABLED` config key (frontend reads it via `getConfig`, i.e. `window.hievents` ← any runtime `VITE_*` env). |
| `backend/app/Services/Domain/Coop/CoopWorkspaceProvisioner.php` | **NEW** — coop groups → one Hi.Events account each (tier map, organizer per group, converges every sign-in). |
| `backend/database/migrations/2026_09_12_120000_add_external_ref_to_accounts.php` | **NEW** — `accounts.external_ref`, the rename-safe workspace key (`coop:<slug>` / `personal:user:<id>`). |
| `backend/app/Http/Actions/Auth/ListWorkspacesAction.php` | **NEW** — `GET /api/auth/workspaces` (the switcher's list). |
| `backend/app/Http/Actions/Auth/WorkspaceSwitchAction.php` | **NEW** — `GET /api/auth/workspace/{account_id}` re-mints the session for another workspace. |
| `frontend/src/hooks/useWorkspaces.ts` | **NEW** — the workspaces query + `switchWorkspace()` navigation helper. |
| `frontend/src/components/common/GlobalMenu/index.tsx` | the **Workspaces** block in the avatar menu (one entry per workspace, current one ticked). |

### Group workspaces (2026-09-12) — one account per coop group

Hi.Events' tenant boundary is the **account**, so a coop group maps onto an
account and the member's group seats become memberships in it. On every sign-in
the app converges on what the coop says (the group is the source of truth):

| What | How |
|---|---|
| group workspace | one account per group, keyed by the new `accounts.external_ref = coop:<slug>` (migration `2026_09_12_120000_add_external_ref_to_accounts.php`) — rename-safe, unlike keying on the account name |
| the member's own | their 1-of-1 group → `external_ref = personal:user:<id>`; a pre-group-workspace account they own is ADOPTED into that ref (existing events stay put) |
| seat → role | the TIER MAP in `CoopWorkspaceProvisioner::ROLE_TO_ACCOUNT_ROLE`: `owner` → ADMIN + account owner, `member` → ADMIN, anything else (e.g. `agent`) → ORGANIZER. Converges on every sign-in, so a demotion bites |
| group page | one organizer per group workspace, created LIVE (name = group name), so `{group}` events have a public home |
| who is switched in | `?group=<slug>` → that group; `?account_id=<id>` → any account they're seated in; otherwise their own workspace |
| switching | `GET /api/auth/workspace/{account_id}?rd=…` re-mints the session for that account and redirects into the admin (a plain navigation from the avatar menu's **Workspaces** list, `GET /api/auth/workspaces`) |

The coop `groups` claim rides the gate: coop-api mints `groups` as a JSON STRING,
the gate forwards it as `x-forwarded-groups` (`--oidc-groups-claim=groups`), the SSR
hands it to the mint endpoint, which provisions before minting. A malformed claim
is logged and ignored — a claim problem must never cost a member their session.

**FOLLOW-ON**: per-group overrides ("this member is a workspace admin" independent
of their seat role) need a group-settings column on the coop side surfaced in the
claim; today the tiering is driven by coop seat roles alone and lives in one
constant. Also deferred: per-group custom domain and per-group mail identity.

### Coop event bus (2026-09-12) — automatic, per event

Every ticketing event carries its own webhook into the coop event bus, created by
the app itself — no clicking through the webhook UI, and nothing to remember when
a new event is made. Sales, attendees and check-ins then land on the workspace's
**stream**: a
group workspace's activity on the **group's** stream (RLS shows it to every
member), a personal workspace's on that member's own.

| piece | where |
|---|---|
| `CoopEventBusWebhookProvisioner` | builds the bus URL for an event's workspace and upserts the `webhooks` row. Target is baked into the URL: `?group=<slug>` for a `coop:<slug>` account, `?owner=<email>` for a personal one (keyed on `accounts.external_ref`, same as the group workspaces). Refreshes `event_types`, drops rows whose target went stale. No-op when `COOP_EVENT_BUS_URL` is unset. |
| `AppServiceProvider::boot()` | `Event::created(...)` → provision, so new events are covered the moment they're made. |
| `CoopEventBusSyncCommand` (`coop:event-bus:sync`) | reconciles every existing event; `startup.sh` runs it on every boot (idempotent, never fatal). |
| `WebhookDispatchService` | for a coop-bus URL, adds `Authorization: Bearer $COOP_EVENT_BUS_SECRET` + `X-Coop-Event-Source: hi-events`, and a `coop` block (`event_id`, `account_id`, `webhook_id`) beside `payload` so the consumer doesn't have to parse the resource shape. |

Subscribed types (`COOP_EVENT_BUS_EVENTS`): `order.created`,
`order.marked_as_paid`, `order.refunded`, `order.cancelled`,
`attendee.created`, `attendee.cancelled`, `checkin.created`, `event.created`.

The coop side (`apps/coop-api/src/hi-events.ts`) maps them to bus types
(`order.created`, `order.paid`, `order.refunded`, `order.cancelled`,
`attendee.registered`, `attendee.cancelled`, `checkin.recorded`,
`event.created`), strips personal data from the payload — **counts and ids
only**, no buyer/attendee names or addresses — and ingests: on the group's stream
via `coop_ingest_group_event` (a definer function, since a system caller has no
RLS identity), or on the member's personal stream via the existing
`coop_ingest_event`. Group members get the live-lane notification (Redis
`irl:notify:{sub}`) through `publishToGroupMembers`; the payload carries
`refs`/`counts`/`fields`/`link` so a Temporal workflow can act on it and the
dashboard renders "3 tickets · backyard dance party".

Verify: `scripts/verify-hievents-bus.py` (10/10 — auth, unknown group, group
targeting, PII stripping, personal targeting, unsubscribed type, cleanup).

### Signup is closed (2026-09-12)

`APP_DISABLE_REGISTRATION=true` in the spec: `POST /api/auth/register` → 403,
`/auth/register` → 302 to the login screen, and no "Sign up" affordance in the UI.
Members are provisioned from the fleet identity instead. The password **login**
form stays (fallback for invites + the pre-SSO local admin); `Forgot password?`
still works, so a gate-provisioned member can set a local password if they ever
need the fallback. Invitations remain admin-initiated (not open signup).

### Auth model, as found

- Sessions are the `token` cookie (JWT, HS256 via `JWT_SECRET`, `Secure;
  SameSite=None`) — jwt-auth's cookie parser reads it, `entry.server.tsx` copies
  it into the axios auth header for SSR, and the browser sends it on XHR
  (`withCredentials`). `localStorage.token` is only used by the impersonation
  flows, so a cookie is enough for a full session.
- The token must carry `account_id` (and `role`) claims — `SetAccountContext`
  resolves the account context from them, exactly as `LoginService` mints them.
- Member provisioning reuses `CreateAccountHandler` (default account
  configuration + messaging tier + an ADMIN owner association), so gate-created
  accounts look like signup-created ones. It honours `APP_DISABLE_REGISTRATION`:
  flipping that to `true` disables SSO provisioning too (**follow-on** — split
  the flag if native signup should close while SSO provisioning stays open).
  It also queues the usual confirmation mail (`MAIL_MAILER=log` today).

### Trust boundary (do not weaken)

`/api/auth/gate-sso` mints a session from a header, so it requires **(1)** the
derived shared secret `COOP_GATE_SSO_SECRET` (`hash_equals`) and **(2)** a
loopback caller (`REMOTE_ADDR` ∈ {127.0.0.1, ::1}). Only the SSR holds the
secret and only the SSR talks to nginx over loopback; a public request arrives
via traefik/the gate with a non-loopback peer, and the two checks together make
a spoofed `X-Forwarded-Email` useless.

## Base + rebuild

```bash
bash infra/build/images/hievents/build.sh 1.11.1-beta.2   # IMAGE tag (bump per patch change)
```

The script clones/fetches `v1.11.1-beta` (`UPSTREAM_TAG`, fixed) into
`/home/service/build/hievents-src`, `git reset --hard`s to a clean upstream tree,
`git apply`s this patch, and builds `Dockerfile.all-in-one` (~10-20 min: yarn
build + composer install) into `irlcoop/hievents-gate-sso:<IMAGE tag>`. Tag
history: `1.11.1-beta` (gate SSO + coop login screen), `1.11.1-beta.2` (+ signup
closed). Then bump the tag in `hievents.yaml`, regenerate, and
`up -d hievents hievents-gate`.
