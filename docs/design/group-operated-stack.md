# Operating the stack from within — successorship is a group

Status: **design (direction accepted)** · 2026-10-12 · Robbie + Hermes.
Supersedes the framing of **B-04** ("name a successor") and **D-29** ("who can recover
the domain, the GitHub account, and the host"). Un-parks the substance of
**D-31** / `coop-launch-and-roadmap-handoff.md` (its gate — the non-custodial vault —
still stands, and is now item 2.1 below).
Builds on: `irl-coop-group.md` (the coop as a group Safe), `group-secret-vault.md`
(threshold-encrypted group secrets), `delegation-and-session-keys.md` §2 (the no-bypass
invariant), `infra-management-monitoring.md` (declared-vs-running), `treasury-relayer`
+ `private-treasury-guards-ledgers.md`, `coop-launch-and-roadmap-handoff.md` §4–§6.

## 0. The decision in one paragraph

**There is no successor. There is a group.** The irl.coop group is created with the
stack's own tools — a group Safe, like any other account — and the entire stack is
designed to be operated *by that group, from inside the stack*. Members are recruited
into it, and the group's continuity is what outlives any individual. Successorship stops
being a person's willingness and becomes a property of the group: how many members it
has, whether every needed role is filled, whether it can still act if one member is
unavailable. Where a group has a single member that is **permissible** — but it is
**flagged as needs-improvement by the group-health metric** (§5), so a one-member
operator is visible rather than indistinguishable from a healthy one.

The doctrine that follows, stated as the invariant to preserve:

> **No management path may depend on someone outside the group.**
> This is the no-bypass invariant of `delegation-and-session-keys.md` §2 — no service
> identity, no system role, no privileged back door — raised from the database to the
> infrastructure. Every capability the stack has today (DNS, certs, deploys, secrets,
> backups, money, the host) is either *moved inside*, *held by the group under
> threshold*, or *named in writing as an accepted concentration*.

## 1. What changes

| Before | After |
|---|---|
| Bus factor 1 is a **person** risk (R-01); the mitigation is a named second person (B-04) | Bus factor is a **group-health** property; the mitigation is recruitment + role coverage |
| Infrastructure control is **transferred to** a group at some future handoff (§6.2 inventory) | Infrastructure control is **born inside** the group; the handoff framing dissolves |
| The stack is operated by its builder via `ssh`, `npm run dev`, `git push` | The stack is operated *in-product*, through the group's own surfaces and thresholds |
| Money is the **ambition** path (D-19), separable from the learning path | Money is **infrastructure**: a group with no externalities pays for its own hosting from its own treasury (§6) |
| "Signup ≠ membership" (D-13) vs invite-on-first-signin (`irl-coop-group.md` §2) | Must be resolved — recruitment is the succession mechanism, so membership is deliberate (§4.3) |

**And one genuine collapse of scope:** the coop's own work, tracked in a Plane project
owned by its own group Safe, is *the first group that is not a demo*
(`coop-launch-and-roadmap-handoff.md` §2). Standing the coop up is therefore itself the
first real-user test — it satisfies the "zero real-user evidence" gap (R-15) without
waiting for an external pilot group.

## 2. The hard part: the bootstrap recursion

To run the stack from inside the stack, every capability the stack currently receives
from outside it must become group-held. But the machinery that would grant that
authority is the machinery you are trying to reach: **you cannot rotate the certificate
that lets you reach the group that authorizes the rotation.**

This is not a reason not to do it. It is the reason the work must be an **inventory with
a migration path per row**, not a slogan. Every row falls into one of three classes,
and they behave differently.

### 2.1 The capability inventory

Verified against the tree and the live host on 2026-10-12.

| Capability | How it works today | Class | Target |
|---|---|---|---|
| **Identity / SSO** | Keycloak realm + coop-api + the gates | **1 — already inside** | Done. The group's authority rests on it |
| **Membership, roles, votes** | `group_members` + `grants`/`role_grants` + `coop_rls.sql`; `decisions.ts` | **1 — already inside** | Done (governance is Safe-governed per `irl-coop-group.md` §1.4) |
| **Monitoring / status** | `stack-report.py` + `GET /api/v1/stack/status` + motd + dashboard "Stack health" | **1 — already inside** | The group's instrument panel. Extend with §5 metrics |
| **Mail / DKIM** | Stalwart, in-stack | **1 — already inside** | Done (its DNS records are class 2 below) |
| **Matrix / comms** | Synapse + Element + appservice, in-stack | **1 — already inside** | Done |
| **Secrets** | `master.key` → HKDF → `${SECRET:…}`; ansible vault for external secrets; **and `group_vault_secrets` encrypted with ONE platform-held key** (`apps/coop-api/src/vault.ts:43`, `pgp_sym_encrypt(…, current_setting('app.vault_master_key'))`) | **1 target — currently class 2** | **The precondition.** k-of-n group vault (`group-secret-vault.md`), quorum to decrypt. No threshold implementation exists in coop-api today |
| **DNS records** | Gandi LiveDNS via a 40-char API key, used by `dns_gandi_livedns.sh` | **1 target** | **The group holds the registrar account** (owner, 2026-10-12: *registrar can be handled by the group*): the account and its key are group-held, records stay as code in the tree, and an in-stack worker renews. Aim: a DNS layer the group can move (§2.3) |
| **Certificate renewal** | `acme.sh` + custom Gandi DNS-01 hook, daily 03:30 cron on the host | **1 target** | An in-stack job. Its input (the DNS key) is the row above |
| **Deploys** | A person runs `generator.py` + `docker compose up` + a Traefik restart | **1 target, class-2 boundary** | An in-stack runner with a scoped, logged, group-authorized apply. The boundary is the container runtime |
| **Backups** | **Nothing exists.** The only copy of the repo is an 84 MB bundle at `/home/service/backups/` on the *same disk* (25 GB free of 468 GB), predating everything after 2026-09-29 | **1 target** | An in-stack backup job; the off-host destination is class 2/3 |
| **The repository** | One personal GitHub account | **2** | A group-held org; the group's seats hold membership |
| **Control of root authority** | `ssh` + `sudo` on one machine; root is a login a person has | **1 target** | **Decentralized root** (owner’s correction, 2026-10-12): §10’s group-authorized short-lived certificates, no standing root; then, as the stack becomes orchestrated (a swarm or other virtualised stack), the unit is a **container** and root-equivalent authority is a **group-governed orchestration permission**, not a login to a machine |
| **Host processes** | irl-dashboard and coop-api run as host `npm run dev` processes | **2 → 1** | **Must move into the stack** — a developer's shell is exactly the privileged path this doctrine removes (also the prerequisite for B-01) |
| **Money in / out** | `payments.ts` + peer_xyz rail (`:3010`) + `CoopUsdcRouter` + treasury-relayer; chain pinned Base `8453`; **4 attempts, all failed**; router undeployed; the destination key's custody is *recorded nowhere* | **1 target** | The group's treasury pays for the group's hosting. Gates in §7 stand |
| **Telephony / DIDs** | No gateway deployed, no DID held | **2** | Carrier account held by the group when it is bought |
| **KYC / a legal personality for the group** | No entity exists | **2 — hard, not unachievable** (owner, 2026-10-12) | A group-held entity with **revocable signatories** — appointed by role grant, never a name in code — funds to the group’s Safe. Aim: a legal personality the group can move between providers, then offered as a service so groups need not each form one |
| **The physical machine, its pipe, and the jurisdiction the coop is organised in** | One machine, one ISP, one country | **3 — concentrated at present, each with an aim (§2.3)** | **Named in writing** (an unwritten reservation is indistinguishable from a hidden one). No row here is accepted as permanent |

### 2.2 The three classes, stated plainly

1. **Moves inside, or becomes a group-held resource** — the whole table, with the owner’s
   corrections of 2026-10-12. **Registrar, KYC and host root are targets, not exceptions.**
   The registrar is handled by the group; KYC is hard but not unachievable (§2.3); and root
   authority is **decentralized** — the group’s threshold *is* root, expressed over a
   machine today and over a container in an orchestrated stack.
2. **Held by the group under threshold, exercised through the stack** — external accounts
   that cannot be "inside" without some privileged path (a registrar API, a code host, a
   payment provider). The path stays; **the unilateral hand goes.** The rule: *the hand is
   fine; the unilateral hand is not.* Every such row carries a mitigation pathway and an aim.
3. **Concentrated at present, with a stated aim — never accepted as permanent** — the
   physical machine, the pipe, the legal jurisdiction the coop is organised in, the chain.
   Named in writing, because an unwritten reservation is indistinguishable from a hidden one
   (`coop-launch-and-roadmap-handoff.md` §6.5). **This list is published, deliberately**
   (owner, 2026-10-12: *we will not survive security from obscurity — we just have to design
   better*): a concentration the group can see is one it can plan around; a hidden one is the
   externality this document exists to remove.

### 2.3 Concentrations: mitigation pathway and decentralization aim

Owner's refinement, 2026-10-12: *"Concentrations will all have mitigation pathways and
clearly defined decentralization aims."* So no row is "irreducible and therefore accepted".
Each carries **what reduces it now** and **where it is heading** — the second of which is a
direction of travel with a trigger, not a slogan. (Precedent for the framing: Base's own
Stage 0/1/2 decentralization staging in `chain-risk-and-portability.md`.)

| Concentration | Today | Mitigation pathway | Decentralization aim (advances when) |
|---|---|---|---|
| **One host, one disk** | 25 GB free of 468 GB; 51 first-party images exist nowhere else; no off-host copy | Phase 0: off-host backup + images exported; the tree is already declarative, so a host is a config | **A second node**, then N nodes — any group able to run one (this *is* "enable other groups to do this too"). Advances when Phase 0 is done and a clean-host bring-up succeeds |
| **The pipe** (ISP → router → `192.168.18.20`) | One address, one router, one ISP | DNS records are in the tree; the wildcard cert and a documented record set make a host move a DNS flip + a bring-up; the DNS key is group-vaulted (Phase 2) | **Host-independence** — moving the stack is a same-day operation with a runbook. Advances when a bring-up runbook is exercised on a second host |
| **The registrar and its jurisdiction** | Gandi, one 40-char API key, one account | **The group holds the account** (owner, 2026-10-12); records are code in the tree; registrar lock and transfer auth held by the group, not a person | **A DNS layer the group can move** — a second registrar or a self-hosted authoritative NS as a warm standby, so jurisdiction is a choice rather than a fact. Advances in Phase 2 |
| **The code host** | One personal GitHub account | A group-held org (§9); members hold seats; a bundle mirror committed to the tree | **Mirror-first** — no single forge holds the history. Advances when the org exists and the mirror job runs |
| **KYC / the payment entity** | No entity exists | The group appoints a **revocable signatory** by role grant (never a name baked into code); funds land in the group’s Safe, not a person’s. *Hard for a group, but not unachievable* (owner, 2026-10-12) | **A legal personality the group can move** between providers and jurisdictions, then **offered as a service** so no group has to form one (the duna / fiscal-sponsor shape). Advances at the first group that needs it — the fiscal pitch’s substance, not a side quest |
| **Control of root authority** | `ssh` + `sudo`, one person; root is a login | §10: group-authorized, short-lived SSH certificates; every privileged act time-boxed and logged; the **group’s threshold, not a person, holds the capability** | **Decentralized root** — the group’s threshold is the only root; then, in an orchestrated stack (swarm / other virtualised), authority is a **group-governed permission over a container**, not a login to a machine. Advances at §10 + Phase 3.1 |
| **The vault's single platform key** | `pgp_sym_encrypt(…, app.vault_master_key)` — one key in coop-api | Phase 2.1: the k-of-n group vault | **No single key** — a quorum of member-held shares. Advances in Phase 2.1 |
| **The chain** | Base `8453` (upgrade control is a 2-of-2 multisig + an 8-of-11 council; Base reached Stage 1 decentralization Apr 2025) | The router is ours and the chain is replaceable by design (`chain-risk-and-portability.md`) | **Documented portability**, exercised before a material amount is at stake. Advances at the first real treasury balance |

## 3. The honest limits — say these out loud

**a) "No external custodian", not "no external dependency" — and *group-held* is the floor,
not the aim.** Where a capability allows it, the aim is real decentralization rather than the
group acting as custodian. Root control is the clearest case (§2.1, §10): the target is not a
group that holds the machine, it is a machine whose only root *is* the group’s threshold.
The stack will keep
depending on a registrar, an ISP, a host, and a payment entity. What the doctrine
removes is *unilateral* control of them. Claiming independence from them would create
the very externality being removed, because the un-nameable dependency is the one that
cannot be handed over.

