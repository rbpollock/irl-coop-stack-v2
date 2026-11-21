
# Federation transition plan — from one node to many

**Status: planning · 2026-11-20 · comprehensive service-area analysis.**

This document maps every service area in the irl.coop stack, identifies what
changes for federation, and sequences the work. The goal: a Detroit node and a
Portland node can cooperate autonomously, with cryptographic trust, no shared
infrastructure, and no platform operator.

## Principle: the node stays the same; the mesh is new

Every service runs unchanged **inside** a node. Federation is added as a
**gateway layer** on top. This means:
- A single-node deployment works exactly as it does today.
- Federation is opt-in per group and per peer.
- Nodes that never federate pay zero complexity cost.

---

## Service area map

| # | Pillar | Service | Federation impact | Effort | Priority |
|---|--------|---------|-------------------|--------|----------|
| 1 | Identity | Keycloak | Realm-level OIDC brokering; Safe address as global ID | Medium | P0 |
| 2 | Identity | coop-api auth | JWT claims carry Safe address; verify foreign attestations | Medium | P0 |
| 3 | Data | Citus/Postgres | Per-node database; pglogical cross-node sync | High | P0 |
| 4 | Data | coop-api RLS | Foreign data table; cross-group query union | Medium | P0 |
| 5 | Bus | Event bus | Federation gateway transport; DHT discovery | High | P0 |
| 6 | Bus | Pathways | HandoffEnvelope as cross-node message format | Low | P0 |
| 7 | Edge | Traefik | Inter-node TLS via Safe signatures, not DNS certs | Medium | P1 |
| 8 | Chat | Matrix/Synapse | Already federates via Matrix protocol | Low | P1 |
| 9 | On-chain | Safe/Registry | Same design — already multi-group | None | — |
| 10 | Storage | MinIO | Content-addressed bucket replication | Medium | P1 |
| 11 | Apps | NocoDB/Plane | Per-group base/workspace scoping | Low | P2 |
| 12 | Mail | Stalwart | Cross-domain mail routing | Medium | P2 |
| 13 | Workflow | Temporal | Cross-node workflow delegation | High | P2 |
| 14 | Telephony | Telnyx | Cross-group DID routing | Medium | P3 |
| 15 | AI | RAG/Inference | Per-node model serving; federated knowledge graph | High | P3 |

---

## Phase 0: Foundation (now — single node, federation-ready)

### 0.1 Identity: Safe address in every JWT

**Current state:** coop-api JWTs carry `sub` (Keycloak subject) and `email`.

**Change:** Extend the JWT claim set to include `safe_address`:

```json
{
  "sub": "abc-123",
  "email": "alice@detroit.coop",
  "safe_address": "0xA1ic3...",
  "groups": ["detroit-soil", "federated:portland-water"]
}
```

The `safe_address` is derived at onboarding and never changes. It becomes the
**global identifier** for Alice across all nodes.

**Work:**
- Update `apps/coop-api/src/auth.ts` `mintCoopJwt` to include `safe_address`
- Update `apps/web/irl-dashboard/src/configs/next-auth.ts` to read it
- Update `coop_rls.sql` `coop_current_sub()` to also expose `coop_current_safe()`

**Effort:** 2 days.

### 0.2 Data: `foreign_data` table

**Current state:** All data is local. RLS policies enforce `group_id = coop_current_group()`.

**Change:** Add a `foreign_data` table that mirrors the shape of local tables
but stores attested replicas from peer nodes:

```sql
CREATE TABLE foreign_data (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_node   text NOT NULL,      -- "detroit.node-47.irl.coop"
  source_group  text NOT NULL,      -- "detroit-soil"
  table_name    text NOT NULL,      -- "soil_survey"
  record_id     text NOT NULL,      -- primary key of the source record
  payload       jsonb NOT NULL,
  attestation   bytea NOT NULL,     -- EIP-1271 Safe signature
  received_at   timestamptz DEFAULT now(),
  UNIQUE (source_node, table_name, record_id)
);

-- RLS: members can see foreign_data from groups their node has federated with
CREATE POLICY foreign_data_read ON foreign_data
FOR SELECT USING (
  source_group IN (
    SELECT foreign_group_id FROM group_federations
    WHERE home_group_id = coop_current_group()
  )
);
```

**Work:**
- Migration in `coop_rls.sql`
- coop-api GraphQL resolver that unions local + foreign_data
- Admin UI for "manage federations"

