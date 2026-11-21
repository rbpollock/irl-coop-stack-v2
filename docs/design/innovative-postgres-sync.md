
# Innovative approaches to global Postgres-compatible synchronization

**Status: research · 2026-11-20.**

This document surveys real tools and research for synchronizing Postgres across
globally distributed nodes — not just "logical replication," but approaches that
handle conflict, offline operation, and grassroots deployment.

## The taxonomy

| Approach | What it is | Postgres-native? | Conflict resolution |
|---|---|---|---|
| **CockroachDB / YugabyteDB** | Distributed SQL built from scratch, wire-protocol compatible with Postgres | Wire-protocol | Raft consensus — no conflicts (single-leader per range) |
| **Electric SQL** | Postgres → local SQLite/PGLite sync via a log-shaping middleware | Yes (middleware on top) | CRDT-like: updates are additive, deletes are soft |
| **PowerSync** | Sync service between Postgres and local SQLite (mobile apps) | Yes (sync service) | Last-write-wins + custom conflict rules |
| **pglogical + custom resolver** | Postgres native logical replication with hook-based conflict handling | Native extension | Pluggable: you write the resolver in SQL/PL/pgSQL |
| **BDR (EDB)** | Enterprise multi-master Postgres | Native extension (commercial) | Automatic + configurable conflict detection |
| **AntidoteDB** | CRDT database (not Postgres, but the seminal research) | No (Erlang/Elixir) | Full CRDTs: all merges converge, no locks |
| **PGLite (WASM Postgres)** | Postgres compiled to WebAssembly, runs in browser | Yes (same code, different target) | None — it is a single-node replica |

## 1. CockroachDB / YugabyteDB — the Google Spanner approach

**The model:** Sharded tables with Raft consensus per shard. Every write goes to
the shard leader (which may be geo-located for latency). Reads can go to followers.

**Why it works for global:** You get serializable isolation across continents.
A transaction touching rows in shard A and shard B is two-phase committed.

**Why it is NOT grassroots-friendly:**
- Requires a minimum of 3-5 nodes for Raft quorum. A single node cannot operate.
- Writes to a shard whose leader is in another continent pay RTT latency.
- Operational complexity: node bootstrapping, rebalancing, certificate management.
- Not actually Postgres: Cockroach uses the Postgres wire protocol but its own
storage engine (Pebble), query planner, and extensions.

**Verdict:** Enterprise-scale, not cooperative-scale. You need an SRE team.

## 2. Electric SQL — the local-first middleware

**The model:** A thin proxy sits in front of Postgres. It translates row changes
into a "shape log" — a filtered, permission-scoped stream of operations. Client
applications (browser, mobile, edge device) connect via WebSocket and receive
only the shapes they are allowed to see.

```
Postgres  →  Electric proxy  →  Shape log  →  SQLite/PGLite on client
                ↑                                  ↓
                └────── writes back (optimistic) ──┘
```

**Why it is innovative:**
- Clients work **offline** — SQLite is local, sync is async.
- The "shape" abstraction means clients do not download the whole database.
  A field worker gets only the surveys for their group, not the whole network.
- Conflict resolution is **implicit** — Electric uses a causal+ consistency model
  and structural CRDTs for its internal log. Application-level conflicts are
  exposed to the developer, not magically resolved.

**Why it fits irl.coop:**
- A node IS the Postgres server. Other nodes are "clients" that subscribe to
  relevant shapes. No shared coordinator.
- The shape log can be relayed peer-to-peer: Node A subscribes to Node B's
  "soil-survey" shape via a federation gateway.
- PGLite (WASM Postgres) means a phone or Raspberry Pi can run a full
  Postgres-compatible engine locally.

**The gap:** Electric SQL currently focuses on client/server (one central Postgres,
many edge clients). Extending it to **peer-to-peer** — Node A's Electric proxy
subscribing to Node B's Electric proxy — is the innovation that would make it a
federation transport.

**URL:** https://electric-sql.com

## 3. pglogical + custom conflict resolution — the Postgres-native path

**The model:** Postgres 10+ ships with native logical replication. `pglogical` (and
its successor `pgoutput`) streams WAL changes from a publisher to subscribers.

By default, conflicts are fatal: subscriber stops, human intervention required.
But you can install a **conflict trigger** that fires instead:

```sql
-- On the subscriber
CREATE OR REPLACE FUNCTION resolve_conflict()
RETURNS TRIGGER AS $$
BEGIN
  -- Custom rule: if the incoming row has a higher " Lamport timestamp",
  -- overwrite. Otherwise, keep local.
  IF NEW.lamport > OLD.lamport THEN
    RETURN NEW;  -- accept incoming
  ELSE
    RETURN OLD;  -- reject incoming, keep local
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER conflict_resolution
BEFORE INSERT OR UPDATE ON soil_survey
FOR EACH ROW
WHEN (pg_trigger_depth() = 0)
EXECUTE FUNCTION resolve_conflict();
```

**Why it is innovative:** It is pure Postgres. No middleware, no new database,
no wire-protocol compatibility layer. Just triggers and replication slots.

**Why it fits irl.coop:**
- Every node is a Postgres publisher AND subscriber.
- Node A publishes its `group_id = 'detroit-soil'` partition.
- Node B subscribes to that publication.
- The conflict trigger implements the group's consensus rules (e.g.
  Safe-signed updates win over unsigned ones).

