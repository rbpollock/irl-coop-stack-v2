# Delegation, Session Keys & Temporal Automation — Design Note

Status: design (discussion). Author: Robbie + Hermes, Aug 2026.
Builds on: [account-and-key-model.md](account-and-key-model.md), [group-scoping.md](group-scoping.md).
Supersedes in part: the digest delivery built in `apps/coop-api/src/temporal/` (platform
sender + BYPASSRLS collect) — that is the pre-delegation model and is marked for rework.

## 1. The problem

Users will automate web3 → fiat → payment tasks (and later hand work to agents).
Temporal is the execution engine for that — one of the main features of the stack,
not a side lane. But a "service worker holds an open gRPC connection and does
system-level work" model gives one invisible identity full reach. That is a bypass,
and bypasses are ruled out.

## 2. Settled invariant (do not relitigate)

1. **No bypass on Temporal.** Every Temporal call is authorized by a *user's*
   ERC-4337 session key. No service identity, no system role, no `BYPASSRLS`
   function, no cross-user reader.
2. **Secrets split into two non-overlapping domains:**
   - **User secrets** — the Safe-anchored Vault slice, unlockable only by that
     user's session key.
   - **Platform secrets** (`master.key`, webhook tokens, client secrets) — live
     only in coop-api's process env; Temporal can never read them, ever.
3. **The worker is dumb.** It must not source `secrets.env`. Identity and secrets
   arrive per execution, injected from the session-key unlock.

## 3. Delegation, not custody

A delegate is not a custodian as long as three properties hold — all ERC-7715-native:

1. The signer is a **permitted key, not an owner**. The Safe remains owner and
   sole source of truth.
2. The permission is **scoped** — bounded actions, caps, recipient allowlists,
   expiry. "Act as me within this exact box," not "act as me."
3. Revocation is **instant and on-chain**, controlled by the Safe, never the delegate.

Custody = the platform holds the asset's authority. Delegation = the platform
holds a scoped, revocable permit. The Safe never hands over ownership.

## 4. One primitive, three shapes

An ERC-7715 permission grant (Safe → signer) is the single primitive. It appears
three ways, differing only in **holder, scope, and expiry**:

| shape | holder | expiry | scope |
|---|---|---|---|
| interactive session key | user device | short | app-level |
| automation / delivery key | platform (custodial, encrypted) | long / renewable | narrow, per-workflow |
| agent key | agent runtime | bounded | narrow, stricter |

This is the backbone of the automation pillar: build the delegation machinery
once and get sessions, Temporal automation, and agents for free.

**Presence decides the mode.** The same scope (actions × resources × limits) is
held by whichever key shape fits the interaction:
- user present, direct dashboard engagement (Plane, Roundcube/Stalwart) →
  interactive session key — the live lane.
- user absent, or event-driven reaction / scheduled work → delivery key —
  Temporal's durable lane.

Temporal's job is **forward** (relay events), **trigger** (react to app/service
events), and **automate** (scheduled). The dashboard is the primary direct
surface. Scope *content* is holder-agnostic — holder + mode + expiry are
delegation-registry metadata, not part of the scope schema.

### 4.1 External channels — the group as a user with a phone

The scope vocabulary is app-agnostic. A group (Safe) holds a presence on
external apps — Postiz (social), WhatsApp, Telegram, Signal, automation tools —
and lends scoped access to that presence the same way it lends internal
resources. Mental model: **the Safe is a user with a phone; delegation is how
it hands out pieces of that phone.**

Two layers:
- **Phone layer** — a runner fleet (the existing browser-management/Playwright
  pillar) holds each channel's session and presents the group's identity to the
  app. External apps see only "a logged-in account," never the Safe.
- **Permission layer** — ERC-7715 grants authorize who may drive the phone
  (which channel, which action, up to what limit).

