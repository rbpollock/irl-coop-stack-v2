# Telephony (FreeSWITCH + FusionPBX)

Group-aware voice/PSTN for the coop. FreeSWITCH is the softswitch; FusionPBX is
the ops/admin GUI (members never touch it — they use the dashboard "Calls" app).

## Decisions

- **FreeSWITCH + FusionPBX**, not bare FreeSWITCH. The FusionPBX UI is
  ops-only; provisioning goes through the FusionPBX API/DB (mod_event_socket
  for live call events).
- **One FusionPBX domain = the coop.** Groups are *granular resources inside
  it* (extensions, queues, conferences, voicemail, IVR, DID routing), NOT
  per-group FusionPBX domains. FusionPBX domains are heavyweight; group
  scoping belongs in coop-api's `resource_scopes` + RLS, like every other app.
- **SIP/WSS** signaling (mod_sofia + a SIP.js dashboard client), interoperable
  with softphones. Not Verto.
- **Roles as bundles of grants** — the grants-table model (below) is real now,
  with telephony as its first consumer.
- **Operator-authored template catalog**, seeded with defaults (Member, Support
  team, Board room).
- **PSTN DIDs** via a trunk (Telnyx/Twilio as stand-ins until the real
  provider's details land).

## Roles-as-bundles-of-grants

`group_members.roles` stays a `text[]` of role *names*; three tables resolve
them to capabilities:

- `grants(name PK, description)` — the primitive capabilities (additive).
- `roles(id, name UNIQUE, description, builtin)` — named bundles.
- `role_grants(role_id, grant_name)` — role → grant, PK `(role_id, grant_name)`.

`coop_has_grant(gid uuid, grant_name text)` (SECURITY DEFINER, `coop_rls`)
answers "does the current sub hold a role that grants this capability for this
group?" It is the fine-grained layer above `coop_is_owner`/`coop_is_member`.

Seeded grants (9): `group.manage`, `group.members.manage`, `resource.scope`,
`telephony.admin`, `telephony.agent`, `telephony.caller`,
`telephony.records.read`, `telephony.device.provision`,
`telephony.platform.admin`.

Seeded roles: `owner` (group.* + telephony.admin/agent/caller/records.read —
NOT the platform grant), `member` (resource.scope, caller, records.read),
`agent` (agent, caller), `telephony-admin` (admin, caller, records.read),
`platform-admin` (`telephony.platform.admin` only).

## Platform admin (FusionPBX ops gate)

`platform-admin` is the one PLATFORM-scoped role: it grants
`telephony.platform.admin` ("administer the shared FreeSWITCH/FusionPBX
platform") and is **not** bundled by `owner` — so a member being `owner` of
their own 1-of-1 group (which bundles the group-scoped `telephony.admin`) does
*not* admit them to the platform gate.

- **Claim** — `getRolesAndGrants(sub)` resolves the union of the member's roles
  and grants across all their seats; coop-api emits them as `roles` + `grants`
  claims in the coop JWT, the id_token, and `/userinfo`.
- **Gate** — the FusionPBX route (`pbx.irl.coop` → oauth2-proxy) reads the
  `grants` claim: `--oidc-groups-claim=grants --allowed-group=telephony.platform.admin`
  (with `--email-domain=*` as the required baseline, NOT the gate).
- **Promote / demote** — idempotent, operator-only, reproducible:
  `SELECT coop_ensure_platform_admin('<sub>')` /
  `SELECT coop_revoke_platform_admin('<sub>')` (SECURITY DEFINER, in
  `coop_rls.sql`, so they survive a storage-pillar reset). TS wrappers:
  `ensurePlatformAdmin(sub)` / `revokePlatformAdmin(sub)` in `db.ts`. The role
  sits on the member's personal 1-of-1 seat; promotion is additive. Each call
  writes an audit event (`source='platform'`,
  `type=platform_admin.granted|revoked`, `payload={sub,actor}`). The functions
  are locked to a least-privilege `coop_ops` DB role (REVOKE EXECUTE FROM
  PUBLIC + `session_user` guard) so the app's `coop` pool can never self-promote.
- **Fresh-grant re-validation** — `/api/auth/userinfo` re-resolves `roles`/`grants`
  from the DB (not the JWT snapshot), and the gate runs `--cookie-refresh=5m`, so
  a demotion bites within ~5m instead of at next re-login.

### Header SSO into FusionPBX (no second login)

The gate already proves `telephony.platform.admin`; FusionPBX trusts it. In
proxy mode the `pbx` gate forwards the identity as `X-Forwarded-Email`
(`--pass-user-headers`, default on — NOT `--set-xauthrequest`, which is the
nginx auth_request-mode variant), nginx passes it to PHP, and a `header_sso.php`
shim (wired via
`php_admin_value[auto_prepend_file]` in the php-fpm pool — the FastCGI
`PHP_VALUE` route is NOT honored) maps the email to an EXISTING `v_users` row
and calls `authentication::create_user_session($result, $settings)` — note the
second `$settings` arg is required (the method calls `$settings->get('domain',
'time_zone', …)`). No password check.

The user mapping is a **one-time operator step** (runtime data, not declarative):
create a `v_users` row (`username = <coop email>`, `user_email = same`,
`password NULL` — SSO bypasses it, so no password login exists) and a
`v_user_groups` row into the `superadmin` group. The shim deliberately does not
auto-provision users; an unmapped identity falls through to the password login.

> Security: the header is trusted only because FusionPBX's nginx is reachable
> exclusively through the gate (no host port, no direct edge route) and
> oauth2-proxy strips any client-supplied `X-Auth-Request-*` header.

Logout is **global**: FusionPBX's "log out" (`logout.php`, overwritten in the
image) → `302 /oauth2/sign_out?rd=<coop logout>` (clears the gate's
`_oauth2_proxy`) → coop-api `GET /api/auth/logout` (clears `coop_session`) →
`302 https://irl.coop/`. The gate needs `--whitelist-domain=.irl.coop` for the
`rd` hop to `api.irl.coop`.

The gate also serves a **branded error page** instead of a bare 403: a custom
oauth2-proxy `error.html` template (mounted via the sidecar's `dev.volumes` +
`--custom-templates-dir`) shows "Access restricted" with a "Sign in" button
(the global-logout chain) and a "Back to irl.coop" link — so a non-admin who
hits `pbx.irl.coop` gets a sign-in screen, not a raw Forbidden.

## Telephony tables

- `telephony_templates(id, name UNIQUE, kind, description, resources jsonb)`
  — platform catalog (operator-written, all-authenticated read, no RLS).
  `resources` is a bundle: `[{type,name,config}]` where type ∈
  extension/voicemail/conference/queue/ring_group/ivr/did/trunk.
- `group_telephony(id, group_id, template_id, name, config jsonb, status)`
  — a template instantiated for a group. RLS: SELECT = `coop_can_view_group`,
  write = `coop_has_grant(group_id, 'telephony.admin')`.
- `telephony_resources(id, group_id, group_telephony_id, resource_type,
  external_ref, config)` — the concrete FreeSWITCH objects, system-provisioned.
  RLS: SELECT = `coop_can_view_group`; writes are system-only (no user policy).

On provision, each resource also writes a `resource_scopes(group_id,
'freeswitch', external_ref, scoped_by)` row — so call events (CDR) resolve to
their group through the *existing* event/digest fan-out, unchanged.

## Extension identity — every group is a phone

**Every account is a group, and every group gets an extension + ring group** —
no `kind` distinction. A member's dialable identity is simply the extension of
*their own* group; a group's number is its extension, fanned out to members by
its ring group. Nothing is keyed to `groups.kind`: a "personal" group is just a
group that started with one member, and may later seat an assistant who takes
its calls.

| Resource | Scoped to (`group_id`) | Meaning |
|---|---|---|
| `extension` | any group | that group's dialable number |
| `ring_group` | any group | fan-out to the group's members' own extensions |
| queue / ivr / did / conference / voicemail | any group | group routing |

- **A user is their own group** — the signup group (`coop_ensure_personal_group()`),
  whose extension *is* the user's number. One own-group per `sub`, so a user has
  exactly one extension regardless of how many other groups they join.
- **A group gets an extension AND a ring group.** The extension is the group's
  number; the ring group fans it out to members. Adding a personal assistant is
  just seating them in the group — the ring group starts dialing their own
  extension too. No schema change, no `kind` special-case.
- **Groups reference members, not extension numbers.** A ring group resolves
  `group_members → sub → own group → extension` at call time (a coop-api
  dialplan lookup — FusionPBX's own dynamic directory is served by mod_lua's
  xml_handler, not mod_xml_curl), so every group dials each member's *one* live
  extension — no snapshot, no drift, no per-group copy.
- **The 1:1 must be hard.** One own-group per `sub` is the load-bearing
  invariant; `coop_ensure_personal_group()` is idempotent but not race-proof, so
  a partial unique index `UNIQUE (created_by) WHERE kind = 'personal'` enforces
  it (added in db.ts). That `kind` marker is only "the user's own group," not a
  telephony distinction.

### Browserphone integration seam

The dashboard "Calls" app is a SIP.js (Browser-Phone) client. It needs five
values, served by `GET /api/v1/telephony/sip-config` for the caller's own
session: `server` (SIP domain `irl.coop`), `extension`, `password` (the caller's
SIP digest secret, from the Vault), `fullname`, plus the fixed
WSS `port:7443` / `path:/wss`. The n0obHere `core/phone/*.php` glue is
FusionPBX-session-coupled and is **not used** — the config endpoint replaces it,
so the phone registers without a FusionPBX session. The static
`Browser-Phone/Phone/` bundle is vendored into the dashboard (`public/phone/`).

## Endpoints (planned, next slice)

- `GET/POST /api/v1/telephony/templates` (read: authenticated; write: operator)
- `POST /api/v1/groups/:id/telephony` (owner/telephony-admin → enqueue provision)
- `GET /api/v1/groups/:id/telephony` (member)
- `PATCH/DELETE /api/v1/groups/:id/telephony/:tid` (owner/telephony-admin)

## Provisioning + events

**Worker shape.** Request-driven, not a sweep: an owner/`telephony-admin` calls
`POST /api/v1/groups/:id/telephony {template_id}`; coop-api inserts a
`group_telephony` row (`status='provisioning'`) and starts a Temporal workflow
`provisionGroupTelephony` (workflow id `telephony-<id>`) on a **second task queue
`coop-telephony`** — separate from `coop-delivery` so a provisioning backlog never
blocks notification delivery.

**Two databases, two roles.** The workflow touches both:

| DB | Role | Holds |
|---|---|---|
| `irlcoop` (Citus) | `coop` (RLS-scoped) | projection: `group_telephony`, `telephony_resources`, `resource_scopes` |
| `fusionpbx` (Citus) | `fusionpbx` | concrete objects: `v_extensions`, `v_voicemails`, `v_conferences`, … |

`provisionResource` (one per template resource) writes the concrete object to the
`fusionpbx` DB, then stamps the identity bridge in the projection via a
SECURITY DEFINER function (owned by `coop_rls`, like `coop_ingest_event`):

```sql
coop_provision_telephony_resource(group_id, group_telephony_id, resource_type, external_ref, config)
-- → upsert telephony_resources (ON CONFLICT group_id+resource_type+external_ref)
-- → insert resource_scopes (group_id, 'freeswitch', external_ref, 'system')
```

That `resource_scopes` row is what makes call events group-aware with **no new
event plumbing** — CDRs resolve to their group through the existing
`coop_ingest_event` fan-out unchanged. The final activity runs ESL
`api reloadxml` and flips `status → active` (`→ error` on hard failure; Temporal
retries transient ones first).

**Event ingress.** A `mod_event_socket` listener → coop-api →
`coop_ingest_event(source='freeswitch', …)` + Redis `irl:notify:{sub}`; Temporal
workflows for multi-step events (missed → voicemail → transcribe → notify →
callback).

### Device credentials live in the user Vault

Extension/SIP passwords are **user secrets**, not platform secrets. The
provisioning activity *fetches* them through a scoped Vault read — it never
generates or owns them (delegation, not custody — see
`delegation-and-session-keys.md`). Three copies, three different contents:

| Copy | Holds | Why |
|---|---|---|
| user Vault | the raw credential | source of truth, member-owned |
| `v_extensions.password` | a **hash** | enforcement copy for SIP digest |
| `telephony_resources.config` | a **`vaultRef` pointer only** | keeps the secret out of the projection |

The projection, the event store, and the bus therefore carry **no credential
material** — only `external_ref` + a pointer. The Vault is not built yet, so the
activity is written against a `vaultClient` interface (stub now), sealing that
contract before the store exists.

### Blind provisioning — set up a softphone without seeing the password

A member may grant an admin (or support role) the right to *set up their
softphone* without the admin ever seeing the unhashed credential. This is a new,
selectively-grantable, revocable grant:

- **`telephony.device.provision`** — "provision/rotate a member's device; the
  secret never passes through the grant-holder." (Seeded; not yet bundled into
  any builtin role — grant it explicitly to an admin/support role.)

