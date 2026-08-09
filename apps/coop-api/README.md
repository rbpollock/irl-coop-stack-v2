# coop-api

Fastify service that sits between the irl.coop frontends and the rest of the stack. It owns two critical boundaries:

1. **Authentication go-between** — the Next.js app (and any future frontend, e.g. mobile) talks only to coop-api. coop-api talks to Keycloak, and Keycloak brokers Google. The frontend has zero knowledge of Keycloak.
2. **Auth-to-EVM bridge** — the JWT issued at login is the same credential used to authorize Safe smart-account deployment (`POST /api/onboard`).

## Auth bridge: NextAuth → coop-api → Keycloak → Google

```
┌──────────────┐  OAuth2   ┌──────────────┐   OIDC    ┌──────────────┐  IdP   ┌────────┐
│  Frontend    │ ────────► │   coop-api   │ ────────► │   Keycloak   │ ─────► │ Google │
│ (NextAuth)   │ ◄──────── │  (:3001)     │ ◄──────── │ (:8081 realm │ ◄───── │        │
│   (:3000)    │  JWT +    │              │   tokens  │   irl-coop)  │        │        │
└──────────────┘  userinfo └──────────────┘           └──────────────┘        └────────┘
```

The browser journey: NextAuth redirects to `GET /api/auth/authorize` → coop-api bounces it to Keycloak's authorize endpoint (baking NextAuth's `state` + `redirect_uri` into its own state so they survive the round trip) → Keycloak shows its login page with the Google identity-provider button → after Google, Keycloak redirects to `GET /api/auth/keycloak/callback` → coop-api exchanges the code with Keycloak **server-to-server**, verifies the ID token signature against the realm JWKS (RS256, aud/iss/exp checked), mints its own signed JWT, and redirects back to NextAuth with a one-time code → NextAuth exchanges the code at `POST /api/auth/token` → fetches the profile at `GET /api/auth/userinfo`.

### Endpoints

| Method | Path                    | Purpose                                                                  |
|--------|-------------------------|--------------------------------------------------------------------------|
| GET    | `/api/auth/authorize`   | OAuth authorization endpoint for NextAuth; 302 → Keycloak. Validates client_id, redirect_uri allowlist, response_type, state. |
| GET    | `/api/auth/keycloak/callback` | Receives the code from Keycloak, exchanges it, verifies the ID token, mints the coop-api JWT, hands a one-time code back to NextAuth. |
| POST   | `/api/auth/token`       | One-time code → `{ access_token, id_token, token_type, expires_in }`. Accepts client credentials via Basic auth (openid-client default) or form fields. Single-use codes, 2-minute TTL. The `id_token` is an HS256 JWT signed with `OAUTH_CLIENT_SECRET` (`iss=coop-api`, `aud=nextauth`) — openid-client 5.7+ requires it for code flows. |
| GET    | `/api/auth/userinfo`    | Bearer coop-api JWT → `{ sub, id, email, name, avatar, status }`. |
| GET    | `/api/auth/onboarding/status` | Bearer JWT → `{ onboarded, profile }` — onboarding authority for all frontends. |
| POST   | `/api/auth/onboarding`  | Bearer JWT + `{ displayName, avatar? }` → marks the user onboarded; profile merged into future JWTs. |
| GET    | `/api/auth/config`      | Diagnostics: prints the effective URL chain (the redirect-URI matrix). |
| POST   | `/api/safe/predict`     | Bearer JWT + `{ saltNonce }` → `{ safeAddress }` — pure CREATE2 prediction, no chain call, nothing stored. |
| POST   | `/api/safe/deploy` (alias `/api/onboard`) | Bearer JWT + `{ saltNonce }` → deploys the user's Safe proxy via the backend signer (gas sponsorship). Returns `{ safeAddress, txHash }`. Persists **nothing**. |

### Uncorrelatable Safe provisioning

Safe proxy addresses are CREATE2-deterministic, so no identity → onchain mapping is ever stored:

- The client derives `saltNonce` from user-held material (its own secret); coop-api never knows how it was derived and never stores it.
- `POST /api/safe/predict` computes the address from `saltNonce` (pure math — clients can do this locally too).
- `POST /api/safe/deploy` deploys via the SafeProxyFactory with the backend signer paying gas; the salt travels only in the request body, and request logs carry no user id, salt, or address.
- The SafeProxy creation code is embedded and **must match the exact artifact the on-chain factory deploys** (this workspace's compile of safe-contracts 1.4.1-2: solc 0.8.20, optimizer runs 200 — the npm-published artifact differs and predicts wrong addresses). Re-extract from `contracts/artifacts` after any Safe/compiler change. Salt formula is the 1.4.1-2 `createProxyWithNonce`: `keccak256(keccak256(initializer) || saltNonce)` — the initializer (owners/threshold) is part of the address.

Env: `SAFE_SINGLETON_ADDRESS`, `SAFE_PROXY_FACTORY_ADDRESS`, `SAFE_BACKEND_SIGNER_KEY`, `RPC_URL` (local Hardhat `http://127.0.0.1:8545`; deploy via `contracts/scripts/deploy_local.ts`).

### Security properties

- Keycloak client credentials live **only** here (never in the Next.js app).
- ID tokens verified: RS256 signature against realm JWKS + audience + issuer + expiry.
- One-time codes: `crypto.randomUUID()`, single use, 2-minute TTL, lazy expiry pruning.
- Client secrets compared with `crypto.timingSafeEqual`.
- `redirect_uri` validated against an explicit allowlist in both directions.

### Onboarding & account linking

- Onboarding profile store: JSON file at `data/profiles.json` (`COOP_PROFILE_STORE` env). Dev-grade — swap for Postgres when coop-api gets a real DB (the `profile-store.ts` module is the seam).
- The onboarding display name/avatar win over the identity-provider claims when minting JWTs (see `mintCoopJwt`).
- Account linking across login methods happens in the Next.js app (`allowDangerousEmailAccountLinking` on the coop-api provider) — emails are Google-verified via Keycloak, so linking by email is safe. The frontends call `/api/auth/onboarding/status` to detect new users.

## Environment variables

| Variable                  | Default                                   | Purpose                                        |
|---------------------------|-------------------------------------------|------------------------------------------------|
| `PORT`                    | `3001`                                    | HTTP port                                      |
| `JWT_SECRET`              | `local-development-secret-irl-coop-v4`    | HS256 secret for coop-api JWTs (shared with `/api/onboard` validation) |
| `KEYCLOAK_ISSUER`         | `http://localhost:8081/realms/irl-coop`   | Keycloak realm issuer                          |
| `KEYCLOAK_CLIENT_ID`      | `coop-api`                                | Confidential Keycloak client (created via admin API) |
| `KEYCLOAK_CLIENT_SECRET`  | —                                        | Keycloak client secret                         |
| `COOP_API_BASE_URL`       | `http://localhost:3001`                   | Public base URL used in the Keycloak redirect_uri |
| `OAUTH_CLIENT_ID`         | `nextauth`                                | Client id NextAuth presents to this bridge     |
| `OAUTH_CLIENT_SECRET`     | —                                        | Shared secret between NextAuth and this bridge |

## Local run

```bash
# 1. Keycloak stack (postgres + keycloak on :8081)
docker compose -f infra/compose/authentication/docker-compose.yml up -d

# 2. This service (from repo root)
npm run dev --workspace=apps/coop-api   # or: cd apps/coop-api && npm run dev
```

On startup the service logs the complete redirect-URI matrix — if a login fails with `redirect_uri_mismatch`, check that printout first.

## Troubleshooting

- **`unauthorized_client` (Invalid client or Invalid client credentials)** — `KEYCLOAK_CLIENT_SECRET` in `.env` no longer matches Keycloak's stored secret (it changes if anyone regenerates it in Admin Console → Clients → `coop-api` → Credentials, or if a setup script runs twice). Re-sync `.env` and restart.
- **`id_token not present in TokenSet` in NextAuth** — openid-client 5.7+ validates an `id_token` for every code flow. This service returns one (HS256, signed with `OAUTH_CLIENT_SECRET`). If you remove it, NextAuth will fail; the NextAuth-side provider must keep `issuer: "coop-api"` and `client: { id_token_signed_response_alg: "HS256" }`.
- **Local E2E login without Google** — create a local user in the realm (Admin Console → Users, or the admin API) and use its username/password on Keycloak's login page; the Google broker is an extra option, not a requirement.

## Mobile / additional frontends

The OAuth surface is a plain, standard OAuth2 provider. A mobile app can register itself as an additional `OAUTH_CLIENT_*` pair (add its callback to `ALLOWED_REDIRECTS`) and reuse the exact same `authorize` / `token` / `userinfo` flow — no Keycloak credentials ever ship to the device. The resulting coop-api JWT is the app's credential for the API.
