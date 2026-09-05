# Digest — Group Shapes + Event Bus + Proofs + Economy

Faithful extraction from:
`event-bus-and-group-shapes.md`, `group-shape-scenarios.md`,
`zk-membership-graph-proofs.md`, `private-treasury-guards-ledgers.md`,
`regenerative-vision-note.md`, `delegation-and-session-keys.md`.
No editorializing; terminology verbatim.

---

## Group shapes

A **shape** is the template a group is born from — **five axes, four inward and one outward**:

- **roles** — the vocabulary, shared between authorization (who can edit the site) and notification targeting (who gets notified). Generalizes the founder/admin/member/inviter/observer set in irl-coop-group.md — that set is the `irl.coop` group's *default* vocabulary, one shape among many.
- **apps** — what gets provisioned, each with a hook.
- **config** — default delivery/urgency rules.
- **governance** — thresholds, quotas, membership policy. The **meta** axis: it governs how the other three (and itself) change, split into **constitutional** (amendment rules, quorum, admission/expulsion — hard to change) and **ordinary** (app bundle, delivery prefs, role assignments — shift under the constitutional process).
- **proofs** — the outward interface: what the group can reveal about itself without exposing internals.

**Shape = seed, not cage.** All five axes are *initial values* written to the group's Postgres record at provisioning. After that the group's record is authoritative and the shape is never re-read (except to show divergence from defaults). A split is a constitutional event producing two new records seeded from the parent's *current state*, not the original shape.

**Composition, not inheritance.** Shapes assemble primitives; they don't extend a base. "Men's circle" is a custom composition (its roles + apps + defaults), not a subclass of "group". Copy-then-modify means a built-in shape evolving later doesn't silently change existing groups.

**Three lifecycles — and the blueprint commons:**
- **built-in** — curated, git.
- **custom** — per-group, Postgres.
- **shared** — a group exports its shape to a public library; others adopt/remix.

The library shares **structure** (roles, apps, governance, proof schema), never **records** (members, votes, metrics) — a blueprint commons, not a data commons. "Highlighted" becomes community-signaled (adoption + remix count) as well as curator-picked. Library *hosting* (central vs federated) is a parked federation question; the *export* is group-local.

Disclosure spectrum (held independently per axis): **proofs-only** (private) ↔ **structure-shared** (library) ↔ **data-public**.

**Child relationships — a rights set, not a flag.** A group can hold a child relationship to another group (parent → child). Not a schema flag or type — it is the existing `subgroup-of` relationship composed with an economics edge for funding. Two declared relationship-record edges:
- **`subgroup-of`** (governance + infra): child is an autonomous Safe sharing the parent's namespace; its *terms* declare the rights set (veto on constitutional changes, reserved powers via the co-owner seat + guard + timelock) and what the child decides autonomously.
- **`sponsored-by`** (economics): the funding allocation — parent transfers a budget into the child's Safe; caps and budget-transfer authority are terms on this edge, not inferred from the subgroup edge.

The child is a full group (own Safe = its flat funding pool, own treasury, own budget and sub-accounts, own seats and governance). Strip the binding and it is independent. Composition applied to relations — the registry's own rule: "ownership implies membership ONLY; every other meaning is DECLARED." Nothing is inherited, everything is declared. A sub-project becomes a child group when it needs its own allocation or autonomous decisions — it is *promoted*, not subclassed.

---

## Event bus

**Model:** Sources *emit* events (votes, matches, alerts, email, chat); channels *deliver* them (toast, inbox, email, chat, push, a Temporal workflow). Email and chat are both. The bus is a **many-to-many router**: any source → any channel, governed by user/group preferences.

**The pipeline:**
```
source → event → notification → channel
```
- **event** — raw, typed, machine-readable: `vote.cast`, `match.found`, `mail.received`. Domain-specific, not user-facing.
- **notification** — rendered, user-scoped, localized: title, body, action, urgency.
- **channel** — where it lands.

**The event/notification split (why persist events).** Persist raw events as the source of truth; render notifications from them. Three things fall out free: **watches** (subscription layer over the stream, not a separate feature), **Temporal** (a workflow is just another channel consuming raw events), **future sources** (the offers/asks matcher emits `match.*` with zero bus changes). Collapsing events → notifications at publish loses all three.

**Topology, targeting, auth:**
- One Redis channel per user: `irl:notify:{sub}`.
- Group targets resolve **server-side**: coop-api looks up members + roles, filters by role allowlist, publishes to each eligible member's channel. The client only ever subscribes to its own channel and never does role filtering — role enforcement lives where it can't be spoofed.
- Targeting: **direct** (event names a user/group/role) and **watch** (saved predicate over the stream).
- Auth at the coop-api SSE edge (`GET /api/v1/notifications/stream`, bearer coop JWT); server subscribes to `irl:notify:{jwt.sub}`. Redis stays on the internal docker net.