The flow splits into **authorize** (the grant check) and **enroll** (the device
fetches its own secret), so the secret moves *device ↔ Vault* directly:

1. **One-time enrollment token / QR.** The admin triggers provisioning and gets a
   short-lived token/QR — not the password. The member scans it; the device
   exchanges the token for its credential over TLS.
2. **Auto-provisioning URL.** The softphone fetches its config + credential from
   an HTTPS provisioning endpoint (reads the Vault server-side); the admin only
   hands over a URL.
3. **Dashboard SIP.js self-fetch.** The member's own authenticated session reads
   the credential from the Vault and registers — no human sees the raw password
   at all.

Invariant: the raw secret exists in exactly two places — the member's Vault and
the member's device. Authorizers, logs, the projection, and the event store see
only handles/tokens. (FreeSWITCH keeps a hash for digest; the softphone needs the
raw value to *compute* the digest at REGISTER, which is precisely why only the
device and the Vault ever hold it.)

**Open items before implementation:** the exact FusionPBX `v_*` column map beyond
`v_extensions`; the hash scheme for `v_extensions.password`; and the Vault's
grant model for its two distinct consumers (the provisioning activity vs the
member's register-time self-fetch).

## Feasibility spike (first build step)

Stand up FusionPBX + FreeSWITCH (its `fusionpbx` DB on the shared Citus, like
keycloak), enable mod_sofia WSS, and prove a browser SIP.js client registers
and completes an internal SIP call — before any group wiring.
