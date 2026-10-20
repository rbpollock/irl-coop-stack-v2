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

---

## 6. Security, custody, and onboarding — added 2026-10-19

Source: two adversarial reviews (`whole-system-adversarial-review.md`,
`security-review.md`), the code-verified verdicts in `security-review-open-questions.md`, the
custody plan (`custody-and-agent-keys.md`), and the onboarding reality check
(`onboarding-flow.md` §9). Findings are prefixed `F<n>`; onboarding steps `O<n>`. Same shapes
as §3. **No issue was created** — this is a proposed list.
**Numbering note:** the two reviews number findings independently, so `F10` is not the same
finding in each. Where they collide this list qualifies it — *on-chain F10* = the dead handover
ABI (`security-review.md`); *whole-system F10* = role truncation (`whole-system-adversarial-review.md`).

### B-11 — A member's Safe is passkey-owned at creation  ← **the keystone**
- **Labels:** `security`, `financial-high-risk`, `pilot-critical`, `architecture-decision`
- **Why:** today every personal Safe is deployed **1-of-1 owned by the platform backend key**
  (`provisioning.ts`, `safe.ts`), and the only route that could hand it over is unbound to the
  caller *and* non-functional (`safe.ts` calls `nonce()`/`getTransactionHash()` on an ABI that
  declares neither). So the platform is the permanent custodian of every member's money, and
  any member can seize any other member's Safe (`F1`, `F7`, `F10`). One change fixes all three
  and makes onboarding's Step 1 true.
- **Depends on:** a `PasskeyOwner` (EIP-1271) owner type; the mainnet deploy (`mainnet-deploy.md`)
  for real use.
- **Done when:** a new personal/group Safe is created with the member's `PasskeyOwner` as the
  sole owner from block zero; the platform EOA only sends the tx; `/api/safe/sovereign` is
  retired (or fixed to bind `saltNonce` to `claims.sub`); the journey asserts the owner set is
  the passkey and **not** the backend, and that a second member's attempt to claim it fails.
- **Work type:** implementation + verification.

### B-12 — Authorize `/api/safe/session/execute` and harden the session module
- **Labels:** `security`, `financial-high-risk`, `agent-high-risk`
- **Why:** the route has authentication but **zero authorization** (no seat/grant check), and the
  module lets `F2` be exploited two ways: a declared `amountIn` makes the budget a no-op
  (`cost = token==0 ? value : amountIn`), and `operation=1` (delegatecall) runs attacker code in
  the Safe's context. Allow-list defaults off; no session expiry (`F2`, and `custody plan P0`).
- **Depends on:** nothing.
- **Done when:** the route requires the caller to hold a seat + the origin **invite/grant** in the
  module's group; `operation` is dropped or allow-listed; spend is bounded by parsed calldata (or
  the declared amount is removed); the allow-list is **denied by default**; a session has an
  expiry; and each bypass is a red-then-green test.
- **Work type:** implementation + verification.

### B-13 — Attest `groups.safe_address` (D-16 seat integrity)
- **Labels:** `security`, `architecture-decision`
- **Why:** `groups.safe_address` is member-writable (RLS permits it), and the whole seat model
  resolves through it — so a member can insert/update a group carrying a victim's Safe and
  inherit their seats (`F3`). It also relates to `B-06`.
- **Depends on:** an on-chain `getOwners()`/EIP-1271 check.
- **Done when:** `safe_address` is written only by a `coop_ops`-locked definer after verifying the
  address's on-chain owner; a `UNIQUE(safe_address)` exists; the psql spoof test fails.
- **Work type:** implementation + verification.

### B-14 — Make the JWT layer fail closed
- **Labels:** `security`
- **Why:** `verify-jwt.ts` falls back to a **hardcoded HS256 secret** when the RS256 key is unset
  (`F4`; latent today because the key *is* set), and **no verify path checks `aud`** (`F5`), so a
  fleet client's id_token or the 30-day cookie is a general Bearer.
