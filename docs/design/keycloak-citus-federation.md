
# Keycloak × Citus federation with Pathways

**Status: design exploration · 2026-11-20.**

## The core question

Every group on irl.coop runs its own Keycloak realm + Citus shard today (one realm, one
coordinator, many workers). When two groups want to federate — a Detroit co-op and a Portland
network — how does Alice prove her Detroit identity to Portland's stack without Portland
trusting Detroit's server?

## What already exists (the primitives)

| Primitive | What it gives us |
|---|---|
| **Keycloak OIDC brokering** | Keycloak can trust *another* Keycloak as an IdP. Alice signs in to `auth.detroit.coop`, gets an OIDC token, presents it to `auth.portland.coop` as a federated identity. Keycloak handles user creation/mapping automatically. |
| **Citus shard routing** | Citus already routes queries to worker nodes by distribution column (group_id). A cross-group query is just a query that hits multiple shards. |
| **Safe-as-everything** | Every person and group has a deterministic EVM address. The address is a persistent, self-custodied identifier that outlives any server. |
| **coop_rls + row-level security** | Postgres already enforces `coop_current_sub()` per query. Cross-group access means the RLS policy must accept *foreign* subs. |
| **Pathways HandoffEnvelope** | A typed, signed, versioned envelope that crosses trust boundaries with an audit trail and attestation. |

## The three-layer model

### Layer 1: Identity federation (Keycloak)

**Pattern: realm-level OIDC brokering with automatic user provisioning.**

Portland's Keycloak adds Detroit's Keycloak as an "Identity Provider" (the built-in Keycloak OIDC
brokering feature). The config lives in Portland's `apps/keycloak.yaml` derived config, same as
Google brokering works today.

```yaml
# Portland's keycloak.yaml (federation stanza)
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
      syncMode: IMPORT  # auto-create Portland user on first Detroit login
      trustEmail: true  # Detroit's email verification = Portland's
```

Alice goes to `plane.portland.coop`, clicks "Sign in," chooses "Detroit Co-op" from the
broker list, signs in at Detroit, and is redirected back to Portland with a federated session.
Keycloak automatically creates a shadow user in Portland's realm with Detroit's `sub` mapped
to Portland's local `sub` (or preserves the original `sub` if configured).

**The portal client**: For cross-group dashboards, there's a special `portal` client that accepts
tokens from *any* brokered IdP. The portal's consent screen says: "Portland Co-op is asking to
see: your email, your groups, your roles." Alice approves once per trust relationship.

**Why this is easy**: Keycloak already ships with `keycloak-oidc` as a first-class broker provider.
The `coop-api` service account (which has `manage-users`) can provision the IdP config
programmatically. `bootstrap-keycloak.py` already does client creation; IdP creation is the same
admin API.

### Layer 2: Membership proof without trusting the foreign server

**Pattern: cryptographically-verified group membership that survives server compromise.**

Brokering gives Portland Alice's identity, but how does Portland know Alice holds `member` in
Detroit's `soil-survey` working group? Trusting Detroit's API to say so is the server-compromise
risk the federation design deliberately avoids.

**The pathway**: A Pathways run produces a `HandoffEnvelope` carrying an EIP-1271 signature from
the Detroit group's Safe, attesting: "Alice (sub `abc-123`) holds role `member` in Detroit
`soil-survey`, signed at block 18,402,391."

```json
{
  "handoff_type": "membership_proof",
  "source_group": "did:safe:0xDetroitSafeAddress",
  "subject": "abc-123",
  "role": "member",
  "scope": "soil-survey",
  "attestation": {
    "type": "Safe_EIP1271",
    "signature": "0x...",
    "snapshot_block": 18402391
  },
  "pathway_run": "pr_0x7a3f...",
  "expires": "2026-12-20T00:00:00Z"
}
```

