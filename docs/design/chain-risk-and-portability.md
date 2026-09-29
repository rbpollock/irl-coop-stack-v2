# Chain risk and portability

Status: design · 2026-09-29 · the structural dependency, stated as precisely as the facts allow.
Related: `provider-seams.md` (the five swappable seams and the one that isn't),
`chain-agnostic-identity.md` (why the identity survives a chain move), `money-in-and-out.md` §5.1
(what survives a chain move and what does not), `cross-chain-action.md` (the swap as an exit).

## 0. The risk, stated precisely

The concern is Base's relationship with US regulators, chain analytics, and account freezes. Before
designing against it, the facts have to be right — because **one common version of this concern is
out of date.**

| | Reality |
|---|---|
| **Upgrade control** | **Not unilateral.** Base reached **Stage 1 Decentralization** in April 2025. Upgrades are gated by a **2-of-2 multisig**: CB Signers (3-of-6, Coinbase) + a **Security Council of 8-of-11 independent entities** from geographically diverse regions. Counting CB as one signer, **any upgrade needs 9 of 12 approvers** — Coinbase alone cannot upgrade the contracts |
| **Fault proofs** | permissionless since October 2024 |
| **Sequencing** | **Coinbase runs the only sequencer.** It orders, batches, and can delay or censor L2 transactions. This is the real centralization |
| **Stated commitments** | Base's published *Neutrality Principles*: unbiased transaction sequencing, no misuse of non-public data, and **freedom to exit** — *"Coinbase does not impose limitations on withdrawals from Base."* Commitments, not guarantees — but public ones, which is a cost to breaking them |
| **The operator's visibility** | the sequencer sees every transaction **and its ordering** in plaintext. Coinbase explicitly concedes access to *"insights that the Base team has access to by virtue of operating the sequencer, such as transaction ordering."* **The operator is a transaction-graph observer.** They commit not to misuse it; they have it |

So "Base is just Coinbase" is **not accurate on the axis people usually mean** (protocol control) —
and it is **accurate on the axis that matters operationally** (who sequences, and who is subject to a
US court order).

## 1. What a freeze actually costs

Worth being precise, because the cost is smaller in one dimension and larger in another than it feels.

- **Secrecy: not lost.** A frozen or censoring sequencer still cannot read the shielded pool's
  contents. Commitments and nullifiers stay opaque. What it sees is what was always visible — the
  **crossings**, which the design already treats as public.
- **Access: lost immediately.** If the sequencer refuses the group's transactions, the treasury
  becomes **unusable** — not exposed, but unreachable. For a group mid-campaign that is the
  catastrophic case.
- **Exit: still possible, but slow.** Withdrawals work through the proof path — proven on L1, then
  through the challenge period (~7 days). So an exit exists; it is not instant, and it needs L1 gas.
- **Governance: not the lever.** Because upgrades need 8 independent council members, a
  US-regulator-compelled *protocol change* (e.g. freezing a contract in the bridge) faces a real
  barrier. **A freeze would most plausibly arrive as sequencer censorship, which needs no upgrade.**

## 2. The escape hatch — and its own chokepoint

The mechanism is real and has precedent:

- **Forced transactions.** *"Users can send transactions directly to the `OptimismPortal` contract on
  L1 Ethereum. This bypasses the sequencer, ensuring that the transaction is recorded on L1."* The
  sequencer is then **obliged to include it within a fixed window** (~12-hour class).
- **It has been used.** An OP-stack chain censoring a contract's transactions was bypassed by the
  community invoking exactly this path. Censorship is possible on OP-stack chains; **the escape works.**

**But the escape hatch has a chokepoint of its own, and this is the part usually missed:**

> Using it requires **ETH on L1**. Which is obtained through the same US-regulated fiat and exchange
> layer that is the *other* freeze vector. So a group censored on Base may find the door out is locked
> by the same kind of actor that shut the first one.

**Therefore: hold a small L1 gas reserve, outside the reach of the freeze it is meant to escape.**
Small, boring, held deliberately, and not on Base. It is the cheapest insurance in this document.

## 3. Are there more democratic, decentralized, low-fee chains? — the honest answer

**Yes, on the sequencing axis. No, in the sense the question hopes for.** The reason is structural:
**fee ↔ decentralization is a real tradeoff.** Almost every chain that is cheap is cheap because
*someone* runs a centralized sequencer or a small validator set. Base is not an outlier; it is a
typical member of the cheap class that happens to be unusually *good* on upgrade governance and
unusually *exposed* on operator jurisdiction.

| Axis | Better than Base |
|---|---|
| **Sequencing neutrality** | chains with **on-chain, stakeholder-run governance and no single US-regulated operator**: **Tezos** (self-amending on-chain vote; low fees; long-running), **Cosmos-style chains** (Juno, Osmosis, Akash — on-chain proposals, community pools, diverse validator sets), **Polkadot / Kusama**, **NEAR**, **Cardano** |
| **Removing the sequencer chokepoint on an EVM chain** | **based rollups** (e.g. Taiko) — sequenced by Ethereum L1 proposers rather than a company; newer, less proven. Also chains claiming decentralized sequencing (Metis) |
| **EVM, low fees, more diverse validators, and community-run** | **Gnosis Chain** — and it collapses two dependencies into one, because **Gnosis Pay is already there** |
| **Most credibly neutral, period** | **Ethereum L1** — and expensive, which is why nobody uses it for small payments |
| **Upgrade governance** | **Base is actually strong here** (Stage 1 + an 8-of-11 independent council). Moving to a chain with a friendly multisig would be a *downgrade* |

**The standout is Tezos**, for a confluence of reasons rather than one: on-chain stakeholder
governance, low fees, **the objkt marketplace the groups already want** (`cross-chain-action.md`), and
no single US-regulated operator in a position to censor. It is the only candidate that is *already on
the roadmap* and improves this axis.

**But no chain is compulsion-proof.** Ethereum is credibly neutral *as a protocol* and still has a
US-regulated exchange layer, staking concentration, and clients that can be compelled at the edges.
So the conclusion is not "pick a better chain."

## 4. Portability is the strategy — not chain selection

> **The chain is a binding, not the identity.** A chain move is a **rebinding**, not a re-founding.

This is precisely what `chain-agnostic-identity.md` prepared, and it is the whole answer to this risk:

- **The principal survives.** A group's identity is its own stable id — `groups.id` — bound to
  per-chain accounts via CAIP-2/CAIP-10. A chain is one binding among several. Replacing it does not
  touch who the group is, who its members are, or its record. **The projection is rebuildable; only
  authority and value were ever chain-bound.**
- **Minimize the footprint.** Only authority and value on-chain. That is already the design, and it
  should be defended as a **resilience property**, not merely an architectural preference. Every
  proposal to put more on-chain is a portability cost.
- **The swap is the exit.** The same cross-chain seam that moves value to a peripheral chain moves it
  *off* Base. Building it is the hedge against chain dependence itself (`provider-seams.md` §5).
- **The standby must be established BEFORE it is needed.** You cannot bridge **authority** during a
  freeze — there is no message path, and the very thing you need is the thing that is censored. So a
  group that may need to move must **already** have a second binding with the same owner set.
  This is **mirrored authority** from `multi-chain-accounts.md` §1 — normally the topology to avoid
  because every membership change costs ×N — and here it is the *only* topology that survives a
  freeze, because it needs no bridge and no message. **That trade is worth making deliberately for
  high-risk groups, and it is the strongest argument for multi-chain in this whole design.**
- **Remove the chain-specific couplings.** Portability fails on small things:
  - **the P-256 precompile.** `PasskeyValidator` uses *"P-256 via Base precompile `0x00…0100` per
    EIP-7212"* — a chain-specific precompile. On a chain without it, passkeys need a fallback
    verifier. **This is the single most concrete portability blocker in the stack.**
  - any other OP-stack-specific behaviour, and the **single-RPC dependency** — run an own node, and
    keep multiple RPC providers so no operator can cut off *access* even without censoring.

## 5. The freeze risk you may be underweighting

For the groups in `adversary-models-and-sector-fit.md` — mutual aid, unions, at-risk artists,
subculture — **the likely vector is deplatforming, not OFAC on a chain.** Payment-processor denial,
bank debanking, and card-network refusal are the routine instruments, and they are faster and more
common than on-chain action.

Which means:

> **The card rails carry a comparable or larger freeze risk than Base — and a single, easier-to-act-on
> chokepoint.** Visa and Mastercard are two companies; a card program's sponsor bank is one more.

This belongs in the same resilience accounting as the chain, and it changes where the effort goes:
`provider-seams.md`'s "second provider configured?" column matters *more* for the card and fiat seams
than for the chain.

**The honest ranking: fiat rails > chain.** Not because Base is safe, but because the fiat layer is
where these groups actually get cut off, and it is a narrower target.

## 6. The shielded pool is the most sanction-exposed component in the stack

Tornado Cash establishes the precedent: **contract addresses sanctioned on a credibly neutral chain**,
for being a mixer. A shielded pool on a US-operated L2 is a *more* exposed configuration than that,
because the operator adds a second lever (sequencing) on top of the contract-level risk.

Two things follow:

1. **Treat the pool as the component most needing a legal read**, and not as a neutral piece of
   plumbing. It is the part of the design most likely to attract action.
2. **The design already carries its best defence: viewing keys and selective disclosure.** A pool
   with a sanctioned disclosure path — *"compliance by viewing key"*, a scope-limited report rather
   than the whole book — is materially more defensible than an anonymous mixer, and it is the reason
   the privacy architecture is a *proof system* rather than a mixer. Say this out loud, because it is
   an asset that is easy to mistake for an implementation detail.

## 7. What to do

| Action | Why |
|---|---|
| **A chain-risk tier at group formation** | some groups can sit on Base comfortably; others must start portable. It is a formation-time choice, like exit and succession rules — you cannot add the option later |
| **A small L1 gas reserve, held off-Base** | the forced-inclusion escape costs L1 gas, and obtaining it in a freeze is the trap |
| **The float policy is a freeze-survival policy** | do not keep everything on one chain; keep enough accessible elsewhere to survive a freeze with no notice |
| **Two bindings for high-risk groups, established before need** | mirrored authority; expensive to maintain, and the only thing that works during a freeze |
| **Own Base node + multiple RPC providers** | removes the access chokepoint even under an uncensored chain |
| **Extend the readiness surface to chains** | for each group: how many chain bindings exist, is an L1 reserve held, which chain-specific features are depended on |
| **A legal read on the pool, early** | it is the most exposed component and the one with the most defensible answer |

## 8. Open questions

- **Is Tezos the standby, or the destination?** It is the best candidate on this axis and already on
  the roadmap for other reasons. Choosing it as the *deliberate* second binding would be a stronger
  move than an incidental one.
- **What is the minimum viable L1 reserve?** Enough for one forced transaction plus the withdrawal
  proof. It needs a number.
- **Does mirrored authority scale to a real collective?** Every owner change becomes ×N. For a group
  with ten members that is ten coordinated signature rounds — plausible once, painful routinely. The
  honest answer may be that mirrored authority is for the *founders* of high-risk groups only.
- **What is the trigger to exercise the exit?** A freeze is obvious; a slow erosion (a sequencer
  starting to delay, an RPC degrading) is not. The readiness surface should carry a threshold, or the
  decision will always be made too late.
- **Would the coop ever run a chain?** Running a validator or sequencer is the only way to remove an
  operator, and it is a large, permanent commitment. Worth naming as the logical endpoint of this
  axis, and then deciding not to.