# Group-Shape Scenario Notes

Status: notes · Aug 2026 · Companion to the group-shapes design
(event-bus-and-group-shapes.md) and the scenario-1 journey
(neighborhood-growing-team). These are the other scenarios Robbie is collecting —
each is a candidate group *shape*, and the point of the notes is to surface the
small set of shared primitives they all reduce to.

## The scenarios at a glance

| # | Scenario | Core need | Dominant primitive |
|---|---|---|---|
| 1 | Local theater | closed group + external actors | guests + production calendar + media capture |
| 2 | Tool library | share tools, minimize storage/cost | inventory + reservation + federation |
| 3 | Childcare coop | rotating watch shifts for parent time-off | rotation + fairness credits + external space |
| 4 | Hobby-sharing | teach/trade skills, materials pot | skill time-bank + materials pot + collective sell |
| 5 | Food skill-sharing | teach food skills, stay fair | teaching turns + reciprocity |
| 6 | Farmer exchange | manure ↔ veggies, seasonal labor | resource match + labor pool |
| 7 | Solutions library | anonymized "how we met the need" stories | story form + milestone prompt |
| 8 | Hand-me-down matching | share kids' clothes, fair contribution | size match + labor fairness |
| 9 | Gathering / celebration | sector symposiums, coffee hour | events + social discovery |

---

## 1. Local theater — closed group with external actors

**Premise.** A theater company (closed membership) that needs external actors,
crew, and audience. Coordination around auditions, scheduling, a production
calendar, and picture capture during process for advertising and fundraising.

**Shape.**
- roles: `director`, `cast` (external guests), `crew`, `admin`
- apps: Plane (production calendar), NocoDB (audition signups + casting), docs
  (scripts/blocking), Matrix (per-production rooms), MinIO (photo/video capture)
- governance: director-led, external actors are time-bound guests
- proofs: fundraising progress, audience reach

**Tool mapping.** Plane = the production calendar and milestones (auditions →
rehearsal → tech → opening). NocoDB = audition signups, casting grid. MinIO =
process photos/videos for ads + fundraising. Funding pool = the fundraising
goal.

**Gaps surfaced.**
- **External/guest identity** — actors are non-members who still need seats
  (audition, role, schedule) and file access for scripts. The `guest`/`observer`
  role exists in the design but isn't wired to external sign-in.