This envelope is:
- **Self-verifying**: Portland verifies the Safe signature against `0xDetroitSafeAddress`; no API
call to Detroit needed.
- **Time-bounded**: expires, forcing Alice (or Detroit's stack) to re-attest periodically.
- **Auditable**: the `pathway_run` ID lets anyone look up the full provenance of how this proof
was produced — who initiated it, what template was used, what autonomy level it ran at.

**How it gets used**: When Alice brokers into Portland's Keycloak, Portland's Keycloak asks
`coop-api` for a "federation supplement" — a set of signed proofs Alice carries from her home
group(s). coop-api validates the signatures, extracts the roles, and writes them into Alice's
Portland session as Keycloak `groups` claims. The custom `coop-groups-mapper.jar` already
does exactly this (fetches groups live from coop-api); extending it to validate pathway
envelopes is a new mapper variant.

### Layer 3: Data routing (Citus)

**Pattern: shard-aware cross-group queries with RLS policy federation.**

Citus distributes tables by `group_id`. Detroit's rows live on Detroit's worker shards; Portland's
rows on Portland's. A cross-group resource share — Detroit shares a `soil_survey` dataset with
Portland — is represented in Citus as:

1. A `group_federations` row: "Portland trusts Detroit's data at autonomy level A2."
2. RLS policy extension: `coop_current_sub()` is augmented to accept brokered subs:

```sql
CREATE POLICY cross_group_read ON soil_survey
FOR SELECT USING (
  group_id = coop_current_group()
  OR group_id IN (
    SELECT foreign_group_id FROM group_federations
    WHERE home_group_id = coop_current_group()
    AND data_scope = 'soil_survey'
    AND trust_level >= 'A2'
  )
);
```

3. The query planner routes to Detroit's shard automatically — Citus already does this for any
distribution value it knows.

**The pathway here**: establishing the federation link itself is a Pathways run. Detroit and
Portland each run a "federation establishment" template at autonomy level A3 (human-gated
execution). The output is a `group_federations` row + a Safe proposal on each side authorizing
the trust. The row is signed by both groups' Safes, and the signatures are stored in a
`group_federation_proofs` table that Citus RLS consults before allowing cross-group access.

## Why this is "easy"

| Hard part | Why it's actually solved |
|---|---|
| Trusting a foreign Keycloak | We don't — we broker through it, but verify membership via Safe signatures on-chain |
| Foreign server compromise | Compromised Detroit server cannot forge Safe signatures; Portland verifies on-chain, not by API |
| Revocation | Remove the `group_federations` row = instant revocation; no central registry to update |
| Audit | Every trust, every proof, every data access goes through a Pathways run with an AquaTree revision — the audit trail is append-only and forkable |
| Bootstrapping | Two groups that have never met can establish trust by signing a short federation manifest with their Safes — no legal entity, no email verification, just math |

## The one-line summary

Each group keeps its own Keycloak realm and Citus shard. Cross-group access is brokered OIDC + 
membership attested by Safe signatures + data shared via shard-aware RLS. The "how do we trust
each other" question is answered by Pathways: the handshake itself is a versioned, auditable,
cryptographically-attested workflow run.

## Open questions

1. **Signature verification cost**: Every cross-group query would need to verify an EIP-1271
signature. Caching the verification result in Postgres (with TTL) trades freshness for speed.

2. **Keycloak federation UI**: The broker selection UI ("Sign in with Detroit Co-op") needs to
be populated dynamically as new federations are formed. A static list won't scale.

3. **Citus multi-coordinator**: True federation might need each group to run its own Citus
coordinator, with cross-coordinator federation via Foreign Data Wrappers (FDW) or logical
replication. This is more complex than single-coordinator + multi-shard.

4. **Pathways ↔ coop-api integration**: The handshake still needs code. Today it's design. The
integration point is the event bus: a Pathways `HandoffEnvelope` arriving on the bus triggers a
coop-api handler that validates the envelope and mutates `group_federations`.
