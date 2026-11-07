# The Weave — Dynamic Interrelated Groups

Status: design · 2026-10-04.

Groups on irl.coop are not isolated. They form, merge, split, sponsor each other, and share
resources. A food coop and a tool library might share members. A farming coalition might spawn a
child group for seasonal labor. A city-wide federation might coordinate ten neighborhood groups.

This interrelated structure is called **the Weave**.

---

## What is a weave?

A weave is a network of groups connected by **bindings** — signed, anchorable records that confer
actual rights, not just social links.

| Binding kind | What it means | Example |
|---|---|---|
| `member-of` | I have a seat in that group | Alice is a member of the Food Coop |
| `subgroup-of` | My parent group's governance reaches me | the Eastside node is a subgroup of the City-wide Fed |
| `federated-with` | We share a sector tag and scoped availability | two food coops federated under `sector:food` |
| `sponsored-by` | They vouched for my tag or status | irl.coop attests that this group is certified organic |

---

## What already works (live)

| Primitive | How it works | Where to read more |
|---|---|---|
| **Groups ARE Safes** | Every group is a Safe. A child group is a Safe deployed by its parent's Safe. | [`irl-coop-group.md`](/design/irl-coop-group) |
| **Seat model** | `group_members` table with roles, visibility, `joinedAt`. One row = one edge. | [`irl-coop-group.md`](/design/irl-coop-group) |
| **Sector tags** | `group.tags`, optionally attested by the irl.coop group. A sector filters the weave, it does not wall it off. | [`scoped-availability.md`](/design/scoped-availability) |
| **Resource scopes** | `resource_scopes { group_id, app, resource_key }` links a group to its tenant in every app. | [`group-shape-scenarios.md`](/design/group-shape-scenarios) |
| **Declared bindings** | Append-only authority records: `role`, `key`, or `vote` confer control. Bilateral consent where a binding grants power over another. | [`declared-binding-registry.md`](/design/declared-binding-registry) |

---

## What is designed, not yet built

| Feature | Status | Where to read more |
|---|---|---|
| **Weave graph API** | `GET /api/v1/weave/:group_id` returns declared relationships scoped by caller visibility. | Not yet specified beyond this doc. |
| **Visual navigator** | `react-force-graph-2d` — zoom focuses on one group and its neighbors. No global "see all" view. | [`group-home.md`](/design/group-home) · [`platform-views.md`](/design/platform-views) |
| **Rights-set inheritance** | Child groups inherit parent `member-of` edges, filtered by scope. | [`group-model-technical-overview.html`](/design/group-model-technical-overview) |
| **Needs/offers matching** | Cross-group matching by sector, with privacy-preserving overlap proofs. | [`needs-offers-matching.md`](/design/needs-offers-matching) |

---

## Open questions

- **Clustering**: If a group has 100 `federated-with` edges, the force-graph is noise. The answer
  is **clustering by sector** — groups in the same sector collapse into a meta-node until zoomed.
  Not yet designed.
- **Cross-group treasury**: When a parent group holds funds on behalf of a child, who can spend
  and under what threshold? The binding registry covers authority, but the UI for cross-group
  proposals is not specified.

---

## Honest limits

- The weave is conceptual. No `weave` API exists, no force-graph navigator is deployed, and no
  cross-group matching runs beyond the designed event shape.
- The `needs-offers` board is a mockup with no backing table.

See [`irl-coop-overview.md`](/design/irl-coop-overview) for how this pillar fits into the whole platform.
