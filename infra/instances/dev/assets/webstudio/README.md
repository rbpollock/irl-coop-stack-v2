# Webstudio Gate-SSO patch (durable source of truth)

The custom builder image `irlcoop/webstudio-builder-gate-sso` (referenced in
`infra/instances/dev/apps/webstudio.yaml`) is the community fork
`webstudio-community/webstudio-fork` with one patch on top of `develop`.

We have **no push access** to the community fork, and the working clone
(`/tmp/webstudio-fork`) is tmpfs — this directory is the durable copy of the patch.

## The patch

`gate-sso.patch` — Gate-SSO auto-login + the "Log in with irl.coop" button
(4 files under `apps/builder/app/`):

- `env/env.server.ts` — `GATE_SSO_ENABLED` in the zod schema + `rawEnv`.
- `shared/db/user.server.ts` — `createOrLoginWithGate(context, email)` (provider `gate-sso`).
- `routes/_ui.login._index.tsx` — loader auto-login on `x-forwarded-email`.
- `auth/login.tsx` — the primary "Log in with irl.coop" button.

## Base

- Repo: https://github.com/webstudio-community/webstudio-fork
- Branch: `develop`
- Base commit: `da1f9bb98a002f7d13232fcc448cb6da70f6fc0d`
  ("fix(self-hosting): forward buildMode to the publisher service (#45)")

## Re-apply + rebuild

```bash
git clone https://github.com/webstudio-community/webstudio-fork /tmp/webstudio-fork
cd /tmp/webstudio-fork
git checkout da1f9bb98a002f7d13232fcc448cb6da70f6fc0d
git apply /home/service/development/irl-coop-stack-v2/infra/instances/dev/assets/webstudio/gate-sso.patch
docker build -f apps/builder/Dockerfile -t irlcoop/webstudio-builder-gate-sso:<tag> .
```

Then bump the tag in `webstudio.yaml`, regenerate, and `up -d webstudio
webstudio-gate`. (Full procedure in the `webstudio-self-host` skill.)
