# Published Items as Groups — publishing &amp; DRM

Status: design · Sep 2026 · Builds on irl-coop-group.md (the group primitive,
seats, roles), private-treasury-guards-ledgers.md (treasury, viewing keys,
distribution), event-bus-and-group-shapes.md (shapes, provisioning), and
group-model-technical-overview.html (§2 the group, §11 the treasury, §12 ZK,
A.5 the zk certificate).

## 0. The shape in one paragraph

Every published item — a comic book, a screenplay, a play, a book, a poem — **is
a group**. The work itself is one encrypted file in that group's MinIO bucket.
Access is *minted, never copied*: a person rents access for a limited time and
receives a **session key**; an owner views at any time, **sells** the work
(swapping their membership for the buyer's), or **lends** it (minting a **viewing
key** scoped to a timeframe and a lend count). The group's membership tiers —
**owner**, **contributor**, **funder** — divide the proceeds (purchases, lending,
licensing) through the entitlement table. Supply is a group setting: a work can
be lent and sold infinitely, or be *artificially exclusive* (a cap on copies).
Creation runs the other way: a work starts as a Plane project, and a
**publication ceremony** turns the project into a group.

## 1. Principles

1. **The item is the group.** There is no separate "asset" entity — the
   published work IS a group Safe, with seats, roles, treasury, and governance.
   DRM becomes a group-membership problem, not a copy-protection problem.
2. **Access is minted, never copied.** A file is never "downloaded and kept";
   the recipient gets a scoped key (session or viewing) bound to a timeframe and
   a lend count. Keys come from the credential machinery (overview §12, A.5),
   not a DRM vendor.
3. **Ownership is a seat.** To own the work is to hold the owner seat (and the
   Safe owner set). To sell is to swap the seller's `sub` for the buyer's —
   "ownership implies membership ONLY."
4. **Proceeds flow through the group's treasury.** Purchases, rents, lends, and
   licensing are inflows to the funding pool; contributors and funders are paid
   per the entitlement table, their percentages fixed at inception.
5. **Supply is declared, not assumed.** A work may be a public good (infinite
   lends/sales) or artificially scarce (a cap). This is the shape's `config`
   axis, enforced by a guard.
6. **Publication is a ceremony, not a button.** A Plane project becomes a group
   through a deliberate transition, optionally arbitrated by an irl.coop
   representative.

## 2. The item and its keys

The work is one encrypted file in the group's MinIO bucket (`resource_scopes`:
app = minio, resource_key = item).

- **Rent.** A person rents access for a limited time; the group mints a **session
  key** scoped to that window. If the group settings allow it, this is
  auto-provisioned (Temporal) with no owner involved per-rent.
- **Lend.** An owner lends the work; the group mints a **viewing key** scoped to
  a timeframe and a **lend count** (one, or many). The group may set a **minimum
  and maximum lending cost** — a config value plus a guard.
- **Re-lend.** A lent work may be re-lent before the window expires: the viewing
  key is *transferred* (re-scoped), never duplicated, so there is at most one
  holder per key — nullifier semantics (overview §12).
- **Sell.** An owner sells the work; the group swaps the seller's `sub` for the
  buyer's in the seat (`group_members`) and the Safe owner set. Ownership is a
  transfer, not a copy.

| publishing action | mechanism |
|---|---|
| rent → session key | credential pathway (A.5): mint a scoped, time-bound key from `H(sub, item, window)` |
| lend → viewing key | credential pathway + a lend-count bound (nullifier: one holder per key) |
| re-lend | transfer the viewing key (re-scope holder + timeframe), never duplicate |
| sell | swap the seat's `sub` + the Safe owner set |

## 3. Membership tiers

Each tier is a seat with a role (owner / contributor / funder) — the same
roles/grants machinery as any group (overview §4), plus the entitlement table for
distribution (overview §11).

- **Owner** — views at any time; may sell, lend, and (with the group) set terms.
- **Contributor** — entitled to a **perpetual or capped** distribution of
  proceeds from purchases, lending, and licensing. Percentages are fixed at group
  inception, in the entitlement table. A contributor may also be an owner.
- **Funder** — sponsored the creation of the publication. May also be an owner,
  but is not necessarily one. Funders sit in the entitlement table (or a separate
  return schedule) per the group's inception terms.

## 4. Supply control

A digitally published asset has no natural scarcity; the design choice is whether
to impose one.

- **Unbounded supply** (a public good). The work may be lent and sold infinitely;
  rents/lends are the revenue, and the file is freely re-lendable.
- **Artificial scarcity** (an exclusive item). The group sets caps — e.g. at most
  N owners, N active lends, or N lifetime sales. The cap is a guard (config axis
  + an app-layer limit): the group refuses to mint a key beyond the cap.

Supply is a shape setting, not a hardcode — the same work could be published as a
scarce "first edition" *and* a free "reading edition."

## 5. Creation: project → group

1. The work starts as a **Plane project**: contributors edit documents, chat in
   the project's Matrix rooms, and contribute in real time — with **contribution
   tracking** (who did what, when — the Tier-2 hash-chained record).
2. On **publish**, all artifacts — anonymized or directly attributed — flow into
   the generated publication group: the final document (encrypted file in MinIO),
   the contributor percentages (entitlement table), the roles, the supply setting.
3. The **publication ceremony** is the project→group transition: a deliberate,
   governed step — a proposal/decision, optionally with an **irl.coop
   representative** to help with decision-making and arbitration. The exact
   ceremony is open (§7), but this is where contributor percentages are fixed and
   disputes are settled.

## 6. What exists vs. what is new

| piece | status |
|---|---|
| group = Safe, seats, roles | built (irl-coop-group.md) |
| encrypted file in group MinIO | built (MinIO + resource_scopes) |
| viewing / session keys | designed (treasury viewing keys §11; credential pathway A.5) |
| entitlement table / distribution | designed (§11) |
| lend-count / supply caps (guards) | designed (§11) |
| contribution tracking | designed (Tier-2 hash-chained ledger §11) |
| project → group ceremony | **NEW — open** |
| re-lend key transfer | **NEW — open** |

## 7. Open questions

1. **The ceremony.** What exactly turns a Plane project into a group — a proposal
   the contributors ratify, a role held by the irl.coop representative, a
   timelock, or all three? What happens to the project's history (anonymized vs.
   attributed)?
2. **Re-lend depth.** How deep can a re-lend chain go, and how is the chain
   tracked without linking readers (nullifier-per-lend vs. a chained viewing
   key)?
3. **DRM's honest limit.** A scoped key controls *access* and *attribution*, not
   *copying* — a determined reader can photograph the screen. The value is
   provenance + scarcity + fair distribution, not unbreakable copy-protection.
   Is that framing accepted?
4. **Capped distribution.** When a contributor's share is "capped," what triggers
   the cap (a total amount, a time, a milestone), and where does the remainder
   go (the pool, the owners, the coop)?

## 8. Why this matters

This one primitive covers a lot of ground: screenplays (lend to a director for a
read, re-lend to a producer), plays (license a run), books (sell a copy, rent a
library window), poetry (funder-sponsored chapbooks). Every case is the same
group — a different supply setting, a different set of tiers, a different
ceremony. The "published item as a group" is the DRM primitive, the same way
"the group" is the coordination primitive.
