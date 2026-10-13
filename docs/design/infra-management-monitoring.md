# Infrastructure Management & Monitoring

The irl.coop stack — how it is declared, brought up, tracked, and watched.
Built 2026-08-12 (commit 4ad2e32 + follow-ups). Status surface: dashboard
home (`/en/dashboards/overview` → "Stack health"), login motd, and
`GET /api/v1/stack/status`.

## The model: declared vs running

The stack has two states, and the gap between them is the management problem:

- **Declared** — `infra/instances/dev/` (instance.yaml + `apps/<app>.yaml`)
  is the source of truth. The generator (`infra/build/generator.py`) emits
  deployment artifacts into `infra/out/dev/` (gitignored): one compose per
  pillar, the Traefik file-provider config (`dynamic.yml`, the LIVE edge),
  the Keycloak client registry, ansible inventory/playbooks, derived
  secrets.env, and MANIFEST.md.
- **Running** — `docker ps -a`. Containers carry compose `project`/`service`
  labels, which is what makes reconciliation exact (never name-matching:
  Plane's container names are nonstandard).

The **reconciler** compares the two. Everything declared-but-not-running is
a gap (missing/down). Everything running-but-not-declared is drift
(**orphans** — the old pre-pipeline bootstraps surface here). This is the
v2-shaped replacement for the v1 "docker-bridge" idea: because the tree
already declares every container, we get drift detection for free instead of
a raw socket read.

## The pipeline (declared → applied)

1. Edit the tree (add `apps/<name>.yaml`, list it in instance.yaml).
2. `uv run --with pyyaml python infra/build/generator.py dev` — pure
   function, wipes + rewrites `infra/out/dev/`.
3. `docker compose -f infra/out/dev/compose/<pillar>/docker-compose.yml -f
   .../docker-compose.override.yml up -d <service>`.
4. `docker restart proxy-traefik-1` — the file-provider inotify breaks on
   atomic rewrites of `dynamic.yml` (known, expected).
5. Provision the OIDC client from `out/dev/keycloak/clients.yaml`; DNS is
   covered by the `*.irl.coop` wildcard.

`enabled: false` on a spec = declared-but-not-wired: no compose service,
edge route, OIDC entry, or inventory (webstudio/formbricks/postiz are parked
this way — their images are not deployable). The spec remains as the intent
record.

## Bring-up & lifecycle

`infra/scripts/stack-up.sh` — idempotent `docker compose up -d` for every
generated pillar (+ overrides), then `type: source` apps (Plane's own
compose), then drifted bootstraps whose compose still exists. It then hands off
to `infra/scripts/stack-up-hosts.sh` for the **host-process apps** (`web`,
`coop-api`, `peer_xyz_payments`, `treasury-relayer`, `hardhat`), which have no
compose at all. Exits nonzero if any project fails.

Systemd: `irl-coop-stack.service` (enabled, oneshot, RemainAfterExit,
After=docker.service) runs it at boot. A failed bring-up lands the unit in a
visible `failed` state — that is the boot-time error flag. Retry with
`systemctl restart irl-coop-stack`.

**Host apps need their own watchdog, because nothing supervises them.**
`irl-coop-hosts-watchdog.timer` (every 2 min, `OnBootSec=3min`) re-runs the
already-idempotent `stack-up-hosts.sh`; because that script health-checks each
port and starts only what is not answering, re-running it *is* the self-heal.
This exists because `ts-node-dev --respawn` recovers from a **crash** but not
from a **TypeScript compile error** — it exits and never respawns, leaving a
live process tree and a dead port. On 2026-09-29 a mid-edit save to
`apps/coop-api/src/safe.ts` did exactly that and `https://api.irl.coop` returned
502 until 2026-10-03. The watchdog bounds that to minutes. Note it also revives
`hardhat` and the temporal worker — stopping any host app on purpose means
stopping the timer too.

Individual containers that predate the pipeline (stalwart16) were given
`--restart unless-stopped` so they survive reboots; the long-term fix is a
proper spec so they are declared like everything else.

## Monitoring surfaces — one reconciler, three windows

Same data, three renderings:

1. **coop-api endpoint** `GET /api/v1/stack/status` (`apps/coop-api/src/
   status.ts`) — auth-gated like every coop-api route. Shape:
   `summary {declared, up, down, healthy, orphans}` · `pillars[]` (id,
   pillar, kind tree|source, compose, declared, up, down, missing[],
   services[] each with container {name, state, health, status, image,
   ports} or null) · `host_apps[]` · `orphans[]`.
2. **Dashboard** — "Stack health" on the home page
   (`components/dashboards/stack-health.tsx`): 4 summary cards, one chip
   per pillar with a dot per service (green running / red down), missing
   services listed, orphan banner. Polls every 30s with the NextAuth
   accessToken as Bearer (same pattern as the docs page).
3. **Login motd** `/etc/update-motd.d/99-irl-coop-stack` + **CLI**
   `infra/scripts/stack-report.py` — stdlib-only twin (no yaml dep: reads
   declared services via `docker compose config --services`), for the host
   where the API/auth may be down. Also writes the boot JSON snapshot to
   `/var/lib/irl-coop/stack-status.json`.

### The host-process leg (why "61/61" is not the whole story)

The reconciler's view of the world is `docker ps`, so **an app with no
container is invisible to it**. The host-process apps (above) therefore have
their own leg, declared once in `infra/instances/dev/host-apps.yaml` and read
by *both* implementations — `host_apps[]` plus
`summary {host_apps, host_healthy, core_host_apps, core_host_healthy,
core_host_problems}`. Each is probed on `127.0.0.1:<port>` (the address the
edge itself targets); **any HTTP response counts as up** — a 401 is a live,
auth-gated server — and only a refused/timed-out connection is a failure.
`role: dev` (today: `hardhat`) is reported but not counted.

This is not decoration. Until 2026-10-03 the report read **"✓ 61/61 core
services healthy"** for four days while `https://api.irl.coop` returned 502 on
every route — the compose count was perfectly accurate and completely useless.
The headline now carries both buckets:

```
irl.coop stack — ✓ 61/61 core services healthy · ✓ 4/4 host apps healthy
```

and goes red on either. Liveness is probed on the **port**, never inferred from
a process list — the wedged coop-api had a healthy-looking supervisor tree the
whole time.

## Reading the flags (honest, not noise)

- **down** — exited/created/missing. `plane-migrator` exits 0 by design
  (one-shot migrations) and is reported down; read the exit code.
- **health** — only present where a service declares a healthcheck (the
  Plane stack and `admin/space/web`; most pillars don't declare one yet).
- **orphans** — running-but-undeclared. Today: `cache-redis-1` and
  `stalwart16` (superseded bootstraps). An orphan after an app is removed
  from the tree is the reconciler noticing the container was left behind.
- **currently flagged as genuinely broken**: `cryptpad` (crashes on start —
  needs first-run setup) and `temporal` (its compose points at a postgres
  hostname that doesn't resolve across compose projects). These are real
  wiring gaps the flagging exists to surface — fixing them is normal app
  work, and the motd/dashboard will go green when they're fixed.

## Access

The endpoint is member-auth-gated (any signed-in coop identity). The
dashboard section is the member view; the motd is the operator view; the
edge and container lifecycle remain operator-side. Member-facing
management (start/stop/restart from the web) is deliberately NOT built yet
— this layer is observe-first.

## Operational playbooks

- **After a reboot** — nothing to do: the systemd unit brings everything
  up; `systemctl status irl-coop-stack` (or the login motd) shows the
  result.
- **Something's down** — the motd names it, the dashboard colors it. Fix
  the app, or `docker compose -f <pillar compose> up -d <service>`.
- **Add an app** — write the spec, regenerate, up, restart traefik. It is
  tracked automatically from the next status call (no code changes).
- **Remove an app** — delete the spec + list entry, regenerate, `docker
  compose -f <pillar> rm -sf <service>`; if you forget the rm, the
  container shows up as an orphan.

## Known limitations / next steps

- Healthcheck coverage is patchy (only where specs declare it) — declaring
  healthchecks per pillar would make "healthy" meaningful stack-wide.
- No metrics, logs, or alerting yet (no Prometheus/Grafana; the motd +
  failed-unit + dashboard IS the alert surface). Docker events → notifier
  is the natural next layer.
- cryptpad + temporal wiring (see flags above).
- stalwart16 into the tree.
- The irl-coop-stack skill's SKILL.md is at its size cap and should shed
  inline content into references/.
