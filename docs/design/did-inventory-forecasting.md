# DID inventory — forecast-driven number provisioning

Status: **design** (a model/plan, not yet built). Extends `telephony-trunking.md`
(one Telnyx account, per-group DIDs). This doc answers a *different* question
than trunking: not "how does a number route," but **"how many numbers do we
buy, where, and when"** — as a demand-forecast + capacity-planning discipline.

## Goal

Stop reacting to DID demand one-signup-at-a-time (paying whatever the spot rate
and setup latency impose). Instead treat **number inventory as a reorder-able
stock**, bought *ahead* of demand in batches, sized by a projection of group
telephony need per region, and attributed to the same commons/vertical-fund
economics every other coop resource uses.

## Why this is a real problem (not a nice-to-have)

| Constraint | Consequence |
|---|---|
| **Rate-center locality** | A DID must be local to its group. A surplus in Portland does not cover a stockout in Peoria. Inventory is **per rate-center**, not global. |
| **Setup latency** | DID provisioning is not instant. A signup that wants a number today should not wait on a carrier round-trip — carry **safety stock**. |
| **Tiered wholesale cost** | Unit DID cost drops with volume. Batch-buying against a forecast beats one-off purchases, both in price and in admin overhead. |
| **Churn returns numbers** | Groups dissolve → their DIDs return to the pool. Release-rate is a *replenishment* input, not a one-way drain. |

## The model

```
projected_need(rate_center, t) =
    projected_groups(rate_center, t)          # signup funnel
  × adoption_rate(rate_center)               # fraction that ENABLE PSTN (opt-in)

target_inventory = projected_need(horizon) + safety_stock

reorder decision:
  if on_hand − projected_need(lead_time) < reorder_point:
      buy  batch_size = target_inventory − (on_hand + on_order)
```

The DID is consumed **only at the enable-PSTN moment**, not at group creation.
Every group starts with internal telephony by default — reachable through the
main irl.coop number + its group/extension, free, no carrier involved. Opting in
to PSTN is the sole, deterministic event that draws from inventory, which makes
the demand signal an *action* (a switch flipped) rather than a *guess* (a
share of signups).

**Terms**

| Term | Meaning | Source |
|---|---|---|
| `projected_groups(t)` | groups in this rate-center expected by month `t` | Keycloak realm + signup funnel + group-shape telephony flag |
| `adoption_rate` | % of groups that will **enable PSTN** (flip the opt-in switch) | observed; seeded low |
| `internal_only_share` | **not needed** — internal telephony is the *default*, not a share | product invariant |
| `safety_stock` | buffer for lead-time + churn spikes | × lead-time, tuned |
| `reorder_point` | inventory level that triggers a buy | `= demand_during_lead_time + safety_stock` |
| `release_rate` | DID/min returned by dissolving groups | churn observation |

## Why the funnel already feeds this

The inputs are all *already logged* — this is a projection over data the coop
owns, not external market research:

- **Enable-PSTN events** — the opt-in switch is the demand signal itself. Each
  flip is a logged, dated event, so `adoption_rate` and its trend are computed
  directly from the enable stream (no `kind` flag needed, no guess).
- **Signup growth** — Keycloak realm (`irl-coop`) + `provisionOnSignIn` (defaults
  to internal telephony; costs nothing, touches no DID inventory).
- **Churn/release** — group lifecycle events → `release_rate` (a disabled PSTN
  group returns its DID to the pool).

The reorder rule is thus a **funnel-driven inventory reorder**, the same shape
as any stock control, applied to numbers instead of parts.

## Data shape (plan artifact, not yet a schema)

Per rate-center row:

```
rate_center        "Augusta ME" / "Portland ME" / ...
area_code          207 (the Northeast/Maine pool)
projected_groups   [monthly series]
adoption_rate      float 0..1
internal_only      float 0..1
safety_stock       int
lead_time_days     int (carrier provision)
on_hand            int
on_order           int
reorder_point      int (computed)
target_inventory   int (computed)
unit_cost_tier     $ (wholesale at current volume)
```

A small `infra/scripts/` forecasting tool computes `target_inventory` and flags
rows where `on_hand − projected_need(lead_time) < reorder_point` — the *buy
list* the operator acts on. (Script is the first deliverable; a live engine in
coop-api is a later, optional stage.)

## Region strategy

First inventory: **Maine / Northeast US** (area code 207), because the early
groups are there and the rate-center is a single coherent pool. Expansion is
*per-rate-center* — entering a new region means seeding a new pool with its own
forecast and safety stock, never borrowing from the first.

- **Buy in the local rate-center** so DIDs are genuinely local to the group
  (the cooperative identity is regional; a Peoria number on a Maine group is a
  stockout in disguise).
- **Portable numbers are the long-term asset.** DIDs we resell must be
  port-able between carriers or the broker layer owns a stranded liability.
  Telnyx allows port-in/out; treat "irl.coop owns the number, not the carrier"
  as the load-bearing property.

## Who holds the carrier relationship (settled: aggregate)

One **irl.coop-level** Telnyx account, not per-group accounts. Reasons, in
weight order:

1. **KYC concentrates once.** Provisioning numbers is KYC-gated by regulation —
   no PSTN DID exists with zero identity disclosure. One account means one
   accountable signer (a registrar/steward role) is KYC'd once; the coop's
   already-public legal entity is the account record. Per-group accounts would
   push KYC onto every group, which an unincorporated volunteer group cannot
   pass.
2. **A-level STIR/SHAKEN survives.** Cross-group caller-ID (`caller_id_grants`,
   `telephony-trunking.md`) stays A-attested only because all numbers sit under
   one account. Across separate accounts it degrades to B-attestation or fails.
