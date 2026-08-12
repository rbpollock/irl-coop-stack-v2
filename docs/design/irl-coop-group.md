# The irl.coop Group — Safe-as-the-Co-op, Invite-on-First-Signin, Roles, Voting, Auto Matrix Channels

Status: design · Aug 2026 · Builds on world-doc-and-contacts.md (seats), account-and-key-model.md (Safe), private-treasury-guards-ledgers.md (treasury), and the live Matrix stack (matrix-synapse-stack.md). Companion docs: world-doc-and-contacts.md, world-doc-architecture.html.

## 0. The shape in one paragraph

The co-op is a **group Safe** — `irl.coop` — deployed like any other account's Safe (CREATE2-deterministic from the same factory/singleton, so it needs no special machinery). Every human who signs in becomes a **member of the group** on first signin (the group is the default landing seat, not an opt-in). Membership, roles, and votes are Safe-governed state (on-chain quorum, EIP-1271). Communications are **auto-provisioned**: each group gets a Matrix space/room-set created by coop-api through the Synapse admin API, and each member's seat carries their Matrix identity. The dashboard's world-doc is the per-user projection of all of it.

## 1. Principles

1. **The group is the primitive, not the user.** Every account is already a Safe; the co-op is one Safe the members hold together. No separate "organization" entity — groups ARE Safes with N-of-M governance. This is the network-theory shape Robbie keeps coming back to: nodes (Safe-accounts) + edges (memberships) = one cooperative graph.
2. **Invite-on-first-signin.** The first time anyone signs in through the Google broker / Keycloak, coop-api atomically: (a) creates the person account (their own Safe, 1-of-1), (b) mints a seat in the `irl.coop` group, (c) provisions their Matrix account + auto-joins the coop rooms. One signin → fully provisioned member. No "join request" gate in dev; approval gates come later per group settings.
3. **Seats are the universal membership primitive.** A seat = per-(user, group) persona `{sub, alias, roles[], visibility, MatrixId, joinedAt}` (world-doc-and-contacts.md). The group seat is the first-class citizen; the personal account is the "self-group" seat. Every app reads the seat, never the raw identity.
4. **Governance is Safe-governed.** Roles are Safe state (owners set, threshold). Voting is Safe transactions (proposal → quorum signatures → execution). The off-chain layer (coop-api) is the UX and the orchestrator — it never holds veto power over group state.
5. **Communications are derived, not stored.** Matrix channels are provisioned FROM the group state (name, member list, roles) and their existence is a projection; the room list in the world-doc is rebuilt from the Synapse admin API, not a separate registry. Delete a group → rooms archived by the same flow that created them.
6. **One identity, one cookie, every app.** The coop_session cookie + per-client id_tokens (fleet-session-gateway) already make "one signin" real; the group layer rides the same rails. No second login for the co-op.
7. **Deterministic, declarative, derivable.** Group ids, room aliases, Matrix localparts, and vote ids are all deterministic (CREATE2 / hash / localpart templates). Nothing in the group layer needs a store of record beyond what exists (Safe on-chain + Synapse DB + the seat index in Citus).

## 2. The irl.coop group Safe

### 2.1 Deployment

- Same `SafeProxyFactory` + `Safe` singleton as user accounts (safe.ts has the creation code + CREATE2 math).
- Salt: a fixed, documented salt (`irlcoop-group-v1`) → **address is deterministic** and can be pre-printed in the UI/docs before deployment.
- Initial owners: Robbie (the deployer), threshold 1-of-1 in dev → promoted to 2-of-3 (Robbie + 2 founding members) when the co-op formalizes.
- The Safe is `safe.irl.coop`'s canonical address in coop-api config (SAFE_SINGLETON_ADDRESS exists in .env already; the GROUP singleton address is a new env).

### 2.2 What the group Safe owns

| Asset | Mechanism | Notes |
|---|---|---|
| Treasury | The group treasury (private-treasury-guards-ledgers.md), one per Safe | shielded notes, group quorum to move |
| Roles | Safe owners set + a role registry (off-chain seat index) | membership = owner list; roles = labeled owner sets |
| Votes | Safe transaction proposals (EIP-1271) | quorum signatures → execution |
| Communications | Matrix space/rooms (derived) | created by coop-api via Synapse admin API |
| Identity | The group's OIDC presence (future: group-level OIDC clients) | the co-op as a single entity to external apps |

### 2.3 Membership = Safe owners