**b) A group holding a key is not a group able to operate — and this is a
requirement, not a limit.** Owner's steer 2026-10-12: *"we can totally fix the
capabilities moving into the UX for things that seem like necessary external
dependencies."* Agreed, with the condition that makes it true: putting the Gandi key in a
group vault does not make anyone able to run an ACME renewal. The capability has to move
into the UX, not just into a Safe. Without that the bus factor is not reduced — it is
**relocated** into a group of people who cannot act on it, which is the `§5` failure mode
wearing a better outfit. So **every class-2 row is a specification, not an excuse**: it
carries a mitigation pathway and a decentralization aim (§2.3).

**c) Recruitment is not succession by itself.** N members who are all new are not a
successor capability. Succession is N members **plus** the runbook being operable
in-product (§2.1 "Deploys"), plus the roles being filled (§5).

**d) A one-member group is a real state, not a failure.** It is permitted; it is
flagged. The metric exists so the gap is visible and improvable, not so it becomes a
gate.

## 4. Preconditions — what must be true before this is real

### 4.1 The vault is platform-custodial today (verified)
`apps/coop-api/src/vault.ts:43` encrypts group secrets with one platform-held symmetric
key. No threshold or share-splitting implementation exists anywhere in `apps/coop-api/src/`
(grepped). So today: **the group can hold the Safe while the platform holds the keys** —
the externality itself. `coop-launch-and-roadmap-handoff.md` §4 already names the vault
fix as a *precondition* for a meaningful handoff, not an adjacent task, and that stands.

