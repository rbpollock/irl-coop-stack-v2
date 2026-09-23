# Group UI — build checklist (todo)

Status: **living todo** · Sep 2026 · The group **home** surface is DESIGN (not built) —
`group-home.md` (interface model: one graph, three axes) + `group-account-resource.md`
(the data prerequisite that pauses the mockup) + `platform-views.md` (the view system
it renders in). This file is the *do-list* for taking that design to a built surface.
Tick boxes as work lands. Companion docs: `group-home.md` (the model),
`group-ui-mockup.html` (the paused cockpit mockup), `platform-views.md` (render/read/
act), `needs-offers-matching.md` (the weave), `event-bus-and-group-shapes.md` (bus +
shapes), `irl-coop-group.md` (Safe-as-coop, seats), `published-items-as-groups.md`.

## Already true — do NOT rebuild
- [x] `react-force-graph-2d` is the committed node-graph renderer.
- [x] The **weave** lens (needs ↔ offers matching) has a working force-graph build
      (`needs-offers-matching.md`; dashboard home force-diagram session 20260823).
- [x] The event bus + shapes (`event-bus-and-group-shapes.md` §2) emit everything
      the "now/heartbeat" needs; the map app exists.
- [x] `platform-views.md` settles the view system: render = Webstudio, read = NocoDB +
      coop-api (RLS `app.sub`), act = Temporal.

## Phase 0 — un-pause (data prerequisite)
- [ ] Land the account-resource model (`group-account-resource.md`) — the earlier
      cockpit mockup was PAUSED on this; resolving it un-pauses the redesign.
      It is the install that makes "hot" pathway edges (member ↔ thing, group ↔ pool)
      real, not mock.
- [ ] Decide the mixed-node vocabulary (open question 1) — what a node *is* before
      drawing it.

## Phase 1 — the graph core (the playable loop)
- [ ] One graph surface, three axes: **zoom**, **lens**, **tense** (`group-home.md` §2).
- [ ] Zoom = navigation. person-as-group nesting: `subgroup-of` tree (`§2.1`); members
      collapse into group nodes on zoom-out, a node opens into people on zoom-in.
      **This aggregation is the hard half of the build.**
- [ ] Tense defaults to **now** — the app opens into the present; heartbeat not
      history (`§2.3`).

## Phase 2 — the lenses (re-layout, not filters)
- [ ] Lenses as distinct force sets on the same nodes (`§2.2`): **weave, structure,
      geography, money** — each re-settles the graph, doesn't filter it.
- [ ] **Geography = the morph** — the signature interaction. Abstract graph slides
      (from "where relationships pull it") onto the real map ("where it is"). Most care.
      Uses the existing map app as a lens, geography is not the default lens.
- [ ] Rendered as platform view types (Webstudio presentation, RLS-scoped read).

## Phase 4 — "now" as a place, not a feed
- [ ] Heartbeat on the graph: node glows on an event, edge lights on a connection —
      the event stream drawn spatially instead of as a feed. Draws on the bus.
- [ ] Resolve the ambient baseline (open question 2) — what "now" looks like when
      nothing happens; graph must read dormant, not dead.
- [ ] Decide: is the past reachable, or does "then" live in a quieter records surface?
      (open question 3 — likely the quieter-records answer.)

## Phase 5 — temperature: the verbs (see §4)
- [ ] **Hot verbs** = pathways drawn as edges (Reserve, Match, Credit, Fund, Govern,
      Cover, Anonymize, Prove, Curate).
- [ ] **Cold verbs** = operations behind a door (Dissolve, Absorb, Devolve, Delegate,
      Succeed, Merge, + candidates Freeze/Contest/Split/Escrow/Attest/Ratify/Restore).
      [ ] Resolve what the "door" *is* visually in a graph world (open question 4).

## Phase 6 — attestation & shape
- [ ] Profile splits into ordinary settings (hot) vs attestations (constitutional) —
      changed as an event, not a `save`.
- [ ] Attestation confidence ladder: self-attest → witnessed → proven. Resolve the
      mechanics of "witnessed" (open question 6).

## Open to resolve (before/during build)
1. What is a node, exactly? Person/group/thing/offer/money-pot/event need names in a
   mixed graph.
2. The ambient baseline (dormant-not-dead heartbeat).
3. Is the past reachable, or does "then" live on a separate records surface?
4. What the operations room ("the door") looks like in a graph world.
5. Aggregation: level-of-detail core — members into groups at zoom-out, legible.
6. Confidence-ladder mechanics: who witnesses what, at what threshold, and how a
   witness is itself attested.

## Notes
- geography lens is presentation; it does NOT require the federation protocol to yet
  exist (map is presentation).
- The map is a lens, not the default lens; irl == geo is a thesis-transition, saved
  for the geography morph.
- This checklist is the UI build only — the data + operation model lives in
  `group-account-resource.md`; where the two meet is Phase 0.