3. **Voice-first keeps the disclosure shallow.** The EIN / 10DLC / branded-calling
   deep-corporate disclosure is *absent* from the plain voice-DID tier. SMS stays
   on TextBee (separate SIM), so the EIN requirement never materializes per-group.

**KYC surface (be precise):** at the voice tier it is a business-email domain +
a KYC identity check on *one* designated signer (government ID + liveness). Not
"staff doxed to Telnyx" — one accountable role, plus the coop's public legal
name/address (already in its incorporation record). Deeper entity disclosure is
deferred or avoided by voice-first. *(Open detail: the exact ID artifact the
voice-tier KYC demands — confirm on the live signup flow before treating as
settled.)*

The telnyx account is **carrier-of-record**; groups are **end customers** on
Telnyx's reseller model ("use the end customer's info on the LOA; the end
customer signs") — number ownership sits with the group and ports out in the
group's name, while the account stays coop-level.

## Cost attribution (commons)

DID cost is a **per-group resource cost, treasury-underwritten, coop-aggregated,
settled at cost** — not a coop markup. The group's Safe treasury is the source of
funds (existing pattern: `published-items-as-groups.md` §4); coop-api meters the
group's DID + minutes and debits its vertical-fund account monthly. irl.coop
floats the aggregate Telnyx invoice (≈$35/mo at 20 groups) and settles per group —
an accounting float, not a rent.

Effective unit cost (not the headline $1.00):

| Line | Cost |
|---|---|
| US local DID | $1.00/mo (volume discount only ≥50 purchased/mo — not reachable at alpha/beta scale) |
| E911 | separate monthly charge per number (optional but expected for real outbound) |
| USF + regulatory passthrough | mandated, usage-based, applies to every VoIP/DID customer |
| **Effective floor** | **≈$1.50–2.00/mo per enabled group** |

**No pre-pay.** Telnyx is pay-per-number-per-month, no contract, no setup fee,
no volume break below 50/mo. Pre-paying a DID carries the same $1/mo with no
price advantage — it would front-load cash against a self-funded beta for zero
gain. Commitment/sustainability is a *member/treasury* concern (annual
membership already *is* the commitment; a group's funded treasury reserve is the
real signal), not a carrier pre-pay.

**No batch-buying yet.** The \(50/mo\) discount is a *monthly purchase-volume*
threshold, not a held-inventory threshold — buying ahead does **not** trigger it,
and front-loads carrying cost. At ~20 groups the optimal policy is blunt:
**buy just-in-time as groups enable PSTN.** The forecasting/reorder model earns
its keep only as scale approaches the 50/mo cliff.

## DID lifecycle (grace / park / release)

A number is part of a group's public identity; losing it is a disproportionate
penalty for a missed month. Stewarding means holding it through hardship. Three
states, sharply separated so the goodwill never becomes an unfunded drain:

```
active ──(payment missed)──▶ grace ──(window lapses)──▶ parked ──▶ released
                              │                           │          (→ DID pool)
                              │ inbound STILL connects;   │ number held &
                              │ outbound throttled to     │ suspended, no
                              │ internal/free; "renew"    │ call path.
                              │ prompt injected on calls  │
                              └────(payment made)────────▶ active
```

- **`grace`** (voted length, seed ~30 days): number held **and** inbound still
  connects — people can still reach the group. Outbound is gated to free/internal
  (the abuse vector). The cost of carrying this is tiny (~$1.75 + inbound
  sub-penny/min).
- **`parked`**: grace lapsed but the number is **not released** — held
  deterministically at ~$1.75/mo, no call path. "We didn't destroy their identity,
  but we also didn't keep paying their traffic."
- **`released`**: only after `parked` expires (or explicit dissolution). Only
  now does the DID return to the inventory pool.

**Pay-by-phone renewal** — the automated prompt is a feature, not just a notice.
During `grace`, inbound and outbound calls carry an IVR prompt: "this group is
in a hardship grace period; calls continue. Press 1 to restore full service now"
→ a pay-by-phone flow on the same vertical-fund rails, or a spoken "connect me to
the group steward." This is the voice-agent landline doing its first real job: a
number that *speaks* a group's state rather than going dead.

**Two voted numbers, not assumed defaults:**

1. **Grace window** — how long to hold + connect before parking.
2. **Who funds the grace float** — default lean: the group **pre-funds a small
   reserve** (~1 month) as the condition of enabling PSTN, *and* the coop holds
   the DID through grace as a commons gesture. The group's buffer funds the
   continuation first; coop goodwill second; never an unbounded drain.

## Open items

- **Voice-tier KYC artifact** — confirm exactly what the Telnyx "verified" (Level
  2) identity check demands for voice DIDs on the live signup flow (government ID
  + liveness vs. softer) before treating the KYC-surface claim above as final.
- **E911 + USF passthrough amounts** — get the real per-number E911 charge and
  regulatory passthrough for the 207/Maine rate-center so the ≈$1.50–2.00 floor
  is a measured figure, not an estimate.
- **Grace window + grace-funding** — the two *voted* numbers (§ lifecycle): how
  long to hold+connect, and whether the group's pre-funded reserve or the coop's
  vertical fund (or both) funds the float. Seed values, to be ratified.
- **Enable-PSTN event captures a timestamp** — the reorder forecast is only as
  good as the stream of enable flips; make sure the opt-in writes a dated event
  (it should already, via the event bus) so `adoption_rate` trends are computable.
- **Port tests** — validate in→out porting cost/terms under the reseller/end-customer
  model before the pool grows.
- **Script vs engine** — ship the `infra/scripts/` forecasting tool first; an
  in-DB inventory engine is a later slice.

## Reads like a plan for

A first inventory buy for **207/Maine**: seed N DIDs (a small batch sized to
the earliest groups + safety stock), then reorder per the rule above as the
signup funnel reports `projected_groups`.
