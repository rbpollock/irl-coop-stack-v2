
# Global node architecture — from one server to thousands

**Status: design exploration · 2026-11-20.**

This document answers: **what changes when "irl.coop" is not one server, but ten
thousand nodes across every continent?**

The short answer: **almost nothing inside the node; everything in the
federation layer.** The `infrastructure-bringup.md` stack — Keycloak, Citus,
Traefik, coop-api, event bus — is a **node**. A global network is nodes talking
to each other. The node software stays the same; the interconnection protocol is
new.

## The mental model: Mastodon, not Slack

| | Slack | Mastodon | irl.coop (proposal) |
|---|---|---|---|
| **Unit** | One platform | One instance (server) | One **node** (`irl-coop-stack-v2`) |
| **Identity** | Slack account | `@user@instance.social` | **Safe address** (`0x...`) |
| **Trust** | Slack Inc. | Instance admin + federation | **Safe signature** (on-chain or off) |
| **Discovery** | Central directory | ActivityPub gossip | **DHT / gossip by Safe address** |
| **Messages** | Slack API | ActivityPub inbox/outbox | **Event bus + Pathways HandoffEnvelope** |
| **Data** | Slack's DB | Instance's DB | **Node's Citus** (local to group) |
| **Cross-instance** | N/A (one instance) | Follows, replies, boosts | **Pathway runs, resource shares, seat transfers** |

The key decision: **irl.coop is not a platform that hosts groups. It is
software that groups run to host themselves, with a federation protocol for
cross-group cooperation.**

## What stays the same (the node)

Every node in the global network runs the exact same stack from
`infrastructure-bringup.md`:

- **Keycloak** — one realm per node (e.g. `irl-co-op`). Brokers Google, passkeys,
  and other nodes' Keycloaks. NOT one realm per group — one realm per **node**.
- **Citus** — one coordinator per node. Holds data for the groups that choose
  this node as their primary. NOT a global database — a **local** database.
- **coop-api** — serves the groups on this node. RLS scopes by group_id. The
  same code, the same tables, the same auth.
- **Event bus** — pub/sub internal to the node. Extended with a "federation
  gateway" transport for cross-node messages.
- **Traefik** — edge proxy for this node's hostnames.
- **Tailscale** — mesh network. Every node joins the same tailnet (or a
  federation of tailnets). Nodes discover each other via Tailscale's
  coordination server, not DNS.

## What changes (the federation layer)

### 1. Identity: Safe address as the global namespace

Inside a node, Alice's identity is her Keycloak `sub`. Globally, Alice's
identity is her **Safe address** — the deterministic EVM address derived from
her passkey or seed phrase. The Safe address is:

- **Self-custodied** — no server can revoke it.
- **Portable** — works on any chain, any node, any app that speaks EIP-1271.
- **Persistent** — survives node migration, key rotation, group changes.

Keycloak's role shrinks: it is the **local session broker**, not the global
identity authority. When Alice signs into `node-47.irl.coop`, Keycloak issues a
local session. The session carries her Safe address as the canonical claim.

**Implication**: `coop-api` JWTs already carry `sub` — extend the claim to
include `safe_address`. Every API call is scoped to both the local Keycloak
sub AND the global Safe address.

### 2. Discovery: DHT by Safe address, not DNS

At global scale, DNS is the wrong tool:
- DNS is hierarchical (ICANN-controlled).
- DNS records stale when nodes migrate.
- DNS exposes topology to passive observers.

**Better**: A content-addressed DHT where the key is `hash(safe_address)` and
the value is the node's Tailscale IP + public key.

```
Alice wants to message Bob.
Alice knows Bob's Safe address: 0xB0b...
Alice queries the DHT: "who hosts 0xB0b?"
DHT returns: {"tailscale_ip": "100.64.x.x", "node_pubkey": "...", "last_seen": "..."}
Alice opens a Tailscale direct connection to that node.
```

**The DHT is NOT a blockchain.** It is a Kademlia-like overlay maintained by
the nodes themselves, gossiped via the event bus. Nodes publish their own
records; peers replicate them with TTL. The only trust requirement is that a
node cannot publish a record for a Safe address it does not control — verified
by requiring the DHT record to carry an EIP-1271 signature from the Safe.

**Tailscale already does this.** The Tailscale coordination server IS a DHT
for machine identities (WireGuard public keys → IPs). Extending it to group /
Safe-address discovery is a natural next step — or use the existing Tailscale
API to query "which node advertises this Safe address?"

### 3. Trust: Safe signatures, not server certificates

When `node-A` receives a message claiming to be from `node-B`, how does it know?

**Not TLS certificates.** TLS anchors to DNS names, which are censorable and
centralized.

