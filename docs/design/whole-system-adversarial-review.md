# Whole-system adversarial review (model-generated)

Generated: 2026-10-19T20:54:44
Model: `moonshotai/Kimi-K3` via the Telnyx inference endpoint.
Inputs: apps/coop-api/src/auth.ts, apps/coop-api/src/verify-jwt.ts, apps/coop-api/src/db.ts, apps/coop-api/src/safe.ts, apps/coop-api/src/provisioning.ts, apps/coop-api/src/keycloak-admin.ts, apps/coop-api/src/invitations.ts, apps/coop-api/src/invite-token.mjs, apps/web/irl-dashboard/src/configs/next-auth.ts, apps/web/irl-dashboard/src/lib/coop-api.ts, infra/compose/storage/scripts/coop_rls.sql, infra/compose/storage/scripts/coop_group_base.sql, contracts/contracts/modules/SessionKeyModule.sol, contracts/contracts/modules/SovereignEvolutionModule.sol, docs/design/custody-and-agent-keys.md

Automated adversarial review across the Keycloak/coop-api/Postgres/frontend/on-chain
seams. NOT an audit and NOT a substitute for the dynamic tests it names. Verify every
finding. finish_reason=stop; usage={'completion_tokens': 28144, 'prompt_tokens': 58635, 'total_tokens': 86779, 'completion_tokens_details': None, 'prompt_tokens_details': {'audio_tokens': None, 'cache_write_tokens': None, 'cached_tokens': 58624}}

---

# Adversarial Review: irl.coop trust-boundary chain

**Evidence note:** the provided source dump carries no line numbers, so evidence is cited as `file — "exact quote"`. Where the in-tree design doc (`docs/design/custody-and-agent-keys.md`) cites approximate lines, I reference them as that doc's own citations. Nothing below invents line numbers; anything I could not verify in the provided sources is marked **speculative** or listed in §5.

---

## System trust model

As I understand it:

1. **Keycloak** is the root identity (Google broker + WebAuthn). It issues RS256 ID tokens to coop-api's `coop-api` client.
2. **coop-api is itself an OIDC issuer** (`OIDC_ISSUER`, default `https://api.irl.coop`). It mints two things with the same RS256 key: (a) short-lived (1h) **coop JWTs** (`aud: "irl-coop"`) used as Bearer tokens, and (b) a long-lived (30d) **session JWT** stored as the `coop_session` cookie on domain `.irl.coop`. The cookie *is* a coop JWT — same key, same issuer, same audience.
3. **Fleet apps** (NextAuth dashboard, oauth2-proxy gates, Synapse, MediaMTX, MinIO) trust the coop JWT via `/jwks` or, for NextAuth only, an HS256 id_token (`iss: "coop-api"`) keyed by the client secret.
4. **coop-api routes** authenticate via `verifyBearer` (verify-jwt.ts), then call `withIdentity(sub)`, which `SET LOCAL ROLE coop_m_<sub8>` + `set_config('app.sub', sub)` on a `coop_app` connection. **Postgres RLS** derives identity from `app.sub` (falling back from a cert-role mapping) and derives *authority over Safes* from `groups.safe_address` via `coop_own_safe()` / `coop_current_safes()`.
5. **On-chain**: personal Safes are CREATE2-deterministic from `keccak256("personal:" + sub)`, deployed **backend-owned 1-of-1**; a `/api/safe/sovereign` route hands ownership to a passkey owner later. A `SessionKeyModule` lets a non-owner bot key spend from a group Safe within a budget/allow-list.
6. **coop-api also holds Keycloak `realm-management/manage-users`** via client_credentials on the *same* client used for public flows.

The critical observation: **layer 4's entire seat-authority model (D-16) bottoms out on a member-writable column (`groups.safe_address`), and layer 5's custody bottoms out on one env var (`SAFE_BACKEND_SIGNER_KEY`).** The seams above them are only as strong as those two facts.

---

## Seam scorecard

| Seam | Verdict | One-liner |
|---|---|---|
| S1 Browser→coop-api OIDC | **weak** | Flow mechanics (code binding, single-use, safeEqual) are sound; but the session cookie is a 30-day, domain-wide, irrevocable bearer token, and any fleet app can mint codes for any visitor by design. |
| S2 Coop JWT trust | **broken** | `verify-jwt.ts` falls back to a hardcoded HS256 secret when `COOP_JWT_PRIVATE_KEY_B64` is unset, and *no* verify path checks `aud`. |
| S3 sub→RLS | **weak** | `app.sub` + FORCE RLS core holds; but `coop_m_<sub8>` truncation collides at scale, and `withIdentity` never binds the role to the sub. |
| S4 sub↔Safe | **broken** | Handover route is unbound to the caller (any member can steal any personal Safe); the "never persisted" mapping is both stored and publicly recomputable; platform is custodian until handover. |
| S5 Frontend session | **weak** | `allowDangerousEmailAccountLinking` + `email_verified ?? true` on every claim path; refresh pattern itself is fine. |
| S6 coop-api→Keycloak admin | **weak** | Works, but one client conflates public OIDC + realm admin; email rewrite forces `emailVerified: true`. Blast radius is the whole realm. |
| S7 On-chain agent path | **broken** | Route has authentication but zero authorization; budget is bypassable via declared `amountIn`; `operation` (delegatecall) is caller-controlled; allow-list defaults off. |
| S8 Invitations | **weak (mostly holds)** | Token primitive is sound (HMAC, timing-safe, expiry, email binding); the redeem SQL and invitations RLS are not in the sources, and the email binding is only as strong as the username-claim flow. |
| S9 Invite-on-signin provisioning | **weak** | Best-effort/idempotent design is fine; Matrix localpart collision enables cross-member impersonation; Safe-stamp race is benign. |

