# Multi-chain accounts, and how a group manages them

Status: design · 2026-09-29 · answers a question, and records the constraints it exposes.
Related: `base-indexing.md` (what the indexer must scope over), `account-and-key-model.md`,
`group-scoping.md` (Layer 1 truth / Layer 2 projection), `delegation-and-session-keys.md`,
`money-in-and-out.md` (D-21: Base mainnet), **`cross-chain-action.md`** (canonical authority,
peripheral action — the objkt.com case, and why reach is not authority).

## 0. The short version

**A Safe can sign for another chain — but never with one signature.** A Safe transaction is
EIP-712 typed data with the **chainId in its domain**, so every signature is valid on exactly
one chain. "Sign once, act on N chains" is real only as *N domain-separated digests, N signature
rounds, N transactions* — or by adding a **cross-chain message bridge**, which is a new trust
assumption and a new target.

And the address is not a shared account: **the same address on two chains is two independent
accounts that happen to coincide**, because the address is a CREATE2 function of the
*deployment-time* inputs. It is a convention you must actively maintain, not a property that
protects you.

**Recommendation: one canonical chain for authority and value (Base), and treat any second
chain as peripheral and exceptional.** This matches D-21, and it matches `MASTER_PLAN.md`,
which explicitly moves the v4 stack *away* from legacy multi-chain architectures.

## 1. What the address actually is

`apps/coop-api/src/safe.ts` already implements this, and its own comment states the property:
*"Same inputs → same address everywhere, forever."*

```
address = CREATE2( factory, keccak256( keccak256(initializer) ‖ saltNonce ), keccak256(deploymentCode) )
```

Three consequences that are easy to get wrong:

| Consequence | Detail |
|---|---|
| **The address commits to the DEPLOYMENT-TIME owner set and threshold** | the `initializer` is inside the salt. Identical address on two chains therefore requires an identical initializer at deploy time. And it attests only what was true *then* — owners can be changed afterwards via Safe transactions **without changing the address**, so the address is **not** evidence of the current owner set |
| **The Safe version and factory bytecode must match across chains** | `SAFE_PROXY_CREATION_CODE` is a pinned blob (safe-contracts 1.4.1-2, solc 0.8.20, optimizer 200) with the warning *"Re-extract from `contracts/artifacts` after any Safe version or compiler setting change."* Deploy a different Safe version on another chain and the predicted address is simply wrong |
| **Current authority is per chain and must be verified per chain** | nothing enforces that owners match. Divergence is silent. Read `getOwners()` / `getThreshold()` on each chain; never infer one chain's owners from another's |

## 2. What a group gets for free: identical deployed-contract addresses

`contracts/scripts/safe-deploy-lib.ts` deploys group contracts **through the Safe** with
`CreateCall` and a DELEGATECALL, "which is what makes the SAFE the deployer". With a salt it uses
`performCreate2`, and its own note says the address *"is a pure function of (Safe, salt, initCode),
so it can be computed and checked BEFORE spending gas."*

Since the Safe address is chain-independent and the salt and init code can be too:

> **A group's deployed contracts land at the same address on every EVM chain**, computable in advance.

**`eip155` only — and that is the ceiling of the property.** CREATE2 address coincidence cannot
cross into a non-EVM namespace: there is no "same address" between an `eip155` chain and
`bip122` or `tezos`, ever. So this is **not** how a group gets one identity across chains —
that needs a chain-agnostic principal bound to per-chain accounts. See
`chain-agnostic-identity.md` §2 and §4.

Two caveats the code already records, and both bite on a second chain:

- **"the address moves if any constructor argument changes"** — any chain-specific constructor
  argument (a token address, a chain id, an oracle) breaks the correspondence.
- **"repeating a salt reverts"** — a redeploy needs a fresh salt, so a redeploy on one chain and
  not another desynchronises the addresses.

## 3. Signing: the part with no clever answer

| Fact | Consequence for a multi-chain group |
|---|---|
| A `SafeTx` is EIP-712 with **chainId in the domain** | a signature is valid on exactly one chain. There is no replay across chains, by design |
| The *payload* (to, value, data, nonce…) can be identical | so the same intent can be signed N times. Safe{Wallet}'s multi-chain batching makes this *feel* like one action; on-chain it is **N signatures and N transactions** |
| **Nonces are per chain** | a multi-chain signing flow must track N nonces. A stale nonce view produces signatures that are simply invalid, and the failure is not obvious |
| **Modules, session keys, guards, owners, threshold are all separate storage per chain** | enabling `SessionKeyModule`, granting a session key, or adding a guardian must be **repeated on every chain**. The tree has *no* ERC-4337 / EntryPoint / paymaster / relayer infrastructure anywhere, so even gas abstraction is unwritten |
| An owner key must be able to pay gas on each chain it acts on | unless a per-chain paymaster or relayer is introduced, which is new infrastructure per chain |

**The only genuine "sign once, act across chains" is cross-chain messaging** — a canonical
bridge, CCIP, LayerZero, Axelar, Wormhole, or an emerging account standard (e.g. ERC-7579-style
cross-chain accounts). Every one of them introduces **a bridge as a trust assumption and a
target**. For a design whose threat model includes a state compelling a party
(`adversary-models-and-sector-fit.md`), and which defines itself against custodied and
compellable intermediaries, **adding a message bridge is a security decision, not a
convenience**. It should be taken deliberately, and the honest default is not to take it.