A person is a member of `irl.coop` **iff** their Safe address is in the group Safe's owner set. The seat index (Citus) is the readable projection of that on-chain fact; the chain is truth. This gives:
- **Provable membership**: any member can produce the on-chain owner-set proof (EIP-1271 signature check or a Merkle/state proof).
- **Clean exits**: removing a member = one Safe transaction removing an owner. All derived state (Matrix rooms, seats, world-doc entries) follows the change via the event → projection pipeline.
- **Boundary-condition friendly** (Robbie's favorite lens): owner death/abandonment → threshold recovery (already designed in account-and-key-model); the group Safe's threshold + recovery path mirrors the individual ones.

## 3. Invite-on-first-signin (the flow)

### 3.1 Signin pipeline (coop-api, after the Keycloak/Google callback)

1. **Person provisioning** (exists): user row + own Safe (CREATE2 from their passkey material) + profile.
2. **Group seat mint** (new): `ensureGroupSeat(sub, group="irl.coop")`:
   - Reads the group Safe's owner set (RPC/etherscan-proof or a cached index).
   - If the user's Safe is not an owner → **propose+execute the add-owner Safe transaction** (threshold 1-of-1 in dev: the backend signer executes directly; multi-sig later: the new member's join is a proposal the founders approve).
   - Writes the seat: `{sub, alias (from email localpart), roles: ["member"], visibility: "members", joinedAt}` into the Citus seat index.
3. **Matrix provisioning** (new): `provisionMatrix(sub)`:
   - Synapse admin API: create user `@<localpart>:matrix.irl.coop` (localpart = email localpart, the existing OIDC convention), set display name.
   - Auto-join the coop rooms (see §5): the group space + default channels.
   - Store `matrixId` on the seat.
4. **World-doc refresh**: the user's world-doc now shows the irl.coop group (seats, rooms, treasury view, capability).

### 3.2 Idempotency

`ensureGroupSeat` is fully idempotent: running it on every signin is safe (seat exists → skip; Matrix user exists → join rooms; owner already set → no-op). This is what makes "invite on first signin" robust — it's a convergent function, not a one-shot job.

### 3.3 First signin is the invite

There is no separate "invite" concept in dev: the Google account IS the invitation (the broker's email allowlist, or later a domain/credential gate). The gate belongs to the group's settings, not the code:
- `open` (dev): any verified email becomes a member.
- `invite-list`: only emails on the group's allowlist (a Safe-controlled list, so it's on-chain-adjacent).
- `approval`: signin creates a PENDING seat; an existing member (role ≥ inviter) approves → seat activates. (This is the "invite each user into the coop" Robbie described — a later toggle.)

## 4. Roles

### 4.1 The role model

Roles are **labels on owner sets**, stored in the seat index, governed by the Safe (changing a role = a Safe transaction that coop-api executes on quorum).

| Role | Powers | Default owner set |
|---|---|---|
| `founder` | everything (manage owners, roles, treasury, group settings) | Robbie |
| `admin` | manage channels, approve members, moderate | founders + appointees |
| `member` | post, vote, read (per visibility) | every member |
| `inviter` | approve pending seats | admins |
| `observer` | read-only seat (hidden groups) | by invite |

### 4.2 Role → capability matrix (app-layer enforcement)

coop-api checks the seat's roles on every group-scoped call:
- `POST /api/v1/groups/:id/rooms` → requires `admin`
- `POST /api/v1/groups/:id/votes` → `member`
- `POST /api/v1/groups/:id/members/:sub/approve` → `inviter`
- treasury ops → Safe quorum (on-chain), app layer pre-validates

The Safe is the final arbiter (EIP-1271 for signatures); the app layer is the UX gate. Both must agree — the two-layer rule from private-treasury-guards-ledgers.

## 5. Communications — auto-provisioned Matrix

### 5.1 The channel model

Each group gets, created by coop-api via the **Synapse admin API** (`POST /_synapse/admin/v1/rooms`):

| Channel | Alias | Purpose | Who |
|---|---|---|---|
| Group space | `#irl-coop:matrix.irl.coop` | the space containing all rooms | all members |
| General | `#irl-coop-general:matrix.irl.coop` | default conversation | all members |
| Governance | `#irl-coop-governance:matrix.irl.coop` | votes, proposals, decisions | members (founder/admin post) |
| Treasury | `#irl-coop-treasury:matrix.irl.coop` | money talk | members (treasury view shared) |
| Per-project | `#irl-coop-<project>:matrix.irl.coop` | auto-created when a project/treasury-scope is created | project members |

Room names/aliases are **deterministic** from the group + channel id — recreating a deleted room yields the same alias (idempotent provisioning, same principle as §3.2).

### 5.2 Provisioning flow

1. Group created → coop-api calls Synapse admin API: create space + general + governance + treasury rooms, set canonical aliases, set join rules (`restricted`/`invite`), power levels (founder/admin = power 100, member = 50, observer = 0 read-only).
2. Member seat minted → `join_room` via the member's own Matrix account (the admin API joins on their behalf using their access token, or the service account invites + auto-accepts).
3. Role change → power-level update via admin API.
4. Member removed → `kick` + room membership revoked; rooms persist (history matters) but the member's access is gone.

