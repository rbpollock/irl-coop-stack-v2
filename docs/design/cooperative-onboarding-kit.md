# Cooperative Onboarding Kit — Facilitator's Instrument

Status: design · 2026-10-27 · Robbie + Hermes.
Companion to: `cooperation-survey-templates.md` (the member-facing surveys), `onboarding-flow.md`
(member journey), `FIRST-PILOT.md` (pilot boundaries), `adversary-models-and-sector-fit.md`
(threat profiles), `account-and-key-model.md` (Safe ownership), and `group-scoping.md` (RLS + seats).

---

## 0. What this is

A working instrument for a **cooperation facilitator** — someone who knows the irl.coop stack, the
principles of cooperation, and the common ways groups break. The facilitator uses this kit to:

1. **Discover** what a business or coop actually is, needs, and risks.
2. **Configure** the group on the stack with correct permissions, roles, management, marketing, and
delivery workflows.
3. **Identify** safeguarding gaps, insurance needs, optimization opportunities, and trust-breakdown
surfaces.
4. **Observe** how the business is performing through instrumented surfaces.
5. **Govern** — connect the group to the appropriate irl.coop vertical governance and, where
applicable, broker a grant from the vertical to the target business.

The kit is **not a sales deck.** It is a diagnostic and configuration tool. Every section produces a
recorded decision or a configured artifact. The facilitator's credibility rests on honesty about what
the stack can and cannot do today.

---

## 1. Principles for the facilitator

1. **The group is autonomous; the platform is a steward, not a root.** The facilitator configures —
they do not own, operate, or override. Every permission the facilitator holds is scoped, revocable,
and time-bounded.
2. **Honesty about limits.** `REALITY.md` is the ground truth. If a feature is designed-not-built, say
so. If money is wired but has never moved, say so. A pilot that trusts fiction becomes a liability.
3. **Consent is recorded, not assumed.** Every configuration choice that affects member privacy,
visibility, or money is a choice the group makes, not a default the facilitator sets.
4. **Trust breakdowns are predicted, not discovered.** The kit assumes cooperation fails in known
patterns and inspects for them explicitly.
5. **The vertical is a peer, not a boss.** Grant relationships are peer-to-peer, with explicit terms,
not charity with conditions hidden in the fine print.

---

## 2. The facilitator's workflow (phases)

```
DISCOVER → DIAGNOSE → CONFIGURE → HARDEN → LAUNCH → OBSERVE → GOVERN
   |          |          |          |        |         |         |
   ▼          ▼          ▼          ▼        ▼         ▼         ▼
 Intake    Trust &     Stack       Safeguard  Pilot   KPIs     Vertical
 Forms     Resilience   setup       & Insure   entry   &        relation
 +                  +                       +      Alerts         + Grant
 Sector               Marketing                               flow
 probe              & delivery                              contract
                    workflows
```

Each phase is a **checkpoint.** The facilitator does not proceed until the group (or its named
owners) have signed off on the phase output.

---

## 3. Phase 1 — DISCOVER: Intake instrument

### 3.1 The five intake forms

These are facilitator-facing worksheets, filled in conversation with the group's founders or
steering committee. They are not member surveys (those live in `cooperation-survey-templates.md`).
They are the **configuration inputs.**

---

#### Form A — The group in one page

| Field | Answer | Maps to stack |
|---|---|---|
| What do you call yourselves? (working name) | | `groups.name`, `groups.slug`, subdomain |
| What do you do in one sentence? | | public page headline, `groups.description` |
| How many people are in the founding set? | | `group_members` rows, Safe threshold design |
| Is this a new group or an existing one moving platforms? | | migration path vs. fresh provision |
| What legal form, if any? (co-op, nonprofit, informal, LLC…) | | `group_metadata.legal_form`; informs governance defaults |
| Do you already have a bank account or treasury? | | money path readiness; Stage 1 vs. Stage 2 pilot gating |
| What is your annual budget or expected turnover? (range) | | `dues_policy`, insurance tier, NocoDB schema |
| Who is the single person the facilitator can reach for decisions? | | designated contact seat; **not an owner by default** |

---

#### Form B — Sector and threat profile

Use `adversary-models-and-sector-fit.md` §4. The facilitator picks the row; the group confirms.

| Question | Options | Stack consequence |
|---|---|---|
| Which sector row fits best? | A–K from adversary doc | Determines default Mode + Footprint (§6 of adversary doc) |
| Is any member identity-threatened? | Yes / No / Prefer not to say | If Yes → `Compartmented` or `Deniable` mode; non-enumeration default; per-pair visibility |
| Is the group in formation, operating, or under external pressure? | forming / operating / under pressure | `hidden` vs. `members` visibility; whether governance is constitutional vs. ordinary |
| Does the group need to produce compliance records to a regulator or certifier? | Yes, who: ___ / No | Selective disclosure setup; custody-chain-and-contest-kit readiness |
| Is there an intimate adversary risk (E1) in the membership? | Yes / No / Unknown | Compartmented sub-groups with separate DEKs; no bulk roster export |
| Footprint preference | Published / Sparse / Unreadable | Projection settings, public page content, SEO visibility |