### 4.2 The coop group Safe does not exist
Designed only: `irl-coop-group.md` (group Safe, deterministic address via the same
`SafeProxyFactory` + CREATE2 math already in `apps/coop-api/src/safe.ts`, initial owners
Robbie + 2 founding, **1-of-1 dev → 2-of-3**). No address is recorded anywhere.

### 4.3 The membership conflict must be resolved (one decision)
`irl-coop-group.md` §2 says every first signin becomes a member of the coop, with "no
join-request gate in dev". That contradicts **D-13** (signup ≠ membership) and it
contradicts this document: recruitment is the succession mechanism, so joining the
operating group has to be deliberate. Resolution options: (a) the coop is the default
landing seat *and* membership is explicit — a signin creates a seat, joining the group
is an accepted request; (b) the coop is open and recruitment is only about *roles*, not
membership. Recommendation: **(a)** — it preserves D-13 and makes the health metric
meaningful. **Resolved by the owner's model, 2026-10-12 (§11):** a signin creates a person
and a seat, never a membership; joining any of the coop's bodies is deliberate.

## 5. Group health metrics (new — the coop is instance #1)

Nothing in this repository defines group health (grepped: zero hits). This doctrine
needs it, and not only for the coop — **every group in the federation needs it**, so the
coop bootstrapping itself is the first instance of a general metric. Advisory, never a
gate (D-13: the platform is a steward, not root).

