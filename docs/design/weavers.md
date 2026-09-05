# Weavers — matching needs to offers across parties

Status: design · future · dropped for reference 2026-08-30.

A **weaver** is a person or group who takes responsibility for connecting
needs/offers in a complex multi-party (or two-party) transaction. It is the
"glue" primitive that binds several collaboration features together.

## The shape of it

The canonical scenario: individual farms (or a farm group) need delivery to a
farmer's market. A weaver connects:

- a **transportation offer** (a person-with-a-van)
- **several farms** into a **pickup schedule**
- a **route** — planned, visible and trackable on the map, with group settings
  for visibility
- optional **insurance** — provided by another group, or by the weaver themselves

The weaver may also opt to **be the transporter** (one role, not a separate entity).

## What makes it a hardcore primitive

It is a **matching + orchestration + trust** layer over the existing primitives:

1. **Matching** — needs/offers are typed (transport, harvest, storage, labour,
   insurance, capital). A weaver is the human/social resolver that matches them
   when algorithmic matching is too coarse for multi-party reality.
2. **Multi-party orchestration** — a transaction is not A↔B but a *graph*:
   N farms → one van → one market, plus an insurer. The weaver holds the graph.
3. **Route + map** — the pickup schedule is a real route, drawn on the sovereign
   map (tracks), trackable live, with per-group visibility (the group visibility
   policy already in the maps design).
4. **Trust / assurance** — insurance is itself a group (or the weaver's own
   offer). Reputation/accountability flows through the group membership + proofs
   machinery, not a platform rating.

## Design dimensions to resolve (later)

- **The transaction object** — a first-class "match"/"agreement" entity joining
  N offers + N needs, with states (proposed → agreed → in-flight → settled).
  Is it a group? A track? A new primitive?
- **Weaver as a role vs a capability** — is "weaver" a group role (in the group
  shape's `roles` axis), a capability grant, or a standalone identity that spans
  groups? Likely a **capability** (metric-agnostic seam, like tour-moderator) so
  it can later gate on ZK-verified reputation.
- **Liability & insurance** — who is on the hook when the van breaks or the
  harvest rots. Insurance as a *group offer* (another group underwrites), with
  the coverage proof / claim flow tying into treasury + ledgers.
- **Route as a first-class object** — the pickup route is a `track` (route kind)
  with scheduled stops (waypoints = farms + market). Live tracking = the existing
  live-location machinery. Visibility = the existing 5-tier scope.
- **Settlement** — how money/credit moves between farms, transporter, weaver,
  insurer. Ties into the treasury + group-of-groups economics (the `sponsored-by`
  / budget-transfer edges).
- **Federation** — a weaver works *across* groups (a group-of-groups operation).
  The needs/offers it matches come from multiple groups; the match is a
  composition, not a merge (consistent with seeds-not-cages).

## Cross-reference map (existing primitives, cited)

Each weaver element maps to an *already-designed* mechanism. None requires new
architecture; all require new **composition** (seeds-not-cages: assemble
primitives, don't subclass them).

| Weaver element | Existing mechanism | Where |
|---|---|---|
| Multi-party match graph | offers/asks matcher → `match.*` events. The bus already anticipates "future sources" — "the offers/asks matcher emits `match.*` with zero bus changes." | event-bus-and-group-shapes.md §2.3 |
| **Weaver = human resolver** | the **coordination family**: `person:<sub>` (handoff target) + `queue:<vertical>:volunteers` (FCFS) resource types; the response-router escalation ladder (deterministic → agent → human). The weaver *is* the top tier of this ladder — a named human who resolves what the matcher can't. | delegation-and-session-keys.md §9.5 |
| Weaver as capability | metric-agnostic **capability** seam (the `tour-moderator` pattern); "roles are bundles of scoped ERC-7715 grants," so a `weaver` role = the grant bundle, and it can later gate on ZK reputation without rework. | sovereign-maps-tracks.md §"Comments + capability gating"; delegation-and-session-keys.md §7 |
| Pickup route + tracking | `track` with `kind: route`, `waypoint` stops (farm = waypoint), live-location machinery, 5-tier visibility. "a group's delivery route = a saved `route` track." | sovereign-maps-tracks.md §"Tracks & geo-tours", §"API", §"live location" |
| Group visibility settings | `visibility_policy` on the group **shape** (`discoverable`, `max_visibility`, `default_visibility`, `require_approval`) — the "group settings for visibility" the user asked for, already designed. | sovereign-maps-tracks.md §"Group visibility policy" |
| Insurance as a group offer | the closest designed analogue is a **risk pool**: the vertical fund's "Reserve" sub-account absorbing losses (the chargeback model) — an insurance group is the same shape (a fund whose Reserve underwrites the weaver's liability). | private-treasury-guards-ledgers.md §10 |
| Settlement across N parties | Tier-1 (money, shielded, conservation in-circuit) vs Tier-2 (labor/participation, hash-chained); project **sub-scopes** inside one treasury. | private-treasury-guards-ledgers.md §4, §2.1 |
| The transaction object | a **project sub-scope** inside a treasury that **promotes to a child group** (`subgroup-of` + `sponsored-by` edges) when it needs its own allocation or autonomous decisions. "The child is a full group." | private-treasury-guards-ledgers.md §1.5; event-bus-and-group-shapes.md §3.4 |
| Adopting weaver into groups | `app_activations` + reconciler; a new feature ships **optional/opt-in** (lazy hook fires on first use), not eager-swept into every group. | event-bus-and-group-shapes.md §5.2 |
| Accountability / reputation | regenerative score (flow / reciprocity / distribution / persistence) + the reputation-derived, **human-gated** bad-actor signal (investigation, not algorithmic application). | event-bus-and-group-shapes.md §6; private-treasury-guards-ledgers.md §10 |

**Seed scenario.** The weaver's canonical case is already in the catalog —
scenario 6 "Farmer exchange" (manure↔veggies, seasonal labor, "20 hands to
harvest, paid in food"). Its flagged gap — *resource match + labor pool* — is
exactly what the weaver resolves. group-shape-scenarios.md §6.

## The parked-federation tension

The weaver is inherently **cross-group** (it matches offers from several farms,
an insurer from another group, a market event). That collides with the parked
federation question (do not design yet). Resolution for now, consistent with
the parking: a weaver operates **within an already-related group-of-groups** —
groups that share an explicit `subgroup-of` / `sponsored-by` edge — and
composes member-group needs/offers over the shared bus. Full *federated*
offer/need discovery (a weaver matching strangers with no prior relationship
edge) is federation, and stays parked. Flag, don't design.

## Open question

Is "weaver" a *feature* (a match/agreement surface) or a *primitive* (a typed
relationship graph that other apps — delivery, skill-sharing, childcare, tool
libraries — all reuse)? The user's framing ("a hardcore primitive, a glue that
binds together several critical features") points at the latter: design the
**match/agreement graph** once, and every vertical's needs/offers become nodes
on it.
