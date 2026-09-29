# The artist collective — an end-to-end story, traced against the code

Status: design · 2026-09-29 · a worked flow used as an acceptance test.
Related: `money-in-and-out.md` (the money path and its step order), `account-and-key-model.md`
(accounts, guards, session keys), `cross-chain-action.md` (objkt, swaps, floats),
`chain-agnostic-identity.md` (a Tezos account is a `tezos:` CAIP-10 account),
`adversary-models-and-sector-fit.md` (why "at-risk" changes the priorities).

## 0. Why this story is the right test

A group of **marginalized and at-risk artists** forms a collective, works, sells across several
marketplaces, and routes the proceeds back to its members — some of whom want their share out to
their own Tezos wallet.

This is the sharpest end-to-end test available, for one reason: **the group's members are the
adversary model.** A thing that works for a farm co-op can still be disqualifying for a group whose
members may be targeted. So the test is not "does the flow complete" — it is **"does the flow
complete without exposing anyone."** That is a harder bar, and it is the bar the design claims to
clear.

## 1. The story, step by step, against reality

| # | Step | Status |
|---|---|---|
| 1 | Form a collective, create a group | **Works.** Groups, seats, roles, scoping are built and were exercised. **But** every Safe is currently owned **1-of-1 by the backend signer** (`safe.ts` `defaultInitializer()`), and that key is Hardhat account #0's *published* key in the tree. No passkey or member key is an owner yet |
| 2 | Create, promote and plan using their own tools **plus** irl.coop's | **Works, and is additive by design.** Postiz (social), Plane (projects), MinIO + OnlyOffice (docs/media), Webstudio (sites). Several are "not in final form" (`AGENTS.md`), and the group keeps its own tools — the stack layers on rather than swallowing the workflow |
| 3 | Attribute contribution — immutable record, **voted on by the group** | **Implemented in code, never exercised.** `tier2-contributions.ts` + `tier2-routes.ts` exist (`recordContribution`, `emitContributionEvent`, `contributionPayloadToEntry`), the counter-signature schema models all three authority classes (`class` … includes the group-vote class), and `db.ts` carries the period-tree/anchoring machinery. **Zero rows** in `tier2_entry`, `tier2_signature`, `anchors`, `proposals`, `votes`. Nothing has ever anchored |
| 4 | Present work for sale — own site, third-party marketplaces, objkt.com | **Partly missing.** Webstudio is a *site*: there is **no store/checkout** in the stack, and `STRIPE_SECRET_KEY` is empty. The fiat rail works but costs the payer up to **20%** — bad for a $30 print — and its quotes are advisory (no guaranteed P2P counterparty). The **objkt/Tezos path needs a `KT1` contract wallet, and nothing Tezos-related exists** (see `cross-chain-action.md` §2) |
| 5 | Purchases **auto-route back** to the group and are **tallied to split to members' group Safes** | **Least built — and it is the step the story calls automatic.** Nothing sweeps the router (`docs/PAYMENTS-SETUP.md` §7). There is **no distribution, split or payout code at all** — the only mention is a comment hoping Tier 2 "feeds the entitlement table — and therefore Tier-1 distributions". And **nothing in `coop-api` ever signs a value transfer out of a Safe**: the only `sendTransaction` is the Safe *deployment* call in `safe.ts`. Paying a member is not merely unautomated, it is unbuilt |
| 6 | A member's rule: funds arriving at their personal Safe **auto-forward** to their Tezos wallet (or elsewhere, or into an investment) | **No machinery.** The `SessionKeyModule` exists as Solidity, but nothing in `coop-api` grants or uses a session key; there is **no ERC-4337, EntryPoint, paymaster or relayer anywhere** in the tree; and there is no executor that watches for an arrival and acts. Plus a privacy trap — see §4 |

## 2. The uncomfortable pattern

**The three steps that carry the safety property are the three least built.**

- Step 3 (attribution) is what makes a claim of contribution *provable without being published* —
  the whole reason Tier 2 is off-chain and anchored rather than on-chain.
