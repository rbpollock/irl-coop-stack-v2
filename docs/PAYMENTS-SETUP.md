# Payments — first-time setup

Status: runbook · 2026-09-29 · derived from the code, not from intent.

This is how someone deploying this stack gets the payment rail working. It is written around
one fact: **the acceptance test already exists**. `GET /api/v1/payments/preflight`
(`apps/coop-api/src/payments.ts:161`) returns six gates, and `ready` is true only when all
six pass. Setup is the work of turning them green — in order, because several of them cannot
pass before the others are done.

Anyone doing this for the first time should read `docs/design/money-in-and-out.md` §3.7
first. It is the record of what was verified against the live sandbox and, more usefully,
of the four traps that cost a debugging cycle each.

---

## 0. The shape you are wiring

```
payer                    provider (Peer.xyz)              Base mainnet          the coop
Venmo / Cash App   ──▶   P2P counterparty receives  ──▶   USDC arrives at  ──▶  sweep() ──▶ the coop's Safe
PayPal / Wise            the fiat; USDC released          the ROUTER            (anyone may call it)
```

Three processes, three jobs, deliberately separated:

| Process | Owns | Holds |
|---|---|---|
| `apps/coop-api` (`src/payments.ts`) | the **contract** (`payment_intent`, statuses, idempotency) and the coop's **policy** (`PAYMENTS_DESTINATION`, chain, currency) | no vendor SDK |
| `apps/peer_xyz_payments` (`:3010`) | the **vendor** — SDK, its native deps, its vocabulary, its status mapping | **nothing about the coop**; stateless |
| the provider | the fiat leg, the P2P counterparty, the USDC release | the fiat |

The rail app is **internal only** — no proxy route, no OIDC client, no nav entry. coop-api
calls it on `127.0.0.1` with a derived bearer token. The **only** public surface is the
webhook: `https://pay.<domain>/webhooks/peer`.

**Settlement is learned by webhook and in no other way.** The provider's SDK exposes no order
lookup, so without a working webhook the coop must ask a human whether a payment arrived.

---

## 1. What you cannot derive (prerequisites)

These are the things no amount of code fixes. Gather them before starting.

| # | Prerequisite | Notes |
|---|---|---|
| 1 | **A provider merchant account for the coop**, onboarding **completed**, and **LIVE** for real money | Sandbox is a property of the **key**, not of a URL or a flag. The SDK's base URL is production in both cases. A sandbox key makes gate 1 fail *by design* |
| 2 | The provider **API key** | → vault, `peerpay.api_key` |
| 3 | The **webhook signing secret** | Shown **once**, at webhook creation. Irrecoverable — if you lose it, delete the webhook and create it again |
| 4 | A **funded Base deployer key** in a `0600` file | Never in the tree, never in a transcript, and **never** Hardhat account #0 (`SAFE_BACKEND_SIGNER_KEY` in `apps/coop-api.yaml` is Hardhat #0's *published* key — correct on a throwaway local chain, disqualifying anywhere real) |
| 5 | The **coop's Safe address** on Base | It becomes the router's immutable destination |
| 6 | A decision on **`PAYMENTS_ENTITY`**, or a deliberate decision to leave it unasserted | Statutory bookkeeping, tax and chargeback obligations land on an entity. No code can check this, so the gate is labelled `asserted`, not `checked` |
| 7 | **A backup exists** (R-07 in `docs/RISKS.md`) | Do not move real money with no backup of the records |

**The economics you are switching on:** the provider's markup on the fiat→USDC swap is capped
at **20%** (`maxFeeConfig.valuePercentage`) and is **borne by the payer**, not by the coop —
`feePayer: MERCHANT` covers the merchant fee. So a $25 dues payment can cost up to $5. The
rail is for **access** (people with no on-chain funds), not for routine payment, and the UI
should show the real number before someone pays. irl.coop's own merchant fee is **not
modelled** in the cost model.

---

## 2. Why the destination must be the ROUTER, and not a wallet

This is the part most likely to be got wrong, and the preflight catches it (§8, gate 2).

