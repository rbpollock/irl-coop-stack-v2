# Security review — verdicts and open questions

Companion to `whole-system-adversarial-review.md` and `security-review.md`. Records what is
**verified against the code**, and what still needs a live system. Updated after reading the
repo-local files (server.ts, coop_invitations.sql, provision-member-certs.sh, coop_group_base.sql,
username.ts, chat.ts, and the coop-api env names).

## Verified against the code (by reading, not by model claim)

| Finding | Verdict | Evidence |
|---|---|---|
| F1 — `/api/safe/sovereign` not bound to the caller | **Confirmed, LIVE** | `safe.ts`: auth only; `claims.sub` never compared to `saltNonce`; salt `keccak256("personal:"+sub)` is public (provisioning.ts). Safe env IS wired, so reachable. |
| F2 — `/api/safe/session/execute` auth-without-authz; `amountIn` + delegatecall bypasses | **Confirmed, LIVE** | route reads `target/data/operation/token/amountIn` from the body, no seat/grant check; module: `cost = token==0 ? value : amountIn`, forwards `operation`, `_allowed` true when `listEnabled` false |
| F3 — `groups.safe_address` writable → D-16 seat impersonation | **Confirmed mechanism + reachable** | see below; member cert DB path IS provisioned |
| F4 — hardcoded HS256 fallback secret, no alg pin | **Confirmed but LATENT** | `COOP_JWT_PRIVATE_KEY_B64` IS set in the live env → fallback not triggered today; still fails open if ever unset |
| F5 — no `audience` check on any verify path | **Confirmed** | `verify-jwt.ts` + `auth.ts verifyCoopJwt`: `{algorithms,issuer}` only; one key signs access tokens, the 30d cookie, and per-client id_tokens |
| F6 — 30-day session cookie is a live Bearer; logout/deletion don't revoke | **Confirmed** | `COOP_SESSION_TTL`/`maxAge 30d`; `verifyBearer` makes no Keycloak call; logout only clears the cookie |
| F7 — every personal Safe backend-owned 1-of-1 | **Confirmed, LIVE** | `deploySafe(signer, …, [signer.address], 1)`; `SAFE_BACKEND_SIGNER_KEY` is set |
| F10 — `coop_m_<sub8>` role truncation | **Confirmed** | `db.ts` and `provision-member-certs.sh` both take the first 8 alnum chars (the script calls it "stable, unique-enough") |
| F11 — Matrix localpart collision / username-claim hijack | **Confirmed** | `provisioning.ts` localpart + `M_USER_IN_USE` accepted; `matrix.ts` resolves `@localpart` → `<localpart>@irl.coop` → `getUserByEmail`; `username.ts` lets a member claim any unclaimed name |

### F3 — confirmed mechanism, reachable

- `groups_insert … WITH CHECK (created_by = coop_current_sub())` (coop_rls.sql:329) — no
  constraint on `safe_address`/`kind`; `groups_update … USING (coop_is_owner(id))` (331), no
  `WITH CHECK`. `coop_own_safe()` reads the column (162–168); `coop_current_safes()` seeds from it
  (185); membership/owner/seat helpers match by `holder_safe = ANY(current_safes)`. No
  `UNIQUE(safe_address)`; nothing attests the address's on-chain owner.
- **Reachability confirmed:** `provision-member-certs.sh` gives each member a LOGIN role + client
  cert (CN = role) + `coop_member` (which holds `INSERT/UPDATE` on `groups`) + a `coop_app` grant,
  and `pg_hba` matches `+coop_member`. Members therefore have direct DB connections that can do it.

### New (not in the reviews)

- **`proposals` / `votes` have NO RLS** and are granted to `coop_app` (coop_rls.sql:1373–1376,
  self-labelled "TODO: give these two RLS like the rest").

## Answers found in the repo (questions that were open)

