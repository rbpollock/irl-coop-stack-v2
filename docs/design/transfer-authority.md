# Transfer authority — and staging the edge registry

Status: design · 2026-09-29 · records two decisions, and specifies the transfer state machine.
Diagram: `docs/design/transfer-state-machine.html` (open it — it is clickable).
Related: `payout-capability.md` (who ratifies a split), `capital-campaign-subgroup.md` (the edges in
use), `money-in-and-out.md` §3.2 (the three authority classes), `delegation-and-session-keys.md`.

## 1. DECIDED — the edge registry is staged: table first, Merkle commitment later

Two things are settled, and the staging is safe for a specific reason.

**The staging.** Declared edges start as an ordinary **Layer-2 table** — queryable, joinable, cheap
to evolve. When the terms need to be *unforgeable* rather than merely *recorded*, the edge set gains
a **Merkle commitment** and the anchors to Base, exactly as Tier 2 already does.

**Why the staging is safe — and it is not merely a deferral:**

- **Access does not depend on the edge record.** `coop_has_grant(gid, g)` scopes capabilities by
  joining `group_members` — it is already group-scoped. So a campaign's contributors get correctly
  scoped access **today**, with no edge registry at all.
- **What the registry buys is auditable, enforceable terms.** That is a real need, not an
  immediate one, and it is separable.
- **The migration is additive.** A leaf is a hash over fields the table already has
  (`from`, `to`, `type`, `terms_hash`, `nonce`). Adding `leaf` and `period` columns and computing a
  period root over existing rows is a back-fill, not a rewrite — and there is no on-chain state to
  reconcile, because there is none yet.

**And the shape is already known**, because it is the Tier-2 primitive pointed at a second set of
leaves:

| Element | Tier 2 | Declared edges |
|---|---|---|
| The set | contribution entries, off-chain, hash-chained | relationship records, off-chain |
| The write path | counter-signed by a conferred authority | same — a seat, a scoped key, or a vote |
| The commitment | period Merkle root, **anchored to Base** | period root over the edge set |
| Revocation | — | **O(1)**, via a revoked-leaves set, without rewriting the root |
| The proof | inclusion against the anchored root | same — an edge is provable without publishing its terms |

`CoopRegistry.sol` already has the right *shape* for this and the wrong *label*: it holds a
`shardRoot` and a `revokedLeaves` mapping, and its `_appendMember` is an empty placeholder. **It is
a commitment registry, not a membership contract** — which is exactly what a Merkle-committed edge
set needs. Rename the intent, keep the mechanism.

**One decision the staging defers, deliberately:** whether an edge leaf commits `terms_hash` alone
or the terms wholesale. Hash-only keeps the terms private and provable; it also means verifying a
term requires holding the document. Start hash-only.

## 2. DECIDED — the guard is authoritative; app-layer is guidance

Transfers are enforced **on-chain by the guard**, with the app layer providing **advisory guidance**
only. The rule that keeps this honest:

> **If the app layer and the guard disagree, the guard is right and the app layer is a bug.**

Consequences, all of which the diagram reflects:

| | On-chain guard | App-layer guidance |
|---|---|---|
| Authority | **authoritative** | advisory |
| Runs | inside the submitting transaction, before the transfer | before the transaction is built |
| Purpose | enforce the declared terms | a clear error **before gas is spent**, naming *which* rule would fail |
| Applies to | every owner — **including the founder** | whoever is driving the UI |
| Removable | only by the authority it protects (self-binding) | n/a |

Guidance exists because `rejected by guard` is expensive in attention and cheap to pre-empt. It must
never become the enforcement point, and it must **name the rule** it predicts failing, or it teaches
nothing.

## 3. The state machine

Specified in `transfer-state-machine.html`; the guarantees worth committing to here:

1. **coop-api owns every state. The chain owns exactly one** — `submitted`, which is the only state
   that cannot be argued with.
2. **`authorized` is bounded.** It carries a deadline, and optionally a timelock with a challenge
   path. An unbounded `authorized` is a standing permission wearing a state name.
3. **The fast path is explicit.** A scoped key resolves authority instantly — `drafted` →
   `authorized` with no waiting state. This is the only unattended route, and it is why the bounds
   (cap, allowlist, expiry, rate) carry the safety.
4. **A distribution is authorised by a batch mandate.** The **vote ratifies the percentages**, not
   each payment; one mandate authorises a run. Per-payment authority would make a distribution
   impossible to complete.
5. **Every terminal state is recorded.** `settled`, `reversed`, `rejected by guard`, `expired` — all
   of them write a Tier-2 entry and join the period root. **Failure is recorded, never silently
   absent** — the same rule already applied to a refused counter-signature.
6. **The inbound lane is a different machine.** A rail payment is `pending` → `settled` → possibly
   `partial` → possibly `reversed` up to 130 days later. It is the reason a receipt means *funds
   arrived* and never *funds are final*.

### The two branches that decide the design

- **`rejected by guard`** — cap, allowlist, expiry, rate, or the authoriser being the beneficiary.
  This is a **feature, not an error path**, and it must read as a clear refusal rather than as a
  failure. It is also the branch the app-layer guidance exists to reduce.
- **`reversed`** — the reversal family arriving after settlement. This is why the vertical fund
  exists, and why a `receipt` entry is a claim about arrival rather than finality.

## 4. Open questions

- **Where do the thresholds live?** The amount at which a transfer escalates from scoped key to role
  holder to vote is a **formation-time governance decision per group**, not a constant. So it belongs
  in the group's constitution, alongside its exit and succession rules.
- **Does `authorized` need a funding check?** An authorised transfer that then fails on balance is a
  wasted authorisation. Checking at intent time is cheap; the balance can change before submission.
- **Who may cancel, and until when?** The initiator only? Any authority-holder? A timelock challenge
  implies a canceller, and the canceller is a party with power that needs naming.
- **What happens to a batch mandate when membership changes mid-run?** A distribution authorised by
  a vote, then a member is removed before execution — does the run continue, or re-ratify?
- **Is `partial` reachable on the outbound side?** Inbound is clearly partial-capable. If an outbound
  rail can also settle partially, the outbound machine needs the state too, and the two lanes stop
  being separable.
- **How much of the guidance is duplicated policy?** Every declared term checked off-chain is a term
  implemented twice. That is the cost of a clear error before gas, and it should be paid only for
  terms that are actually reachable in normal use.