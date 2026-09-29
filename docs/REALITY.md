# REALITY.md — what actually works

Status: checkpoint inventory · 2026-09-29.
Method: direct evidence from the repository, configuration, and the live host.
This document deliberately separates *evidence found* from *reasonable inference*;
inference appears only in the "Risks / gaps" column and is marked as such.

## Labels used

**Current state** — one of: Not found · Concept / design · Scaffolded ·
Partially implemented · Implemented but not demonstrated · Demonstrated in
development · Demonstrated in a real group workflow · Not verified.

**Suitable for real group use?** — one of: No · Limited, supervised pilot only ·
Unknown / not verified · Yes, with stated boundaries.

"Demonstrated" requires an identified test, deployment record, or reproducible
procedure — never a code path that merely looks plausible. **The last two state
labels are unused in this table: no subsystem has yet been demonstrated in a real
group workflow.**

| Domain | Evidence / location | Current state | End-to-end demonstration | Suitable for real group use? | Principal risks / gaps | Smallest next proof |
|---|---|---|---|---|---|---|
| Repository & deployment reproducibility | `infra/instances/dev/`; `infra/build/generator.py`; `infra/scripts/stack-up.sh`; `irl-coop-stack.service` | Partially implemented | Bring-up runs at boot (systemd, enabled); not re-verified from a clean host | **No** | Dashboard and coop-api run as host `npm run dev` processes, not containers; the generator deletes `infra/out/` on every run; secrets live in host `.env` files outside the vault | Bring the stack up from the repo alone on a clean machine and reach the sign-in page |
| Identity & sign-in | Keycloak realm `irl-coop`; `apps/coop-api/src/auth.ts`; OIDC clients web-app/coop-api/plane/nocodb-gate | Demonstrated in development | Canonical issuer verified through the edge; Plane zero-click SSO verified E2E | Limited, supervised pilot only | IdP secrets cannot round-trip a realm export (the admin API masks them); coop-api service-account roles are not declared in the tree and are silently dropped by an import | Fresh-browser login reaching every app without re-auth |
| Invite & onboarding | `apps/coop-api/src/onboarding.ts`; `docs/design/onboarding-flow.md`; `POST /api/v1/groups/:id/members` | Partially implemented | Not demonstrated | Unknown / not verified | No end-to-end run of a real person being invited, joining, and landing in a group | Invite one outsider by email; they complete signup and appear in the group |
| Group / workspace lifecycle | `apps/coop-api/src/groups.ts`; `groups`/`group_members`/`resource_scopes` in `src/db.ts`; `coop_ensure_personal_group()` in `infra/compose/storage/scripts/coop_rls.sql` | Demonstrated in development | `infra/scripts/journeys/journeys/groups-scope.mjs` | Limited, supervised pilot only | No archive/delete path; group-of-groups is now representable — D-16 (a seat's holder is a Safe) is implemented and verified in a scratch DB, though not yet applied to the live database (see D-01, D-16) | One real group created, operated, and archived |
| Role & permission model | `grants`/`roles`/`role_grants` tables; `coop_has_grant()` (`coop_rls.sql:497`); `use-has-grant.ts` | Implemented but not demonstrated | Per-app role mapping verified ad hoc (postiz, NocoDB, Keycloak mapper) | Limited, supervised pilot only | Cross-app role mapping is bespoke per app; nothing shows a member's effective access in one place | A role change in one group visibly changes access in two or more apps |
| Cross-service / global access control | Postgres FORCE RLS + `coop_is_member`/`coop_is_owner`/`coop_can_view_group`; oauth2-proxy gates with unique cookie names; `internal.ts` groups mapper; `provision-member-certs.sh` | Demonstrated in development | `infra/scripts/verify-coop-rls.mjs`; journeys | Limited, supervised pilot only | Three parallel identity paths (RLS `app.sub`, DB cert role, OIDC claim); the NocoDB visibility fallback can over-expose (mitigated by `enforce-nocodb-visibility.sh`) | Re-run the RLS-contrast test against a freshly created group |
| Documents & file storage | `src/files.ts`; `src/docs.ts`; `src/ooxml-templates.ts`; MinIO buckets; OnlyOffice | Demonstrated in development | Files panel Phase 1 verified 15/15 (2026-08-12) | Limited, supervised pilot only | Share links are relay tokens; if derived `MINIO_*`/`DOCS_SIG`/`FILES_SIG` vars are missing from coop-api `.env`, S3 operations fail silently with wrong credentials | Share a document with an outsider and revoke the access |
| Task / project coordination | Plane CE (`infra/instances/dev/apps/plane.yaml`); `/api/plane/projects`; dashboard embed | Demonstrated in development | Zero-click SSO verified E2E; Plane canonicalization complete | Limited, supervised pilot only | Plane is a third-party app with its own tenancy; group↔project binding is via `resource_scopes` | One real group runs one project to completion |
| Public web pages / CMS | `apps/webstudio.yaml` (`enabled: false`); `apps/wordpress.yaml`; group subdomain `{slug}.irl.coop` | Scaffolded | Not demonstrated | **No** | Webstudio is declared-but-not-wired; group page publishing is unverified | Publish one group page and load it logged-out |
| CRM / relationship management | ERPNext (live app) + `docs/design/erpnext-tenancy-notifications.md`; Twenty parked | Partially implemented | Not demonstrated | Unknown / not verified | Two CRMs are contemplated (ERPNext native vs Twenty) — an unresolved decision | A contact/relationship record scoped to, and visible only within, one group |
| Email / communications | Stalwart v0.16 (:8083 admin; 25/587/143/993); Roundcube; Matrix/Element/Cinny (federation off) | Demonstrated in development | All four mail ports answered externally; the mailbox self-provisions on first auth | Limited, supervised pilot only | DMARC is still `p=none`; a broker-email leak into fleet JWTs previously broke IMAP auth (fixed; self-heals on next authorize) | Send and receive from a group address with an outsider |
| Governance / proposals / voting | `src/decisions.ts` (proposals, quorum, deadline, EIP-1271 vote capture); `proposals`/`votes` tables; `docs/design/irl-coop-group.md` §6 | Implemented but not demonstrated (off-chain); **Concept / design** (on-chain) | Not demonstrated | Limited, supervised pilot only | On-chain tallying is mocked; the off-chain layer must never carry a legally consequential decision | One real group passes one binding-in-spirit proposal off-chain |
| Accounting | ERPNext (`apps/erpnext.yaml`) | Partially implemented | Not demonstrated | **No** | No verified per-group chart of accounts; tax/statutory treatment flagged unresolved | One group's income and expense recorded and reported |
| Treasury / payments / banking | `src/payments.ts` (policy + contract); `src/dues.ts`; `payment_intent`/`rail_event`/`dues_policy`/`dues_waiver` tables; `apps/peer_xyz_payments` (Peer.xyz / zkp2p rail, `:3010`); `contracts/contracts/CoopUsdcRouter.sol` + `contracts/test/CoopUsdcRouter.ts` + `contracts/scripts/deploy_usdc_router.ts`; `apps/coop-api.yaml` pins `PAYMENTS_DESTINATION` and `PAYMENTS_CHAIN_ID: 8453` | **Attempted, never completed** | **4 `payment_intent` rows and 23 `rail_event` rows exist (last 2026-09-16) — all 4 intents have status `failed`**; no transfer has ever completed; no deployed router is recorded anywhere, and whether the provider account is funded is unknown | **No** | Real money; **who holds the keys to the pinned destination address is not recorded**; no funded rail account is known; Base is pinned in configuration and hard-gated by the API while `money-in-and-out.md` still lists the chain decision as open; ticketing payment keys are unset; no backup exists anywhere (R-07) | A small real amount arriving at the pinned destination on Base and sweeping to a coop-controlled address, under explicit written risk bounds |
| Integrations & automation | Temporal worker (outbox, digests, postizSync, tier2); `src/temporal/*`; `src/provisioning.ts`; `events` table + `coop_sweep_undelivered`; Redis `irl:notify:{sub}` | Demonstrated in development | Outbox + digest sweep runs | Limited, supervised pilot only | Temporal is "not in final form"; the delivery lane is type-agnostic (SMS is deliberately not emitted) | One event flows source → bus → notification to a real member |
| Telephony | `telephony_resources`/`group_telephony`/`telephony_templates`/`phone_message` tables; `src/telephony.ts`; `src/sms.ts`; FreeSWITCH + FusionPBX | Partially implemented | Not demonstrated | **No** | No gateway deployed and no DID held — nothing can arrive except from a token-holder; a mis-attributed message could taint a DID | One SMS arrives at a coop-controlled number and reaches the owning group |
| Maps / location data | `apps/maps.yaml`; `tracks`/`markers`/`waypoints` tables; `infra/scripts/build-pmtiles.sh`; `docs/design/sovereign-maps-tracks.md` | Demonstrated in development | Basemap built and served | Limited, supervised pilot only | The ~10 GB basemap is not cheaply rebuildable and lives only on this host (it was once destroyed by the generator) | A group records a track and reads it back |
| AI agents | `src/mcp.ts` (grant-filtered, RLS-scoped, read-only); client-side local inference; `docs/design/local-ai-chat.md` | Implemented but not demonstrated | Not demonstrated | **No** | Write-capable agents are the high-risk class; today's tools are read-only, which is correct | A member's local model calls a read-only tool and sees only their own group's data |
| MCP servers | `src/mcp.ts` (streamable-HTTP JSON-RPC); upstream proxying to the RAG knowledgebase; `rag*` apps | Implemented but not demonstrated | Not demonstrated | **No** | Upstream MCP server trust is unexamined; the tool-grant model is unproven | An MCP client authenticates and lists only its permitted tools |
| Observability, logging, backups, restoration | `infra/scripts/stack-report.py`; `GET /api/v1/stack/status` (`src/status.ts`); systemd unit + motd; `/var/lib/irl-coop/stack-status.json` | Observability: Demonstrated in development · **Backups: Not found** · **Restoration: Not verified** | Declared-vs-running report runs at login and on the dashboard | **No** | No Citus or MinIO backup exists anywhere in the repo or host; the only backup artifact is a git bundle on the same disk; single host | Restore a database dump into a scratch DB and read a group back out |
| Security engineering & secret management | Derived keys (`infra/instances/dev/secrets/master.key` → HKDF → `${SECRET:name}`, `infra/build/secrets.py`); ansible vault for external secrets; gitignored `.env*`/certs; FORCE RLS; per-member certs | Implemented but not demonstrated | No rotation drill; no external review | **No** | One `master.key` plus one vault-pass is a single point of total compromise; bus factor 1; Keycloak IdP secrets cannot round-trip an export | A full bring-up on a clean host using only the secrets material |

## Contradictions found between documentation and code

1. **`ConfidentialVoting.sol` is referenced but does not exist.**
   `zk-membership-graph-proofs.md:57` cites it as an existing primitive;
   `contracts/contracts/` holds 11 contracts and no `ConfidentialVoting.sol`.
2. **`CoopRegistry.sol` is a stub, not a registry.** It stores a Merkle root and a
   revocation map; `_appendMember` is an empty `// Placeholder`. None of the four
   relationship edge types exist on-chain.
3. **`STATUS.md` is stale and disagrees with `instance.yaml`.** STATUS (last updated
   2026-08-13) claims "declared apps (21)"; `instance.yaml` lists 38. STATUS never
   gained litefarm, maps, erpnext, wordpress, peer_xyz_payments, the Matrix stack, or RAG.
4. **`AGENTS.md` carries a stale tailnet address** (`100.122.136.95`); the host's
   live tailnet address differs.
5. **"Nested groups exist in code" is not supported by the code or the database.**
   The model is seats, not columns ("relationships are edges, not columns"); the
   *edge* registry that would make nesting real is unbuilt.
6. **Money is further along in code than its own document claims — the opposite
   direction from every other contradiction here.** `money-in-and-out.md` §0
   (2026-09-13) states money has "essentially zero implementation" and that the chain
   decision is the open blocker. But `apps/coop-api.yaml` already pins
   `PAYMENTS_CHAIN_ID: 8453` (Base) and `PAYMENTS_DESTINATION`; `src/payments.ts`
   hard-gates on Base; `CoopUsdcRouter.sol` is a complete non-custodial forwarder with
   tests and a deploy script; and a Peer.xyz rail service is wired at `:3010`. The
   document understates the code — while the code still has no demonstration behind it.
   **A returning maintainer should trust neither the doc nor the config alone: the code
   exists, the evidence does not.**

## Stale, abandoned, or duplicate

- `surfy` — the retired v1 edge host; still on the LAN, its tailnet route is down.
- `lab-mgcp/` — lab telephony artifacts, including root-owned build output left
  tracked by accident (now untracked and gitignored).
- `src/vault.ts` and `src/livestream-state.ts` at the repository root appear to
  duplicate the versions under `apps/coop-api/src/` — unverified.
- `apps/coop-api/sweep-ctl.ts` is untracked source; `pnpm-lock.yaml` is untracked at
  the repository root.

## Assumptions requiring confirmation

1. **This host is the only deployment**, and this repository is the only copy of the
   code. (Owner-stated, not independently verified.)
2. **No collaborators, legal entity, fiscal sponsor, or custodian exist** — taken
   from the owner's answers.
3. No test suite was run for this document; no service was started or restarted; no
   secret file was opened.
4. The "~2 years" hibernation duration is the owner's stated intention, not a
   decision recorded anywhere in the repository.
5. Real-money pilot scope is the owner's stated preference; the repository does not
   support it yet (chain decision, payment rail, treasury contract).