Consequence for the schema: `resources` gains external-account references
(`whatsapp:<num>`, `telegram:<channel>`, `signal:<num>`, `postiz:<account>`,
`email:<mailbox>`) beside the internal `resource_scopes`/`route`/`treasury`
ones; `actions` become channel-agnostic (`channel:send`, `channel:read`,
`channel:respond`). One four-dimension shape covers "deliver my digest," "pay
up to $X," and "post to our Telegram channel."

Security note: internal apps (Matrix, Stalwart) have a native Safe/OIDC identity
and RLS as a backstop. External apps have none — the runner's session IS the
account, so the delegation grant (scope + limits + revocation) is the ONLY
boundary there. External channels therefore make limits + revocation more
load-bearing, and `browser-management` itself must come under the delegation
model (driven by scoped keys, never a free-roaming service identity).

## 5. How the session key reaches Temporal (the bridge)

Temporal's authorizer validates a JWT against a JWKS — it cannot do on-chain
signature checks. So keep on-chain logic where it already lives (coop-api owns
Safe/anchor + RPC):

1. User's device holds a session key (ERC-7715 grant from their Safe).
2. To act, the user signs a challenge; coop-api validates the signature AND the
   on-chain grant (`isValidSignature` / the permission record).
3. coop-api mints a short-lived Temporal JWT: claims encode Safe → user mapping
   and the granted scope.
