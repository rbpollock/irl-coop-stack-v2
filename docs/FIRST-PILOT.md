# FIRST-PILOT.md — the smallest safe real-world validation

Status: checkpoint pilot definition · 2026-09-29.
Owner input: the intended pilot group is a **collective of individual farm coops**
(meta-group). The owner's preferred proof is **money**. This document is written to
honour both intentions *and* the repository's actual state — see §1.

## 0. The evaluation question

> **Can a real group complete a meaningful, bounded piece of shared work with less
> friction and more group autonomy than their usual patchwork of tools?**

Everything below exists to answer that question, not to demonstrate every subsystem.

## 1. Why the pilot is two stages

Three of the owner's intentions cannot run today, and the repository says so plainly:

| Intention | Repository reality |
|---|---|
| Money moves | Still true, but not for the reason this document first gave. D-21 **is** decided (Base `8453`, pinned in `apps/coop-api.yaml`), the rail is wired with real credentials, and a destination address is set — yet **all 4 payment attempts have failed**, the router is not deployed, and nothing has moved. |
| A collective containing coops | Representable as of D-16 (a seat's holder is a Safe). Implemented and verified in a scratch DB — **not yet applied to the live database**. |
| Support from caring experts | Concept only. No running feature, no support roster. |

So the pilot is split. **Stage 1 delivers learning with real people this season.**
**Stage 2 carries the full ambition and is gated on work that does not exist yet.**

Being honest about this is the point: a pilot that promises money and delivers a
mock-up would discredit the project with exactly the people it needs most.

---

## Stage 1 — runnable now

**Hypothesis:** a small farm coop can plan and complete one bounded piece of shared
work inside one platform, with clear roles and their own record of it, at lower
coordination overhead than their current patchwork — and without the platform
operator touching the data.

### Target group
One real farm coop or a small collective of individual producers: **3–8 people**,
including at least one person who is *not* technical and at least one who is
sceptical. The owner has working relationships with several food producers.

### Concrete scenario
**"One shared work session, planned and recorded."**
The group plans and runs a single shared work session — a planting day, a harvest
push, a shared-equipment maintenance day, or a joint bulk-supply run — using only the
platform for planning, assignment, documents, and the record.

### Participant journey
1. **Invited.** Each participant receives an invitation and signs in. (Expect friction
   here — this path is labelled *not verified*; observations are the data.)
2. **Oriented.** They land on the group's home and can see: who is in the group, what
   their own role is, and what is planned.
3. **Assigned.** The facilitator assigns roles for the session (facilitator, doer,
   document-keeper, timekeeper) and each person can see their own role.
4. **Planned.** The group creates the session with a date, a location pin, and a short
   document describing what is happening and who brings what.
5. **Executed.** On the day, tasks are marked done as they are completed; notes and
   photos are attached as wanted.
6. **Recorded.** When the session ends, the group **exports its own record** — the
   session, the roles, the tasks, and the notes — and keeps it.
7. **Reflected.** Participants answer the feedback questions (§ below).

### Roles
| Role | Who | Notes |
|---|---|---|
| Group owner | one member | Can change group settings |
| Facilitator | one member | Assigns roles, runs the session; **the "caring expert" position, if filled, sits here** |
| Member | everyone else | Reads the plan, works tasks, sees the group's own state |
| Observer | the maintainer or a researcher | Watches and records; does **not** do the group's work for them |

### Success criteria (all observable)
- **≥5 of the 8** participants complete one assigned task with **no help from the operator**.
- Every participant can see **their own role** and the **group's plan** without asking.
- The group **exports its own record** unassisted.
- The group reports **lower or equal friction** than its current tools on the same task.
- No participant sees another group's data (verified, not assumed).

### Failure criteria (stop and re-plan)
- Any participant sees data belonging to a group they are not in.
- Any routine step requires the operator to perform it for them.
- The group cannot export its own record.
- Any data is lost or cannot be found again.
- More than half the group cannot sign in without hand-holding.

### Usability observation plan
- One observer, present throughout, taking notes against a fixed template.
- **Time-to-first-task** and **number of interventions** are the two headline numbers.
- Screen recording **only with explicit per-person consent**; notes otherwise.
- Distinguish sharply between "the software failed" and "we explained it badly."

### Consent and privacy
- Written, plain-language consent before anything starts, covering: what is recorded,
  who sees it, how long it is kept, and how to withdraw.
- **No sensitive personal data** beyond what the work session needs. Names only, and
  pseudonyms are acceptable if the group prefers.
- The group owns its data and may delete it at any point without justification.
- No financial information of any kind.

### Feedback questions
1. What did you expect to be able to do in the first five minutes?
2. What was the first thing that confused you?
3. Did you always know what you were supposed to do, and what others were doing?
4. What would you have used instead, and how would that have compared?
5. What would have to be true for you to keep using this next season?
6. What did we not ask about that we should have?

### Exit / cleanup
- The group keeps its exported record; the platform copy is removed on request.
- Teardown is documented so the next pilot starts clean.
- Every finding lands in `REALITY.md` and the backlog — including findings that make
  the platform look bad.

### Feature boundary — Stage 1
| | |
|---|---|
| **Required** | Group create; invite + sign-in; roles visible per member; one session with date/location/notes; task assignment and completion; document attachment; group-state visibility; export |
| **Optional** | Chat channel; photo attachments; maps pin for the location |
| **Deferred** | Money; nested/meta-groups; telephony; agent tools; public pages |

### Stage 1 explicitly excludes
Real fund custody · banking · treasury control · production accounting · legally
consequential governance · sensitive personal data · autonomous write-capable agents ·
telephony and mass email · any irreversible payment or blockchain action.

---

## Stage 2 — the full ambition, gated

**What it adds:** the collective — one meta-group containing several farm coops —
plus **real money in and out** with explicit risk bounds.

**Gate: every item below must be true before Stage 2 starts.**
- [ ] D-16 implemented: a seat's holder is a Safe, so a coop's Safe can hold a seat.
- [ ] The collective is representable and navigable (group-of-groups).
- [x] D-21 decided: the chain is Base `8453`, pinned in `apps/coop-api.yaml` (USDC
      address verified on-chain 2026-09-13).
- [ ] A payment rail exists and has moved value in a non-production test. It exists
      (`:3010`, real credentials) but has moved nothing: 4 attempts, all failed.
- [ ] The treasury contract exists, and the custody question is answered: **who holds
      the key, and can the platform ever act alone?**
- [ ] Written risk bounds: a hard amount cap per group, a refund path, a named person
      accountable for a failure, and a stop condition.
- [ ] A backup and restore drill has succeeded (R-07) — you cannot pilot money on a
      system with no backups.
- [ ] Legal and tax treatment decided for the jurisdiction the money lands in.

**Stage 2 hypothesis (to be re-written once the gates clear):** a collective of farm
coops can pool and move real (small) money under its own governance, with the platform
as a steward that cannot act alone.

Do not write Stage 2's scenario, journey, or success criteria now. Anything written
before those gates are cleared would be fiction, and this project's problem is already
too much fiction ahead of its code.