**Not a blockchain transaction per message.** Too slow, too expensive.

**Instead: every cross-node message carries an EIP-1271 signature from the
sender's Safe.** The signature covers:
- The message hash
- The recipient Safe address
- A timestamp (anti-replay)
- A sequence number (ordering within a stream)

```python
signature = safe.sign_message(
    keccak256(message_body + recipient_safe + timestamp + seq_num)
)
```

The receiving node verifies:
1. Signature is valid for the claimed sender Safe.
2. Timestamp is within a window (±5 minutes).
3. Sequence number is greater than the last seen from this sender.

This is **session-layer cryptography**, not transport-layer. The underlying
connection can be TCP over Tailscale, QUIC over Tor, or carrier pigeon — the
signature is what matters.

### 4. Data: local-first, sync-on-demand

**No global database.** No shared Citus cluster. NoSQL or blockchain state for
group data.

Each node's Citus holds data for the groups that **chose** that node. A group
can have one primary node (for writes) and any number of replica nodes (for
reads), synchronized via:

- **Logical replication** (Postgres native) for real-time sync.
- **Pathway runs** for batch transfers (e.g. "share last month's survey data").
- **On-chain anchors** for trust, not data storage.

**Cross-group access** does not query a remote Citus shard. It queries a
**local replica** that the foreign group chose to share, or it receives a
**Pathways HandoffEnvelope** carrying the data directly.

Example: Detroit shares a soil survey with Portland.

1. Detroit's coop-api writes the survey to Detroit's Citus.
2. Detroit's node initiates a "data share" pathway run.
3. The pathway produces a `HandoffEnvelope` with the survey data (or a pointer
to a MinIO object), signed by Detroit's Safe.
4. Detroit's federation gateway sends the envelope to Portland's node (discovered
via DHT).
5. Portland's node verifies the Safe signature, stores the envelope in a
`foreign_data` table, and makes it available to Portland members via RLS.

**No SQL federation. No cross-shard joins. Just signed messages and local
tables.**

### 5. The event bus extended with a federation transport

The existing event bus (five-axis: needs/offers, membership, Safe events, Matrix
messages, provider callbacks) is intra-node. Add a **federation transport**:

```
┌─────────────────┐     ┌─────────────────┐
│   Node A bus    │◄───►│ Federation GW   │◄──► Tailscale mesh
│  (five-axis)    │     │ (new component) │
└─────────────────┘     └─────────────────┘
                               ▲
                               │ DHT discovery
                               │ Safe-signed envelopes
                               │ HandoffBus (Pathways)
```

The federation gateway:
- **Subscribes** to local bus events marked `federate: true`.
- **Looks up** the recipient node via DHT / Tailscale.
- **Packages** the event into a `HandoffEnvelope` with Safe signature.
- **Transmits** via the best available route (direct Tailscale, relay, or
asynchronous store-and-forward via IPFS / pinned CID).
- **Receives** envelopes from peer nodes, verifies signatures, and publishes
to the local bus.

**This is the only new code needed for global federation.** Everything else —
Keycloak, Citus, coop-api, RLS — stays exactly as it is.

## Scaling properties

| Concern | How it scales |
|---|---|
| **Users** | Horizontal across nodes. 10K users/node × 1K nodes = 10M users. No global bottleneck. |
| **Groups** | Each group chooses one primary node. Group count is unbounded. |
| **Keycloak** | One realm per node (not per group). Realm size scales with node users. |
| **Citus** | One coordinator per node. Shard count scales with node groups. No global coordinator. |
| **Storage** | Local MinIO per node. Replicated via pathway runs or logical replication for hot data. |
| **Messages** | Gossip-based. Bandwidth per node = O(peers), not O(total network). |
| **Discovery** | DHT lookup = O(log N). No central registry. |
| **Trust** | Signature verification = O(1) per message. No certificate authority. |

## The honest limits

| Limit | Why | Mitigation |
|---|---|---|
| **No global search** | No central index of all groups/users/content. | Search is scoped to your node's groups + explicitly federated peers. Discovery is social (invite links, QR codes) or via on-chain registry (opt-in). |
| **Eventual consistency** | Cross-node sync is asynchronous. | Pathways provides explicit sync points. RLS on `foreign_data` shows "last synced at" timestamps. |
| **Node migration is manual** | Moving a group to a new node requires replicating data and updating the DHT record. | Pathway run: "node migration" template copies data, verifies, updates DHT, revokes old node. |
| **No global admin** | No one can ban a group from the network. | Groups self-moderate via their own RLS and federation allowlists. A toxic group is just... not followed. |
| **Tailscale dependency** | The mesh relies on Tailscale's coordination server. | Fallback to direct WireGuard with manual key exchange, or use a public DHT (libp2p Kademlia) as the discovery layer. |