Candidate signals, each cheap to compute from state that already exists:

| Signal | Source that already exists | Needs-improvement when |
|---|---|---|
| **Member count** | `group_members` | **1 member** (explicitly: permissible, flagged) |
| **Active members** | seats + recent participation (events/notify lane) | fewer than 2 active in a window |
| **Role coverage** | `grants` / `role_grants` | a role the group's own definition requires is unfilled |
| **Quorum reachability** | governance design (Safe threshold) | the threshold cannot be met by currently-active members |
| **Key-loss resilience** | Safe owner set + threshold | one unavailable member can freeze the group |
| **Runbook coverage** | this document's §2.1 inventory | a dependency has no written procedure |

Reported on the group home beside the existing stack-health surface, and (per the
existing convention) in the same report the motd and dashboard already share.

## 6. What this does to the backlog — the re-scored priority list

The 2026-09-29 triage (`BACKLOG-TRIAGE.md` §5) ordered protect-first, then the two
verifications, then the ambition. This doctrine re-scores it. **Four calls were left
open and are taken here as defaults** (§8) — each is reversible.

### Phase 0 — Protect (days; everything else is recoverable, this is not)

0. **0.1 Commit the 13 days.** 85 changed/untracked paths; last commit 2026-09-29. A
   group cannot inherit work that exists only on one disk. (Also closes R-04.)
