# Platform-level Base indexing

Status: design · 2026-09-29 · decision, not exploration.
Related: `money-in-and-out.md` (the money design), `group-scoping.md` (Layer 1 / Layer 2),
`multi-chain-accounts.md` (what changes if a group is ever on more than one chain),
`docs/PAYMENTS-SETUP.md` (the rail this serves).

## 0. The answer in one line

**A small self-hosted log indexer as its own app — the same seam as `apps/peer_xyz_payments` —
reading `eth_getLogs` for an explicit allowlist of our contracts, writing a rebuildable,
chain-scoped projection, with a checkpoint and reorg handling.** Not a subgraph. Not a hosted
indexer. And for Safe specifically: **do not index it ourselves** — use the Safe Transaction
Service, and read current authority with `eth_call`.

## 1. The volume settles the tooling question

`money-in-and-out.md` already did this arithmetic. Tier-2 entries run ~120/day/group
(~569k/year) and they are **deliberately off-chain, hash-chained, and anchored** — not indexed.
What remains on-chain is gate-shaped: a deposit, a sweep, a distribution, one anchor per group
per day, a governance attestation.

| | Count |
|---|---|
| Tier-2 entries (off-chain by decision) | ~569,000 / year |
| Tier-2 anchors (on-chain, indexable) | ~4,745 / year |
| Tier-1 value crossings (deposits, sweeps, distributions) | tens to low hundreds / year |

Tens-to-low-thousands of events per year. Every indexing framework is more machinery than the
data, and a hosted service adds a dependency we must not need. See §5 for why a subgraph is
specifically the wrong answer here.

## 2. Split the concern first — this matters more than the tool

| Kind | How to get it | Why |
|---|---|---|
| **Truth that must be CURRENT** — a Safe's owner set and threshold, a group's authority, whether an address is a contract | **`eth_call`. No indexer** | `getOwners()` / `getThreshold()` is authoritative and instant. **Never index what you can read.** An indexed owner set is a *stale* owner set, and this is exactly the Layer-1 truth the D-16 seat model resolves against. `apps/coop-api/src/safe.ts` already does this by JSON-RPC |
| **History that must not be lost** — deposits, sweeps, module events, anchors, Safe executions | **an indexer** | A log is only retrievable inside the RPC's block window. "Did a payment land that nobody noticed?" is precisely the question the router cannot answer about itself, and the provider's API cannot be polled |

This is the same discipline as `group-scoping.md`: on-chain is **truth**, the Citus projection
is **rebuildable**. An indexer that cannot be re-run from genesis is not a projection, it is a
second source of truth — the exact failure mode `money-in-and-out.md:275` rejected.

## 3. The design: `apps/chain_indexer`

Its own app, for the same reason the rail is its own app: the RPC vendor lives behind a seam,
so a provider being taken down, blocked, or broken kills **one** process, and swapping providers
is configuration rather than an edit to core.

**Non-negotiables:**

| Rule | Why |
|---|---|
| `eth_getLogs` over an explicit **allowlist of (chain_id, address, ABI)** | never a firehose. We index what we own, nothing else |
| **Idempotent upsert keyed `(chain_id, tx_hash, log_index)`** | re-running must be a no-op; the projection must be rebuildable |
| A **checkpoint row** (`chain_id`, `last_indexed_block`) | the checkpoint is the Layer-2 contract. Without it, "the database is disposable" is false |
| **`head − N` confirmations + a re-scan window** | Base is an OP-stack L2. Reorgs are shallow but real. Never index to the tip |
| **On reorg: delete rows above the safe head, re-insert from the window** | leaving orphaned rows is how a projection silently diverges from truth |
| **Emit to the existing bus** (outbox → Temporal) | a deposit then becomes an app event by the same route a webhook does |
| **Refuse to start if `CHAIN_ID` ≠ the RPC's `eth_chainId`** | the rail's own rule: assert the environment by asking, never infer it from a flag |
| **Refuse an index target with no code** | reuse the preflight's contract-vs-EOA check, including the **EIP-7702 designator** trap (`0xef0100…`) — a delegated EOA is a person's account, not a contract |
| **Scope every key and query by a CAIP-2 chain id** | see `chain-agnostic-identity.md`. `chain_id` is a **CAIP-2 string** (`eip155:8453`), not an integer, so a non-EVM namespace (`bip122`, `tezos`, `near`) needs no migration. Part of the identity, always |

**Suggested schema** (fits the existing projection; `anchors` already anticipates `chain`):

```
chain_log               -- the raw, re-buildable layer
  chain_id text, block_number, block_hash, tx_hash, log_index  (PK: chain_id, tx_hash, log_index)
  -- chain_id is a CAIP-2 STRING ('eip155:8453'), not an integer, so a non-EVM
  -- namespace (bip122, tezos, near) can be added without a migration
  address, event_name, args jsonb, observed_at

chain_indexer_checkpoint
  chain_id (PK), last_indexed_block, last_safe_head, updated_at

-- plus projections built from chain_log, e.g.:
chain_deposit           -- router deposits, the thing that tells someone to sweep
  chain_id, tx_hash, log_index, router, amount, swept_at, sweep_tx_hash
```

**One thing this indexer incidentally fixes:** it is the monitor that tells a human the router
is holding USDC and needs `sweep()`. Today **nothing** calls `sweep()` in production (see
`docs/PAYMENTS-SETUP.md` §7), so a deposit can sit indefinitely with no one told.

## 4. Safe: do not build this

The single biggest saving. The Safe ecosystem already indexes Safes, and the tx decoder is the
genuinely hard part — it is already written and battle-tested.