**Rule:** if identity-threatened members exist, the facilitator **does not** set a Published footprint
without explicit written consent from those members.

---

#### Form C — Roles and decision-making

| Question | Answer | Maps to stack |
|---|---|---|
| How do you make big decisions? (consensus, majority, designated leader, rotating…) | | `governance` axis in group shape; `proposals` table config |
| Who can spend money? (one person, two signatories, whole group…) | | Safe threshold design; `treasury_guards` table |
| Who invites new members? | | `invite_grant` default; `group_members.role_grants` |
| Who can read the money ledger? | | `private_treasury_guards_ledgers` visibility tier |
| Is there a conflict-of-interest policy? | Yes / No / Drafting | If No → facilitator must flag; if Yes → record in `governance` axis |
| Do you have a succession plan if a key person leaves? | Yes / No | If No → trigger `warm questions` (onboarding-flow §5) before launch |
| Do you use consensus and worry about deadlock? | Yes / No | If Yes → suggest threshold `≤ owners − 1` with a tie-breaking protocol |

---

#### Form D — Operations and tooling

| What do you use today? | Will you keep it? | Replacement on stack? | Migration needed? |
|---|---|---|---|
| Communication (Slack, WhatsApp, Signal, email…) | | Matrix/Element, Stalwart mail, SMS spine | member invite + channel seeding |
| Task tracking (Trello, Asana, spreadsheets…) | | Plane projects | manual or CSV import |
| Documents (Google Drive, Dropbox, local…) | | MinIO + OnlyOffice | file upload / bulk migration |
| Database / CRM (Airtable, HubSpot, none…) | | NocoDB bases or ERPNext | schema design + import |
| Accounting (QuickBooks, spreadsheet, none…) | | ERPNext accounting module | chart of accounts setup |
| Scheduling (Calendly, Doodle, none…) | | Cal.com (if deployed) or NocoDB calendar | booking links |
| Public web presence (Squarespace, WordPress, none…) | | Webstudio or WordPress | content copy |
| Events / ticketing (Eventbrite, none…) | | Hi.Events | event clone |
| Payments (Square, Venmo, cash, none…) | | Peer.xyz rail + group Safe | Stage 2 gate only |
| Phone / SMS (personal cells, Google Voice, none…) | | Telnyx DID + FusionPBX extensions | DID provisioning |

---

#### Form E — Money and custody readiness

**This form gates Stage 1 vs. Stage 2.** Do not let a group believe money will move if the stack
cannot move it. See `FIRST-PILOT.md` §1 and `docs/PAYMENTS-SETUP.md`.

| Question | Answer | Gate |
|---|---|---|
| Do you need to move real money through the platform this season? | Yes / No | Yes → Stage 2 gates apply (see §8) |
| What currency / rail? (USD card, USDC, cash, check…) | | Determines rail config |
| Who holds the keys to your existing treasury? | | Custody audit; informs Safe threshold design |
| Has the group agreed a spending limit per transaction without a meeting? | | `dues_policy` threshold; session key module config |
| Do you need income reporting for tax or grant compliance? | | ERPNext chart of accounts; NocoDB reporting base |
| Do you have a reserve / emergency fund policy? | | `treasury_guards` circuit breaker design |
| What happens if a payment fails or is disputed? (P2P rails reverse) | | `rail_event` handling; refund path; risk bounds |

---

### 3.2 Discovery output: the Intake Record

A single JSON/row artifact stored in the facilitator's NocoDB base (not the group's), with:
- All Form A–E answers.
- Assigned sector + default Mode + Footprint.
- A **risk summary** (see §4).
- A **configuration manifest** (see §5).
- Phase sign-off: dates + names of the group representatives who confirmed.

---

## 4. Phase 2 — DIAGNOSE: Trust & resilience plan

### 4.1 The seven trust-breakdown patterns

Based on `cooperation-survey-templates.md` and common cooperative failure modes. The facilitator
scores each 1–5 (1 = healthy, 5 = acute) and records the score.

