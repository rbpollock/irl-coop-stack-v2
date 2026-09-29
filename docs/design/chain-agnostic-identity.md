# Chain-agnostic identity

Status: design · 2026-09-29 · corrects an EVM assumption in the identifier layer.
Related: `account-and-key-model.md` (Safe-as-universal-account), `multi-chain-accounts.md`
(cross-chain signing), `base-indexing.md` (what the indexer scopes over), `group-scoping.md`,
**`cross-chain-action.md`** (what the Base authority may do on other chains).

## 0. The correction

`account-and-key-model.md` opens with **"Every account on irl.coop is a Safe smart contract."**
Safe is EVM-only. So the model's *principle* is chain-agnostic — a **t-of-n threshold account**
as the universal account, no TEEs, recovery independent of the backend, uncorrelated identity —
but its *mechanism* (Safe, EIP-1271, ERC-4337, `CreateCall`, passkey modules) is not.

**The identifier is where that distinction has to become explicit.** If a seat's holder is a
`0x…` address, the design cannot express a Tezos, Bitcoin, or NEAR account at all — and `chain_id`
does not fix it, because an integer chain id is equally EVM-shaped.

The fix is a chain-agnostic identifier, and there is already a standard for it.

## 1. The standard: CAIP-2, CAIP-10, CAIP-122

| Standard | Identifies | Form | Example |
|---|---|---|---|
| **CAIP-2** | a **chain** | `namespace:reference` | `eip155:8453`, `bip122:000000000019d6689c085ae165831e93`, `tezos:NetXdQprcVkpaWU`, `near:mainnet` |
| **CAIP-10** | an **account on a chain** | `namespace:reference:account` | `eip155:1:0xab16a96D359eC26a11e2C2b3d8f8B8942d5Bfcdb`, `bip122:000000000019d6689c085ae165831e93:128Lkh3S7CkDTBZ8W7BbpsN3YYizJMp8p6`, `tezos:NetXdQprcVkpaWU:tz1MJx9vhaNRSimcuXPK2rW4fLccQnDAnVKJ`, `near:mainnet:alice.near` |
| **CAIP-122** | a **chain-agnostic signed statement** ("Sign in With X") | per-namespace profiles | the Tezos profile exists (`namespaces.chainagnostic.org/tezos/caip122`) |

Syntax per CAIP-2: `namespace` matches `[-a-z0-9]{3,8}`, `reference` matches `[-_a-zA-Z0-9]{1,32}`.
Namespaces are extensible by design — `eip155`, `bip122`, `tezos`, `near`, `cosmos`, `polkadot`,
`starknet`, `solana`, and more. **CAIP-10 is the right primitive for "an account on a chain."**