---

## Findings

### F1 — `/api/safe/sovereign` never binds `saltNonce` to the caller: any member can seize any member's personal Safe
- **Seam:** S4 (sub ↔ Safe), reachable through S2.
- **ATTACK:** (1) Attacker A authenticates as any member and obtains a coop JWT. (2) A computes victim B's personal salt: `personalSalt(B_sub) = keccak256("personal:" + B_sub)` — no secret involved. (3) A predicts B's Safe address with the public factory/singleton/initializer (the initializer is `encodeSafeSetup([backendSigner], 1)` — public). (4) A POSTs to `/api/safe/sovereign` with `{ safeAddress: B_safe, passkeyOwner: A_EOA, saltNonce: personalSalt(B_sub) }`. The route checks only: predicted==safeAddress ✓, deployed ✓, `owners == [backend]` ✓ (true for every member who hasn't completed handover). `passkeyOwner` need only pass `ethers.isAddress` and differ from the backend — **an attacker EOA qualifies**. (5) The route itself signs and submits `swapOwner(SENTINEL, backend, A_EOA)`. A now owns B's Safe 1-of-1, including funds, and B can *never* complete handover (the route refuses non-backend-owned Safes).
- **EVIDENCE:** safe.ts — `const claims = verifyBearer(request, reply); if (!claims) return;` followed by `const { safeAddress, passkeyOwner, saltNonce } = request.body as {...}`; the only identity use is authentication. The guards are `if (predicted.toLowerCase() !== safeAddress.toLowerCase())`, `if (code === "0x")`, `if (owners.length !== 1 || owners[0].toLowerCase() !== backendAddr.toLowerCase())` — **no comparison of `claims.sub` to the salt anywhere**. provisioning.ts — `function personalSalt(sub: string): bigint { return BigInt(ethers.keccak256(ethers.toUtf8Bytes(`personal:${sub}`))); }` with the comment "Stable for a given identity, independent of any stored secret".
- **SEVERITY:** Critical. **CONFIDENCE:** certain.
- **PROOF:** Hardhat + `fastify.inject` journey: provision users A and B; run `ensurePersonalSafe(B_sub)`; as A, `POST /api/safe/sovereign` with B's salt and A's EOA; assert `getOwners(B_safe) == [A_EOA]`. Expected today: 200 and ownership transferred.

### F2 — `/api/safe/session/execute` lets any authenticated member drive the group Safe; budget and allow-list are both bypassable; delegatecall is caller-controlled
- **Seam:** S7 (agent path), reachable through S2.
- **ATTACK (three independent variants, any member JWT suffices — the route checks no group membership, no Safe binding):**
  - **(a) Budget bypass via declared amount:** POST `{target: USDC, token: "0x0000000000000000000000000000000000000000", value: "0", data: transfer(attacker, fullBalance)}`. The module computes `cost = (token == address(0)) ? value : amountIn` → `cost = 0`. The Safe's entire ERC-20 balance moves; `spentToday` is untouched. The module's own comment states it "does NOT parse calldata — the automation declares the amount".
  - **(b) Total takeover via delegatecall:** POST `{target: attackerContract, operation: 1, data: <payload>}`. `executeSpend` forwards `operation` verbatim to `execTransactionFromModule`; a delegatecall executes attacker code in the Safe's context (owner storage overwrite, module enabling, arbitrary approvals) — the daily budget is irrelevant.
  - **(c) Allow-list is default-open:** even where (b) is noticed, `listEnabled` defaults false, and `_allowed` returns `true` immediately when off. Even when armed, `_allowed` never inspects `operation`, and `amountIn` remains declarative, so (a) still works against a whitelisted token target.
- **EVIDENCE:** safe.ts — `fastify.post("/api/safe/session/execute", ...)` body: `const claims = verifyBearer(request, reply); if (!claims) return;` then `const target = body?.target; ... const data: string = body?.data ?? "0x"; const operation: number = body?.operation ?? 0;` passed straight to `module.executeSpend(target, value, data, operation, token, amountIn)`. SessionKeyModule.sol — `uint256 cost = (token == address(0)) ? value : amountIn;`, `bool ok = ISafe(SAFE).execTransactionFromModule(target, value, data, operation);`, `if (!listEnabled) return true;`, and the header comment "`listEnabled` defaults to false: with it off, executeSpend is budget-only and can call anything the Safe could."
- **SEVERITY:** Critical. **CONFIDENCE:** certain (route authorization); on-chain impact certain once the module is enabled on a Safe — which is its documented production purpose ("the coop signs as the session bot and drives the group Safe's SessionKeyModule").
- **PROOF:** Fork test: enable the module on a test Safe holding 1000 USDC; as an unrelated member JWT, call the route with variant (a); assert attacker balance +1000 USDC and `spentToday == 0`. Variant (b): delegatecall to a contract that writes owner slot; assert `getOwners()` changed. Note: `docs/design/custody-and-agent-keys.md` admits the allow-list/expiry defects but **misses the delegatecall and declared-amount bypasses and the missing route-level authorization**.

### F3 — `groups.safe_address` is member-writable, and the entire D-16 seat-authority model keys off it: trivial cross-member RLS impersonation
- **Seam:** S3 × S4 (RLS ↔ Safe binding).
- **ATTACK (two variants):**
  - **(a) INSERT variant — no update needed:** Attacker (a member with a cert role, a designed access path: "A member is a LOGIN role whose client cert CN == role name") creates a coop group with `safe_address = V` (victim's personal Safe, publicly derivable per F1) and seats themselves. `coop_current_safes()` clause (b) returns "the Safe of every group where they hold a DIRECT person seat" → now includes `V`. Every seat with `holder_safe = V` (the victim's backfilled seats) now matches `coop_is_member`, and `coop_is_owner` matches `gm.holder_safe = coop_own_safe()`-equivalent via the same set → **the attacker inherits the victim's membership visibility and owner authority in every group where the victim holds a Safe-keyed seat**, including the victim's personal group (their entire event stream).
  - **(b) UPDATE variant:** `UPDATE groups SET safe_address = V WHERE kind='personal' AND created_by = <attackerSub>` — allowed by `groups_update` (`USING (coop_is_owner(id))`; the attacker owns their personal group). Then `coop_own_safe()` itself returns `V`.
- **EVIDENCE:** coop_rls.sql — `CREATE POLICY groups_update ON groups FOR UPDATE USING (coop_is_owner(id));` (RLS is row-level; no column restriction); `GRANT SELECT, INSERT, UPDATE, DELETE ON groups, group_members, resource_scopes, events, ... TO coop_member;`; `CREATE POLICY groups_insert ON groups FOR INSERT WITH CHECK (created_by = coop_current_sub());` (no constraint on `safe_address`); `coop_own_safe()` = `SELECT g.safe_address FROM groups g WHERE g.kind = 'personal' AND g.created_by = coop_current_sub()`; `coop_is_owner` matching `(gm.holder_safe IS NOT NULL AND gm.holder_safe = coop_own_safe())`; the backfill `UPDATE group_members gm SET holder_safe = (SELECT g.safe_address FROM groups g WHERE g.kind='personal' AND g.created_by = gm.sub ...)`. There is no unique constraint on `groups.safe_address`.
- **SEVERITY:** Critical. **CONFIDENCE:** certain as a mechanism (all components quoted above); the reachability depends on member cert DB access being live, which the SQL presents as designed ("pg_hba matches `+coop_member`"). Any future "link my Safe" app route opens the same hole through the API pool.
- **PROOF:** psql journey: as `coop_m_<attacker8>`, `SET app.sub`; insert group with victim's Safe address; self-seat; then `SELECT coop_is_owner('<victim_personal_group>')` and `SELECT * FROM coop_my_seats()` — expect `true` and the victim's seats. Root cause: `safe_address` attestation is missing — it should be written only by a `coop_ops`-locked definer function after on-chain `getOwners()`/EIP-1271 verification.

### F4 — `verify-jwt.ts` falls back to a hardcoded HS256 secret with no algorithm/issuer pinning when `COOP_JWT_PRIVATE_KEY_B64` is unset
- **Seam:** S2.
- **ATTACK:** Per the threat model, a missing/misconfigured env is in-scope. If `COOP_JWT_PRIVATE_KEY_B64` is absent: `publicKey` is `null`, and verification becomes `jwt.verify(token, "local-development-secret-irl-coop-v4")` — a secret **published in the source tree**, with no `algorithms` and no `issuer` constraint. Anyone mints `HS256 {sub: <any member>, ...}` and passes every `verifyBearer` route: `/api/safe/*` (combine with F1/F2), invitations, profile, all `withIdentity` DB access as any sub. Worse, in the same misconfigured state `auth.ts` generates an *ephemeral* RSA key (`crypto.generateKeyPairSync`), so legitimate RS256 tokens **fail** verification — legitimate users are locked out while forgers walk in. The two files disagree about the fallback; neither fails closed at boot.
- **EVIDENCE:** verify-jwt.ts — `const jwtSecret = process.env.JWT_SECRET ?? "local-development-secret-irl-coop-v4";`, `const publicKey = keyB64 ? crypto.createPublicKey(...) : null;`, and `if (publicKey) { return jwt.verify(...RS256...); } return jwt.verify(auth.slice(7), jwtSecret);`. auth.ts — `const keyB64 = process.env.COOP_JWT_PRIVATE_KEY_B64 ?? ""; const privateKeyPem = keyB64 ? ... : crypto.generateKeyPairSync("rsa", ...)`.
- **SEVERITY:** Critical (conditional on env). **CONFIDENCE:** certain (code path).
- **PROOF:** Boot coop-api in a container without `COOP_JWT_PRIVATE_KEY_B64`; `jwt.sign({sub:"victim"}, "local-development-secret-irl-coop-v4")`; `curl -H "Authorization: Bearer $T" https://api.irl.coop/api/auth/userinfo` → expect 200 as victim. Add a boot-time assertion: if the key is missing, the process must refuse to start.

### F5 — No audience check on any coop-JWT verify path: token-type confusion across id_token / access_token / session cookie
- **Seam:** S2 (with S1/S5 consequences).
- **ATTACK:** `verifyBearer` (RS256 branch) and `verifyCoopJwt` both pin only `algorithms` + `issuer`. The same private key signs: access tokens (`aud: "irl-coop"`), 30d session cookies (`aud: "irl-coop"`), and per-client id_tokens (`aud: clientId`, e.g. oauth2-proxy/Synapse clients). Because `aud` is never verified: (1) any fleet client's **id_token is accepted as a coop-api Bearer token**; (2) the **30-day session cookie is accepted as a Bearer token** — `sessionFromRequest` and `verifyBearer` are interchangeable for it. An attacker who obtains any one of these artifacts (e.g., an id_token logged by a gated app, or the cookie per F6) holds a fully general coop-api credential.
- **EVIDENCE:** verify-jwt.ts — `jwt.verify(auth.slice(7), publicKey, { algorithms: ["RS256"], issuer: oidcIssuer })` (no `audience`). auth.ts — `function verifyCoopJwt(token: string): any { return jwt.verify(token, publicKeyPem, { algorithms: ["RS256"], issuer: env.oidcIssuer }); }`; token endpoint signs the non-NextAuth id_token with `privateKeyPem`, `iss: env.oidcIssuer`, `aud: clientId`; `mintCoopJwt` signs with `audience: "irl-coop"`; `setSessionCookie(reply, sessionJwt, request)` where `sessionJwt = await mintCoopJwt(claims, stored, sessionTtl)`.
- **SEVERITY:** High. **CONFIDENCE:** certain.
- **PROOF:** Complete the OIDC flow for a non-NextAuth test client; take the returned `id_token`; `curl -H "Authorization: Bearer $ID_TOKEN" /api/auth/userinfo` → expect 200 today. Then use the `coop_session` cookie value as a Bearer header → expect 200.

### F6 — The 30-day session cookie is a stateless, domain-wide, irrevocable bearer credential; logout and user deletion don't help on the Bearer path
- **Seam:** S1 (with S2/S5).
- **ATTACK:** The cookie is a 30d RS256 coop JWT on `domain: ".irl.coop"`, sent to every `*.irl.coop` app. There is no server-side session store, jti, or denylist: `/api/auth/logout` only clears the browser cookie. The `/api/auth/authorize` path does check Keycloak liveness (`getUserProfile(session.sub)`), but `verifyBearer` does **not** — so a cookie stolen (XSS on any subdomain, malicious extension, threat actor C) remains a valid Bearer credential for up to 30 days **even after the victim logs out, and even after the Keycloak user is disabled or deleted**. Contrast: the authorize path treats a stale sub as "not authenticated"; the API path never notices.
- **EVIDENCE:** auth.ts — `const sessionTtl = (process.env.COOP_SESSION_TTL ?? "30d")`; `maxAge: 30 * 24 * 60 * 60`; `domain: ... env.cookieDomain` (`".irl.coop"` default); logout route body is only `clearSessionCookie(reply, request); return reply.redirect("https://irl.coop/");`. verify-jwt.ts contains no Keycloak call. The liveness check exists only in auth.ts authorize: `const live = await getUserProfile(session.sub);` with the "stale session" comment.
- **SEVERITY:** High. **CONFIDENCE:** certain.
- **PROOF:** Journey: sign in, capture the cookie value; `GET /api/auth/logout`; then `curl -H "Authorization: Bearer <cookie>" /api/auth/userinfo` → still 200. Delete the Keycloak user; repeat against a `verifyBearer` route (e.g. `/api/safe/predict`) → still 200; repeat against `/api/auth/authorize` → cookie cleared (proves the asymmetry).

### F7 — Platform custody: every personal Safe is backend-owned 1-of-1; one env key controls all member funds until a voluntary handover
- **Seam:** S4.
- **ATTACK:** `SAFE_BACKEND_SIGNER_KEY` sits in coop-api's environment. Every personal Safe's sole owner is that key (`encodeSafeSetup([backendSigner], 1)`). The platform — or anyone who compromises the coop-api host, its env, or its secrets store — can sign `execTransaction` on **every member Safe** and drain everything. Handover (`/api/safe/sovereign`) is client-initiated; nothing forces it, and per F1 the handover itself is hijackable. The in-tree design doc concedes this: "The platform key is the owner at creation… Between creation and that call, the platform *is* the wallet" and "Signer keys sit in plain env (`SAFE_BACKEND_SIGNER_KEY`, `SESSION_KEY`), long-lived" — and the doc is marked "Status: design (a plan; nothing here is built)".
- **EVIDENCE:** safe.ts — `const defaultInitializer = (): string => encodeSafeSetup([new ethers.Wallet(env.backendKey).address], 1);` and `deploySafe(signer, {...}, [signer.address], 1)`; provisioning.ts — `await deploySafe(signer, { ..., saltNonce: personalSalt(sub) }, [signer.address], 1);`. docs/design/custody-and-agent-keys.md — defects 3 and 4 as quoted above.
- **SEVERITY:** Critical (systemic custody risk). **CONFIDENCE:** certain.
- **PROOF:** On a devnet: provision two members, fund both Safes, then from a shell with only the backend key, sign a Safe `execTransaction` transferring both balances out (reuse the signing code in `/api/safe/sovereign`). Assert both succeed without any member action.

### F8 — coop-api's Keycloak client conflates public OIDC flows with `realm-management/manage-users`; email rewrite forces `emailVerified: true`
- **Seam:** S6.
- **ATTACK:** The same `KEYCLOAK_CLIENT_ID`/`KEYCLOAK_CLIENT_SECRET` is used for the browser-facing auth-code + password grants (auth.ts) *and* for client_credentials admin (keycloak-admin.ts). One secret leak (it is transmitted in every `/api/auth/login` and token exchange) yields full realm user management: `setUserCanonicalEmail` rewrites **any** user's email and unconditionally sets `emailVerified: true`; `addUserRequiredAction` mutates login requirements. Email rewrite → broker re-link / password-reset / NextAuth email-linking (F9) → fleet-wide account takeover. Additionally, the authorize path makes a **blocking admin call per authorize** (`getUserProfile`), so admin-plane outages cascade into SSO.
- **EVIDENCE:** keycloak-admin.ts header — "the coop-api service account has realm-management/manage-users — the canonical-identity authority"; `body: JSON.stringify({ email, emailVerified: true })` in `setUserCanonicalEmail`; `grant_type: "client_credentials"` with the same `KC_CLIENT_ID`/`KC_CLIENT_SECRET` env names that auth.ts uses for `grant_type: "password"` and the code exchange.
- **SEVERITY:** High. **CONFIDENCE:** certain (design); the route-level authorization of the username-claim endpoint that calls `setUserCanonicalEmail` is **not in the sources** (see §5).
- **PROOF:** From the coop-api host, use the client credentials to `PUT /admin/realms/irl-coop/users/<victim>` with a new email; observe `emailVerified: true` persisted. Config review: confirm one client holds both public and admin roles; the fix is two clients (public + admin) with the admin secret vaulted.

### F9 — `email_verified ?? true` on every claim path + `allowDangerousEmailAccountLinking: true`
- **Seam:** S5.
- **ATTACK:** The claim defaults to `true` when absent in `mintCoopJwt` (`email_verified: claims.email_verified ?? true`), in the token endpoint's id_token (`email_verified: access.email_verified ?? true`), and in userinfo (`email_verified: decoded.email_verified ?? true`). NextAuth links accounts by email across both providers with `allowDangerousEmailAccountLinking: true`, justified by the comment "emails arrive verified from Google via Keycloak". That justification is circular given the default-true and given F8's forced `emailVerified: true` on canonical-email claims: any path that lets a member influence their asserted email (the username-claim flow, not in sources) becomes an account-linking primitive against the victim's NextAuth user.
- **EVIDENCE:** quotes above; next-auth.ts — `allowDangerousEmailAccountLinking: true` on both providers with the "Safe: emails arrive verified" comment.
- **SEVERITY:** Medium. **CONFIDENCE:** likely (the dangerous default is certain; exploitability hinges on the unseen username-claim authorization).
- **PROOF:** Unit: mint a coop JWT with no `email_verified` claim; assert userinfo returns `email_verified: true`. Journey: with a staging username-claim, claim `victim@irl.coop`, then sign in via the second provider and observe Prisma account linking.

### F10 — `coop_m_<sub8>` role derivation collides at scale, and `withIdentity` never binds the role to the sub
- **Seam:** S3.
- **ATTACK:** The role is the first 8 alphanumeric chars of the sub — 32 bits for UUID-style subs. By birthday math, collisions are expected around ~65k members (≈1% at 10k). On collision, member A's request `SET LOCAL ROLE`s into member B's role: whatever table grants and `grp_*` schema USAGE bind to that role are shared. `withIdentity` checks only that the role *exists* (`SELECT 1 FROM coop_member_role WHERE role_name = $1 AND revoked_at IS NULL`) — never that the mapped `sub` equals the request's sub. Row-level isolation still holds (identity comes from `app.sub`, and `coop_role_sub()` reads `session_user`, which `SET LOCAL ROLE` doesn't change), so the impact is rights-bleed, not row-bleed — but the design doc (`member-scoped-app-access.md`, referenced) intends per-member rights separation.
- **EVIDENCE:** db.ts — `const key = (sub.match(/[A-Za-z0-9]/g) ?? []).join("").slice(0, 8);`, the `coop_member_role` existence check quoted above, and the comment "This supplies the RIGHTS, not the identity".
- **SEVERITY:** Medium. **CONFIDENCE:** certain (collision math + missing binding check); impact **speculative** without `infra/scripts/provision-member-certs.sh` (not in sources) showing what per-role grants exist.
- **PROOF:** Insert two synthetic subs sharing an alnum-8 prefix into a scratch DB; run `withIdentity(subB)`-equivalent and `SHOW ROLE` → observe `coop_m_<shared>` entered for B's session; diff `has_schema_privilege`/`has_table_privilege` against A's intent.

