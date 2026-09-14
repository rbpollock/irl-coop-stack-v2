# Survey 0 — "Is cooperation for you?" (instrument spec)

Status: draft instrument · Sep 2026 · Author: Robbie + Hermes.
Part of the Cooperation Starter Pack (`cooperation-survey-templates.md` #0).
Purpose: a **learning tool** first and a funnel second. It interrogates the value
system underneath the wish — what a person is *actually* reaching for when they
imagine being rich, safe, or free — and then compares two honest routes to that same
thing: **accumulate** or **coordinate**. It never grades the person, never shames the
want, and is explicit that cooperation has a price.

## The insight this survey is built on

People rarely want money; they want what they think money buys — safety, freedom from
permission, time, good food and gatherings, being needed, being respected, a culture
that belongs to a place. Accumulation is one route to those ends. Cooperation is
another route to *the same ends* that doesn't require hoarding — and in several cases
delivers them **better**: locally sourced food with real ingredients, gatherings with
actual feeling instead of jockeying for position, people who show up when you're in
need, a culture made of the place rather than a repackaged consumer version of it.

The survey's job is to let the respondent *see their own want clearly*, then see both
routes side by side, including what the cooperative route costs (slower, negotiated,
visible, obligated, occasionally conflicted). A funnel that hides the cost produces
people who leave in month three.

## Design rules specific to this one

- **No score, no "cooperativeness" rating, no ranking.** Branch on *what they named*,
  so the reflection reads back their own words ("safety") — never a number about them.
- **The want is legitimate.** Every question treats the desire for wealth, autonomy,
  or status as sane and human. No moralising, no "greedy", no implied right answer.
- **Anonymity is irrelevant here** (it's solo), but the answers are the person's own —
  nothing is shared with any group unless they choose to show it.
- **It must be answerable in a group chat context**: ~4 minutes, mobile-first, plain.

## The instrument (12 taps + reflection)

**Q1 — "When you picture being rich, what does the money actually buy?"**
*(multi-select, max 3)*
`Safety and never worrying about money` · `Freedom to do what I want, when I want,
without asking anyone` · `Time that's mine` · `A beautiful place to live and good food
to eat with people I like` · `Being respected / looked up to` · `Knowing my people are
covered if something happens to me` · `Being able to make something real — a farm, a
building, a body of work` · `Leaving something behind that outlasts me`
*(→ sets the reflection branch: whichever they pick as primary)*

**Q2 — "Which of these would you genuinely be sorry to give up?"**
*(multi-select)*
`Deciding alone and moving fast` · `Nobody being able to tell me what to do` ·
`Keeping my money and my things separate` · `Not depending on anyone` · `My privacy` ·
`Being the one others look to` · `Not having obligations to people`
*(→ the honest cost probe: these are the things cooperation asks you to trade. Naming
them up front is what makes the rest credible.)*

**Q3 — "Think of a time you felt genuinely well. What made it good?"**
*(multi-select)*
`People who showed up for me` · `The food, the place, the table` · `Being needed` ·
`Making something real with my hands` · `Being seen for who I am` ·
`Moving at my own pace` · `Having no obligations for a while` · `Something else`

**Q4 — "When you need something you can't get alone, what do you do?"**
*(single-select)*
`Ask someone and owe them one` · `Pay for it` · `Do without` · `Join something that
already exists` · `Build it myself, slowly` · `I usually figure it out alone`

**Q5 — "Right now, how much coordination can you actually carry?"**
*(two ratings, 1–5, presented as a pair)*
`I want to decide alone ○○○○○ I want to decide together` ·
`I have almost no spare hours ○○○○○ I have real time to give this`

**Q6 — "Which side of these are you on today?"** *(3 pairs, single choice each)*
`I need more money` / `I need enough money and better living` ·
`I never have enough time` / `I want more of my time to be unclaimed` ·
`Obligations to people drain me` / `Being needed sustains me`

**Q7 — "What would make this not work for you?"** *(open text, optional)*
*(the pre-mortem; also the single most useful answer for whoever's in the room with
them later)*

**Q8 — "Who came to mind while you were answering?"** *(open text, optional)*
*(the relational probe — pairs with the "invite them" CTA)*

## The reflection (5 branches + one shared card)

Logic: jump on **Q1's primary pick** (Formbricks `jumpToBlock` / conditional logic) to
one of five tailored endings. Each ending has the same five-part shape:

1. **Name it back.** "You said the thing you're reaching for is *safety*."
2. **The accumulation route, honestly.** What that route gives, and what it charges:
   you pay in time, in isolation, and in dependence on systems you don't control.
   It works — some people get there.
3. **The coordination route, to the same end.** Concrete, not romantic:
   - *safety* → many small interdependencies beat one big pile: people who cover you,
     a group fund, a shared roof, skills you can borrow
   - *freedom from permission* → pooled capacity: the van, the kitchen, the shop, the
     tool library — you own a share, you don't ask leave
   - *time* → shared labour, rotas, division of the unglamorous work
   - *place, food, gatherings* → local sourcing, cooking together, a table that isn't a
     performance; a gathering where nobody's jockeying
   - *being respected / needed / leaving something* → being depended on beats being
     envied; a named role in something that outlives you
4. **The price of the cooperative route, plainly.** Slower decisions, negotiation as a
   permanent feature, your wants being visible to others, real obligations, and
   conflict you can't dodge by leaving quietly. If those look worse than the gains,
   that is a legitimate answer — cooperation is one good option, not the only one.
5. **Next step** (one tap): take the answers to your chat · start a group ·
   see the next survey in the pack.

**Shared card (all branches): "How to read this with your people."** Bring your Q1 and
Q2 answers to the conversation; compare them before comparing anything else. Where Q1
overlaps and Q2 is tolerable, you have something to build. Where Q2 collides, no
amount of shared purpose will save it — better to know on page one.

## Build notes (Formbricks 5.4.0, our instance)

- **Public link survey** on `surveys.irl.coop` (ungated, `skip-auth` path), in the
  irl.coop skin (tokens + self-hosted serif). Mobile-first: the audience is a chat.
- **Logic jumps are supported in OSS** (`ZSurveyLogic` → `ZActionJumpToBlock` /
  `legacy jumpToQuestion`; also `ZActionCalculate` + `number`/`text` **variables**), so
  the five reflections are real branches on Q1 — no scoring of persons required.
  If we ever need a computed element (e.g. a "coordination readiness" read-back), use a
  *named variable* and show it as descriptive language, not a grade.
- **Question types available**: single/multiple choice, rating, NPS, open text, matrix,
  file upload, CTA, consent — Q1–Q8 map cleanly.
- **Ending CTA**: `https://irl.coop/signup?intent=formbricks` (already repointed in the
  chrome patch) — so finishing the survey lands them in a workspace **born
  irl.coop-styled** (auto-skin, §6e).
- **Where the pack lives**: build these in a `Blueprints` workspace and let groups
  duplicate, or add a real template pack to the fork later (scope doc §6d).

## How the branch is actually wired (implementation note)

Formbricks **endings cannot carry logic** (`ZSurveyEnding` = endScreen | redirectToUrl),
so the reflection is routed by a `logic` rule on a question: `objective:
"jumpToQuestion"` with the **ending id as the target** — `survey-transformation.ts:191`
explicitly handles ending ids and converts them to `jumpToBlock`. Verified against the
pinned source, not assumed.

Two consequences:

- The branch key is the **final required question** (`q12_most_matters`, single-select
  over the five want-buckets), not Q1. Logic fires when its own question is answered, so
  a required closer always routes — a multi-select Q1 is ambiguous (what if they pick
  safety *and* freedom?) and an optional question would silently fall through.
- Endings[0] is a **generic fallback** ("read this one out loud to your people");
  endings[1..5] are the five tailored reflections.

| Branch | Want named | Route to it |
|---|---|---|
| `w_safety` | never worrying about the basics | many small interdependencies instead of one pile |
| `w_freedom` | freedom + time that's mine | shared capacity buys hours nobody has to sell |
| `w_belonging` | people who show up | relationships with obligations built in |
| `w_place` | good food, real gatherings, our culture | nearby food, a table that isn't a performance |
| `w_recognition` | respect + something that outlasts me | respect from beside, not from above |

Every branch states the accumulation route *and* the price of the cooperative one
(slower, negotiated, visible, obligated, conflict you can't dodge) — the honest-cost rule
is what makes this trustworthy rather than a pitch.

## 5. Build state — SHIPPED (image `5.4.0-irl.4`)

Delivered as a **code template** (route B), not an API-created survey: Formbricks 5.4.0 has
no template storage at all (the only `%template%` table in the database is Postgres's own
`pg_ts_template`), so templates are code-defined and ship in the image.
`apps/web/app/lib/irlcoop-templates.ts` (363 lines, `irlcoop-templates.patch`) holds the
pack; `templates.ts` spreads `irlcoopTemplates(t)` at the **head** of the gallery array.

Verified end-to-end through the gate as `e2e-test`:

| Check | Result |
|---|---|
| Gallery shows the tile | `hasTitle: true, tiles: 1` |
| "Use this template" creates a survey | `cmtzs7pr0000201pblagymaoq` → editor opened |
| Structure survived the copy | 7 blocks · 12 elements · 6 endings · 5 logic rules |
| Branch routing | all five `w_*` choices land on the matching reflection ending |

Note: a survey created from a template lands as **draft** (that's the app's behaviour, not a
bug) — the group publishes it when ready.

### Discoverability — CLOSED in `5.4.0-irl.6`

Both surfaces now carry the pack, verified in a real browser through the gate:

| Check | Result |
|---|---|
| Gallery tile | `hasTitle true · tiles 1` |
| New **Cooperative** category renders | `hasCooperativeCategory true` |
| Clicking **Cooperative** actually filters | `tiles 1` (the pack is in that industry) |
| New **Group organizer** role renders | `hasGroupOrganizerCategory true` |
| Featured row on `/surveys` leads with it | `hasTitle true` |
| "Use this template" → survey | `cmtzt7y8y000201oikwzzfczf` (7 blocks, 6 endings) |

How: `ZWorkspaceConfigIndustry` and `ZTemplate.industries` gained `cooperative`;
`ZTemplateRole` gained `cooperativeOrganizer` (label "Group organizer"); both mappings
were added to `getIndustryMapping` / `getRoleMapping` + `en-US.json` (and to the upstream
mapping test, which asserts them literally); the pack's template carries
`industries: ["cooperative"]` + `role: "cooperativeOrganizer"`; and `featured-templates.tsx`
prepends the pack to the featured row, reading its name/description from the pack so the
two can't drift.

### Deep links — FIXED in `5.4.0-irl.7`

The redirect condition in `proxy.ts` was `isAuthProtectedRoute(pathname) || pathname === "/"`,
and upstream's protected list doesn't include `/workspaces/<id>/…`. So a deep link fell
through the middleware, the page's server code threw `AuthenticationError`, and the client
router navigated to `/auth/login` (which is why the gate log showed a 200 where a redirect
was expected). Now: **no session + app page + gate header → gate-sso**, excluding `/auth/*`
(the login page must render), `/api/*` (including gate-sso itself — that would loop) and the
public survey domain. Verified:

```
/workspaces/<id>/surveys/templates → 307 /api/auth/gate-sso?callbackUrl=…
/workspaces/<id>/surveys           → 307 …
/workspaces, /organizations, /, /setup/intro → 307 …
/api/auth/gate-sso?callbackUrl=/  → 307 /        (normal success redirect, no loop)
```

### The login page's SSO section is EE — so we added our own door

`login-form.tsx` renders `<SSOOptions>` from `apps/web/modules/ee/sso/**`, which is
enterprise-licensed and renders **nothing** without a licence — hence no SSO button ever
appeared. Same pattern as the ERPNext Social Login Key: a first-party
**"Sign in with irl.coop"** link → `/oauth2/start?rd=<callbackUrl>`, hitting the oauth2-proxy
gate. Verified in a browser (the login form is **client-rendered** — `curl` returns only a
~27 KB shell with no `<form>`, so this can only be checked with a real browser):

```
login page: hasDoor true · href /oauth2/start?rd=https%3A%2F%2Fforms.irl.coop
after click: https://forms.irl.coop/workspaces/<id>/surveys     ← landed inside the app
```

Chip colour for the coop role added too (`getRoleBasedStyling` was falling through to the
neutral slate default).

## 6. Open decisions

- Q1 "max 3" with a follow-up "which of those matters most?" (needed to branch) vs
  a single-primary question: single is faster, but multi-select captures more nuance.
  Proposal: multi-select **then** a one-tap "which one first?" — one extra screen, worth it.
- Do we offer a personal share card at the end (their own answers as an image/link) so
  the conversation starts with artifacts, not screenshots?
- Language: "rich" is deliberately blunt in Q1; alternative framings ("well off",
  "secure") soften it but lose the honesty the question is for.