A rail delivers a plain ERC-20 `transfer`. **USDC has no transfer hook, so no code of ours
runs on arrival** — the tokens simply sit at the destination until someone calls `sweep()`.
That is inherent to ERC-20 and the contract does not pretend otherwise. What it guarantees is
that they can only ever go to **one** place:

| Property | Consequence |
|---|---|
| **No admin** — no owner, no setter, no upgrade path | an admin is a party a state can compel; being uncompellable is the point |
| **Immutable destination** — fixed in the constructor | `sweep()` cannot be aimed anywhere else |
| **Permissionless `sweep()`** | anyone may forward, nobody may redirect: no keeper to compel and none to lose |
| **No `receive`/`fallback`** | ETH cannot be trapped |
| **The deposit event names an OBSERVER, not a payer** | the depositor is unknowable on-chain; a field called `from` would be misread by any indexer |

**Because the router has no admin and an immutable target, the destination needs no key at
all.** That is what dissolves the "who holds the keys to `0x7E11a6…`?" question: with the
router there is no key to hold. Pointing `PAYMENTS_DESTINATION` at a wallet instead
re-introduces exactly the custody problem the design exists to remove — and the preflight will
call it an EOA and refuse.

**One fork you should know you are choosing.** A *shared* coop-wide destination leaks nothing
about which group paid, but a plain ERC-20 transfer carries **no calldata**, so the router
**cannot know which group a deposit belongs to**. A *per-group* router attributes naturally
but tells the provider and the P2P counterparty which group paid. The pool (step 2 of the
money path) is what resolves this. **Until then a shared destination means the coop pools, and
attribution stays off-chain** — which is a decision, not an oversight.

---

## 3. The three secrets

| Secret | Kind | Source | Action |
|---|---|---|---|
| `payments.rail-token` | **derived** (HKDF from `master.key`) | `infra/build/secrets.py` | none — it appears in `out/dev/secrets.env` automatically and both sides read the same value |
| `peerpay.api_key` | **external** | provider dashboard | put it in the vault |
| `peerpay.webhook_secret` | **external** | shown once at webhook creation | put it in the vault immediately |

```
ansible-vault edit --vault-password-file infra/instances/dev/secrets/vault-pass \
  infra/ansible/inventory/group_vars/all/vault.yml
```

Regenerate and restart both processes after the vault changes:

```
uv run --with pyyaml python infra/build/generator.py dev
```

**Note the stale reference:** `peer_xyz_payments.yaml` previously said the webhook secret is
"shown ONCE by `peer-pay-cli webhooks create`". No such binary exists anywhere in this
repository, and the provider's signature scheme is HMAC (see §6), not a custom header. That
comment has been corrected in place; **how you actually create the webhook is provider
tooling or the provider dashboard, and that step is not documented here because it has not
been done from this host.**

---

## 4. Deploy the router to Base

Do the rehearsal first if you want the practice, but understand what it can and cannot prove.

**Base Sepolia proves the CHAIN side** — a real deploy, real gas, a real Safe, real
verification, a real explorer. **It cannot prove the payment rail**: the provider declares
`chains: ["8453"]` and its merchant config carries `destinationChainId: 8453`, so **USDC is
delivered on Base mainnet only**. A Sepolia router can never receive a Peer payment. A real
payment test is a mainnet test. **Do not create real groups on Sepolia** — authority and value
live on the chain, so a Sepolia group is throwaway in a way a mainnet group is not.

