# Cross-chain action: one authority, many places to act

Status: design · 2026-09-29 · the refinement that separates **authority** from **reach**.
Related: `chain-agnostic-identity.md` (CAIP identities), `multi-chain-accounts.md` (cross-chain
signing), `base-indexing.md` (indexer scope), `account-and-key-model.md` (guards, session keys),
`money-in-and-out.md` (§4: the platform never intermediates).

## 0. The refinement

> **Base stays the canonical home for the group's Safe — and that Safe is allowed to act on and
> through accounts on other chains.**

Formally: **authority is canonical, reach is peripheral.** The Base Safe holds the owner set,
the threshold and the book of record. A peripheral chain holds accounts the group *acts through*,
which are governed by rules *declared* on Base and *enforced* locally.

This is the right shape, and it also dissolves the tension in `multi-chain-accounts.md`: you do
not need the authority to be everywhere, only the *reach*.

## 1. Three control topologies — pick deliberately

How a Base authority controls an account on another chain is not one thing. The options differ
enormously in trust cost.

| Topology | Mechanism | Cost |
|---|---|---|
| **Mirrored authority** | the peripheral account is a native multisig whose key set is the **same member keys** | simplest and most native, but **authority is duplicated, not derived**: the two owner sets can diverge silently, and every membership change is ×N |
| **Bridged authority** | the peripheral account accepts a message from Base, so the Base threshold *is* the authority | the honest model, but it requires a **message bridge** — a trust assumption and a target |
| **Declared delegation** (recommended) | the peripheral account is a contract whose rules were **declared** on Base, enforced **locally**, and **time-bounded** | no bridge; the peripheral chain enforces its own guard. Revocation is by *expiry*, not by message |

**Recommendation: declared delegation with local enforcement**, using the pattern the design
already has (guard + session key: the scope is declared, the enforcement is local, and the
permission "expires on its own"). Mirrored authority is the fallback where a chain cannot
enforce rules; bridged authority only where a genuine dialogue is needed.

**And there is no ready bridge from Base to Tezos.** A search of Base's own documentation returns
L1↔L2 messaging (`CrossDomainMessenger`, the `OptimismPortal` with its 7-day challenge window)
and a Base↔Solana bridge — **nothing for Tezos.** A Base→Tezos message path would mean a
purpose-built bridge or a third-party validator set. That is a real, ongoing trust and
maintenance commitment, and it is the single strongest argument for the declared-delegation
topology here.

## 2. The worked example: an NFT listed on objkt.com

The group lists an NFT on objkt, the account is group-controlled rather than an individual's, and
the proceeds propagate toward the main Safe.

### The mechanics, as they actually are

| Fact | Consequence |
|---|---|
| **Listing works by an FA2 operator grant.** On Tezos, `update_operators` adds the marketplace contract as an operator of the token — and objkt's marketplace contract (`KT1Xjap1…MrPZY`) is documented as an operator on essentially every listed token | listing is a **transaction from the owner** granting operator rights, plus the marketplace-side listing record |
| Therefore **the group's account must hold the NFT** | the group's Tezos presence is not a passive receiver; it is the holder and the seller of record |
| **A `tz1` implicit account cannot enforce anything** — no code, no rules, no local guard | the group's Tezos presence **must be a `KT1` contract wallet** with a generic execute entrypoint (so it can call `update_operators` and the marketplace) plus its own local rule set |
| A `KT1` holding an operator grant means **the marketplace can move the token** | the local contract's rules must cover what may be listed, at what floor, and by whose authority |

*Prior art, noted as an example rather than a standard:* a Tezos contract with
`administrator`/`coreParticipants`/`shares` and an `update_operators` path exists on-chain
(`KT1L9XpR…Jc4qm`) — i.e. a multi-participant contract that mints and lists objkt NFTs. Worth
reading before writing one; not a specification.

So the Tezos side needs **writing**, in a Tezos language (LIGO/SmartPy/Michelson). That is a new
skill surface for this project, and it should be sized honestly rather than waved at.

### What the group's Tezos contract must encode

- **Who may act** — participants or a threshold, mirroring *a declared subset* of the Base
  authority (not necessarily all of it).
- **What they may do** — the local guard: which collections, floor prices, whether transfers are
  allowed, daily limits. The analogue of `SessionKeyModule` + a `TransactionGuard`.
