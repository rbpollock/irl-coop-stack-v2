# DECISIONS.md — decision register

Status: checkpoint register · 2026-09-29.
Purpose: record what is settled, what is tentative, what is open, and what was
rejected — so a returning maintainer does not re-litigate settled questions or
mistake a design document for an implemented feature.

"Established" means the decision is implemented or is firm policy across the
repository. "Tentative" means decided in conversation but not yet reflected in
code. Owner/steward is "Owner" throughout: at the checkpoint date there is one
maintainer and no co-steward — recorded as a risk (RISKS.md R-01).

## Established decisions

| ID | Decision | Status | Why it matters | Evidence / source | Revisit trigger | Owner / steward |
|---|---|---|---|---|---|---|
| D-01 | **A group is a Safe.** Individual = 1-of-1, group = N-of-M; "create a group" and "deploy the account Safe" are one event. | Established | One primitive for identity, account, and governance | `group-scoping.md:9-11`; `apps/coop-api/src/safe.ts` | If Safe deployment cost or key recovery blocks onboarding | Owner |
| D-02 | **One Keycloak realm is the single identity source.** Google is brokered through Keycloak, not a direct frontend provider. | Established | One issuer for every app; no per-app identity silos | `AGENTS.md`; `STATUS.md` identity pillar | If brokering breaks recovery for members | Owner |
| D-03 | **Membership is a set, not a tree.** Every relationship is declared; nothing is inherited. | Established | Determines how groups compose and how access resolves | `account-and-key-model.md:164`; `event-bus-and-group-shapes.md:146` | Never — this is the model's core | Owner |
| D-04 | **Relationships are edges, not columns.** The graph is committed and proven, not stored as foreign keys. | Established | Explains why the group graph is not in the database schema | `zk-membership-graph-proofs.md:62` | If a plaintext edge table is ever proposed | Owner |
| D-05 | **Hidden is the norm** — membership is provable, not enumerable. | Established | Drives the ZK proof requirement from "later" to core | `group-scoping.md:60-70` | If most groups turn out to be `open` | Owner |
| D-06 | **Declarative infrastructure.** The instance tree is the source of truth; generated output is never hand-edited. | Established | Makes the stack reproducible in principle | `AGENTS.md`; `STATUS.md` config flow | If a service cannot be expressed in the tree | Owner |
| D-07 | **Two-tier secrets** — derived keys (HKDF from `master.key`) for everything generated; an ansible vault for external secrets. | Established | No plaintext secrets in the tree | `AGENTS.md`; `infra/build/secrets.py` | Never | Owner |
| D-08 | **No TEEs, no Lit, no cloud KMS** — pure cryptography only. | Established | Constrains every custody and privacy design | `AGENTS.md` ("Do not") | Never | Owner |
| D-09 | **Postgres RLS is the enforcement point** — no application-level bypass. | Established | Data isolation does not depend on app correctness | `infra/compose/storage/scripts/coop_rls.sql` | If a service cannot connect under RLS | Owner |
| D-10 | **One shared Citus Postgres and one shared Redis**, keys prefixed per service. | Established | One store to back up, one to reason about | `AGENTS.md`; `apps/*.yaml` | If contention or blast radius demands splitting | Owner |
| D-11 | **Matrix federation is OFF.** | Established | "Public" currently means any irl.coop account | `AGENTS.md`; `group-scoping.md:134-136` | When the federation design is revisited (parked) | Owner |
| D-12 | **SMS receipts are deliberately not emitted to the event bus.** | Established | Prevents one text becoming one email per member | `AGENTS.md` SMS spine | When a delivery policy is chosen (D-27) | Owner |
| D-13 | **The platform is a steward, not root.** Groups are autonomous; signup ≠ membership; funds are opt-in. | Established | Sets the governance posture of the whole project | Owner | Never | Owner |
| D-14 | **Delegation is session keys, not custody.** | Established | A platform delegate never holds a member's keys | `docs/design/delegation-and-session-keys.md`; Owner | Never | Owner |
| D-15 | **Gandi DNS with acme.sh + a custom LiveDNS hook.** | Established | Certificate renewal depends on it | `AGENTS.md`; `infra/scripts/dns_gandi_livedns.sh` | If renewal fails twice in a window | Owner |

## Tentative decisions

| ID | Decision | Status | Why it matters | Evidence / source | Revisit trigger | Owner / steward |
|---|---|---|---|---|---|---|
| D-16 | **A seat's holder is a Safe** — the subject's 1-of-1 Safe for a person, another group's Safe for nesting. | Tentative (in conversation; not implemented) | Unifies person↔group and group↔group membership in one mechanism | Today `group_members.sub` is a Keycloak subject; `coop_is_member` compares `coop_current_sub()`; `coop_ensure_personal_group()` already mints the 1-of-1 Safe | If acting-as-Safe resolution proves unreliable for multi-Safe members | Owner |
| D-17 | **The pilot is two-stage**: Stage 1 runs now (one farm coop; no money, no nesting); Stage 2 adds the collective and real money. | Tentative | Lets real learning happen without waiting on the chain decision | Conversation 2026-09-29; see `FIRST-PILOT.md` | If Stage 1 finds the seat model unusable for farms | Owner |
| D-18 | **The pilot's eventual group shape is a meta-group** — a collective containing several farm coops. | Tentative | Requires group-of-groups, which D-16 would make possible | Owner | If farm coops prefer to stay unnested | Owner |
| D-19 | **Money is the pilot's headline proof.** | Tentative (currently impossible) | Owner's stated priority; the repository cannot move a dollar | Owner; `money-in-and-out.md` §0 | When D-21 is decided | Owner |
| D-20 | **LiteFarm is the agricultural vertical**; farm = group. | Tentative | The pilot's farm path runs through it | `apps/litefarm.yaml`; fork branch `irl-coop-integration` | If the farm pilot uses different tooling | Owner |

