# ZK-Metric & Membership Proofs — the provable-but-private group graph

Status: design / feasibility-assessed · Aug 2026.
Builds on: [group-scoping.md](group-scoping.md) §3 (hidden-norm, provable membership),
[private-treasury-guards-ledgers.md](private-treasury-guards-ledgers.md) (ZK substrate,
notes/commitments/nullifiers), [account-and-key-model.md](account-and-key-model.md)
(relationship registry, the four relationship types).

## 1. The primitive

The stack's group graph is **hidden by default, provable on demand** (group-scoping
§3). Most groups are `hidden`; their membership, roles, and relationship edges are
not enumerable — but any *specific* fact about them can be attested by a ZK proof.
This doc specifies that one primitive: a family of proofs over the group graph that
is the substrate for cooperativeness scoring, connection-weight / conflict-of-interest
exclusion, provisioning, mail-as-group, and every other group-aware surface.

Four statements, in increasing difficulty:

1. **Membership** — "X is a member of group G."
2. **Role** — "X holds role Y in group G."
3. **Relationship** — "edge (G₁, R, G₂) exists" for R ∈ {member-of, subgroup-of, sponsored-by, federated-with}.
4. **Distance / connection weight** — "X is ≥ K hops from G" (conflict-of-interest exclusion), and its weighted form "weight(X, G) ≤ T."

## 2. Feasibility verdict (the honest answer)

**The core is feasible today with off-the-shelf tooling; only the *exact* distance
form is research-grade.** The single real risk is prover performance on mobile, not
cryptographic possibility.

| Statement | Construction | Feasibility |
|---|---|---|
| Membership "X ∈ members(G)" | Merkle proof over the group's member-commitment tree (Semaphore / zk-kit lineage) | **Off-the-shelf** |
| Role "X holds Y in G" | membership proof with the role inside the leaf commitment | **Off-the-shelf** |
| Relationship "edge (G₁,R,G₂)" | membership proof over an edge-commitment tree (each edge a committed leaf) | **Off-the-shelf** |
| Non-membership "X ∉ members(G)" | frontier tree, or sorted-tree range proof (Micali–Rabin–Kilian ZK-Sets; eprint 2019/1255, 2024/1259) | **Off-the-shelf** |
| Bounded distance "dist(X,G) ≥ K", small K | conjunction of non-membership over G's ≤(K−1)-hop neighborhood | **Feasible, medium effort** |
| Exact distance "dist(X,G) = K", arbitrary K | ZKGraph-style SSSP verification (relaxation + lookup constraints over the edge table) — O(m) circuit | **Research-grade** |

Everything here is *simpler than the shielded transfer* the treasury already commits
to (private-treasury §2): membership/non-membership proofs are strictly lighter than
conservation-in-circuit. If the shielded treasury is feasible, this is feasible.

## 3. The four proofs

### 3.1 Membership & role (off-the-shelf)

Each group maintains a **member commitment tree** — a Merkle tree whose leaves are
`commit(sub, role)` (the Keycloak `sub` and the seat role(s), blinded by a per-seat
nonce). The group's root is public (or in the on-chain registry); membership is a
standard Merkle-authentication-path proof that a leaf commitment is in the tree, in
ZK so neither the `sub` nor the role is revealed beyond what the statement asserts.

- "X is a member" → prove a leaf whose `sub = X` is in the tree.
- "X holds role Y" → same, with `role = Y` exposed as a public input, `sub` hidden.
- This is exactly the zk-badge already referenced for hidden groups
  (group-scoping §3), and the same primitive `ConfidentialVoting.sol` (Semaphore)
  uses for private tallying.

### 3.2 Relationship edges (off-the-shelf)

Relationships are edges, not columns. Each declared edge `(G₁, R, G₂, terms)` is a
commitment; proving "this edge exists" is a membership proof over the group's
**edge-commitment tree** (or a global edge registry tree). A proof can reveal R and
one endpoint while hiding the other — e.g. "some group is `sponsored-by` G" without
naming which, or "G₁ is `subgroup-of` some group" without naming the parent. This is
what makes the four relationship types (account-and-key-model) provable-but-private.

### 3.3 Non-membership (off-the-shelf)

"X ∉ members(G)" without revealing the tree: prove X sorts strictly between two
adjacent leaves (sorted-tree range proof), or prove the leaf at X's index is empty in
a sparse/frontier tree. These are known, efficient constructions (ZK-Sets lineage).

### 3.4 Distance / connection weight (the hard one)

The conflict-of-interest exclusion needs "X is far enough from G." Two readings:

- **Exact** — "dist(X,G) = K": this is the research-grade form. The state of the art
  (ZKGraph, arxiv 2507.00427; ALITHEIA, CCS'14) proves shortest-path correctness by
  *not* running BFS in the circuit: the prover computes distances off-circuit, and the
  circuit verifies the distance vector via Bellman-Ford relaxation + predecessor/edge
  lookups. Correct, but the circuit is O(edges), so it does not scale to a large
  relationship graph per proof.
- **Bounded** — "dist(X,G) ≥ K" for small K: this is the form we actually need, and it
  is tractable. "Not within K−1 hops" = X ∉ members(G) **and** X ∉ any group related
  to G within depth K−1 (member-of, subgroup-of, sponsored-by edges). That is a
  **conjunction of non-membership proofs over G's bounded neighborhood** — cheap,
  and it reuses §3.3.

**Decision (recommended):** ship **bounded distance** with K ∈ {1,2,3}. Conflict-of-
interest in a small cooperative community is a *local* property; a 2–3 hop bound
captures "member of G, member of a sibling, sponsored-by G, subgroup-of G" — the
cases that actually bias an investigator. Defer exact distance indefinitely; the
fallback (include-but-reveal-weights) covers anything the bounded proof can't.

Connection *weight* (the continuous form) is the same bounded neighborhood, summed
with decay per hop, then range-proved (`weight ≤ T`) — a small arithmetic circuit on
top of the same non-membership witnesses.

## 4. Two tiers of "hidden" — and which is the default

"Hidden" has two strengths, and conflating them breaks the roles/grants model:

- **Hidden-from-public (tier 1 — the default "hidden-norm").** Membership is stored
  centrally but RLS-scoped: a member reads their own seats; third parties cannot
  enumerate; no public projection (world-doc, library) exposes the group. Roles and
  grants mint exactly as today — `getRolesAndGrants(sub)` reads the user's *own* seats
  into the JWT `roles`/`grants` claims. Authorization is unchanged.
- **Hidden-from-platform (tier 2 — opt-in, deferred).** The platform holds only
  commitment roots, no plaintext seats. A user's roles are no longer read from the DB —
  the user presents membership proofs at sign-in and the backend verifies them into the
  JWT. Two real costs: (a) JWT mint becomes proof-verification, and (b) member
  **fan-out** (notification digests, group mail, ring groups, provisioning) can no
  longer enumerate members — resolved by derived delivery keys (§8), or pull-based
  delivery as the v0 fallback. A per-group opt-in for the highest-privacy cases,
  not the norm.

The relationship-registry commitments of §3.2 apply to tier 2; tier 1 keeps the
plaintext `group_members` projection, hidden only from third parties via RLS.

## 5. Prover / verifier placement & tooling

Same split as the treasury (private-treasury §6): **prover runs client-side** (the
sovereignty pattern — members prove their own membership/distance; the backend never
holds witnesses), **verifier runs on-chain** (a Groth16/PLONK verifier), coop-api is
the relay/pre-validation layer. Tooling is the treasury's own: Poseidon over BN254,
Groth16 (or PLONK), Semaphore/zk-kit for membership, and ZKGraph's expansion-centric
circuits only if exact distance is ever needed.

## 6. Phasing

- **v0 — membership + role + non-membership** (the off-the-shelf tier). Unblocks
  hidden-group "prove I belong, role Y", and the first cooperativeness inputs.
- **v1 — relationship edges** (member-of/subgroup-of/sponsored-by proofs).
- **v2 — bounded distance** (K ≤ 3) for conflict-of-interest exclusion, with the
  include-but-reveal fallback as the correct degenerate path.
- **v3 (only if needed)** — exact distance / arbitrary graph queries (ZKGraph).

## 7. Open questions

1. **Mobile proving gate** (shared with the treasury, private-treasury §9): membership
   proofs are light, but "prove at launch scale on phones" is still the binding
   constraint — measure v0 circuit size + latency before anything else.
2. **Chain/curve choice** — BN254+Groth16 vs a PLONKish stack; the treasury's choice
   should be reused, not re-decided here.
3. **Root publishing** — where member-tree/edge-tree roots live (on-chain registry vs
   a commitment column in the projection) for hidden groups.
4. **Bounded-distance K** — default 2 or 3; a per-vertical knob or platform constant.

## 8. Fan-out without enumeration — derived delivery keys

The tier-2 fan-out cost ("the platform can't enumerate members") has a clean
resolution: **fan-out needs endpoints, not identities.** Separate the two:

- **Membership tree** — commitments of `(sub, role)`. Hides *who* is a member; proofs
  attest membership facts (§3).
- **Delivery tree** — per-group derived public keys (stealth-address / subaddress
  style): `D_i = H(sub_i, group_id) · G`. The platform enumerates these (they are just
  keys) and fans out to each; each member scans with their private scanning key to find
  and decrypt their own. The keys are unlinkable to identities, so enumerating them
  reveals nothing about *who* the members are.

This is the treasury's own note-delivery plan (private-treasury §9.3, "stealth
addresses, encrypted note delivery") applied to fan-out, plus the delivery-key concept
from delegation-and-session-keys.md §6. Matrix already works this way: encrypted rooms
fan out to device keys, never identities.

Per channel:

- **Notifications/digests** — encrypt to the member's delivery key; liveness via a
  public per-group "new events" counter (a count, not identities) that members poll,
  or a push signal to the derived key. v0 = poll-on-counter; v1 = push-to-key.
- **Mail** — a derived, opaque mailbox `{token}@{group}.irl.coop`, never
  `{name}@{group}.irl.coop` (which would link identity to address).
- **Matrix** — already solved.
- **Telephony ring group** — the genuinely hard case: a phone number/extension is
  reachable *and* linkable by nature. Ring groups route to derived SIP identifiers the
  member's own device resolves; if that proves impractical, telephony is the one
  channel that stays tier-1.
