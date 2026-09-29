# The payout capability

Status: design · 2026-09-29 · the flow from recognised work to money a member can actually spend.
Related: `money-in-and-out.md` (Tier 1/2, the money path), `account-and-key-model.md` (guards,
reserved powers, formation defaults), `artist-collective-end-to-end.md` (the story this serves),
`cross-chain-action.md` (the rail seam).

## 0. The capability in one line

**A group's work is recognised by people (a steward role, then a vote), the split is ratified, and
each member receives their share in a form they can use — on-chain by default, with an opt-in Visa
path when they need fiat.**

Five pieces, in order:

```
work happens
  ↓  steward attests  (routine, per contribution)
Tier-2 entry  ──→ period root ──→ anchored to Base
  ↓  vote ratifies the PERCENTAGES  (rare, consequential)
entitlement table  (a ratified artifact)
  ↓  threshold-signed transfers out of the group Safe
member's earnings Safe  ──→ (opt-in) card funding  ──→ Visa / wallet tap
```

## 1. Who owns the group Safe at formation

### The owner is an account, not a key

The seeding owner must be the founder's **own account** — a Safe — not an EOA and not a raw key.
Two reasons, both already load-bearing in the design:

- **It composes.** A Safe can own a Safe, so the founder's account is an ordinary member-account
  from the first moment. Nothing special is introduced.
- **It is recoverable in its own right.** A bare key has no recovery story; an account does.

**The coop is never an owner.** Steward, not root. If assistance is wanted it must be an opt-in
path the group can remove — the *assist-only co-owner* shape in `account-and-key-model.md`, never a
default seat.

### No special permissions exist to revoke — that is the point

`account-and-key-model.md` settles it: **"Safe ownership is binary, so reserved powers are NOT a
special owner role."** So the requirement "they can vote me out" needs no new mechanism:

> Removing the founder is `removeOwner` under the group's normal threshold. **There is no role, no
> module exemption, and no reserved permission to strip** — the founder holds exactly what every
> other owner holds.

That is the cleanest possible answer, and it is a property the design already has. The founder's
privilege is *temporal*, not structural.

### The bootstrap window is 1-of-1 — and that is correct, not a flaw

**Corrected.** An earlier version of this section required threshold ≥ 2 from the first block. That
is wrong for the real case: **many groups will be formed by a single individual and grow into rich
multi-user collectives**, and demanding a second key at formation would block the very formation it
was meant to protect.

**1-of-1 is right at bootstrap, for a reason that dissolves the fragility concern entirely: during
bootstrap there is no collective to protect.** It is one person and their own money, on an account
they alone control. That is the same risk profile as their personal wallet — not a new exposure.

### The real invariant: no owner is ever indispensable

What must be true is not "two keys at formation" but **"no owner can be held hostage."** State it as
one checkable rule:

> **`threshold ≤ ownerCount − 1`** — i.e. **a Safe must never require unanimity.**

| Owners | Threshold | Any one owner removable without their own signature? |
|---|---|---|
| 1 | 1 | vacuous — the bootstrap case |
| 3 | 2 | **yes** — the other two remove the third |
| 5 | 3 | **yes** — any three remove any one |
| 5 | 4 | **yes** — the other four remove the fifth |
| 5 | 5 | **no — UNANIMITY, forbidden** |

Three things this buys at once:

1. **"Vote me out" becomes structural rather than promised.** Once a group has three owners, the
   founder is removable by the other two under the group's *ordinary* threshold — no special module,
   no formation-time timer, nothing anyone has to remember.
2. **Joining a group means becoming an owner**, and the threshold is re-derived at each join so the
   invariant keeps holding. **The group grows by changing its own owner set** — which is also the
   cleanest statement of what a cooperative *is* here.
3. **A lost key can never freeze the Safe.** Unanimity is the property that lets one dead or
   unreachable owner lock everyone out forever. Forbidding it is the actual fragility fix — and the
   reason this rule is better than the one it replaced.

**Enforced where it cannot be forgotten: a guard.** Every owner-set or threshold change must satisfy
the invariant or revert. Same self-binding guard pattern as everything else
(`account-and-key-model.md`: *"Enforcement is local and self-binding… the child cannot opt out"*).
It replaces the `GraduationModule` proposed earlier, because the invariant is **permanently** true
rather than true from some member count.

**The honest pinch at n = 2.** The invariant bites awkwardly with two owners: `threshold ≤ 1` lets
either act alone; `threshold = 2` is a mutual veto. Both are defensible and both are temporary. Two
owners must choose knowingly — either trusts the other to act alone, or accepts a veto until a third
joins. **The way out of the pinch is the third member**, which is the same thing that makes the
founder removable. Say so in the UI at the moment of the second join.

**And a delegatecall guard, which must bind the founder too.** `account-and-key-model.md` flags this as an open knob
(*"a group's Safe holds real value (whitelist the delegatecall target)"*). It matters more here,
because a founder who can `delegatecall` can install anything — including a module that bypasses
the unanimity invariant. **The guard must bind the founder too, or the invariant is decorative.**

## 2. Who ratifies the split