## Open decisions

| ID | Decision | Status | Why it matters | Evidence / source | Revisit trigger | Owner / steward |
|---|---|---|---|---|---|---|
| D-21 | **Which chain.** | Open in the design doc — but **already pinned in configuration**: `apps/coop-api.yaml` sets `PAYMENTS_CHAIN_ID: 8453` (Base) and `src/payments.ts` hard-gates on it | Money cannot be designed without it; the configuration has effectively answered it for the payment path | `money-in-and-out.md` §0 calls it open; `apps/coop-api.yaml:96`; `src/payments.ts:230` | If the owner rejects Base for custody, fee, or jurisdictional reasons | Owner |
| D-22 | Which CRM: ERPNext-native or Twenty. | Open | Two CRMs contemplated; one is already live | `AGENTS.md` pending list | Before adding Twenty | Owner |
| D-23 | Frappe Insights data source: row-level coop data (bypasses RLS) or aggregates only. | Open | A direct Postgres source would bypass RLS | `AGENTS.md` pending | Before any reporting build | Owner |
| D-24 | Which single value proof the first pilot must establish. | Open — owner unsure, leaning fundraising | Determines the pilot's success criteria | Conversation 2026-09-29 | Before Stage 1 starts | Owner |
| D-25 | Blueprint library hosting: central or federated. | Open (parked with federation) | Affects the library's durability | `event-bus-and-group-shapes.md` §3.3 | When federation is unparked | Owner |
| D-26 | DMARC: stay `p=none` or move to `quarantine`. | Open | Deliverability vs false-positive risk | `AGENTS.md` pending | After real mail volume is observed | Owner |
| D-27 | Notification delivery policy (per-message vs digest). | Open | Decides whether domain events mail members | `AGENTS.md` SMS spine note | Before enabling SMS delivery | Owner |
| D-28 | Backup strategy. | Open — none exists | No Citus or MinIO backup anywhere | `REALITY.md`; RISKS.md R-07 | Immediately | Owner |
| D-29 | Succession: who can recover the domain, the GitHub account, and the host. | Open — owner answer was "maybe" | Determines whether the project survives a 2-year gap | Owner | Immediately | Owner |
| D-30 | Federation / takedown-resilient DNS+edge. | Open — **PARKED**, do not design until raised | Large architectural surface | `AGENTS.md` pending | When the owner raises it | Owner |
| D-31 | Coop launch + infrastructure handoff. | Open — **PARKED**; gated on the non-custodial vault fix | A handoff before the vault fix hands over the deed and keeps a copy of the keys | `docs/design/coop-launch-and-roadmap-handoff.md` | After the vault fix | Owner |
| D-32 | Parked integrations: Mautic + cal.diy; Twenty + Payload; Frappe Insights. | Open (intent recorded, not built) | Scope control | `AGENTS.md` pending list | When a partner needs them | Owner |

## Rejected / superseded

| ID | Decision | Status | Why it matters | Evidence / source | Revisit trigger | Owner / steward |
|---|---|---|---|---|---|---|
| D-33 | TEEs / Lit Protocol / cloud KMS. | **Rejected** | Removes a whole class of custody design | `AGENTS.md` ("Do not") | Never | Owner |
| D-34 | A direct frontend Google OAuth provider. | Superseded by brokering via Keycloak | One issuer, not several | `AGENTS.md` | Never | Owner |
| D-35 | TextBee-app for SMS. | **Out** | Signup must not auto-taint a DID | Owner | Never | Owner |
| D-36 | lego as the ACME client. | Rejected — Gandi's 40-char key format | Renewal would fail silently | `AGENTS.md` | Never | Owner |
| D-37 | The `surfy` v1 edge host. | Retired; this host supersedes it | Avoid reviving a dead environment | `AGENTS.md` LAN note | Never | Owner |
| D-38 | Upstream Cal.com. | Rejected — closed source; the MIT fork (cal.diy) is the choice | Licence and self-hosting | `AGENTS.md` pending | Never | Owner |
| D-39 | S3 `PutBucketCors` for MinIO CORS. | Not implementable (returns 501); superseded by `MINIO_API_CORS_ALLOW_ORIGIN` | Cross-origin access has exactly one working path | `AGENTS.md` quirks | Never | Owner |
| D-40 | One shared oauth2-proxy cookie name. | Superseded by unique per-app cookie names | Shared names poison fleet-scoped cookies | `AGENTS.md` quirks | Never | Owner |
| D-41 | `plane-minio`. | Retired; Plane uses the coop object store | One store, one backup | `AGENTS.md` | Never | Owner |