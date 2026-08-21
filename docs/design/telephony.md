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

Seeded grants (7): `group.manage`, `group.members.manage`, `resource.scope`,
`telephony.admin`, `telephony.agent`, `telephony.caller`, `telephony.records.read`.

Seeded roles: `owner` (all 7), `member` (resource.scope, caller, records.read),
`agent` (agent, caller), `telephony-admin` (admin, caller, records.read).

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
  secret never passes through the grant-holder." (Not yet seeded — an 8th grant
  to add beside the existing 7.)

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