### F11 — Matrix provisioning localpart collision: second member with the same email localpart joins rooms as the first member's account
- **Seam:** S9.
- **ATTACK:** `localpartFromEmail` maps `alice@gmail.com` and `alice@irl.coop` (and `alice@outlook.com`) to the same Matrix localpart `alice`. Registration tolerates `M_USER_IN_USE` and proceeds to invite + join **as that existing userId**. A second member whose email shares the localpart is joined into the coop's General/Governance/Treasury rooms as the *first* member's Matrix identity — reading history and sending under their name. The canonical-username flow (F8/F9) makes a deliberate version of this reachable if a member can claim a localpart matching another member's existing Matrix account.
- **EVIDENCE:** provisioning.ts — `const lp = email.split("@")[0].toLowerCase().replace(/[^a-z0-9._=-]/g, "")`; `if ((body as any).errcode !== "M_USER_IN_USE") { ... return null; }` (i.e., IN_USE is accepted), then the invite/join loop uses `?user_id=${userId}`.
- **SEVERITY:** Medium. **CONFIDENCE:** likely (collision is certain given real email diversity; impact depends on room content sensitivity — "Treasury" is a default room).
- **PROOF:** Staging: sign in user A (`alice@gmail.com`), then user B (`alice@x.com`); query Synapse for room members of `#irl-coop-general`; assert B's session can post as `@alice:...` and read A's history.

