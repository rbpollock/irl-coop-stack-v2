# Fundraising & programmable transfers — a dashboard surface

Status: design · 2026-09-29 · the fundraising *surface* + the transfer-automation
shapes, built on the campaign-subsidy pattern and the transfer state machine.
Not built — this doc designs the capability. For the underlying machines see
`capital-campaign-subgroup.md` (the contributor pattern), `transfer-authority.md`
(the state machine + guard-vs-guidance), `payout-capability.md` (who ratifies a
split), `private-treasury-guards-ledgers.md` (shielded holdings + off-chain
verifier), `money-in-and-out.md` (USDC on Base; deposits).

## 1. The ask, mapped to existing machinery

> A surface in the app dashboard to fundraise — a sharable link accepting a
> credit card (fiat) or a secure deposit address. Available from the group's
> profile. Better than GoFundMe or Kickstarter. Plus: one-time transfers,
> recurring transfers, and rule-based transfers — payouts/distributions to
> members, and encumbrances levied by a deal/promise with another group.

That is **three systems** the stack already designs separately, and the surface
unifies them:

| Ask | Existing piece it plugs into |
|---|---|
| Sharable fundraising link, credit-card OR deposit-address | the **capital-campaign subgroup** pattern (§ shape) + the **money rail** (credit card → fiat onramp/USDC; deposit address → the Safe deposit lane) |
| On the group's profile | group-profile is a real surface; the campaign is a *shape the group takes* (`capital-campaign-subgroup.md`) |
| Better than crowd-sells | the **coverage proof** (§7) + **scoped contributor access** + **no-control guarantee** (the properties GoFundMe cannot give a cooperative) |
| One-time transfers | the **transfer state machine** (`submitted → authorized → ... → settled`) |
| Recurring transfers | the **standing-mandate** shape (an approval per mandate, not per run) |
| Rule-based transfers (payouts/distributions) | a **distribution = a batch mandate** ratifying percentages, not per-payment authority |
| Encumbrances / inter-group deals | the **declared-edge registry** (`transfer-authority.md` §1) + a **standing order** |

So the fundraising surface is not a new subsystem — it is **the campaign pattern
pointed at real money flows**, with the transfer automation built on the state
machine. The doc specifies the *surface* (the link, the profile placement, the
progress rendering) and the *transfer shapes* on top of what exists.

## 2. The fundraising link

### 2.1 What the link is

A campaign group publishes **one URL** that leads a donor to:

- **A fiat card checkout** (Stripe/on-ramp — the existing rail) — instant, no wallet,
  cards accepted. Money lands as USDC into the campaign Safe (or the group Safe).
- OR **a deposit address / QR** — the on-chain lane, for donors who hold
  crypto. The address is a Safe deposit (or a standing-order address), never a
  hot public wallet.
- Shared disclosure that reads: **"This is a contribution to a cooperative —
  recognition and access, not equity or a return. No ownership. You can see what
  we spend it on."** Reused verbatim from the campaign-sponsorship wording
  (`capital-campaign-subgroup.md` §5) — the same text that protects the group from
  drifting into an offering.

### 2.2 Why it is better than GoFundMe/Kickstarter

GoFundMe is a black box: your donation goes to a platform that pays out when it
decides, from accounts that are politely hosted, with no proof your money did
what was asked. Kickstarter adds a corporate custodian and a crowdfunding
cameo. Both are also hostile to their own financing shape (cost, control,
censorship). The stack's bar:

| Crowd-fund property | GoFundMe/Kickstarter | This stack |
|---|---|---|
| Donor trust | a slogan (trust us) | a **coverage proof**: "raised ≥ X, spent ≥ Y on Z" verified against an anchored root, published without publishing the books |
| Contributor role | a payer | a **real member** of a campaign group, with scoped dashboard/status/gating access |
| Control after giving | none, opaque | none (by construction — contributor is seated *in the campaign*, the parent stays sovereign) — `coop_has_grant` scopes it |
| Money custody | platform | the **group's Safe / treasury** — no third party holds donor money |
| Reclaim / refund | platform decides | preset rules, stated before any money moves |
| Fund destination | platform pool | the group's Safe, to the purpose, provably |

