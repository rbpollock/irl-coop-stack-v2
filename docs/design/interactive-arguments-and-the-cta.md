# Interactive arguments & the call to action

Status: design · 2026-09-13 · Robbie + Hermes.
How the argument documents become interactive on the landing page, what the CTA is, and where
Formbricks does and does not belong.

## 0. Two findings from the current site that change the answer

**Finding 1 — the docs are already on the web, and Formbricks is already wired for anonymous
respondents.** So neither half of this needs new plumbing:

- `apps/web/irl-dashboard/src/app/(unlocalized)/design/page.tsx` and `design/[slug]/page.tsx` already
  render the documents, and the landing page already links to them ("Docs").
- `design-docs.ts` holds a hand-maintained registry (`slug`, `title`, `category`, `status`,
  `description`, `file`) — so publishing a doc is a **one-entry change**, not a build.
- `infra/instances/dev/apps/formbricks.yaml:21-23` states the split plainly: **`surveys.irl.coop` is
  NOT gated** (anonymous respondents, the `/s/*` + client-API surface), while `forms.irl.coop` is the
  gate-SSO admin. **A public landing-page survey therefore already works with no route changes.**

**Finding 2 — the landing page already promises things that are designed, not built.** This is the
honesty problem, found in the FAQ copy on `[lang]/(plain-layout)/page.tsx`:

| FAQ answer (verbatim) | Reality today |
|---|---|
| *"There's a setting for that. Members can prove to each other that they belong, without any public roster an outsider could read."* | **Non-enumeration is designed and deferred** (`group-scoping.md` §3 tier 2). The setting does not exist |
| *"People can hold verifiable credentials and show them when needed — proof without oversharing."* | zk-badges: designed, not built |
| *"A group can back a claim with a checkable proof… without handing over anything private."* | Selective-disclosure proofs: designed, not built |
| *"Groups earn a reputation through what they actually do — recorded in a way that can be checked."* | Regenerative/cooperativeness score: designed, not built |

**Present tense, unqualified.** This is exactly the `chilling-effect-and-the-story.md` §5.7 guardrail,
violated on the page that matters most — because these four answers are the *most attractive* claims
on the whole site, and they are the four least built. That is not a tone problem; it is the specific
way this platform could lose the trust it is asking for.

**Consequence: the interactive work and the honesty work are the same work.** If the documents become
data-driven, their claims and the page's claims must draw from **one source that carries a status
per claim** — otherwise the interactive version drifts ahead of the product faster than the static
one did.

## 1. Formbricks: right for the CTA, wrong for the documents

**It is a survey engine.** Multi-step branching questionnaires with logic and piping. It is excellent
at *asking*, and it cannot:

- compute anything (no arithmetic — a cost comparison cannot live in it),
- hold explorable data (no hover/expand/toggle over a dataset),
- render the documents without putting the platform's most load-bearing content inside another app's
  templating.

So: **do not move the documents into Formbricks.** But four of the interactive ideas genuinely *are*
questionnaires, and those belong there:

| Fits Formbricks | Belongs in the dashboard |
|---|---|
| "Tell us about your group" intake (the CTA) | The cost calculator (needs arithmetic) |
| The fear checklist — *"which of these have you caught yourself doing?"* | The 300-user wall slider (needs a live chart) |
| The sector quiz → a personalized readout | The gradient/inversion before-after toggle |
| A "what do you need first" preference poll | Doc reading, search, and cross-references |

**Cheap to build, because the templates-as-code workflow already exists** (`refs/formbricks-*.md`).
Two caveats to clear first: the **workspace-scoped** API key (an org-scoped key returns 400, and the
vault entry is still pending — `${VAULT:formbricks.api_key}`), and the **deep-link fix in `5.4.0-irl.7`
is unverified** — which matters precisely because a CTA links *into* a specific survey.

## 2. The CTA ladder — and why "sign up" is the wrong ask right now

The honest problem: **the modes, the vault fix, selective disclosure and the custody chain are not
built.** So a CTA that says "sign up for the private platform" is selling the thing the docs just
admitted is designed. The ladder fixes that by asking for less, honestly, at each rung:

| Rung | The ask | Cost to them | What they get | Why it's honest today |
|---|---|---|---|---|
| **1. See** | "Put your numbers in" — the calculator | 0 — no account | Their own group's comparison, with sourced prices | Arithmetic over published prices; nothing unbuilt |
| **2. Check** | "Where does your group sit?" — sector quiz + fear checklist | 2 minutes, no account | A readout: your adversary profile, the defaults working against you, the mode you'd need, **and what isn't built yet** | Returns something useful whether or not they ever sign up |
| **3. Tell** | "Tell us what you're trying to do" — Formbricks intake | 5 minutes | A reply from a person; a say in what gets built next | The only thing the platform can honestly offer pre-launch |
| **4. Join** | "Start a group" / "Run a node" | An account / an afternoon | The actual product, as it exists | Kept at the bottom, where it belongs until the modes ship |

