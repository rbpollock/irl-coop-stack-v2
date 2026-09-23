# Group shape and lifecycle — the group as a moving shape, not a fixed type

**Status: draft · Sep 2026.** This revises the *"group is the primitive"* claim in
[irl-coop-group.md](irl-coop-group.md) (§1.1, §2.3) and answers the two open items I flagged
there: **#3** (membership = Safe owner set) and **#4** (a one-person group has no quorum).
The frame: **a group is a node whose shape — how power is distributed across it — moves over
its lifetime through a lattice of governance configurations.** Human social dynamics are the
soft side; the Safe, roles, thresholds, and the operations are the *hard surface* those
dynamics land on. This doc is where the two touch.

Builds on: `irl-coop-group.md` (Safe-as-group, seats), `digest-group-shapes-event-bus-proofs-economy.md`
(the five-axis shape, the score-measured-not-declared rule), `event-bus-and-group-shapes.md`,
`group-account-resource.md` (the *operation* as the custody primitive, the departure ladder),
`group-home.md` (the surface it renders into).

## 1. The reframe: shape is a coordinate, not a type

A group is born with a **shape** — the five axes already settled (roles, apps, config,
*governance* [constitutional/ordinary], proofs). That was called "a seed, not a cage." The
missing half: **the seed is not static. The governance axis is the one it can move along, and
moving along it is what a group does over time** — a shape shift, a merge, a split, a
delegate. A group's *type* (coop / personal / published item) is fixed at birth; its **shape
is a moving coordinate.**

Restated plainly:

> A group is a **durable identity** (person, coop, item) wearing a **shape** — and the shape
> moves over its lifetime through a lattice of governance configurations, each move a
> **group operation**. A node is a group; its *current* shape is a point on the lattice; its
> **life** is the path it walked.