### F12 — Unresolved `${ENV_VAR}` OIDC client secrets remain as literal, guessable secrets
- **Seam:** S1/S2.
- **ATTACK:** Client secrets in `OIDC_CLIENTS` may be `${VAR}` references, resolved only `if (m && process.env[m[1]])`. If the referenced env var is missing, the secret stays the literal string `"${SOME_DERIVED_SECRET}"` — a value an attacker can read straight out of the deployment config/repo template and present at `/api/auth/token` as a valid `client_secret` (and, for the NextAuth client, as the HS256 id_token signing key → forge NextAuth-session id_tokens).
- **EVIDENCE:** auth.ts — `const m = /^\$\{([A-Z0-9_]+)\}$/.exec(c.secret); if (m && process.env[m[1]]) { c.secret = process.env[m[1]]!; }` (no else-branch failure); the NextAuth id_token is `jwt.sign({...}, app.secret, { algorithm: "HS256" })`.
- **SEVERITY:** Medium (conditional on env). **CONFIDENCE:** speculative (depends on `OIDC_CLIENTS` content, not in sources); the code pattern is certain.
- **PROOF:** Boot with `OIDC_CLIENTS={"nextauth":{"secret":"${UNSET_VAR}","redirects":[...]}}` and `UNSET_VAR` absent; exchange a code using `client_secret=${UNSET_VAR}` (literal) → expect 200. Boot should instead fail closed on unresolved references.

