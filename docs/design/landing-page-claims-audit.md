# Landing page claims audit — and what to actually do

Status: audit + plan (revised) · 2026-09-13 · Robbie + Hermes.
Registry: `docs/design/claims.data.json`.
Surface: `apps/web/irl-dashboard/src/app/[lang]/(plain-layout)/page.tsx`.

## 0. The standard this audit uses — corrected 2026-09-13

**My first pass held the landing page to a marketing standard. That was the wrong standard, and
Robbie corrected it: the entire platform is under development, so its claims are aspirational by
design — not a sales pitch.**

The consequence, which I had backwards:

- **Do not weaken an aspirational claim to satisfy an audit.** Present-tense description of intent is
  the normal convention for software being built — every README does it — and the page's own docs
  section already states the posture: *"written for anyone to read and challenge."* The ambition is
  the point of the page. An audit that strips it is misreading the genre.
- **The right question is not "is this true yet?" but "does the reader know where it sits?"** A
  development project's roadmap is an **asset**, not a caveat: it attracts collaborators, it invites
  the review the site asks for, and it lets the big claims stand at full strength.

**So the registry's job is inverted from my first draft: it is not a compliance register. It is the
source of the public roadmap** — one place that answers "is this true today?" the same way everywhere.

### 0.1 The one exception — and it is a different kind of claim

**A `live-state` claim asserts a fact about *current conditions* rather than about *capability*.
Aspiration cannot cover it, because it is not aspirational — it is a status report, and it is the
only kind of claim on the page that can be false while everyone is being honest.**

There is exactly one: the footer. (Same distinction as the video rules: *a recording is a receipt,
an animation is a claim.* A status dot is a receipt.)

### 0.2 The vocabulary — what a visitor experiences

| Status | Meaning | Count |
|---|---|---|
| **works** | Usable today. `note` carries any caveat (e.g. it doesn't persist) | **21** |
| **in-progress** | Partly usable, or actively being built right now | **5** |
| **designed** | Settled design, not started. Aspirational — publish the stage, keep the claim | **8** |
| **live-state** | Asserts current conditions. Must be wired to a real source, or removed | **1** |

### 0.3 The correction that made this honest

| Was | Now | Why |
|---|---|---|
| `app-needs-offers` = **mockup** | **works** (doesn't persist) | **Wrong, and I should have opened the file.** `needs-offers-mockup.tsx` is **780 lines of working UI** — tabbed weave/board/trade-chain views, an interactive `react-force-graph-2d` weave graph, posting composer, zone filter, search, selection drawer, expediting detail. The name is legacy; the page comment (*"mockup only — no backend wiring yet"*) is where it came from. **It functions. It doesn't save.** |

**The rest of the inventory stands** — 20 of the 35 were verified `works` from the code, and the
classification of the designed eight is unchanged. What changes is what those labels *mean* and what
to do about them.

## 1. The one thing that is actually wrong

**The footer's green dot and "All systems operational."** Hardcoded JSX (`page.tsx:857-860`);
nothing reads health; audit-time reality was 21 of 82 services down.

This is the only item on the whole list that is a **defect rather than a roadmap entry**, and it is
the cheapest fix in the document:

```
wire: GET /api/v1/stack/status   (exists; the dashboard home already renders it)
or:   delete the dot
```

A green dot that does not read health is worse than no dot at all — it makes *every other claim on
the page* look like decoration, including the aspirational ones that are honestly framed.

## 2. The eight designed claims: publish the stage, keep the claim

**Do not rewrite them into the past tense.** Label them and let them stand at full strength:

> *"Members can prove to each other that they belong, without any public roster an outsider could
> read."* — **in design**

That is more persuasive to this audience than either an unqualified claim (which a cooperative reader
will test) or a timid rewrite (which signals the project doesn't believe itself). The badge is not an
apology; it is the project's honest self-report, and the docs section on the same page **already does
exactly this** — its cards render `{doc.status}` from the registry. The FAQ simply never adopted the
pattern.

## 3. The five in-progress claims: one-line notes, not rewrites

| Claim | The one line to add |
|---|---|
| *Every decision on a quorum* | "Decisions record today; the voting interface is in progress." |
| *A treasury per group — automatic splits* | "A group treasury exists; funds and splits are in design." |
| *Members hold roles — one plans, one spends* | "Roles work; 'one spends' waits on the treasury." |
| *A group can be private* | "Scoping is real — it hides rows from other tenants; it is not encryption." |
| *You can take it with you* | "Files and open formats export today." |

## 4. What to actually do, in order

| # | Step | Effort | Why here |
|---|---|---|---|
| **1** | **Fix the footer** — wire `GET /api/v1/stack/status`, or delete the dot | ~1 hour | The only defect. And it sits under everything else, so it is the cheapest credibility in the document |
| **2** | **Rename the file** — `needs-offers-mockup.tsx` → what it actually is | minutes | The name has now fooled me and it will fool the next reader. Add the persistence note where a visitor would post something real |
| **3** | **Add the stage layer** — render the status from `claims.data.json` on the FAQ answers and app cards | ~half a day | Keeps the ambition, adds the roadmap, and makes the posture explicit instead of inferred |
| **4** | **One source for all surfaces** — landing page, `/design`, the interactive components (`interactive-arguments-and-the-cta.md` §3), and the survey readout read the same file | with step 3 | So "is this true today?" has exactly one answer everywhere |
| **5** | **Re-audit as a diff** — the registry carries `audited_on` and `revision` | ongoing | The next pass compares, rather than re-reads |

**Nothing in this plan removes a claim.** Steps 1 and 2 fix a defect and a misleading filename;
steps 3–5 turn the aspirational posture into a published roadmap.

## 5. The two governance blockers (not engineering)

| Claim | Needs |
|---|---|
| *Membership runs on a sliding scale* | **The coop to set a price.** The price is simply the cost calculator's calculation for the previous month of usage. This is not required to be paid. The cost model's `revenue.member_monthly` is still `illustrative: true` |
| *Automatic splits, paid on a schedule* | **A group to set a split policy.** The engine is the easy part |

Both are decisions, not builds — and both are honest to leave aspirational until the coop makes them.

## 6. What "done" looks like

- The footer reads real health and tells the truth when something is down.
- Every claim carries a visible stage, rendered from one file.
- The page keeps every ambition it has today, and a reader can tell what they can use tonight versus
  what is being built — **which is the actual promise a project under development should make.**
