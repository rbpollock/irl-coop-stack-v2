# Cost model — what this replaces, and what it costs to run

Status: live (generated) · 2026-09-13 · consumes `docs/design/cost-model.data.json`
Used by: `docs/design/intro-video-series.md` (V3 side-by-side, V8 self-sustaining),
any landing-page pricing section, and the eventual `/api` cost readout.

Regenerate (never hand-edit the numbers):

```
python3 infra/scripts/cost-model.py            # print
python3 infra/scripts/cost-model.py --inject docs/design/cost-model.md
python3 infra/scripts/cost-model.py --json     # machine-readable
```

## Why this file exists instead of a spreadsheet

V3 ("what this costs, side by side") and V8 ("why this can pay for itself") are the two
videos whose entire persuasive force is arithmetic. Arithmetic in a video is only as good as
its source, and hand-typed numbers in a slide deck rot silently. So the numbers live in one
JSON file with a source and a verification date per price, and a script that emits every
figure the videos use.

Three rules are **enforced in code**, not just documented here:

1. **A price with `status != "verified"` never enters a total.** It appears in an "open items"
   list instead. The code cannot produce a total that quietly includes an invented number.
2. **Every commercial price is the annual-billing list price** — the cheapest published rate —
   so the comparison stays conservative. Where a real-world negotiated price is *higher*
   (Slack Enterprise+ was custom-quoted, so the source is the median of 535 verified
   purchases), that is stated rather than substituted.
3. **Costs common to both worlds are excluded** rather than counted as savings: card
   processing (~2.9% + $0.30), the group's own labour, and the price of the software the
   group already had. Only the *delta* is claimed.

## The three worlds, framed honestly

| World | Its honest strength | Its honest cost shape |
|---|---|---|
| **Enterprise (per-seat)** | Everything is supported, integrated, and someone else is accountable | Cost scales with **headcount** — including members who can't pay. And the real price isn't the list price, it's the procurement process |
| **Mid-tier (fixed fee)** | Genuinely good value; most small organizations should be here and are | Fixed per **app**, with tier ceilings tied to how many people you serve. A co-op needs five of them, and growing means moving up a tier |
| **irl.coop** | One identity, one event stream, one stack the members govern | Membership + stewardship of **shared infrastructure**; the marginal group costs almost nothing. The group can export everything and leave |

The comparison is deliberate about not being a price-war table. Beating Slack on
$ per seat means competing on the incumbents' turf. The argument is: **a cooperative is paying
for governance and coordination, not for seats** — and per-seat pricing is a tax on being
a large, poor, member-run organization.

## What each input is for

| Input | Where | Why it matters |
|---|---|---|
| `scenario.members` | `cost-model.data.json` | multiplies every per-seat line. Use a real group's headcount, not a round number chosen to flatter |
| `scenario.ticket_revenue_monthly` | same | drives the per-transaction comparison — the sharpest line in the model |
| `node.*` | same | the denominator of "self-sustaining". **Currently illustrative** — the emitter watermarks every derived number until a real hosting figure is set |
| `stewardship.*` | same | a person's time, kept as its own line. Folding it into "infrastructure" is the move that makes every self-sustaining claim collapse a year later |
| `revenue.*` | same | irl.coop's own pricing — a governance decision, not an arithmetic one. Currently illustrative |
| `comparables[]` | same | one entry per commercial equivalent, with source + `verified_on`, plus a `tiers` list naming which column(s) it represents |
| `slice_scope` | same | who needs a paid seat per slice. **`members` only where access can't be granted as a free viewer** (identity, mail, chat); everything else is charged at the organizer count |
| `tiers` (per comparable) | same | explicit tier membership — `lean` / `standard` / `enterprise`. Never inferred from list order |
| `mid_tier_pick` (per comparable) | same | the *credible* entry for a per-org slice ($85 QuickBooks Essentials, not $38 Simple Start). Slices without one fall back to the cheapest and are reported |
| `node_external` | same | third-party costs the node pays and **cannot** make free — carrier DIDs. Kept out of "infrastructure" on purpose |
| `storage` | same | the **measured** footprint (du on the host, dated), its live/scratch split, the disk, and the $/TB hardware input behind the node's own rate |
| `scenario.map_loads_monthly` | same | drives the map-tile comparison; each vendor's free allowance is honoured |
| `scenario.egress_gb_monthly` | same | drives the transfer comparison — the line where storage bills actually live |
| `free_monthly` / `free_multiple_of_stored` (per comparable) | same | usage free allowances (Mapbox 50k loads, Google 10k, B2 3× stored) |
| `zero_is_the_rate` (per comparable) | same | marks a genuinely verified $0 (R2 egress) so it isn't confused with a deliberately unquoted rate |

## The three editorial judgements in this model

Say all three out loud before showing any number, because a reader who spots them unaided
stops trusting the rest of the page.

1. **Which product represents each tier.** `standard` is defined as *the tier with real
   admin/SSO controls*, because irl.coop ships SSO and comparing against a no-SSO tier would
   be comparing against something a member org can't actually run. That is a judgement, and
   it is written into the data (`tiers: [...]`) rather than hidden in a sort order. Every
   per-user slice has an explicit pick for all three tiers — the emitter reports any fallback,
   and there are none.

2. **Who needs a seat.** Only identity, mail and chat are charged to all members. Everything
   else is charged at the organizer count, because a 40-member co-op does not buy 40 CRM
   seats. Counting every slice at every member would inflate the per-seat column by ~3×
   ($5,092 → $2,226), and the inflated number is the one a skeptic would use to dismiss the
   whole comparison.

3. **Which entry is *credible*, not just cheapest.** The mid-tier column wanted to take the
   cheapest per-org plan in each slice, which put accounting at QuickBooks **Simple Start
   $38/mo** — a plan with one user and no bills, i.e. not accounting. It now uses an explicit
   `mid_tier_pick` (Essentials, $85). Same mechanism as `tiers`: the judgement is written
   down instead of emerging from a `min()`.

## The four comparisons worth doing on camera

Robbie picked these, and each one turns out to argue differently — which is why they are
worth separate segments rather than rows in one table.

**Telephony — a licence argument, not a free-numbers argument.** The stack makes FreeSWITCH
and FusionPBX free (they are live: `communication 13/13 up`). It does *not* make the phone
number free: a DID is rented from a carrier in every world, so the model carries carrier
numbers as an explicit third-party line ($1.50 × 3 illustrative) rather than burying them in
"infrastructure". What actually changes is the **shape**: carriers sell a line per person
($10–$25/user/mo across Google Voice, Zoom Phone, RingCentral), while the node rents numbers
per *group* and lets one extension ring several volunteers. Segment the seats and the gap
narrows; segment the *numbers* and it doesn't. Never say "phone is free now".

**Accounting — the cleanest cost argument of the three.** QuickBooks Online is a per-company
subscription with a 9× price spread ($38 Simple Start → $340 Advanced), and the Aug 2026
increase moved Plus from $99 to $140. ERPNext is already deployed (`accounting.irl.coop`
answers 200 through the edge). Here the node's claim is straightforward — no per-company
licence, no tier ceiling on users or invoices — and the honest caveat is that the co-op
takes on the upgrades, the tax-jurisdiction setup, and finding someone who knows the system.
Payroll is a separate line in both worlds (~$60 + ~$6.50/employee/mo on QuickBooks).

**Maps — NOT a cost argument, and saying so is the strongest move.** Mapbox gives 50,000 web
map loads free per month; Google gives 10,000 per SKU. At the scenario's 25,000 loads, a
co-op comparing on price pays **$0 either way**, so claiming a saving would be the easiest
claim in the whole model to disprove. The honest segment: Google's own number at that volume
would be $105/mo, the free tier is not a promise (it is a marketing allowance that has already
been restructured once), the card is on file, and the tiles you host cannot be re-priced,
rate-limited, or switched off. **Terms, not money.**

**Storage — measured on the host, and it turned up two real findings.** The slice is built on
`du` output, not on an assumption: **34.3 GB** under `/opt/app/storage`, of which only
**11.25 GB is live data**. The other 23 GB is 12.9 GB of OSM build input (reproducible, not
served) plus **one byte-identical duplicate of the 10 GB basemap** — it exists both at
`geo-data/coverage.pmtiles` and in the MinIO `maps` bucket. The postgres data dir is `0700`
owned by uid 999 and is *not readable from the service account*, so it is excluded and the
footprint **understates** — say that rather than rounding up.

Then the rates, which are the actual argument: the node's own disk works out at
**$0.00217/GB/mo** (hardware ÷ capacity ÷ amortization) against S3 **$0.023**, R2 **$0.015**,
B2 **$0.00695**. At 11 GB that is 2¢ vs 26¢ — **pennies, and not a monthly saving worth
selling.** The honest differences are the *shape* and the *transfer*:

- **One pool vs a quota per member.** Google sells per account; 40 members means 40 accounts
  or a Workspace seat each. The node has no per-member ceiling.
- **Egress is where the bill actually lives.** S3 charges **$0.09/GB out** — 200 GB/mo of
  shared event video is **$18/mo in transfer alone**, often more than the storage line it is
  attached to. R2 is genuinely $0 (verified, marked `zero_is_the_rate`); B2 is free up to 3×
  stored, so only 34 GB of the 200 GB is free and **its overage rate is deliberately not
  quoted** — the model shows "unpriced" rather than inventing a number.
- **The capacity ceiling is real and it is in the provider's favour.** Google Workspace pools
  2 TB *per user*; the node has **87 GB free on a 468 GB disk that is 81% full** — and the
  reason it is 81% full is container images and source checkouts, not data. Per gigabyte the
  node wins ~10×; per terabyte of headroom a consumer plan wins. Both are true; say both.
- **Self-hosting moves the cost from the invoice to the pipe.** 200 GB/mo out of a domestic
  uplink is felt in bandwidth, not on a bill. It is not free, it is unpaid.

## At scale — the argument the rest of this model exists to support

The base scenario (40 members) shows the cost curve is different. The at-scale model shows
**why nobody ever gets to see it**, and it is the piece most likely to be quoted.

The finding is structural, not financial:

| Vendor | Self-serve product | Max users | Above it |
|---|---|---|---|
| Microsoft | 365 Business Premium (and every Business-family SKU) | **300** | M365 E3 — $22 → $39/user/mo |
| Google | Workspace Business Starter / Standard / Plus | **300** | Enterprise, custom quote |
| Zoom | Workplace Business | **250** | Zoom Enterprise, sales-led |
| Slack | Pro / Business+ self-serve | ~**500** active users | Enterprise Grid, negotiated |