**Effort:** 1 week.

### 0.3 Bus: event schema marks `federate: true`

**Current state:** The five-axis event bus is intra-node. All consumers are local.

**Change:** Add a `federate` boolean field to the event schema. Events marked
`federate: true` are candidates for cross-node replication:

```typescript
// apps/coop-api/src/events.ts
interface CoopEvent {
  id: string;
  type: 'need' | 'offer' | 'membership' | 'safe_event' | 'matrix_msg' | 'external';
  payload: Record<string, unknown>;
  federate: boolean;  // NEW
  source_node?: string; // NEW: set by federation gateway on receipt
}
```

Default `federate: false`. Explicit opt-in per event type.

**Work:**
- Add column `federate` to `events` table
- Update event publishers to set the flag
- Gate the federation gateway on this flag

**Effort:** 3 days.

---

## Phase 1: Node-to-node trust (1 month)

### 1.1 Keycloak: realm brokering

**What:** Portland's Keycloak adds Detroit's Keycloak as an Identity Provider.

**How:** Keycloak's built-in `keycloak-oidc` broker provider:

```yaml
# Portland's keycloak.yaml
federation:
  - alias: detroit-coop
    providerId: keycloak-oidc
    enabled: true
    config:
      authorizationUrl: https://auth.detroit.coop/realms/irl-co-op/protocol/openid-connect/auth
      tokenUrl: https://auth.detroit.coop/realms/irl-co-op/protocol/openid-connect/token
      jwksUrl: https://auth.detroit.coop/realms/irl-co-op/protocol/openid-connect/certs
      clientId: portland-federation-client
      clientSecret: ${SECRET:keycloak.federation.detroit}
      syncMode: IMPORT
      trustEmail: true
```

**Bootstrap automation:**
- Extend `bootstrap-keycloak.py` to read a `federation:` stanza from
  `apps/keycloak.yaml` and create the IdP config via admin API.
- The `clientSecret` is derived from `master.key` same as any other secret.

**User flow:**
1. Alice goes to `plane.portland.coop`.
2. Clicks "Sign in with Detroit Co-op."
3. Redirected to Detroit Keycloak, signs in.
4. Redirected back to Portland with federated session.
5. Portland Keycloak auto-creates a shadow user linked to Detroit's `sub`.
6. coop-api sees the session, reads Alice's Safe address from the token.

**Work:**
- Add `federation:` stanza to `apps/keycloak.yaml` schema
- Extend `bootstrap-keycloak.py` with IdP creation
- Dashboard sign-in UI shows broker list dynamically

**Effort:** 1 week.

### 1.2 On-chain: `group_federations` registry

**What:** A table + on-chain anchor that records "Group A trusts Group B."

**Off-chain (Citus):**

```sql
CREATE TABLE group_federations (
  home_group_id      uuid REFERENCES groups(id),
  foreign_group_id   uuid REFERENCES groups(id),
  foreign_node       text NOT NULL,  -- Tailscale IP or hostname
  foreign_safe       text NOT NULL,  -- 0x... address
  trust_level        text CHECK (trust_level IN ('A1','A2','A3')),
  data_scopes        text[],          -- ['soil_survey', 'events']
  established_at     timestamptz DEFAULT now(),
  revoked_at         timestamptz,
  PRIMARY KEY (home_group_id, foreign_group_id)
);
```

**On-chain (CoopRegistry.sol):**

```solidity
struct FederationLink {
    bytes20 homeGroup;
    bytes20 foreignGroup;
    bytes32 foreignNodeHash;  // hash of node hostname
    bytes32 foreignSafe;      // truncated Safe address
    uint8 trustLevel;         // 1=A1, 2=A2, 3=A3
    uint256 establishedAt;
    bool revoked;
}
mapping(bytes32 => FederationLink) public federationLinks;
// key = keccak256(homeGroup ++ foreignGroup)
```

**Why both?** The on-chain record is the **source of truth** for trust level and
Safe address. The off-chain table caches it for fast queries. If they diverge,
the on-chain version wins.

**Establishment flow (Pathways run at A3):**
1. Detroit proposes: "Federate with Portland, trust level A2, scopes: soil_survey."
2. Detroit Safe votes. On execution, `CoopRegistry` records the link.
3. Portland sees the on-chain event (via Base indexer) and mirrors the row.
4. Both nodes' coop-api update `group_federations`.

