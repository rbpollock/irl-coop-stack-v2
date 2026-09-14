# Coop launch & roadmap handoff — PARKED WISH LIST

Status: **wish list / parked · 2026-09-13 · Robbie.**
**Do not design or build any of this until Robbie raises it.** Recorded because a wish list item
that lives only in a conversation is a wish list item lost — same convention as the PARKED
federation/DNS session in `AGENTS.md`.

## 1. The two items, as stated

1. **Roadmap development maps to a Plane project for irl.coop, owned by an irl.coop group** —
   the coop tracking its own build in its own tool, under its own group Safe.
2. **Stand up the coop itself and hand off infrastructure control to it.**

They are one item in two halves: (1) is the work becoming visible inside the structure, (2) is the
structure becoming real.

## 2. Why it matters more than it looks

**It is the only thing that answers the adversary the whole archive names and then works around.**

`adversary-models-and-sector-fit.md` §1.1 lists **I7 — the platform steward, including me** — as one
of the eight *universal* internal tensions. Every cryptographic mitigation in
`federation-encryption-and-access.md` **relocates** trust: it shrinks the set of parties who must be
trusted and makes each one visible. **None of them remove the human currently holding the keys.**
Item 2 is the only item on any list in this repo that actually answers I7. Everything else is a
rearrangement.

**It also makes "groups" true for the first time.** Every group shape, seat model, treasury guard and
governance design in `docs/design/` has been exercised on paper. The coop's own work — tracked in its
own Plane project, owned by its own group Safe, funded by its own treasury — is the first group that
is not a demo. The first real tenant is the coop itself.

## 3. What already exists (so unparking is cheap)

| Piece | State |
|---|---|
| The coop-as-group | **Designed** — `irl-coop-group.md`: group Safe, salt `irlcoop-group-v1`, deterministic address; initial owners Robbie, threshold **1-of-1 (dev) → promoted to 2-of-3 (Robbie + 2 founding members)**. Not created |
| A group-owned Plane project | **Mechanism exists** — Plane is an OIDC client with `data: {scoped_by: sub, views: [...]}` scoping, so per-group views are the designed path |
| The roadmap itself | **Exists as data** — `claims.data.json` (35 claims with status) + the ordered plans in `landing-page-claims-audit.md` §4 and `interactive-arguments-and-the-cta.md` §2b. The Plane project is where that becomes *work* rather than a list |

## 4. The sharp dependency — record this, it is the whole point

**Handing over the Safe is not handing over control while the vault is custodial.**

`apps/coop-api/src/vault.ts:42` encrypts with a **platform-held** key (tier 2 in
`federation-encryption-and-access.md` §2), and the platform's `master.key` custody is currently one
person. So a Safe transfer at threshold **without** the non-custodial vault hands over the deed while
the steward quietly keeps a copy of the keys.

**Therefore the vault fix — universal build item #1 in `adversary-models-and-sector-fit.md` §8 — is a
*precondition* for a meaningful handoff, not an adjacent task.** This is the concrete link between the
cryptography work and the organisational milestone, and it is the reason the two should be planned
together rather than sequenced independently.

## 5. The honest limit to say out loud

**A handoff without a second person is not a reduction of the bus factor — it is a relocation of it.**
A cooperative whose control sits with one active member is a cooperative with a Safe and one member.
This is the same founder/bus-factor tension as §1.1 in the adversary doc, and the same mitigation
applies at coop scale as at node scale: **a named second person and a documented handover procedure**
(`cost-model.md`'s federation failure modes: a stale coverage proof is the early warning for exactly
this).

So item 2 is not "create a Safe and change the owners." It is "have two people who can, and a written
procedure for when one of them cannot."

## 6. Decision points for when this is unpicked (questions, not a spec)

1. **Who are the two founding members?** Names, not roles — the threshold is meaningless without them.
2. **What exactly transfers?** An inventory question, and probably larger than expected: the group
   Safe and its owners; `master.key` and the derived-secret chain; the domain registrar and DNS; the
   DIDs/carrier accounts; payment and any treasury; the node's physical and operator access; backups
   and their destinations. **Some of these may deliberately NOT transfer** — a break-glass path is
   worth naming explicitly rather than discovering.
3. **What threshold, and when does it change?** 2-of-3 founding → 3-of-5 after N members?
4. **Group-owned project, or instance-owned Plane?** The scoping design supports per-group views;
   instance ownership is a different and larger question.
5. **What does the steward keep, and is that written down?** An unwritten reservation is
   indistinguishable from a hidden one.

## 7. Unparking safely — get the bug flood before the audience