**Honest caveat on coverage:** namespace ratification varies. NEAR's CAIP-2 is still an **open
issue** in `ChainAgnostic/namespaces` (#106, opened 2024-03), and the identifiers above are
community-converged rather than formally ratified. So adopt CAIP, but treat per-namespace
coverage as **a checklist to verify per chain** rather than an assumption. Same discipline as
`networks.json`, which records *how* an address was verified rather than trusting a document.

## 2. Two levels — an account and a principal

This is the part that is easy to miss: **CAIP-10 is chain-specific by construction.** It names an
account on exactly one chain. Therefore:

> **A multi-chain account cannot be a CAIP-10 string.** A group that exists on several chains
> needs a **principal** — one chain-agnostic identifier — bound to a *set* of per-chain accounts.

| Level | Is | Example |
|---|---|---|
| **Principal** | the group (or person) as one thing, across chains | the group's own stable id |
| **Binding** | one account on one chain | a CAIP-10 string + the fact it belongs to that principal |

**Recommendation: the principal already exists.** `groups.id` (and the member's `sub`) is
already the stable, chain-agnostic identifier. `groups.safe_address` was never the identity —
it is **one binding of many**. So the model becomes:

```
group_account
  group_id      uuid      -- the principal
  chain         text      -- CAIP-2, e.g. 'eip155:8453'
  account       text      -- CAIP-10, fully qualified
  kind          text      -- 'safe' | 'tezos-contract' | 'btc-multisig' | ...
  is_canonical  boolean   -- the chain authority is read from
  created_at    timestamptz
  PRIMARY KEY (group_id, account)
```

This needs no new identity system. It reuses the seats/scopes model: the group is the principal,
and each chain account is a delegate of it.

**Why not the same address everywhere?** Because that only ever worked *within* EVM — see §4.

## 3. Namespaces are not interchangeable — authority needs adapters

There is **no universal "read the authority" operation.** The same seam that makes the payment
rail its own app applies here: one adapter per namespace, behind a common contract.

| Namespace | The account is | Authority read | Signature scheme |
|---|---|---|---|
| **`eip155`** (EVM) | a Safe proxy | `getOwners()` / `getThreshold()` — authoritative, instant | ECDSA; `EIP-1271` for contract accounts, `EIP-712` payloads with **chainId in the domain** |
| **`tezos`** | a `tz1`/`tz2`/`tz3` implicit account or a `KT1` contract | contract storage read | **the address encodes the curve** — `tz1`=Ed25519, `tz3`=NIST P-256 (verified: the CAIP-10 examples show both). So the scheme is a property of the *account*, not the system |
| **`near`** | a named (`alice.near`) or implicit account; multisig lives in a contract's state | contract state read | Ed25519; `NEP-413` message signing |
| **`bip122`** (Bitcoin) | **not an account at all** — a P2SH/P2WSH/taproot **script** | **nothing to query.** There is no contract state and no authority call; a threshold is a property of the *script* you must already know | `BIP-322` generic message signing; verification is a signature check against the script |

**Bitcoin is the case that breaks naive abstraction.** "Ask the chain who controls this account"
is unavailable — so the adapter interface must be built around what is genuinely common:

- **verify a signature** by account A over payload P (all namespaces can answer, schemes vary);
- **is A a controller of account B** (EVM/Tezos/NEAR can answer from state; Bitcoin returns
  *unknown* unless you supply the script);
- and it must be able to answer **"unknown" honestly** rather than guess.

## 4. What this changes in the code

| Today | Becomes |
|---|---|
| `groups.safe_address text` (`db.ts:38`) | the group's identity is `groups.id`; accounts become rows in `group_account` |
| **D-16:** `group_members.holder_safe` | `holder_account` — a **CAIP-10** string. `holder_key = COALESCE(holder_account, sub)` still works (longer text, same shape) |
| `coop_own_safe()` / `coop_current_safes()` | `coop_own_accounts()` / `coop_current_accounts()`, over CAIP-10 strings |
| `votes.signature` (EIP-1271) | namespace + scheme recorded; verification is per-namespace (CAIP-122 shape) |
| indexer keyed on an integer `chain_id` | keyed on a **CAIP-2 string**, so a non-EVM namespace needs no migration |
| `SAFE_PROXY_CREATION_CODE` + CREATE2 prediction | **unchanged and correct — within `eip155`.** It is an EVM mechanism |

**Good news: the D-16 work survives.** The seat-resolution logic is a recursive walk over "the
accounts I act as"; making it chain-agnostic changes the *value format and column names*, not the
recursion, the cycle handling, or the traverse-vs-direct split. The scratch harness that verified
it can verify the renamed version the same way.

**The correction that matters most:** `multi-chain-accounts.md` §2 showed that a group's
deployed contracts land at the *same address on every chain* via CREATE2. That property is
**EVM-only**. There is no "same address" across `eip155` and `bip122`, ever. So address
coincidence is *not* how a group gets one identity across chains — **the principal plus bindings
is.** That is why §2 exists.

## 5. What survives, what must be re-expressed

| Survives unchanged | Must be re-expressed |
|---|---|
| t-of-n threshold as the universal account | **"Every account is a Safe"** → every account is a *threshold account*, realized per namespace (Safe, Tezos contract, Bitcoin script, NEAR multisig) |
| "Context is a property of the action" | **"The seat holder is a Safe"** → the holder is a **chain-agnostic account reference** |
| Seats and typed edges; ownership implies membership only | **EIP-1271 everywhere** → a per-namespace signature check (CAIP-122 shape) |
| The recursive "accounts I act as" walk | **EIP-712 domain with chainId** → CAIP-122 statement carrying a CAIP-2 chain |
| Layer 1 truth / Layer 2 rebuildable projection | **"Read the authority from the chain"** → adapter-mediated, and *not total* (Bitcoin) |
| No TEEs; backend never custodies; recovery without the backend | **Key material per chain** — and the compromise concentration that follows |

## 6. Honest limits and open questions

- **A chain-agnostic identifier does not give chain-agnostic authority.** "One signature acts
  across chains" still requires a message bridge, with all the trust that adds. See
  `multi-chain-accounts.md` §3. The identifier fixes *naming*, not *reaching*.
- **The safety of a threshold depends on the chain that enforces it.** A Bitcoin script's
  threshold is enforced by consensus with no contract to inspect; an EVM Safe's is enforced by
  contract code. Those are not the same guarantee, and the UI must not imply they are.
- **Key reuse across chains concentrates compromise.** A single chain-agnostic identity tempts
  you to use one key everywhere; one theft then hits every namespace. **Per-namespace keys bound
  to one principal is safer than key reuse**, and it should be the default.
- **Do we need a DID?** Not for internal use — `groups.id` is already a working principal. A DID
  adds a resolvable external document, which matters only if a **third party** must resolve our
  groups without our API. Worth revisiting then, not now.
- **Which namespace is authoritative for a group's seats?** The same question as
  `multi-chain-accounts.md` §4, now with the vocabulary to answer it: **`is_canonical` on the
  binding**, one per group, chosen deliberately.
- **Non-EVM work is unbuilt and unproven here.** Nothing in the tree mentions Tezos, Bitcoin,
  NEAR, or CAIP at all today. This document fixes the identifier so that adding a namespace is
  an adapter rather than a redesign — it does not claim any of it is tested.