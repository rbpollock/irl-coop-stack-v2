# Coop-readiness probe

Status: design · 2026-09-13 · Robbie + Hermes.
Companion to `coop-launch-and-roadmap-handoff.md` §7. **This is the thing that turns "a flood of bugs
awaits" into a number you already know.**

## 0. The design brief is emotional, not technical

The probe's job is not only to find problems. **It is to be run.** A probe that produces dread is a
probe that gets postponed, and a postponed probe is worth nothing — so the following are load-bearing
requirements, not nice-to-haves:

| Requirement | Why |
|---|---|
| **Read-only by default** | The fear includes "what if the probe breaks something." A probe that cannot write cannot cause harm. Writes live behind one explicit flag, and are named in the output |
| **Synthetic members, scratch group** | Removes the *social* fear entirely. The "audience" is fabricated accounts. When real tolerant members are swapped in later, the delta should be small |
| **Severity tiers, counted separately** | Fear scales with *unknown* volume × *imagined* severity. Both shrink when the terrifying class is separated and given a number |
| **Pre-registered expectations** | The single most de-escalating technique here — §2 |
| **Bounded passes, stoppable at any point** | Pass 0 is read-only and takes minutes. Nothing forces pass 1 |
| **Re-runnable** | Once it exists, "will this break something?" stops being a feeling and becomes a command |

## 1. What it is not

**It is not a security audit**, not a penetration test, and not a substitute for the adversarial
analysis in `adversary-models-and-sector-fit.md`. It checks that the founding-group journey *works*,
not that the platform is *safe*. Saying so matters: a probe that quietly implies "we audited
everything" would be the single most dangerous artifact in this repo.

## 2. Pre-register the expected findings — the de-escalation that does the most work

**Write the predicted bug list down *before* running anything.** This is not a trick; it is the honest
framing, because the list mostly already exists in these documents:

- The six findings from 2026-09-13 (`coop-launch-and-roadmap-handoff.md` §7.1) — the classifier bug,
  four failed `*-minio-init` jobs, the hardcoded footer, the custodial vault, the
  `needs-offers-mockup.tsx` name, the four aspirational FAQ answers.
- The 8 `designed` claims in `claims.data.json` — **each one is a predicted finding**: non-enumeration,
  verifiable credentials, selective disclosure, reputation, participation credits, treasury splits,
  nested groups, sliding-scale pricing.
- The known-honest limits already written down: rows plaintext at rest (`group-scoping.md:61-63`),
  MinIO SSE off (`minio.yaml:21-23`), no epoch keys (so a departed member keeps what they had),
  `signup ≠ membership`.

**If the probe returns that list, it has confirmed rather than surprised.** That is the whole point:
the flood is not unknown, it is un-*collected*. A probe that finds 30 things of which 26 were
pre-registered is a checklist. The other 4 are the actual news, and now they have a number.

## 3. Severity tiers — so the scary class is separated and counted

| Tier | Definition | Expected volume |
|---|---|---|
| **S1 — catastrophic** | data loss, permission/scoping leak, money moved or lost, credentials exposed | **expect 0. Any S1 is a stop-everything and is the probe's entire justification** |
| **S2 — blocking** | a founding member cannot complete the core journey (sign in → group → seat → invite → see it) | a few |
| **S3 — degrading** | it works, but with friction, a wrong default, or a misleading surface | most of them |
| **S4 — cosmetic / naming / copy** | the six findings above are mostly here | the bulk |

**The distribution is the reassurance**, and it is checkable rather than asserted: the probe prints
the counts per tier. If the first run is 0 / 3 / 12 / 19, the honest reading is "19 things that
embarrass us and 3 that block three people who expect breakage" — which is a very different fact from
"a flood of bugs."

**Small-sample honesty:** a few hours of adversarial *reading* on 2026-09-13 produced 6 findings, **0
of them S1**, and 3 of them naming/copy/process. That is weak evidence from a biased sample (reading,
not running) — and it is the only evidence that exists. The probe replaces the estimate with a
measurement.