Three independent vendors stop selling at ~250–300 users; a fourth at ~500. Microsoft's is
documented as a **hard ceiling across the entire Business family** — at user 301 the product
stops existing and you migrate. This is not incompetence or malice; it is price discrimination
by size. Per-seat pricing makes the bill a function of your success, and past a certain number
the vendor negotiates instead of publishing.

**The org's experience of this is "this is not for me"** — long before it is a bill. That is
the mechanism behind "small orgs preclude themselves from even considering this kind of
growth": they have met the wall once, on some other tool, and they have learned that the
attempt turns into a procurement process they have no staff for.

### The arithmetic at movement scale

Seats are allocated honestly — chat and identity for everyone (that *is* the movement), mail
for staff and coordinators, functional tools for a sliver — so nobody can dismiss it as "you
assumed 10,000 CRM seats". And the killer detail: **participation IS the bill.** Slack prices
Enterprise Grid per *monthly active user*; mail and identity price per provisioned account.
A movement's growth is its invoice.

| | 10,000 participants | 50,000 participants |
|---|---|---|
| Identity (Okta, list) | $140,000/mo | $700,000/mo |
| Chat (Slack Enterprise Grid, low end of the negotiated range) | $110,000/mo | $550,000/mo |
| Docs (Notion Business) | $30,000/mo | $120,000/mo |
| Mail (Office 365 E1 — the cheapest *uncapped* SKU) | $15,000/mo | $60,000/mo |
| **Commercial floor** | **$295,000/mo · $3.54M/yr** | **$1,370,000/mo · $16.44M/yr** |
| **irl.coop node** | **$2,026/mo · $24,318/yr** | **$6,024/mo · $72,288/yr** |
| Per participant / year | $354 vs **$2.43** | $329 vs **$1.45** |
| Ratio | **146×** | **227×** |

Project management is *excluded* from the commercial column because no verified rate exists at
that volume — so the commercial figure is a **floor**, not an estimate, and the model says so.
The identity line is list price and would come down in an enterprise agreement; the Slack line
uses the lowest verified negotiated rate. Both biases run in the argument's *disfavour*, on
purpose.

Note the direction of travel: 146× → 227×. The commercial curve is linear in participants; the
node's is nearly flat (hosts scale with load, stewardship scales sublinearly, and per-
participant cost *falls* from $2.43 to $1.45). The gap widens with success.

### What must be conceded first

