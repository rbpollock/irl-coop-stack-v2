# Mainnet deploy — the coop's contracts on Base

Status: **runbook** (the durable plan; nothing deployed to Base mainnet as of 2026-10-17).
Owner: the irl.coop group eventually; today a single funded deployer is the one unavoidable
human concentration for the one-shot deployment (record under the D-42 framing once the
group exists).

## Why this must happen before "the group exists on mainnet"

1.1 of `group-operated-stack.md` is "the `@irl.coop` group + Safe at 1-of-1". A Safe that
sits on the local Hardhat node is a development artifact, not a live group. "The group
exists" only when the contracts behind it live on **Base mainnet (chainId 8453, D-21)**.
Today **no** coop contract is deployed there: stack-up deploys a fresh local node on each
boot, and `whoami --network base` reports `NO SIGNER` (no deployer key on the box).

## What is already mainnet-ready (verified in the repo)

- `contracts/hardhat.config.ts` has a `base` network → `https://mainnet.base.org`, chainId
  8453, `accounts: PRIVATE_KEY`.
- `contracts/networks.json` → `base` entry with the on-chain-verified USDC
  `0x833589fCD6Edb6E08f4c7C32D4f71b54bdA02913` (chainId `0x2105`, `symbol()='USDC'`,
  `decimals()=6`, verified 2026-09-13) and explorer `https://basescan.org`.
- `contracts/scripts/deploy_router_testnet.sh` is network-agnostic: reads RPC/chainId/USDC
  from `networks.json`, reads the deployer key from a private 0600 file, never prints it,
  and gates on a funded `whoami`.
- `contracts/scripts/whoami.ts` prints the deployer + balance and refuses a zero balance.

## The one real precondition: a funded Base mainnet deployer

The only human/real-money step and the **single gate**. Create an EOA, fund it with ETH on
Base (just enough for the deploy txns), and store ONLY the 0x-key in a 0600 file, e.g.
`~/.secrets/base-mainnet.key` (or set `DEPLOY_KEY_FILE`). The balance check refuses a zero
balance. The deployer only pays gas — it is never a minting/treasury address.

## Deploy inventory — "all the contracts"

Deploy **our** contracts; do **not** redeploy the canonical Safe — Base has a verified Safe
singleton + proxy factory, and they are referenced by address, not re-published.

1. **Contract set on base** (per contract, deploy + verify):
   - `SafeImports.sol` — library/factory wiring, i.e. Safe address references, not re-deploy.
   - `CoopBatchRouter.sol`, `CoopRegistry.sol`, `CoopUsdcRouter.sol` — the coop routers
     and registry.
   - `ShieldedPool.sol` — needs the USDC address above; deploy via `deploy_shield.ts --network base`.
   - `modules/SessionKeyModule.sol`, `modules/SovereignEvolutionModule.sol` — if a module of
     the Safe is used, deploy per module and wire into the Safe.
   - Test-only fixtures (`Lock.sol`, `MockUsdc`, `ShieldedPoolMock`, `DeployerProbe`,
     `StubVerifier`) do **not** go to mainnet.
   - Nominate the exact per-contract script and verify the scripts present before running
     (`ls contracts/scripts/*.ts`).

## The run, conditionally (only when the key is funded)

```bash
CONTRACTS=/home/service/development/irl-coop-stack-v2/contracts
cd "$CONTRACTS"
export DEPLOY_KEY_FILE=$HOME/.secrets/base-mainnet.key   # 0600, 0x-prefixed, funded

# 1. gate: who pays, and can they?
npx hardhat run scripts/whoami.ts --network base

# 2. the payment-router path (deploy + verify a USDC router for the group Safe)
DEST=<the @irl.coop group Safe address, CREATE2-predicted once group creation catches up>
bash scripts/deploy_router_testnet.sh base "$DEST"

# 3. registry / shield / modules per their deploy scripts: <script>.ts --network base
```

## Verification discipline

- Record every deployed address with its verified identity — chainId, `symbol()`,
  `decimals()` — following the `networks.json` rule ("verified on-chain, never typed from
  memory"). Extend `contracts/networks.json` with `base` entries for the routers/registry,
  the modules, and the Safe singleton/factory addresses.
- Confirm each artifact on `https://basescan.org`; `hardhat verify` a contract before any
  partner can land money on it.
- After deploy, flip coop-api's Safe-deploy target from the local node to `base`
  (chainId 8453 + a paid RPC/relayer). That wiring is the real "group exists" gate.

## Open / deferred (written here so they gate nothing)

- **Deployer-key custody**: the funded key is briefly a heavy concentration that the Safe
  group supersedes once D-42 (keys come home / group operates) lands. Keep it a human 0600
  file, label it one-shot, and record its location — never in the repo.
- **Gas-only deployer**: the EOA exists only to pay gas for the deploys — never a
  minting/treasury address. Top it up per launch, not as a standing balance.