### 5.3 Why this is derived, not stored

The room list in the world-doc is `GET /_synapse/admin/v1/rooms` filtered by the group's space, rebuilt on every world-doc refresh. There is no second registry of channels. The Synapse DB is the store; the seat index points at it; the world-doc projects it. Same boundary rule as everything else (world-doc-and-contacts.md): projection, never truth.

## 6. Voting

### 6.1 Model

Votes are **Safe transactions with a UX layer**:

1. **Propose**: any `member` creates a proposal (JSON: title, options, quorum %, deadline, optional Safe transaction payload). Deterministic vote id: `H(groupId, nonce, proposerSub)`.
2. **Deliberate**: the governance Matrix room gets an announcement (auto-posted by coop-api); discussion happens in-thread.
3. **Vote**: members sign the proposal hash (EIP-1271 via their Safe — personal signature, not the group's). coop-api aggregates signatures in the seat index.
4. **Count**: when quorum% of the owner set has signed by deadline → the proposal passes → if it carries a Safe transaction payload, coop-api submits it (threshold met → executes; else the proposal is a resolution recorded on-chain as a signed statement).
5. **Record**: the outcome is a Safe-level record (the executed tx or the signed statement), and the world-doc's governance view shows it.

### 6.2 Vote types (first pass)

| Type | Payload | Execution |
|---|---|---|
| Resolution | none (statement) | recorded, no tx |
| Membership | add/remove owner | Safe transaction |
| Treasury | transfer / budget | treasury guard flow (private-treasury) |
| Settings | group config change | Safe transaction + app-layer reconfig |
| Channel | create/rename room | coop-api → Synapse admin API |

### 6.3 Privacy

Votes are visible to members by default (`visibility: members`). For sensitive votes, the seat visibility model (open/members/hidden) applies: hidden groups' votes are provable-but-not-enumerable (zk membership proof to show you voted, without revealing the tally). Same privacy tiering as contacts.

## 7. World-doc integration

The world-doc's group panel (world-doc-architecture.html) shows, per group seat:
- **Membership**: seat (alias, roles, joinedAt), the owner-set proof status
- **Governance**: open votes (with my vote state), past resolutions
- **Treasury view**: the treasury panel (proofs-not-balances for hidden tiers)
- **Communications**: the room list (from Synapse admin API) with join links (deep links into element.irl.coop)
- **Capability**: what I can do right now (propose? approve? moderate?) — derived from roles + pending items

## 8. API surface (coop-api, all behind the coop JWT)

```
GET    /api/v1/groups                      # my groups (seats)
GET    /api/v1/groups/:id                  # group detail (members, roles, channels)
POST   /api/v1/groups                      # (admin) create a group
POST   /api/v1/groups/:id/channels         # (admin) create a channel → Matrix room
GET    /api/v1/groups/:id/channels         # (member) room list (from Synapse)
POST   /api/v1/groups/:id/votes            # (member) propose
POST   /api/v1/groups/:id/votes/:vid       # (member) cast vote (EIP-1271 sig)
GET    /api/v1/groups/:id/votes/:vid       # (member) tally
POST   /api/v1/groups/:id/members/:sub/approve  # (inviter) approve pending seat
```

## 9. What already exists vs what's new

| Piece | Status |
|---|---|
| Safe deployment + CREATE2 (safe.ts) | ✅ exists |
| Passkey onboarding (onboarding.ts) | ✅ exists |
| coop_session + fleet OIDC | ✅ exists |
| Matrix stack (Synapse admin API reachable from host) | ✅ exists (media on MinIO, OIDC localpart from email) |
| Seat model + privacy tiers | 📐 designed (world-doc-and-contacts.md) |
| Group Safe (irl.coop) deployment | 🆕 |
| ensureGroupSeat / invite-on-first-signin | 🆕 |
| Role registry + capability checks | 🆕 |
| Matrix auto-provisioning (rooms, joins, power levels) | 🆕 |
| Voting (propose/sign/count/execute) | 🆕 |
| World-doc group panel | 🆕 |

## 10. Open decisions (Robbie)

1. **Group Safe threshold**: 1-of-1 dev (backend executes add-owner directly) vs 2-of-3 from day one (join requires a founder signature). Picks: 1-of-1 now, promote later — the promotion itself is the first group vote.
2. **Invite gate default**: `open` (any verified Google) vs `invite-list` (allowlist) vs `approval` (pending seats). Dev = open; the gate is a group setting.
3. **Matrix room history**: keep rooms after member removal (history matters) vs archive-on-exit. Recommend keep + kick.
4. **Vote quorum default**: simple majority of owners vs 50%+1 of *active* members (activity = signed in last 30d, from the seat index).
