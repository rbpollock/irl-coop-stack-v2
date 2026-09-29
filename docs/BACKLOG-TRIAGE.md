# BACKLOG-TRIAGE.md — proposed backlog grouping

Status: checkpoint triage proposal · 2026-09-29.
**No issue was created, edited, or closed.** This document proposes a grouping so a
returning maintainer can triage quickly. Work the ten items in §3 first.

## 1. Labels

| Label | Means |
|---|---|
| `restart-blocker` | Must be resolved before the project can be picked up again at all |
| `security` | Affects confidentiality, integrity, or access control |
| `pilot-critical` | Required for the first pilot to produce a real answer |
| `usability` | Affects whether a real person can use it unaided |
| `integration` | Wiring between services rather than work inside one |
| `architecture-decision` | Needs a decision before code; not implementable yet |
| `operations` | Running, backing up, recovering, or accounting for the system |
| `future-platform` | Real, but not needed for the first pilot |
| `financial-high-risk` | Touches money, custody, or ledger correctness |
| `agent-high-risk` | Gives automation or an AI write authority |
| `needs-evidence` | A claim without a test, record, or reproducible procedure behind it |
| `good-first-return-task` | Small, self-contained, low-risk, and useful immediately |

## 2. How to read this

**Ten items are listed, and only two are implementation.** The project's dominant problem
is not missing code — it is missing evidence, missing backups, and missing decisions.
A backlog that reads like a build queue would be a misdiagnosis.

## 3. The ten highest-leverage items

### B-01 — Bring the stack up from the repository on a clean host
- **Labels:** `restart-blocker`, `operations`, `needs-evidence`
- **Why:** every other restart claim rests on this, and it has never been done. The
  declared bring-up omits the two host processes the stack needs.
- **Depends on:** secrets material only.
- **Done when:** a machine that has never run the stack reaches the sign-in page and
  completes one authenticated request, using the repository plus the secrets material —
  with every deviation written down.
- **Work type:** verification.

### B-02 — Take a backup and restore it, once, successfully
- **Labels:** `restart-blocker`, `operations`, `security`
- **Why:** no backup exists anywhere. Every data-bearing store is one failure from gone,
  and the project already has an unrecoverable-loss incident in its history.
- **Depends on:** nothing.
- **Done when:** a dump of each data-bearing store is restored into a scratch instance
  and a known group's data is read back and matches.
- **Work type:** implementation, then verification.

### B-03 — Get the first-party images off the host
- **Labels:** `restart-blocker`, `operations`
- **Why:** thirteen custom images exist only on the host. If it dies, the custom database
  bundle, the farm fork, the ticketing gate, the telephony builds, and the search stack
  are gone; only recipes remain.
- **Depends on:** a registry or an off-host archive location.
- **Done when:** every first-party image is retrievable from somewhere that is not the host.
- **Work type:** operations.

### B-04 — Name a successor and record a recovery arrangement
- **Labels:** `restart-blocker`, `operations`
- **Why:** the single risk that no engineering can fix. Currently no person is identified
  who could continue the project.
- **Depends on:** a human decision by the owner.
- **Done when:** at least one named person can reach the domain, the repository, and the
  secrets material; the arrangement is written down.
- **Work type:** documentation (of a decision) + a human action.

### B-05 — Decide the chain
- **Labels:** `architecture-decision`, `financial-high-risk`
- **Why:** it blocks the treasury contract and therefore every money feature. Money is the
  owner's stated headline proof, so this decision gates the project's ambition.
- **Depends on:** owner judgement.
- **Done when:** a chain is chosen and the choice is recorded in `DECISIONS.md` with its
  rationale.
- **Work type:** design / decision.

### B-06 — Implement D-16: a seat's holder is a Safe
- **Labels:** `architecture-decision`, `pilot-critical`
- **Why:** it is what makes person-membership and group-membership the same mechanism, and
  therefore what makes a collective of coops representable at all.
- **Depends on:** confirmation that acting-*as*-Safe resolution is solid for members who
  hold several Safes.
- **Done when:** a membership record identifies its holder by Safe; a person's own Safe
  and another group's Safe are both valid holders; access resolves through the acting Safe;
  the row-level helpers and their tests are updated together.
- **Work type:** implementation.

### B-07 — Make group-of-groups navigable
- **Labels:** `pilot-critical`, `architecture-decision`
- **Why:** the intended pilot group is a collective containing several farm coops. Being
  able to *record* it is not the same as being able to *navigate* it.
- **Depends on:** B-06.
- **Done when:** a collective can list its member coops and a member of a coop can tell
  which collectives their coop belongs to.
- **Work type:** implementation.

### B-08 — Invite and onboard one real person, end to end
- **Labels:** `pilot-critical`, `usability`, `needs-evidence`
- **Why:** the invite-and-onboarding journey is labelled *not verified*. It is the very
  first thing every pilot participant must survive, and the most likely place to lose them.
- **Depends on:** the stack running.
- **Done when:** a person who has never seen the platform is invited, signs in, and reaches
  the right group — with the friction counted, not explained away.
- **Work type:** verification.

### B-09 — Run the Stage 1 pilot with one farm coop
- **Labels:** `pilot-critical`, `usability`
- **Why:** the project has **zero** real-user evidence. `REALITY.md` never uses the label
  "Demonstrated in a real group workflow". Everything else is inference.
- **Depends on:** **B-08 only.**
- **Done when:** 3–8 people complete one bounded shared work session on the platform and
  answer the feedback questions in `FIRST-PILOT.md`, and the findings are recorded in
  `REALITY.md` — including the unflattering ones.
- **Work type:** verification.

### B-10 — Correct the stale documents and the unsupported claims
- **Labels:** `good-first-return-task`, `needs-evidence`
- **Why:** `REALITY.md` records five document-vs-code contradictions, including a contract
  cited as existing that does not. A returning maintainer will otherwise trust the wrong
  document, and collaborators will repeat claims the code cannot support.
- **Depends on:** nothing.
- **Done when:** `STATUS.md` and `AGENTS.md` are corrected or clearly marked as historical;
  the non-existent contract reference is fixed; the stale network address is corrected.
- **Work type:** documentation.

## 4. What this backlog deliberately does not say

- **The platform does not need to be finished for the project to learn something.** B-09
  depends only on B-08. It can run next season, on one group, without money, without
  nested groups, and without a chain decision.
- **Money is not on the critical path to learning.** It is on the critical path to the
  owner's *ambition*. Those are different things, and conflating them is how projects
  spend two years building a treasury nobody has tested a group on.
- **`future-platform` work is not urgent.** The parked integrations, federation design,
  and CMS work are real and can wait indefinitely.
- **No item here proposes a large rewrite.** The largest is B-06, and it is a change of
  identity keying, not a new subsystem.

## 5. Suggested triage order

1. B-02, B-03, B-04 — the three that stop being fixable once the gap starts.
2. B-10 — cheap, and it stops the documentation misleading whoever returns.
3. B-01, B-08 — the two verifications that unblock the pilot.
4. B-09 — the pilot itself.
5. B-05, B-06, B-07 — the path to the owner's ambition, once the pilot has produced
   evidence.