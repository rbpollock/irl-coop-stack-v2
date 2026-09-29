# The capital campaign subgroup

Status: design · 2026-09-29 · a reusable pattern for contributors who are not governors.
Related: `account-and-key-model.md` (seats, edges, the four dimensions, formation defaults),
`payout-capability.md` (steward + vote ratification), `provider-seams.md`, `group-scoping.md`.

## 0. The pattern

> **A subgroup representing the campaign is created for contributors. Contributing makes you part
> of it. Its preset rules say what happens to the funds. Its members get scoped access — dashboard,
> status, gating — and acquire no control over the group. It can dissolve, or fold into the group.**

This is the right answer to the contributor problem, and it is right for a structural reason rather
than a permissioning one: **it puts contributors somewhere real instead of adding roles to the
group.** They are members of something, with access to that thing's surfaces, and the group's
governance is untouched.

## 1. The structure

```
main group  (the group Safe, its owner set, its governance)
   │
   │  subgroup-of   — declared: infra + trust scoping, parent governs the child
   ▼
campaign group  "Capital Campaign — <purpose>"
   ├── funds: contributed USDC (+ the campaign's own Safe if it needs one)
   ├── seats: contributors, role `campaign-contributor`
   ├── surfaces: its own dashboard, status, project, gating
   └── preset rules: where funds go, when, and what dissolves it
        │
        │  sponsored-by  — declared: ECONOMICS ONLY. one-way flow, recognition, no control
        ▲
   contributors  (seated here only — never in the main group's owner set)
```

Two declared edges, and they point in opposite directions on purpose:

| Edge | Direction | Carries | Does *not* carry |
|---|---|---|---|
| `subgroup-of` | campaign → main group | the parent's authority to govern, dissolve and fold the child | — |
| `sponsored-by` | main group ← contributors | economics and recognition | **any control over the main group** |

That is `account-and-key-model.md`'s own vocabulary doing exactly what it was designed for:
**"ownership implies membership ONLY — every other meaning is DECLARED in the on-chain relationship
record, never inferred."**

## 2. Contributing makes you part of it

The mechanic: **a contribution mints a seat in the campaign group.**

- The deposit is the trigger; the seat is the membership. No admin has to add anyone, and the
  contributor becomes a real member of a real group immediately.
- **The seat's role comes from the preset rules** — `campaign-contributor` at minimum, possibly
  tiered by amount, with the tier mapping to more or fewer scoped grants (not to more control).
- **A minimum threshold is required.** "Anyone who sends money gets access" is safe only if the
  amount is meaningful or the campaign is invite-only; otherwise a trivial transfer buys a seat.
  The campaign's `privacy` setting (`open` / `members` / `hidden`) decides who may contribute at
  all, and that should be a deliberate choice at creation.
- **What contributing does *not* do:** no owner seat, no vote in the main group, no claim on the
  main group's assets, no share of its future revenue. Those are not withheld by policy — they are
  simply not created, because the contributor is seated in the campaign and nowhere else.

## 3. Why "scoped access without control" is a property, not a promise

This is the part that makes the pattern sound, and it is **already true in the code.**
`coop_has_grant(gid, grant)` resolves grants like this:

```sql
FROM group_members gm
JOIN roles r ON r.name = ANY(gm.roles)
JOIN role_grants rg ON rg.role_id = r.id
WHERE gm.group_id = gid
  AND gm.sub = coop_current_sub()
  AND rg.grant_name = g
```

Note `gm.group_id = gid`. **Grants are scoped to the group the seat is held in.** So a
`campaign-contributor` seat in the campaign group confers capabilities **in the campaign group and
nowhere else** — not because a rule forbids otherwise, but because the function cannot see across
groups. Contributor access is scoped by construction.

Roles themselves are global definitions (`roles.name` is unique) but are **held per group** through
`group_members.roles`. So the campaign's contributor role is one definition, and its reach is exactly
the campaign.

**And the reverse protection matters just as much:** the campaign cannot govern the group, because it
holds no seat in the group.

## 4. The preset rules