**Delivery is not the bus's job.** The bus decides *who should know*; a group-configurable **Temporal workflow** decides *what to do about it* (email via Stalwart, post to Matrix). The bus never learns SMTP or Matrix. Delivery config (which event types route to which channels) lives in Postgres as group config, read by the workflow at execution time.

**Notification shape:**
```
{ id, user, type, title, body, action:{label, url, method?}, urgency, ts, read }
```
`action` = deep link + optional inline accept/reject (not decorative). `urgency` maps to channel behavior (high → toast + email; low → inbox only).

**Anonymization is owned by the source, never the bus.** The form system knows its anonymity setting and either omits the submitter or marks `anonymous`. The bus renders what it's given and never strips identity — privacy policy lives where the identity lives.

Event namespaces referenced: `vote.*`, `match.*`, `mail.*`, `chat.*`, `social.*` (e.g. `social.comment`), `project.completed`, `milestone.reached`, `group.created`, `group.<thing>.created`.

---

## Provisioning

**Two declarative layers, same shape:**
1. **Platform** (existing): `infra/instances/dev/` → `generator.py` → `out/` — shared infra, static.
2. **Group template** (new): per-shape YAML declaring the app bundle — Safe, roles, Plane project, DB schema, `info@{name}.irl.coop`, `{name}.irl.coop` site, Matrix room, other apps.

The group template maps **1:1 onto a Temporal provisioning workflow**: each declared app is an **activity (hook)**, run in order, idempotent, with compensation on failure. Flow: `group.created` → workflow → provision each → emit `group.<thing>.created` → notify members as things come online.

**Stored where:** template (what a group *should* get) → git, versioned. Provisioned state (what *this* group *actually* got — Safe address, Plane project id, DB schema, room id) → irl.coop Postgres (the group store). Same "declared vs running" idea as infra-management-monitoring.md, applied to groups.

**Boundary:** `info@{name}.irl.coop` needs **wildcard MX**, not just wildcard A. `*.irl.coop` A records cover the website; MX is a separate record type and wildcard-MX support at Gandi isn't guaranteed. Fallbacks: single mail domain with per-group local-parts (`info.menscircle@irl.coop`), or a Stalwart catch-all routed by recipient domain.

**Hot-pluggable apps.** An app is an independent unit: own compose pillar, own provisioning hook, own edge route + OIDC client. To add an app without a rebuild, separate three things currently one:
- **catalog** — what apps exist + their hooks/spec → git (versioned code)
- **activation** — is it on, for platform or this group → Postgres (runtime)
- **state** — the running instance → Postgres (runtime)

Add an app = catalog (code) + flip activation (Postgres) + run its hook (Temporal). Remaining friction: the traefik edge restart on `dynamic.yml` change (known quirk), and manual OIDC client provisioning.

**The reconciler (declared vs actual):**
```
declared  = catalog features × this group's activation    (what it should have)
actual    = resource_scopes + per-app state               (what it got)
drift     = declared − actual                             (missing → provision it)
reconciler runs the missing hooks (idempotent Temporal activities)
```
- **declared** — catalog's feature set filtered by activation rows (`app_activations`).
- **actual** — `resource_scopes` plus each app's state rows.
- **drift** — only gaps get filled. The reconciler never rewrites customization (composition, not inheritance). The sweep is one Temporal workflow fanning out per group (or a periodic job).

