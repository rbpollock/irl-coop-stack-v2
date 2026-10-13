# The payment seam — a stub rail, and the checkout handoff

Status: design · 2026-10-04 · Robbie + Hermes.
Question: *"ecommerce is kinda critical. we can imagine the payment path is designed or stubbed, or we can do
a spike that connects it."*
Answer: **do both, in that order — and the seam that makes it cheap already exists.**
Companions: `PAYMENTS-SETUP.md` (the runbook, derived from the code) · `money-in-and-out.md` §3.7 (the
live-sandbox record and its four traps) §4 (never intermediate funds) §5.2 (no personal payment accounts) ·
`site-plugins-and-embeds.md` §2.1 (the ecommerce row this unblocks) · `RISKS.md` R-07 (backups) R-11
(custody).

## 0. The seam already exists — this is not a rewrite

`apps/coop-api/src/payments.ts` opens by stating the split, and it is already the design we would ask for:

> coop-api holds the **contract** and the **policy**; the rail service holds the **provider**. *"Nothing
> vendor-specific appears here — no SDK, no provider status vocabulary, no provider field names. Swapping
> providers means pointing `RAIL_*` at a different app; a swap never touches this file."*

- `IntentStatus` is **ours**: `pending | partial | settled | cancelled | failed | unknown` — and `partial`
  is first-class, because *"the money arrived" is not boolean*.
- `policy()` **refuses to create a payment** if the destination is unset or not an address, rather than
  letting a rail fall back to a provider default.
- `railCapabilities()` **refuses any rail that intermediates funds** — "not a warning… unusable by
  construction rather than by policy."
- The **acceptance test already exists**: `GET /api/v1/payments/preflight` → six gates; `ready` is true
  only when all six pass.

So a stub is not new architecture: **it is a second implementation of an interface that already has one**,
and the spike is config + keys + one payment.

## 1. What exists vs what is actually missing

| Exists (built, sandbox-verified) | Missing |
|---|---|
| the intent contract + status vocabulary | a **LIVE** provider merchant account (the environment is a property of the *key*) |
| the policy refusal + the rail-capability refusal | `peerpay.api_key` and `peerpay.webhook_secret` in the vault |
| the **webhook receiver**: HMAC over raw bytes, 300s replay window, `(rail, event_id)` idempotency, **500-on-failure so the provider retries** | a funded `0600` Base deployer key (human-created) |
| reversals as data — `PAYMENT_CHARGEBACKED`, `ORDER_PARTIALLY_CHARGEBACKED`, the `REFUND_*` family | the coop's **Safe address on Base** |
| `CoopUsdcRouter.sol`: **no admin, immutable destination, permissionless `sweep()`**, no `receive`/`fallback` | **nothing calls `sweep()` in production** |
| | `PAYMENTS_DESTINATION` = `0x7E11a6…` — **answered live 2026-10-04 (§8)**: an EIP-7702 delegated EOA **and** the merchant's own default wallet |
| | whether the provider delivers by plain ERC-20 `transfer` — **unverified (§9)** |
| | a `PAYMENTS_ENTITY` decision, and a backup (R-07) |

## 2. First: the stub rail

A second rail app answering `/rails`, `/merchant` and order-create, and posting a **signed** webhook at the
same route. It exercises the whole contract — including the parts that are expensive to build later:
`partial`, chargeback, refund.

**The one rule that keeps it honest: the stub may never make `preflight.ready` true.** It reports
`rail: "stub"`, and gate 1 reads the merchant environment — a stub cannot be `LIVE`. A stub that reports
ready would be the **false green** the runbook warns about in three separate places (*"do not infer the
environment from a config flag"*, *"the sandbox can create an order… it cannot complete a real settlement"*,
*"do not treat a sandbox success as proof the rail works"*).

**What it unlocks, verifiably today:** catalogue → cart → intent → checkout handoff → confirmation state →
order record → the site widget, **plus every reversal path**.

## 3. The checkout handoff — how ecommerce works on a site at all

The site never takes the card (`money-in-and-out.md` §5.2). The flow:

```
site widget            coop-api                 the coop's own checkout        rail → Base
catalogue (read)  ──▶  POST /payments/intent ──▶ {slug}.irl.coop/checkout ──▶  provider ──▶ router ──▶ Safe
cart (client)                                        (the money leg lives here)
   ▲                                                                              │
   └──────────── widget shows state on return, from the intent ───────────────────┘
```

So the site's ecommerce work is **unblocked by the stub**; only the money leg waits. And one recorded
consequence to keep: with a **shared** destination the router cannot know which group paid (a plain ERC-20
transfer carries no calldata), so the coop pools and **attribution stays off-chain until the pool exists** —
a decision, not an oversight.

## 4. Then: the spike, in phases