```
# 0. ADD THE BASE NETWORK FIRST — it does not exist. hardhat.config.ts defines only `local`
#    and `base-sepolia`, so `--network base` dies with an unknown network even though
#    networks.json carries a verified `base` entry. Add to the `networks` block:
#
#      base: {
#        url: "https://mainnet.base.org",
#        chainId: 8453,
#        accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
#      },
#
#    plus the matching npm scripts — contracts/package.json wires only local and base-sepolia.

# 1. Re-verify the token address ON CHAIN. A token address taken on trust sends funds nowhere.
#    networks.json records how each address was verified and when (base USDC verified 2026-09-13).
cat contracts/networks.json

# 2. Deploy — use the WRAPPER, not deploy_usdc_router.ts directly. The wrapper reads the key
#    from a 0600 file, refuses a world-readable key file and an unfunded deployer, passes the
#    verified USDC address in as ROUTER_TOKEN (the inner script would otherwise deploy a
#    MockUsdc, which on Base is a useless fake token), and never prints the key.
DEPLOY_KEY_FILE=~/.secrets/base.key \
  bash contracts/scripts/deploy_router_testnet.sh base 0x<COOP_SAFE_ON_BASE>

# 3. Verify — the wrapper runs this itself once it parses the address. Read-only.
#    Asserts the chain, that the address is a CONTRACT (not an EOA and not an EIP-7702
#    delegation designator), that the token answers USDC/6, that destination() is what you
#    expect, and that the deployed ABI exposes NO admin surface.
ROUTER_ADDRESS=0x<ROUTER> ROUTER_DESTINATION=0x<COOP_SAFE> \
  npx hardhat run scripts/verify_deployment.ts --network base
```

**The unverified assumption, stated before you rely on it:** the sandbox cannot move real
funds, so it is **not confirmed that the provider delivers by a plain ERC-20 `transfer`**. If
it delivers by calling a contract method, the router could act on receipt instead of waiting
for a sweep. Check this before relying on the sweep model.

---

## 5. Configure the stack

`infra/instances/dev/apps/peer_xyz_payments.yaml`:

| Variable | Value |
|---|---|
| `PEER_XYZ_PAYMENTS_PORT` | `3010` |
| `RAIL_AUTH_TOKEN` | `${SECRET:payments.rail-token}` — already wired |
| `PEER_PAY_API_KEY` | `${VAULT:peerpay.api_key}` |
| `PEER_PAY_API_BASE_URL` | `https://api.pay.peer.xyz` |
| `PEER_PAY_CHECKOUT_BASE_URL` | `https://pay.peer.xyz` |
| `PEER_PAY_WEBHOOK_SECRET` | `${VAULT:peerpay.webhook_secret}` |
| `COOP_API_URL` | `http://127.0.0.1:3001` |

`infra/instances/dev/apps/coop-api.yaml`:

| Variable | Value | Note |
|---|---|---|
| `RAIL_URL` | `http://127.0.0.1:3010` | neutral naming — the provider's name belongs in the rail app |
| `RAIL_ID` | `peer` | |
| `RAIL_AUTH_TOKEN` | `${SECRET:payments.rail-token}` | one trust boundary, both directions |
| **`PAYMENTS_DESTINATION`** | **the ROUTER address from §4** | currently `0x7E11a6…`, which must be replaced by the deployed router or gate 2 will fail |
| `PAYMENTS_CHAIN_ID` | `8453` | gate 4 asserts exactly this |
| `PAYMENTS_CURRENCY` | `USDC` | |
| `PAYMENTS_RPC_URL` | optional | defaults to `https://mainnet.base.org`; the preflight reads the chain through it |
| `PAYMENTS_ENTITY` | the registered name, or leave unset | unset is recorded as `unasserted`, never as passed |

The code **refuses to create a payment** if the destination is missing or is not an address,
rather than let a rail fall back to the provider's default. That is the right failure mode;
do not work around it.

---

## 6. Register the webhook

Point the provider at `https://pay.<domain>/webhooks/peer`.

The provider **signs** its deliveries:

```
X-Webhook-Signature: hex( HMAC-SHA256( secret, "<X-Webhook-Timestamp>.<rawBody>" ) )
X-Webhook-Timestamp: <unix seconds>        # 300s replay window
X-Webhook-Id:        <event id>
```

Two details are load-bearing, and both cost a debugging cycle to learn:

1. **The raw bytes must be signed.** Re-serialising the parsed JSON changes them and the
   signature can never match — which is why `server.ts` installs a content-type parser that
   keeps `rawBody`.
