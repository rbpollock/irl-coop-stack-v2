# Provider seams — decoupling the transactional layer

Status: design · 2026-09-29 · a resilience requirement, not a refactor.
Related: `cross-chain-action.md` (the swap, the rail seam), `payout-capability.md` (the card),
`base-indexing.md` (the chain-data seam), `money-in-and-out.md` §3.7 (the original rail seam).

## 0. The requirement

The transactional layer is **the most fluid part of the system and the part the coop depends on
most.** So the design goal is not "pick good providers" — it is:

> **Every provider must be replaceable by configuration, without touching the core, and the one
> component that is *not* replaceable must be named so nobody assumes otherwise.**

The pattern already exists and is proven once: the payment rail is its own app, the core holds only
`RAIL_URL` / `RAIL_ID` / `RAIL_AUTH_TOKEN`, and *"swapping providers is a new app behind the same
contract, not an edit to coop-api."* **This document generalizes that pattern to every seam.**

## 1. The seams

| Seam | The core knows | The adapter knows | Status of the pattern |
|---|---|---|---|
| **Fiat on-ramp** | "a rail, id `peer`, at `RAIL_URL`" | Peer.xyz, its SDK, its vocabulary | **Reference implementation.** Already built this way |
| **Cross-chain swap** | "a swap, id X" | ChangeNOW / the aggregator / its deposit-address flow | Designed (`cross-chain-action.md` §3b) |
| **Card / fiat access** | "a card program, id X" | Gnosis Pay or Immersve, its KYC and funding protocol | Designed (`payout-capability.md` §4) |
| **RPC** | `CHAIN_RPC_URL` per CAIP-2 namespace | the node operator | To apply |
| **Chain data / indexer** | "an indexer for namespace N" | TzKT, objkt API, Safe Transaction Service, Basescan | Designed (`base-indexing.md`) |
| **The chain itself** | — | — | **NOT swappable. See §5** |

The last row is the point of the whole document: five seams are hot-swappable, and one is not.

## 2. The decoupling rules

These are the conditions that make a provider swap a *configuration change* rather than a
refactor. Each is checkable, and each one has already been satisfied once by the payment rail.

1. **No vendor noun in the core.** `money-in-and-out.md`: *"Nothing else in coop-api names a
   provider: verified by asserting the module contains no vendor term at all."* Generalize: if the
   core's code or schema contains a provider's name, the seam is leaking.
2. **Vendor detail lives in exactly one opaque column.** `payment_intent.provider_payload` is *"the
   ONLY home for vendor detail."* Every seam that needs to retain provider-shaped data gets one
   such column, and never a provider-shaped column.
3. **Vendor credentials are vault entries, per provider, never named in core.** `peerpay.api_key`
   is referenced as `${VAULT:peerpay.api_key}`; the derived `payments.rail-token` is the *core's*
   own token. Swapping a provider means writing one vault entry — not editing the core.
4. **The migration test.** *Can you replace the provider without a schema migration?* If no, the
   coupling is in the data model, which is the hardest place to find it. Every seam must pass this.
5. **The core addresses providers by an abstract id; a policy decides which id serves a request.**
   This is what makes two-providers-at-once possible, and what makes a cutover a policy change.
6. **Every provider declares its capabilities, and the core validates them before use.** The rail
   already does this (`directToDestination`, `canObserve`, chains, currency) and *refuses* a rail
   that fails. This is the contract that lets an unknown provider satisfy a known need — and it is
   how a substantively different provider (a swap service that holds funds mid-flight) is admitted
   *visibly* rather than by silently relaxing a check.
7. **The core boots and serves with every adapter absent.** If the system cannot start without a
   provider, the coupling is wrong in the most dangerous direction. The test is one command: remove
   the adapters, start the core, confirm everything unrelated works.
8. **No provider is on the critical path of an unrelated feature.** A provider being taken down
   kills ONE process — that is the stated reason the rail is its own app. A swap outage must not
   stop dues, mail, documents, or governance.

## 3. Two at once, and the cutover

The design already names the benefit: *"Two rails could even run at once, which is the resilience
argument for naming the app after the provider."* Generalize:

- **N adapters per seam may be live**, each declaring its capabilities.
- **A policy selects** — by cost, by availability, by privacy posture, by group preference.
- **Cutover is a policy edit**, and rollback is the reverse edit. Both are reversible in the time it
  takes to change a config value.

This is what "rapidly decouple" means operationally: not "we could rewrite it", but **"we flip a
value and the old provider is gone from the path."**

## 4. The drill — a seam you have never swapped is not a seam

The strongest statement in the current design is also its weakest evidence: *"swapping the
provider, when it is taken down. Implement the interface in a new app, then point `RAIL_URL` at
it."* That is a **claim**, and it has never been executed.

> **Decoupling is a rehearsed capability, not an architectural property.** Schedule a cutover
> rehearsal — stand up a second implementation of one seam, route a test through it, then cut back.
> Record the date and the elapsed time.

Until one drill has run, every statement in §2 is untested, and the coop's most-depended-on layer is
unproven exactly where it matters. The drill belongs on the same footing as the payments preflight:
a thing that is either done or visibly not done.

## 5. The honest limit: the chain is not hot-swappable

Everything above applies to providers. It does **not** apply to the chain, and pretending otherwise
would be the most expensive mistake available here.

`money-in-and-out.md` §5.1 states it plainly:

| Store | Holds | Survives a chain move? |
|---|---|---|
| Postgres / the projection | records: members, seats, roles, scopes, documents, the Tier-2 ledger | **Yes** |
| Chain | **authority and value**: the Safe, owner set, threshold, treasury, notes | **No** — re-established at redeploy |

*"The group's work survives; its keys and money do not."* So the chain is the one dependency you
cannot flip, which is precisely why it is the one the coop is most dependent on. Three consequences,
and they are the real answer to this whole concern:

1. **Minimize the on-chain footprint.** The design already does this — only authority and value are
   on-chain; everything else is a rebuildable projection. **That minimal footprint *is* the
   decoupling strategy.** Keep it minimal deliberately, and treat any proposal to put more on-chain
   as a resilience cost, not just an architectural choice.
2. **Multiple RPC providers per namespace**, so no single operator can censor or degrade access.
   This is cheap, and it is the one part of the chain dependency that *is* hot-swappable.
3. **The swap capability is the chain-exit capability.** The same seam that moves value Tezos → Base
   moves it Base → anywhere else. So building the cross-chain rail is not only about peripheral
   chains — **it is the hedge against chain dependence itself.** That is a strong second reason to
   build it, and it should be recorded as such.

## 6. A provider-readiness surface

The payments preflight is the right shape — gates that are only green when the work is done.
Generalize it into one surface covering every seam:

| Per seam | Shows |
|---|---|
| Live adapter | which provider id is serving, and for which namespaces |
| Capability declaration | what it claims (`directToDestination`, `intermediatesFunds`, chains, currency, regions) |
| **Second provider configured?** | whether a substitute exists at all — the difference between "swappable" and "swappable only in theory" |
| **Last drill** | when the cutover was last rehearsed, and how long it took |
| Concentration | how many seams share one provider (a single vendor across fiat *and* cards is one outage, not two) |

The "second provider configured?" column is the one that will hurt, and it is the honest measure of
this whole document. A seam with one implementation and no drill is **not** decoupled — it is
merely *structured* for decoupling.

## 7. Open questions

- **Which seam gets the first drill?** It should be the one with the highest dependence and the
  lowest switching cost — the fiat on-ramp is already abstracted and has real alternatives
  (FixedFloat, StealthEX, SimpleSwap, Godex; aggregators like Trocador).
- **Do we run two providers permanently, or one plus a hot spare?** Permanent dual-running doubles
  the surface but removes the cutover entirely; a hot spare keeps it thin but unexercised.
- **Who owns the policy that picks a provider?** The coop, or the group. Privacy posture differs per
  group (`cross-chain-action.md` §3b), so this is probably a group-level policy with a coop default.
- **How much provider concentration is acceptable?** One aggregator fronting several seams would be
  a single point of failure wearing three hats.
- **Is there a cost ceiling on substitutability?** Keeping a second card program warm costs money
  and attention. The honest framing is an insurance premium, and it needs a number.