**The gap:** Logical replication is **asymmetric** — one publisher, one or more
subscribers. True multi-master (node A and node B both write the same table)
requires **BDR** (see below) or careful application-level partitioning (each node
owns a `group_id` slice).

## 4. BDR (Bi-Directional Replication) — enterprise multi-master

**The model:** EDB's commercial extension turns Postgres into a true multi-master
cluster. Every node accepts writes. Conflicts are detected and resolved automatically
or via user-defined rules.

**Why it works:** True multi-master means any node can write any row. Geographic
latency is hidden by asynchronous replication (eventual consistency) or mitigated
by CRDT-like merge functions.

**Why it is NOT grassroots-friendly:**
- Commercial license from EDB. Not open source.
- Operational complexity comparable to CockroachDB.
- Not designed for "nodes that come and go" — it assumes a stable cluster.

**Verdict:** Enterprise-only. Not for a cooperative federation.

## 5. AntidoteDB — the CRDT research baseline

**The model:** Not Postgres at all. An Erlang database where every data type is a
CRDT (counters, sets, maps, registers). Writes never conflict because all types
have mathematically-defined merge functions.

**Why it matters:** It proves that **global consistency without locks is possible**.
The trade-off is that not all SQL operations map to CRDTs (e.g. arbitrary
`UPDATE ... SET x = x + 1` is not a CRDT unless `x` is a counter type).

**Research extension to Postgres:** Could Postgres rows be tagged with CRDT
semantics? `lamport_counter` type, `merge_set` type, `lww_register` type? Then
multi-master replication becomes "apply the CRDT merge function" instead of
"last write wins." This is an active research area.

## 6. The novel hybrid: Citus + pglogical + CRDT triggers + Electric proxy

None of the above is perfect for irl.coop. Here is a synthesis that might be:

### Layer 0: Postgres with CRDT-aware types

Extend `coop_rls.sql` with CRDT primitives:

```sql
CREATE TYPE coop_lww AS (
  value text,
  timestamp bigint,
  node_id text
);

CREATE FUNCTION coop_lww_merge(a coop_lww, b coop_lww)
RETURNS coop_lww AS $$
BEGIN
  IF a.timestamp > b.timestamp THEN RETURN a; END IF;
  IF b.timestamp > a.timestamp THEN RETURN b; END IF;
  -- Tie-break by node_id lexical order for determinism
  IF a.node_id > b.node_id THEN RETURN a; ELSE RETURN b; END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

Tables that need cross-node sync use these types instead of plain `text`/`int`.

### Layer 1: pglogical per-group publication

Each node publishes one logical replication slot per group:

```sql
-- On Detroit's Postgres
CREATE PUBLICATION detroit_soil FOR TABLE soil_survey
WHERE (group_id = 'detroit-soil');
```

Portland subscribes:

```sql
-- On Portland's Postgres
CREATE SUBSCRIPTION detroit_soil_sub
CONNECTION 'host=detroit.node-47 port=5432 user=frepl password=...'
PUBLICATION detroit_soil;
```

The subscription only receives rows for `group_id = 'detroit-soil'`.
Citus on Portland stores these in a `foreign_data` shard.

### Layer 2: Electric proxy for shape-based sync

Instead of raw replication slots, an Electric proxy on each node exposes
"shapes":

```json
{
  "shape": "soil_survey",
  "where": "group_id = 'detroit-soil'",
  "columns": ["survey_id", "data", "updated_at"]
}
```

Remote nodes subscribe to shapes, not tables. The proxy handles filtering,
permission checks ("is Portland allowed to see Detroit's soil surveys?"), and
format translation.

### Layer 3: Safe-signed writes

Before a node applies a replicated row, it verifies the row carries a valid
EIP-1271 signature from the source group's Safe. The conflict trigger checks:

```sql
IF NOT verify_safe_signature(NEW.data, NEW.signature, NEW.source_group_safe)
THEN
  RAISE EXCEPTION 'Invalid signature on foreign data';
END IF;
```

This means: **even if the replication stream is compromised, the data is only
accepted if the group authorized it.**

## Honest comparison

| Approach | Complexity | Grassroots? | Offline? | Conflict free? | Maturity |
|---|---|---|---|---|---|
| CockroachDB | High | No | No | Yes (consensus) | Production |
| Electric SQL | Medium | **Yes** | **Yes** | Partial | Beta |
| pglogical + triggers | Medium | **Yes** | No | No (hand-coded) | Production |
| BDR | High | No | No | Configurable | Commercial |
| AntidoteDB | Low | **Yes** | **Yes** | **Yes** (full CRDT) | Research |
| **Hybrid (proposed)** | Medium-High | **Yes** | **Yes** | Partial | Design only |

## Recommendation for irl.coop

**Phase 1 (now):** Use `pglogical` for node-to-node replication of specific group
data, with RLS-filtered publications. This is native Postgres, no new software,
works today.

**Phase 2 (next):** Add Electric SQL as an optional transport for edge clients
(phones, Raspberry Pi nodes). The shape abstraction maps perfectly to
"only sync what this member may see."

**Phase 3 (later):** Research CRDT-typed columns in Postgres. If a counter,
set, or LWW register can be a native Postgres type with a merge function, then
multi-master sync becomes "apply the merge" instead of "resolve the conflict."

**What to avoid:** CockroachDB and BDR. They are excellent software, but they
turn a cooperative federation into an enterprise deployment. A Detroit urban farm
co-op cannot run a 5-node Raft cluster. They can run one Postgres + one Electric
proxy.