| Phase | What it proves | Needs |
|---|---|---|
| **1. Sepolia rehearsal** | deploy + `verify_deployment.ts` + **a sweep from a throwaway key** — the chain side and the tooling | a funded `0600` Sepolia deployer key *(human-created)* |
| **2. Mainnet deploy** | the real router, the coop's Safe as its immutable destination, verified on Base | funded `0600` mainnet key + the coop's Safe address |
| **3. Webhook + first payment** | **the rail itself.** Gate 5 goes green *because of* it — **the first live payment is the test** | LIVE merchant account; key + webhook secret in the vault; the webhook created in the provider dashboard |

**A Sepolia router can never receive a Peer payment** — the provider declares chain `8453` only. Phase 1
proves the tooling, never the rail.

**What the spike forces to be decided (currently unrecorded):**

- **Who sweeps the router, and how is it watched?** Nothing in the repo calls `sweep()` in production.
  The step exists, is permissionless, and is documented as a step a human must know about.
- **What is `0x7E11a6…`?** If it is a wallet rather than the router, gate 2 fails and real money lands in a
  key a person holds — R-11's custody gap, seen from the code side. **Answered 2026-10-04: it is exactly
  that (§8).**
- **`PAYMENTS_ENTITY`** — asserted or deliberately unasserted (recorded as `unasserted`, never as passed).

## 5. What a stub cannot tell you — say it before it is discovered

- whether the merchant account will be **approved at all**;
- **how the provider delivers** (a plain ERC-20 `transfer` vs a contract call) — the whole sweep model
  depends on it, and the sandbox cannot show it;
- **real reversals**: `T+130` chargebacks. *"Funds arrived", never "funds are final."*
- **liquidity**: `checkQuoteAvailability` is server-side and advisory, reserves nothing, and order creation
  can still fail `NO_QUOTE` (409) — **"pay by card" is never a guaranteed path**, so the UI must be able to
  say so;
- **the fee reality**: the provider's swap markup is capped at **20% and borne by the payer** — a $25 dues
  payment can cost $5. The UI must show the real number before someone pays, and **the coop's own merchant
  fee is still unmodelled**.

**The stub proves the flow. Only a real payment proves the money.**

## 6. Sequencing

1. **Stub rail + the handoff** — cheap, unblocks all ecommerce product work, and builds the reversal paths.
2. **Sepolia rehearsal** — the chain tooling, with a throwaway key.
3. **Mainnet deploy + sweep tooling**, and decide who sweeps.
4. **One small real payment** — the seven prerequisites are the only gate, and gate 5 turns green because
   of it.

## 7. Decisions

| # | Decision | Recommendation |
|---|---|---|
| 1 | A stub rail as a second app behind the existing contract? | **Yes** — and it must never be able to report `ready` |
| 2 | Does a site ever take the card? | **No.** Catalogue → cart → handoff; the widget's job ends at the URL |
| 3 | Who sweeps, and how is it watched? | **Decide before phase 3** — it is unrecorded today |
| 4 | `PAYMENTS_ENTITY` | Assert it, or record it deliberately unasserted — never "passed" |
| 5 | Which of the seven prerequisites can you supply now? | That single answer sets the date on phase 3 |
| 6 | **Router ABI: plain-transfer-only, or transfer *plus* a deposit-noting function?** | **Support both** — and decide **before** the first mainnet deploy, because there is no upgrade path (§9) |

## 8. The live preflight, read 2026-10-04 — 2 of 6 green

```
GET https://api.irl.coop/api/v1/payments/preflight   →  ready: false
```

| Gate | State | Detail (from the endpoint) |
|---|---|---|
| 1 `live-merchant` | ✗ | provider environment is **SANDBOX**, onboarding NOT completed |
| 2 `destination-is-a-contract` | ✗ | `0x7E11a6…` **is an EIP-7702 DELEGATED EOA** — *"its 23-byte code is a delegation designator (0xef0100…), and the account is still controlled by a key"* |
| 3 `destination-is-not-the-default` | ✗ | **the destination IS the merchant's own wallet** — the provider's default |
| 4 `chain-is-base` | ✓ | `8453` |
| 5 `webhook-evidenced` | ✓ | **23 verified provider events recorded** — a signed delivery has been accepted |
| 6 `operating-entity` | ✗ | unasserted |

**Three things this settles:**

1. **The open question in `PAYMENTS-SETUP.md` §9 finding #4 is answered — and it is the concerning
   answer.** The destination is not the router: it is a **delegated EOA** *and* simultaneously the
   **provider's default merchant wallet**. Member money would land in an account a person still controls,
   via the merchant's own fallback. Gates 2 and 3 exist precisely to catch this, and both caught it.
   **Do not send real money until the destination is the deployed router.**
2. **The webhook leg is real, not aspirational.** 23 signed deliveries accepted means the HMAC-over-raw-bytes
   verification, the replay window and `(rail, event_id)` idempotency have all survived real traffic. That
   is usually the hardest part of a payment integration, and it is already proven.