- **Depends on:** nothing.
- **Done when:** the process refuses to boot without `COOP_JWT_PRIVATE_KEY_B64`; algorithms are
  pinned; `audience` is checked; a forged-HS256 token and a cross-audience token both 401.
- **Work type:** implementation + verification.

### B-15 — Session cookie lifecycle (revocation + shorter life)
- **Labels:** `security`
- **Why:** the 30-day `coop_session` is a stateless, domain-wide Bearer that survives logout and
  even Keycloak user deletion on the API path (`F6`).
- **Depends on:** nothing.
- **Done when:** logout revokes server-side (jti/denylist) or the TTL is short with refresh; a
  post-logout and post-deletion replay both 401.
- **Work type:** implementation + verification.

### B-16 — Stop reflecting any `*.irl.coop` origin with credentials
- **Labels:** `security`
- **Why:** `server.ts` CORS reflects any `irl.coop` subdomain with `credentials: true`, so one
  compromised subdomain can read `api.irl.coop` responses as the user — a fleet amplifier.
- **Depends on:** a list of the real origins.
- **Done when:** CORS allows only the enumerated dashboard/api origins; a random `*.irl.coop`
  origin is refused.
- **Work type:** implementation.

### B-17 — Split the Keycloak client (public vs admin) and stop forcing `emailVerified`
- **Labels:** `security`, `operations`
- **Why:** one client secret drives the browser auth-code/password flows **and**
  `realm-management/manage-users` (`F8`), and the email rewrite forces `emailVerified: true`.
  Blast radius is the whole realm.
- **Depends on:** a realm-config change.
- **Done when:** two clients exist (public + admin, admin secret vaulted); the browser flow uses
  the public one; `email_verified` reflects Keycloak truth, not a default (`F9`).
- **Work type:** configuration.

### B-18 — Order and harden the username claim
- **Labels:** `security`, `usability`
- **Why:** a member can claim any unclaimed `<name>@irl.coop` with **no proof of mailbox
  ownership**, so invites addressed there are redeemable by whoever claims first (`F14`), and via
  `matrix.ts` a claim can seize the matching Matrix identity (`F11`). This is `O4`.
- **Depends on:** B-11 (identity at creation).
- **Done when:** the claim is ordered before invites are redeemable; `@localpart` cannot resolve to
  another member's account; the collision journey fails clean.
- **Work type:** implementation + verification.

### B-19 — Bind the DB role to the sub (or widen the derivation)
- **Labels:** `security`
- **Why:** `coop_m_<sub8>` truncates the sub to 8 alnum chars (≈32 bits) and `withIdentity` never
  checks the role maps back to the caller's sub (`F10`).
- **Depends on:** nothing.
- **Done when:** `withIdentity` verifies `coop_member_role.sub == request sub`, or the derivation is
  collision-free; the collision property test passes.
- **Work type:** implementation + verification.

### B-20 — Consent: capture and record
- **Labels:** `pilot-critical`, `usability`, `needs-evidence`
- **Why:** the design promises a terms hash recorded at onboarding (`onboarding-flow.md` §4 Step 6)
  and the invitation doc's §4.3 consent depends on it. **Zero code exists** (`O2`).
- **Depends on:** nothing.
- **Done when:** onboarding records a consent artefact (hash + timestamp) and a member can see it.
- **Work type:** implementation.

### B-21 — Recovery / succession named at formation
- **Labels:** `pilot-critical`, `operations`
- **Why:** the design asks "who carries this forward?" (`onboarding-flow.md` §4 Step 5). **Zero
  code exists** (`O3`); it is also what `D-42` eventualises.
- **Depends on:** B-11.
- **Done when:** a member can name a recovery contact at formation and it is stored + visible.
- **Work type:** implementation.

### B-22 — Give `proposals`/`votes` RLS
- **Labels:** `security`
- **Why:** they carry no RLS and are granted to `coop_app` (the SQL file says so itself, "TODO").
- **Depends on:** nothing.
- **Done when:** both tables have FORCE RLS + policies like the rest; a cross-group write fails.
- **Work type:** implementation + verification.