**Rung 3 is the real CTA, and it is a conversation rather than a conversion.** Three reasons:

1. **It is useful to them even if they never join** — which is the whole ethos, and it means the
   survey is not a funnel wearing a costume.
2. **It is the only thing actually on offer.** Pre-launch, the valuable and honest exchange is
   *information for a reply*, not a freemium account for their data.
3. **It respects `signup ≠ membership`** — telling the platform about a group is not becoming a
   member, and the coop shouldn't blur that for the sake of a metric.

Rungs 1 and 2 are also **the best survey instrument the coop will ever have**: a calculator and a
self-assessment tell you what groups are actually made of, and which fears are load-bearing, without
asking a single demographic question.

## 2b. What this adds up to on the homepage — and what to leave off

**Everything proposed across this session, in one list, with a verdict.** The honest framing
first: the homepage is *already dense* — a hero, 11 recipes, 17 app cards, three "how it works"
tiles, the docs carousel, 24 FAQ answers and a closing CTA. Bolting five interactive tools onto that
buries all of it. **Three additions maximum**, and two of them are fixes rather than additions.

| # | Proposal | Type | Why | Effort | Verdict |
|---|---|---|---|---|---|
| 1 | **Wire the footer to real health** (`core_healthy`/`core_services`) | **fix** | It is the only non-aspirational claim on the page, it is *accidentally true* today, and the endpoint now returns a clean core-only number (`stack-report.py`, 2026-09-13) | ~1 hour | **DO FIRST** |
| 2 | **The cost calculator** — members, organizers, ticket revenue → their own comparison | addition | The one artifact nobody else has, and the thing that makes the fear *falsifiable*. Already unblocked: `cost-model.py --json` emits valid JSON (37 keys) | 1–2 days | **BUILD** |
| 3 | **The stage/roadmap layer** — render `claims.data.json` status as a badge on FAQ answers and app cards | addition | Turns the aspirational posture into a *published roadmap* instead of something a reader must infer. The docs cards on the same page already do exactly this | ~half a day | **BUILD** |
| 4 | **The fear checklist** ("which of these have you caught yourself doing?") | addition | The content and the CTA as one object — genuinely the best survey instrument the coop will get | 1 day + Formbricks survey | **DEFER** to launch |
| 5 | **Sector selector → personalised readout** | addition | Excellent, and it is a *tool*, but its readout must name what isn't built — so it needs #3 first | 2 days | **DEFER** after #3 |
| 6 | **The 300-user wall slider** (drag 10 → 10,000) | addition | The best animation in the series — and it belongs *in the video*, where it has narration. Embed V9 instead | — | **VIDEO, not a component** |
| 7 | **Gradient / inversions before-after toggle** | addition | Compelling, but it is the same content as V11 and the thesis section. Redundant on one page | — | **SKIP as a component** |
| 8 | **Video embeds** (V9, V11) | addition | Highest reach per hour once the videos exist | — | **AFTER the videos** |
| 9 | **Sector-hook copy variants** (`chilling-effect-and-the-story.md` §5b) | copy | One sentence per sector, for the *existing* sections — not a new one | minutes | **USE IN PLACE** |
| 10 | **Needs & Offers: rename the file, note that nothing saves yet** | fix | **`needs-offers-mockup.tsx` is 780 lines of working UI** (corrected 2026-09-13) — the name undersells it and has already misled one reader. It works; it doesn't persist | minutes | **DO WITH #1** |
| 11 | **The claims registry itself** | infrastructure | One source all surfaces read, so "is this true today?" has one answer everywhere | with #3 | **BUILD** |

### The three things this is really about

