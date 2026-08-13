# Browser management pillar — design

The managed browser-automation layer for the fleet. Automations run as
ephemeral, containerized Playwright runners, orchestrated by Temporal, and
their evidence lands in MinIO. Secrets needed by an automation are released
at run time from the Safe-anchored vault (see `private-treasury-guards-ledgers.md`).

## Layers

1. **Automations panel** (full-kit, mirrors the Files panel) — list, create,
   schedule, and inspect automations and their evidence.
2. **browser-farm** — ephemeral `irlcoop/browser-runner` containers. Each run
   is one container: deterministic Chromium (Playwright's base image), the
   scenario harness copied in, evidence (screenshots/artifacts) written to
   `/tmp` and collected to MinIO.
3. **Temporal orchestration** — automations are workflows; each run is an
   activity that dispatches a runner container. The panel schedules →
   coop-api enqueues → Temporal runs → the activity calls the runner →
   evidence back.

## The runner image (`infra/build/images/browser-runner/`)

- `FROM mcr.microsoft.com/playwright:v1.46.0` — node + chromium + deps
  pre-baked, no browser download, no npm dance.
- Harnesses staged from `apps/web/full-kit/e2e/` (the full-kit workspace owns
  them; the image context does not).
- `build.sh` stages into `infra/out/browser-runner` (gitignored) and builds
  `irlcoop/browser-runner:latest`.
- Two uses: dev/test harness (`docker run irlcoop/browser-runner node
  /app/e2e/<scenario>.mjs`) and the fleet runtime (Temporal activities; the
  spec contract — JSON inputs in, evidence out — lands with the activity
  slice).

## Scenarios

- `files-flow` — passkey login (enrollment on first run) + the files-panel
  flow. The first automation; proves the whole chain.
- `linking-flow` — the passkey ↔ existing-account linking: the account
  console's Signing-in section, the secondary-mechanism login (Google for
  members), the WebAuthn ceremony, the credential bound to the SAME user.

## Passkey specifics

- The browser-flow copy `browser-passkey` (Keycloak 25.0.6) renders the
  login page; enrollment happens via the `webauthn-register-passwordless`
  required action on the first login.
- The CDP virtual authenticator makes the ceremony deterministic (no Google
  leg, no interactive prompt) — the E2E unlock for the whole fleet.

## Secrets

- Runner containers get inputs via env at dispatch time (e.g.
  `E2E_PASSWORD`), never baked into the image.
- Long-lived automation secrets: Safe-anchored vault, released in the
  runner's memory at run time (see the vault design).