## The one-line summary

Every irl.coop node is a self-contained server stack. The global network is
nodes discovering each other by Safe address, verifying trust with Safe
signatures, and exchanging data via Pathways-enveloped events over a mesh. No
central database. No central identity server. No platform operator. Just
groups, nodes, and math.

## Open design questions

1. **DHT implementation**: Extend Tailscale's existing machine DHT, build a
   libp2p Kademlia overlay, or use something like ENS for on-chain discovery?

2. **Store-and-forward**: When a node is offline, where do pending envelopes
   queue? IPFS pinning? A rendezvous server run by a friendly group? Each node's
   own mailbox?

3. **Global consistency for group registry**: The on-chain `CoopRegistry.sol`
   holds group roots. How does it handle chain congestion and gas costs at
   10K+ groups?

4. **Rate limiting and anti-spam**: Without a central gate, how does a node
   protect itself from a malicious peer flooding envelopes? Proof-of-stake
   (Safe-locked tokens) per message? Reputation decay?

5. **Matrix federation vs. irl federation**: Matrix already federates chat
   (servers -> servers via SRV records + server keys). Does irl reuse Matrix's
   federation transport for chat, and build a separate one for data/workflows?
   Or unify everything under one transport?


## Code integrity — "is this node running our software?"

**The attack:** A malicious operator runs a modified node that steals data,
censors transactions, or injects backdoors. At global scale you cannot visit
every data center. You need a cryptographic answer to: "what code is this node
actually running?"

### The current state (gaps)

```
# Today: Docker images use tags, not digests
image: quay.io/keycloak/keycloak:25.0.6
# A tag can be repointed. 25.0.6 today might be malware tomorrow.

# Today: Git commits are not signed
# git log --format='%G? %h' shows 'N' (no signature) for recent commits
```

This is fine for one operator (Robbie) on one server. It is unacceptable for
a global federation where unknown peers run nodes.

### The solution: build attestation + digest pinning

Four layers, from repository to runtime:

#### Layer 1: Signed commits (developer identity)

Every commit to `irl-coop-stack-v2` is signed with the maintainer's SSH or GPG
key. Git already supports this:

```bash
git config commit.gpgsign true
git config user.signingkey ~/.ssh/id_ed25519.pub
```

A commit without a valid signature is rejected by CI and cannot become a
"blessed release."

#### Layer 2: Reproducible builds (build integrity)

The `infra/build/images/` Dockerfiles are designed to produce the **same image
digest** on every build. Requirements:

- Base images pinned by digest, not tag: `FROM ubuntu:24.04@sha256:abc123...`
- Deterministic timestamps (`SOURCE_DATE_EPOCH`)
- No network fetches at build time (everything vendored)
- Multi-stage builds with exact dependency lockfiles

A CI runner builds the image twice on different hosts. If the digests match,
the build is reproducible and the digest is published as "blessed."

#### Layer 3: Safe-attested releases (group authority)

The `irl.coop` group (the steward) periodically votes on-chain to bless a
specific commit hash + image digest combination:

```solidity
// CoopRegistry.sol
struct Release {
    bytes20 gitCommit;
    bytes32 imageDigest;   // sha256 of the flattened image
    bytes32 configHash;    // hash of infra/instances/dev/apps/*.yaml
    uint256 blockNumber;
}
mapping(uint256 => Release) public blessedReleases;
```

A Safe proposal says: "Bless release v4.2.1: commit `abc123`, digest
`sha256:xyz...`." The group votes; on execution, the release becomes the
official one. No individual can bless alone — the threshold governance prevents
that.

#### Layer 4: Runtime attestation (node verification)

When two nodes federate, they do not exchange certificates. They exchange
**attestations** as part of the Pathways HandoffEnvelope handshake:

```json
{
  "handoff_type": "node_attestation",
  "node_safe": "0xNodeSafeAddress",
  "release": {
    "version": "4.2.1",
    "git_commit": "abc123...",
    "image_digest": "sha256:xyz...",
    "config_hash": "sha256:cfg...",
    "chain_block": 18402391,
    "safe_signature": "0x..."
  },
  "timestamp": "2026-11-20T20:00:00Z"
}
```

The receiving node verifies:
1. The `safe_signature` is valid for `node_safe`.
2. The `git_commit` exists in the `irl-coop-stack-v2` repo.
3. The `image_digest` matches the blessed release in `CoopRegistry.sol`.
4. The `timestamp` is fresh (±5 minutes).

**If any check fails, the handshake aborts.** The node is treated as a stranger,
not a federation peer.

### What this gives you