2. **Two separate checks are required.** The signature proves *the provider sent this*; the
   `X-Webhook-Id` is what makes a retry idempotent. The provider reuses the **same** id across
   all 7 retry attempts with a **fresh** signature. `rail_event` dedupes on `(rail, event_id)`.

The route returns **500** when coop-api cannot record a delivery, deliberately, so the
provider retries. Losing a settlement notice silently is the failure mode worth being loud
about.

**Reversals arrive this way too.** The provider's own types carry nineteen event types, and
the ones that matter most are not "fulfilled": `PAYMENT_CHARGEBACKED`,
`ORDER_PARTIALLY_CHARGEBACKED`, and the `REFUND_*` family. That is the T+130 window arriving
as data, and it fixes what a receipt means: **"funds arrived", never "funds are final".**

---

## 7. Sweep — the step nothing automates

**Grep the whole repository and you will find nothing that calls `sweep()` in production.**
Only `contracts/scripts/deploy_usdc_router.ts` and the tests do. So:

> After a deposit lands in the router, the funds sit there until a human calls `sweep()`.

That is by design — a permissionless sweep is what removes the keeper who could be compelled
or lost — but it means a first-time deployer **must know this step exists**, because nothing
will tell them. `verify_deployment.ts` prints a hint (`INFO the router currently holds N…;
sweep() is permissionless`) and nothing more.

Whoever operates the first live payment needs:

- a way to **call `sweep()`** (any funded account, including one with no other role);
- a way to **watch the router's balance** (`DepositNoted(observer, amount)` exists precisely so
  the coop can learn a payment arrived without asking the provider);
- a **written answer to who sweeps, and how often**. Currently there is none.

---

## 8. Prove it — the preflight loop

```
curl -s https://api.irl.coop/api/v1/payments/preflight | jq
```

| # | Gate | Kind | Satisfied by |
|---|---|---|---|
| 1 | `live-merchant` | **checked** | the provider environment is `LIVE` and onboarding is complete. The rail's `/merchant` is the only honest source — never a config flag |
| 2 | `destination-is-a-contract` | **checked** | the destination has contract code on Base. An EOA or an **EIP-7702 delegated EOA** fails — a delegated EOA still has a 23-byte designator (`0xef0100…`) and is *a person's account*, which is the false green this check was written to catch |
| 3 | `destination-is-not-the-default` | **checked** | the destination differs from the merchant's own default wallet (`v1EvmWalletAddress`). In the sandbox that default **is** the merchant's wallet, so a naive setup sends member money to a wallet the group does not control |
| 4 | `chain-is-base` | **checked** | `PAYMENTS_CHAIN_ID` is `8453` |
| 5 | `webhook-evidenced` | **checked** | `coop_rail_event_count() > 0` — at least one signed delivery has been accepted. Read through a `SECURITY DEFINER` count because `rail_event` is FORCE RLS with no policies; a failed read reports *"cannot answer"*, never *"nothing arrived"* |
| 6 | `operating-entity` | **asserted** | `PAYMENTS_ENTITY` is set. Labelled an assertion because no code can know whether a coop legally exists |

**Gate 5 is chicken-and-egg, and that is the point.** It cannot pass until a real signed
delivery has arrived, so the first live payment *is* the test. Hence the shape you chose:
small real amounts, written risk bounds, and a named person accountable. There is no way to
make gate 5 green in advance, and pretending otherwise would be the most dangerous false green
in the set.

**Two product truths the rail forces, worth knowing before you promise anything:**

- `checkQuoteAvailability` is **server-side only and advisory** — it probes live liquidity and
  reserves nothing, so order creation can still fail with `NO_QUOTE` (HTTP 409). A P2P rail has
  no guaranteed counterparty, so **"pay by card" is never a guaranteed path** and the UI must be
  able to say so.
- `PARTIALLY_FULFILLED` is a real state. **"The money arrived" is not boolean**, which is why
  `partial` is a first-class status in `payment_intent`.

---

## 9. Gaps and contradictions found while writing this

Recorded rather than smoothed over.