The single sentence that packages the whole difference: **"contributor gets
access, not control; the group proves its spending, not its books."**

### 2.3 Placement — the group's profile

A campaign is a group (the campaign subgroup). So it surfaces **where groups
surface**:
- On the group's public profile/home: a `Fund` card — purpose, raised-to-date,
  the sharable link, the deposit address, the progress coverage-proof.
- On the dashboard home for members of the main group: a campaign row under the
  group's surfaces.
- Non-member funders: the link surfaces the campaign *itself* (its own profile/
  component page), not the main group — so a public donor sees the campaign and
  its stated purpose, never the group's internal surfaces.

The profile placement is "available via the group's profile" by making the
campaign a *first-class surface the group can present*, exactly as it can present
a project or a file.

## 3. The four transfer shapes

All four are **the same on-chain transfer** with different *authorization and
trigger* semantics — the state machine in `transfer-authority.md` doesn't change;
what changes is who/what causes a `drafted → authorized` and whether a standing
mandate sits behind it.

### 3.1 One-time transfers

The commodity. A member/initiator drafts a transfer, it is authorized per its
path (scoped key, hold, or vote), then settles. Spark: goes through the standard
machine. "$X from the campaign to the treasury." Nothing new — this is the
monotone rail.

### 3.2 Recurring transfers

A **standing mandate with a cadence**. Approval is once, up front; the rhythm
(weekly dues, a monthly stipend, a scheduled distribution) runs on it, with each
execution a fresh `authorized` derived from the mandate, not a new vote.
Two design points from the reward where this already lives:
- Cost: reuse the **off-chain-verifier + anchor** path (`private-treasury-guards-
  ledgers.md` §8) so each recurring execution is ~$0.1–0.2, not a Safe-quorum
  re-check per run.
- Cancellable: a standing mandate is bounded (cap, allowlist, `expiry)` and revocable.
  That is the safety that makes an unattended authority acceptable
  (`transfer-authority.md` §3.3: the fast path is safe *because* of the bounds).

### 3.3 Rule-based transfer — payouts and distributions

A **distribution = a batch mandate**: the vote ratifies the *percentages* once,
the run executes per member (see `transfer-authority.md` §3.4 — per-payment voting
would make a distribution impossible). Contribution-attribution feeds it: the
percentages come from the Group's contribution tracking, ratified, then a
scheduled run pays each member's Safe.
- This is the "we raised X, split Y among members" shape.
- Rules can reference on-chain/registry state (a member still seated, a campaign
  still active, a contribution amount) so the split is derived, not re-typed, and
  `rejected by guard` catches drift.

### 3.4 Rule-based transfer — encumbrances (inter-group deals)

A deal/promise with another group or subgroup levies an **encumbrance on the
group**: a standing obligation that a transfer path triggers, without a fresh
vote, because forming the deal *was* the authorization.
- Storage: the **declared-edge registry** (`transfer-authority.md` §1) — an edge
  carrying `terms_hash` commits the promise; the encumbrance is a standing order
  on that edge.
- Trigger: when a condition dates up (e.g. a campaign subgroup releases funds to
  the group, a parent holds a dust-term payment, a coalition member that
  contributed has an agreed payout), the encumbrance resolves as an `authorized`
  transfer via standing order — the partnership's deal is the mandate.
- Enforce: the guard checks the declared edge still holds (edge live + terms
  still met, e.g. the counterparty is still a `sponsored-by`/`subgroup` edge)
  before letting the encumbrance fire. If the edge is revoked, the encumbrance
  dies with it — the deal expires the moment the relationship is closed.
- This is where campaign release (§ of capital-campaign) becomes a rule:

  a campaign hitting its release condition is a *programmed* transfer across the
  `subgroup-of`/`sponsored-by` edge, not a manual sweep.

## 4. The one design decision that prices all of it

**Whose Safe holds the funds?**

- **Campaign has its own Safe** → funds are visibly separated, the campaign has
  its own audit trail, and encumbrances/release are edges *between two Safes* —
  clean, but two guards and a custody step.
- **Campaign is a ledger on the main group's Safe** → simpler (no second
  custody), but the campaign's funds lose their own compartment and its own
  audit trail; release is a *scoped* transfer not a Safe-to-Safe edge.