0. **0.2 A backup and a verified restore, with one copy off this host.** (B-02 / R-07.)
   Nothing exists today; the single artifact is on the only disk.
0. **0.3 Get the 51 first-party images retrievable off-host.** (B-03 / R-16.) New
   members cannot rebuild what exists only here.
0. **0.4 Finish the documentation corrections** (B-10) — done 2026-10-13: STATUS.md
   app-count/header corrected and the Comms & outreach section added; AGENTS.md's stale
   tailnet value was replaced with the live one; the `ConfidentialVoting.sol` phantom citations
   were marked as an as-yet-unbuilt design intent rather than a claimed existing primitive. One
   manual step remains: escrow `infra/instances/dev/secrets/backup-restic-pass` to the owner's
   password manager.

### Phase 1 — The group exists

Membership is now the branching idea in §2.1 of `invitation-and-join-mechanism.md`:
**membership = your Safe key**; a participant tier is the open door; permits and the payment
covenant are the group's own dials. Phase 1 runs the door:

1. **1.0 The on-ramp core** (builds the door) — schema/RLS + signed token; one token, any
   door (link/QR/email/SMS); the **grantable "invite" capability** with a per-inviter
   _may-assign_ set; a **participant** tier; **open permits** (capped, participant-only,
   self-revocable); a per-group **payment covenant** (nominal + waivable by default; a group
   may set its bar — the platform never does).
2. **1.1 The coop Safe exists** — the `@irl.coop` group + Safe at 1-of-1.
3. **1.2 Walk a real person through the door** — participant → member (Safe-owner admit),
   then promote to **2-of-3**. First real use, and proof the door works.
4. **1.3 Group-health v0** (§5) — the "1 member → needs-improvement" flag pays in live.
5. **1.4 Make the join deliberate, then open** — join-request & the open `participant`
   permit stay a coop dial: invite-only at first, weak-tie intake opened later with a cap.
6. **1.5 The roadmap as the group's first Plane project** — owned by the Safe, runs at
   1-of-1, and generates the daily-use bug list.

### Phase 2 — The keys come home (the precondition)

1. **2.1 The k-of-n group vault**, replacing the single platform-held key. The gate
   that D-31/`coop-launch-and-roadmap-handoff.md` has been waiting on.
2. **2.2 The capability inventory as work:** DNS key into the group vault + an in-stack
   renewal worker; deploys through a scoped in-stack runner; backups as an in-stack job
   with an off-host destination; the repo into a group-held org.
3. **2.3 Name the class-3 concentrations in writing**, with the break-glass procedure
   and the migration path per row.

### Phase 3 — The group operates (this is the proof)

1. **3.1 Move irl-dashboard and coop-api off `npm run dev` into the stack.** Removing a
   developer's shell as a management path is this doctrine applied, and it is also
   B-01's prerequisite.
2. **3.2 A clean-host bring-up from the repository**, using the group's own written
   runbook (B-01) — the first real test that the runbook is operable by someone who is
   not the builder.
3. **3.3 Run it, collect the bug list** — the coop is the first real detector (§1).
4. **3.4 Then the external Stage-1 pilot** (`FIRST-PILOT.md`) — unchanged, now second
   rather than first.

### Phase 4 — Gated / deferred

- **Money** moves from "ambition" (D-19) to **infrastructure**: a group with no
  externalities pays for its own hosting. The Stage-2 gates (`FIRST-PILOT.md`) still
  apply in full — custody of the destination key written down, a backup that exists,
  written risk bounds, legal treatment — and **the first real transfer must not be the
  transfer that funds the stack.**
- **Comms / outreach** gains a second purpose: it is now the **recruitment** channel
  for the operating group. Its own state is in `STATUS.md` § Communications.
- Parked and unchanged: federation (D-30), the parked integrations (D-32), Frappe
  Insights (D-23).

## 7. Do not