## 4. The management model for a group

**One canonical chain for authority and value: Base.** Other chains, if ever, are peripheral.

Why this is the right default rather than a limitation:
- The coop's identity, authority, governance and treasury are **one thing**; splitting them
  across chains multiplies every authority change by N, with no benefit the design asks for.
- `MASTER_PLAN.md` already states the direction: the v4 stack moves *away* from multi-chain
  architectures and TEEs.
- Every added chain adds a bridge-or-duplication choice, an RPC dependency, a gas balance, an
  indexer, and a place for owner sets to diverge silently.

**A group's identity is a chain-agnostic principal, not an address.** `(chain_id, safe_address)`
is EVM-shaped and cannot express a Tezos, Bitcoin or NEAR account. The principal already exists
— it is `groups.id` — and its on-chain accounts are **bindings** of it, one or more per
namespace. See `chain-agnostic-identity.md`.

### The costs, stated honestly

| Operation | Cost on N chains |
|---|---|
| Add or remove an owner / change threshold | N signature rounds, N transactions, N nonce updates |
| Enable a module or grant a session key | N deployments, N enables |
| Replace a lost key | N × the recovery procedure — and recovery is already an open risk (R-08) |
| Every governance execution | N |
| Key compromise | **All N at once**, because the same owner keys must be present on each chain |
| Indexing and monitoring | N indexers (or one, chain-scoped) |
| Reconciliation | N places value can sit, each needing its own sweep/monitor |

The last row of that is the real argument: **multi-chain does not reduce risk, it multiplies
every existing risk by N.**

### Concrete consequences inside the current design

These are not hypotheticals — they follow from what is already built:

1. **D-16 seats are chain-ambiguous, and `chain_id` is not the fix.** A seat's holder is a Safe
   (`group_members.holder_safe`), stored as a bare EVM address. An integer `chain_id` column is
   equally EVM-shaped and still cannot express a Tezos, Bitcoin or NEAR holder. **The fix is a
   chain-agnostic identifier (CAIP-10)** — see `chain-agnostic-identity.md` §4. Left
   unaddressed this breaks quietly, which is the worst way.
2. **Votes are chain-scoped and the verifier does not exist.** `decisions.ts` captures an
   EIP-1271 signature in `votes.signature` with no chain column, and comments that verification
   is "on-chain later". `ConfidentialVoting.sol` (named in `zk-membership-graph-proofs.md`) does
   **not exist**. So governance is chain-agnostic today only because it is entirely off-chain —
   and it will become chain-specific the moment it lands on-chain.
3. **The indexer must be chain-scoped from day one** (`chain_id` in every key and query), even
   while only Base exists. Retrofitting chain-scoping into a projection is far worse than
   carrying the column from the start. See `base-indexing.md`.
4. **Safe provisioning is currently a placeholder**, which multi-chain would multiply: every
   Safe the system creates is owned **1-of-1 by the backend signer**
   (`defaultInitializer()` in `safe.ts`), and that key is Hardhat account #0's *published*
   key. Fine on a throwaway local chain; disqualifying on one chain, let alone several.

## 5. What to build, and in what order

**Now (Base only):**
1. Declare `CHAIN_RPC_URL` + `CHAIN_ID` once, and refuse to run when they disagree. This is
   already a blocker for `base-indexing.md` and for the payments preflight.
2. Carry `chain_id` through the projection from the start — including wherever a Safe address
   is stored.
3. Replace the 1-of-1-backend-signer placeholder with real per-member owners before any real
   value is at stake.
4. Treat Base as the canonical chain **in writing**, so nobody adds a second one by accident.

**If a second chain is ever genuinely needed:**
1. **A cross-chain authority audit first** — a tool that reads `getOwners()`/`getThreshold()`
   on every chain for every group Safe and reports divergence. Without this, "same address" is
   an assumption and not a fact.
2. Pin the Safe version and factory across chains, and re-verify each chain's USDC/token
   addresses on-chain (as `networks.json` already does for Base and Base Sepolia).
3. Decide the messenger question explicitly — per-chain signature rounds (no new trust) versus
   a bridge (new trust, new target). Default to the former.
4. Extend the indexer to the new chain rather than adding a second indexer.

## 6. Open questions

- **Is any second chain actually wanted?** Nobody has asked for one. D-21 names Base; this
  document exists so that if someone does, the constraints are already written down. If the
  answer is "no", most of this becomes a recorded guardrail rather than a plan.
- **Could the same-address property be used deliberately** for a group that wants one identity
  across chains while keeping value only on Base? That is the most defensible use of
  multi-chain here, and it needs no bridge.
- **Who holds the owner keys for a group Safe, and is a passkey an owner?** The code says
  passkeys "slot in as owners". Until that is answered, multi-chain would be multiplying a
  placeholder.
- **Does the Safety of one chain's owner set depend on the other's?** Only if you decide it
  does. Nothing on-chain forces it, and nothing detects divergence — which is why §5's authority
  audit is the prerequisite, not an optional nicety.