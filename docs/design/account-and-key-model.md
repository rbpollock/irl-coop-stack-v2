# Account & Key Model — Design Note

Status: discussion (pending decisions). Author: Robbie + Hermes, Aug 2026.
Supersedes: nothing yet — this is the working record for the Safe-as-everything account model.

## The model in one paragraph

Every account on irl.coop is a Safe smart contract. An individual is a 1-of-1 Safe
(one passkey owner). A group is the same contract with N-of-M owners. The infra DAO
(irl.coop group) is a Safe that owns/operates the backend. There is no second account
type — groups compose because a Safe can be an owner of another Safe. The Safe's
owner-set + threshold is the enforcement layer: no single operator, server, or hostile
backend can act alone because the math (threshold) forbids it and the holders are
separated by structure.

## Settled principles (do not relitigate)

1. **Sovereignty**: pure mathematical cryptography (threshold/Shamir, later ZK/FHE).
   No TEEs, no hardware backdoors. Lit Protocol ruled out.
2. **Safe as the universal account** — user = 1-of-1 group; groups = N-of-M; DAO = Safe.
3. **Recovery never depends on the backend.** The user + their own recovery material
   must always suffice. The backend/DAO may assist, never block, never steal.
4. **User simplicity first** (Robbie's directive): members must never see keys,
   thresholds, or the word "Safe" if we can avoid it. Passkey-first UX; recovery
   feels like a normal web reset; group membership is invisible ownership math.
5. **Uncorrelation**: no identity→onchain mapping is ever stored server-side
   (built Aug 2026 in `apps/coop-api/src/safe.ts` — CREATE2-deterministic addresses
   from a user-held saltNonce; see coop-api README "Uncorrelatable Safe provisioning").

## The two layers

- **Layer 1 — the account (Safe)**: owners + threshold. All policy and authority
  lives here. Modules (SovereignEvolutionModule, SessionKeyModule, PasskeyValidator —
  deployed on the local node) encode member-set policy; there is no human override path.
- **Layer 2 — the keys**: how each owner key is held. Server-held keys are
  Shamir-split / threshold-encrypted (the "group secret" vault: ciphertext may sit
  anywhere, decryption requires a quorum of member-held shares). No key in .env.

## Failure modes (Robbie's ranking)

| Mode | Mitigations |
|---|---|
| Lockout | Recovery path independent of backend; 2-of-3 user Safes (passkey + recovery + DAO-assist); printed/offline shares at DAO level; timelocks before owner changes |
| Theft | Threshold quorum (no single key/server); policy modules (limits, allowlists, rate caps); session keys for routine ops (small blast radius); on-chain audit trail; timelock intervention window |
| Regulatory | Non-custodial shape: coop provably cannot unilaterally move member funds (quorum across independent parties + audit) → less custodial surface. Tradeoff: freeze orders need quorum + recorded legal authority (compliance module) — deliberate with the DAO's legal form |

## Enforcement levers (what "enforce" means)

1. Math — t-of-n threshold: single-party action is impossible (hard bound)
2. Structure — shares held by adversarially-separated parties (different pillars,
   different admins, member devices, offline copies)
3. Transparency — every Safe action is an on-chain event; collusion leaves a trail
4. Time — timelocks create an intervention/reversal window
5. Code — policy modules with no override path

Honest limit: t parties who all collude cannot be stopped by math alone — choose t
and the holders so the collusion set is structurally implausible. A hostile backend
can censor (liveness), never steal; censoring is visible and survivable via
alternate submission paths.

## How the backend signs (as its own Safe)

The backend holds no authority; it relays and sponsors gas. When the DAO Safe must
act (e.g. approve a user Safe tx as 2-of-3 co-owner): its operator keys (Layer-2
held) sign the tx hash → the user Safe calls `DAO_Safe.isValidSignature(hash, sig)`
(EIP-1271) → DAO Safe verifies against ITS owner set/threshold → magic value →
user Safe counts it. Policy (which operators, what rules) is enforced at that
verification point by the DAO Safe's modules.

## Open knobs (decide in this order)

1. **User Safe ownership**: default proposal — 2-of-3: passkey + user recovery
   (second passkey or printed recovery key) + DAO Safe as assist-only owner.
   Simplest-for-user alternative: passkey + DAO-assisted recovery (recovery looks
   like a normal web reset, gated by DAO quorum + timelock).
2. **DAO Safe quorum**: default proposal — 3-of-5: [2 operator keys, separate
   pillars], [1 member-elected validator key], [1 member-held key], [1 timelock +
   circuit-breaker module].
3. **Key custody**: server-held keys Shamir-split across machines + offline; env
   secrets into a threshold-encrypted vault only the DAO quorum can open. Backend
   deploy key moves out of `.env` (`SAFE_BACKEND_SIGNER_KEY`) as part of this.

## Boundary conditions (the edges — Aug 2026)

Thresholds handle the happy path; the trust model is defined by the edges. Every Safe
(person or group) gets pre-committed answers at formation, never in crisis.

| Scenario | Failure | Design response | Primitive |
|---|---|---|---|
| Group inactive / abandoned | quorum decay → permanent freeze (funds + infra) | Time escalation, NOT decay (decay is an attacker's waiting game): dead-man's-switch (no auth in T → countdown → successor set), time-locked recovery (own quorum + public notice + timelock), owner replenishment via the active quorum | DeadManSwitch module, TimelockGuard |
| Individual dies | 1-of-1 passkey Safe unrecoverable; family locked out; coop must NOT recover unilaterally (custodianship) | Beneficiary/legacy owner set at onboarding ("who can recover this if something happens to you?" — one question, invisible after); opt-in time-based inheritance (long inactivity → named beneficiary after notice period); legal bridge: release requires documentation (death cert) + DAO quorum + recorded order | Succession registration, compliance gate |
| Group splits — amicable | none (it's just governance) | Partition proposal: quorum votes allocation to child Safes (each its own owners/threshold), Safe-to-Safe transfer | Partition/batch module |
| Group splits — confrontational | majority traps minority | Ragequit: any member withdraws proportional share anytime, no quorum (exit queue + delay, pro-rata, no flash-exit — Moloch pattern); arbitration: arbiter named at formation (third-party Safe or coop DAO), timelock + appeal window; formation constitution: exit rights, valuation method, arbitration path, succession — all shipped as defaults | Ragequit module, ArbitrationModule, GroupFactory (constitution pre-wired at creation) |

Principles:
1. Pre-commitment — succession/exit/arbitration rules are set at formation; you cannot bolt partition rights on after a conflict starts (the quorum won't agree). Defaults matter more than features.
2. Every Safe has a will — named successor / beneficiary / partition rights, person or group, no exceptions.
3. Time is the resolution primitive — timelocks, notice periods, inactivity escalation; anything not decidable instantly becomes a time-gated process.
4. Liveness vs. security resolved by escalation, not decay — keep quorums strong, add gated recovery paths that activate slowly.
5. Arbitration is layered and opt-in — individual → group → coop DAO → external law; each layer's powers defined at formation, each with timelocks and appeals. Sovereignty means the final arbiter can be external law, bridged to on-chain execution.
6. The DAO is the continuity layer — successor, arbiter, compliance gate, systemic memory. This is why the backend-as-DAO is the right shape.

## Architecture fit

Module layer (on-chain, `contracts/` — extends the deployed set: SovereignEvolutionModule,
SessionKeyModule, PasskeyValidator):
- TimelockGuard — foundational; time-gates owner/param changes everywhere
- DeadManSwitch / Succession — inactivity escalation + named successors
- Ragequit / Partition — unilateral proportional exit; amicable partition proposals
- ArbitrationModule — named arbiter, timelock, appeal window, forced-partition rulings
- Compliance gate — legal-documentation check (DAO quorum + recorded order → release)
- GroupFactory — deploys group Safes with the default constitution pre-wired (modules
  attached at creation); the formation-defaults decision gates this design

Service layer (coop-api, `apps/`):
- Group provisioning: `/api/group/*` — create (with constitution), join/leave
  (add/removeOwner via quorum), partition proposals, succession registration
- Onboarding extension: the one succession question after user Safe deploy
- Arbitration orchestration: notice windows, appeal scheduling — the service
  schedules, the chain enforces
- Threshold-encrypted vault: group secrets (salt backups, env secrets) — key custody

Pillar placement (sovereign-infrastructure): identity-data pillar → vault + succession
registry; workflow-ops pillar → arbitration scheduler + group API. On-chain modules are
chain-agnostic. Ansible/Traefik per existing patterns.

Sequencing: boundary conditions are v2 — they ship WITH group accounts. The one
decision that gates group design today is formation defaults (constitution baked in vs
negotiated). User Safe deploy + passkey wiring stay the v1 path; the succession question
is asked in onboarding from day one so the data model is never retrofitted.

## Service provisioning (core services — decisions Aug 2026)

Locked decisions (Robbie):
- **JIT-first + lazy materialization** — onboarding grants entitlements; accounts materialize on first use. Nothing eager except identity, consent, and Safe deploy. Onboarding never fails on a downstream service being down.
- **All services for all members** — flat entitlements; group membership inherits the group's set.
- **Zero-credential bias** — core services authenticate via OIDC only; user-facing per-service credentials = 0. IMAP/SMTP via XOAUTH2; MinIO STS tokens on demand; DB via coop-api query proxy (JWT) or PG OIDC; Jitsi = JWT room tokens. App passwords exist ONLY as self-service, revocable fallbacks for legacy mail clients — never stored server-side.
- **Email addressing** — people `<username>@irl.coop`; groups `<alias>@groupname.irl.coop`. Each group is a Stalwart domain AND a subdomain (doubles as the group's Traefik namespace). Wildcard DNS + wildcard MX. Group slug chosen at group creation (same moment as the group Safe deploy) — one name drives Safe, subdomain, and mail domain.
- **Registry-backed catalog** — adding a core service = one registry entry (name, OIDC client, JIT|materialized, pillar, provisioning endpoint), not an onboarding rebuild.

Flow: identity (exists) → consent/terms (hash on-chain) → Safe deploy (pending salt/backup UX) → entitlements (Keycloak groups/roles) → lazy materialization on first service use → dashboard "your services" one-click OIDC.

Engine (coop-api — its designated integration-boundary role): `/api/provisioning/status`, `/api/provisioning/enable`, `/api/provisioning/email` (mailbox + app-password fallback); username/slug registry (global uniqueness); idempotent, retryable, audited (DAO-visible).

Per-service matrix:

| Service | Auth | Stored creds |
|---|---|---|
| Matrix/Dendrite | OIDC JIT | 0 |
| Jitsi | JWT room tokens | 0 |
| File storage (MinIO) | OIDC + STS | 0 |
| Email (Stalwart) | OIDC web; XOAUTH2 IMAP/SMTP | 0 |
| Citus/Postgres | coop-api query proxy / PG OIDC | 0 |

Open details: group slug rules/collisions; direct DB access vs proxy (proxy preferred for zero creds + audit); vault role for service-to-service secrets (not user-facing).

## Group relationships & reserved powers (framework + mechanism — Aug 2026)

Every actor is a Safe; relationships between Safes are typed edges over four orthogonal dimensions:
- **Governance** (owner seats · threshold) · **Infrastructure** (namespace · mailboxes · quotas) · **Trust** (OIDC · SMTP · Matrix · arbitration) · **Economics** (funding · sponsorship)

Rule: **ownership implies membership ONLY** — a Safe in another's owner-set is a seat in its decisions, nothing more. Every other meaning is DECLARED in the on-chain relationship record (registry), never inferred.

Relationship types (dimension combinations): **member-of** (governance only — the default) · **subgroup-of** (governance + infra: autonomous Safe sharing the parent's namespace; terms define what's shared and what the parent may do) · **federated-with** (trust: peer interop, no control) · **sponsored-by** (economics: one-way flow, recognition, no control). Membership is a set, not a tree — a Safe holds seats in N groups; thresholds define how seats combine.

### Reserved powers — mechanism (Board/ED Safe co-owns department Safes)

Safe ownership is binary, so reserved powers are NOT a special owner role. Four pieces:

1. **Co-owner seat** — the Board Safe sits in the department Safe's owner set; full-threshold txs require its EIP-1271 signature, which itself requires the Board Safe's internal quorum (3-of-5 directors) — double-gated; one director can never act alone.
2. **Allowance / session-key module** — staff get short-lived session keys with per-key limits; routine txs execute without the board seat; the board is in the loop only for what the constitution says matters.
3. **Guard module (the enforcement)** — a TransactionGuard runs before every tx and blocks what the constitution forbids: above-limit txs without a board signature, owner-set/threshold changes without the board (including removal of the board's own seat), module installs/removals without the board, relationship-record changes without the board. Enforcement is local and self-binding: the child's own guard guarantees the parent's reserved rights; the child cannot opt out (removing the guard requires the board).
4. **Timelock guard** — sensitive changes pend for a notice period so compromise can be raced and cancelled (circuit-breaker: one director can trigger a temporary freeze; unfreeze = full quorum + timelock).

Reserved powers = one co-owner seat + allowances for routine flow + a guard encoding the declared terms + timelocks for reversibility — all sourced from the relationship record (auditable data, not hidden backdoors). Pre-commitment applies: the constitution is fixed at formation and changes only through the guarded path.

## Worked example — farm coalition ("one big world", Aug 2026)

A farmer (Maria) belongs to overlapping Safes and moves between them without "switching hats": **context is a property of the action** — the object she touches determines the governing Safe, and the confirmation line IS the context ("as member of Cold Storage Co-op — 2-of-3, 1 signature from you").

- **Her Safes**: Farm Safe (1-of-1 + family) · Cold Storage Co-op Safe (2-of-3; capital in, capacity quotas out) · Tractor-Share Safe (time-shares)
- **Declared edges**: labor-swap ledger (relationship-scoped mutual credit — 4h = 4 credits) · planting-data agreement (data stays at the farm; provenance hashes on-chain) · distributor contract (federated-with; their trucks stay theirs) · restaurant bulk orders (joint procurement — one order, contributions split per terms)
- **Regional Working Group Safe**: umbrella; member farms hold seats; owns its external surfaces as ASSETS — Postiz (social), shared mailbox (orders@working-group…), automated ordering & payments, website
- **Staff from member subgroups** hold role-scoped access to those surfaces via guard + session-key modules (the reserved-powers mechanism) — access, never ownership
- **UI consequences**: one unified approval inbox across all of the user's Safes; permissions derived from seats; the object graph is complete (every resource bound to a Safe) so context resolution never fails
- **New primitives exercised**: relationship-scoped ledgers · data-sharing agreements · asset-share records · joint-venture Safes (all extensions of the four dimensions, nothing new conceptually)

## zk-badges & participation gating (Aug 2026)

A zk-badge is a zero-knowledge proof over the participation records a user already generates (relationship-scoped ledgers, provenance hashes, Safe activity). It proves a predicate about that history WITHOUT revealing it: "≥10 quests completed" (not which) · "time-bank balance ≥ 40" (not the value) · "verified cold-storage fills this season" (not the farm) · "member of a coalition ≥ 1 year" (not which one).

- **Substrate**: ledgers + provenance records are hash-anchored on-chain; the proof binds to those commitments — tamper with the record, the badge is invalid. Badges cannot be faked (anti-sybil).
- **Prover**: client-side / at the user's site; records never leave home (the sovereignty pattern).
- **Issuance**: zk-badge module; badge = (predicate, proof, public inputs), holder-bound + time-limited (decay). Badges are relationship-record outputs → disputes are arbitrable.
- **Verification**: app layer (coop-api verifies, issues a scoped capability) for everyday gates; on-chain (Groth16/STARK verifier inside a guard module) for high-value gates.
- **Gates**: quest-board trust floor (≥3 completed quests to post) · cold-storage priority (verified contributors book first) · group-join tenure (member of some group ≥1 yr — without exposing which) · DAO vote participation. The guard modules (see reserved powers) are the enforcement point.

Constraints (settled): badges prove contribution, never worth — no class system, floors stay low · decay kills badge farming · holder-binding stops sale · minimal-disclosure predicates (correlation ceiling — never a fingerprint) · money stays fully auditable — ZK applies to participation/social stats, never cash flows.

> Consolidated spec — private ZK treasury, guards & ledgers: [private-treasury-guards-ledgers.md](private-treasury-guards-ledgers.md). Privacy by default, compliance on demand; money = shielded on-chain, participation = hash-chained off-chain; guards enforced in-circuit + on-chain + app-layer.

## What already exists (don't rebuild)

- User Safe deploy: `POST /api/safe/predict` + `POST /api/safe/deploy`
  (`apps/coop-api/src/safe.ts`), verified end-to-end Aug 2026
- Modules deployed on local node (singleton 0x5FbD…, factory 0xe7f1…,
  PasskeyValidator 0x9fE4…, SovereignEvolutionModule 0xCf7E…, SessionKeyModule 0xDc64…)
- Onboarding + account linking (coop-api authority), OAuth bridge (irl-dashboard ↔
  coop-api ↔ Keycloak ↔ Google) — all E2E-verified

## Gaps to build (when knobs are decided)

1. Passkey registration in coop-api (SimpleWebAuthn; PasskeyValidator module;
   P-256 via Base precompile 0x00…0100 per EIP-7212)
2. Infra DAO Safe deployment + backend Safe as deployer/co-owner
3. Group accounts (N-of-M creation; join = addOwnerWithThreshold)
4. Threshold-encrypted group secret vault (salt backups, env secrets)
5. Frontend onboarding Safe step (salt generation/backup UX, keep it invisible)