- **For how long** — an **expiry**. This is the load-bearing piece; see §5.
- **What it must never do** — accept arbitrary calls. The Base-side lesson from
  `account-and-key-model.md` (a guard on `delegatecall`) applies with more force here: a generic
  execute entrypoint is a custody risk unless constrained.

## 3. Proceeds: three ways value crosses, and what each costs

An earlier version of this section said value "cannot reach Base without a bridge or a custodian"
and ruled the second out as forbidden. **That was too absolute, and the distinction it missed
matters.** The prohibition is on *the platform* holding or intermediating member funds
(`money-in-and-out.md` §4) — not on a group choosing an external service for its own account.
Corrected, there are three paths:

| Path | In-flight custody | What you trust |
|---|---|---|
| **Bridge** | none — a message and a proof | the bridge's validator / light-client set |
| **Swap service** (ChangeNOW, FixedFloat, StealthEX, SimpleSwap, Godex; aggregators like Trocador route between them) | **the in-flight amount sits at a deposit address the service controls, for seconds to minutes.** The honest description is "non-custodial — no account, no balance — but the swap is mechanically routed through an address they hold" | the service: it can fail, refund late, or flag and hold |
| **Working float** | none — value never crosses | a second place value sits, with its own accountability gap |

All three are legitimate. They differ in **what** you trust and **for how long**, not in whether
trust exists. The swap-service path is cheaper and more practical than it first appears, and
reverse-direction (Base → Tezos) is arguably the more valuable flow, because it is how a group
**funds** peripheral operations from its treasury.

**Recommended default: Base is the book of record; the peripheral chain holds a float**, funded
and drawn down deliberately through one of the three paths above.

1. **Name the float limit** — how much value may sit on a peripheral chain, and who is
   accountable for it. An unbounded float is an unaudited treasury in a second place.
2. **Record the sale on Base anyway.** What *can* bubble up trustlessly is **the record**: the
   sale commits into a Tier-2 period root anchored to Base. So "the group sold this for N" is
   **provable without being published** — which is exactly what the anchor design already does.

## 3b. Using a swap service — four things decide it, and one is already forbidden

**Frame it as the product actually needs: an internal transfer.** A group's accounts are
**surfaces it acts through**, so moving value between two of them is *one operation to the group* —
"move 200 XTZ from my Tezos account to my Base account" — not "use a bridge" or "do a swap". The
group already has *"one unified approval inbox across all of the user's Safes"*
(`account-and-key-model.md`); a cross-chain move belongs in that same inbox, with the same approval
shape. The swap service is an implementation detail behind the operation, and it should stay
invisible at the surface.

The API is real and usable. ChangeNOW: `POST https://api.changenow.io/v2/exchange` with an
`x-changenow-api-key` header, alongside `/exchange/estimated-amount`, `/exchange/min-amount`,
`/exchange/range`, `/exchange/by-id` and `/exchange/currencies`. The flow is quote → `POST
/exchange` returns a **deposit address** → funds are sent → the swap pays out to the destination.
Status lifecycle: `waiting, confirming, exchanging, sending, finished`.

### 1. The rail seam already excludes this class — on purpose

`apps/peer_xyz_payments/src/server.ts` refuses any rail that is not `directToDestination`:

> `rail ${caps.rail} is not direct-to-destination; the coop does not intermediate member funds`

and `money-in-and-out.md` §3.7 states the intent: *"a rail that would hold funds itself is
refused by the seam, so the invariant 'the platform never intermediates' is enforced rather than
documented."* A deposit-address swap service **is** a rail that holds funds, briefly.

**So this cannot be added as an exception.** It needs an **explicit capability** — for example
`intermediatesFunds: true` with `inFlightCustody: 'seconds-to-minutes'` and a recorded
per-group acknowledgement — so the relaxation is *visible in the capability declaration* instead
of quietly skipped. The existing seam is the reason this is a design decision rather than a
config line; keep it that way.

### 2. One shared partner key is correct — and the key is not authority over funds

**Corrected.** An earlier version of this section argued for per-group API keys. That was wrong:
this is precisely what irl.coop's **shared-infrastructure model** is *for*, and thousands of
provider accounts would be absurd.

The precedent already exists and is load-bearing: the platform holds `peerpay.api_key` in the
vault, and the rail app calls the provider on behalf of **every** group. A shared ChangeNOW partner
key is the same pattern, not a new transgression.

What makes it safe is a distinction worth stating plainly:

> **A partner API key is not authority over funds.** `/exchange` returns a *deposit address*; the
> funds move only when the group's own account signs the deposit transaction. The key can create
> orders. It cannot move money.

So the key belongs to the platform, **authority** stays with the group's account, and the two are
not in competition. That is the shared-infrastructure model working as designed.

### 2b. Revenue from swap action is affiliate income, not money transmission — DECIDED

An earlier version of this section warned that being paid per transfer "starts to look like money
transmission." **That was overstated**, and the correction is worth recording because the
*reasoning* is what matters:

| Factor | In this flow |
|---|---|
| Does irl.coop ever accept or hold the funds? | **No.** The group's own account sends to a deposit address the *provider* controls, and the provider pays out |
| Does irl.coop have discretion over the funds or the recipient? | **No.** The group names the destination, and its own account signs the send |
| Is irl.coop paid for arranging? | **Yes** — a partner revenue share |

Money transmission turns on **possession and discretion**, not on being paid. Payment alone does
not convert software into a transmitter — otherwise every wallet, dApp or agent that embeds a swap
API would be an MSB, and the provider's own product is explicitly aimed at *wallets, Web3 platforms
and exchanges* embedding swaps. **This is the affiliate/referral pattern.**

**Decision: irl.coop may take the revenue share.** The coop has no income and pricing is an unmade
governance decision (`cost-model.md`), so this is a legitimate first revenue line from the money
path.

**The one boundary to hold — and it is not the commission:**

> **Possession.** The moment irl.coop accepts funds first and forwards them, everything above
> inverts. That is precisely the line `money-in-and-out.md` §4 already draws — *"the platform never
> holds, moves, or intermediates member funds"* — and it is why the pool must be a **contract the
> coop's own Safe owns**, operated as software, not a wallet an operator holds. **Custody would be
> the risk; the fee is not.**

Two things that are real, and different from transmission: a provider flagging an address can hold
a group's funds mid-swap (an operational exposure, not a licensing one), and counterparty contracts
may impose their own conditions. Neither is a reason to refuse the revenue.

### 2c. Three roles, and only one of them makes the coop a counterparty

**There is no shared pool in ZKP2P to put money into.** It is an **order book of discrete escrowed
deposits**: a seller ("maker") escrows USDC in a contract and sets a rate, payment platforms and
limits — *"like an Airbnb host sets price, dates, and rules"* — and a buyer ("taker") picks a
specific deposit and signals an intent against it. Each deposit is a **named offer**, and one of the
seven on-chain invariants is *"correspondence of the deposit to the correct off-ramper."*

So the role that involves capital does make the coop a counterparty — but **only to the trades
matched against its own deposit, and only when a buyer takes it.** Not to swap action in general.
Corrected: the coop **could be** a counterparty; it is not structurally one.