| Threat | How it's stopped |
|---|---|
| Operator installs a modified build | The image digest won't match the blessed release on-chain |
| Attacker compromises CI and pushes a malicious image | The image digest is not blessed by the group's Safe vote; nodes reject it |
| Maintainer goes rogue and signs a bad commit | The Safe threshold requires multiple stewards to bless a release; one rogue maintainer cannot push malware globally |
| Sybil attack (thousands of fake nodes) | Each node must prove a unique Safe address + blessed release. Fake nodes without blessed code are network-isolated. |
| Replay of an old attestation | Timestamp + sequence number in the envelope; old attestations are rejected |

### The "slightly modified" exception

Some nodes will want to patch: a custom theme, a local translation, a hardware
adapter. These are **not federation peers** — they are "edge nodes" that speak
only to their own members. They do not participate in the global DHT or peer
event bus.

To become a federation peer, a node must run a **blessed release with zero
modifications** (config via `apps/*.yaml` is fine; `docker build` from a
modified Dockerfile is not).

### Practical migration

1. **Today:** Pin all `image:` values in `apps/*.yaml` to digests, not tags:
   ```yaml
   image: quay.io/keycloak/keycloak@sha256:7a3f...
   ```
2. **This week:** Enable commit signing for maintainers.
3. **This month:** Add a CI step that builds every image twice and asserts digest equality.
4. **This quarter:** Add the `blessRelease` function to `CoopRegistry.sol` and
   make `bootstrap-keycloak.py` verify peer attestations before accepting a
   federation handshake.


## The global database — there isn't one

At 10,000 nodes, there is no shared Citus coordinator. Each node has its own
Postgres. So what does "global data" mean?

### Local-first with signed sync

**Data lives where it is created.** Detroit's survey is written to Detroit's
Citus. Portland never queries it directly. Instead, Detroit **pushes** the data
to Portland via a Pathways run, and Portland stores it locally:

```sql
-- Portland's Citus
create table foreign_data (
  source_node   text,      -- "detroit.node-47.irl.coop"
  source_group  text,      -- "soil-survey-detroit"
  data_id       text,
  payload       jsonb,
  attestation   bytea,     -- Safe signature
  received_at   timestamp,
  primary key (source_node, data_id)
);
```

Portland's coop-api treats `foreign_data` exactly like local data — same RLS
policies, same GraphQL schema, except the `source_node` column scopes access.

### Consistency model: CRDTs for shared state, anchors for ordered state

| Data type | Pattern |
|---|---|
| **Group membership** | Local-first CRDT. If Alice is removed in Detroit, the tombstone propagates via event bus. Multiple concurrent removals merge safely. |
| **Financial ledger** | Ordered chain per group. Period roots are anchored on-chain. No CRDT — order matters. Cross-group swaps are two entries, not one. |
| **Chat messages** | Matrix federation (already exists). Messages are CRDT-like: out-of-order delivery is fine, clients show threaded history. |
| **File storage** | Immutable content-addressed blobs. A file hash never changes. Sync is "do you have this hash?" not "what is the latest version?" |

### The on-chain anchor as the "global clock"

There is no global logical timestamp. There is a **periodic on-chain anchor**:

```
Block 18,402,391:  root = hash(all period roots submitted this month)
```

Each node submits its period root (a hash of its local data for the period) to
`CoopRegistry.sol`. The transaction's block number becomes the global anchor
point. Any data claimed to exist "before period P" must have a proof path that
terminates at anchor P or earlier.

This is not a global database. It is a **global checkpoint** — a way to prove
that data existed at a time, without storing the data itself on-chain.

### Querying across nodes

A member on Portland asks: "show me all soil surveys from my federated groups."

Portland's coop-api queries:
```sql
select * from soil_survey where group_id = 'portland-soil'
union all
select payload->>'survey' as data from foreign_data
where source_group in ('soil-survey-detroit', 'soil-survey-casco')
```

The foreign data is already on Portland's Citus — fetched asynchronously via the
federation gateway. The query is fast because it is local. The member sees a
unified view. The synchronization happened in the background, not at query time.

### Summary

| Global construct | What it actually is |
|---|---|
| "Global database" | A mesh of local Postgres instances, each holding its own groups' data + replicas of federated peers' data |
| "Global identity" | Safe addresses (on-chain, self-custodied) |
| "Global clock" | Periodic on-chain anchors (block numbers as timestamps) |
| "Global trust" | Safe threshold governance blessing releases and federation links |
| "Global search" | Local search + explicit federation manifest (no global index) |

The irl.coop stack — Keycloak, Citus, coop-api, event bus — becomes a **node
kernel**. A thousand nodes running the same kernel, discovering each other by
Safe address, trusting each other by Safe signature, and syncing data via
Pathways runs. That is the global architecture.