### B-23 — Fail closed on unresolved `${ENV}` OIDC client secrets
- **Labels:** `security`
- **Why:** an unresolved `${VAR}` stays as the literal string, usable as a valid `client_secret`
  (`F12`).
- **Depends on:** nothing.
- **Done when:** boot refuses an unresolved reference; the literal no longer authenticates.
- **Work type:** implementation.

### B-24 — Auth hygiene bundle
- **Labels:** `security`, `operations`
- **Why:** `F15` — no rate limit on `/api/auth/login`, unbounded in-memory code store, uncached
  JWKS, nonce never verified, `Host`-header trust for cookie flags, logout CSRF.
- **Depends on:** nothing.
- **Done when:** each item has a mitigation + a test (k6 for the login lockout; unit for nonce/exp).
- **Work type:** implementation + verification.

### B-25 — Dynamic test pack for the above (supports B-08)
- **Labels:** `needs-evidence`, `pilot-critical`
- **Why:** the reviews name the tests; none exist yet. This is `O5` plus the security journeys, and
  it is what turns breadth into proof. Feeds `B-08` (invite + onboard one real person).
- **Depends on:** from B-11 onward, added test-by-test.
- **Done when:** the sovereign-hijack, session-execute-abuse, RLS-spoof, token-confusion, and
  onboarding journeys run in `journeys.sh` and pass after their fixes.
- **Work type:** verification.

## 7. Ranked priority (added 2026-10-19)

Ranked by *what must be true before anything of value rests on it*, cheapest first within a
tier. Nothing here is on fire today (the platform holds no funds); all of it is due **before**
the first dollar and the first real member.

| # | Task | Fixes | Size | Depends |
|---|---|---|---|---|
| 1 | **B-11 Passkey-owned Safe at creation** | F1, F7, on-chain F10, O1, P1 | medium | PasskeyOwner; mainnet |
| 2 | **B-12 Session-execute authz + module** | F2, P0 | medium | — |
| 3 | **B-14 JWT fail-closed + audience** | F4, F5 | small | — |
| 4 | **B-15 Session-cookie lifecycle** | F6 | small–med | — |
| 5 | **B-16 CORS origins** | new (CORS amp) | small | origin list |
| 6 | **B-13 Attest `safe_address`** | F3 | medium | on-chain check |
| 7 | **B-17 Keycloak client split** | F8, F9 | small | realm config |
| 8 | **B-18 Username claim hardening** | F14, F11, O4 | medium | B-11 |
| 9 | **B-19 Bind DB role→sub** | whole-system F10 | small | — |
| 10 | **B-24 Auth hygiene bundle** | F15 | small each | — |
| 11 | **B-22 RLS for proposals/votes** | (new) | small | — |
| 12 | **B-23 OIDC_CLIENTS fail-closed** | F12 | small | — |
| 13 | **B-20 Consent capture** | O2 | small | — |
| 14 | **B-21 Recovery named at formation** | O3 | small | B-11 |
| 15 | **B-25 Dynamic test pack** | O5 | medium | alongside B-11… |
| 16 | **B-26 Modular accounts (7579/6900)** | P3 | large | future |
| 17 | **B-27 Group sovereignty / service accounts** | P4 | large | `group-operated-stack.md` |

**Why this order.** Items 1–5 are the identity and custody spine: with them, a member provably
owns their Safe, the agent can't drive it arbitrarily, and the token layer can't be forged or
replayed. Items 6–9 close the data-integrity and blast-radius holes behind that spine. Items
10–12 are cheap hardening. Items 13–15 complete onboarding and make all of it *proven*. Items
16–17 are structural and can wait.

**Note:** everything on-chain (1, 6, 8, 14) depends on the mainnet deploy
(`mainnet-deploy.md`) — but each can be built and tested on devnet now.