- Do not claim the stack is operated from within until §0's invariant actually holds —
  the vault, the host processes, and the deploys are the three that do not.
- Do not hide a class-3 concentration to make the story cleaner. Naming it is the
  doctrine.
- Do not treat a one-member group as either a failure or a success. It is flagged.
- Do not create the coop group Safe, transfer anything, or move the host processes on
  the strength of this note alone — the four defaults in §8 are the owner's to confirm.

## 8. Open — decisions taken as defaults (reversible)

| # | Question | Default taken | Reversal cost |
|---|---|---|---|
| 1 | When does the vault fix happen? | **First engineering item of the arc** (§2.1) — it is the externality itself | Low; it is a build order, not a design change |
| 2 | Host root / registrar / code host / KYC: inside or outside? | **All four are targets, not exceptions** (corrected by the owner, 2026-10-12): the **registrar is handled by the group**; **root authority is decentralized** — the group’s threshold is the only root, and in an orchestrated future it is a permission over a container rather than a machine login; **KYC is hard but not unachievable** via a group-held entity with revocable signatories; the code host is a group-held org (§9). Break-glass is named and documented, never relied on | High after a handoff |
| 3 | Who are the first members? | **Plan for one member (flagged), recruit from existing working relationships next** (§5) | None — recruitment is additive |
| 4 | What is this arc's proof? | **The coop operating itself first**, the external farm-coop pilot second (§1, Phase 3) | Low |
| 5 | Does the bootstrap-council's authority expire? | **Yes — scoped, enumerated, and it sunsets on a trigger** (§11.3). An invite-only council with unlisted "broad authority" is founder oligarchy wearing a democratic label | High after the coop is public; near-zero now |
| 6 | Where does the treasury's authority sit? | **The contributors' group**, not the council — the council's seat there is one seat, not control (§11.2). Otherwise "contributors decide allocation" is decorative | High — it is the difference between a real cooperative and a decorative one |
| 7 | Who admits a member to the users group? | **Human invitation on a costly+social+physical signal** (§11.4), never an automatic score | Low |

---

## 9. Service accounts: a member kind, never a platform identity

**Owner's requirement, 2026-10-12:** *"the github has to go inside the group. the group is
designed to hold service accounts (`admin@irl-coop.irl.coop`)."*

**This collides with a standing prohibition, and the collision is worth resolving in
writing rather than by quietly amending the older rule.** `member-scoped-app-access.md`
§1 says: *"no service identity, ever. If an app cannot be called as the member, it is not
wired — it is not wired read-only 'for now', because a read-only blanket credential is
still a blanket credential."* `delegation-and-session-keys.md` §2 and **D-14** say the
same thing from the Temporal side: no service identity, no system role.

The prohibition is aimed at a specific thing: **a credential that can act on its own,
across groups.** Both properties are what must stay forbidden. A group-held service
account is a different object, and it is legitimate only while it differs on all three:

| | Forbidden (the blanket credential) | Allowed (a group-held service account) |
|---|---|---|
| **Whose authority** | the platform's own | **exactly one group's**, derived from that group's grants — a **member kind**, not a platform identity |
| **Blast radius** | spans tenants | spans **one group** — the same radius as that group's members |
| **Recoverability** | opaque, long-lived, unrevocable | granted by a **group act**, revoked by a **group act**, every use logged as a distinguishable actor |

**The line, stated as a test:** if it can act for more than one group, or its authority
does not derive from a group's own grants, it is the forbidden thing — not a service
account. Store it in the group vault (`group-secret-vault.md`), bind it to a role grant,
and make its use a logged group act.

**Two consequences:**

1. **The stack's own service accounts are seats in the coop group.** `admin@irl-coop.irl.coop`
   is a service seat — held by the coop, scoped to coop resources, revoked by a coop vote,
   never human. It is how the coop touches its own stack without any individual holding a
   credential. Service seats are also why **R-12** (agent overreach) stays a live risk: the
   seat's scope is the control, and it must be narrow by default.
2. **The GitHub org credential is not an in-stack app credential at all.** GitHub is not
   one of our apps, so the `member-scoped-app-access` rule does not reach it. What reaches
   it is the group vault: the group holds an **org-level credential (or a GitHub App
   installation) as a class-2 external secret**, and using it is a group-authorized act
   through the session-key path. "GitHub goes inside the group" therefore means: the org
   is held by the group, members hold seats, and no individual holds the deploy credential.

