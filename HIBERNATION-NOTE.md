# HIBERNATION-NOTE.md

**Checkpoint date:** 2026-09-29
**Intended duration:** ~2 years; the maintainer is unavailable, no fixed resume date.
**Maintainer:** one person, on one host (bus factor = 1).

## What IRL.coop is

IRL.coop is an open-source, self-hostable cooperation platform. It exists to help
groups organize from the ground up and build durable alternatives to extractive and
individualistic systems — group identity, roles, coordination, documents, email,
chat, governance, maps, telephony, and (eventually) treasury, in one place the
group controls.

The intended shape is a cooperative commons: every account is a group, every group
is meant to hold its own on-chain account, and groups relate by *declared*
relationships rather than a platform owning the data.

Today it is in development by one person on one host.

## Status — read this before anything else

This project is under active development. It is **not** production-ready and **not**
a fully integrated platform. It is also not a coherent MVP: some pillars are wired
and verified, others exist only as design documents, and money custody — the pillar
that would make a group self-sufficient — **cannot receive or spend anything today**.

Installed software, packages, environment variables, architecture plans, and
prototypes do **not** prove operational readiness. The authoritative statement of
current state is `docs/REALITY.md`.

## Purpose of this checkpoint

1. Reduce the project's dependency on one person.
2. Preserve technically meaningful context — the decisions, not just the code.
3. Record what actually works versus what is merely intended.
4. Make the restart path obvious for whoever returns.
5. Define the smallest safe real-world validation, without risking money, custody,
   private data, or critical operations.

## Continuity documents

| Document | What it answers |
|---|---|
| `docs/REALITY.md` | What actually works, with evidence and honest labels |
| `docs/SYSTEM-MAP.md` | Layers, components, data classification, trust boundaries |
| `docs/RETURNING.md` | How to restart after 6–24 months |
| `docs/FIRST-PILOT.md` | The smallest safe validation with a real group |
| `docs/DECISIONS.md` | Decisions established, tentative, open, rejected |
| `docs/RISKS.md` | Risks, mitigations, and what proof each requires |
| `docs/OPERATIONS-INVENTORY.md` | Accounts, domains, providers — by reference only |
| `docs/BACKLOG-TRIAGE.md` | Label set + the 10 highest-leverage items |
| `docs/WALKTHROUGH-RUNBOOK.md` | A 15–30 minute continuity recording outline |

> All ten documents listed above exist as of this checkpoint date. If any is missing
> from the repository, it was removed after the checkpoint rather than never written.

## Do not infer

- Code present ≠ feature works.
- A package installed ≠ integrated.
- A design document ≠ implementation. There are ~79 design documents; the design is
  far ahead of the code.
- A prototype ≠ a product.
- A working demo ≠ safe for a real group.
- A verified development flow ≠ a reproducible deployment.

Where evidence is absent the correct label is **Unknown**, **Not verified**,
**Concept only**, or **Present in code but not demonstrated**.

## Safe scope during hibernation

Collaborators may, without claiming readiness or taking control of high-risk systems:

- read the repository, the design docs, and this checkpoint;
- run the stack locally and inspect it;
- fix documentation, typos, and small isolated bugs, with review;
- improve tests and documentation;
- prototype one feature behind a flag.

They must **not**, without a design review and the maintainer's approval:

- touch money, custody, keys, or secrets;
- change DNS, deploy to the live host, or rotate credentials;
- treat governance, accounting, or telephony output as operationally or legally
  binding;
- give an AI agent write access to external systems.