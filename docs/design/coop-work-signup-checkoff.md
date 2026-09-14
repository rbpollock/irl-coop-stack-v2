# Cooperative work — signup, printable task sheet, check-off

Status: design sketch · Sep 2026 · **the consumer now exists** — the Tier-2 participation
ledger is built (`tier2-entry-model.md`), so the check-off event has somewhere real to land.
The member-facing write path is still missing; see "The prerequisite" below. Author: Robbie + Hermes.
Scope: a member-facing workflow for **group work** — members sign up for
concrete work items, the group can print a one-page task summary, and people
check off what they've done. Adjacent to — but distinct from — needs/offers
matching (that's surplus *exchange*; this is people *showing up for work*).

## The shape in one paragraph

A group (or the coop) has a set of work items for a window or event — a work
day, a harvest push, a season's maintenance list. Members open the list,
**select the thing** they'll take ("I'll do the fence row"), and their name
lands next to the item. Anyone can pull a **printable one-page summary** (task
| where | when | who | ☐) — for the clipboard at the site, no device needed.
As work happens, people (or the organizer) **check items off**; each check-off
records who and when and flows to the participation ledger, so "what I did"
accumulates into contribution history and zk-badges ("prove you showed up —
never how much").

## Jobs (the verbs)

1. **Signup** — a member claims an open item. Claim semantics to decide:
   first-come, assign-only (organizer), or hybrid with a per-person cap so one
   person can't swallow a work day.
2. **Select the thing** — the item must be *selectable*: visible, unclaimed,
   one tap. No forms; the list is the UI.
3. **Printable summaries** — a `?print=1` route (or PDF) rendering: the day's
   sheet grouped by task with blank ☐ next to each claim; and the inverse, a
   per-person sheet ("your list") for members who want their own copy. Print
   CSS, no chrome — this is a sheet of paper first.
4. **Check-off** — toggle an item done; store `done_by` + timestamp (not just
   a boolean). Optional organizer-confirm mode for jobs that need sign-off.
5. **Contribution trail** — every check-off emits one event
   (`contribution.logged`, `source_event_id` = the task row) onto the bus; the
   participation ledger (Tier-2 time-bank/quest credits) is its consumer.
   Check-off is how "showed up" becomes provable later.

## Where the tasks live (the Plane question)

Do **not** build a new task store — a work list is a *projection* over the
task source that owns the work (the world-doc principle: projection, never a
store of record). By work type:

| Work type | Lives in | Signup/check-off reads |
|---|---|---|
| Field, crop, harvest work | **LiteFarm** task (farm = group; the domain data is already there) | LiteFarm task API / its event stream |
| Logistics, events, builds, general coop work | **Plane** issue on the group's project (e.g. a "Work day" project) | Plane API/webhook |
| **Scheduled / time-boxed work** — teaching slots, market shifts, workshops, clinic hours | **cal.diy** booking (the MIT fork of Cal.com — the parked integration) | cal.diy booking API/webhook; a *completed* booking is the one source that carries a real **duration** |
| Anything cross-group / federation-wide | a needs/offers-style loop on the board (see litefarm §6 note) | the bus |

So "maybe integrate with Plane" — yes, when the work is Plane-shaped; a
work-day sheet is a *view over one Plane project filtered to the window*,
rendered in the dashboard. The signup UI ("I'll take this") writes the Plane
assignee/status through coop-api; the check-off writes status + emits the
contribution event. Same seam for LiteFarm tasks when the work is farm work.
Nothing new stores tasks; the app that already has the task is the source of
truth.

## Sketch of the seam (Plane leg)

- Read: group's work-day project issues (due within window, unarchived) via
  Plane API through the session-authed coop-api proxy.
- Claim: `POST` sets the issue assignee to the member (Plane status stays
  "To do" until claimed, or gets a custom "Claimed" state).
- **Transport (decided 2026-09-13): the durable lane, not a direct write.** The check-off emits
  `contribution.logged` into the `events` outbox (which already carries `source` +
  `source_event_id`); `tier2Sweep` fans out one child workflow per event and the activity calls
  `appendTier2Entry` — the only writer. A human-initiated log appends **and** emits in one
  transaction, so the record never depends on the messaging layer's availability.
  Full reasoning: `tier2-entry-model.md` §5.6.
- Check-off: move to Done + emit `contribution.logged {sub, source, task_id,
  done_at}` on the bus (source = plane|litefarm; idempotent on task_id).
- Print: dashboard route `/print/work-day?project=…&date=…` — server-rendered
  table, print CSS; the browser's Print→PDF is the "export" (no new export
  machinery).

## Four sources, one ledger — the rules that keep it honest

Robbie, 2026-09-13: hours could come from cal.diy, farm tasks, Plane tasks, or a dedicated
tracker. All four fit, and the doc's own principle decides the last one: **a work list is a
projection over the source that owns the work**, so a *new* time-tracker store is the option to
avoid unless nothing already owns that work. Four rules keep multiple sources from corrupting
the record:

**1. A source proposes; the ledger records; a counter-signature attests.** Three different
things, and the ledger only ever holds the third. **No source keeps its own authoritative
hours** — the moment one does, there are two truths and their disagreement is unfalsifiable.

**2. `idempotency_key = "<source>:<source_event_id>"`.** The schema's
`UNIQUE (group_id, idempotency_key)` then makes double-crediting from the same source
*structurally* impossible — including a webhook retry, which is the normal case rather than the
exception. When the same work legitimately arrives from two sources (a cal.diy booking **and**
the Plane issue for it), that is **one entry whose `refs` name both** — not two entries.

**3. Completion is not a duration.** A task moved to Done measures nothing. A task source may
satisfy a task-*count* obligation, or contribute a **declared** quantity that a human supplied —
it must never silently assert hours it never measured. That is precisely what `quantity` + `unit`
and the `attested` basis are for: an unmeasured figure is a *claim*, and a claim needs a
signature.

**4. A tracker is a surveillance surface INSIDE the group.** Raw intervals — start/stop,
sequence, location — are more legible than any total, and would make a member's work rhythm
readable by whoever reads entries. So **a tracker emits shift totals, never raw intervals**: the
aggregate becomes the record, the detail stays in the source and never enters the ledger. Same
shape as "commitments, not content".

**And every source is a scoped key** (`tier2-entry-model.md` §3.2) — grantable, expiring, and
volume-capped per entry class — so its entries are `machine-only` until a role holder or a vote
touches them. A Plane webhook therefore yields **provisional** credit. That is the correct
default, not a limitation.

## The prerequisite nobody has built yet

The seam sketched above writes through coop-api — and **there is no route that appends a Tier-2
entry at all.** `appendTier2Entry` is callable only from a script today. So the first piece is the
member-facing write path: log hours or claim/check off, with the counter-signature the three
authority classes need. Integrations are **producers** of that record; multiplying producers
before the record's shape has been exercised end to end multiplies the ways it can be wrong.

Order: **① the entry route + check-off (self-log → counter-sign) → ② ONE source as a proposer,
to prove the pattern → ③ the rest.** For ②, Plane is live and already per-group; LiteFarm is
deployed and its tasks are the farm leg (verified: `/apps/farm` frames `farm.irl.coop`, whose own
copy reads "fields, crops, tasks and sales"); cal.diy is newest and its task API leg has **never
been verified** — the fork is chosen, nothing is deployed, so it waits.

## Open decisions

- Task source by work type (table above) — confirm Plane-vs-LiteFarm split and
  whether a group picks per work-day.
- Claim semantics: first-come vs assign vs cap; waitlist on over-claimed days.
- Verification: self-check default vs organizer-confirm for specific jobs;
  whether check-off credit ever gates on a zk-badge (bond gates action, not
  actor — trust floor low).
- Recurrence: repeat a work-day template (the same sheet next month) — Plane
  project template or a stored "window" definition that re-queries.
- Visibility: group-scoped by default; public slice only if the group opts a
  "come help" listing in (that's the litefarm/needs-&-offers seam, separate).

## Cross-references

- Plane = the projects app (issues per group) — task source for general work.
- `litefarm-integration.md` §6 — farm tasks as the LiteFarm leg; the note
  there (farm work → needs/offers board) is the *public reach* version of this
  flow, not the internal sign-up sheet.
- `private-treasury-guards-ledgers.md` §4 — Tier-2 participation ledger
  (time-bank/quest credits) is where check-offs land.
- `zk-membership-graph-proofs.md` / zk-badges — completion history is the
  badge substrate ("≥ N work days" without which ones).
- Needs/offers matching — deliberately NOT this; exchange vs. contribution.