1. **Fix the two defects** (#1, #10) — an hour, and the page stops containing anything checkably false.
2. **Add the calculator** (#2) — because it is the argument, personalised, and no competitor can
   publish the same page.
3. **Add the roadmap layer** (#3) — because a platform under development should be *visibly* under
   development, and a badge does that better than a disclaimer.

**Everything else waits for a reason**: #4–#5 need a launch to point at, #6–#7 are video or
redundant, #8 needs the videos, #9 is copy that slots into what already exists.

## 3. Per-document interactive treatment

| Document | Interactive form | Value |
|---|---|---|
| `cost-model.md` | **The calculator.** Members, organizers, ticket revenue, map loads → their own comparison against the commercial stack, every price date-stamped and sourced | **Highest.** It makes the fear *falsifiable* (`chilling-effect-and-the-story.md` §0.1) — and it is the one artifact nobody else has |
| `chilling-effect-and-the-story.md` | **The fear checklist.** Tick the ones you recognise → a readout of what each is costing you, each with its limit | **Highest, and it is also the survey.** The content and the CTA are the same object |
| `adversary-models-and-sector-fit.md` | **Sector selector.** Pick your sector → profile, mode, footprint, and the honest limits | High — it is the sales pitch *as a tool* |
| The 300-user wall (V9) | **The slider.** Drag 10 → 10,000 participants; watch the lines diverge | High — the single best animation in the series |
| Gradient / inversions (§0.2–0.3) | **Before / after toggle.** Default ↔ inversion, one row at a time | Cheap, and it *is* the thesis |
| `custody-chain-and-contest-kit.md` | Keep as a deep document; no interactive form needed | Low |
| `federation-encryption-and-access.md` | Keep as a deep document, **except** the operator-blind claim, which needs the disproof-proof presentation before it goes anywhere near a landing page | Low, with one caveat |

**Build first: the calculator.** It has a real data source (`cost-model.data.json`), the machine-
readable path already exists (`cost-model.py --json`), and it answers the one question the landing
page currently cannot: *what would this cost my group?*

## 4. The technical path (single source, or don't bother)

```
docs/design/cost-model.data.json        ← the only place a number is typed
        ├── infra/scripts/cost-model.py --inject → docs/design/cost-model.md   (existing)
        ├── infra/scripts/cost-model.py --json   → src/data/cost-model.json    (new step)
        │        └── interactive components (calculator, wall chart, inversions)
        └── videos + storyboard charts                                          (existing)
```

**Rules that make it worth doing:**

1. **No number is typed in a React file.** The components read the generated JSON. This is the same
   rule the videos follow, and it is why the storyboard's *transcribed* charts were flagged as debt
   (`video-charts-storyboard.html` footer) — now fixable, because the JSON path is real.
2. **Every price renders with `source` + `verified_on`.** The model already carries both; the
   component must show them, or the page becomes marketing.
3. **Any claim with `status != shipped` renders as a commitment, not a capability.** See §5.
4. **A build step, not a runtime fetch.** `--json` writes into `src/data/` at generate time, so the
   page cannot render a half-stale model against a fresh one.
5. **`/design` already exists** — so the docs' interactive versions have a home next to the deep
   versions, rather than replacing them. Long-form stays readable; the argument gets a tool.

## 5. The claims registry — BUILT, and it is a roadmap source, not a compliance register

> **Corrected 2026-09-13.** This section originally framed the page's unbuilt FAQ answers as "the
> honesty problem" and proposed auditing them. That was the **wrong standard** — see
> `landing-page-claims-audit.md` §0. The platform is under development, its claims are aspirational
> by design, and present-tense description of intent is the normal convention for software being
> built. **Do not weaken an aspirational claim to satisfy a register.** What the register is for is
> telling a reader *where the claim sits*.

**Status: built.** `docs/design/claims.data.json` — 35 claims inventoried against the code, with
`audited_on` and a `revision` history (`claims.data.json`; audit in `landing-page-claims-audit.md`).

| Field | Meaning |
|---|---|
| `claim` | the sentence as it appears on the site |
| `status` | **`works`** \| **`in-progress`** \| **`designed`** \| **`live-state`** — what happens if a visitor tries it right now |
| `note` | the caveat one word cannot carry (e.g. *it works, it doesn't save*) |
| `evidence` | code path, route, component, or "not built" |
| `fix` | for `works` claims: `None`. For `designed`: **publish the stage**, do not rewrite |
| `revision` | so a correction is traceable rather than silent |

**The one exception that this register does police** is `live-state` — a claim about *current
conditions* rather than capability. Aspiration cannot cover it, because it is not aspirational. There
is exactly one (the footer), and it is the only claim here that can be false while everyone is being
honest.

**The same registry feeds the survey's readout**, which is how rung 2 of the CTA ladder becomes
honest by construction rather than by diligence — and the video series' sector hooks
(`chilling-effect-and-the-story.md` §5b) draw on the same source.

## 6. What would need to be true

| To claim | Needs |
|---|---|
| The calculator on the landing page | `cost-model.py --json` → `src/data/cost-model.json` + one build step. **Nothing else** |
| The fear checklist as a CTA | A Formbricks survey on `surveys.irl.coop` (already ungated) + the workspace-scoped API key |
| The sector selector's readout | The claims registry (§5) so rung 2 can name what isn't built |
| "Members can prove they belong without a public roster" — **the FAQ's most attractive sentence** | **Non-enumeration built** (`group-scoping.md` §3 tier 2). Until then it must move to future tense or a "planned" badge |
| Anything about operator-blind hosting on the landing page | The vault fix + `federation-encryption-and-access.md` §9's allowed claim, and nothing stronger |