**Work:**
- Add `FederationLink` struct and `proposeFederation` to `CoopRegistry.sol`
- Add `group_federations` table to `coop_rls.sql`
- Add indexer handler in `coop-api/src/on-chain.ts`

**Effort:** 2 weeks.

### 1.3 coop-api: verify foreign attestations

**What:** When a federated user accesses Portland's API, Portland verifies their
membership proof from Detroit.

**Current state:** `keycloak-admin.ts` fetches user profile from Keycloak.

**New behavior:**

```typescript
// apps/coop-api/src/federation.ts
export async function verifyForeignMembership(
  safeAddress: string,
  foreignGroup: string,
  foreignNode: string
): Promise<boolean> {
  // 1. Check local cache
  const cached = await db.query(
    "SELECT * FROM group_federations WHERE foreign_group_id = $1",
    [foreignGroup]
  );
  if (!cached.rows.length) return false;

  // 2. Fetch attestation from foreign node (or local cache)
  const attestation = await fetchAttestation(foreignNode, safeAddress, foreignGroup);

  // 3. Verify EIP-1271 signature
  const valid = await verifySafeSignature(
    attestation.payload,
    attestation.signature,
    cached.rows[0].foreign_safe
  );

  return valid && !attestation.revoked;
}
```

**Work:**
- New `federation.ts` module
- Extend `coop_rls.sql` policies to accept foreign subs
- Cache attestation results with TTL (don't verify on every query)

**Effort:** 1 week.

---

## Phase 2: Data sync (2 months)

### 2.1 pglogical per-group publications

**What:** Each node publishes logical replication slots scoped to its groups.
Peer nodes subscribe to the slots they are federated with.

**On Detroit's Postgres:**

```sql
-- One publication per group (or one per federated group pair)
CREATE PUBLICATION detroit_soil_pub FOR TABLE soil_survey, events, decisions
WHERE (group_id = 'detroit-soil');

-- A replication slot for each subscriber
SELECT pg_create_logical_replication_slot('portland_sub', 'pgoutput');
```

**On Portland's Postgres:**

```sql
CREATE SUBSCRIPTION detroit_soil_sub
CONNECTION 'host=100.64.x.x port=5432 user=federation password=... dbname=irlcoop'
PUBLICATION detroit_soil_pub
WITH (copy_data = false, create_slot = false, slot_name = 'portland_sub');

-- Replicated data lands in foreign_data table, not local tables
```

**The connection string:** Uses Tailscale IP, not public DNS. Authentication via
a dedicated `federation` Postgres role with minimal permissions (read-only on
publications).

**Revocation:**
```sql
-- Detroit revokes Portland
DROP SUBSCRIPTION portland_sub;
-- or
ALTER PUBLICATION detroit_soil_pub DROP TABLE soil_survey;
```

**Work:**
- Add `federation` Postgres role to `coop_rls.sql`
- Automation: when a `group_federations` row is created, create the pub/sub pair
- When revoked, drop the subscription and replication slot

**Effort:** 2 weeks.

### 2.2 Electric SQL for edge clients

**What:** Field workers on phones sync via Electric proxy, not direct Postgres.

**Architecture:**

```
Postgres (node)  →  Electric proxy  →  Shape log  →  PGLite/SQLite (phone)
                          ↑
                     Port 6543 on node
                     Exposed only to Tailnet
```

**Why Electric instead of pglogical for phones:**
- pglogical requires a persistent TCP connection — phones go offline.
- Electric handles offline/online sync with a local SQLite cache.
- Shapes mean the phone only downloads what the field worker needs.

**Security:** Electric proxy is exposed on a Tailnet-only port. No public access.
Authentication uses the same coop JWT as the rest of the stack.

**Work:**
- Deploy Electric proxy on each node (Docker container)
- Define shapes per app (soil_survey shape, event shape, etc.)
- Mobile app uses Electric client library

**Effort:** 3 weeks (new component).

### 2.3 CRDT types for conflict-free tables

**What:** Some tables (counters, presence, simple kv) can use CRDT semantics
instead of last-write-wins.

**Custom Postgres types:**

```sql
CREATE TYPE coop_lww_register AS (
  value text,
  timestamp bigint,  -- Lamport or HLC
  node_id text
);

CREATE FUNCTION coop_lww_merge(a coop_lww_register, b coop_lww_register)
RETURNS coop_lww_register AS $$
BEGIN
  IF a.timestamp > b.timestamp THEN RETURN a; END IF;
  IF b.timestamp > a.timestamp THEN RETURN b; END IF;
  IF a.node_id > b.node_id THEN RETURN a; ELSE RETURN b; END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**Usage:**
```sql
CREATE TABLE presence (
  user_id text PRIMARY KEY,
  status coop_lww_register
);

-- On sync, apply merge instead of overwrite
UPDATE presence SET status = coop_lww_merge(status, incoming.status)
WHERE user_id = incoming.user_id;
```

**Tables that benefit:**
- `presence` (online/offline status)
- `group_settings` (name, avatar, description)
- `knowledge_graph` (counters on node references)

**Tables that do NOT benefit (must stay ordered):**
- Financial ledgers (strict sequence)
- Decisions/votes (temporal ordering)
- Event log (append-only)

**Work:**
- Define CRDT types in `coop_rls.sql`
- Update pglogical conflict triggers to use `coop_lww_merge`
- Document which tables are CRDT-safe

**Effort:** 1 week.

---

## Phase 3: Cross-node workflows (3 months)

### 3.1 Event bus federation gateway

**What:** A new transport on the event bus that sends `federate: true` events
to peer nodes and receives events from them.

**Components:**

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Local bus      │     │ Federation GW   │     │  Peer nodes     │
│  (Redis pubsub) │◄───►│  (new service)  │◄───►│  (Tailscale)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
    ↑                        ↑
    │                        │
    consumers             DHT discovery
```

**The gateway:**
- Subscribes to `events WHERE federate = true`
- Looks up recipient nodes via DHT (by `foreign_node` in `group_federations`)
- Packages event into `HandoffEnvelope` with Safe signature
- Sends via HTTP/2 or QUIC over Tailscale
- On receipt, verifies signature, publishes to local bus

**Envelope format:**

```json
{
  "handoff_type": "event_bus_sync",
  "source_node": "detroit.node-47.irl.coop",
  "source_group": "detroit-soil",
  "events": [
    {
      "id": "evt_abc",
      "type": "need",
      "payload": { ... },
      "timestamp": "2026-11-20T20:00:00Z"
    }
  ],
  "safe_signature": "0x...",
  "seq_num": 1847
}
```

**Work:**
- New `federation-gateway` service (Rust or Go for performance)
- DHT discovery (extend Tailscale API or use libp2p)
- Message queue for store-and-forward (offline peers)

**Effort:** 4 weeks (the biggest piece of new code).

### 3.2 Temporal: cross-node workflow delegation

**What:** A workflow started on Detroit can hand off a task to Portland, then
resume when Portland completes it.

**Current state:** Temporal workflows are local to the node's Temporal cluster.

**Federated workflow:**

```typescript
// A Pathways run implemented as a Temporal workflow
workflow = {
  name: 'cross_group_grant_application',
  steps: [
    { node: 'detroit', task: 'draft_proposal', autonomy: 'A2' },
    { node: 'portland', task: 'review_and_cosign', autonomy: 'A3' },
    { node: 'detroit', task: 'submit_to_funder', autonomy: 'A2' }
  ]
}
```

**Implementation:**
- Detroit's Temporal workflow sends a `HandoffEnvelope` to Portland via the
  federation gateway.
- Portland receives it, starts its own Temporal child workflow.
- On completion, Portland sends a result envelope back.
- Detroit's workflow resumes.

**Work:**
- Custom Temporal activity that calls the federation gateway
- Idempotency: each handoff envelope has a unique run ID; duplicate deliveries
  are detected and deduplicated

**Effort:** 2 weeks.

### 3.3 MinIO: content-addressed federation

**What:** Large blobs (images, PDFs, video) are referenced by hash, not URL.
Nodes replicate blobs on-demand or eagerly based on federation scopes.

**Current state:** MinIO holds blobs in buckets (`docs`, `stalwart`, `matrix-media`).

**Federated state:**
- Each blob is addressed by `sha256` in a global content-addressed namespace.
- Node A asks Node B: "Do you have `sha256:abc...`?"
- If yes, Node B streams it. If no, Node B asks its federated peers.
- This is exactly IPFS's model, but scoped to the federation graph (not the
  public IPFS DHT).