| # | Pattern | How it shows | Diagnostic question |
|---|---|---|---|
| 1 | **Unclear purpose** | Meetings wander; members join for different reasons; no shared charter | "If you had to explain to a new member why this group exists, would three founders say the same thing?" |
| 2 | **Unspoken expectations** | People assume roles that were never assigned; resentment builds quietly | "Is there any work one person does that the group hasn't named and agreed to?" |
| 3 | **Unexamined power** | One founder holds all keys/decisions; newer members don't know how to challenge | "If [name] disappeared tomorrow, could the group still run its next event?" |
| 4 | **Uncounted labor** | Care work, outreach, emotional labor done by the same people without recognition | "Whose work keeps the group alive but never appears in a task list?" |
| 5 | **Avoided conflict** | Tensions surface as jokes, side-chats, or sudden departures; no repair path | "When two members disagree, what happens?" |
| 6 | **Money opacity** | Funds move informally; no ledger; suspicion about fairness | "Can every member see how much came in, how much went out, and who decided?" |
| 7 | **Boundary collapse** | Work bleeds into personal life; no exit path; people feel trapped | "Can a member step back for a month without the group falling apart?" |

**Scoring rule:**
- Any score ≥ 4 → **mitigation required before launch.** The facilitator brokers a session using
the `Tension & repair` survey (survey #8 in `cooperation-survey-templates.md`) or an external
facilitator if the vertical provides one.
- Two or more scores ≥ 3 → **flag for pulse monitoring.** Set `Pulse` survey (survey #5) to
fortnightly instead of monthly.

### 4.2 Resilience checklist

| Item | Check | Mitigation if No |
|---|---|---|
| At least two people can invite and manage members | ☐ | Name a second admin before launch |
| Safe threshold is ≤ owners − 1 (not unanimity) | ☐ | Explain deadlock risk; adjust threshold |
| A recovery contact / succession is named | ☐ | Trigger `warm questions` (Step 5 in onboarding-flow) |
| Consent to terms is recorded | ☐ | Hold launch until `B-20` (consent capture) is implemented |
| Conflict-of-interest policy exists or is drafted | ☐ | Add to governance axis; set reminder |
| A documented exit path exists (member leaving, group dissolving) | ☐ | Draft exit terms in `governance` axis |
| The group has met in person or by video at least once | ☐ | Require synchronous meeting before invite-only launch |
| Members know how to reach the facilitator / vertical steward | ☐ | Add contact to group welcome message |

---

## 5. Phase 3 — CONFIGURE: Stack setup manifest

The facilitator translates the Intake Record into a concrete configuration. Each item names the
file, route, or table involved.

### 5.1 Identity & Safe creation

| Config item | Value / rule | Where |
|---|---|---|
| Personal Safe owner | `PasskeyOwner` from member's registered passkey | `safe.ts` create path; gated on `B-11` |
| Group Safe owners | Founding member Safes | `groups.ts`; `group_members` with `is_owner` |
| Group Safe threshold | ≤ owners − 1, minimum 1-of-2 if 2+ founders | `safe.ts` deploy; enforced by guard |
| `safe_address` attestation | On-chain `getOwners()` verified before write | `coop_ops`-locked definer; `B-13` |
| DB cert role | `coop_m_<sub8>` derived from Keycloak `sub` | `provision-member-certs.sh` |

### 5.2 Group shape & apps

From Form D, activate apps in `instance.yaml` + `resource_scopes`:

| App | Enabled? | Group-scoped via | First config step |
|---|---|---|---|
| Plane (projects) | Yes / No | `resource_scopes` → Plane project canonicalization | Create project; map members to roles |
| NocoDB (data) | Yes / No | Per-member DB cert + base grants | Create base; invite members; run `enforce-nocodb-visibility.sh` |
| Matrix/Element (chat) | Yes / No | `resource_scopes` → Matrix space | Create space + rooms; invite via `matrix.ts` |
| ERPNext (CRM/accounting) | Yes / No | Gate SSO + per-tenant data | Set chart of accounts if money; configure contacts |
| Stalwart (mail) | Yes / No | Domain auto-provisions on first auth | Verify `@group.irl.coop` resolution |
| Hi.Events (ticketing) | Yes / No | Gate SSO | Clone event template; set payment keys (Stage 2 only) |
| Webstudio / WordPress (public pages) | Yes / No | Subdomain + `slug.irl.coop` | Publish minimal landing page |
| Maps (tracks/markers) | Yes / No | Per-group RLS | No initial data; document how to record |
| Telephony (DID + SMS) | Yes / No | `telephony_resources` 'did' | Hold until gateway + DID acquired |

**Rule:** do not enable an app the group does not have a trained user for. A misconfigured ERPNext is
worse than no ERPNext.

### 5.3 Roles & grants

Map the group's real roles to `role_grants` + `grants` tables. Start with the smallest set that
works; expand later.

| Real-world role | Stack role | Grants (see `coop_rls.sql` `coop_has_grant`) |
|---|---|---|
| Coordinator / facilitator (the role, not the irl.coop facilitator) | `admin` | `group:manage`, `members:invite`, `treasury:read`, `treasury:propose` |
| Treasurer | `finance` | `treasury:read`, `treasury:propose`, `dues:manage` |
| Member | `member` | `group:view`, `files:read`, `chat:read`, `tasks:read` |
| Observer / intern | `visitor` | `group:view` (selective bases/projects only) |
| Public-facing contact | `outreach` | `pages:edit`, `events:manage`, `mail:send` |

---

## 6. Phase 4 — HARDEN: Safeguarding, insurance, optimization

### 6.1 Safeguarding matrix

| Risk class | Source | Safeguard | Verification |
|---|---|---|---|
| Data leak between groups | RLS policy misconfiguration | Run `verify-coop-rls.mjs`; confirm non-member gets 403 on every group read | Automated in `journeys.sh` |
| Former member retains access | No epoch keys | Document as known gap (`REALITY.md`); plan manual seat removal | Check `group_members` left_at timestamp |
| Platform custodial access | Backend signer owns Safe | **Blocked on B-11.** If not fixed, flag as `pilot-critical` stopper | `SafeCreatedPasskeyOwned.ts` test |
| Operator coercion (state) | Host is compellable | Selective-disclosure default; no server-side DEK; client-side encryption where available | Architecture review |
| Insider sabotage / embezzlement | Authorized member | Threshold on Safe; spending limits; session key expiry; audit trail in `rail_event` | `SessionKeyModule` test pack |
| Username claim hijack | Unordered claim before invite | **Blocked on B-18.** Verify `@localpart` collision check exists | Username collision journey |
| Credential stuffing / auth bypass | Auth hygiene gaps | **Blocked on B-24.** Rate limits, nonce verification, JWKS caching | k6 + unit tests |
| CORS origin reflection | Fleet amplifier | **Blocked on B-16.** Enumerate real origins; reject random `*.irl.coop` | Origin spoof test |

### 6.2 Insurance checklist

Not every group needs every item. The facilitator marks relevant rows.

| Coverage | Fits when… | Action |
|---|---|---|
| General liability | Public events, physical space, customer-facing | Document current coverage; recommend mutual-aid captive if vertical offers one |
| Directors & officers | Incorporated co-op with a board | Flag if absent; vertical may broker group policy |
| Cyber / data breach | Sensitive member data; identity-threatened members | Required for `Compartmented`/`Deniable` mode |
| Event cancellation | Ticketing; outdoor events; weather-dependent | Hi.Events terms should reference cancellation policy |
| Product liability | Food, goods sold to public | Contest kit + custody chain (`custody-chain-and-contest-kit.md`) as evidence reserve |
| Fidelity bond / theft | Treasury > $X or multiple signatories | Safe threshold + session limits are the software side; bond is the financial side |

### 6.3 Optimization opportunities

| Surface | Current state | Optimization |
|---|---|---|
| Onboarding friction | Not verified (`FIRST-PILOT.md`) | Reduce steps; add skip-to-world; track `time-to-first-task` |
| Cross-app navigation | Dashboard embeds apps but context is lost | Unified seat/role display across Plane/NocoDB/Matrix |
| Notification noise | Redis pub/sub exists; no member preferences | Per-channel opt-in (email vs. Matrix vs. SMS) |
| Public findability | Webstudio/WordPress optional; SEO unexamined | Published footprint + sitemap + `robots.txt` tuned to mode |
| Grant reporting overhead | Manual data gathering | NocoDB views + automated exports to vertical reporting base |
| Treasury visibility | Off-chain ledger has zero rows | Start `tier2_entry` recording immediately for attribution |

---

## 7. Phase 5 — LAUNCH: Marketing & delivery workflows

### 7.1 Marketing workflow setup

| Channel | Stack tool | First-week task | Owner |
|---|---|---|---|
| Public web | Webstudio or WordPress | Publish landing page with offerings, hours, contact | Outreach seat |
| Social feed | Postiz (fediverse distribution) | Connect accounts; schedule announcement | Outreach seat |
| Email list | Stalwart + group alias | Create `@group.irl.coop`; add subscribe CTA to site | Outreach seat |
| Events / RSVP | Hi.Events | Create first event; embed on site | Outreach seat |
| Maps / location | Maps basemap | Drop pin for meetup / farm / pickup point | Coordinator |
| Public chat | Matrix public room (if desired) | Create bridged room; post rules | Coordinator |

**Important:** For `Sparse` or `Unreadable` footprint, the public web is a **projection** — offerings
and hours only, never membership roster, supplier list, or growth trajectory
(`adversary-models-and-sector-fit.md` §0.6).

### 7.2 Delivery workflow setup

| What you deliver | Stack workflow | Integration |
|---|---|---|
| Services (facilitation, repair, design) | Plane project per engagement → tasks → completion → invoice intent in ERPNext | Cal.com scheduling if deployed |
| Physical goods (CSA box, art print, tool loan) | NocoDB inventory base → order row → fulfillment status → custody-chain receipt | Hi.Events for pickup RSVPs |
| Digital goods (document, ticket, recording) | MinIO bucket → share link → delivery confirmation | OnlyOffice for inline review |
| Membership / subscription | `dues_policy` → payment intent (Stage 2) → `dues_waiver` for hardship | Pulse survey tracks retention |
| Mutual-aid distribution | Needs/offers matching (`needs-offers-matching.md`) → allocation → delivery log | Anonymous by default if sector A/B |

---

## 8. Phase 6 — OBSERVE: Performance surfaces

### 8.1 The facilitator's KPI board (NocoDB base template)

Create one base per group, or one per vertical, with these views:

| Metric | Source table / query | Frequency | Healthy threshold | Alert if… |
|---|---|---|---|---|
| Member sign-in rate | `group_members.last_login_at` | Weekly | > 70% active in 14 days | < 50% |
| Task completion velocity | Plane API → issues closed / week | Weekly | Baseline after 2 weeks | Zero for 2+ weeks |
| Document creation rate | `files` table + MinIO logs | Monthly | > 1 doc per member | Zero in 30 days |
| Pulse sentiment (net) | Survey #5 average | Fortnightly | ≥ 3.5 / 5 | < 3.0 |
| Treasury inflow | `payment_intent` where `status = succeeded` | Monthly | Matches forecast | 4 failures in a row |
| Rail event error rate | `rail_event` where `status = failed` | Per event | < 5% | Any failure unreviewed > 48h |
| Chat engagement | Matrix room message count | Weekly | > 10 msgs/week | Zero for 1 week |
| Public page visits | Webstudio/WordPress analytics | Monthly | Growing or stable | Sudden drop > 50% |
| Proposal participation | `proposals` → `votes` participation % | Per proposal | > 60% of members | < 30% (governance risk) |
| Open trust-breakdown score | Diagnostic scores (§4.1) | Monthly | Improving or stable | Any score rises by ≥ 1 |

### 8.2 Automated alerts

Wire the Temporal worker (or a scheduled script) to emit events when thresholds breach:
- Low sign-in → `irl:notify:{sub}` via Redis → email to facilitator + coordinator.
- Repeated payment failure → hold treasury; alert `finance` seat; do not retry blindly.
- Governance participation drop → trigger `Power & participation audit` (survey #6).

---

## 9. Phase 7 — GOVERN: Vertical relation & grant flow

### 9.1 Vertical governance mapping

| Vertical | Steward role | What the vertical provides | What the group owes |
|---|---|---|---|
| Facilitation | Process design, mediation roster | Trained facilitators, conflict-resolution protocol | Feedback data, case studies, no-platform members |
| Conflict & repair | Neutral arbiter access, repair fund | Escrow for repair work, facilitated session booking | Agreement to use vertical protocol before litigation |
| Group & org design | Blueprint library, governance templates | Shape packs, constitutional clauses, threshold guidance | Contribution to blueprint library |
| Psychodynamics | Practitioner circles, supervision | Safe containers, peer supervision groups | Anonymized pulse data |
| Food sovereignty | Coalition bargaining, certifier vouching | Supply-chain anonymity, land-pipeline connections | Traceability proofs (selective disclosure) |
| Cultural power | Event safety, deniable infrastructure | Short-lived keys, rapid rotation, no central roster | Event data (aggregate only) |
| Healing justice | Practitioner certification, liability cover | Per-practitioner key custody, exculpation records | Compliance-ready session logs |

### 9.2 Grant flow instrument

When a vertical subsidizes a target group:

1. **Eligibility probe** — the facilitator runs the Intake Record through vertical criteria.
2. **Terms negotiation** — a NocoDB base records:
   - Grant amount and currency.
   - Deliverables (never beneficiary lists; use counts, proofs, or anonymized outcomes).
   - Reporting rhythm.
   - Termination conditions.
   - Data-sharing bounds (what the vertical can see, what stays group-internal).
3. **Disbursement path** — vertical Safe → group Safe, with a `dues_waiver` or `treasury_project_scope`
   record. If Stage 2 money is not live, the grant is off-platform (check/wire) with a commitment to
   reconcile on-chain later.
4. **Obligation tracking** — deliverables linked to Plane milestones; proof submissions via `tier2_entry`
   + anchor.
5. **Completion / clawback** — on-chain proposal in the group to release final tranche or return
   unspent funds.

**Hard rule:** the vertical never receives a `group_members` export, a `profiles` dump, or an
unredacted `rail_event` ledger. Proof > roster. This is `adversary-models-and-sector-fit.md` §5.7.

---

## 10. NooNAO Layer — Trust Networks, Portable Communities, and Extreme Decisioning

This section integrates concepts from **NooNAO** (`nao.is` / NooNet) — a platform-cooperative research initiative for Networked Adaptive Organisms — into the facilitator's instrument. NooNAO's primitives are a natural fit for irl.coop's group-graph architecture, and the facilitator can use them to strengthen trust formation, sensemaking, and collective governance.

The core idea: **humans are neurons, relationships are synapses, and groups are adaptive organisms.** The facilitator's job includes making those synapses *high-fidelity* and the organism *capable of extreme decisioning*.

### 10.1 What NooNAO adds to the stack

| NooNAO primitive | What it is | How it maps to irl.coop | Facilitator action |
|---|---|---|---|
| **Trust Networks by invitation** | Social graphs grown by invitation where every link is a high-fidelity representation of what A thinks of B, backed by an accountability chain | `group_members` + `coop_rls` identity; seats with per-group personas; the declared-binding registry (when built) | Seed the founding graph with labeled edges; ensure every invitee is vouched for |
| **GreenCheck — three-friend proof of personhood** | Identity attestation by three existing members who know you, rather than a state ID or a credential factory | Keycloak realm + passkey ownership (`B-11`); `member_passkey` table; `profiles` | For groups needing proof-of-personhood (e.g., mutual aid, community safety), facilitate three-member attestation before full seat activation |
| **Praise / respect vectors** | A relationship edge is a labeled floating-point vector (dimensions like skill, reliability, care, courage) — not a 1-bit "friend" connection | Future: `relationship_edges` table with typed labels and weights; near-term: capture via `needs-offers-matching.md` + `cooperation-survey-templates.md` survey #1 (gifts/needs) as a proxy | Run survey #1 with dimensional praise; store in NocoDB as a relationship base; review at pulse time |
| **Stigmergy / WhoKnows** | Members mark allies with domain expertise, especially place-based (bioregional) knowledge, creating a collective "who knows what where" map | `tracks`/`markers`/`waypoints` tables + NocoDB expertise base + Matrix room topics | Set up a "WhoKnows" base in NocoDB; map members to domains + bioregions; link to group map pins |
| **Extreme decisioning** | Real-time, any-scale, any-domain collective decision-making via continuous delegation/proxy links weighted by domain-specific authoritativeness ("mojo") | `proposals`/`votes` tables + `role_grants` + `delegation-and-session-keys.md` scoped grants | Configure proxy delegation per domain (finance, operations, outreach); weight votes by role + contribution record (`tier2_entry`) |
| **Portable Communities Protocol** | Group membership that synchronizes across platforms — persistent, composable, application-independent | `groups`/`group_members`/`resource_scopes` + Safe ownership graph; future: declared-binding registry as a federation anchor | Document the group's native stack identity; prepare for cross-platform sync when the protocol lands |
| **Social bookmarking (Best of Now)** | A group-curated stream of links, resources, and signals, collectively tagged and ranked | `files` table + MinIO + Matrix pinning + NocoDB resource base | Create a "Best of Now" base; wire a Matrix room bot for link capture |
| **Collective ownership as a network cooperative** | The Trust Network itself owns and governs the platform, capturing and allocating value emergently as a fractal commons | Group Safes + `treasury_guards` + `dues_policy` + the shielded pool; vertical governance | Frame the group's relationship to irl.coop as peer-to-peer, not vendor-to-customer; the group is a node in a network cooperative |

### 10.2 Trust-network seeding — facilitator guide

A group starts as a sparse graph. The facilitator's job in the first two weeks is to make the edges *labeled*, not just *present*.

**Step 1 — Map the founding synapses**
- Before any member is invited, ask: who vouches for whom?
- Record the answer in the Intake Record (§3.2) as a simple directed graph: `A → B (how they know each other, for how long)`.
- If three members cannot vouch for a prospective member, delay full seat activation until they can (GreenCheck principle).

**Step 2 — Run the gifts/needs survey as a dimensional praise exercise**
- Survey #1 (`cooperation-survey-templates.md`) asks "what I bring, what I need."
- Add a NooNAO-style prompt: "Name one member you trust for [domain] and one word that describes why."
- Store the result in the NocoDB relationship base as a row per praise: `praiser`, `praisee`, `domain`, `dimension` (skill, reliability, care, courage, presence), `weight` (1–5).
- This is the group's initial *mojo* map.

**Step 3 — Make the graph visible (to members, not to the world)**
- A read-only NocoDB view shows each member their incoming praise: "People trust you for…"
- Never show the full matrix publicly; respect the `footprint` setting (§3.1).
- The graph updates after every pulse survey and every completed project.

### 10.3 Extreme decisioning — configuring delegated governance

NooNAO's "extreme decisioning" works because influence is weighted by domain-specific authoritativeness derived from the trust network. The facilitator sets this up within irl.coop's existing `proposals`/`votes`/`role_grants` tables.

**Per-domain delegation setup**

| Domain | Typical grant | Proxy delegation | Weight source |
|---|---|---|---|
| Finance | `treasury:propose` + `treasury:read` | Treasurer can proxy-vote for absent members on budget matters | `role_grants` + `tier2_entry` (contribution hours in finance tasks) |
| Operations | `group:manage` + `tasks:assign` | Coordinator can proxy-vote on logistics | `tier2_entry` (operations tasks) + pulse reliability score |
| Outreach | `pages:edit` + `events:manage` | Outreach lead can proxy-vote on brand/public voice | `tier2_entry` (outreach tasks) + social proof (Best of Now tags) |
| Conflict resolution | `proposals:mediate` | Rotating pair from `Power & participation audit` (survey #6) top scorers | Survey #6 scores + attendance record |

**Rules for proxy delegation**
1. Proxies are **continuous** until revoked — not per-vote.
2. A member can have **different proxies per domain** — not one delegate for everything.
3. Proxy votes are **visible** (who voted, via whom) but the underlying trust edge is **private**.
4. A proxy chain longer than 2 hops is **discouraged** — trust decays fast.
5. Emergency override: any member can **always vote directly** by signing into the proposal; the proxy is a convenience, not a replacement.

**Implementation note:** today `proposals`/`votes` have zero rows and no RLS (`B-22`). Implement `B-22` and the delegation weights before activating extreme decisioning. The facilitator documents the intended rules now and flips the switch when the code is ready.

### 10.4 Portable Communities — cross-platform identity

The facilitator records the group's irl.coop-native identity so that future sync to other platforms (or vice versa) is possible without re-founding.

**The group identity bundle** (stored in the Intake Record):
- `group_safe_address`
- `group_slug`
- `group_merkle_root` (when `CoopRegistry.sol` is functional — currently a stub)
- `keycloak_realm_id` + `keycloak_client_id`
- `founding_block_timestamp` (on-chain Safe creation)
- `member_public_keys` (passkey credentials, not private keys)

**The member identity bundle** (per member, portable):
- `personal_safe_address`
- `passkey_id`
- `keycloak_sub`
- `profile_hash` (consent + terms, when `B-20` is implemented)

**Facilitator promise:** if the group ever leaves irl.coop, these bundles are theirs. The platform is a steward, not a root.

### 10.5 Sensemaking — the inquiry layer

NooNAO includes a "Sensemaker" concept: structured inquiries that the network uses to perceive itself. The facilitator can adopt this as a standing practice.

| Inquiry | When | Stack tool | Output |
|---|---|---|---|
| "What is urgent but unspoken?" | Every pulse survey | Survey #5 + Matrix open-thread | A ranked list of silent tensions |
| "Who is unseen but load-bearing?" | Every `Power & participation audit` | Survey #6 | Rebalancing proposals for role rotation |
| "What do we know that no one else does?" | Quarterly | WhoKnows base + Best of Now | Identified blind spots + external resource gaps |
| "What is the cheapest experiment we could run?" | After every failed proposal | Plane project template | A seed task + $0 budget + one-week deadline |
| "If we had to dissolve tomorrow, what would we keep?" | Annual review | Group-world-document rebuild | Minimal-viable-shape (the "seed, not cage") |

### 10.6 Bioregional and place-based tagging

For food sovereignty, land, mutual aid, and cultural power verticals, the facilitator encourages **bioregional stigmergy**:
- Every member's profile includes a `home_bioregion` free-text field (no geo precision required — a watershed, a neighborhood, a cultural region).
- Every `track`/`marker`/`waypoint` is tagged with a bioregion + a domain tag (food, water, culture, safety).
- The group map becomes a collective knowledge layer: "who knows what where."
- Future: the `maps` basemap can render density heatmaps of expertise + place.

---

## 11. The facilitator's handoff checklist (revised)

Before the facilitator steps back:

- [ ] Intake Record stored and shared with group representatives.
- [ ] Configuration manifest stored; group representatives can read it.
- [ ] All enabled apps have at least one trained user in the group.
- [ ] Safe threshold and owners verified on-chain; recovery contact named.
- [ ] Consent recorded (or flagged as blocked on `B-20`).
- [ ] Pulse survey scheduled; facilitator contact visible in group welcome.
- [ ] Marketing channels live with at least one published artifact.
- [ ] Delivery workflow tested end-to-end with one synthetic order/task.
- [ ] KPI board visible to coordinator + treasurer; alerts wired.
- [ ] Vertical relation documented; grant terms stored if applicable.
- [ ] **Trust-network graph seeded** — founding members have at least one labeled praise edge recorded.
- [ ] **Extreme decisioning rules documented** — per-domain delegation, proxy limits, emergency override.
- [ ] **Portable identity bundle** stored for the group + each member.
- [ ] Known gaps documented (from `REALITY.md`, `RISKS.md`, `BACKLOG-TRIAGE.md`) and shared.
- [ ] Next check-in date scheduled (recommended: 2 weeks, then monthly).

---

## 12. Open questions

1. Should the facilitator be a **group seat** (`group_members` with a `facilitator` role), or an
   external party with a time-bounded `resource_scope`? The latter is safer; the former is easier to
   implement today.
2. Does the kit need a **paper / offline version** for groups with low digital literacy or hostile
   jurisdictions? (A printed facilitator workbook derived from this doc.)
3. How does the facilitator's own **liability** get handled — are they a contractor of the vertical,
   an insured role, or a peer volunteer?
4. Should the Intake Record be **anchored on-chain** (a Merkle root of the configuration manifest),
   making the facilitator's work tamper-evident?
5. What is the **minimum viable facilitator training** — a read-through of this doc, a shadowed pilot,
   or a certified course?

---

*This document is current with the stack as of 2026-10-27. Where it references a `B-` backlog item,
that item is from `BACKLOG-TRIAGE.md` and may not yet be implemented. The facilitator's honesty
about those gaps is part of the instrument.*

---

## 13. Sources and credits

### External frameworks and projects

| Source | What we drew from | Where it appears |
|---|---|---|
| **NooNAO / NooNet** (`nao.is`) | Trust Networks, proof-of-personhood (GreenCheck), praise vectors, extreme decisioning, portable communities, sensemaking, bioregional stigmergy, the neuron/synapse/organism metaphor | §10 (NooNAO Layer), §10.2–10.6 |
| **Brad DeGraf & Charles Blass** (NooNet / Planetwork) | Project stewardship and contact for NooNAO; fiscal sponsorship via Planetwork 501(c)(3) | §13 (this section) |
| **Richard Bartlett** (Loomio / The Hum) | Quote on portable communities and the "critical gap" of synchronizing group membership across platforms; referenced in NooNAO materials | §10.1 (Portable Communities Protocol) |
| **Kevin Kelly** | Quote: "The only organization capable of unprejudiced growth, or unguided learning, is a network." | §10 intro |
| **Smartocracy** (2005 LANL whitepaper) | Social-network collective decision-making; "extreme decisioning" prior art; predates the term "liquid democracy" | §10.1 (Extreme decisioning) |
| **Loomio** | Influence on cooperative decision-making culture and facilitation patterns | §1 (Principles), §5 (Trust-breakdown patterns) |
| **Loomio / Enspiral** | Cooperative governance patterns, consent-based decision culture | §5.1 (Consent erosion) |

### Internal stack documents

These irl.coop design documents are referenced throughout and should be read alongside this kit:

- `cooperation-survey-templates.md` — the seven core + two optional surveys (§3.4)
- `onboarding-flow.md` — member journey from invite to first task (§0 companion)
- `FIRST-PILOT.md` — pilot boundaries and stage gates (§0 companion)
- `adversary-models-and-sector-fit.md` — threat profiles by sector and footprint settings (§3.1, §6.2, §9.1)
- `account-and-key-model.md` — Safe ownership, passkeys, session keys (§4.2, §4.4)
- `group-scoping.md` — RLS model, seats, and resource scopes (§4.1, §4.3)
- `needs-offers-matching.md` — mutual-aid matching engine (§3.4, §10.2)
- `delegation-and-session-keys.md` — scoped grants and proxy delegation (§10.3)
- `custody-chain-and-contest-kit.md` — evidence reserve for liability disputes (§6.2)
- `REALITY.md` — current implementation state; read before promising anything (§1)
- `RISKS.md` — top risks to group safety and stack integrity (§1, §6.2)
- `BACKLOG-TRIAGE.md` — `B-` items referenced throughout; honesty about gaps is required (§1, §4.4, §10.3)

### How to update this section

If you add a new external framework, quote, or concept to this kit, add a row to the external table and cite the specific section where it appears. If the attribution is indirect (e.g., a concept learned through a workshop or conversation, not a published source), note that in the "What we drew from" column.