The campaign's terms, **disclosed before any money moves** and enforced by the campaign's guard —
the same self-binding pattern used for reserved powers (`account-and-key-model.md`: *"Enforcement is
local and self-binding… the child cannot opt out"*).

| Rule | Must state |
|---|---|
| **Purpose** | what the campaign is for |
| **Release** | what triggers funds moving to the group, on what schedule, against what condition |
| **Non-refundability** | that a contribution is committed, and **explicitly not** a withdrawable share |
| **Dissolve** | what happens to any residual if the campaign ends or fails |
| **Disclosure** | what contributors can see (see §7) |

**One rule that must be stated, because the default in this design is the opposite: ragequit.**
`account-and-key-model.md` gives members a proportional unilateral exit — correct for a cooperative
and **wrong for a capital campaign**, whose money is committed to a purpose and partly spent. So the
campaign's rules must exclude proportional exit over contributed funds, and say so plainly. A
campaign where contributors can pull out pro-rata at any moment is not a campaign; it is a fund.

## 5. This is a sponsorship, not an investment — hold that line

The name "capital campaign" invites a misreading that must be closed explicitly:

> A contribution buys **recognition and access**. It does **not** buy equity, a share of the group's
> assets, a claim on its future revenue, or a vote. **No return is promised or implied.**

Two reasons this is a design requirement rather than legal boilerplate:

1. **Otherwise it is an offering.** A contribution that entitles the payer to a share of future value
   is an investment instrument with an entirely different regulatory shape — and it would be the coop
   drifting into a role it has explicitly refused everywhere else.
2. **Otherwise the group is permanently obligated.** If contributors hold a claim on the group's
   future, the group can never be said to have earned anything of its own, and every later decision
   runs against a standing liability.

The `sponsored-by` edge is precisely right for this: *"economics: one-way flow, recognition, no
control."* The disclosure belongs in the preset rules, in the plainest available language, and the
word "campaign" should carry a clear definition rather than an aspiration.

## 6. Dissolve, and fold

Both are **declared operations**, not restructurings — which is the payoff of *"nothing is
inherited, everything is declared."*

**Dissolve** — the campaign ends, successfully or not:
1. Residual funds move per the preset rules (to the group, or returned per the stated rule).
2. Contributor seats are **revoked** — the campaign group is archived, and the seats stop resolving.
3. The declared edges are closed and the record retained, so the campaign's history stays auditable.

**Fold** — the campaign succeeds and is absorbed:
1. Funds transfer to the main group (a Safe-to-Safe transfer, or a routed rail payment).
2. The `subgroup-of` edge is closed and a `sponsored-by` edge is written **directly on the main
   group**, so the contribution is still recognised.
3. Optionally, contributors receive a **scoped, non-governing role on the main group** — status and
   dashboard access, a "founding supporter" surface, and nothing more. `coop_has_grant` scopes it
   there, so it carries no control.

Because both are registry changes plus a transfer, **neither requires restructuring anything.** That
is the strongest argument for the pattern: the campaign is a *shape the group can take*, not a
change to what the group is.

## 7. Progress is a coverage proof

A campaign needs a public progress surface — "we raised X and spent it on Y" — and the design already
has the right primitive. `anchors.family` is `('tier2','custody','coverage')`, and `db.ts` describes
the coverage family as the way a *"cross-group claim (coverage, cooperativeness) is provable without
any group"* publishing its books.

So:

- **The campaign publishes a proof, not its ledger.** "Raised ≥ X", "spent ≥ Y on Z", "the funds
  reached the purpose" — each provable against an anchored root.
- **Donor trust without donor surveillance.** Contributors get status and a verifiable claim; the
  group's amounts and members stay private (`money-in-and-out.md` §3: money is never public, always
  provable).
- **For an at-risk group this is the difference between fundraiseable and not.** A public campaign
  that cannot prove its spending is unpersuasive; one that proves it while publishing nothing is
  exactly the design's promise.

## 8. What is missing

**The declared-edge registry has no storage.** There is **no relationship or edge table** in the
schema — the vocabulary (four dimensions, four types, "ownership implies membership ONLY") is
designed, and the on-chain registry that was meant to hold it (`CoopRegistry.sol`) is a **51-line
stub with an empty `_appendMember`**. So `subgroup-of` and `sponsored-by` are expressible *in
language* and not yet *in data*.

Two mitigating facts:

- **The effect works today without it.** The scoped-access property (§3) comes from
  `coop_has_grant` scoping to the seat's group, which is live. The campaign can be built and used
  before the edge record exists — the edge is what makes the *terms* auditable and tightable to a
  guard.
- **A projection table is the interim answer**, exactly as the seats themselves are a Layer-2
  projection of Layer-1 truth. The edge record can start as a table and be rebuilt on-chain later,
  which is the same discipline `group-scoping.md` already sets.

## 9. Open questions

- **Does the campaign need its own Safe?** If contributions are held in the campaign's own Safe, the
  parent governs it and the funds are visibly separate. If they go straight to the main group's Safe,
  the campaign is a *ledger* rather than a *holder* — simpler, but the funds lose their own
  compartment and their own audit trail.
- **Who may contribute?** Open campaigns are the fundraising default; some groups must run invite-only
  or hidden ones. That is a creation-time choice, and for a threatened group it is a safety choice.
- **What does the minimum contribution buy in?** One threshold, or tiers mapping to more grants? Tiers
  are attractive for recognition and dangerous for expectations — a tier that looks like a class is a
  class.
- **Do folded contributors keep access forever?** The fold can grant a recognition role on the main
  group; whether it expires (like every other scoped grant here) or persists is a governance decision
  the group should make *at creation*, not at fold time.
- **Does a failed campaign return funds pro-rata?** The preset rules must answer this, and the answer
  interacts with §5: a pro-rata return on failure is not a return *on* contribution, so it does not
  make it an investment — but the wording has to be precise enough to survive being read that way.
- **Can one campaign overlap another?** Two campaigns for the same purpose, or a campaign nested in a
  campaign, are both expressible — and both are ways to accidentally recreate the governance the
  pattern exists to avoid.