4. The JWT rides `authorization: *** gRPC metadata into Temporal; the authorizer
   validates against coop-api's JWKS and maps claims → namespace/ops.

Temporal stays a dumb JWT verifier. coop-api is the only thing that touches the
chain. Platform secrets never leave coop-api; user secrets are released through
the Vault only when the session key proves ownership.

## 6. The provision-time delivery key (resolves scheduled vs ephemeral)

Scheduled (cron-like) delivery needs a standing authorization, but interactive
session keys are ephemeral by design. Resolution: **account provisioning creates
a dedicated, longer-lived delivery key.**

- Created at provisioning — the one moment the user is present to *sign* the
  grant (after `ensurePersonalSafe`, alongside the personal group).
- Narrow scope: read own events/notification state (RLS-bound), deliver own
  digest — never another account's data, never a platform secret, never a
  Safe-control op (no spending, no ownership change).
- **Custodial**: coop-api holds the private material, encrypted, per-user, in the
  user's Vault slice. Semantically a *user* secret, not a platform secret — so
  the boundary in §2 holds.
- **Safe-revocable + renewable**: revocation is the on-chain kill switch;
  re-provisioning issues a fresh key. "Long-lived" ≠ "permanent."

This is delegation, not custody, in the §3 sense: coop-api holds a scoped permit,
the Safe holds the power to tear it up.

## 7. Groups delegate via roles (roles are bundles, not labels)

Because every account is a group Safe, individual delegation is the group-of-one
special case — roles generalize it.

- A **role is a named bundle of scoped ERC-7715 grants**, not a string like
  "admin." Assigning a role = the group Safe signs the grants to the member's key
  (or an agent/Temporal key). Removing a role = revoking the bundle.
- No shared keys, no inheritance — permissions are *composed* from roles held
  (composition-not-inheritance, made literal).
- **Two levels, unlike individual delegation:** who may assign/revoke roles is
  itself a governance decision (threshold, voting). Governance decides → Safe
  signs → member/agent holds the grant.
- `resource_scopes` (group_id → app → resource_key) is the proto-registry; roles
  formalize it (role → apps, resources, limits, expiry). The table is the index,
  the Safe is the source of truth, the grant is the enforcement.

### The 5-axis group shape

roles / apps / config / governance / ZK-proofs — **roles are the delegation
layer** of that shape. The other axes fill in: `apps` = which surfaces a role
reaches; `config` = the limits; `governance` = who may assign/revoke;
`ZK-proofs` = anonymous presentation of a role.

### ZK presentation

"Prove I hold role X" without revealing *which member* — a ZK proof against the
role registry, verified by the group Safe. Same grant layer, zero-knowledge
presentation instead of a bare key. Feeds the regenerative-score metric (act/be
scored under role authority while staying anonymous to other parties).

## 8. Delegation registry (the anchor)

One registry enumerates every delegate — session, automation, agent — with scope
and expiry; one place to revoke. On-chain ERC-7715 grants are the truth; an
off-chain index makes it queryable by Temporal, the agent runtime, and the app.
The Safe is the revocation authority for everything. This is what keeps "no
bypass" true even as Temporal and agents multiply: every actor is a *named
delegate with a visible, revocable scope*, never an invisible system identity.

## 9. Open decisions (in order)

1. **Custody shape — DECIDED (Aug 2026).** Device-side generation, bundled into
   the provisioning step (same flow as passkey registration; ~100ms WebCrypto
   keygen, no new screen). The delivery key is a disposable, scoped, revocable
   permit — not an owner key — so recovery = revoke + re-issue (no backup
   share). Provisioning becomes a **delegation manifest**: generate + register
   the account's full key set (delivery key now; agent keys opt-in later), each
   with a Safe-signed grant, in one atomic flow. Extensible after — seed, not
   cage. coop-api holds a custodial share per key (scheduled use requires it);
   the grant's scope + revocation is the boundary, not key secrecy.
2. **Scope schema** — the ERC-7715 `permissionData` shape. Start with one coarse
   "delivery" permission, or granular (read-notifications, send-digest, per-app)?
   Must also express payment-type limits: allowed routes, per-run caps, recipient
   allowlists, token constraints.
3. **Agent threat model** — same primitive, stricter defaults: narrower scopes,
   lower caps, and a human-in-the-loop tier above a value threshold.

## 9.5 Coordination family — routing, escalation, and the unifying pattern

A third action family sits beside financial and data: **coordination**. Worked
case: irl.coop's sub-groups (verticals — Land Back, Solidarity Economies,
Ecological Repair, Community Safety, Healing Justice, Cultural Power, Relational
Infrastructure) each post to the main irl.coop socials; inbound comments/chats
become events; a **response router** dispatches each to an outcome that sits on
an automation→human spectrum:

| outcome | human-in-the-loop |
|---|---|
| send material | none (automated) |
| lead to form/website | low |
| notify a rep to reach out | handoff (1:1) |
| popup FCFS volunteer queue | coordination (1:many) |

- **New resource types**: `person:<sub>` (handoff target) and
  `queue:<vertical>:volunteers` (FCFS coordination) — the first *human*
  primitives. The stack stops moving only data/money and starts coordinating
  people (facilitation, repair, running rooms).
- **New event source**: `social` (Postiz et al.) beside matrix and mail; the
  router is a Temporal consumer of `social.comment` events. Hotline/helpdesk is
  the same router with a different inbound source.

**Router rules are set by governance, and may mix all three tiers.** The three
tiers — deterministic rules, agent judgment, human moderator — are ONE
escalation ladder, and governance sets each boundary. The router's grant encodes
the ladder: act deterministically within the rules, use judgment only inside the
granted band, *must* escalate to human above it. This resolves §9.3: human-in-
the-loop is a per-scope escalation boundary set at grant time, not a global flag.

**The unifying pattern** (every scenario reduces to it): governance decides →
a delegate executes → the grant is the bridge (its content IS the decision) →
the Safe revokes. The 10/20/70 transfer and the routing policy are the same
artifact; only the box's content differs.

Schema note: `limits` generalizes to **constraints** — numeric caps/allowlists
for money, an escalation-ladder policy for coordination. Same slot, different
content; the shape stays five fields.

## 10. What already exists (don't rebuild)

- Safe deploy + modules: `apps/coop-api/src/safe.ts`; modules listed in
  account-and-key-model.md §"What already exists" (SessionKeyModule deployed).
- `resource_scopes`, `group_members.roles`: group-scoping.md §2 (projection only).
- Vault: Safe-anchored secret store in coop-api (the "group secret" vault,
  account-and-key-model.md §2 layer-2).
- Temporal worker + delivery/digest workflows: `apps/coop-api/src/temporal/` —
  to be re-architected under §2 (no BYPASSRLS, per-user, no platform sender).
