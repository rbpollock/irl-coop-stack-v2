# Group app integrations (SSO wishlist)

Status: **notes / wishlist — recorded 2026-08-27; not designed, not built**

## Principle

A group's Webstudio site is a **presentation shell** that embeds group-aware
apps. Every app is an **OIDC client of the one Keycloak realm** (`irl-coop`), so
single-sign-on is free once the client is registered; the real work per app is
two-fold:

1. **Group-scoping the app's data** — Postgres RLS on `app.sub` (same injection
   coop-api/NocoDB use) so one member of group A never sees group B's rows.
2. **Embedding it** — iframe into the group site (the Plane/NocoDB pattern),
   scoped by the group slug from the `{group}.irl.coop` host.

This is the "apps" axis of a group shape (`docs/design/event-bus-and-group-shapes.md`):
which apps a group gets provisioned is seed data, not hard-coded.

## The set (7 categories)

| # | Category | What it covers | Status |
|---|---|---|---|
| 1 | Treasury / finance / tracking | group Safe balances, contributions, expenses, ledgers | money rails — spec level |
| 2 | Voting / governance / history / logs | proposals, weighted votes, tamper-evident history | governance — design only |
| 3 | Chat / Matrix / video-calls | per-room chat, presence, calls, SFU | Matrix built; video pending |
| 4 | Phone-banking / phone log | call-through, member directory, call metadata | telephony built (FreeSWITCH); log design only |
| 5 | Availability / calendar | booking, scheduling, group calendar | roadmap — not started |
| 6 | Marketplace / inventory / NocoDB embeds | listings, stock, arbitrary tabular data | NocoDB built |
| 7 | Blog / CMS / forms | posts, pages, structured data entry | Webstudio (CMS) built; Postiz (blog) built; Formbricks (forms) pending |

## Per-category notes

### 1. Treasury / finance / tracking
- Money rails (roadmap). A group's treasury = its **group Safe** (ERC-4337
  accounts) + a **private ledger** — see `private-treasury-guards-ledgers.md`
  (guards: cost public, payment private-but-provable; coverage proofs).
- Settlement / sponsorship rails are spec-level only (design doc written).
- SSO: the treasury surface reads the caller's group claim and scopes to the
  group Safe. No custody in the app — signing stays in member keys.

### 2. Voting / governance / history / logs
- Governance = shape axis 4. Vote **weight** comes from membership proofs, not
  a username: `zk-membership-graph-proofs.md` (membership/role/non-membership
  are off-the-shelf Merkle/Semaphore; bounded-distance K≤3 for
  conflict-of-interest is feasible; exact distance deferred).
- History / logs = an append-only, tamper-evident log fed by the event bus
  (`event-bus-and-group-shapes.md`): every `vote.cast` / `proposal.approved`
  lands on a group-scoped ledger so decisions are auditable after the fact.

### 3. Chat / Matrix / video-calls
- Matrix is **live** (`matrix-chat-and-notifications.md`): Element embedded
  per-room, coop-api as the appservice fanning metadata into the bus, member
  token minted server-side (see the `matrix-chat-gateway` skill).
- Video-calls: the SFU interest from `telephony-privacy.md` Phase 3 —
  internal calls P2P over Matrix, media on a **member-owned E2EE SFU**
  (LiveKit/mediasoup), not the switch.

### 4. Phone-banking / phone log
- Telephony is **live** (FreeSWITCH + FusionPBX, see `telephony-privacy.md` /
  `telephony-trunking.md`): one coop domain, groups = granular resources,
  SIP/WSS softphone (`webrtc-softphone` skill).
- Phone **log** = call metadata, which is the highest-privacy surface
  (surveillance-resistance applies to metadata, not just media) — design-only,
  see `telephony-privacy.md`.

### 5. Availability / calendar
- Booking / scheduling is on the roadmap, not started.
- The interesting question is group-aware availability: a member's calendar
  scoped so a group can see *when* someone is free without seeing *what* they
  are doing (free/busy vs full-title — a privacy dial, not a binary).

### 6. Marketplace / inventory / NocoDB embeds
- NocoDB is **live** (custom Gate-SSO image, `nocodb-custom-build` skill):
  auto-login via `x-forwarded-email` header, workspaces read API, SPA-shell
  fixes. Inventory / listings = NocoDB tables behind RLS.
- "Marketplace" here also means the **Webstudio template marketplace** itself —
  the cooperative-vertical templating work (this session's thrust).

### 7. Blog / CMS / forms
- **CMS** = Webstudio itself (the visual builder + NocoDB-as-data).
- **Blog** = Postiz (built; group-awareness design in
  `postiz-group-awareness.md`).
- **Forms** = Formbricks — pending: SSO is behind an **enterprise gate** and
  admin accounts aren't provisioned yet. Native `<input>`/`<textarea>`/`<select>`
  also hang the Webstudio fragment parser (styled-`<div>` placeholders today),
  so real form controls are a known gap across both surfaces.

## Open questions (to settle later)

- **Embedding contract** — iframe + `postMessage` (current Plane/NocoDB pattern)
  vs a shared component library. Iframe is cheap and isolates auth; the cost is
  no shared React state.
- **Per-group app enablement** — which apps a group gets is shape seed data, but
  the *provisioning order* (Temporal workflow, one activity per app) is designed
  in `event-bus-and-group-shapes.md`, not built.
- **The privacy dial** — several of these (calendar, phone log, treasury) want a
  per-field visibility control rather than app-level all-or-nothing. That dial
  is a cross-cutting concern, not per-app.