- **Media capture workflow** — a bucket + gallery for "pictures during process",
  tied to the production timeline (the MinIO store exists; the *workflow* doesn't).
- **Public-facing fundraising** — a funding pool anyone can pay into (external
  contributors, not members) — the treasury is designed member-only today.

## 2. Tool library — shared tools, minimized storage & spend

**Premise.** Neighbors who don't all want to buy a lawnmower, trailer,
wheelbarrow, snow-removal gear, leaf blower, chainsaws, hand tools, woodworking
tools, drills, drivers, nail gun, air compressor — small machines needing gas,
oil, routine maintenance, and storage. Some people own some things; some have
space to store them. How to maximize usage while minimizing storage and
expenditure — possibly as a *regional federation* of tool libraries.

**Shape.**
- roles: `member`, `steward` (maintains a tool), `host` (stores it), `admin`
- apps: NocoDB (inventory + checkout log), Plane (maintenance schedule),
  Matrix (coordination), funding pool (gas/oil/blades/replacement)
- governance: checkout rules, damage/replacement policy, usage quotas
- proofs: fair-usage (borrow vs lend), coverage of shared costs

**Gaps surfaced.**
- **Resource inventory + reservation** — a catalog of tools with a checkout /
  reservation / return state machine. Not built; the closest is the files/docs
  bucket model, which doesn't reserve.
- **Storage as a contribution** — "hosting a tool" (space) is a contribution on
  par with buying one — needs the labor/space credit.
- **Maintenance as a child group** — the maintenance effort is a separately tracked
  project with its own fund allocation (Safe wallet) + sub-accounts, as a **child group**
  of the tool-sharing parent (a rights-set relationship, not a flag); it decides its own
  maintenance spending from its budget.
- **Regional federation** — multiple tool libraries sharing a catalog. This is
  the **parked federation question** (do not design yet) — the notes just flag
  that tool-sharing is the scenario that most obviously *needs* it.

## 3. Childcare coop — rotating watch shifts

**Premise.** ~20 stay-at-home parents, ~14 kids. They need a couple hours a week
to themselves. Takes ~3 parents to watch the kids while the rest go out. Everyone
takes a shift and everyone gets their own time, once a week. Space may be
external (a church) or someone's home.

**Shape.**
- roles: `parent`, `host` (provides the space), `coordinator`
- apps: Plane (rotation calendar), NocoDB (shift signups + kid roster),
  Matrix (coordination), the credit ledger (shifts)
- governance: shift fairness (you watch → you get time), coverage quorum
  (3-on-duty minimum)
- proofs: reciprocity (watched-shifts ≈ earned-time)

**Gaps surfaced.**
- **Rotation scheduling with a coverage floor** — "3 parents stay" is a hard
  constraint on the schedule (not just signup). Plane has cycles/issues but not
  a coverage-guaranteed rotation.
- **External space booking** — a church or a member's home as a bookable
  resource that isn't owned by the group.
- **Shift fairness** — the time-bank (Tier-2 credit) applied to *time-off
  entitlement*, not money.

## 4. Hobby-sharing — craft skills + materials pot

**Premise.** People who are really good at a hobby — knitting, crochet, macrame,
lace-work — want to share skills and trade amongst themselves, with a plan for a
skill-sharing community. They might need a *pot of money* so everyone can access
materials. Each takes turns teaching. They may want to collectively sell what
they make to fund more sharing.

**Shape.**
- roles: `teacher` (rotating), `learner`, `admin`
- apps: docs (patterns/guides), Matrix (coordination), NocoDB (materials
  inventory + sales), funding pool (materials pot)
- governance: take-turns teaching (everyone teaches, everyone learns)
- proofs: teaching contribution (taught N, learned N)

**Gaps surfaced.**
- **Skill time-bank** — "take turns teaching" is the Tier-2 credit applied to
  *teaching*, distinct from materials.
- **Materials pot** — a group treasury sub-scope everyone can draw materials
  from (the funding pool, sized to the group).
- **Collective selling** — a byproduct of the group creating a Webstudio site
  with an e-commerce component (to be built). Revenue lands in member wallets,
  with compliance-reproducible records (taxes, business filings, reporting).
  The group then manages its treasury: individualized payouts (percentage,
  one-time, or flat-rate), interest-earning savings, allocation to another
  project or fund, or a donation to irl.coop for infrastructure — visible on
  the dashboard or emailed. See "Treasury payout engine" below.

## 5. Food skill-sharing — stay fair over time

**Premise.** People teach each other knife skills, tanning, tallow-making, fish
& game processing; people bring materials for cooking lessons. The question is
*how it stays fair over time*.

**Shape.**
- roles: `teacher`, `learner`, `host`, `admin`
- apps: docs (recipes/guides), Matrix, NocoDB (session signups + material
  contributions), funding pool (materials)
- governance: contribution parity (bring materials ≈ take materials)
- proofs: reciprocity over time

**Gaps surfaced.**
- **Fairness over time is the core metric** — this scenario names the exact
  anti-freeloader signal the regenerative score's *reciprocity* axis is for.
  Materials-in vs materials-out needs a lightweight ledger.

## 6. Farmer exchange — manure ↔ veggies, seasonal labor

**Premise.** Animal-processing farms give manure to veggie farms; get hay and
scraps in return. Compost experts, shared labor where different seasons need
different inputs. More hands make work faster — the potato farmer needs 20 people
to harvest; the same people help move cattle fences. Everyone gets meat and
veggies for their work hours.

**Shape.**
- roles: `farmer`, `laborer`, `composter`, `admin`
- apps: NocoDB (offers/needs board), Matrix (coordination), Plane (seasonal
  workdays), the credit ledger (work hours)
- governance: barter parity (manure ↔ hay ↔ scraps), seasonal reciprocity
- proofs: work-hours → produce received

**Gaps surfaced.**
- **Resource match (offer ↔ need)** — manure, hay, scraps, labor are all
  *exchangeable resources*; the production matcher (`match.*` events) is the
  designed-but-unbuilt mechanism.
- **Labor pool** — "20 people harvest" is a one-off labor event with a
  produce payout. This is the Tier-2 credit in its rawest form: work hours →
  meat/veggies. The ledger is the missing piece, not the concept.
- **Seasonal scheduling** — inputs are seasonal; the calendar/rotation primitive.

## 7. Solutions library — anonymized "how we met the need"

**Premise.** Anonymized stories of how people had their needs met through
collaboration on the site — a form, possibly prompted after a project milestone
or completion.

**Shape.**
- roles: `author` (anonymized), `admin` (moderates)
- apps: a form (NocoDB form or native), docs (the library), the event bus
  (milestone → prompt)
- governance: anonymization policy (owned by the source)
- proofs: the story itself (a positive social proof)

**Gaps surfaced.**
- **Story-capture form** — a structured form with a first-class
  *anonymization* toggle (the "anonymization is owned by the source" principle
  from event-bus-and-group-shapes.md §2.6 — the form omits or marks the author,
  the bus never strips identity).
- **Milestone hook** — the bus needs a `project.completed` / `milestone.reached`
  event that prompts the form. This is the notification action (deep link into
  the form) — designed, not built.

## 8. Hand-me-down matching — share kids' clothes

**Premise.** Parents with kids a year or two apart share clothes the older kids
have outgrown. Is there a collective place to sort and gather? Is it a
free-for-all event? How to make sure people contribute as much as they take —
and let those without much to share contribute *labor* (manning tables,
organizing).

**Shape.**
- roles: `giver`, `taker`, `organizer`, `admin`
- apps: NocoDB (size inventory + matching), Matrix, an event/calendar (the
  free-for-all), the credit ledger (contribution)
- governance: contribution parity — items *or* labor
- proofs: contribution ≈ taking (with labor as an equal contribution)

**Gaps surfaced.**
- **Size/age matching** — "kids 1–2 years apart" is a match predicate over
  inventory (size, season, gender-neutral). The offer/need matcher again.
- **Collective gathering** — a physical sort-and-gather *event* (space + time),
  distinct from the ongoing matching.
- **Labor as contribution** — the crucial fairness point: labor counts. This
  collapses "contribute as much as you take" into the labor-credit ledger.

## 9. Gathering / celebration — how we celebrate what we're making

**Premise.** An irl.coop gathering by sector, a group-wide symposium, coffee
hour + social time so people can find out what their needs are.

**Shape.**
- roles: `host`, `attendee`, `admin`
- apps: Matrix (rooms), Element (video), Plane/NocoDB (RSVP), the calendar
- governance: open invitation, sector grouping
- proofs: attendance/reach

**Gaps surfaced.**
- **Events + RSVP** — a calendar/event primitive with RSVP, sector tags, and
  deep links into Matrix rooms.
- **Social discovery** — "find out what your needs are" is the discovery layer:
  people surfacing their needs and finding others who can meet them. This loops
  back to the matcher (needs board) and is the *onboarding* into every other
  scenario.

---

## The cross-cutting primitives

All ten scenarios (including the neighborhood growing team) reduce to a small
set of shared primitives. This is the payoff: the "group shapes" catalog is
really a *composition* of these, not ten bespoke builds.

| Primitive | Scenarios that need it | Status |
|---|---|---|
| **Labor/contribution credit** (Tier-2 time-bank) | childcare, hobby, food skills, farmers, hand-me-down, growing team | 📐 designed (Tier-2, hash-chained) |
| **Resource match** (offer ↔ need) | farmers, tool library, hand-me-down, hobby (trading) | 📐 designed (bus `match.*`) |
| **Inventory + reservation** (checkout/booking) | tool library, childcare space, hobby materials | 🆕 not designed |
| **Funding pool** (pot of money) | hobby materials, tool maintenance, theater fundraising | 📐 designed — the group's Safe *is* the flat pool; sub-projects become **child groups** (own Safe + budget) via a rights-set "child" relationship |
| **Fairness / reciprocity** (anti-freeloader) | food skills, hand-me-down, tool library, childcare | 📐 designed (regenerative score) |
| **Calendar / rotation / coverage** | theater, childcare, farmers | 🆕 partial (Plane has none with coverage floors) |
| **External guests** (non-member seats) | theater actors, audience | 🆕 partial (`observer` role, not wired) |
| **Anonymized story capture** | solutions library | 🆕 partial (form + bus hook) |
| **Events / gathering / RSVP** | gathering, hand-me-down events | 🆕 not designed |
| **Collective selling** (Webstudio e-commerce → wallets) | hobby, any group with a site | 🆕 not designed — Webstudio e-commerce component |
| **Treasury payout engine** (percentage / one-time / flat-rate → savings / allocate / donate) | hobby, theater, any revenue group | 🆕 not designed — dashboard + email notify |
| **Federation** (regional sharing) | tool library | ⛔ **parked** — surfaced, do not design yet |

## What this means

1. **Build the primitives, not ten apps.** The labor-credit ledger and the
   matcher are the two highest-leverage primitives — they appear in almost every
   scenario. The funding pool is third.
2. **"Composition, not inheritance" holds.** Each scenario is a *shape* that
   selects a subset of primitives + a role vocabulary; none is a new category.
3. **External participation is a distinct axis.** Theaters (actors/audience),
   childcare (a church), farmers (non-member laborers) all cross the member
   boundary — the `guest`/`observer` role + external identity is a real gap the
   current member-only model doesn't cover.
4. **Fairness is the load-bearing metric everywhere.** Nearly every scenario
   ends on "how does it stay fair" — reciprocity (contribute ≈ take, with labor
   as an equal contribution) is the shared answer, and the proof that makes a
   coop self-sustaining instead of a place free-riders drain.
5. **Collective selling is a site feature, not a marketplace.** A group's
   Webstudio site gains an e-commerce component; revenue goes to member wallets,
   and the *reproducible records* (taxes, filings, reporting) are a first-class
   output, not an afterthought. Treasury management — individualized payouts
   (percentage / one-time / flat-rate), interest-earning savings, reallocation
   to another project/fund, or donation to irl.coop for infrastructure — is a
   distinct "treasury payout engine" primitive, surfaced on the dashboard with
   email notification.
