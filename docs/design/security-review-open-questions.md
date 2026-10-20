# Security review — verdicts and open questions

Companion to `whole-system-adversarial-review.md` and `security-review.md`. The reviews are
model-generated breadth; this file records what is **verified against the code**, and every
question still needing information, with where to look and what it decides.

## Verified against the code (by reading, not by model claim)

| Finding | Verdict | Evidence |
|---|---|---|
| F1 — `/api/safe/sovereign` not bound to the caller | **Confirmed** | `safe.ts`: only `verifyBearer` + `predicted==safeAddress` + `owners==[backend]`; `claims.sub` never compared to `saltNonce`; `personalSalt(sub)=keccak256("personal:"+sub)` is public (provisioning.ts) |
| F2 — `/api/safe/session/execute` auth-without-authz; `amountIn` + delegatecall bypasses | **Confirmed** | route reads `target/data/operation/token/amountIn` from the body with no seat/grant check; `SessionKeyModule.executeSpend`: `cost = token==0 ? value : amountIn`, forwards `operation`, `_allowed` returns true when `listEnabled` is false |
| F3 — `groups.safe_address` writable → D-16 seat impersonation | **Confirmed (mechanism)** | see below |
| F4 — hardcoded HS256 fallback secret, no alg pin | **Confirmed** | `verify-jwt.ts`: `JWT_SECRET ?? "local-development-secret-irl-coop-v4"`, `jwt.verify(token, jwtSecret)` when the RS256 key is absent |
| F5 — no `audience` check on any verify path | **Confirmed** | `verify-jwt.ts` + `auth.ts verifyCoopJwt`: `{algorithms,issuer}` only; the same key signs access tokens, the 30d session cookie, and per-client id_tokens |
| F6 — 30-day session cookie is a live Bearer; logout/deletion don't revoke | **Confirmed** | `COOP_SESSION_TTL ?? "30d"`, `maxAge 30d`, `verifyBearer` makes no Keycloak call; logout only clears the cookie |
| F7 — every personal Safe backend-owned 1-of-1 | **Confirmed** | `provisioning.ts` + `safe.ts`: `deploySafe(signer, …, [signer.address], 1)` |
| F10 — `coop_m_<sub8>` role truncation | **Confirmed (mechanism)** | `db.ts`: `sub.match(/[A-Za-z0-9]/g).join("").slice(0,8)`; `withIdentity` never binds role→sub |
| F11 — Matrix localpart collision | **Confirmed** | `provisioning.ts`: `localpartFromEmail` + `M_USER_IN_USE` accepted, then invite/join as that userId |

### F3 — confirmed mechanism

- `groups_insert … WITH CHECK (created_by = coop_current_sub())` (coop_rls.sql:329) — no
  constraint on `safe_address` or `kind`.
- `groups_update … USING (coop_is_owner(id))` (line 331), no `WITH CHECK` — an owner can rewrite
  their personal group's `safe_address` to any value.
- `coop_own_safe()` reads that column (162–168); `coop_current_safes()` seeds from it (185);
  `coop_is_member`/`coop_is_owner`/`coop_my_seats` match seats by `holder_safe = ANY(current_safes)`
  (227, 241, 266). The backfill keys person seats to the personal Safe (151–156).
- **No `UNIQUE(safe_address)`**; nothing verifies the on-chain owner of the address.
- **Reachability:** a direct member DB connection (cert role `coop_m_*`; `groups` is granted
  INSERT/UPDATE to `coop_member`, line 105 — the designed NocoDB path) or any future route that
  lets a caller set `safe_address`. Not reachable through today's create-group route (the app
  sets it). Blast radius depends on whether member cert DB access is live.

### New (not in the reviews)

- **`proposals` / `votes` have NO RLS** and are granted to `coop_app` (coop_rls.sql:1373–1376,
  self-labelled "TODO: give these two RLS like the rest"). Any holder of the `coop_app` role can
  read/write any group's governance rows.

## Open questions — everything still needing information

**A. Environment / secrets (decides F4, F5, F7, F12, F2 impact)**
1. Is `COOP_JWT_PRIVATE_KEY_B64` set in the live env? — `apps/coop-api/.env`, `secrets.env`, the
   app spec. Decides whether the hardcoded-secret fallback is exploitable. (`JWT_SECRET` too.)
2. Does every `${VAR}` in `OIDC_CLIENTS` resolve? — same files. Decides F12.
3. Are `SAFE_PROXY_FACTORY_ADDRESS` / `SAFE_SINGLETON_ADDRESS` / `SAFE_BACKEND_SIGNER_KEY` /
   `SESSION_KEY` set, and pointing at which chain (local vs Base)? — app spec. Decides whether the
   safe routes are live at all, and on which chain.
4. Is `INVITE_SIGNING_SECRET` set (are invitations live)? `COOP_OPS`/`POSTGRES_*` set; is the
   `coop_ops` password non-default?
5. What is `COOP_SESSION_TTL` actually?

**B. Keycloak realm (decides F8, F9, F11, F14)**
6. Does the coop-api client actually hold `realm-management/manage-users`? — realm config scripts.
7. Brute-force protection, WebAuthn policy, broker email-verified setting, token lifespans.

**C. Repo files not yet read (the reviews' blind spots; mostly settleable locally)**
8. `apps/coop-api/src/server.ts` — CORS / helmet / rate limit / `trust proxy` (decides F15 and
   whether the `Host`-header trust in `setSessionCookie` is exploitable).
9. `/api/v1/me/username` route and `setUserCanonicalEmail` callers — **load-bearing** for F9/F11/F14.
10. `infra/compose/storage/scripts/coop_invitations.sql` — `invitations` DDL/RLS and
    `coop_invite_redeem` single-use enforcement (F14). (It is NOT in `coop_rls.sql`.)
11. `infra/scripts/provision-member-certs.sh` — per-role grants and whether member cert DB access
    is live (decides F3 reachability and F10 impact).
12. `infra/compose/storage/scripts/coop_group_base.sql` — not yet read.
13. `telephony.ts`, `erpnext-provision.ts`, `profile-store.ts`, `chat*.ts`, `internal.ts` — trust of
    system callers, esp. the `issueCodeForUser` caller.
14. Edge: Traefik dynamic config — TLS / WAF / rate limiting in front of coop-api.
15. On-chain state: is `SessionKeyModule` enabled on any Safe (and with what limit / is the list
    armed)? Has any handover completed? Does `PasskeyOwner` exist and behave? (decides F2/F7/F10.)
16. NextAuth runtime: `NEXTAUTH_SECRET`/JWE and Prisma account-linking behavior under race.

## Verdict so far
F1, F2, F4, F5, F6, F7, F10, F11 are code-confirmed. F3's mechanism is confirmed. F8, F9, F12, F14
are conditional on items A/B/C above.