## 10. A group mechanism for SSH and root

**Owner's suggestion, 2026-10-12:** *"maybe hooking keycloak up to the linux auth."* That
is the right instinct, and the shape that makes it a *group* mechanism rather than an
identity mechanism:

**Short-lived SSH certificates issued on a group-authorized grant.** Nothing standing.

1. **No static `authorized_keys` for humans, and no shared root password.** Static keys
   are the class-2 credential this doctrine exists to remove: unrevocable, unauditable,
   and invisible to the group.
2. **A login is an OIDC login.** The member authenticates to Keycloak as themselves (the
   same identity everything else uses), and an in-stack issuer mints a **short-TTL SSH
   certificate** — minutes to hours, never days.
3. **The authorization decision comes from group state, not from a config file.** Which
   principal, which host, which role, what TTL = a row in Postgres derived from the
   member's seat and `grants` in the coop group (`coop_my_seats()` → `role_grants` →
   `grants`, the resolver that already exists in `member-scoped-app-access.md` §2). Adding
   someone to the group grants them nothing until a role grant says so — and that grant is
   revocable.
4. **Root is not a login, it is a time-boxed grant.** `root` is a role whose grant
   requires a group act above a stated scope, carries a short TTL, and is logged. A
   standing root shell should not exist at all; the console on the physical machine is the
   documented break-glass (§2.3).
5. **Every session is a group act.** Session start/end, the certificate's fingerprint, and
   the commands are recorded, and the events flow to the existing bus → the coop's Matrix
   room. This is what makes it *democratic* rather than merely *authenticated*: the group
   can see who did what with the authority it granted.
6. **Root generalises to orchestration.** In a swarm or other virtualised stack the unit is
   a container, not a machine — so the same authority is expressed as a **group-governed
   permission** (who may deploy, scale, or reach a privileged container), held by the same
   threshold. Designing §10 as *group-authorized privileged access* rather than *SSH* is what
   makes it survive the move to an orchestrated host instead of needing a rewrite.
7. **The CA is itself a concentration.** Its root key is a group-vaulted secret with
   k-of-n shares (Phase 2.1) — otherwise the CA is the new single point, and we have moved
   the problem one layer down instead of solving it.

**Why this serves more than the coop:** every group that runs its own node needs the same
mechanism, so this is not bespoke infrastructure — it is the **first instance of a
per-group capability** (§2.3, second node). Design it once, in the group's terms.

## 11. The coop's governing bodies

**Owner's model, 2026-10-12:** an invite-only **bootstrap-council** with broad authority; a
**contributor** sub-group that raises funds and decides their allocation (with a council
seat on it); and a **users** tier that signup does not confer — joining requires enough
demonstrated activity to be *confidently human*, after which a member gets invited and
votes on decisions affecting users.

This resolves the §4.3 conflict the right way: **a signin creates a person and a seat, not
a membership.** So the coop's three bodies are **groups** (`subgroup-of` irl.coop, per
`account-and-key-model.md`: *member-of* = governance only, *subgroup-of* = governance +
infra, sharing the parent's namespace), because a group has its own Safe, threshold and
treasury — which is what makes the council's seat on the contributors expressible at all
(D-16: a seat's holder is a Safe). **No inherited visibility** between them (I10 in
`adversary-models-and-sector-fit.md`): being in the council does not reveal the users'
group's data.

There is also a working precedent to build on rather than invent: `capital-campaign-subgroup.md`
already designs *a subgroup that contributors become part of by contributing*, with the
`subgroup-of` / `sponsored-by` edges declared on the main group.

### 11.1 The clean three-way split (recommended)

"Broad authority" is the part to fix, because broad means unbounded, and unbounded is the
thing that cannot be handed over. The bootstrap need is real but narrow — it is **custody
and operation of the stack**, not everything. Splitting it three ways gives each body an
enumerated competence and a check on the others:

| Body | Holds | Explicitly cannot |
|---|---|---|
| **bootstrap-council** | infra custody (the group Safes, the vault, the SSH/CA grants, the runbook); admitting its own members; proposing constitutional amendments | spend the contributors' money; amend its own authority or the transition rules alone; read the users group's data |
| **contributors** | the treasury: raising funds and deciding their allocation; the roadmap as work | touch infra custody or the stack's privileged access |
| **users** | decisions that affect users — their data, their rights, features they depend on | touch money or custody |

**Rule: decide at the lowest tier the decision affects** (subsidiarity). A change to how
the stack is backed up is the council's; how the money is spent is the contributors'; how
their own group works is the users'.

### 11.2 Money must not be the council's
If the council controls the treasury, "contributors decide how it is allocated" is
decorative. The treasury's authority belongs to the contributors' group; the council's
seat there is **one seat**, with a veto only over a short enumerated class (e.g. a
solvency or legal-boundary breach) or none at all. This is the difference between a
cooperative and a company with a members' forum.

### 11.3 The bootstrap-council must not be able to entrench itself
An invite-only body with unlisted authority is a founder oligarchy wearing a democratic
label — **I7 relocated from one person to five**, which is the exact failure the doctrine
exists to prevent. So, from day one, in writing:

- **Enumerated authority** — the council's powers are a list (§11.1), not "broad".
- **A sunset on a trigger, not a date** — as the contributor and users groups reach stated
  sizes, council seats become **elected**, or the authority narrows to the enumerated infra
  list. A date would be arbitrary; a trigger is verifiable.
- **Two levels of decision** — *ordinary* (a tier decides) vs *constitutional* (thresholds,
  authority, the transition rules). Constitutional changes need the council **plus at least
  one other tier**: no body can amend the rules that constrain it alone.
- **The group-health metric flags it** (§5): council age, self-perpetuation, and the
  proportion of decisions taken without another tier. Add *council* to the health signals —
  the coop's own operator body should be the most scrutinised one, not the least.

### 11.4 "Confidently human" — costly + social + physical, and invited, not scored
Two failure modes to design against: the signal can **exclude** exactly the people the coop
wants (non-technical farmers, anyone without a digital trail), and it can be **gamed** (a
bot can complete tasks). So the signal should be evidence a bot cannot cheaply fake, and it
should accumulate from things a person is *already* doing:

- **social** — vouching from existing members (the recommendation is already in
  `adversary-models-and-sector-fit.md` §528: *"you cannot win, you can only shrink the blast
  radius: vouching, progressive disclosure, compartmentalised sub-groups"*);
- **physical** — a tie to the world: a number the coop controls at a node (`coop-accounts-and-phone-verification.md`), a real-world relationship, a farm-coop or movement contact;
- **costly** — verifiable work or participation with consequences, not volume of clicks.

And the last step stays **human**: an invitation from a member, not an automatic threshold.
A score that admits people automatically is a gate that cannot hear context; a member's
invitation carries the accountability the score cannot.

### 11.5 Service accounts in the membership model
Per §9, a service account is a **member kind**, not a person: a seat whose holder is not
human, whose authority is one group's, and whose existence is a revocable group act. It
appears in the member list (never as a person), it never counts toward "confidently human"
or human quorum, and a group whose governance depends on a service seat's presence is
flagged by the health metric.

## 12. What this adds to the backlog

Folded into the phases in §6, in this order: **§11's body definitions and the membership
resolution** (Phase 1 — they are design decisions, cheap now, expensive later); **§9's
service-account rule and the GitHub org** (Phase 2, with the vault); **§10's SSH/root**
(Phase 3.1, beside moving the host processes in — both remove the same operator shell);
**§11.4's personhood signal** (Phase 3, when there are people to invite); and **§2.3's
decentralization triggers** as the milestones that advance each concentration.

## 13. Do not

- Do not amend the "no service identity" rule in place — §9 is the reconciliation, and the
  test (one group, grants-derived, revocable) is the part that keeps it honest. A service
  account that spans groups is the forbidden thing under a new name.
- Do not give a static SSH key or a shared root credential to a new member "for now".
- Do not let the council’s authority be described as broad. Enumerate it or it is
  unbounded.
- Do not treat host root, the registrar, or KYC as permanent exceptions. They are targets
  with pathways (§2.3).
- Do not rely on the obscurity of the concentrations list. **It is published by design** —
  see §2.2 class 3.