**Recorded 2026-09-13, because the real reason this is parked is not the work — it is the fear that
starting the coop will reveal a flood of bugs.** That prediction is probably *correct*, and the useful
response is not reassurance. Three things are true at once:

### 7.1 The bugs are already there. The coop changes the detection surface, not the defect count

Today there is one user (Robbie) and a forgiving operator, so failures are **silent**. Evidence from a
single afternoon of adversarial looking on 2026-09-13 — **six findings, every one of them found by
looking, not by a user**:

| Found | How long it had been true |
|---|---|
| The status report counted every non-running container as "down", including completed one-shot jobs | unknown — and it made any *real* outage invisible in the noise |
| Four `*-minio-init` jobs `Exited (1)`, undetected | **6 days** |
| The footer's "All systems operational" is hardcoded, and only *accidentally* true | since it was written |
| The vault is platform-custodial (tier 2) vs. the k-of-n design it was supposed to implement | since the vault was built |
| `needs-offers-mockup.tsx` is a working 780-line tool | since it was written |
| Four FAQ answers promise unbuilt capability in the present tense | since they were written |

**The current failure mode is worse than a flood of bugs: it is silence.** The phantom "21 down"
figure is the proof — the instrument was so noisy that a genuine outage would have been
indistinguishable from a migration finishing. Members are not a new source of bugs; they are the
*first real detector*.

### 7.2 The cost curve runs the opposite way from the fear

Bugs found with **three tolerant founding members** are cheap: no reputation, no payments, no
support load, no one's data at risk, and every member expects breakage. The identical bugs found with
**fifty paying members** are expensive. **Delaying does not avoid the bugs — it moves them to a larger
audience at a higher price with less goodwill.** The coop step is the *cheapest possible* bug-finding
instrument, as long as it is run at the smallest possible scale with people who expect it.

### 7.3 The genuinely scary class looks structurally sound (checked, not assumed)

The class worth actually fearing is not "a button is broken" — it is **permission and scoping
leaks**. Checked 2026-09-13 in `apps/coop-api/src/groups.ts`:

- `POST /api/v1/groups/:id/members` → gated on `isOwner(...)` → 403 `not a group owner`
- `GET  /api/v1/groups/:id/members` → gated on `isMember(...)` → 403 `not a group member`
- `POST /api/v1/groups/:id/resources` → gated on `isMember(...)`
- **and every one runs inside `withIdentity(claims.sub, …)`**, so the row-level-security context is
  the *caller's* identity on each request — the correct shape.

**This is not proof there are no leaks** — it is three routes read, not the whole surface, and not a
runtime cross-group isolation test. But it is the right evidence, of the right class, and it is
positive. The scariest failure mode is not the one the code appears to invite.

### 7.4 Do these in order, and the flood arrives on your schedule

1. **Split item 1 from item 2** (§1). They are separable and should not be unparked together:
   - **Item 1 — the roadmap in a group-owned Plane project — can run at `1-of-1`.** That is *already
     the designed dev stage* (`irlcoop-group.md`: 1-of-1 → promoted to 2-of-3). Zero audience, zero
     handoff, zero exposure — and it generates the **daily-use** bug list, which is the list the fear
     is actually about.
   - **Item 2 — the handoff — waits** until that list is short, the vault fix has landed (§4), and
     there is a named second person (§5).
2. **Build the detector before the audience** — spec'd in **`coop-readiness-probe.md`**, which
   separates the read-only infrastructure pass from the synthetic founding-group pass so the first
   measurement needs no writes and no humans. The ingredients exist: the stack report now classifies
   correctly (a real signal instead of noise), the browser journeys
   (`infra/scripts/journeys` + the runner fleet) exercise flows end to end, and `claims.data.json`
   already lists what is claimed versus what works — **the registry is the probe's test plan**.
3. **Run the probe privately, get the list, fix the top of it.** Then the coop step reveals a
   **known** set of bugs instead of an unknown one. The fear is mostly about *unknown volume* — a list
   converts it into work with an order.
4. **Start with only what is already stable.** The inventory in §6.2 is for the *handoff*; the *first
   members* only need the parts that are in the healthy set today (identity, groups/seats, Plane,
   NocoDB). Mail, documents, treasury and federation are not required for a founding group of three.

**A useful test to set in advance:** if starting the coop with three tolerant members produces a bug
list you can hold in one page, the coop was ready and the fear was the only thing in the way. If it
produces one you cannot, that is not a failure — it is the instrument doing its job, and it is
strictly better information than you have today.

## 8. Do not

- Do not create the group Safe, the Plane project, or transfer anything on the strength of this note.
- Do not design the handoff procedure yet — it depends on §6, and those are Robbie's calls.
- Do not treat this as a roadmap commitment in a video or on the landing page until it is scheduled.
