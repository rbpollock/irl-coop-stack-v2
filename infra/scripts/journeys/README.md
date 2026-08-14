# Journey-based test suite

An end-to-end suite organised around **user journeys** rather than unit-level
endpoints. Each journey walks one narrative path a real member takes through the
stack and asserts the security/behavioural invariants along it.

## Run

```
infra/scripts/journeys.sh
```

Credentials are derived in-memory from `master.key` (never echoed, never written
to disk). Exit code is non-zero on any failure.

## Journeys

| Journey | Description | Key invariants |
| --- | --- | --- |
| `identity-isolation` (host) | RLS contrast as the `coop` role | each user sees exactly their own personal group; anonymous sees 0 |
| `sign-in` | A member signs in via SSO | OIDC discovery + JWKS; password grant → coop JWT; wrong/no token rejected |
| `groups-scope` | A member sees + manages their groups | RLS-scoped read; personal group auto-provisioned; owner PATCH works; non-owned → 403 |
| `membership` | A member onboards a collaborator | create group (Safe deploy); seat a member; scope a resource |
| `nocodb-read` | A member works in the shared Coop base | bases list renders (no spinner); read returns RLS-scoped rows |
| `nocodb-write` | A member edits a group row | write-path identity (`app.sub`) — owner PATCH round-trips |
| `anonymous` | An anonymous visitor is walled off | every surface rejects a missing/bad token; NocoDB returns nothing |

## Layout

- `journeys.sh` — entry point: derives credentials, runs the host-side isolation
  check, then launches the browser-runner for the API + NocoDB journeys.
- `run.mjs` — runner (loads + executes journeys, reports a unified summary).
- `lib.mjs` — shared harness (env, results accumulator, coop-api client, passkey
  login).
- `journeys/*.mjs` — one file per journey; each exports `{ name, description, run(ctx) }`.

## Why two execution contexts

- **Host** (`journeys.sh`): the identity-isolation check needs `psql` as the
  `coop` role — the `postgres` superuser **bypasses** `FORCE ROW LEVEL SECURITY`,
  so the contrast must connect as the app role to actually observe RLS.
- **browser-runner**: SSO/NocoDB journeys need Playwright (passkey flow) and the
  shared NocoDB `xc-auth` token. `create group` (Safe deploy) degrades to a
  graceful `SKIP` when the Safe contracts / RPC aren't configured (503).

## Extending

Add `infra/scripts/journeys/journeys/<name>.mjs` exporting `run(ctx)`; register
it in `run.mjs` (`apiJourneys` or `browserJourneys`). Use `ctx.check(name, ok,
detail)` for assertions and `ctx.skip(name, detail)` for a graceful skip.