### F13 — `SovereignEvolutionModule.onlySafe` is an empty modifier; stage flags are spoofable by anyone
- **Seam:** S7.
- **ATTACK:** `modifier onlySafe() { // In a real module, we verify msg.sender is the Safe proxy _; }` — no check. Anyone can call `promoteToSovereign` for any `msg.sender`-keyed config. It cannot move on-chain owners (it only writes its own mapping), so the direct damage is nil — but any off-chain system that trusts `getSafeConfig(safe)` to conclude "backend signer revoked" can be lied to. The design doc flags exactly this ("a stub that looks real… its name invites exactly that") yet the contract still ships.
- **EVIDENCE:** SovereignEvolutionModule.sol — the empty modifier quoted above; custody-and-agent-keys.md defect 2.
- **SEVERITY:** Low/Medium (hazard, not a live exploit). **CONFIDENCE:** certain.
- **PROOF:** Hardhat: call `initializeSafe` then `promoteToSovereign([g1,g2])` from an unrelated EOA; assert `getSafeConfig` reports Stage 2. Then grep the repo for any consumer of `getSafeConfig` — if none, delete the contract per the doc's P2.

### F14 — Invite redemption binds to the JWT's `email` claim; strength depends entirely on the unseen username-claim flow
- **Seam:** S8.
- **ATTACK:** Redeem requires `good.email === String(claims.email ?? "").toLowerCase()`. The JWT email is the Keycloak canonical email, which members can influence via the `/api/v1/me/username` claim (referenced in auth.ts comments; route not in sources) with `emailVerified: true` forced (F8). If that claim flow lacks verification of mailbox ownership, an attacker claims `target@irl.coop`, obtains a JWT with that email, and redeems invitations addressed to `target@irl.coop` — seating themselves (possibly as owner, when `member_offer` is set) in the victim's stead.
- **EVIDENCE:** invitations.ts — `if (!good || good.id !== id || good.email !== String(claims.email ?? "").toLowerCase())`; the token primitive itself is sound (invite-token.mjs enforces ≥24-char secret at sign, `timingSafeEqual` at verify, expiry check). `coop_invite_redeem` and the `invitations` table DDL/RLS are **not in the provided sources**.
- **SEVERITY:** Medium. **CONFIDENCE:** speculative (hinges on the unseen claim flow and unseen SQL).
- **PROOF:** Journey: owner invites `victim@irl.coop`; attacker claims username `victim`; attacker redeems with the leaked/intercepted token → observe seat. Separately, audit `coop_invite_redeem` for single-use (`status` transition under `FOR UPDATE`).