3. **The stub cannot move a single one of these gates** — 2/3 need a deployed router, 1 needs a LIVE key, 6
   needs a decision. That *is* the stub's honesty rule (§2) confirmed against live data: the stub lets
   product work proceed while every gate stays honestly red.

## 9. Delivery method: a plain `transfer`, or a contract call?

The runbook's §4 flags this as unverified: *"the sandbox cannot move real funds, so it is not confirmed that
the provider delivers by a plain ERC-20 `transfer`."* Robbie's read (2026-10-04): *"we can count on a plain
ERC-20 transfer, although a call would give us a lot more information (like a hash with the details)."*

**Attempted on-chain verification, same day: not available from this host.** Outbound JSON-RPC is blocked
(five public Base endpoints, all refused). Note that **coop-api can read the chain** — the preflight read
code at the destination through its own RPC — so the check *can* run through the stack's RPC rather than a
public one. Until then, the honest state is **unverified**, and we cannot "count on" anything: the delivery
method is *their* code.

### 9.1 Why this has a deadline — the deadline is the good part

The router has **no admin and no upgrade path**, and the destination is **immutable in the constructor**.
That is exactly why it has no custody problem — and it also means **no function can be added later without
redeploying the router and re-pointing `PAYMENTS_DESTINATION`**. Whatever the ABI should be, it must be
**final before the first mainnet deploy**. Decide once; deploy once.

### 9.2 Read the ABI first — `noteDeposit()` already exists

`CoopUsdcRouter` is 88 lines, and it **already carries the observation mechanism**:

```solidity
function noteDeposit() external { emit DepositNoted(msg.sender, token.balanceOf(address(this))); }
```

Permissionless, emits the *amount held*, and names the **observer** — deliberately never a payer, because
*"a field called `from` would be read as 'the payer' by anyone indexing this."* So **observation needs no
change at all**: any watcher records that a deposit landed, without asking the provider — which matters
because *"this provider's API cannot be polled at all."*

But the same contract states the assumption as fact:

> *"The rail will not call this (nothing calls into us — see the contract note)."*

**That sentence is the thing actually under test in §9.**

**And the real risk is not lost information — it is a failed delivery.** If the provider delivers by
*calling a method* and the router has no matching selector, the call **reverts** and the delivery fails: the
payment never lands. "We would get less information" understates the hazard.

**The cheap pre-deploy hedge: a no-op `fallback()` that refuses value** (`if (msg.value > 0) revert;`), doing
nothing otherwise. It keeps the *"no native value can be trapped here"* property **and** converts an
unexpected provider call from *reverting* into *harmless* — one function, no change to any custody property.
It must be decided before the deploy, because the destination is immutable.

**A commitment-carrying function is only worth adding if we *know* they call.** Otherwise it is dead code on
a contract with no upgrade path — and this ABI's real virtue is being tiny.

**And if a call ever does happen, the calldata must carry a *salted commitment*, never an identifier.**
Calldata is public. A group id in calldata would be *worse* than a plain transfer, because it publishes
attribution permanently. A salted hash is a commitment only the coop can open — which is exactly Robbie's
*"a hash with the details"*, stated safely: on-chain attribution, opaque record.

### 9.3 The alternative that needs nobody's cooperation: a per-intent deposit address

If they do plain transfers and we still want attribution, attribution can come from **which address
received** rather than from calldata — a distinct destination per intent, mapped to the order off-chain.
No cooperation required, and the address↔order map stays off-chain, so nothing about the group is public.

Honest caveats: (i) it requires the provider to allow a **per-order destination**, which is unknown — the
merchant config currently carries a *single* destination plus a default wallet, suggesting one per merchant;
(ii) a deploy and a sweep per address (gas on Base is cheap, not free); (iii) it changes the destination
model, so it is a pre-deploy decision too.

### 9.4 Either way it is not a blocker

- **Plain transfer** → attribution is resolved by **the pool** (already step 2 of the money path), and stays
  off-chain until then.
- **A noting call** → attribution is on-chain, immediately.

So the branch changes *when* attribution is available, never whether the rail works. Which is why the cheap
hedge wins: **build the noting function into the router and let reality decide** — the plain-transfer path
keeps working either way, and a redeploy is the one thing we cannot do cheaply.

## Cross-references

- `PAYMENTS-SETUP.md` — the runbook; §9 lists the gaps, four of which are still open above.
- `money-in-and-out.md` §3.7 / §4 / §5.2 — the sandbox record, the never-intermediate rule, the no-personal-accounts rule.
- `site-plugins-and-embeds.md` §2.1 — the ecommerce row this unblocks.
- `docs/design/coop-launch-and-roadmap-handoff.md` — the ordering constraint (no real coop group before the Base switch).
- `RISKS.md` R-07 (backup before real money), R-11 (custody).