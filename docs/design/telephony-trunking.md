# Telephony trunking + group caller-ID

Status: **design** (Telnyx trunk + per-group DIDs + cross-group caller-ID grants).
FreeSWITCH/FusionPBX are live (`:spike` images); the PSTN trunk is the missing
piece.

## Goal

One carrier relationship for the whole coop, with per-group identity on the
wire:

- **One Telnyx account** = the coop's single PSTN ingress/egress. FreeSWITCH
  multiplexes every member's extension onto that one trunk.
- **Per-group DIDs** are the default outbound caller-ID: calls from group A
  present A's number.
- **Consented cross-group caller-ID**: a "customer-service coop" can present
  *another* group's number when it places calls on that group's behalf.

## Division of labor

| Layer | Owner | Notes |
|---|---|---|
| PSTN ingress/egress, number inventory, STIR/SHAKEN | **Telnyx** (one account) | licensed carrier, A-level attestation |
| SIP signaling + media | **FreeSWITCH** (`mod_sofia`) | SIP 5060 / WS 5066 / WSS 7443, RTP 16384–32768 |
| Per-user/group routing, dial plan, permissions | **FreeSWITCH** dialplan (driven by coop-api lookups) | groups = granular resources |
| Per-member metering / billing split | **coop-api** → event bus | `ingestEvent(freeswitch)` → CDR → event |

FreeSWITCH registers to Telnyx via one **credential-based SIP connection**
(trunk). Telnyx sees one customer (the coop); every extension egresses through
it. Telnyx never needs to know about individual members.

## Current state (what's already built)

- `infra/instances/dev/apps/freeswitch.yaml` — `irlcoop/freeswitch:spike`, host
  networking, `mod_sofia` terminates SIP/WS/WSS/RTP directly; WSS serves the
  `*.irl.coop` wildcard cert (`wss://sip.irl.coop:7443`); event socket :8021.
- `infra/instances/dev/apps/fusionpbx.yaml` — ops/provisioning UI only
  (`pbx.irl.coop` → :8087), drives FreeSWITCH over the event socket, `fusionpbx`
  DB on shared Citus. **Members never touch this** — they get the dashboard
  "Calls" app over WSS.
- **Auth**: phones/extensions get **coop-issued SIP digest** credentials (not
  the FusionPBX UI). GUI is oauth2-proxy OIDC.
- **coturn** in the stack for WebRTC NAT traversal.
- **Event bus**: call events already flow `freeswitch → ingestEvent` → CDR.

## Caller-ID model

### 1. Per-group DIDs (default)

Each group owns a DID pool (its outbound caller-ID and inbound routing
identity). A call from group A presents A's number by default — no lookup
needed beyond the caller's own group.

### 2. Cross-group grants (the customer-service-coop case)

A group (the *granter*) consents to let another group (the *grantee*) present
its number. E.g. **CS Coop** is granted the right to present groups A/B/C's
numbers when it makes support calls on their behalf.

**Key insight — this is a policy check, not a spoofing problem.** All numbers
sit under the single coop Telnyx account, so presenting group B's number from
group A's extension is "the coop's account presenting a number the coop owns" →
STIR/SHAKEN **A-level attestation still holds**, zero carrier friction. The
only thing to enforce is *authorization*: is this extension permitted to
present that number?

## Schema

DID ownership reuses the existing resource-scoping pattern; the grant is a new,
directed, consented edge.

```sql
-- DID ownership: which group a number belongs to (reuses resource_scopes).
-- app='telephony', resource_key='did:<e164>', group_id=<owner>, scoped_by=<provisioner>
-- (or a dedicated group_dids(group_id, did, label) if resource_scopes proves awkward)

-- Cross-group caller-ID grant (new).
CREATE TABLE caller_id_grants (
  granter_group_id uuid NOT NULL REFERENCES groups(id), -- owns the number
  grantee_group_id uuid NOT NULL REFERENCES groups(id), -- may present it
  granted_by       uuid NOT NULL,                      -- granter's owner (consent)
  created_at       timestamptz NOT NULL DEFAULT now(),
  revoked_at       timestamptz,
  PRIMARY KEY (granter_group_id, grantee_group_id)
);
```

- **Consent is one-way and explicit**: B → A. CS Coop cannot unilaterally use
  B's number; B's owner creates the grant (and can revoke it by setting
  `revoked_at`).
- **Revocation is instant**: the next dialplan lookup fails → caller-ID falls
  back to the caller's own number. No carrier involvement.
- **Audit**: cross-group calls are already in the CDR/event bus; the grant just
  means `presented_number ∉ caller's own group`, the exact trail for "CS Coop
  called on behalf of group A."

## Dialplan enforcement point

At call setup (before the outbound leg), FreeSWITCH resolves the caller's
permitted caller-ID set:

```
permitted(extension) =
  DIDs owned by extension's group
  ∪ DIDs of groups where (grantee=extension's group AND not revoked)
```

- Requested caller-ID ∈ `permitted(extension)` → allow, present it.
- Else → reject the outbound leg (or fall back to the caller's own number).
- Lookup via `mod_xml_curl`/a coop-api endpoint at call time (same seam
  FusionPBX already uses for dynamic directory/dialplan), so the grant table is
  the single source of truth — no static dialplan hand-editing.

## UX — "call as" selector

The dashboard Calls app shows the caller their *permitted set* (own group +
any grants) as a "call as" dropdown. Selecting a grant presents that group's
number for that call. This is the same lookup rendered as UI.

## Incoming reliability (the Google Voice trick)

For a phone to ring reliably even when the app is closed, mirror Google Voice's
"linked number" fallback: the in-app/native softphone is the data path, and the
**member's real mobile number** is a PSTN-forward fallback over the trunk (a
few cents of trunk time per ring). This sidesteps the iOS CallKit/PushKit +
Android background-service push problem for inbound while the softphone matures.

## Softphone surfaces

1. **In-app (web)** — SIP.js over WSS → FreeSWITCH, WebRTC media via coturn,
   coop-issued SIP digest. Low effort; the "Calls" app. Limitation: only rings
   while the tab is open.
2. **Native (Play/App Store)** — React Native + linphone-sdk (or pjsip),
   SIP-TLS/WSS with the same digest. The heavy lift is background ringing:
   iOS CallKit + PushKit VoIP push (mandatory), Android FCM + foreground
   service. Ship after the web softphone + PSTN-forward fallback.

## Gotchas / checklist (Telnyx)

- **Business verification**: Telnyx wants a legal entity (the coop's EIN/reg)
  before full outbound is unlocked.
- **STIR/SHAKEN**: A-level attestation on US outbound (Telnyx is a licensed
  carrier) — the reason to use a real carrier, not a reseller.
- **Caller-ID = a number you own**: outbound caller-ID must be a number on the
  account. Per-group DIDs = one number per group (~$1/mo each); a single
  shared coop number is the zero-cost fallback.
- **Pay-as-you-go**: per-minute + per-number; there's no "unlimited coop plan."
  Fine — the coop already meters via CDR.

## Open items / sequencing

1. Wire the Telnyx trunk: account + business verification + one SIP connection;
   FreeSWITCH gateway + `group_dids`/resource-scope provisioning.
2. Add `caller_id_grants` + the coop-api lookup endpoint + dialplan enforcement.
3. In-app Calls softphone (SIP.js over WSS) + "call as" selector.
4. PSTN-forward "linked number" fallback for reliable inbound.
5. Native softphone (linphone + push) last.