**Shortcuts:**
- Use MinIO's bucket replication with filtering by prefix (group-scoped prefixes).
- For ad-hoc sharing, use the event bus to send a `blob_request` event; the
  peer node streams the blob over HTTPS.

**Work:**
- MinIO bucket replication rules per federation link
- Event type `blob_request` / `blob_offer` on the bus
- Content hash verification on receipt

**Effort:** 1 week.

---

## Phase 4: App-layer federation (4+ months)

### 4.1 NocoDB: per-group bases with cross-group views

**Current state:** NocoDB has one base per group. No cross-group visibility.

**Federated state:** A "federated view" is a NocoDB view that UNIONs local data
with `foreign_data` rows for the same table schema. The RLS policy enforces
that only federated groups' data appears.

**Work:**
- NocoDB extension or middleware that constructs federated views
- schema registry: ensure Detroit and Portland use the same column names/types

**Effort:** 2 weeks.

### 4.2 Plane: cross-group project collaboration

**Current state:** Plane has workspaces. One workspace = one group.

**Federated state:** A "federated workspace" invites members from other groups
by Safe address. Plane's existing OIDC integration reads the `groups` claim from
the coop JWT; extending it to read `federated_groups` is a config change.

**Work:**
- Extend Plane's OIDC group mapping to include federated groups
- Add `federated_members` table (invited by Safe address, not email)