- Step 5 (routing and splitting) is where money becomes visible if it is routed naively.
- Step 6 (the member's own destination) is where a payout can be tied to a person.

And the *shielding* those steps depend on — the pool, step 2 of the money path — is unbuilt. So:

> **Running this story on the stack as it stands today would be maximally exposing.** The
> marketplace act is public, the social promotion is public, and there is no shielding between a
> sale and a member's wallet. For this group specifically, that is the opposite of the requirement.

That reframes the priority: for at-risk artists, **the shielded pool is the product**, not a later
privacy feature. It sits on the critical path, ahead of most of the rails.

## 3. What each missing step actually needs

**Step 3 — attribution.** The primitives are there; what is missing is a **first real entry**: one
contribution recorded, counter-signed under one of the three authority classes, and its period root
anchored to Base. Nothing has written to `anchors` except an operator function that has never been
called. Until one entry exists and one anchor lands, "immutable and voted on" is a design claim
rather than a demonstrated property.

**Step 4 — selling.** Two distinct gaps: (a) a **storefront with a checkout** for their own site —
today Webstudio is presentation only, so the honest options are the crypto rail or a third-party
shop; (b) the **objkt path**, which needs a `KT1` contract wallet built in a Tezos language, plus
verification that objkt's flow accepts a contract account as owner/seller across the paths used.

**Step 5 — routing and splitting.** This is the largest single piece of unwritten code in the
story, and it decomposes into four things that do not exist:
1. **Detection** — something must notice a purchase landed. That is the indexer
   (`base-indexing.md`), and it is also the thing that would tell a human to `sweep()`.
2. **Sweeping** — `sweep()` is permissionless and nothing calls it.
3. **An entitlement table** — derived from attributed contribution, which depends on step 3 having
   real entries.
4. **A distribution** — a threshold-signed transfer out of the group Safe to each member's Safe.
   Nothing signs value out today, and per `money-in-and-out.md` §5.3 automated splits are step 4 of
   the money path (v1 automation), gated behind the shielded treasury.

**Step 6 — the member's own destination.** Needs a **delegation with an expiry and a cap**
(`SessionKeyModule` plus the session-key pattern), an **executor** to act on arrivals, and — for a
Tezos destination — a swap service behind the rail seam (`cross-chain-action.md` §3b).

## 4. The privacy trap inside step 6

"Auto-forward the funds the moment they arrive" **destroys the privacy it was meant to preserve.**

- An arrival immediately followed by a matching forward is a **1:1 link** on a public ledger. An
  observer learns "the address that received X sent X on to Y" — and if the member's Tezos wallet
  is theirs, the payout is now attributed to a person.
- Withdrawing from the shielded pool to a transparent address is a **visible crossing by design**
  (`money-in-and-out.md` §3 — the only visible crossings are deposits and withdrawals). Choosing a
  transparent destination is choosing to disclose. That is fine — it is the member's call, and the
  group already accepts that an unsecured account is not shielded — but it must be a *deliberate*
  disclosure, not one the automation performed anonymously on their behalf.

**So the member's rule must be "accumulate and forward on a schedule", never "forward on arrival."**
Batching is what makes the crossing tell the observer nothing about *which* member was paid.

**And "or invested in something" should be explicitly out of scope or separately gated.**
Automatically taking a position with someone else's money is a different activity from transferring
it, it carries real loss risk, and for a member who is already a target, an automation holding
spend authority is a theft vector. If it is wanted, it needs its own cap, allowlist and consent.
The safe default for this group is **no automation until asked for.**

## 5. What the story needs, in dependency order

1. **Real Safe ownership** — replace the 1-of-1 published backend signer with member-held keys or
   passkeys. Nothing else in this story is safe before this; it is the first thing an at-risk group
   would need, and it is already listed as a gap in `account-and-key-model.md`.
2. **One Tier-2 entry, counter-signed and anchored** (step 3). Proves the attribution claim.
3. **The shielded pool** (money path step 2). This is the product for this group.
4. **The indexer** (`base-indexing.md`) — detection plus the sweep alert.
5. **A storefront/checkout decision** for their own site, and separately the objkt `KT1` work.
6. **Distributions** (money path step 4) — the split, on top of the pool.
7. **Member payout rules** — accumulate-and-forward with an expiring, capped delegation.

Rails (money path step 3) are the one item already partly standing, which is why the story's
critical path runs *through* Tier 2 and the pool rather than through the payment plumbing.

## 6. Open questions

- **Does this group even want to be publicly listed?** An objkt listing with a collective's name is
  a public statement. Some groups want the exposure; for others it is disqualifying. It should be a
  formation-time choice, alongside the exit and succession rules (`account-and-key-model.md`).
- **Is the collective itself the visible entity, with members hidden behind it?** That is the
  likely shape — and it means the collective's public face must never resolve to its members' wallets.
  Achievable through the pool, but only if payouts are batched.
- **What is a contribution worth?** The entitlement table turns hours into money, which makes the
  Tier-2 write path economically meaningful — `money-in-and-out.md` §3.2 already flags this: *"a
  scoped key that can sign hours is, indirectly, a money-minter."* For a small collective with real
  stakes, that is the highest-trust surface in the whole story.
- **Tax and income exposure.** A distribution to a member is income, and a record of it is a record
  of the member's association. The design can hide the *amounts*; it cannot remove the member's own
  obligations. Worth stating plainly rather than discovering.
- **Does the story need the fiat rail at all?** Its up-to-20% payer-side cost makes it wrong for
  small prints. If most buyers are crypto-native or pay in person, direct USDC and Tezos payments
  may carry the story, and the rail becomes the exception for card payers.