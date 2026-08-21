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

A Temporal activity (`coop-telephony` queue) provisions via the FusionPBX
API/DB and records `telephony_resources` + `resource_scopes`, flipping
`group_telephony.status`. A mod_event_socket listener → coop-api →
`coop_ingest_event(source='freeswitch', …)` + Redis `irl:notify:{sub}`;
Temporal workflows for multi-step events (missed → voicemail → transcribe →
notify → callback).

## Feasibility spike (first build step)

Stand up FusionPBX + FreeSWITCH (its `fusionpbx` DB on the shared Citus, like
keycloak), enable mod_sofia WSS, and prove a browser SIP.js client registers
and completes an internal SIP call — before any group wiring.