| Role | Counterparty? | Capital at risk | Fit |
|---|---|---|---|
| **Affiliate / referrer** — `referrer` + `referrerFee` are first-class in `signalIntent` (≤50%, paid out of the buyer's amount). ZKP2P V3 states outright that *"protocols who integrate ZKP2P can finally monetise and earn through affiliate fees"* | **No** | **None** | The §2b path with a concrete mechanism — but note the fee comes **out of the buyer's USDC**, so on a member's own swap the member pays it. Disclose it |
| **Gating service** — decides which buyers may hit coop liquidity; *"does not custody or touch funds ever"* | **No** | **None** | Policy without custody, which is the coop's shape. Membership rules as a live filter |
| **Maker** (escrow liquidity) | **Yes — on matched trades only** | **Committed capital.** USDC locked in escrow while offers are open; *"no promised returns"*, *"on days without buyer demand you may earn nothing"*, and it is *"not lent out or put to work anywhere else"* | A treasury decision: cap it, own it, accept contingent revenue against committed capital |

**The affiliate and gating roles are the ones worth naming**, because they give the coop revenue and
policy influence **without taking a position** — and they fit a platform that is deliberately not a
counterparty. Being a maker is the one that puts coop capital inside the rail, and it should be
evaluated as such rather than as a revenue switch.

Worth noting for §2b: **the referrer mechanism makes the affiliate path native.** The coop does not
have to negotiate a partner deal to earn from swap activity — the protocol pays it by construction.

### 3. Programmatic, not browser automation

A partner API exists, so browser automation has no advantage and carries specific failure modes:

| Failure | Why it matters here |
|---|---|
| **Funds in flight when the UI breaks** | the API returns a deposit address and the funds leave. If the automation then cannot drive the payout, money sits at a deposit address and a human must recover it. **This is the worst failure mode available** |
| **Prompt injection with spend authority** | a browser agent reading untrusted page content while able to move money is the classic agentic-wallet failure. `mcp.ts` is deliberately read-only for exactly this reason — *"write-capable agents are the high-risk class"*. Granting a browsing agent spend authority contradicts an existing, deliberate safety posture |
| **Opacity vs the audit trail** | the API yields a transaction id, a status lifecycle and a record; the UI yields screenshots |
| **Fragility and terms** | driving a human UI is brittle and likely contrary to terms, with no upside to offset it |

**So: its own app, behind the rail seam, programmatic, with per-group credentials that are
time-bounded and capped** — the session-key pattern, because that is what bounds the blast radius
of a key that can move money. *"Permissioned browser automation"* is a fallback only where no API
exists, and never with unattended spend authority.

### 4. Batching through the pool removes the link — and the pool is the load-bearing piece

**Corrected, and this is the more interesting half.** An earlier version treated the privacy cost
as dominant. It is not — *provided the destination the provider is given is not the group's Safe*.

What a provider learns on each order is the **source** and the **destination** it was told. If the
destination is a **pool address** rather than the group's Safe, then the provider only ever sees:

- the group's Tezos account — which is **already public** on objkt, so nothing new is disclosed;
- a pool address, shared by every group.

**No link between the Tezos account and the Base Safe is created.** And
`money-in-and-out.md` §3.7 already designed exactly this: *"one shared destination, batched, then
shielded withdrawals into per-group/per-member value with no public link — which is step 2."*

**Which makes the pool a dependency of the seamlessness goal, not merely a privacy feature.** The
cross-chain move works *because* the platform is shared infrastructure: the group's Safe is never
handed to a third party, so there is nothing to correlate. That is a structural advantage of the
coop model over a per-group integration, and it is worth naming as such.

**Two honest residuals:**

1. **Batching removes the direct link; mixing removes the inferential one.** If one group's swap
   maps 1:1 onto one pool deposit of the same amount, a determined analyst recovers the pair
   without the provider's help. The pool's privacy is therefore a function of its **traffic** — it
   needs other flows passing through it, as any mixing pool does. Batch on a schedule, and do not
   size deposits to mirror individual sales.
2. **An unsecured peripheral account's balance is not shielded — accepted, and stated.** A Tezos
   float is publicly inspectable, so its *size* becomes public information. Keep the float small
   and treat its magnitude as disclosed, deliberately.

Aggregators that publish each partner's KYC level (Trocador's model) remain useful for choosing a
no-KYC route deliberately rather than hoping for one.

## 4. Privacy: what zk does here, and what it cannot do

**The Tezos ledger is transparent.** Amounts, addresses and timing are public, and objkt displays
the seller address. **You cannot retroactively shield a public Tezos transfer.**

What the zk architecture actually buys:

| Layer | Privacy |
|---|---|
| The objkt listing and the sale | **None.** Public by construction, on a transparent chain |
| From the deposit into the shielded pool inward | **Yes** — the shield applies at the crossing, and the onward distribution is hidden |
| The group's internal books, membership, entitlements | **Yes** — via period anchors and selective disclosure |

The correlation trap: `money-in-and-out.md` §3 says the only visible crossings are deposits and
withdrawals. **A deposit whose amount equals a recently public sale is trivially linked.** So:

- **Batch and delay** — pool deposits rather than mirroring each sale, and anchor **period roots,
  not per-event roots** (the existing correlation ceiling).
- Accept that the group's **public marketplace act is a public face**. Listing on objkt is a
  disclosure about the group, and being publicly visible is a choice, not a leak to be patched.
- **If the listing itself must be private, the only real answer is not to list publicly.** No
  amount of zk on Base hides an objkt listing.

## 5. Revocation without a bridge

A removed owner or delegate must lose peripheral access. **Without a bridge, revocation on Tezos
is not instant.**

The mechanism that makes this safe is the one the design already chose for session keys:

> **Time-bounded and capped delegations.** The peripheral contract enforces an expiry and a
> spending/action limit; the Base decision *not to renew* is the revocation. A revoked member's
> access **expires** instead of persisting until a bridge message lands.

Without an expiry, a removed member keeps acting on Tezos indefinitely and the only remedy is a
bridge — which is exactly the dependency §1 recommends avoiding. **This is why the expiry is not
a nicety: it is what makes bridge-less delegation safe.**