**Nonprofit programs.** Google Workspace is **free for eligible 501(c)(3)** organizations via
a dedicated Nonprofit edition (paid tiers from ~$3/user/mo); Airtable's nonprofit rate is
$12 vs $20 list; Microsoft runs nonprofit grants and discounts. State these *before* the
argument, not after — they lower the commercial column for a registered charity. Two limits
keep them from dissolving the point: eligibility is organisational (a loose movement may not
qualify), and they cover **staff accounts** — not 10,000 volunteer participants. Where no
verified rate was captured (Microsoft's nonprofit grant), the model says so and quotes no number.

**What a movement actually does instead.** Not "pay $3.5M" — it uses Discord, WhatsApp,
Facebook Groups, a Google Group and a spreadsheet. Those *are* free at scale, because somebody
else's business model pays for them. That is the honest competitor, and it sharpens the
argument rather than weakening it: the real choice is between a funder-backed extractive
platform and somebody else's free platform the org does not govern and cannot export from.

### The honest limits of the node at scale

- **It is not one box.** The host count (3 and 8) is an estimate, not a measured capacity
  claim. 10,000 Matrix accounts and 10,000 mailboxes need a real topology, and mail needs
  deliverability work — shared-IP reputation, blocklists, SPF/DKIM/DMARC discipline — that a
  commercial provider absorbs on your behalf.
- **The binding constraint is coordination labour, not compute.** Stewardship is the largest
  line in both node columns ($1,800 of $2,026 and $5,400 of $6,024). At 50,000 participants
  moderation is a staffed function. The platform makes the software free; it does not make the
  moderating free. What it changes is that the org *decides* to staff coordination rather than
  *being billed* for every person who shows up.
- **Egress is an assumption** ($5/TB). On a domestic line it is unmetered and invisible, which
  means the cost is real and simply not invoiced. Set it to 0 to model that case, and say so.

## The federation — orgs running nodes that carry for each other

**Scope: the economics and the incentive design.** The DNS/edge topology for surviving a
takedown stays parked (`AGENTS.md`), and nothing below requires deciding it — the tiered on-ramp
deliberately starts with a node that only *holds* data and serves behind a cache.

**This invents no new mechanism.** `event-bus-and-group-shapes.md` §7 and the commons-economy
digest already settled the infrastructure layer: **cost is public**, payment is
private-but-provable, and contribution appears as a **coverage proof** on a subsidy gradient
(free-rider → covers-self → subsidizer), as a positive credential with no shame flag. Running a
node is simply the **in-kind form of the same proof**: *"I covered ≥X% of the platform cost by
hosting it."* No token, no scoreboard, no second economy.

The cost model is what makes that proof possible at all — **you cannot publish a cost you have
not measured.** Which is why the storage measurement and the node rate came first.

### The proposal, in one paragraph

Ask an org for **one hour and about $6 a month** — not a weekend and not a server rack. An
**edge node** holds a full replica of the federation's shared assets and serves the map tiles,
fonts and static JS for its own region. That is the smallest thing that is genuinely useful, it
targets the biggest byte volume in the system, and it needs no inbound public traffic. From
there the ladder runs up: add a backup target for another node ($0 marginal, idle disk), then
take on one shared pillar, then graduate to a full steward instance.

| Tier | Node | Runs | Hardware | Labour | Total/mo |
|---|---|---|---|---|---|
| **B** | Edge — the honest entry point | 5 apps | $6 | 1 hr | **$51** |
| **C** | Service — one pillar for everyone | 12 apps | $18 | 3 hrs | **$153** |
| **A** | Steward — a full instance (this host) | 37 apps | $73 | 8 hrs | **$433** |

**Even the smallest node is labour-dominated by ~8×** ($6 of hardware against $45 of
attention). That single ratio is the design constraint for the whole on-ramp: the entry point
must cost someone an hour, not a weekend, or nobody finishes phase 1.

### Redundancy is nearly free — that is the actual argument

| Nodes holding the assets | Federation storage | Node cost/mo | Resilience |
|---|---|---|---|
| 1 | 11.25 GB | $0.02 | one loss is an outage |
| 3 | 33.75 GB | $0.07 | survives any single loss; rolling upgrades possible |
| 10 | 112.5 GB | $0.24 | survives multiple losses; regional serving |

Each replica is **2 cents a month** of idle disk on hardware the org already bought. The same
three replicas on S3 would cost $0.78/mo — and the *shape* is what matters more than either
number: **the federation's redundancy is not funded, it is the by-product of nodes existing.**
That is the sentence the whole feature turns on. It also means the honest resilience promise is
at the *asset* layer (maps, media, docs, static) — never an uptime number.

### The incentive, without pretending it's altruism

The org gets: no per-seat cost for its own people; its data on hardware it controls with no
per-member ceiling; **a governance seat** (node operators are the ones who can actually hold the
platform accountable); reciprocal hosting, so it stops depending on one host and one person; and
an in-kind credential it can show instead of money. The federation gets: N× serving capacity
with no egress invoice, N replicas, geographic locality, and a failure that stops being
existential.

### The failure modes are the real design work

- **Steward burnout** — the failure that actually ends volunteer infrastructure, and no
  architecture prevents it. Mitigation: tier the on-ramp, require a named second person per
  node, treat handover as a documented procedure. The settled design already gives a signal: a
  stale coverage proof *is* the early warning.
- **Version drift** — N nodes at different generator versions is how federations rot. The
  declarative tree is the defence (each org gets its own instance dir; `stack-report.py`
  already reconciles declared-vs-running per node) — the gap is nobody acting on the report.
- **No SLA, no on-call** — nobody is paged at 2am, which is a real regression against a paid
  provider for mail and chat. Say it in the recruitment video rather than hide it.
- **Hosting other people's data — and it is not all encrypted.** This one was written as a
  governance worry and turned out to be a factual one. MinIO has server-side encryption switched
  **off** (`apps/minio.yaml:21-23` nulls `MINIO_KMS_SECRET_KEY_FILE`); Postgres rows are
  plaintext at rest — the design doc says so itself (`group-scoping.md:61-63`, *"the rows still
  exist in plaintext at rest"*); and mail and collaborative documents are **structurally**
  server-readable, not merely unconfigured. Crucially, **at-rest encryption would not fix it
  anyway**: the operator holds the key, so it protects a stolen disk, not the person holding it.
  Only end-to-end encryption delivers "I don't mind a node hosting my data".
  **So scope federation by pillar and say which is which**: maps/static assets, E2EE chat bodies,
  CryptPad, vault shares and treasury state are federation-safe **today**; mail, documents and
  database rows require a **trusted node**. That is a perfectly good answer for a federation of
  known co-ops — it just has to be a stated property rather than an assumed one. The full
  pillar-by-pillar table, with the evidence, is in the generated model below. **The fix design is
  `docs/design/federation-encryption-and-access.md`** — envelope encryption with a per-group DEK,
  erasure-coded ciphertext sharding across nodes, canaries, and the client-integrity problem that
  quietly breaks all of it if a node serves the client it is not trusted to serve.

## Using this in the videos

**V3** — build the three columns live, in this order: enterprise, mid-tier, irl.coop. Do not
show the totals first; the argument is the *shape* of each cost curve. Show the
`standard`-tier table as the receipt for the per-seat column. End on the per-ticket line
(15.6% of the group's own revenue, growing with success) rather than on the bottom line.

**V8** — the self-sustaining claim rests on two numbers and one honest caveat:
the node's monthly cost, the crossover group count, and *stewardship is real labour*. Show the
command that produced the numbers on screen. Re-run it during recording so the dates match.

**Before either video:** replace the illustrative node and revenue inputs, re-verify every
commercial price, and date-stamp each one on screen.

## The model

<!-- BEGIN GENERATED: cost-model.py -->
### Cost model — generated

Scenario: **40 members**, 6 organizers, 1 group(s) on the node, $4,000.00/mo of ticket revenue at $20.00/ticket. Commercial prices are annual-billing list prices, verified 2026-09-13.

#### Enterprise tier — per-seat

| Tier | Monthly for the org | Composition | Slices on fallback |
|---|---|---|---|
| lean | $1,625.92 | 3 slice(s) × 40 members + 6 slice(s) × 6 organizers | none |
| standard | $2,318.86 | 3 slice(s) × 40 members + 6 slice(s) × 6 organizers | none |
| enterprise | $4,032.08 | 3 slice(s) × 40 members + 6 slice(s) × 6 organizers | none |

Tier membership is set EXPLICITLY per product in `cost-model.data.json` (`tiers: [...]`), not inferred from list order — which product represents "what a member org would actually buy" is an editorial judgement, and the model shows it rather than hiding it behind an index. `lean` = cheapest credible paid tier per slice; `standard` = the tier with real admin/SSO controls (the fair comparison, since irl.coop ships SSO); `enterprise` = the top published tier or the negotiated figure.

**Seats are scoped per slice** (`slice_scope`): only identity, mail and chat are charged to every member — a co-op does not buy 40 CRM seats. Everything else is counted at the organizer count. Charging all members for all slices would inflate this column by roughly 3×, which is exactly the kind of number that gets a comparison dismissed. A slice with no entry marked for a tier falls back to its cheapest option and is named in the fallback column.

**What the `standard` column is made of:**

| Slice | Vendor | Product | /user/mo | Scope | Seats | /mo | Source |
|---|---|---|---|---|---|---|---|
| chat | Slack | Business+ | $15.00 | members | 40 | $600.00 | usecarly.com 2026 (annual billing) |
| databases | Airtable | Team | $20.00 | organizers | 6 | $120.00 | airtable.com/pricing + support.airtable.com (annual) |
| docs_wiki | Notion | Business | $20.00 | organizers | 6 | $120.00 | notion.com/pricing via review roundup |
| erp_crm | HubSpot | Sales Hub Starter | $15.00 | organizers | 6 | $90.00 | docket.io 2026 HubSpot Sales Hub pricing research |
| identity | Okta | Workforce Identity — Core Essentials | $14.00 | members | 40 | $560.00 | okta.com/pricing |
| mail_calendar_docs | Google | Workspace Business Standard | $14.00 | members | 40 | $560.00 | knowledge.workspace.google.com (annual plan) |
| project_management | Asana | Starter | $10.99 | organizers | 6 | $65.94 | rock.so + gend.co 2026 (annual; asana.com/pricing) |
| telephony | Zoom | Phone — US/Canada Unlimited | $15.50 | organizers | 6 | $93.00 | voipcostsavings.com 2026 |
| video_calls | Zoom | Workplace Business | $18.32 | organizers | 6 | $109.92 | itqlick + trustradius 2026 (annual; $18.33 on trustradius) |
| | | | | | **$2,318.86** | |

#### Mid-tier — fixed fee, per app

| Slice | Vendor | Product | /mo | Credible entry |
|---|---|---|---|---|
| accounting | Intuit | QuickBooks Online Essentials | $85.00 | ✔ selected |
| community | Circle | Professional (entry) | $89.00 | ✔ selected |
| forms_surveys | Typeform | Plus | $50.00 | ✔ selected |
| membership_management | Wild Apricot | Basic (100 contacts) | $53.55 | ✔ selected |
| social_publishing | Buffer | Essentials — 4 channels | $24.00 | ✔ selected |
| websites | Squarespace | Basic | $19.00 | ✔ selected |
| workflow_automation | Zapier | Professional (750 tasks/mo) | $19.99 | ✔ selected |

**$340.54/mo across 7 subscriptions.** The fee is fixed *per app* — that is the mid-tier argument: fixed does not mean one.

The selected entry per slice is marked `mid_tier_pick` in the data, because "cheapest" and "credible" are not the same thing: QuickBooks Simple Start at $38/mo is the cheapest and is not a real accounting setup for a co-op, so Essentials is marked instead. No slice fell back to the default.

#### Usage-metered layers — tickets and map tiles

**Tickets.** Eventbrite Flex: 3.7% + $1.79/ticket + 2.9% per order.

On $4,000.00/mo of ticket revenue (200.0 tickets), the platform fee is **$622.00/mo — 15.6% of the group's own revenue**. irl.coop's platform fee on the same revenue: **$0.00**. Card processing (~2.9% + $0.30) is common to both worlds and excluded.

The sharpest line in the model: a per-ticket fee **grows with the group's success**, while the cost of a shared node does not.

**Map tiles.** At **25,000 map loads/month** (the `scenario.map_loads_monthly` input):

| Vendor | Free allowance | Billable loads | Rate | /mo |
|---|---|---|---|---|
| Mapbox — Web map loads (self-serve) | 50,000 | 0 | $5.00/1k | $0.00 |
| Google — Maps Platform — Dynamic Maps (Essentials SKU) | 10,000 | 15,000 | $7.00/1k | $105.00 |
| irl.coop — self-hosted PMTiles on MinIO | no cap | 25,000 | — | $0.00 |

**At this volume the cheapest commercial option is inside its free tier**, so a co-op comparing on price alone pays $0 either way — while the pricier option here would be $105.00/mo. That makes maps a **terms** argument at this scale, not a cost argument: the tiles cannot be re-priced, rate-limited, or switched off, and there is no card on file. Say the terms, not the money — a claimed saving here is the easiest claim in this whole model to disprove.

#### Storage — measured, not assumed

Measured on the host **2026-09-13** (du -s --block-size=1M on /opt/app/storage, read-only, from the service account): **34.3 GB** under `/opt/app/storage`, of which **11.25 GB is live data** and 23.07 GB is build scratch plus a duplicate — see the findings below.

| Path | GB | Kind | Detail |
|---|---|---|---|
| `/opt/app/storage/data/minio` | 11.18 | live | maps 10.13 (the basemap) + webstudio-assets 1.02 + docs, matrix-media, chat, plane, rag, profiles, postiz, stalwart, formbricks (all under 15 MB each) |
| `/opt/app/storage/geo-data/web` | 0.07 | live | MapLibre embed + self-hosted Noto glyphs |
| `/opt/app/storage/data/cryptpad` | 0.01 | live |  |
| `/opt/app/storage/geo-data/coverage.pmtiles` | 10.13 | scratch | DUPLICATE — byte-identical to the MinIO maps bucket copy, stored twice |
| `/opt/app/storage/geo-data/sources` | 12.93 | scratch | OSM source data for building the basemap — reproducible from the build, not needed at runtime |
| `/opt/app/storage/geo-data/tile_weights.tsv.gz` | 0.01 | scratch |  |

**Findings from the measurement** (each one is a sentence the video can say):

- The basemap exists TWICE (~10 GB each): /opt/app/storage/geo-data/coverage.pmtiles and the MinIO maps bucket. One copy is redundant.
- 12.9 GB is OSM build input (sources/), reproducible from the build and not served at runtime.
- So of 34.3 GB measured, only ~11.3 GB is live data and ~23 GB is build scratch plus a duplicate — roughly two thirds of the data footprint is reclaimable housekeeping, not working storage.
- **Not measured:** /opt/app/storage/data/postgres — mode 0700, uid 999; unreadable from the service account, so it is EXCLUDED and this footprint understates
- Disk: 468 GB, 358 GB used, 87 GB free. The DATA is 34 GB; the DISK is 81% full because container images, source checkouts and build artifacts share the volume — roughly 325 GB beyond /opt/app/storage. Data footprint and platform footprint are different numbers, and only the first one is small.

**Node rate: $0.00217/GB/mo** (hardware ÷ capacity ÷ amortization), so the 11.25 GB of live data costs **$0.02/mo** *(illustrative)*. That disk is *already inside the infrastructure line above* — this is a RATE comparison, and adding it to the totals would be a double count.

| Vendor | Rate | Billable | /mo at the live footprint |
|---|---|---|---|
| Backblaze — B2 — storage | $0.00695/GB | 11.25 GB | $0.08 |
| Cloudflare — R2 — storage | $0.015/GB | 11.25 GB | $0.17 |
| Amazon — S3 Standard — storage | $0.023/GB | 11.25 GB | $0.26 |
| irl.coop — MinIO on the node's disk | $0.00217/GB | 11.25 GB | $0.02 |

**Egress, which is where storage bills actually live** — at 200 GB/mo of transfer:

| Vendor | Free allowance | Billable | Rate | /mo |
|---|---|---|---|---|
| Cloudflare — R2 — internet egress | none | 200.0 GB | $0.00/GB | $0.00 |
| Backblaze — B2 — internet egress | 33.75 GB | 166.25 GB | — | — *rate deliberately unquoted* |
| Amazon — S3 — internet egress | none | 200.0 GB | $0.09/GB | $18.00 |
| irl.coop — the node's own uplink | no cap | 200 GB | — | $0.00 |

**The same bytes as a fixed consumer tier** (sold per account, not per pool):

| Vendor | Tier | Capacity | /mo | Effective |
|---|---|---|---|---|
| Google | One 100 GB | 100 GB | $1.99 | $0.0199/GB |
| Google | One 2 TB | 2,048 GB | $9.99 | $0.00488/GB |
| Dropbox | Plus 2 TB | 2,048 GB | $11.99 | $0.00585/GB |
| Amazon | Drive 2 TB | 2,048 GB | $11.99 | $0.00585/GB |

These are **not** added to the mid-tier column: Google Workspace Business Standard (already counted at $14/user) includes 2 TB pooled storage per user, so adding a Drive subscription on top would double-count it.

#### The irl.coop side

| Line | /mo |
|---|---|
| Infrastructure — node, backups, DNS, amortized hardware | $73.00 *(illustrative)* |
| Third-party the node cannot make free — carrier numbers, etc. | $4.50 *(illustrative)* |
| **Running cost (like-for-like)** | **$77.50** |
| Stewardship — a person's time (**not** infrastructure) | $360.00 *(illustrative)* |
| **Total, honestly stated** | **$437.50** |

- *PSTN DIDs (inbound numbers)* — 3 × $1.50/mo. Wholesale SIP DID rates run roughly $0.50–$2/mo per number. Deliberately per-NUMBER, not per-person: 3 numbers can front an entire group however many volunteers answer them — that shape difference is the actual argument.

Node inflow at the current pricing inputs: **$145.00/mo** *(illustrative)* → +$72.00/mo (198.6% of infrastructure cost covered).

- Groups needed to cover **infrastructure**: 0 extra groups — member contributions alone cover it
- Groups needed to cover **infrastructure + stewardship**: 13 group(s) at $25.00/mo each

Stewardship stays its own line, and third-party costs stay their own line too. A node that "pays for itself" because nobody counts the hours *or* because the phone numbers were quietly left out is not self-sustaining — it is subsidised by a volunteer and a credit card, which is the exact failure mode this platform exists to fix.

#### Comparison at a glance

| | /mo | Basis |
|---|---|---|
| Per-seat stack (`standard`) | $2,318.86 | 3 slices × 40 members + 6 slices × 6 organizers |
| Mid-tier fixed fees | $340.54 | 7 subscriptions |
| Ticketing platform fees | $622.00 | per-ticket, on the group's own revenue |
| Map-tile fees | $0.00 | cheapest option at 25,000 loads/mo |
| Object storage | $0.08 | cheapest vendor at 11.25 GB live — the node's own disk is already inside the infrastructure line |
| Egress | $0.00 | cheapest option at 200 GB/mo |
| **Commercial total** | **$3,281.48** | |
| **irl.coop — infrastructure only** | **$73.00** *(illustrative)* | one shared node |
| **irl.coop — running cost** | **$77.50** | node + the third-party costs it cannot remove |
| **irl.coop — running + stewardship** | **$437.50** | one shared node, the person running it, and the carrier |

Ratio on infrastructure alone: **45×**. On the like-for-like running cost: **42×**. Including stewardship (the honest denominator): **8×**. The commercial total excludes every slice with no verified price, plus local AI, the event bus, and governance — and it *includes* the map-tile line at $0, because at this volume that is the truth.

#### Caveats — say these out loud

A comparison with only one side's asterisks is an advertisement. These are the commercial stack's real advantages and the irl.coop side's real limits; naming them is what makes the rest of the numbers believable.

- **Several vendors discount for nonprofits and co-ops** — Airtable's nonprofit rate is $12/collaborator/mo against a $20 Team list price — a 40% discount. Google and Microsoft both run nonprofit programs. These are list prices, so they are the CEILING of the commercial stack, not the floor. State that on screen: the honest claim is that this is what the software costs at list, and a determined co-op can shave it.
- **The tiers are not feature-equal** — Asana Advanced carries AI and Gantt views; Slack Business+ is a mature product with a support contract. irl.coop's Plane or chat is not Asana Advanced or Slack Business+ feature-for-feature today. The model compares SLICES of capability, not parity. Say so — the argument is about the cost curve and ownership, not about out-featuring a decade of product work.
- **This is one node's cost, and a node is not a datacentre** — The irl.coop side is a single host with a single failure domain. No SLA, no 24/7 on-call, no geographic redundancy. Those are real things the commercial stack buys. Price them in as honest trade-offs rather than leaving a skeptic to point them out.
- **Migration and learning are real costs, and they are not in either column** — Moving a group off five subscriptions costs time — exporting, re-training, re-inviting people. Neither column includes it, so neither should be claimed to win on it.
- **Telephony: the software is free, the phone number is not** — FreeSWITCH + FusionPBX removes the per-seat licence, not the carrier. A DID is rented in every world, and inbound/outbound minutes are metered in almost all of them. The saving is per-seat licensing and the fact that numbers attach to GROUPS rather than people. Say that, rather than 'phone is free now'.
- **Maps, under the free tiers, is not a cost argument at all** — Mapbox gives 50,000 web map loads a month free; Google gives 10,000 per SKU. A small co-op's public map sits inside both allowances and pays $0 either way. The argument there is terms and sovereignty — the tiles cannot be re-priced, rate-limited, or switched off — not money. Claiming a saving would be the easiest thing in this whole model to disprove.
- **Taxes, regulatory fees and card fees sit on top of every per-seat number** — Business VoIP runs ~15-25% above the headline in taxes and regulatory fees; Eventbrite adds card processing on top of its platform fee. None of it is in either column here, so a like-for-like comparison must add it to BOTH sides — the node's carrier minutes are taxed too.
- **Storage: at this volume the money is pennies, and the quota model is the argument** — 11 GB of live data costs $0.26/mo on S3, $0.17 on R2, $0.08 on B2, and about 2 cents on the node's own disk — where the disk is ALREADY paid for inside the infrastructure line. So do not sell this as a monthly saving. The real differences are: one shared pool instead of a per-member quota (40 members = 40 accounts to buy), egress you do not meter, and no capacity tier to move up.
- **Storage: the capacity ceiling is real, and it is in the provider's favour** — Google Workspace Standard pools 2 TB PER USER; Drive and Dropbox sell 2 TB for ~$12/mo. The node has 87 GB free on a 468 GB disk that is already 81% full. Per gigabyte the node wins by 10x; per terabyte of headroom a consumer plan wins. Say both — the co-op's answer is that a co-op's own documents are not 2 TB, and if they become 2 TB that is a disk purchase, not a tier upgrade.
- **Egress is where the storage bill actually lives — and the node's limit is its uplink** — S3 charges $0.09/GB out; R2 charges nothing; the node's disks charge nothing either because the bytes ride the co-op's own connection. But that connection is a domestic or office uplink: a group serving 1 TB/mo of video from a home line will feel it in bandwidth, not in a line item. Self-hosting moves the cost from the invoice to the pipe — it does not delete it.
- **Chain transaction costs are NOT in this model** — Chain = Base mainnet (decided 2026-09-13), so on-chain writes cost real money: deposits, withdrawals, transfers, Tier-2 anchor writes, timelock upkeep, and monthly distribution runs. The node's $73/mo infrastructure line carries no chain cost at all. It is deliberately un-priced rather than guessed — gas has no list price, and a made-up per-transaction figure would discredit the rest of the model. It is also the ONE out-flow that grows as the commons economy works as designed (frequency x groups x members), so it needs a measured rate before it ships.
- **The platform never holds member funds — and that shapes the whole comparison** — Money lives in group Safes; the fiat bridge is a vertical fund that is itself a group; the platform fee is $0.00 and that is CONFIGURED, not merely claimed (hievents.yaml APP_SAAS_STRIPE_APPLICATION_FEE_PERCENT = 0). BYO payment rails were considered and REJECTED on 2026-09-13 because a single account holder breaks governance-controlled finance. Consequence for this model: the group's own money handling is not a line the platform can price, because the platform is not in the path.

#### Derived figures (assumption stated)

- Buffer Essentials — 4 channels (social_publishing) — 4 channels × $6/channel/mo — the channel count is an assumption, stated on screen

#### No direct comparable

- **Local AI / RAG over the group's own docs** — Comparable products bill per seat plus per token, and the documents leave the building.
- **Coop-api — the fleet session gateway + event bus** — This is the part that has no product equivalent at all: the glue that makes one identity and one event stream span every app. It exists nowhere to buy.
- **Group Safe / treasury / governance** — Bank-like and board-like functions sold separately (or not at all) to small organizations.
- **Per-group numbers instead of per-seat lines** — The carriers sell a line per person; the node rents numbers per GROUP and lets one extension ring several volunteers. No per-seat vendor has a product shaped like that, so it cannot be priced — it can only be described.

### At scale — where the per-seat model stops existing

This is the argument the rest of the model builds toward, and it is **structural, not financial**: at exactly the size a volunteer movement reaches, the self-serve product is no longer for sale. A small org rules the attempt out before pricing it because it has already met this wall once, on some other tool.

#### The ceiling table

| Vendor | Self-serve product | Max users | Above it | Price move |
|---|---|---|---|---|
| Microsoft | 365 Business Premium (and every Business-family SKU) | 300 | Microsoft 365 E3 | $22.00 → $39.00 (the upgrade the ceiling forces: +$17/user/mo) |
| Google | Workspace Business Starter / Standard / Plus | 300 | Workspace Enterprise (custom quote) | $14.00 → custom quote |
| Zoom | Workplace Business | 250 | Zoom Enterprise (sales-led) | $18.32 → custom quote |
| Slack | Self-serve plans (Pro / Business+) | 500 | Enterprise Grid (negotiated) | $15.00 → $11.00 (per-seat falls, the bill doesn't: at 10,000 active users $11.00 × 10,000 = $110,000/mo) |
| Airtable | Team / Business (self-serve) | feature-limited | Enterprise Scale (sales-led) | $20.00 → custom quote |
| Okta | Workforce Identity (self-serve suites) | feature-limited | Professional / Enterprise (custom quote) | $14.00 → custom quote |

- **Microsoft** — A HARD ceiling across all Business-family plans, not a guideline. At user 301 the product you were buying does not exist; you migrate to Enterprise. M365 E3 rose $36 to $39 on 2026-07-01.
- **Google** — Purchasable for a maximum of 300 users; Enterprise has no published price.
- **Zoom** — Pricing limited to 1-250 licences. Another ~300 wall, on the video tool.
- **Slack** — Above ~500 active users Enterprise Grid is the route and it is negotiated, not published. Realised: $11.00-13.50/user/mo at 2,000+ active users, $12-15 at 500-2,000. The lowest verified rate is used here on purpose.
- **Airtable** — Self-serve caps by plan features and record limits rather than a user count, then goes sales-led.
- **Okta** — $1,500/yr minimum, then Professional and Enterprise are quoted. Identity is the line nobody budgets for.

Three independent vendors stop selling at ~250-300 users, and a fourth at ~500. That is not a coincidence, it is price discrimination by size: per-seat pricing makes the bill a function of your success, and once the number is big enough to matter the vendor negotiates instead of publishing. The org experiences this as *this is not for me* — long before it experiences it as a bill.

**How seats are counted:** Participation IS the bill: Slack prices Enterprise Grid per MONTHLY ACTIVE USER, and mail/identity price per provisioned account. So a movement's success is its invoice. Seats are split by who genuinely needs each slice — chat and identity for everyone, mail for staff and coordinators, functional tools for a sliver — so the number cannot be dismissed as 'you assumed 10,000 CRM seats'.

#### A volunteer movement — 10,000 participants

25 staff, 9,975 volunteers. Chat and identity for everyone (that is the movement), mail for staff plus coordinators, functional tools for a sliver. Even this narrow allocation is what breaks the per-seat model.

| Slice | Vendor | Product | Rate | Seats | /mo |
|---|---|---|---|---|---|
| identity | Okta | Workforce Identity — Core Essentials (list) | $14.00 | 10,000 | $140,000.00 |
| chat | Slack | Enterprise Grid (2,000+ active users) | $11.00 | 10,000 | $110,000.00 |
| docs_wiki | Notion | Business (list, per member) | $20.00 | 1,500 | $30,000.00 |
| mail_calendar_docs | Microsoft | Office 365 E1 | $10.00 | 1,500 | $15,000.00 |
| | | | | **$295,000.00** | |

**Not priced — no verified rate exists at this volume:** project_management (150 seats). These are sales-led enquiries, not purchases, and they are excluded from the total. The commercial figure below is therefore a **floor**.

**Rate basis — where these figures are bounds, not quotes:**

- **Okta Workforce Identity — Core Essentials (list)** — LIST price. At 10,000 accounts this is a negotiated enterprise agreement, so treat $14 as an upper bound — the commercial column may be lower, never higher.
- **Slack Enterprise Grid (2,000+ active users)** — Low end of the verified realised range — chosen because understating the commercial column is the honest direction.
- **Notion Business (list, per member)** — List price; Enterprise is custom at this volume.
- **Microsoft Office 365 E1** — The cheapest verified enterprise SKU with NO user cap — $10.00/user/mo. The honest floor for mail at 10k+ users, and it is the floor precisely because Business Premium stopped at 300.

| | Commercial | irl.coop node |
|---|---|---|
| Per month | **$295,000.00** | **$2,026.50** |
| Per year | **$3,540,000.00** | **$24,318.00** |
| Per participant / year | $354.00 | $2.43 |
| Ratio | **145.6×** | |

Node side: 3 host(s) at $219.00 + 1.5 TB egress at $7.50 + 40 hrs/mo of stewardship at $1,800.00.

#### A national movement — 50,000 participants

60 staff, 49,940 volunteers. Moderation at this size is a staffed function, not a hobby — the honest binding constraint is coordination labour, not compute.

| Slice | Vendor | Product | Rate | Seats | /mo |
|---|---|---|---|---|---|
| identity | Okta | Workforce Identity — Core Essentials (list) | $14.00 | 50,000 | $700,000.00 |
| chat | Slack | Enterprise Grid (2,000+ active users) | $11.00 | 50,000 | $550,000.00 |
| docs_wiki | Notion | Business (list, per member) | $20.00 | 6,000 | $120,000.00 |
| mail_calendar_docs | Microsoft | Office 365 E1 | $10.00 | 6,000 | $60,000.00 |
| | | | | **$1,430,000.00** | |

**Not priced — no verified rate exists at this volume:** project_management (400 seats). These are sales-led enquiries, not purchases, and they are excluded from the total. The commercial figure below is therefore a **floor**.

**Rate basis — where these figures are bounds, not quotes:**

- **Okta Workforce Identity — Core Essentials (list)** — LIST price. At 10,000 accounts this is a negotiated enterprise agreement, so treat $14 as an upper bound — the commercial column may be lower, never higher.
- **Slack Enterprise Grid (2,000+ active users)** — Low end of the verified realised range — chosen because understating the commercial column is the honest direction.
- **Notion Business (list, per member)** — List price; Enterprise is custom at this volume.
- **Microsoft Office 365 E1** — The cheapest verified enterprise SKU with NO user cap — $10.00/user/mo. The honest floor for mail at 10k+ users, and it is the floor precisely because Business Premium stopped at 300.

| | Commercial | irl.coop node |
|---|---|---|
| Per month | **$1,430,000.00** | **$6,024.00** |
| Per year | **$17,160,000.00** | **$72,288.00** |
| Per participant / year | $343.20 | $1.45 |
| Ratio | **237.4×** | |

Node side: 8 host(s) at $584.00 + 8.0 TB egress at $40.00 + 120 hrs/mo of stewardship at $5,400.00.

#### Before anyone in the audience says it: the nonprofit programs

- **Google** — Workspace for Nonprofits — free Nonprofit edition for eligible organizations; paid tiers from ~$3/user/mo. This is the STRONGEST counter-argument to the thesis and it must be stated before an audience raises it. It meaningfully lowers the commercial column for a registered 501(c)(3). Two limits keep it from dissolving the argument: eligibility is organisational (a loose movement may not qualify), and these programs cover STAFF ACCOUNTS — they do not cover 10,000 volunteer participants.
- **Airtable** — Nonprofit rate $12/collaborator/mo vs $20 Team list. A 40% discount on one slice — real, and still per-collaborator.
- **Microsoft** — Nonprofit grants and discounts on M365. Broadly known to exist; deliberately NOT priced in this model because no verified rate was captured. Do not quote a number for it — cite the program and tell the org to check eligibility.

These are real and they must be conceded on camera **before** the argument, not after. They lower the commercial column for a registered charity. Two limits keep them from dissolving the point: eligibility is organisational (a movement may not qualify), and the programs cover **staff accounts** — they do not cover 10,000 volunteer participants.

#### What a movement actually does instead

The realistic alternative is not 'pay $2.5M/yr' — it is Discord, WhatsApp, Facebook Groups, a Google Group and a spreadsheet. Those ARE free at scale, because somebody else's business model pays for them. That is the honest competitor, and it sharpens the argument rather than weakening it: the choice for a small org is between a funder-backed extractive platform and somebody else's free platform that it does not govern and cannot export from. A movement that wants neither currently has nothing — which is the gap.

**The honest limits of the node at this scale** — state all of them, because a skeptic will otherwise do it for you:

- **This is not one box.** The host count above is an estimate, not a measured capacity claim; 10,000 Matrix accounts and 10,000 mailboxes need a real topology, and mail needs deliverability work (shared-IP reputation, blocklists, SPF/DKIM/DMARC discipline) that a commercial provider absorbs for you.
- **The binding constraint is coordination labour, not compute.** Stewardship is the largest line in every node column above. At 50,000 participants moderation is a staffed function. The platform makes the software free; it does not make the moderating free — what it does is make the *decision* to staff it, rather than the *bill* for it.
- **Egress is priced as an assumption.** At $5.0/TB it looks trivial; on a domestic line it is unmetered and invisible, which means the cost is real and simply not invoiced. Set it to 0 to model the domestic case and say so.

### The federation — nodes that carry infrastructure for each other

*Scope: the ECONOMICS and the incentive design. The DNS/edge topology for surviving a takedown stays parked (`AGENTS.md`) and nothing here requires deciding it.*

This is not a new mechanism. event-bus-and-group-shapes.md §7 and the commons economy digest already settled: cost is PUBLIC, payment is private-but-provable, and contribution shows as a COVERAGE PROOF with a subsidy gradient (free-rider → covers-self → subsidizer). Running a node is simply the IN-KIND form of the same proof: 'I covered ≥X% of the platform cost by hosting it.' The cost model built here is what makes that proof possible — you cannot publish a cost you have not measured.

#### What a node costs, and what it carries

| Tier | Node | Runs | Hardware | Storage | Labour | Total /mo |
|---|---|---|---|---|---|---|
| B | Edge node — the honest entry point | 5 apps | $6.00 | 11.25 GB | 1 hr | **$51.00** |
| C | Service node — one pillar for everyone | 12 apps | $18.00 | 51.25 GB | 3 hrs | **$153.00** |
| A | Steward node — a full instance | 37 apps | $73.00 | 36.25 GB | 8 hrs | **$433.00** |

*Totals include labour at $45.00/hr; the on-ramp below quotes cash only. Note what that does to the cheapest node: an edge node is $6.00 of hardware and $45.00 of somebody's attention — **even the smallest node is labour-dominated by roughly 8×.** That is the real argument for tiering the on-ramp, and it is why the entry point must be ~1 hour, not 'a weekend'.

- **Edge node — the honest entry point** — Serves the shared assets — basemap tiles, fonts, static JS — for every group in its region, and holds a full replica of the federation's shared data. *It is the smallest thing that is genuinely useful, and it targets the biggest byte volume in the system. A Raspberry Pi on a connection the org already pays for, or a $6/mo VPS.*
- **Service node — one pillar for everyone** — Absorbs a whole workload for the federation: the node that moves bytes for everyone else's media, or the one that runs the jobs nobody wants on their laptop. *The natural second step: same skills as the edge node, real offload.*
- **Steward node — a full instance** — Everything: its own groups' services, plus the shared assets and whatever pillars it volunteers to carry for the federation. *This is what a member org graduates to — and what this host is today. It is the only tier that needs a person who can read a log.*

#### Redundancy is nearly free — that is the whole argument

On owned hardware, redundancy is nearly free. That is the whole argument, and it is arithmetic rather than aspiration: the same object costs $0.23/GB/mo on S3 and $0.00217/GB/mo on a disk the org already bought.

| Nodes holding the assets | Federation storage | Node cost /mo | Resilience | Serving |
|---|---|---|---|---|
| 1 | 11.25 GB | $0.02 | no redundancy — one loss is an outage | 1× |
| 3 | 33.75 GB | $0.07 | survives any single loss; rolling upgrades possible | 3× |
| 10 | 112.5 GB | $0.24 | survives multiple losses; each region served locally | 10× |

Each 11.25 GB replica costs **$0.02/mo** on hardware the org has already bought — it is idle disk, not a purchase. The same three replicas on S3 would be **$0.78/mo** ($0.023/GB). The federation's redundancy is not funded; it is the by-product of nodes existing.

Three independent nodes holding the shared assets. Below that, the loss of one node is a visible outage; at three, any single loss is invisible and a rolling upgrade is possible without downtime.

#### Why an org would run one — the incentive, stated as the design already states it

**What the org gets:**

- No per-seat cost for its own people — the reason it is reading this model at all.
- Its data on hardware it controls, exportable, with no per-member storage ceiling.
- A governance seat: node operators are the ones who can actually hold the platform accountable.
- Reciprocal hosting — it stops depending on one host and one person.
- An in-kind coverage proof it can show instead of money: cheaper than a subscription and visibly concrete.

**What the federation gets:**

- Serving capacity multiplies: N nodes serve N times the bytes with no egress invoice.
- N replicas of the shared assets instead of one — redundancy bought with idle disk.
- Geographic locality: the basemap and media served from near the people using them.
- Failure stops being existential: no single host, no single steward, no single bill.

**The proof extension (no new mechanism invented):** Contribution in kind is the same credential as contribution in money once the cost is published: "hosted ≥1 node (≥X% of platform cost)" sits on the same gradient as "covered ≥ 100%". No new mechanism, no token, no scoreboard — the settled coverage proof, extended from money to hosting.

#### The on-ramp — nobody is asked to run a whole stack first

| Phase | What the org takes on | Setup work | Ongoing | Unlocks |
|---|---|---|---|---|
| 1 | An edge node | ~1 hour, once | ~$6/mo or a Pi on the existing connection | Its region's map tiles + a full replica of shared assets |
| 2 | An edge node + shared backups | ~1 hour to set a remote target | $0 marginal (idle disk) | Another node's backups no longer live on the node they protect |
| 3 | A service pillar | an afternoon, then 3 hrs/mo | ~$18/mo | A whole workload lifted off every other node |
| 4 | A steward node (own instance) | a weekend, then 8 hrs/mo | ~$77/mo + labour | Sovereign services for its own groups, plus federation pillars it volunteers for |

#### Which pillars can actually be federated — read from the stack, not assumed

The federation's trust model was briefly justified with 'all the data is encrypted'. That is not true yet, and the distinction matters more than the fact: encryption AT REST with an operator-held key does NOT make hosting someone else's data acceptable — the operator has the key. Only end-to-end encryption, where the node never holds the key, delivers 'I don't mind a node hosting my data'.

| Tier | Encrypted with | Protects against | Operator can still read? |
|---|---|---|---|
| 1 — At rest, operator holds the key | LUKS, MinIO SSE-KMS, Postgres PGE | a stolen disk, an improperly decommissioned drive | yes |
| 2 — Application-level, platform holds the key | encrypted columns, encrypted blobs with a platform master key | a compromised backup target, a database dump in transit | yes |
| 3 — End-to-end, the user holds the key | Matrix E2EE room bodies, CryptPad, the group secret vault's k-of-n shares | the operator, the host, and a seized disk alike | **no** |

| Pillar | Encrypted today | Federation-safe | Federation target |
|---|---|---|---|
| Object store (MinIO): docs, mail blobs, media, avatars, webstudio assets | **no** | **no — trusted node required** | Client-side AES-GCM before PUT; node holds ciphertext only. Cheapest and largest win — it covers files, media, attachments, avatars. |
| Postgres / Citus rows — seats, memberships, events, tickets, ledgers | **no** | **no — trusted node required** | Split: non-sensitive stays; sensitive -> commitments (group-scoping tier 2, already designed) + blind indexes where equality search must survive. |
| Chat — E2EE room message bodies | yes | yes | Force E2EE on group rooms; client-side encrypt attachments. Metadata is the residual, not the message body. |
| CryptPad documents | yes | yes | None needed — this is the federation-safe document path. Use it in place of OnlyOffice for docs hosted by another org's node. |
| Group secret vault | yes | yes | None needed structurally — but the CODE does not match the design yet: apps/coop-api/src/vault.ts:42 encrypts with a platform-held pgp_sym key. Replace with the designed client-side SSS envelope. |
| Documents (OnlyOffice via the docs panel) | **no** | **no — trusted node required** | No cryptographic fix keeps collaborative editing working. Either move these docs to the owning group's own node, or use CryptPad. |
| Mail (Stalwart) | **no** | **no — trusted node required** | No honest full fix. Trusted node, or mail local to the owning group's node. PGP/S-MIME is a per-user opt-in that costs server-side search and most clients. |
| Maps / static shared assets | n/a — public | yes | None — public by design, which is why federation phase 1 costs nothing. |
| Treasuries | yes | yes | None — ZK commitments on-chain already. |

The full fix design — threat model, envelope encryption, erasure-coded sharding, canaries, the client-integrity problem, and what cannot be solved — is `docs/design/federation-encryption-and-access.md`.

- *Chat — E2EE room message bodies:* message BODIES only. Room metadata, membership, and media in non-E2EE rooms are not covered.

**The design consequence.** Federation can distribute STATIC assets and E2E content today: maps, static JS/glyphs, chat bodies, CryptPad, vault shares, treasury state. Distributing MAIL, DOCS or DATABASE ROWS to a node you do not trust needs either (a) end-to-end encryption for those layers — structurally hard for mail and for collaborative documents — or (b) the honest admission that a node carrying them is a TRUSTED node. Option (b) is fine and probably right for a co-op federation of known orgs; it just has to be a stated property, not an assumed one.

**What would have to change to make the stronger claim true:**

- Enrol MinIO in SSE-KMS with a key each node holds separately — moves the object store from tier 1 to ‘no’ on custody, because the node still holds the key. Necessary for disk theft, insufficient for federation trust.
- Encrypt Postgres at rest (tier 1, same limitation) or move group-scoped secrets to commitments (tier 3 — already designed for membership; not for event/ticket rows).
- For mail: accept it as a trusted-node pillar, OR ship client-side PGP/S-MIME and give up server-side search. There is no third option that keeps a normal mail client working.
- For documents: keep them on the owning group's own node, or accept a trusted node. Collaborative editing is not end-to-end-encryptable without going back to a CRDT-in-the-client design.

#### Two adversary classes are universal — so their answer is universal too

TWO CLASSES ARE UNIVERSAL, so the answer to them is universal — and that is the finding that matters: the state is a permanent constraint (it cannot be opted out of, it can compel third parties, it rewrites its own rules, it can act unseen) and internal tensions apply to every group of every size. Together they force one rule: THE PLATFORM CAN NEVER BE THE TRUST ANCHOR, because the state can compel it. That makes the whole encryption design the floor for every sector — including a food co-op whose data is public but whose platform must still not be a compellable concentration point. Sectors are then MODIFIERS on that core, not separate threat models, and the two classes vary along different axes: internal tensions scale with SIZE and structure; external adversaries scale with POLITICS and activity. Full analysis, including the eight invariant internal tensions (leaving member, over-permission, future self, operator, platform steward, the FOUNDER, the coerced member, the wronged member), the four modes the state can take (hostile / indifferent / gatekeeper / dependency), and the sector rows: adversary-models-and-sector-fit.md.

**The state, in the four modes it actually takes** — the wrong answer differs per mode, and confusing them produces the wrong primitive:

| Mode of the state | The answer | Primitive |
|---|---|---|
| **Hostile / targeted** | Minimisation — nothing to seize, nothing to name | client-side encryption, non-enumeration, erasure sharding |
| **Indifferent** | Nothing. This is where encryption theatre lives. | none — and saying so is the honest move |
| **Gatekeeper** | Selective disclosure — prove compliance without revealing the data | selective-disclosure proofs (zk-badges, coverage proofs, commitments) |
| **Dependency** | Provable compliance, kept separate from member data | proofs + separation of compliance records from member records |
| **Instrument (steered)** | Contest capability — prove your own account of events, fast, without disclosing everything. No amount of good intent substitutes for having the evidence already. | tamper-evident custody logs + commitments (commit now, reveal later, selectively) |

**The eight internal tensions that apply to every group, at every size:**

| Tension | Why it is universal | Lever |
|---|---|---|
| **The leaving member** | every group has departures; E2EE cannot retroactively un-share | epoch keys |
| **The over-permissioned member** | access accumulates; roles drift | least privilege, per-object access, no bulk export by default |
| **The group's future self** | every group eventually has contested succession or a faction | constitutional vs ordinary governance; timelocks |
| **The operator and the platform steward** | whoever runs the box and ships the code | client-side keys; the platform never holds a DEK |
| **The founder** | holds every key, knows every password, won't leave or leaves badly | handover as a documented procedure; keys held by a threshold, never by a person |
| **The coerced member** | any member can be pressured; only the probability is sector-specific | deniability, compartmentalization, no single person holding everything |
| **The nested boundary** | any group with sub-groups has a parent/child visibility question | separate DEKs per compartment; no inherited visibility |
| **The wronged member / interested party** | someone with a stake in an outcome is also someone with access | recusal as a governance primitive; conflict-of-interest records in the governance axis |

The founder is the same adversary as the node steward's burnout, one level down: a single person as the trust boundary. 'Require a named second person per node' is the group-level mitigation too — one feature, not two.

**Why this collapses the sequencing problem.** Internal tensions vary with *size and structure*; external adversaries vary with *politics and activity*. Because both universal classes are already present for every group, the core is buildable now without choosing pilots:

- The vault fix — custodial → non-custodial (a platform-held key defeats every mode)
- Non-enumeration as a first-class property (group-scoping §3 tier 2 — designed, deferred, now promoted)
- Selective-disclosure proofs (the gatekeeper-state answer; one family unblocks unions, funders, alt-health, credit unions)
- Contest readiness — commit now, reveal later, WITH ITS SUBSTRATE: the counter-signed CUSTODY CHAIN (docs/design/custody-chain-and-contest-kit.md). Every group can be falsely accused, so an evidence-ready, tamper-evident record of your own events is a universal capability — and a contest claim without the chain behind it is only a promise. Turns the 'cannot be exculpated' trade into a non-choice: provable without being readable.
- Epoch keys (the leaving member is universal, not a corner case)

Sector choice then only decides which **mode** ships next:

- Compartmented mode — unions in formation, community safety, peer support (highest value: its absence is a safety problem)
- Deniable mode — rave, subculture, hostile jurisdictions, entheogenic
- Open mode — deliberately ABSENT privacy machinery, so the platform stops reading as a surveillance product to groups that need none

**The economic adversaries** — the class the first version of this analysis lacked, and the one a food coalition actually faces. An economic adversary behaves nothing like a state or a hacker:

| # | Adversary | Capability | How it wins |
|---|---|---|---|
| E15 | **The corporate incumbent** | outspends you by orders of magnitude; can buy your distributor, processor, landlord or certifier; can price below cost until you fold; can litigate to exhaust you | reads your footprint — supply chain, land pipeline, volumes, membership, capital plan — and interdicts the weakest link before you reach scale |
| E16 | **The chokepoint holder (distributor, co-packer, certifier, lender, landlord, insurer)** | sits between you and the market; is not a member; is often acquirable or pressure-able | sees the whole network by virtue of its position |
| E17 | **The asset speculator** | reads public land records, outbids, holds, waits | buys the land under the farms the co-op depends on and sets the rent |
| E18 | **The identity-based violent actor (three domains at once)** | PHYSICAL harm to people, property, crops, water; INFORMATIONAL attacks — planted negative coverage, rumours, manufactured scandal; SUPPLY-CHAIN sabotage — contaminated inputs, spoiled storage, tampered equipment | the group is discredited, shut down or displaced. The incident IS the attack: a contamination event destroys a food business permanently even when the sabotage is later proven |

**Adversaries converge without coordinating.** The chain neither adversary has to plan:

`subtle sabotage → food-safety incident → regulatory action → market vacancy the incumbent fills`

- The incident IS the attack — the reputational damage persists even when the sabotage is proven, so detection is not the goal, contestability is.
- The state can be recruited as an unwitting step (the Instrument mode) — a plausible complaint enlists an inspector at no cost to the adversary.
- The weakest link is whoever has the least to lose — often a counterparty, not a member.

#### Contest readiness — the capability the sabotage case forces

The analysis assumed the problem is BEING READ. This adds the opposite: BEING ACCUSED. Same primitive family, used in the other direction.

| Mode | Question it answers | Consumers |
|---|---|---|
| **Selective disclosure (positive)** | how are we doing? | certifiers, funders, regulators, members |
| **Contest readiness (defensive)** | what actually happened, and who held custody? | an inspector, a court, an insurer, the press |

Both are commitments + proofs + tamper-evident logs + selective reveal. Together they RESOLVE the 'cannot be exculpated' trade: the false choice was between unreadable and able-to-prove; the answer is COMMIT NOW, REVEAL LATER, SELECTIVELY — provable without being readable, with the group choosing when and to whom.

- Signed custody chain (who signed for what, when) — the hash-chained ledger tier applied to GOODS instead of credits
- Counter-signed receipts between counterparties — a disputed delivery carries two signatures, neither alterable alone
- Anchored records — periodic anchors to an external witness, so a later 'the log was edited' claim is checkable
- An incident log shaped as evidence (timestamps, custody, signatures, no retroactive edits) — it will be read by an insurer, a regulator or a court

This flips §5.9: the traceability records a certified operation is OBLIGED to keep become its DEFENCE KIT — provided they are the co-op's own and tamper-evident, not only in the certifier's file.

**What it cannot do:** Stop a lie. The platform can own a channel, pre-position signed/dated statements of fact (so a smear meets verifiable priors instead of a vacuum), and produce evidence fast. Selling reputation defence as a technical guarantee would be the same dishonesty as selling disk encryption as protection from the operator.

#### The custody chain — the substrate a contest claim stands on

Append-only, hash-chained, COUNTER-SIGNED log of custody events for physical goods — the Tier-2 ledger substrate (off-chain, hash-chained) applied to GOODS moving instead of people contributing. A Tier-2 SIBLING, not a fourth ledger.

Contest readiness without a tamper-evident record is just a promise. The incident IS the attack, so the group must be able to answer 'what did you receive, from whom, when, and who had custody' precisely and verifiably — often before it gets a chance to explain, because the demand arrived via the state's INSTRUMENT mode after someone else's complaint.

**The trick that keeps it compatible with the footprint axis:** The chain is PUBLICLY VERIFIABLE and PRIVATELY READABLE: record commitments and chain links are publishable/anchored; record content (parties, quantity, conditions) is encrypted to the parties; a disclosure reveals ONE record plus its inclusion proof against an anchored root — not the chain. So it proves facts about the past while keeping the network illegible, which EXTENDS the footprint axis rather than undermining it.

**Anchoring:** Periodic Merkle roots anchored outside the operator's control (the Base/Safe stack, optionally co-signed by member devices). An operator who stops anchoring is VISIBLE — a liveness limit you can see, which is the point.

**Why third parties must sign too:** Self-signed records prove only that the group is consistent with itself. Third parties sign their OWN records into the chain — an inspector, a lab, a buyer — so a claim is backed by someone with no incentive to lie for the group. This is also what makes the certification burden pay off twice: the traceability records a certified operation must keep become its defence kit.

| Proves | Does **not** prove |
|---|---|
| a record existed at a time and has not been altered since (with an anchor) | that the goods were what the record says — A SIGNED LIE IS STILL A LIE |
| both parties agreed to a transfer | that either party was honest or uncoerced at signing |
| the order of custody, and where a chain demonstrably broke | that nothing happened off-chain |
| that a named third party attested a fact | that the attestation was correct |

**The false claim to avoid:** 'we can prove our food is safe'. The true claim is narrower and better: 'we can prove our records are real, and show exactly where custody was held if something goes wrong.'

**Where it earns its keep:**

- Inputs and produce — the sabotage case: prove custody held, seals intact, and the break point
- Seed provenance — a SIGNED LINEAGE proves a seed line's origin without publishing the exchange network (the no-GMO / no-commercial-input coalition's exact need)
- Cash and treasury in transit; tools and equipment loans; medicine and herbal preparations
- Incident logs — evidence-shaped records of contamination, theft or damage for insurers and regulators
- Federation-level: a node's own custody handovers (backups, erasure shares, key ceremonies) get the same treatment for free

**Work item** — build #4 in the universal core, as the substrate for contest readiness:

1. Record type + hash-chain substrate (reuse the Tier-2 mechanism — small, the shape exists)
2. Counter-signature flow, with append-a-correction rather than edit
3. Encrypted content + commitment structure (same per-group DEK and selective-reveal machinery)
4. Anchoring — periodic roots to Base, optional member co-signature
5. Third-party signing (inspector/lab/buyer) — a UX problem more than a crypto one

*OFF by default, per group. A two-person tool library does not need a custody chain; a farming coalition with certified inputs and a sabotage risk does.*

**Open decisions:**

- Who hosts the chain — the group's own node (operator can drop records; detectable via anchors, not preventable) or sharded/replicated across the federation (cheap at this data size, removes the single-custodian rewrite risk)?
- Anchor cadence and who pays (batch to Base; group or federation subsidy)
- Who may counter-sign, and what happens when a counterparty REFUSES — the design should allow a one-sided record marked UNCOUNTER-SIGNED rather than silently missing
- The platform never holds the plaintext — same rule as the vault; the group operates the chain, the platform is an optional relay

#### Footprint — the third axis, orthogonal to mode

Mode and footprint are ORTHOGONAL, chosen independently. Mode governs how members and content are protected; footprint governs how legible the organisation is to an outsider. A food hub wants a PUBLISHED front and an UNREADABLE back. The footprint applies to the PROJECTION, never the store of record: a Published front is rendered from the encrypted back and stays sparse by construction. This is the correction to the first version of the analysis, which filed food co-ops under Open mode and conflated a public storefront with a public organisation. Rule of thumb: 'the data is public' is almost never true of an organisation — only of its projection.

| Footprint | What an outsider can reconstruct | Who needs it |
|---|---|---|
| **Published** | the deliberately sparse front: offerings, hours, contact | retail-facing co-ops, public events |
| **Sparse** | existence and rough purpose; nothing that maps the network | most operational groups, food hubs |
| **Unreadable** | not even a reliable count | identity-threatened coalitions, supply-chain organisers, hostile jurisdictions |

Illegibility is ATTACK-SURFACE REDUCTION, not only disclosure control: if an outsider cannot see who supplies what, they cannot choose the highest-leverage node to attack. A coalition with an unreadable supply chain is harder to interdict AND harder to discredit by proxy — a second, independent argument for the footprint axis.

Food co-ops are NOT Open mode. The incumbent is an economic adversary (E15) that can pick a smaller coalition apart link by link, and at scale a coalition DISRUPTS the status quo in a way that invites adversarial behaviour — even for food. Three sub-cases need different profiles: the adoption/disruption co-op (Sparse or Unreadable footprint), the identity-threatened coalition (e.g. Somali, Latino, Black farmers organising together — Unreadable, with non-enumeration as a SAFETY property and per-member exposure tiers because the group is not one perimeter), and the input-refusers (the certification conflict). Two principles fall out: (1) NO SINGLE COUNTERPARTY MAY RECONSTRUCT THE COALITION — anti-correlation across the certifier, lender and distributor, because each is acquirable; shard the VIEW, not just the storage; (2) the CERTIFIER IS A PRIVACY DECISION — a private accredited certifier holds traceability records privately, a state program is a public agency whose records may be obtainable by anyone who files.

#### The certification conflict — the second gatekeeper pattern

Certified organic production is legally required to be traceable — the food-sector twin of the union's statutory record duty, and the second instance of the gatekeeper pattern. The map a coalition wants illegible is the map it is obliged to document.

- **7 CFR Part 205 (National Organic Program):** 'Fully disclose all activities and transactions of the certified operation, in sufficient detail as to be readily understood and audited'; records must span purchase/acquisition through production to sale or transport, and be traceable back to the last certified operation.
- **In practice:** ~5-year retention, annual inspection including a TRACEBACK exercise (finished product back to each ingredient) and a MASS-BALANCE exercise (quantities reconcile).
- **The answer:** Selective disclosure: prove traceability TO THE CERTIFIER without the map being readable by anyone else who can obtain it.
- **Actionable:** The choice of certifier is a privacy decision — private accredited certifier vs state program (public agency, records obtainable). Put it in the onboarding flow.

#### The chilling effect — the harm that lands before any adversary acts

The primary harm happens BEFORE any adversary acts. A group that anticipates them changes what it does, so the leak never has to occur for the damage to be done — THE EXPECTATION IS THE MECHANISM.

> *You don't have to be doing something morally wrong to be afraid. You just have to know you're up against systemic challenges, or a larger status quo poised against your direction — which is usually anti-cooperation and pro-monopolistic-capital. (Robbie, 2026-09-13)*

IT REQUIRES NO CONSPIRACY. Nothing in it claims anyone is out to get you — the threat is a GRADIENT, the default direction of the environment, and a gradient needs no villain to run one way. That is its rhetorical AND evidentiary strength: you never have to prove intent, so an audience that resists the word 'villain' has nothing to argue with. It also REMOVES THE SHAME: organizers read their own caution as being secretive, when the correct reading is declining to hand an advantage to someone who already has one.

- *"You're not hiding something wrong. You're declining to hand over an advantage."*
- *"Privacy isn't a confession. It's a negotiating position."*
- *"The 'nothing to hide' answer is only available to people already swimming with the current."*

A claim about fear would normally be unfalsifiable — which is why the cost model, the 300-user wall and this analysis matter. They are not primarily about money or features: THEY ARE EVIDENCE THAT THE CURRENT RUNS ONE WAY. V9 is not a pricing video; it is a proof of the gradient.

**The mechanics of the current — each a property of how the market is arranged, not an act by anyone:**

| The default | What it does to a coalition |
|---|---|
| **Scale is priced — cost tracks headcount** | growth is punished by unit economics, precisely when the group is gaining leverage |
| **Self-serve ends at ~300 users** | the moment you're big enough to matter you're in a procurement process you have no staff for |
| **Legibility is a requirement, not an option** | every tool wants a roster, a real name, a phone number — the group's shape is the entry price |
| **Continuity is rented** | records, history and admin rights live in someone else's account |
| **Exit is expensive** | export is partial, migration is manual, and switching cost rises with use — hostage value grows |
| **The free tier is someone else's business model** | free at scale because a third party's incentives pay for it |
| **Deplatforming is a business decision** | an availability attack with no appeal, and no court to appeal it to |

NO STEP IN THAT LIST REQUIRES ANYBODY TO WISH A CO-OP HARM. That is the whole point — and it is why the argument is unanswerable.

**The response — deliberate inversions:**

| The default (the gradient) | The inversion irl.coop makes |
|---|---|
| Price scales with headcount → growth is punished | fixed infrastructure cost → participation is free at the margin |
| Self-serve ends at 300 users → sales-led procurement | no user ceiling at all |
| The vendor holds your data on the vendor's terms | client-side keys; operator-blind storage |
| A single vendor is a single point to buy, ban or re-price | federated nodes; exportable; open source |
| Membership is visible to the platform and to each other | roster-less membership is possible |
| Records live in a vendor account and die with people | group-held encrypted archive with succession |
| The platform decides who may act | the group's own governance decides |
| Someone else's business model pays for free | the group's own contributions cover the cost, publicly |

If the environment is adversarially defaulted toward concentration, the platform's job is structural counter-weighting. EVERY DESIGN CHOICE HERE IS THE INVERSE OF A DEFAULT — which makes the cooperative identity the ENGINEERING SPEC, not a moral flourish.

**How this changes the telling:**

1. Never allege a villain — show the shape. More persuasive, and also TRUE: libel-proof and impossible to rebut with 'who, exactly?'
2. Name the asymmetry, not the actor. 'The menu ends at 300 users' is checkable; 'they don't want you to grow' is not.
3. Use the numbers as evidence of the GRADIENT, not just the bill — the cost model's job is to make an unfalsifiable fear falsifiable.
4. Present every mitigation as an INVERSION: here's the default, here's what we did instead.
5. Close on the identity claim: cooperation is a deliberate counter-current — not sentiment, it is the reason the architecture looks the way it does.

**The series spine — every episode measures the same gradient:**

- **V9** — the menu ends at 300 users — growth is punished at the moment it would matter
- **V3/V8** — scale is priced; the free tier is someone else's business model
- **V11** — legibility is the entry price — so groups self-censor before anyone acts
- **V4** — continuity is rented, and a vendor can be bought or ban you
- **V2** — exit is expensive, so the switching cost grows with use

**The tells — say these verbatim; recognition is the whole game:**

- *"let's talk about that in person"*
- *"don't put that in the chat"*
- *"who else knows?"*
- *"let's not put it in writing"*
- *"a group chat named after something innocuous"*
- *"screenshots quietly forbidden"*
- *"no minutes, no member list, no written plan — on purpose"*
- *"a second phone, a second number"*
- *"recruiting by whisper: 'I know someone'"*
- *"deliberately staying small"*
- *"'we'll deal with that later'"*

Being unrecorded feels like safety and functions as AMNESIA: no institutional memory, no proof a decision was made, no onboarding path, nothing to contest with, no case for a funder, no succession, no leverage. The fear buys safety and pays in capability — a trade almost never named out loud.

**The loop:** fear of the adversary -> nothing written down -> nothing provable -> no funding, no growth, no leverage -> fragility -> more fear

BREAK IT AT 'nothing written down' — the cheapest link, and the only one the platform controls. Everything else in the design is downstream of that choice.

| The fear | What it makes organizers do | What irl.coop does | The honest limit |
|---|---|---|---|
| If I write it down, it can be seized or leaked | nothing written; strategy stays verbal | client-side encryption at rest; operator-blind storage | a DEVICE seized with the key still yields plaintext — device policy is the member's |
| If we recruit openly, the list gets out | whisper recruiting; no public invitation | roster-less membership — provable, not enumerable | someone already in the room can still talk |
| If our people are identifiable, they're targets | the most vulnerable never join; allies excluded | pseudonymous seats; commitment membership; per-pair visibility | physical security is not something the platform can provide |
| If we're the visible face, we'll be attacked | no public voice, no spokesperson | a published front, unreadable back — sparse projection | a lie can still be told about you |
| If we keep records, they'll be used against us | no minutes, no votes, no audit trail | tamper-evident records + contest readiness | A SIGNED LIE IS STILL A LIE |
| If we take money, we'll owe someone | cash in a drawer; no treasury, no grants | private-but-provable treasury; coverage proofs | cash still exists, and so do the people who want control of it |
| If we get big, we can't manage it | deliberately staying small | no per-seat cost curve; modes that scale | coordination labour is real — the platform doesn't do the moderating |
| If we use one tool, we're dependent | five tools, five lists, no memory | exportable data; self-hostable; federated nodes | migration is work, and the first one is the hardest |
| Nobody will understand our way of working | the rules live in people's heads | shapes: roles, config, governance encoded per group | it is still people — the software only holds the rules |

**The comparison rule:** SIGNAL IS EXCELLENT AND WE DO NOT BEAT IT AT MESSAGING. Any claim otherwise is false on its face. The argument is not 'our chat is more private' — it is 'those are messaging tools; you are trying to be an ORGANISATION.'

| Tool | Genuinely good at | What it cannot give you | The honest catch |
|---|---|---|---|
| **Signal** | best-in-class E2EE messaging; open source; battle-tested; minimal metadata; free | roster-less membership; an archive that survives a lost phone (by design); a verifiable vote; any proof to an outsider; succession; reach without a phone number; integration | A Signal group is a CONVERSATION. The moment you need an organisation, you are using a filing cabinet made of chat |
| **WhatsApp** | reach — in much of the world everyone already has it; E2EE content; broadcast | hidden membership; escape from Meta's address-book and metadata graph; immunity from ToS enforcement; structured export; any governance | The RELATIONSHIPS are the dataset, not the messages |
| **Discord** | community features, voice, events, moderation tooling — good UX at scale | E2EE in practice; hiding anything from the platform or admins; survival of a ToS ban; guaranteed export | a well-run SURVEILLANCE-FRIENDLY community platform. Fine for a public community, poor for a threatened one |
| **SMS** | universal; no app; works for members with no smartphone | any privacy at all — plaintext, carrier-retained, trivially obtained | use it for logistics, never for anything that matters |
| **Facebook Groups** | reach and familiarity | everything above | the group is Meta's asset |

**The five gaps — what NO chat tool can do:**

1. Membership without exposure — there is NO roster-less membership in any of them; being in the group means every other member and usually the platform sees you
2. Decisions that are records — no quorum, no recusal, no ratification, no verifiable tally, no provable minutes. SCREENSHOTS ARE NOT GOVERNANCE
3. Continuity across people — history lives on devices, administration lives with whoever created the group, and there is no succession
4. Facts you can prove to an outsider — dues, attendance, a vote, a delivery, a safety record: impossible from chat, for you AND against you
5. One identity across the work — five silos means five invitations, five member lists, five copies of the roster to leak

**Interoperability stance:**

- Do not demand migration: broadcast to WhatsApp and SMS, make the DECISIONS AND RECORDS happen on the platform. A co-op only reachable by people with a login is a co-op that excludes
- A bridge is NOT a privacy upgrade: a Matrix bridge to WhatsApp terminates the encryption — the bridge sees plaintext — so it adds a new custodian rather than removing one. Say it plainly
- When to keep using Signal: a small group of known people, a conversation, nothing needing governance or a record. Keep it — that is the pitch working, not failing

**Guardrails — claims we must never make:**

- Never 'more private than Signal' for messaging — false, and one informed audience member ends the pitch
- Never 'your data is safe on any node' (the forbidden claim from federation-encryption-and-access.md)
- Never imply protection at the physical layer (seized device, raid, abusive partner with the passcode)
- Never imply a bridge makes WhatsApp private
- Never claim encryption removes the need for trust — it relocates WHO must be trusted
- Never claim the platform stops a lie — it makes your own account checkable
- NEVER sell today's capability as tomorrow's: as of 2026-09-13 the shipped parts are one identity, groups/seats, events and ticketing, chat, files/docs, and a self-hosted node. The modes, the vault fix, selective-disclosure proofs and the custody chain are DESIGNED, NOT BUILT. The chilling-effect story is true today; the mitigations must be spoken as commitments with a stated timeline

#### Group modes — chosen at formation, movable later

| Mode | Fits | Membership visibility | Content | Keys | Blocked by |
|---|---|---|---|---|---|
| **Open** | tool libraries, childcare rotas, public events — the parts that are MEANT to be public | public roster — for the public parts only | plaintext — a public good | none | nothing |
| **Guarded** | mutual aid, advocacy, practical programs, food hubs and adoption co-ops | in-group only, non-enumerable to outsiders | client-side encrypted | per-group DEK, k-of-n to members | the vault fix (custodial → non-custodial) |
| **Compartmented** | unions in formation, community safety, peer support, identity-threatened coalitions (e.g. Somali / Latino / Black farmers organising together) | commitment-only — not even the platform can enumerate | encrypted per sub-group, separate DEKs per compartment | epoch keys; rotation on membership change | epoch keys + the commitment tier (group-scoping §3 tier 2, designed and deferred) + per-pair visibility (a group is not one perimeter) |
| **Deniable** | rave, subculture, hostile jurisdictions, entheogenic | no central roster; membership proven on demand | encrypted; no persistent plaintext on member devices | short-lived keys, frequent epoch rotation | epoch keys + device policy + short-lived grants |

A mode change is a first-class operation, not a migration: the union's `hidden → members` flip at recognition is exactly this. It rotates keys and re-issues proofs; it does not rewrite history.

#### Failure modes — stated, because they are what actually kills volunteer infrastructure

- **The steward burns out and the node dies with them** — This is the failure that ends most volunteer infrastructure, and no amount of architecture prevents it. It is visible in the settled design's own terms: a stale coverage proof IS the signal — the gradient watches for it, so the federation can see a node going quiet before it disappears.
  *Mitigation:* Tier the on-ramp so no single person carries a whole stack; require a named second person per node; treat handover as a documented procedure, not a favour.
- **Version drift across nodes** — N nodes at different generator versions is how federations rot: one node serves a schema the others don't expect.
  *Mitigation:* The declarative tree is the defence — each org has its own instance dir, and `stack-report.py` already reconciles declared-vs-running. Drift is detectable per node; what is missing is anyone acting on the report.
- **No SLA, no on-call** — Nobody is paged at 2am. For a co-op's mail and chat, that is a real service-level regression against a paid provider — and it must be said out loud in any recruitment video.
  *Mitigation:* Say it. Price it as a trade-off, not hide it. Redundancy at the asset layer (maps, media, docs) is honest to promise; an uptime number is not.
- **Heterogeneous networks (NAT, residential uplinks, dynamic IPs)** — An org's node sits behind a consumer router. Serving inbound traffic from one is a different problem from storing data on one.
  *Mitigation:* An edge node that only holds a replica and serves behind a cache needs far less than one that terminates public traffic. THIS is where the parked DNS/edge question begins — name it and stop there.
- **Free-riding** — If contribution is invisible, the honest org subsidises the strategic one.
  *Mitigation:* The coverage-proof gradient already designed: positive credential, no shame flag, ranges rather than amounts.
- **A node hosts other people's data — and the data is NOT all encrypted** — This was written as a governance worry. Reading the stack, it is a factual one: MinIO has server-side encryption switched OFF, Postgres rows are plaintext at rest (the design doc says so), and mail and collaborative documents are structurally server-readable. So 'encrypted at rest' would not fix it anyway — at-rest encryption protects a stolen disk, not the operator, who holds the key. See `federation.encryption_reality`.
  *Mitigation:* Scope federation by pillar and say which is which: static assets and E2E content are federation-safe today; mail, docs and DB rows require a TRUSTED node. That is a fine answer for a federation of known orgs — it just has to be stated rather than assumed.

<sub>Cross-check: 37 apps declared in `infra/instances/dev/instance.yaml` — traefik, keycloak, citus, irl-redis, minio, nocodb, stalwart, roundcube, cryptpad, temporal, temporal-ui, formbricks, hievents, webstudio, postiz, plane, coop-api, matrix, element-web, element-call, cinny, livekit, lk-jwt, coturn, freeswitch, fusionpbx, mediamtx, onlyoffice, maps, litefarm, rag, rag-inference, rag-migrate, rag-api, rag-worker, erpnext, wordpress.</sub>

<sub>Regenerate: `python3 infra/scripts/cost-model.py` · data: `docs/design/cost-model.data.json`</sub>
<!-- END GENERATED: cost-model.py -->