**Effort:** 1 week.

### 4.3 Stalwart: cross-domain mail routing

**Current state:** Stalwart serves one domain: `irl.coop`.

**Federated state:** A Detroit member can email a Portland member at
`alice@detroit.irl.coop` → `bob@portland.irl.coop`. Stalwart already supports
multiple domains; federated routing means the MX record points to the right node.

**Work:**
- Dynamic MX resolution: lookup `bob@portland.irl.coop` → Portland node's IP
- Stalwart config per domain, federated via the event bus

**Effort:** 2 weeks.

### 4.4 Telephony: cross-group DID routing

**Current state:** Each group has a Telnyx DID. Calls are internal to the group.

**Federated state:** A Detroit member calls Portland's group number. The call
routes through Telnyx to Portland's FreeSWITCH node.

**Work:**
- DID federation registry (which group owns which DID)
- SIP trunking between nodes over Tailnet
- Call forwarding rules in FreeSWITCH config

**Effort:** 3 weeks.

---

## Cross-cutting concerns

### Security: the four trust boundaries

| Boundary | Mechanism | Verified by |
|---|---|---|
| **Node software** | Reproducible builds + Safe-attested releases | `global-node-architecture.md` §Code integrity |
| **Node identity** | Safe address via DHT discovery | Handshake attestation |
| **Group membership** | Safe-signed attestation | On-chain `CoopRegistry` + coop-api verifier |
| **Data integrity** | SHA-256 content hashes + AEAD encryption | Client-side verify on receipt |

### Operations: what an operator needs to know

A node operator (someone running a server for their group) needs to:
1. Run the standard bring-up (`infrastructure-bringup.md`)
2. Join the Tailnet
3. Set their node's Safe address in config
4. Optionally propose federation links via the dashboard

They do NOT need to:
- Configure Keycloak brokering manually (it's automated)
- Set up pglogical subscriptions manually (automated by `group_federations` changes)
- Manage certificates for peer connections (Tailscale handles WireGuard)
- Run a blockchain node (they use the public Base RPC)

### Economics: who pays for what

| Cost | Who pays | Mitigation |
|---|---|---|
| Node hosting | The group running the node | Low-end VPS (~$20/mo), Raspberry Pi for small groups, donated infrastructure for mutual-aid networks |
| On-chain gas (Base) | The group proposing federation links, blessings, etc. | Batch operations, L2 is cheap (~$0.01/tx), subsidized by irl.coop steward for pilot |
| Cross-node bandwidth | Both nodes (symmetric) | Data is only synced if explicitly federated; shapes filter to need-to-know |
| Electric proxy (if used) | Same node | One proxy per node, negligible CPU for small groups |

---

## Summary: what changes, what doesn't

| Does NOT change | Changes |
|---|---|
| The node bringup script | Adds federation automation on top |
| Keycloak's core code | Adds broker providers via config |
| coop-api's core routes | Adds `federation.ts` middleware |
| Citus/Postgres code | Adds `foreign_data` table + CRDT types |
| Event bus schema | Adds `federate` flag + federation gateway |
| Matrix/Synapse | Already federates — no change |
| Safe contracts | Already multi-group — no change |
| Traefik core | May add inter-node routing rules |
| NocoDB/Plane/Stalwart | Config changes for federated views/members |
| RAG/AI | Per-node serving; federated knowledge graph later |

The principle holds: the node stays the same. The mesh is new code that runs
alongside it.