**Adoption policy** (who adopts a new feature — a new feature is NOT written into every existing group's record, that would turn the shape into a cage):

| feature kind | prod default | trigger |
|---|---|---|
| core (identity, common room, event bus, root membership) | opt-out | batch-reconcile all groups on ship |
| optional (any new app) | opt-in | lazy — hook fires on first use |
| platform (irl.coop root group) | always | declarative build |

- Activation rows live in `app_activations(group_id, app, enabled, adopted_at)` — kept separate from the shape so the shape stays read-only and the sweep can index by app.
- "Core" is narrow and rarely grows; the sole case that gets an eager opt-out sweep. Dev phase is non-lazy (in dev all kinds sweep on ship regardless of prod default); prod flips optional back to lazy/opt-in.

**Updates to existing apps:**

| change | auto? | mechanism |
|---|---|---|
| runtime (image bump) | yes | declarative layer bumps tag, container re-creates, app runs startup migrations — deploy-level |
| data/schema — additive + idempotent | yes | `ADD COLUMN IF NOT EXISTS` / `CREATE IF NOT EXISTS` (the existing `initDb` / `coop_rls.sql` pattern) |
| data/schema — transformative / breaking | no | versioned migration (schema watermark), run once explicitly, with rollback/compensation |

Rule: migrations auto-apply only when additive and idempotent; breaking changes are versioned, one-shot, reversible.

---

## On-chain

**Treasury principles (from private-treasury-guards-ledgers.md):**
1. Privacy by default — balances and flows are private to the account (Safe) that owns them.
2. Private from day 1 — never ships public-then-private; privacy is a one-way door.
3. Pure math, no TEE — all hiding/proving is ZK (commitments, proofs, nullifiers); no trusted hardware, no trusted operator, no Lit.
4. One treasury per Safe — every account (person 1-of-1, group N-of-M, DAO) holds exactly one private treasury, bound to its Safe but logically separate from Safe governance state.
5. Project accounts are sub-scopes, not entities — until they become groups (promoted to child group: own Safe + treasury + sub-accounts, bound by a child-relationship rights set). The parent's own Safe *is* the flat funding pool; no separate "funding pool" entity.
6. Compliance on demand, not by default — verifiable reports via selective disclosure, never publishing the whole book.
7. Money auditable; participation cheap — money = shielded on-chain; participation credits = off-chain hash-chained; badges = off-chain commitments.
8. Guards gate everything — three enforcement points; no single component can create or move value alone.
9. Settlement rails are the only visible points — inbound deposits / outbound withdrawals cross legal rails; everything INSIDE is shielded.

**The private treasury (shielded state model).** Reference architecture: shielded value pool (Zcash/Penumbra lineage; Aztec for EVM-embedded variants). The chain stores NO balances — it stores commitments.
- **Notes (UTXOs).** Value lives in notes: `commit(amount, owner_key, project_scope, rng)`. A note is an asset of exactly one project account inside one treasury.
- **Commitments tree.** Each treasury's note commitments form a Merkle tree; the root is the chain state. Balances are not readable from the chain — only commitments.
- **Nullifiers.** Spending reveals `nullifier = H(note_secret)`. Chain checks "nullifier unseen" — a note spent exactly once; double-counting structurally impossible.
- **Transfers as ZK proofs.** A transfer proves: (a) sum of input notes = sum of output notes (**conservation, in-circuit**); (b) every input nullifier corresponds to a committed note (existence); (c) the spender is authorized — the proof attests the Safe's quorum signed (**EIP-1271** from the Safe) and the guard conditions held; (d) outputs are new commitments to recipients' trees.
- **Viewing keys.** Master viewing key (held by the Safe's custodian set). Project accounts get **PROJECT VIEWING KEYS** — sub-key opening only that project's notes. Compliance = a scope-limited report (opened amounts for a period, or ZK proofs over them: total received ≥ X, net position, tax basis) WITHOUT the rest of the treasury.

**Project-based money accounts (guard conditions):**

| Account | Scope | Typical rules (guard conditions) |
|---|---|---|
| Savings goal (solar fund) | personal | standing order routing, target cap, withdraw only by owner |
| Capital-raising pool | group | quorum-gated, no single withdrawal, per-member contribution sub-ledger |
| Operating fund | group | 2-of-3, per-ledger limit, expense categories |
| Distribution fund | group | auto-split per entitlement table, monthly via keeper |
| Reserve | group | 3-of-5, timelock on outflow, circuit-breaker freeze |
| DAO treasury | DAO | full constitution: budgets, grants, veto paths |

**Guard integration — three enforcement points** (same rule language compiled to all three targets):
1. **In-circuit conditions** — the transfer proof itself attests policy (per-ledger limits, required seats encoded as the Safe's signature in the circuit's public inputs, timelock windows, zk-badge gates = proof-over-proof). A violating tx cannot even be CONSTRUCTED as a valid proof.
2. **On-chain Safe guard (`TransactionGuard`)** — authoritative for governance-adjacent actions the circuit doesn't cover: owner-set changes, module installs, relationship-record edits, seat protection. Solidity, reads the registry, gates the Safe's `execTransaction`.
3. **App-layer pre-validation (coop-api policy engine)** — same rules evaluated cheaply before submission (UX, gas, belt). Never authoritative alone.

Guards are data-driven (terms from the relationship registry), versioned, upgradeable only through the guarded path.

**Ledger taxonomy (the hybrid):**

| Tier | What | Where | Integrity |
|---|---|---|---|
| 1 | Money: savings, shares, capital, distributions, DAO funds | **Shielded on-chain** (ZK treasury) | conservation in-circuit + nullifiers + chain consensus |
| 2 | Participation: time-bank hours, labor swaps, quest credits | Off-chain (Postgres), hash-chained, periodically anchored | double-entry invariant + idempotency keys + sequence numbers + hash chain + Merkle anchors on-chain |
| 3 | Badges/stats: zk-badge predicates | Off-chain commitments | proof binds to Tier-2 hash chain / provenance hashes |

Rule: **money stays auditable — Tier 1 is never public, but it is always provable.** Cash flows are never invisible to the OWNER or authorized reporters, only to third parties.

**Architecture placement:** Chain (Base-class EVM; local Hardhat today) = Safe contracts, guard modules, shielded-treasury contract (commitment tree, nullifier set, Groth16/PLONK verifier), registry, relationship records, anchors. Prover = client-side (sovereignty pattern; notes/secrets never leave home). coop-api = JWT bridge, provisioning, policy engine, submission path. Temporal = the keeper (standing orders, monthly distributions split per entitlement table, timelock racing, badge decay refresh, dead-man's-switch countdowns). Postgres (Citus) = read model (profiles, projects, registry materialized views, Tier-2 ledger log append-only hash-chained, event log).

**Settlement & sponsorship (chargeback protection).** Fiat is reversible ~130 days (Visa/MC/ACH dispute windows); Safe (crypto) is final. The "sponsor" is a **vertical fund** — a `subgroup-of` irl.coop (root group) whose Safe *is* the fund's crypto treasury. A group is **`sponsored-by`** its vertical fund (one-way flow, recognition, **no control**); cap, settlement fee, repayment schedule are terms on the edge. Contributor fiat → group escrow (Tier-2 pending-liability ledger, held 130 days, chargeback-exposed). Fund crypto → group liquidity (Tier-1 inbound, instant/final). **T+130 settlement** (the only visible crossing): fiat repays the fund's principal, settlement fee taken, remainder to the fund always. Chargeback losses absorbed by the fund up to the per-vertical cap (fund's "Reserve" sub-account is the chargeback-protection pool).

**Decided (Aug 2026):** (1) Capitalization = donors to irl.coop + coop-member governance decisions, informed by member surveys (Formbricks). (2) Settlement remainder always to the fund. (3) Sponsorship priority is **computed, not declared** — cooperativeness is a *measured* score (inputs: regenerative score ZK-metric, communication patterns, internal payouts, transaction types, events, livestreams, chats). (4) Cap set by per-vertical policy voted by that vertical sub-group's members. **Purpose categories** (food sovereignty, civic engagement, infrastructure, …) are multi-valued organizing axes, each maintained by a vertical sub-group. Bad-actor signal is reputation-derived but human-gated (every grievance investigated by an irl.coop representative before affecting standing). Conflict-of-interest exclusion: investigators drawn by random quorum from the vertical; candidates "too close" (extended graph distance/connection weight over the relationship registry) auto-excluded via ZK proof.

---

## ZK proving

**The primitive** (zk-membership-graph-proofs.md): the group graph is **hidden by default, provable on demand** (group-scoping §3). Four statements, increasing difficulty:
1. **Membership** — "X is a member of group G."
2. **Role** — "X holds role Y in group G."
3. **Relationship** — "edge (G₁, R, G₂) exists" for R ∈ {member-of, subgroup-of, sponsored-by, federated-with}.
4. **Distance / connection weight** — "X is ≥ K hops from G" (conflict-of-interest exclusion), and weighted form "weight(X, G) ≤ T."

**Feasibility verdict:** core is feasible today with off-the-shelf tooling; only the *exact* distance form is research-grade. The single real risk is prover performance on mobile, not cryptographic possibility.

| Statement | Construction | Feasibility |
|---|---|---|
| Membership "X ∈ members(G)" | Merkle proof over the group's member-commitment tree (Semaphore / zk-kit lineage) | Off-the-shelf |
| Role "X holds Y in G" | membership proof with the role inside the leaf commitment | Off-the-shelf |
| Relationship "edge (G₁,R,G₂)" | membership proof over an edge-commitment tree (each edge a committed leaf) | Off-the-shelf |
| Non-membership "X ∉ members(G)" | frontier tree, or sorted-tree range proof (Micali–Rabin–Kilian ZK-Sets; eprint 2019/1255, 2024/1259) | Off-the-shelf |
| Bounded distance "dist(X,G) ≥ K", small K | conjunction of non-membership over G's ≤(K−1)-hop neighborhood | Feasible, medium effort |
| Exact distance "dist(X,G) = K", arbitrary K | ZKGraph-style SSSP verification (relaxation + lookup constraints over the edge table) — O(m) circuit | Research-grade |

**Membership & role.** Each group maintains a **member commitment tree** — a Merkle tree whose leaves are `commit(sub, role)` (Keycloak `sub` + seat role(s), blinded by a per-seat nonce). Root is public (or in the on-chain registry). Membership = standard Merkle-authentication-path proof in ZK so neither `sub` nor role is revealed beyond what the statement asserts. "X holds role Y" = role exposed as public input, `sub` hidden. Same primitive `ConfidentialVoting.sol` (Semaphore) uses for private tallying.

**Relationship edges** (edges, not columns): each declared edge `(G₁, R, G₂, terms)` is a commitment; proving "this edge exists" is a membership proof over the group's **edge-commitment tree** (or a global edge registry tree). Can reveal R and one endpoint while hiding the other.

**Non-membership.** "X ∉ members(G)" without revealing the tree: prove X sorts strictly between two adjacent leaves (sorted-tree range proof), or prove the leaf at X's index is empty in a sparse/frontier tree (ZK-Sets lineage).

**Distance / connection weight.** Exact ("dist(X,G) = K") is research-grade: state of the art (ZKGraph, arxiv 2507.00427; ALITHEIA, CCS'14) proves shortest-path correctness by *not* running BFS in-circuit — the prover computes distances off-circuit, the circuit verifies the distance vector via Bellman-Ford relaxation + predecessor/edge lookups; O(edges), doesn't scale. Bounded ("dist(X,G) ≥ K" for small K) is the form actually needed: "not within K−1 hops" = X ∉ members(G) **and** X ∉ any group related to G within depth K−1 (member-of, subgroup-of, sponsored-by edges) — a **conjunction of non-membership proofs over G's bounded neighborhood**. **Decision (recommended):** ship bounded distance with K ∈ {1,2,3}; defer exact distance indefinitely (fallback = include-but-reveal-weights). Connection weight = same bounded neighborhood, summed with decay per hop, then range-proved (`weight ≤ T`).

**Two tiers of "hidden":**
- **Hidden-from-public (tier 1 — the default "hidden-norm").** Membership stored centrally but RLS-scoped; member reads own seats; third parties can't enumerate; no public projection. Roles/grants mint as today — `getRolesAndGrants(sub)` reads the user's own seats into JWT `roles`/`grants` claims. Keeps plaintext `group_members` projection, hidden only from third parties via RLS.
- **Hidden-from-platform (tier 2 — opt-in, deferred).** Platform holds only commitment roots, no plaintext seats. Roles no longer read from DB — user presents membership proofs at sign-in, backend verifies into JWT. Costs: (a) JWT mint becomes proof-verification; (b) member fan-out can no longer enumerate members — resolved by derived delivery keys or pull-based delivery (v0 fallback). Per-group opt-in, not the norm.

**Prover/verifier placement & tooling.** Prover runs **client-side** (sovereignty pattern; backend never holds witnesses), verifier runs **on-chain** (Groth16/PLONK verifier), coop-api is the relay/pre-validation layer. Tooling: **Poseidon over BN254**, Groth16 (or PLONK), Semaphore/zk-kit for membership, ZKGraph's expansion-centric circuits only if exact distance ever needed.

**Phasing:** v0 = membership + role + non-membership (off-the-shelf tier); v1 = relationship edges; v2 = bounded distance (K ≤ 3) for conflict-of-interest exclusion; v3 (only if needed) = exact distance (ZKGraph).

**Fan-out without enumeration — derived delivery keys.** Fan-out needs endpoints, not identities:
- **Membership tree** — commitments of `(sub, role)`; hides *who* is a member.
- **Delivery tree** — per-group derived public keys (stealth-address / subaddress style): `D_i = H(sub_i, group_id) · G`. Platform enumerates these (they are just keys) and fans out; each member scans with their private scanning key. Keys are unlinkable to identities.
Per channel: Notifications/digests = encrypt to delivery key, liveness via public per-group "new events" counter (v0 poll-on-counter, v1 push-to-key). Mail = derived opaque mailbox `{token}@{group}.irl.coop` (never `{name}@`). Matrix = already solved. Telephony ring group = genuinely hard (reachable + linkable by nature); if impractical, telephony stays tier-1.

**Regenerative score as ZK-metric** (regenerative-vision-note.md). Four generic-core metrics, each required to pass the inclusion test (provable in ZK **and** hard to game):

| Metric | Signals | The anti-signal it catches |
|---|---|---|
| **flow** | value actually moved (contributions, exchanges) | aspiration without activity |
| **reciprocity** | flow balanced vs extractive | the freeloader |
| **distribution** | flow spread vs hub-concentrated | 100 members, 3 active |
| **persistence** | retention + survival of a node leaving | churn / succession fragility |

These composite into the regenerative score. Honest > comprehensive: a Sybil-friendly metric defeats the proof entirely, since a ZK proof only vouches for the claim, never the truth of the data. Principles: (1) Privacy-Preserving — proof of cooperative acts/skill-sharing/land contributions computed locally on-device, only the verified cryptographic proof submitted/verified on-chain (ZK-SNARKs/ZK-proofs); (2) Individual & Group Metrics — both members and entire groups maintain scores; (3) Sovereign Reputation — decentralized, non-transferable primitive for governance weights, resource allocation, micro-grant distribution.

**Freshness and binding.** A proof is a snapshot and must bind a timestamp/block ("as of block N, score ≥ 0.8"), or a stale proof is indistinguishable from a current one. It binds the claim to the group's public identity (its Safe address) so it can't be replayed by another group.

**Privacy by default.** The ZK layer is a third consumer of internal state (alongside notifications and Temporal). Group internals feed the prover; the prover emits proofs; verifiers check against the group's public commitment. External parties never touch internals — a proof is the only sanctioned leak.

**What is proven vs hidden (summary):** proven = specific membership/role/relationship/distance/score-threshold facts as asserted by the statement; hidden = the `sub`, the unasserted roles, the tree contents, the unasserted endpoints, and the raw amounts/balances (in the treasury). Membership proofs reveal `role` only when the statement exposes it as a public input; `sub` is hidden.

---

## Delegation

**Settled invariant (do not relitigate):**
1. **No bypass on Temporal.** Every Temporal call is authorized by a *user's* **ERC-4337 session key**. No service identity, no system role, no `BYPASSRLS` function, no cross-user reader.
2. **Secrets split into two non-overlapping domains:** *user secrets* (Safe-anchored Vault slice, unlockable only by that user's session key) vs *platform secrets* (`master.key`, webhook tokens, client secrets — only in coop-api's process env; Temporal can never read them).
3. **The worker is dumb.** It must not source `secrets.env`; identity and secrets arrive per execution, injected from the session-key unlock.

**Delegation, not custody** (three properties, all ERC-7715-native):
1. The signer is a **permitted key, not an owner** — the Safe remains owner and sole source of truth.
2. The permission is **scoped** — bounded actions, caps, recipient allowlists, expiry ("act as me within this exact box," not "act as me").
3. Revocation is **instant and on-chain**, controlled by the Safe, never the delegate.

Custody = the platform holds the asset's authority. Delegation = the platform holds a scoped, revocable permit. The Safe never hands over ownership.

**One primitive, three shapes** (an ERC-7715 permission grant, Safe → signer, differing only in holder/scope/expiry):

| shape | holder | expiry | scope |
|---|---|---|---|
| interactive session key | user device | short | app-level |
| automation / delivery key | platform (custodial, encrypted) | long / renewable | narrow, per-workflow |
| agent key | agent runtime | bounded | narrow, stricter |

**Presence decides the mode** (same scope content is holder-agnostic): user present + direct dashboard engagement → interactive session key (live lane); user absent / event-driven reaction / scheduled work → delivery key (Temporal's durable lane). Temporal's job = **forward** (relay events), **trigger** (react to events), **automate** (scheduled). Scope *content* is holder-agnostic — holder + mode + expiry are delegation-registry metadata, not part of the scope schema.

**External channels — the group as a user with a phone.** Two layers: **phone layer** (runner fleet, existing browser-management/Playwright pillar, holds each channel's session, presents the group's identity; external apps see only "a logged-in account," never the Safe) + **permission layer** (ERC-7715 grants authorize who may drive the phone). Schema consequence: `resources` gains external-account references (`whatsapp:<num>`, `telegram:<channel>`, `signal:<num>`, `postiz:<account>`, `email:<mailbox>`) beside internal `resource_scopes`/`route`/`treasury`; `actions` become channel-agnostic (`channel:send`, `channel:read`, `channel:respond`). External channels make limits + revocation more load-bearing; `browser-management` itself must come under the delegation model.

**How the session key reaches Temporal (the bridge):**
1. User's device holds a session key (ERC-7715 grant from their Safe).
2. User signs a challenge; coop-api validates the signature AND the on-chain grant (`isValidSignature` / the permission record).
3. coop-api mints a short-lived Temporal JWT (claims encode Safe → user mapping + granted scope).
4. JWT rides `authorization:` gRPC metadata into Temporal; the authorizer validates against coop-api's JWKS and maps claims → namespace/ops.

Temporal stays a dumb JWT verifier; coop-api is the only thing that touches the chain.

**Provision-time delivery key.** Account provisioning creates a dedicated, longer-lived delivery key (the one moment the user is present to sign the grant, after `ensurePersonalSafe`, alongside the personal group). Narrow scope: read own events/notification state (RLS-bound), deliver own digest — never another account's data, never a platform secret, never a Safe-control op. **Custodial**: coop-api holds the private material, encrypted, per-user, in the user's Vault slice (semantically a *user* secret, not a platform secret). Safe-revocable + renewable ("long-lived" ≠ "permanent").

**Groups delegate via roles (roles are bundles, not labels).** A **role is a named bundle of scoped ERC-7715 grants**, not a string like "admin." Assigning a role = the group Safe signs the grants to the member's key (or agent/Temporal key); removing a role = revoking the bundle. No shared keys, no inheritance — permissions composed from roles held (composition-not-inheritance made literal). Two levels: who may assign/revoke roles is itself a governance decision (threshold, voting). `resource_scopes` (group_id → app → resource_key) is the proto-registry; roles formalize it (role → apps, resources, limits, expiry). **The table is the index, the Safe is the source of truth, the grant is the enforcement.**

**The 5-axis group shape** — roles are the delegation layer; apps = which surfaces a role reaches; config = the limits; governance = who may assign/revoke; ZK-proofs = anonymous presentation of a role.

**ZK presentation.** "Prove I hold role X" without revealing which member — a ZK proof against the role registry, verified by the group Safe. Same grant layer, zero-knowledge presentation instead of a bare key. Feeds the regenerative-score metric.

**Delegation registry (the anchor).** One registry enumerates every delegate (session, automation, agent) with scope + expiry; one place to revoke. On-chain ERC-7715 grants are the truth; off-chain index makes it queryable by Temporal, agent runtime, app. The Safe is the revocation authority for everything. Every actor is a *named delegate with a visible, revocable scope*.

**Decided (Aug 2026) — custody shape:** device-side generation bundled into provisioning (same flow as passkey registration; ~100ms WebCrypto keygen, no new screen). Delivery key is a disposable, scoped, revocable permit — recovery = revoke + re-issue (no backup share). Provisioning becomes a **delegation manifest**: generate + register the account's full key set (delivery key now; agent keys opt-in later), each with a Safe-signed grant, in one atomic flow. Extensible after — seed, not cage.

**Coordination family — routing, escalation, unifying pattern.** A third action family beside financial and data: **coordination**. Response router dispatches each inbound (`social.comment` event, Temporal consumer) to an outcome on an automation→human spectrum: send material (none), lead to form/website (low), notify a rep to reach out (handoff 1:1), popup FCFS volunteer queue (coordination 1:many). New resource types: `person:<sub>`, `queue:<vertical>:volunteers` — the first *human* primitives. The three tiers (deterministic rules / agent judgment / human moderator) are ONE escalation ladder, boundaries set by governance at grant time. `limits` generalizes to **constraints** — numeric caps/allowlists for money, escalation-ladder policy for coordination (same slot, different content; shape stays five fields). Unifying pattern: governance decides → a delegate executes → the grant is the bridge (its content IS the decision) → the Safe revokes.

---

## Commons economy

**Pay-what-you-want** (event-bus-and-group-shapes.md §7). Full visibility into cost, "pay what you want" on payment, and a **coverage proof** as the social signal — the anti-freeloader signal for the infrastructure layer (as reciprocity is for the exchange layer). Two economies, one principle: reveal good citizenship, not means.
- **Cost is public** — every group's infrastructure cost is published.
- **Payment is private-but-provable** — the group proves "covered ≥ X%" without revealing the amount (load-bearing: a subsidizer proves generosity without advertising slack to opportunists).
- **Encourage, not enforce** — the proof is a *positive* credential; its absence is *neutral* (non-coverage inferable, never asserted — no shame flag). A carrot with no stick.
- **Subsidy gradient** — free-rider → covers-self → subsidizer, provable as ranges ("covered ≥ 100%", "≥ 150%", "subsidized N others"). Groups can cover other groups' costs.
- **Single-user groups** are the degenerate case, not a special one — "every account is a group of one"; same schema and threshold apply to an individual and a 500-member collective.
- **The gamble is testable** — costs and coverage both visible, so self-selection pressure can be observed and adjusted.

**Currencies (ledger tiers).** Three distinct value ledgers: Tier 1 **money** (shielded on-chain, ZK treasury), Tier 2 **participation credits** (off-chain hash-chained — time-bank hours, labor swaps, quest credits), Tier 3 **badges/stats** (zk-badge predicates, off-chain commitments).

**Scores.** The **regenerative score** (ZK-metric) composes flow/reciprocity/distribution/persistence; sovereign, non-transferable, used for governance weights, resource allocation, micro-grant distribution. The **cooperativeness score** (sponsorship priority) is *computed, not declared* — inputs are the operational signals the event bus + ledgers already ingest (regenerative score, communication patterns, internal payouts, transaction types, events, livestreams, chats). The formula (inputs/weights/thresholds) is set by each vertical sub-group; the platform supplies the measurable-signal substrate, not the formula.

**Skill-sharing economy** (group-shape-scenarios.md). Ten scenarios reduce to shared primitives: labor/contribution credit (Tier-2 time-bank), resource match (offer↔need, `match.*`), inventory+reservation, funding pool (the group's Safe *is* the flat pool), fairness/reciprocity (regenerative score), calendar/rotation/coverage, external guests, anonymized story capture, events/RSVP, collective selling, treasury payout engine, federation (parked). The two highest-leverage primitives: the **labor-credit ledger** and the **matcher** (appear in almost every scenario); the **funding pool** is third.

**Vertical funds & sponsorship.** A group is `sponsored-by` its vertical fund (a `subgroup-of` irl.coop whose Safe is the fund's crypto treasury). Fiat absorbed through the fund's T+130 settlement; the fund is the fiat→crypto bridge. Purpose categories (food sovereignty, civic engagement, infrastructure, …) are multi-valued organizing axes, each maintained by a vertical sub-group. Sub-verticals named: Land Back, Solidarity Economies, Ecological Repair, Community Safety, Healing Justice, Cultural Power, Relational Infrastructure.

---

## Diagram nodes

### Group shapes
- **nodes**: Shape (5 axes), Group (Postgres record), Role vocabulary, App bundle, Config (delivery/urgency), Governance (constitutional / ordinary), Proofs interface, Library (built-in / custom / shared), Parent group, Child group, Registry.
- **edges**: Shape →(seeds at provisioning)→ Group record; Group record →(authoritative, shape never re-read)→ …; Governance →(meta, governs)→ {roles, apps, config, governance}; Group →(subgroup-of)→ Parent; Parent →(sponsored-by)→ Child; Group →(exports structure)→ Library; Library →(adopt/remix)→ Shape; split →(constitutional event)→ two new records seeded from parent's *current state*.

### Event bus
- **nodes**: Source, Event (typed), Notification (rendered), Channel, Redis (`irl:notify:{sub}`), coop-api SSE edge, Temporal workflow, Postgres delivery config, Watches, Matcher (`match.*`).
- **edges**: Source →emit→ Event →render→ Notification →deliver→ Channel; coop-api →(resolves members+roles, filters role allowlist)→ publishes to each member's `irl:notify:{sub}`; Event stream →(subscription predicate)→ Watch; Event stream →(channel consumer)→ Temporal workflow; Temporal →(reads delivery config)→ Postgres; Temporal →email→ Stalwart / →post→ Matrix; Source →(owns anonymization)→ omit/`anonymous` mark.

### Provisioning
- **nodes**: Group template (per-shape YAML), catalog (git), activation (`app_activations`), state (Postgres), Temporal provisioning workflow, app activity (hook), resource_scopes, reconciler, generator.py (platform layer).
- **edges**: `group.created` →→ workflow →provision→ each app hook (idempotent, compensable) →emit→ `group.<thing>.created` →→ notify members; declared (catalog × activation) − actual (resource_scopes + app state) = drift → reconciler runs missing hooks; catalog entry (git) + flip activation (Postgres) + run hook (Temporal) = add app.

### On-chain
- **nodes**: Safe (N-of-M), TransactionGuard, shielded-treasury contract (commitment tree, nullifier set, Groth16/PLONK verifier), registry, relationship records, anchors, Notes (`commit(amount, owner_key, project_scope, rng)`), nullifier (`H(note_secret)`), master viewing key, project viewing key, keeper (Temporal), Postgres (Citus) read model, vertical fund.
- **edges**: transfer proof →attests→ conservation in-circuit + existence + EIP-1271 quorum signature + guard conditions; note →(spend)→ nullifier →(chain: "unseen")→ one-time; Safe →(EIP-1271)→ transfer; TransactionGuard →(gates)→ execTransaction; keeper →(monthly distribution per entitlement table, standing orders, timelock, dead-man's-switch)→; vertical fund →(sponsored-by, T+130 settlement, cap)→ group Safe; master viewing key →(opens)→ whole treasury; project viewing key →(opens)→ project account only.

### ZK proving
- **nodes**: prover (client-side), verifier (on-chain, Groth16/PLONK), member commitment tree (`commit(sub, role)`), edge commitment tree, sorted-tree / frontier tree, bounded-distance neighborhood, delivery tree (`D_i = H(sub_i, group_id) · G`), coop-api relay, regenerative score.
- **edges**: prover →(witness = own secrets, never leaves device)→ proof; verifier →(checks)→ group public commitment (root / Safe address); member tree →(Merkle path proof)→ membership/role; edge tree →(membership proof over committed edge)→ relationship (reveal R + one endpoint); sorted/frontier tree →→ non-membership; non-membership conjunction over ≤(K−1)-hop neighborhood →→ bounded distance (K ∈ {1,2,3}); delivery tree →(enumerate keys, unlinkable)→ fan-out; flow/reciprocity/distribution/persistence →composite→ regenerative score →(ZK-metric proof)→ verifier.

### Delegation
- **nodes**: Safe (owner), session key / delivery key / agent key (ERC-7715 grants), delegation registry, coop-api (JWKS, chain touch), Temporal (dumb JWT verifier), Vault slice, runner fleet (phone layer), role bundle.
- **edges**: Safe →(ERC-7715 grant)→ permitted key (scoped, revocable); user signs challenge → coop-api validates signature + on-chain grant (`isValidSignature`) → mints short-lived Temporal JWT → `authorization:` gRPC metadata → Temporal authorizer validates against coop-api JWKS; provisioning →(signs grant)→ delivery key (custodial in Vault slice); role = bundle of grants →(Safe signs)→ member/agent key; delegation registry →(enumerates every delegate + scope + expiry)→; governance decides → delegate executes → grant bridges → Safe revokes.

### Commons economy
- **nodes**: group infrastructure cost, coverage proof, payment (private-but-provable), subsidy gradient (free-rider / covers-self / subsidizer), Tier 1 money, Tier 2 participation credits, Tier 3 badges, regenerative score, cooperativeness score, matcher, labor-credit ledger, vertical fund.
- **edges**: cost →(published)→ public; payment →(coverage proof "covered ≥ X%")→ positive credential (absence neutral); reciprocity/flow →→ regenerative score →→ cooperativeness score (computed, not declared) →→ sponsorship priority; offer↔need →matcher→ `match.*` events; labor/items →(Tier-2 time-bank, hash-chained)→ participation credit; group →(sponsored-by)→ vertical fund →(T+130, cap, remainder to fund)→ settlement.