Recommendation: for fundraising, **the campaign Safe** (ownholding) is the
right shape — the whole point of donations is a visibly separate, purpose-bound
bucket, and the *contribution beats surveillance/article* property
(`capital-campaign-subgroup.md` §7) wants the money visibly not mixed with the
group's operational treasury. The fractional-cost trade is worth it for
fundraising campaigns; the ledger shape is fine when the campaign is small and
internal (e.g. the release is a single internal split).

## 5. What is already decided, what's genuinely open

**Decided (anchor prior docs — do not relitigate):**
- Contributor access is scoped *by construction* (`coop_has_grant` sees only its
  seat's group); the campaign cannot govern the main group.
- Transfers are enforced by the **on-chain guard**; the app layer only predicts a
  rule before gas (`transfer-authority.md` §2).
- A distribution is a **batch mandate**; an encumbrance is a **standing order on a
  declared edge**.
- Money is never public; a campaign is **provable, not exposed** (coverage).
- Campaign terms must exclude proportional ragejust — it's a committed
  contribution, not a fund.

**Open:**
- Whose Safe holds the funds (own vs. ledger) — a governance choice per group;
  the doc recommends campaign Safe.
- Fiat-card handling: which on-ramp/rail is the card lane, and whether it lands
  straight into the campaign Safe or a shared mailbox address. The card is a
  wallet-free convenience lane; the rail/on-ramp choice lives in
  `money-in-and-out.md` / provider seam.
- Does the "campaign" cover a recurring dues goal differently than a fixed goal?
  (a campaign with a "reachable monthly" metric is a recurring-shape campaign.)
- Do encumbrances carry an expiry (a deal that lapses), and is that the edge's
  `valid_until`?
- **Minimum contribution / invite-only** config for campaigns that must not be
  open (an at-risk group), mirroring `capital-campaign-§4`.

## 6. Build order (mapped to the existing phases)

The machines exist or are in flight; the surface lands on top:

1. **Campaign subgroup + profile surface + sharable link** — depends on the
   capital-campaign pattern (exists) and a *campaign Safe* (new, minor) plus the
   fiat on-ramp (rail seam). Small, highest leverage.
2. **Coverage proof on the page** — depends on the coverage anchor (exists) and
   a public "submit the proof, not the books" endpoint. Makes it "better than
   GoFundMe."
3. **Recurring/standing mandates** — depends on the state machine (exists) +
   the off-chain verifier lane. The dues/membership economy.
4. **Distributions** — depends on attribution (exists) + batch-mandate execution.
5. **Encumbrances** — depends on the *edge registry* (§8 of capital-campaign —
   its biggest missing piece). A deal-based transfer can only be *programmed*
   once *declared edges have storage*.

So the *surface* (1-2) is buildable now; the *rule-based* stuff (3-5) is gated on
the declared-edge registry + the off-chain verifier lane materializing — which
is exactly the private-treasury/transfer work already in the plan.

## 7. Out of scope (for now)

- Individually-launched GoFundMe/Kickstarter-style micro-sites (this is group-scoped, not per-person).
- Card issuance to members (that's the treasury/visa lane, separate).
- Public read of the group's *ledger* — the coverage proof is the ceiling.
- A crowdfunding *creator-fees / take-rate* model (this is cooperative — the
  platform neither charges a creator percentage nor takes the from-scratch
  overhead GoFundMe does).