Your steer, adopted: the counter-signing authority for this capability is **a role-based steward
role or a member vote** — not a machine key. That maps onto two classes with different jobs:

| Class | Attests | Frequency | Strength |
|---|---|---|---|
| **Steward role** | *"I saw this happen."* A contribution entry | routine, many per week | bounded by the role's grant matrix |
| **Group vote** | *"We accept these percentages."* The ratified split | rare, one per period | the authority of last resort |

**The key insight is that they do different work.** The steward makes the record; the vote makes the
*money decision*. Contributions are witnessed continuously and cheaply; the **percentages** are
ratified deliberately and rarely. That is exactly the design's own guidance — *"use the cheapest
one that can honestly attest… a vote is the most expensive and should be the rarest."*

Consequences worth fixing now:

1. **The entitlement table is a ratified artifact**, not a derived number. A distribution run reads
   **ratified entries only** and treats a steward-signed-but-unratified entry as *provisional*
   (`money-in-and-out.md` §3.2 already specifies this).
2. **The steward role is economically meaningful and must be treated as such.** It cannot move
   money directly — but it decides what the vote is voting on. So: **scoped per entry class,
   expiring, and rate-limited**, the same care as a key that moves funds. *"A stolen stand key
   should cost one day's hours at one stand, not the group's whole history of labour credit."*
3. **The risk moves from key theft to governance capture.** Making the human authority the decider
   is right, but capture is *harder to detect and slower to reverse* than a stolen key. So the vote
   itself needs its protections: quorum, a **timelock** with a challenge window, and the rule that a
   later decision **supersedes but never erases** (the record of the old percentages stays).
4. **Percentages can be public to the group without amounts being public.** The split ratio is not
   sensitive; the earnings are. Say so in the UI, so members understand what is and isn't disclosed.

## 3. The distribution

For each period, for each member with a ratified share:

- the amount is a transfer from the group Safe to the member's **earnings Safe**;
- it is **threshold-signed** — no single key can pay out;
- the run reads the ratified entitlement table, and a bare steward-signed entry is provisional;
- each transfer is batched with the others, so the *set* of payouts does not reveal which member
  received what.

**Note what this requires that does not exist yet** (assume the easy fixes are done — these are not
easy): a distribution run, and threshold signing of value transfers out of a Safe. Nothing in
`coop-api` signs value out today. This is the piece to build first after the formation mechanics.

## 4. Fiat access — the card

### The candidate

**Immersve** is the best fit and it is an API, not a consumer product:

| Fact | Detail |
|---|---|
| Built for this exact case | *"add Immersve card issuing capabilities into a **non-custodial web3 wallet**"* |
| **Base is supported** | funding table lists Base with **deposit-based** funding (`universal` variant) |
| **The funding source may be a smart contract implementing ERC-1271** | so a **Safe can be the funding wallet** — no EOA required |
| Cards | virtual and physical; usable in-store by loading into a wallet/Apple-Google Pay (`XPay`) |
| Withdrawals | *"Users can withdraw funds or revoke approvals at any time"*; permissionless withdrawal on the flexi variant |
| **Custody, stated plainly** | *"Immersve holds funds when Mastercard requests payment authorization. Immersve settles held funds after the Mastercard network clears the payments."* — custody for the **authorization-hold window only** |
| KYC | **required.** *"Immersve Conducted KYC is the recommended KYC mode for non-custodial apps"*, or Partner-conducted if already verified. **Regions are limited** — check `Get Supported Regions` |

### Gnosis Pay is back on the table — the chain mismatch is what the swap solves

**Corrected.** An earlier version of this document ruled Gnosis Pay out because its spendable tokens
must be **on Gnosis Chain**. That was the wrong conclusion: **the chain is not an obstacle, it is
exactly what the cross-chain capability exists for.** Base stays the canonical home of the group's
Safe; an account on Gnosis Chain is one more **surface the group acts through**
(`cross-chain-action.md` §0).

So the flow is simply:

```
group Safe (Base, USDC)
  → swap  (ChangeNOW or an aggregator — cross-chain-action.md §3b)
    → a Gnosis Chain account the group controls
      → Gnosis Pay Safe  →  Visa card
```

And Gnosis Pay is the **stronger** option on the thing that matters most here:

| | Gnosis Pay | Immersve |
|---|---|---|
| **Custody** | *"Gnosis Pay never holds or stores your funds"* — funds stay in the Safe until the moment of spend; T+1 settlement with Visa | *"holds funds when Mastercard requests payment authorization"* — custody for the authorization-hold window |
| Chain | Gnosis Chain, reached by a swap | **Base native** |
| Integration | consumer product; attaching an existing Safe multisig is *"planned"* | **API built for embedding** in non-custodial wallets |
| Card | Visa, spendable directly from the Safe | Mastercard, virtual + physical |
| KYC | required | required, and regions are limited |

**Neither requires the group's *canonical* Safe to be the spender.** We need an account the group
controls — so Gnosis Pay's pending "attach an existing Safe" feature is **not a blocker**. Its Safe is
created with owners *you* specify, which means the group sets the owners and the group controls it.