- **Current authority** → `eth_call` (`getOwners`, `getThreshold`). No indexer, always fresh.
- **Safe history** (executions, confirmations, transfers, module enables) → the **Safe
  Transaction Service** — open source and self-hostable, with a hosted instance covering Base.
  Reach it through a seam; self-host later if sovereignty requires it. The pattern is identical
  to the rail's.
- **Do not** hand-crawl `SafeSetup` / `ExecutionSuccess` unless the service genuinely does not
  surface what we need.

Note the tree has **no Safe SDK dependency** in `apps/coop-api` (no `@safe-global/protocol-kit`
or `api-kit`); `safe.ts` hand-rolls the CREATE2 math with `ethers`. Talking to the Transaction
Service means either adding a dep or calling its HTTP API directly.

## 5. Alternatives, and why they lose

| Option | Verdict |
|---|---|
| **`apps/chain_indexer` (above)** | **Recommended.** Matches the existing seam, tiny surface, no framework, and we control the schema so it fits the projection we already have |
| **Ponder** (MIT, TS, self-hosted, Postgres-backed) | The honest upgrade path. It is this design with checkpointing and reorg-aware backfill already solved — but it wants to own its tables and migrations, and it is more machinery than ~5 event types justify. Adopt it **when the contract surface grows** |
| **Explorer API** (Basescan / Etherscan V2) behind the same seam | Good for **exploratory and audit** queries only ("every tx to this address since launch"). Zero infra. Never load-bearing, never the correctness path — it is rate-limited and centralised |
| **Hosted subgraph** (The Graph / Goldsky) | **Against.** It reintroduces exactly what `money-in-and-out.md:275` already rejected — *"two sources of truth and a sync problem"* — and puts the read path in a hosted service we must not need. Unlike the rail, there is no regulatory reason to prefer a vendor here |
| **Run our own Base node** | Only if a sovereign RPC becomes a requirement. It is a real cost in disk and operations, and it does not change this design — the seam already allows it as a drop-in `CHAIN_RPC_URL` |

## 6. What to index, contract by contract

| Contract | Events | Index? |
|---|---|---|
| `CoopUsdcRouter` | `DepositNoted`, `Swept`, `Rescued` | **Yes — first.** The only evidence USDC physically arrived, and whether it has been forwarded. Load-bearing for both "did the payment land" and "should someone sweep" |
| USDC `Transfer` to/from our addresses | — | **Yes, for reconciliation** — the independent check that value moved, against the provider's own story |
| our anchor writes | Merkle roots | **Yes** — cheap, and `anchors` already has `chain` / `tx_hash` / `anchored_at` waiting for it |
| Safe + our modules | `SessionKeyEnabled` / `SpendRecorded`; `StageUpgraded` / `BackendSignerRevoked` / `GuardiansAdded` | **Yes, but via the Safe Transaction Service first**; index the module events only if it does not surface them |
| `CoopRegistry` | `MembershipUpdated`, `MemberRevoked` | **No — not yet.** A 51-line stub, `_appendMember` is an empty placeholder, never deployed, and it is `Ownable` — an **admin**, which contradicts the no-admin property every other money contract holds. Index it when it is real |
| `CoopBatchRouter` | `DepositRouted` | **No.** Superseded and unusable — `routeDeposit()` keeps value with no withdrawal. Mark deprecated |
| `MockUsdc`, `ShieldedPoolMock`, `Lock`, `DeployerProbe` | test doubles | **No.** `ShieldedPoolMock` stands in for the real shielded pool, which is step 2 and unbuilt |

## 7. Blockers that come before any of this

An indexer cannot be built correctly on the current chain configuration.

1. **There is no single chain config.** `RPC_URL` is **not declared** in
   `apps/coop-api.yaml`, and four modules default to `http://127.0.0.1:8545`
   (`safe.ts:104`, `groups.ts:122`, `provisioning.ts:70`, `server.ts:240`) while `payments.ts`
   defaults to **Base mainnet**. Today the Safe path and the payments path point at different
   chains. Declare `CHAIN_RPC_URL` and `CHAIN_ID` **once**, and refuse to run when they disagree.
2. **The Safe layer is still the local chain.** `SAFE_SINGLETON_ADDRESS` and
   `SAFE_PROXY_FACTORY_ADDRESS` are Hardhat's local deployment addresses, and
   `SAFE_BACKEND_SIGNER_KEY` is Hardhat account #0's *published* private key, in plaintext in
   the tree. `money-in-and-out.md` §5.2b already calls this correct for a throwaway local chain
   and disqualifying anywhere else.
3. **Safe provisioning is a placeholder.** `safe.ts` derives every Safe as **owned 1-of-1 by
   the backend signer** (`defaultInitializer()`), so no member key or passkey is an owner yet.
   Indexing these Safes is fine; *trusting* them is not, and that is a separate task.

## 8. Open questions

- **Confirmation depth on Base.** N needs a number, argued rather than guessed (OP-stack
  sequencer reorgs are typically a few blocks; 20–30 is generous and cheap).
- **Does the Safe Transaction Service surface our custom module events?** If not, that is the
  one place we index ourselves.
- **Who acts on a deposit alert?** The indexer can detect that the router holds USDC. Whether
  that pages a human, retries a sweep, or is just a dashboard row is a product decision, and it
  is the same unwritten question as "who sweeps".
- **Does the indexer own the anchor write, or only observe it?** Today nothing writes to
  `anchors` — the table exists empty. Observing and writing are different jobs; keep them apart.