## 4. Passes — each one stoppable

### Pass 0 — read-only infrastructure (~10 minutes, no writes, no audience)

Safe to run immediately and repeatedly.

- Stack report: core services healthy, and **the failed-job list specifically** (the four
  `*-minio-init` at `Exited (1)` are current, real, pre-registered findings).
- Declared-vs-running drift; undeclared containers.
- **Disk headroom** — 87 GB free at 81% full is an operational risk for a node that is supposed to
  hold members' files.
- Certificate expiry and the acme.sh renewal window.
- Backup currency: when did the last one run, and does a restore path exist?
- Mail DNS: SPF / DKIM / DMARC present and matching the DKIM selector.
- Every `works` claim in `claims.data.json` that is *statically* checkable (route exists, component
  renders, file present).

### Pass 1 — the synthetic founding group (~an afternoon, writes, **no humans**)

> **Blocked on the flow.** This pass scripts the journey from "I have an idea" to "something useful",
> and that journey is designed-not-built (`idea-to-useful.md` §0). Its §5 steps are what this pass
> would exercise. **Build the flow, then this.**

A scratch group with fabricated members, exercising exactly the founding-group journey:

1. A synthetic user signs in through the fleet gateway (the one-cookie instant path).
2. A group is created; the group Safe predicts and deploys.
3. Three synthetic seats are added with different roles and `visibility` values.
4. **The highest-value check in the whole probe: a non-member receives 403 on every group read.**
   The earlier review *read* the code and found the gates in the right place
   (`groups.ts`: `isOwner` / `isMember` / `withIdentity(claims.sub, …)`) — the probe **tests it at
   runtime, across groups**, which is a different claim. This is the one to run first in pass 1.
5. One seat leaves. **Pre-registered finding: they retain access** (no epoch keys). Confirming this is
   success, not failure — it converts a documented design gap into a measured one.
6. The founding-set apps open group-scoped: Plane project, NocoDB base list, a per-group chat room.

**The claims registry *is* the test plan** — each `works` claim becomes a pass/fail check, so the
probe is largely already specified and it stays current as the registry updates. That is the registry
paying for itself a second time.

### Pass 2 — three real tolerant members (only when pass 1 is clean)

The delta from pass 1 should be small: real humans do the things you did not think to script, which is
precisely the information the synthetic pass cannot produce. This is the step the fear is about, and by
now it is the *cheapest* step rather than the first one.

### Pass 3 — ongoing

Re-run pass 0 on a schedule; pass 1 before any release that touches identity, groups or seats.

## 5. What "ready" means

The test is deliberately falsifiable, from `coop-launch-and-roadmap-handoff.md` §7.4:

> **If starting the coop with three tolerant members produces a bug list you can hold in one page, the
> coop was ready and the fear was the only thing in the way.** If it produces one you cannot hold, that
> is the instrument doing its job — strictly better information than exists today.

Add the tier rule: **pass 2 only proceeds if pass 1 has zero S1 and no S2.** Everything else is a
known list, and a known list is work rather than dread.

## 6. Build order

| Step | What | Effort |
|---|---|---|
| 1 | **Pass 0 as a script** (`infra/scripts/coop-readiness.py`) — read-only, reuses `stack-report.py`, prints the severity table | ~half a day |
| 2 | **The expected-findings file** — pre-register the list in §2 as data, so the probe can mark each finding **confirmed / not reproduced / new** | ~2 hours |
| 3 | **Pass 1** — the synthetic journey, driven from the existing browser-runner fleet (`infra/scripts/journeys`). **DEPENDS ON THE FLOW: `idea-to-useful.md` §5.** Scripting it before the journey exists measures the design doc, not the product | 1–2 days |
| 4 | Pass 0 on a cron, so drift is caught before members are | ~1 hour |

**Start with steps 1 and 2.** They are read-only, they need no decisions from anyone, and together
they replace "I'm scared of what it will find" with a printed table of what is already known plus a
short column of what is new.