This answers "what is a node" (group-home.md's open question): a node is an identity that
owns and governs; a projection (world-doc, trade chain) is not a node. And it makes
"one-of-one" not a dead end but **the most concentrated point on the lattice — where
membership, authority, and quorum are one person.**

## 2. The lattice, not a ladder

The tempting misreading is a **ladder** — "start all-owners → democratize → council" — where
more distribution is always better. Wrong, in both directions. A fledgling group may start
with every member an owner and grow a council as it scales (decisions under load). A mature
coop may do the reverse — open a closed circle to everyone for some acts. Groups choose their
shape *for their needs and their timeframe*: a hotline wants speed (concentrated authority
during an incident), a commons wants breadth. So the model is a **lattice** of configurations,
and a life is a walk across it, either direction, many times. Four levers:

| axis | the graduated version |
|---|---|
| breadth | who can act: one → many |
| threshold | quorum: 1-of-1 … 2-of-7 … N-of-N |
| scope | what the actions touch: a seat / a scoped pool / the whole group |
| cadence | how fast a change is allowed: emergency bypass vs constitutional time-locks |

## 3. Lifecycle moves ARE the operations

The operations in `group-account-resource.md` are the moves of the lifecycle — no new
primitive is needed:

| operation | what it does on the lattice |
|---|---|
| merge | two shapes → one (a 1-of-1 folds into a 2-of-2) |
| split | one shape → two (the inverse of merge) |
| delegate | a bounded, revocable grant of authority without a shape change (the emergency seat) |
| devolve | authority moves down the chain while the group keeps existing |
| absorb | merge from the receiving side (push, not pull) |
| succeed | the terminal move — death / full dissolution, destination fixed |
| *(candidates)* attest, ratify, freeze, contest | feed / seal / brake / undo the moves |

Each move is **constitutional, not editorial** — the constitutional side of the governance
axis — has evidence, and executes at the *departing holder's own threshold while it is still
healthy* (the invariant in group-account-resource.md). So a group changing shape is not a
lighter patch; it is a **witnessed, versioned event with a threshold and an anchor.** The
same hard surface enforces both the minute-by-minute (a seat can be added) and the
generation-by-generation (a council can be adopted or dissolved). That unity is the point.

## 4. Membership vs governance (#3, fixed)

The static bug: "a person is a member **iff** their Safe is in the owner set"
(irl-coop-group.md §2.3). Under the lifecycle, **membership is a seat (broad); governance
authority is the owner-set / named role bundle (narrow) — and they may differ.** They differ
precisely because a group walks the lattice:

- a **member** holds a seat (read, post, participate).
- a **governor** sits in the N-of-M set or a named role bundle that carries authority.
- the **N of the quorum is drawn from the governance set, not from "all members."**

So a group with 500 seats can run a 2-of-3 council (a concentrated-lattice shape), and a
"shape shift" is a move of that boundary — add a council to an all-members group, or open
the council to all members — both a governance operation, never a by-product of signup.
This kills the scaling bug: onboarding a new signer adds a **seat**, not a **governance
owner**, and the group decides which seats are governors as its shape setting.

## 5. The one-person group is a shape, not a dead end (#4, fixed)

The "no quorum" worry from group-account-resource.md's open question #4 dissolves as a
category error: **quorum is the hard surface for a distributed authority; a 1-of-1 has no
electorate, so it needs none.** Its lifecycle is the simple moves — delegate (an agent),
merge (fold its holdings into another shape), succeed (its single-authority handoff) — none
of them a quorum vote. It is the zero-corner of the lattice, and "it might grow into a
merge" is the natural start state, not a broken type. That is how "every account is a
personal group" stops being a philosophical nicety and becomes the *input* to every larger
shape.

## 6. The measure and the nudge — and the line the platform must not cross

The tall ask: *the platform computes the fairness / holocratic efficacy of a group and nudges
it toward more fairness, transparency, and distributed power at every stage.* The settled
rule this must respect ("what you do gets computed, not declared"; the cooperativeness-score
formula is the vertical's, the platform only supplies the signal substrate) sets the
boundary: **the platform computes where the group is; the group — or its vertical — decides
what "fair" means.**

So the platform computes the **descriptive coordinates** (unarguable, measurable):

| coordinate | what it measures (the anti-signal it catches) |
|---|---|
| concentration | value/authority in a few hands — "100 members, 3 active" |
| quorum-dilution | how few signers can pass an action vs total members |
| concentration drift | whether one person controls the N-of-M over a window |
| shape-mobility | how the group actually uses the lattice (a merge a year ago, frozen since) |
| resilience | whether a departure breaks it (the persistence anti-signal, group form) |

Then it **surfaces** the current lattice coordinate, compares to peer shapes on the same
constraints (comparison, not verdict — "fair" varies by intent), and **proposes** a lifecycle
move as options the group can adopt or refuse ("this shape runs 3-of-something and it's slow
to react — here are two delegate or council shapes that would..." ). That is the nudge:
**measure + describe + suggest; the group decides. Encourage, not enforce** — the same
carrot-no-stick as pay-what-you-can for cost coverage.

Any step that *pushes* the group to a platform-declared optimum, or makes "fair" the
platform's verdict, turns the model into a new central authority and breaks the
"steward, not root" stance. So: **signal + geometry + options — never the verdict.**

## 7. What this changes, and what it doesn't

- **Changes**: the "group is the primitive" (irl-coop-group §1.1) into the three-part
  primitive — (a) a **durable identity**, (b) wearing a **shape**, (c) whose **life** is a
  path through the lattice, moved by the operations; and it lets §2.3 say membership =
  seat, governance = owner set, quorum drawn from the latter.
- **Does NOT revisit**: the Safe as the holder; seats as the participation primitive; the
  five-axis governance split (constitutional/ordinary); the "score is measured not
  declared / the formula is the group's" invariant.

## Open under this model
1. The lattice needs a finite set of *named* shapes (how many canonical configurations before
   the field parametrization takes over) — a scaffold for the new UI.
2. Which operations are constitutional-only vs faster paths under the same rules (is a
   merge always constitutional, a delegate never?).
3. **The trigger for the nudge**: does the platform auto-measure and offer a move on an
   event, or hold quiet until the group starts one — the "nudge" itself needing a cadence
   and an anti-nag rule.
4. How a fledgling group picks its starting shape without requiring constitutional
   fluency the day it signs up (an onboarding default, chosen later).