| # | Finding |
|---|---|
| 1 | **No `peer-pay-cli` exists in this repo**, though the rail's config comment referenced one. Webhook creation is provider tooling or the dashboard, and **that step is undocumented here** — it has not been done from this host. `money-in-and-out.md` records the same limit: *"no route exists (this is a verified sandbox call, not an integration)"* |
| 2 | **The webhook-signature comment in `peer_xyz_payments.yaml` was wrong** (it claimed a custom header and "no signature scheme"). Corrected; the root error was reading the SDK's TypeScript types as the provider's contract |
| 3 | **Nothing sweeps the router** (§7). No production caller of `sweep()` exists |
| 4 | **`PAYMENTS_DESTINATION` is `0x7E11a6…`, and nothing in the repo or docs says what it is** — a contract or a wallet. If it is a wallet, gate 2 fails and real money would land in a key a person holds. This is the same question as the custody gap in `docs/RISKS.md` R-11, seen from the code side |
| 5 | **Whether the provider delivers by plain ERC-20 `transfer` is unverified** — the sandbox cannot move real funds, and the sweep model depends on it |
| 6 | **`apiKeyIpAllowlist` is empty** on the merchant. Worth setting to the host's egress IP before going live |
| 7 | **The merchant fee is not modelled** in the cost model |
| 8 | `STRIPE_SECRET_KEY` is still empty in `hievents.yaml` (events can't take payment), and `money-in-and-out.md` §5.2 is explicit that the fix is **not** to point groups at personal payment accounts — that is a governance regression |
| 9 | **Base mainnet is not a configured hardhat network.** `hardhat.config.ts` defines only `local` (chainId implicit) and `base-sepolia` (84532). `networks.json` has a verified `base` entry, but the hardhat side does not — so `deploy_router_testnet.sh base …` fails on an unknown network, and `contracts/package.json` has no `base` script either. **The mainnet deploy path has never been runnable from this repo as it stands.** The chain deployment that was proven on 2026-09-13 was the LOCAL chain |

---

## 10. Do not

- **Do not set a wallet as the destination.** It is the platform holding member money, and it
  re-creates the custody problem the design removes. Gate 2 audits this.
- **Do not infer the environment from a config flag or a URL.** The environment is a property
  of the key. A "sandbox mode" variable that disagrees with the key is the failure that spends
  real money.
- **Do not create real groups on Sepolia.** Authority and value live on the chain and do not
  survive a move.
- **Do not create the coop's own group before the Base switch is done.** Otherwise the founding
  Safe — with real members, real governance and real funds — is itself a throwaway.
  (`money-in-and-out.md` §5.1; ordering constraint in `coop-launch-and-roadmap-handoff.md`.)
- **Do not let the platform ever hold or intermediate member funds** — §4 of
  `money-in-and-out.md`. It is the one decision that keeps every other money property intact,
  and it is regulatory, not merely a value.
- **Do not treat a sandbox success as proof the rail works.** The sandbox can create an order
  and return a checkout URL; it cannot complete a real settlement.
- **Do not put the deploy key anywhere but a `0600` file.** It never enters a transcript, a
  shell history, or the tree.

---

## Order of operations, in one list

1. Provider merchant account, onboarding complete, **LIVE** key in hand.
2. API key and webhook secret into the vault.
3. Funded `0600` deployer key on Base; confirm the coop's Safe address.
4. **Add the `base` network to `contracts/hardhat.config.ts`** (it does not exist); re-verify
   base USDC on-chain; deploy the router via the wrapper with the Safe as its immutable
   destination; run `verify_deployment.ts`.
5. Set `PAYMENTS_DESTINATION` to the router; regenerate; restart coop-api then the rail.
6. Create the webhook against `https://pay.<domain>/webhooks/peer`.
7. Confirm `/api/v1/payments/rails` and `/merchant` answer; decide who sweeps and how it is
   watched.
8. Write the risk bounds, the amount cap and the named accountable person; take a backup.
9. One small real payment. `preflight` gates 1–4 green before it; gate 5 goes green because of
   it.