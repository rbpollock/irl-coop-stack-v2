# Knowledge Aggregation — the world-doc of knowledge

Status: design · Sep 2026 · Builds on mautic-calcom-mcp-inference.md (the MCP /
knowledgebase layer and client-side inference), event-bus-and-group-shapes.md
(group shapes, provisioning), world-doc-and-contacts.md (seats and the world-doc
aggregation), and the live RAG backbone (deep-agent-rag-stack on the shared
Citus — see the committed `rag-*` app specs).

## 0. The shape in one paragraph

A member's knowledge view is the **union of everything they can see** — public
knowledge bases, the knowledge areas of every group they hold a seat in, and any
direct grant. This is the same aggregation the world-doc does for the platform's
*structure* (seats, groups, contacts), applied to the platform's *knowledge*.
Three visibility tiers — **public**, **group**, **private** — feed one surface:
the "world-doc of knowledge." A group does not live in a silo; it sees its own
knowledge *plus* every public knowledge base it can reach, the same way a member
sees the union of their connected groups.

## 1. Principles

1. **Knowledge follows membership.** The caller's `groups` claim is the
   aggregation key: whatever groups a member holds a seat in, they see that
   group's knowledge area. No separate "join the knowledge base" step.
2. **Public is a tier, not a default.** `deny-by-default` holds: an area is
   visible only because a visibility rule says so (public, a group mapping, or a
   direct grant) — never by omission.
3. **One surface, not N.** The member's knowledge view is a single aggregated
   query, not a list of groups to search one at a time.
4. **The aggregation boundary is the weave's boundary.** A scoped AI (the weave)
   senses a need and may draw on exactly this union — public plus the caller's
   connected groups — and nothing beyond it.

## 2. The three visibility tiers

| tier | who sees it | provisioned by |
|---|---|---|
| `public` | any authenticated member | the coop-wide knowledge base + any group's published docs |
| `group` | the group's members (via the `groups` claim) | auto-provisioned at group creation |
| `private` | explicit members only (a direct grant) | opt-in — e.g. a group's internal-only knowledge |

`group` is the default for a group's knowledge area; `private` is a group
deliberately narrowing a scope; `public` is a group (or the coop) deliberately
widening one. The tier lives on the area itself, not on the caller.

## 3. The aggregation

A member's accessible areas are already a union of two sources:

1. **direct grants** — `area_user_roles` where `user_sub == principal.sub`
2. **group grants** — `area_group_roles` where `group_path IN principal.groups`

Because `principal.groups` already spans every group a member belongs to, the
"knowledge of all my connected groups" falls out of this query for free. What is
missing is (a) admitting `public` areas into that union, and (b) a *multi-area*
retrieval so the union is one call rather than N per-area calls.

## 4. Mapping onto the RAG

| piece | status |
|---|---|
| `area_group_roles` (group → area role) | exists |
| `area_user_roles` (direct user → area role) | exists |
| `list_accessible_areas` (the union: group + direct) | exists |
| `retrieve_area_contexts` (single-area) | exists |
| `Area.visibility` (`public` / `group` / `private`) | **NEW** |
| multi-area `retrieve_contexts` (query the whole union) | **NEW** |
| group → area provisioning (on group creation) | **NEW** (coop-api Temporal activity) |

The two RAG-side pieces are small: a `visibility` column the area gate consults
(public areas admitted to any authenticated principal), and a retrieval entry
point that fans a question out across every accessible area and merges the
ranked, cited results. The coop-side piece is provisioning — when a group is
created, coop-api mints a `group`-visibility area and writes the group's
Keycloak group id into `area_group_roles`, exactly the shape of
`provisionMatrixRoom`.

## 5. The weave symmetry

This is the knowledge substrate for "the weave." A scoped AI senses a need →
`list_areas` shows the union it is allowed to see (public + connected groups) →
it queries across that union → synthesizes. The aggregation boundary and the
weave's boundary are the same line: the AI may coordinate across whatever groups
the caller can legitimately see, and no further. Public knowledge bases are what
let groups discover each other; group knowledge is what lets them act together;
private knowledge is what a group keeps to itself.

## 6. Open questions

1. **Anonymous public.** Is a `public` area visible to *any authenticated*
   member, or also to unauthenticated visitors (a truly open knowledge base, the
   "public blueprint library" the founding vision describes)? If the latter, it
   needs a read path that skips the Bearer-token gate.
2. **Merged citations.** When a question fans out across N areas, how are the
   merged results ranked and cited — per-area provenance labels, or one global
   ranking that a member can still trace back to its source area?
3. **Cross-group dedup.** Two connected groups may hold overlapping knowledge
   (a shared doc appears in both). Does the union dedup by content, or surface
   both (letting the reader see the overlap as a signal)?
4. **Provisioning timing.** Is a group's area minted at group *creation*, or
   lazily on the first member querying it — and what happens to the area when a
   group disbands (archive, transfer to the coop, or delete)?

## 7. Why this matters

The world-doc made the platform's structure *visible as one thing*. This makes
the platform's knowledge *queryable as one thing*. A member asking "what do we
know about X" gets an answer drawn from their whole membership — their group,
their federation of connected groups, and the public commons — without ever
learning which silo it came from unless they ask. That is the difference between
"a tool per group" and "a cooperative mind."