## 6. What to build — and what not to

**Do not build Tezos indexing.** The same "don't build what exists" logic as the Safe Transaction
Service applies, and it is stronger here:

| Need | Use | Note |
|---|---|---|
| Tezos chain data: accounts, operations, contract storage, bigmap history, balances | **TzKT API** (`api.tzkt.io`; REST + WebSocket) | open source (`baking-bad/tzkt`), **self-hostable**, so the sovereignty path exists |
| objkt marketplace state: listings, operators, holders, sales | **objkt public API v3** (`data.objkt.com`) | exposes `listing`, `listing_active`, `token_operator`, `holder`, `event` |

Both go **behind the adapter seam** (`chain-agnostic-identity.md` §3), which means the Tezos
adapter is mostly *wiring* rather than indexing — the expensive part is already someone else's
job, and both are self-hostable if that ever matters.

**Do build:** the binding record (`group_account` in `chain-agnostic-identity.md` §2); an
expiring, capped delegation; and the local guard contract on the peripheral chain.

## 7. Honest limits and open questions

- **No trust-minimized Base↔Tezos message path exists today.** Everything in §1 turns on this.
- **Tezos-side development is a new surface.** Nothing in this repository is Tezos-related today;
  a `KT1` wallet + guard means writing Michelson or a Tezos high-level language, with its own
  audit and testing needs.
- **Must verify before building:** whether objkt's flow accepts a **contract account as the token
  owner/seller** for all the paths we care about (listing, offers, auctions), or whether any path
  assumes an implicit `tz1`. This is checkable against the live contracts and API, and it gates
  the whole example.
- **Tezos storage burns XTZ.** Contract origination and storage growth are a real, recurring
  out-flow that the cost model does not carry — the same gap `money-in-and-out.md` §2.12 already
  flags for gas.
- **Float accountability.** How much may sit on Tezos, who watches it, and what the sweep or
  spend policy is — unwritten, exactly like the `sweep()` gap on Base.
- **Which commands does the Base authority actually issue to the periphery?** Declaring a scope
  is clear; what happens when the scope must change mid-life (a floor price, a participant) is
  the interesting case, and it is the one that tempts a bridge.
- **Does the group want a public face at all?** A group's Tezos account is publicly identified on
  objkt. For some of the groups in `adversary-models-and-sector-fit.md` that is disqualifying;
  for a farm co-op selling at market it is the point. The answer is per group, and it should be a
  decision rather than a side effect.
- **Does the swap capability get added at all?** §3b shows the seam already refuses this class of
  rail. Adding it is a **deliberate relaxation of an existing invariant**, so it should be decided
  by the coop rather than assumed by whoever writes the adapter.
- **Which swap route, and who chooses?** A no-KYC aggregator, a single provider, or a per-group
  choice. This is the same shape as the rail swap problem — `RAIL_ID` is already neutral.
- **What is the float limit and the swap policy?** How much may sit on a peripheral chain; whether
  swaps are batched on a schedule or per-sale; who signs off. Unwritten, and it is the same
  unwritten question as `sweep()` on Base.
- **Is the pool (step 2 of the money path) therefore a prerequisite of cross-chain movement?**
  §3b says yes, if the group's Safe is to stay unlinked: the destination handed to the provider must
  be the pool, not the Safe. So "move money between my accounts" depends on the shielded treasury
  being built — it is not a standalone feature.
- **How is swap revenue accounted for and disclosed?** Taking it is **decided** (§2b). What remains
  is where it lands — coop treasury or the pool — and whether it is disclosed to groups. The
  incentive to route swaps exists either way and is answered by transparency, not by refusing the
  fee.
- **Does the coop ever act as a maker (escrow liquidity)?** Contingent revenue against committed
  capital, and a counterparty **only on matched trades** (§2c). Needs a cap, an owner, and an
  appetite for days that earn nothing.
- **Does the coop run a gating service, or take the affiliate fee?** Both are no-capital,
  no-counterparty roles (§2c), and both fit the platform's shape better than being a maker. The
  affiliate fee is paid out of the buyer's amount, so disclosure to members is part of it.
- **What is the float policy?** How much may sit on a peripheral chain, who watches it, whether
  swaps are batched on a schedule or per-transaction, and who signs off. Unwritten — the same
  unwritten question as `sweep()` on Base.