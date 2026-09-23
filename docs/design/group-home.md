# The Group Home — one graph, three axes

Status: design · Sep 2026 · Builds on event-bus-and-group-shapes.md (shapes, event bus),
irl-coop-group.md (Safe-as-coop, seats, roles), group-account-resource.md (group
operations), group-model-technical-overview.html (the nine pathways),
needs-offers-matching.md (the matcher). Companion docs: group-who-picker.md,
group-shape-scenarios.md, published-items-as-groups.md, private-treasury-guards-ledgers.md.

## 0. What this doc is

This is the agreed model for the group's **home surface** — the main screen a member
sees when they open the platform and "are" a group. It was designed as a game screen,
not a dashboard. It is the *interface model only*: the account resource and operation
model (group-account-resource.md) remains the data prerequisite that paused the earlier
cockpit mockup (`group-ui-mockup.html`), and this doc is what unpauses the redesign.

The through-line: **the home screen is a graph, and the graph has three axes you move
along — zoom, lens, and tense.** Everything else (the cockpit, the map, the feed) is a
view of that one graph.

## 1. The game

The platform is named **irl** — in real life. The main screen exists to sell one
feeling: *this thing is ours, it's alive, and I have a place in it.* The game is
"keep something alive that's bigger than any one of you"; cooperation is the playable
loop. A structure lens is a directory, a money lens is a ledger, a geography lens is a
map — documents. The home screen has to be a *place* you return to, not a form you
fill in.

## 2. One graph, three axes

The whole surface is a node-graph (the force diagram — `react-force-graph-2d` is
already the committed renderer). Nodes are groups and the things groups hold; edges are
relationship and flow. The same graph is viewed along three axes:

| axis | what it moves | the question it answers |
|---|---|---|
| **zoom** | scale | "how far out am I?" |
| **lens** | aspect | "which face of the group am I looking at?" |
| **tense** | time | "when?" — and the answer is **now** |

### 2.1 Zoom — scale

A person **is** a group (every account is a personal 1-of-1 group; irl-coop-group.md),
and groups nest (`subgroup-of`, event-bus-and-group-shapes.md §3.4). So zoom *is* the
navigation: me → us → region → nation. Members collapse into their group node as you
pull out; a group node opens into its people as you push in. "You are here" replaces the
tab bar. **Zoom = level of detail** — and that aggregation is the hard half of the build.

### 2.2 Lens — aspect

A lens is not a filter. It is a **different set of forces on the same nodes**: the
force layout is a physics simulation, and the lens decides which edges pull and how
hard, so the same graph re-settles into a different shape.

| lens | edges that pull | shape that emerges |
|---|---|---|
| **weave** | needs ↔ offers | who can help whom clusters |
| **structure** | membership, `subgroup-of` | subgroups clump by belonging |
| **geography** | none — nodes pin to lat/lng | the graph relaxes onto the real map |
| **money** | treasury ↔ member flows | the pool becomes the gravity well |

The **geography lens is the morph.** The abstract graph slides from *where its
relationships pull it* to *where it actually is*. That one transition is the "irl"
thesis performed as animation: *this network is this real place.* It is the signature
interaction and gets the most care.

The lenses are realized as **platform view types** — see `platform-views.md`, the view
system that renders this surface (Webstudio presentation, RLS-scoped read, Temporal
act).

### 2.3 Tense — time (default: now)

Tense is not a lens. It is the stance every lens wears. The app opens into the
**present** — the group has a heartbeat, not a history. That is what separates a place
from a filing cabinet: a feed says "here's what happened"; a heartbeat says "this thing
is alive right now."

"Now" renders as pulse and heat *on the graph*, not as a list — a node glows when
something happens to it, an edge lights when two people connect. The event bus
(event-bus-and-group-shapes.md §2) already emits everything; "now as home" is the event
stream drawn spatially instead of as a feed.

## 3. Geography shapes

Some groups collapse geography; others are intensely local. That difference is one
axis, and a group *declares* it (see §5). Four shapes:

| shape | what it is | example |
|---|---|---|
| **point** | one place | storage facility, venue |
| **route** | a line through places | delivery run, pickup loop |
| **territory** | a bounded area | neighborhood association, a region |
| **field** | everywhere its members are, no center | a global skill-sharing guild |

Local associations feeding regional feeding national = the `subgroup-of` tree rendered
as containment: a national association is a big territory containing regional
territories containing local points. **Zoom out = federation.** The map is presentation;
it does not require the federation protocol to exist yet.

Two visual languages, two layers of one screen: the **earth** (points, routes,
territories) and the **constellation** (fields, and the weave that connects across
distance). A local group is a place on the earth; a global group is a constellation
above it; the weave is the light between them.

## 4. Temperature — the verbs

The two primitive sets are different temperatures, and they do not share a surface (see
group-model-technical-overview.html §A.1 for the nine pathways, and
group-account-resource.md for the operations).

- **Hot verbs — the pathways.** Reserve, Match, Credit, Fund, Govern, Cover, Anonymize,
  Prove, Curate. Frequent, light, present-tense. In a node-plane a pathway is an **edge
  you draw, not a button you press**: Reserve = a time-limited edge between a member and
  a thing; Match = an edge between two offers; Fund = an edge from the pool to a member;
  Govern = members co-signing an edge. Playing the game = tending the graph.
- **Cold verbs — the operations.** Dissolve, Absorb, Devolve, Delegate, Succeed, Merge,
  plus the candidates (Freeze, Contest, Split, Escrow, Attest, Ratify, Restore). Rare,
  heavy, ceremonial. They live **behind a door** — a different room, with gravity (vote,
  cooldown, confirmation). Freeze and Contest are the brake and the undo; they should
  feel like it.

The present is for living; the door is for ending.

## 5. Attestation — the shape is declared, not configured

The group's profile splits into two temperatures, the same line as §4:

- **Ordinary settings** (hot) — app bundle, delivery prefs, which pathways sit on the
  quick bar. Changed casually, no ceremony.
- **Attestations** (constitutional) — what we are, where we are, what we're for. Signed,
  witnessed, versioned. Changing one is an *event*, not a save.

This generalizes "attest" from its origin in group-account-resource.md (the
evidence-feeding operation): **attest is the primitive by which a group declares what it
is.** The shape is the first and most basic attestation — including the geography shape
("we are a territory", "we are a field").

The honest tension: a group attesting to itself is self-declared, and the design's own
rule is *evidence must not be self-declared*. So attestation carries a **confidence
ladder**:

- **self-attest** — "we call ourselves a coop." Cheap, immediate, aspirational.
- **witnessed** — another group co-signs: "the regional association confirms we're their
  local chapter."
- **proven** — a badge or proof: "verified — we served 40 households last season."

What you *are*, you declare. What you *do*, gets computed — the same principle as the
cooperativeness score being measured, not claimed
(digest-group-shapes-event-bus-proofs-economy.md).

The payoff: the profile is the group's **character sheet**; the graph is the group **in
play**. The attested shape decides how the group renders — its geography shape, its
default lenses, its active pathways. Ordinary settings are the sliders; attestations are
the backstory that stays true until re-declared.

## 6. Open questions

1. **What is a node, exactly?** Person, group, thing, offer, money-pot, event —
   "everything is a group" (published-items-as-groups.md) says they're uniform, but the
   mixed types need names.
2. **The ambient baseline.** What "now" looks like when nothing is happening — the
   heartbeat. The graph must read dormant, not dead.
3. **Is the past reachable?** Scrub back to last week / the season, or does "then" live
   in a quieter records surface so the living graph stays act-able?
4. **The door.** What the operations room *is*, visually, in a graph world — a place in
   the graph (the group's core), or a separate room entirely?
5. **Aggregation.** The level-of-detail core: how members collapse into groups at
   zoom-out without losing legibility.
6. **The confidence ladder's mechanics.** How "witnessed" works — who may witness what,
   at what threshold, and how a witness is itself attested.