**Env / secrets (live `.env` key list + `server.ts`):**
- `COOP_JWT_PRIVATE_KEY_B64` — **set** → F4 latent, not live. (`JWT_SECRET` also set.)
- `SAFE_SINGLETON_ADDRESS`, `SAFE_PROXY_FACTORY_ADDRESS`, `SAFE_BACKEND_SIGNER_KEY`, `RPC_URL` —
  **all set** → the safe routes are **live**; F1/F2/F7 are reachable today. `server.ts` logs the
  factory/singleton/RPC at boot, so the chain is confirmable live.
- `INVITE_SIGNING_SECRET` — set → invitations live. `OIDC_CLIENTS`, `COOP_SESSION_TTL`,
  `COOP_COOKIE_DOMAIN` — set. `COOP_OPS` is generator-derived into `secrets.env` (spec
  `${SECRET:coop.ops}`).

**`server.ts`:**
- `trustProxy: true`; **CORS reflects any `*.irl.coop` origin with `credentials: true`** → any
  compromised subdomain (or XSS there) can read `api.irl.coop` responses as the user — a fleet-wide
  amplifier for the cookie findings (F5/F6, chains C4/C5).
- **No rate limiting** (`@fastify/rate-limit` not registered) → F15(a) confirmed for
  `/api/auth/login`. No `helmet`. Swagger UI at `/api/docs` is public (route inventory disclosure).
- `setSessionCookie` trusts the raw `Host` header for its `secure`/`domain` decision.

**`coop_invitations.sql`:**
- `coop_invite_redeem` genuinely single-use: `SELECT … FOR UPDATE` + `status<>'pending'` + expiry
  (120–129). Good primitive.
- Members hold direct `INSERT`/`UPDATE` on `invitations`/`open_invitations`/`join_requests`
  (grants 149–152) — bounded by RLS to their own rows / owned groups; no clear escalation, but a
  wider direct-DB write surface than the API exposes.

**`username.ts` (the F9/F14 linchpin):**
- A member can claim **any unclaimed `<name>@irl.coop`** with **no proof of mailbox ownership**;
  the only gate is Keycloak uniqueness ("taken"), plus a tiny `RESERVED` list. So F14 holds: an
  invite addressed to `<name>@irl.coop` is redeemable by whoever claims that name first. Combined
  with `matrix.ts` (which resolves `@name` via `<name>@irl.coop`), claiming a name can also seize
  the matching Matrix identity — sharpening F11.

**`chat.ts`:** `issueCodeForUser` is called only by coop-api's own chat route with the member's
claims (an internal, trusted caller) — that "unverifiable caller" concern is largely closed.

**`coop_group_base.sql`:** per-group schemas (`grp_<uuidhex>`) of `security_invoker` views narrowed
to the group, member **read-only** (`GRANT SELECT ON ALL TABLES`); personal base = a federated lens
over the global views (RLS-scoped). Sound as written.

## Still open — needs a live system (cannot be settled from the repo)

1. **Keycloak realm config** — does the coop-api client actually carry
   `realm-management/manage-users` (F8)? Brute-force protection, WebAuthn policy, broker
   email-verified setting, token lifespans.
2. **On-chain state** — is `SessionKeyModule` enabled on any Safe, with what limit, allow-list
   armed? Has any handover completed? Does `PasskeyOwner` exist and behave? (Decides F2/F7 real
   impact.)
3. **Edge layer** — Traefik TLS / WAF / rate limiting in front of coop-api (may mitigate F15).
4. **NextAuth runtime** — `NEXTAUTH_SECRET`/JWE and Prisma linking behavior under race.
5. **`OIDC_CLIENTS` values** — are all `${VAR}` references resolved live (F12)?
6. **`pg_hba`** — is the member-cert DB path network-reachable in the live deployment (decides F3's
   practical exposure; the design says yes).

## Verdict so far
F1, F2, F5, F6, F7, F10, F11 are code-confirmed; F4 is latent (key is set); F3's mechanism and
reachability are confirmed. F8/F12/F14 are conditional on items 1/5/6. The most urgent live item is
**F1** — any member can seize another's Safe, with neither misconfiguration nor DB access.