### F15 — Abuse-surface hygiene on S1: no rate limiting, unbounded in-memory code store, uncached JWKS, nonce never verified
- **Seam:** S1.
- **ATTACK / EVIDENCE:** (a) `/api/auth/login` proxies the password grant with no visible throttling — credential-stuffing amplifier (Keycloak's own brute-force config is not in sources). (b) `codes` is a process-local `Map` with entries deleted only on exchange — each authorized request with a session adds an entry; no sweep → memory growth, and multi-replica deployments break code exchange (availability). (c) `verifyIdToken` fetches the realm JWKS on **every** callback/login with no cache. (d) The authorize URL sends `&nonce=${crypto.randomUUID()}` to Keycloak but `verifyIdToken` never compares the returned nonce — replay protection is illusory; also `if (payload.exp && ...)` means a token lacking `exp` skips expiry. (e) Cookie `secure`/`domain` decisions trust the client-supplied `Host` header (`request.headers.host`). (f) Logout is an unauthenticated GET with no state — trivial logout-CSRF.
- **SEVERITY:** Low (each). **CONFIDENCE:** likely (absence of evidence in-file; edge/proxy controls may exist — see §5).
- **PROOF:** k6 against `/api/auth/login` measuring lockout behavior; script N authorize calls with a session and diff process RSS; code-review checklist for the nonce/exp items.

---

## Cross-layer attack chains

**C1 — One member, total custody loss (S2→S4).** Any member JWT → F1: compute `personalSalt(victimSub)` → `/api/safe/sovereign` with attacker EOA → own every not-yet-handed-over personal Safe. No env assumptions, no DB access, no XSS. *This is the shortest path from "authenticated member" (actor A) to "moves other members' funds".*

**C2 — One member, group treasury takeover (S2→S7).** Any member JWT → F2 variant (b): `operation: 1` delegatecall through `/api/safe/session/execute` → arbitrary code in the group Safe's context → owners rewritten, budget moot. Variant (a) drains ERC-20s with `cost = 0` even if delegatecall is later blocked.

**C3 — Misconfiguration → full identity + custody compromise (S2→S3→S4).** Missing `COOP_JWT_PRIVATE_KEY_B64` → F4 forged HS256 token with any `sub` → `withIdentity(forgedSub)` makes RLS trust the assertion (app.sub is the *only* identity input on the API path) → read/write any member's rows via any route → then F1/F2 for the on-chain layer. One missing env var collapses layers 2–5.

**C4 — One compromised fleet app → impersonate every visitor fleet-wide (S1→S5→S7/S4).** Actor C's compromised `*.irl.coop` app navigates a visiting victim's browser to `/api/auth/authorize` with *its* `client_id`/redirect (same-site: `sameSite` doesn't help; the cookie flows by design) → receives a code at its own callback → exchanges with its client_secret → holds a fresh victim coop JWT → F2/F1. This is the SSO gateway working as designed; the blast radius of one app compromise is every member who visits it. The NextAuth `refreshCoopToken` function demonstrates the exact programmatic pattern.

**C5 — Cookie theft → 30-day unpatchable impersonation (S1→S2).** One XSS on any subdomain (or actor C's app reading the redirect) captures the `coop_session` value → F5/F6: usable as a Bearer token for 30 days; logout doesn't revoke; Keycloak deletion doesn't revoke on the API path; the victim cannot self-remediate.

**C6 — coop-api compromise → realm-wide identity takeover (S6→S5).** The API's env yields Keycloak `manage-users` (F8) → rewrite any user's email with `emailVerified: true` → NextAuth `allowDangerousEmailAccountLinking` (F9) links the attacker's next login into the victim's account → fleet access as victim → F1/F2 for funds. Each layer's "convenience" default compounds.

**C7 — Operator with DB read (actor D) → correlation + 2FA interception (S3/S4/S9).** DB read alone yields: `groups.safe_address` (the sub→Safe mapping the code comments claim is never stored — F9-adjacent), `phone_message` bodies ("a verification code has to land somewhere the group's people can see it" — including SMS 2FA codes with `expires_at`), tier2 ledgers, dues waivers (the exact "mode leak" the schema elsewhere works to prevent). No keys needed; combine with F3 knowledge to target high-value Safes.

---

## What a model review cannot prove here

1. **Env reality.** Whether `COOP_JWT_PRIVATE_KEY_B64`, `JWT_SECRET`, `INVITE_SIGNING_SECRET`, `OIDC_CLIENTS` (and its `${...}` references), `COOP_OPS`, and the DB passwords are actually set in any environment. F4/F12 are conditional on this by construction.
2. **Truncated sources.** `apps/coop-api/src/db.ts` and `coop_rls.sql` were cut at 60k chars. Not visible: the `invitations` table DDL and its RLS, `coop_invite_redeem` (single-use enforcement), the dues-waiver count function tail, any `coop_app` role grants, and whether the `coop` owner role has `BYPASSRLS` (the db.ts comment claims the owner "can read any row, bypass every policy" despite `FORCE ROW LEVEL SECURITY` — unverifiable either way).
3. **Unseen routes and modules.** `server.ts` (CORS, global rate limits, helmet, trust-proxy — which determines whether the `Host`-header trust in `setSessionCookie` is exploitable), `/api/v1/me/username` (the authorization behind canonical-email claims — load-bearing for F9/F11/F14), `telephony.ts`, `erpnext-provision.ts`, `profile-store.ts`, the chat gateway that calls `issueCodeForUser` (it asserts `sub`/`email` from its own verification — its trustworthiness is unverifiable).
4. **Keycloak realm config.** Brute-force protection, WebAuthn policy, broker email-trust settings, whether the `coop-api` client truly has `manage-users` (the comment asserts it), token lifespans.
5. **On-chain state.** Whether `SessionKeyModule` is enabled on any real Safe, with what `dailyLimit`, whether `listEnabled` was ever armed, whether any member completed sovereign handover, and whether `PasskeyOwner` exists/behaves as the design doc hopes. F2's impact is stated conditionally for this reason.
6. **`infra/scripts/provision-member-certs.sh`** — what per-`coop_m_*` grants exist determines F10's real impact.
7. **NextAuth runtime.** `NEXTAUTH_SECRET` handling/JWE encryption of the session JWT, and the Prisma adapter's actual linking behavior under race.
8. **Edge layer.** Whether TLS termination, WAF, or rate limiting sits in front of coop-api (F15 items may be mitigated there).

---

## The dynamic tests to actually run

Ranked by expected-value; each names the harness to add.

1. **Sovereign-hijack journey (F1).** `apps/coop-api/test/journey/safe-sovereign.spec.ts` — Fastify `inject` + Hardhat node: provision members A/B, deploy B's personal Safe, as A call `/api/safe/sovereign` with B's salt and A's EOA; assert current code returns 200 and `getOwners() == [A]`. Then fix (bind `saltNonce == personalSalt(claims.sub)` + require `passkeyOwner` to be a verified EIP-1271 contract) and assert 4xx.
2. **Session-execute abuse pack (F2).** `contracts/test/SessionKeyModule.abuse.ts` + API journey: (a) `token=0,value=0,data=ERC20.transfer(all)` → assert drain with `spentToday == 0`; (b) `operation=1` delegatecall → assert owner-slot overwrite; (c) route-level: member with no seat in the module's group → assert today's 200. Fix = route authorization (seat + grant check), drop/whitelist `operation`, parse calldata or remove the declared-`amountIn` shortcut, default-deny allow-list, expiry.
3. **RLS safe-address spoof (F3).** `infra/compose/storage/scripts/test/rls_safe_spoof.sql` — as a `coop_m_*` role: INSERT-variant and UPDATE-variant; assert `coop_is_owner(victim_group)` and `coop_my_seats()` leakage today. Fix = move `safe_address` writes into a `coop_ops`-locked definer function with on-chain verification; add `UNIQUE(safe_address)`; re-run to prove denial.
4. **Misconfiguration boot matrix (F4/F12).** `apps/coop-api/test/boot/env-matrix.spec.ts` — boot with each secret-bearing env unset; assert the process **refuses to start** (today: assert it starts, demonstrating the finding); include the forged-HS256 curl as the positive control.
5. **Token-confusion suite (F5/F6).** `apps/coop-api/test/journey/token-confusion.spec.ts` — id_token-as-Bearer, cookie-as-Bearer, post-logout replay, post-deletion replay against both `/api/auth/authorize` and a `verifyBearer` route; assert the asymmetry, then assert 401s after adding `audience` checks + a session jti/denylist (or short TTL + rotation).
6. **Keycloak blast-radius audit (F8).** Script: enumerate the `coop-api` client's service-account roles via the admin API; assert `manage-users` present (confirming the finding) and drive the two-client split; journey for email-rewrite → NextAuth linking (F9) on staging.
7. **Role-collision harness (F10).** Property test generating subs to force an alnum-8 prefix collision; assert `withIdentity` enters the shared role for both and enumerate the rights delta; then add the `coop_member_role.sub == request sub` binding check (or widen the prefix) and re-run.
8. **Matrix localpart collision (F11).** Staging journey with colliding emails; assert cross-member room impersonation; fix = sub-derived (not email-derived) localparts.
9. **Invite flow audit (F14).** Read `coop_invite_redeem` + invitations RLS (outside this dump); journey for token reuse, cross-email redeem, and username-claim-then-redeem.
10. **Load/abuse sweep (F15).** k6 against `/api/auth/login` and `/api/auth/authorize` measuring lockout, `codes`-map growth, and JWKS fetch amplification; add nonce verification and `exp` mandatory checks to `verifyIdToken` with unit tests.

**Bottom line:** seams S2, S4, and S7 are broken as written — F1, F2, and F3 are each independently sufficient for an ordinary authenticated member to take other members' funds or identities, and none of them requires any misconfiguration. F4 turns a single missing env var into a platform-wide collapse. The RLS/RLS-helper architecture, the token endpoint's code binding, the `coop_ops` privilege split, and the invite token primitive are genuinely good bones — but the custody layer and the JWT verification layer need to be fixed before anything of value rests on them.