**Recommendation: Gnosis Pay as the primary fiat path** — the better custody story, spendable
directly from a Safe — reached by a swap from Base. **Immersve as the Base-native alternative** for a
group that would rather not hold a Gnosis Chain account. Baanx-powered cards are a third option
(Base, self-custody, converts at point of sale) but are consumer products rather than APIs. All three
sit behind the same rail seam and declare their in-flight custody honestly.

### What it is, architecturally: another rail

The card is a **rail** behind the same seam as the swap service, and it has the **same capability
question** — it holds funds during the authorization window. So it declares it:

```
capabilities: { rail: 'immersve', directToDestination: false,
                intermediatesFunds: true, inFlightCustody: 'authorization-hold' }
```

That keeps the seam's exclusion honest: the class is refused by default and admitted by an explicit
declaration, not by quietly relaxing a check.

### The one tradeoff that cannot be engineered away

**Fiat access requires identity.** A Visa card is a regulated instrument, so KYC is not optional.
The consequence for this group is specific and unavoidable:

> The member's identity gets linked, in the issuer's records, to a funding address — and the issuer
> knows every merchant they paid.

The on-chain flow can be private. **A card cannot be.** So:

1. **Per-member, opt-in, with the disclosure stated in plain language.** Some members will take it;
   some must not.
2. **Never fund the card from the earnings Safe.** Give each member **two Safes** — *earnings* and
   *spending* — and use the spending Safe as the card's funding source. Then the issuer's identity
   link attaches to a spending surface, not to the member's earnings history. Funding moves
   earnings → spending **batched**, on a schedule, so the two are not 1:1 linked.
   **With a Gnosis Chain card the separation is free**: the earnings Safe sits on Base and the
   spending account on Gnosis Chain — and **the swap is the batched move**, which is also what breaks
   a 1:1 link. The chain hop does the compartmentalising for you.
   This is cheap: a Safe costs nothing to derive, only gas to deploy.
3. **The card float is a float.** On Base the funding model is **deposit-based**, so funds must be
   pre-loaded into the cardholder contract — a float, with the same obligations as every other
   float in this design: a **cap**, an **owner**, and something that **watches it**.
4. **A group card is a separate, useful thing.** Because the funding source can be a contract, the
   *group's* Safe can hold a card for group expenses — distinct from member cards, and governed by
   the group's threshold rather than an individual's.

### Why this can land "ASAP"

The card capability **does not depend on the shielded treasury.** It needs the rail seam, a
personal-Safe rule, and a funding flow — no pool, no proofs. That is unusual in this design, where
most things sit behind step 2. It is the one member-facing money capability that can ship before
the shielding does, which is exactly why it is worth doing now.

## 5. What to build, in order

1. **Formation mechanics** — the **unanimity invariant** (`threshold ≤ ownerCount − 1`) enforced by
   a guard on every owner-set change, plus a **delegatecall guard that binds the founder**. 1-of-1 is
   the correct bootstrap; **nothing here blocks a solo founder.**
2. **Steward role + contribution attestation** — the role, its grant matrix, its expiry and caps.
3. **The ratification vote** — percentages, quorum, timelock, supersede-not-erase.
4. **The entitlement table + distribution run** — reads ratified entries; threshold-signed transfers
   out of the group Safe. *This is the largest genuinely new piece.*
5. **Two Safes per member** (earnings, spending) and the batched earnings → spending move.
6. **The card rail** — Immersve behind the seam, per-member opt-in, float policy, region check.

Steps 1–4 are the payout capability proper. 5–6 are what makes the money *usable*.

## 6. Open questions

- **How is the n = 2 pinch resolved?** The unanimity invariant makes a two-owner group awkward by
  construction: either one owner acts alone, or the pair holds a mutual veto. Which default, and how
  loudly does the UI push the third member?
- **Does joining always mean becoming an owner?** If groups want contributors who are *not* owners,
  the invariant needs a companion rule for non-owner members — otherwise "member" and "owner" quietly
  drift apart.
- **Which chain hosts each group's spending account?** Gnosis Chain (via a swap, better custody) or
  Base native (Immersve). Per-group, and it decides where the identity link lands.
- **Who holds the bootstrap key, and is there a recovery share?** With 1-of-1 accepted, the founder's
  single key *is* the group for a while. A passkey plus an offline recovery share is the cheap
  hardening — and it should not be mandatory, or it blocks exactly the solo founder we are designing
  for.
- **Does the founder's seat become a normal seat, or disappear?** Once the group can remove it
  freely, keeping it as an ordinary owner is the honest default — the founder stays a member with no
  more power than anyone else, which is the stated intent.
- **Which regions can our members actually get a card in?** Immersve's region list gates this, and
  for a distributed collective it may exclude some members. Check before promising.
- **Do members want a *group* card as well?** A group card for shared expenses (materials, shipping,
  booth fees) is a different and probably easier win than per-member cards.
- **What happens to a member's spending float if they leave?** Permissionless withdrawal exists on
  the flexi variant, so the technical answer is "they can pull it" — the governance answer is
  whether leaving forfeits anything.