# DevOps — Build, Extend, Maintain

Status: design · 2026-10-04.

The stack is **declarative, generated, and verifiable**. You describe what you want in YAML; the
generator produces Docker Compose; the reconciler checks that reality matches the declaration.

Changes are **small, reversible, and traceable**. No hand-editing generated files. No snowflake
servers. Every change is a commit; every commit is a deploy.

---

## What already works (live)

| Primitive | How it works | Where to read more |
|---|---|---|
| **Generator** | YAML specs → `infra/out/dev/compose/`. Idempotent; `rmtree`s `out/` each run. | `infra/build/generator.py` (source) |
| **Stack report** | `stack-report.py` — declared vs running containers, status per service. | `infra/scripts/stack-report.py` (source) |
| **Journey suite** | 29/30 browser-automated end-to-end tests (SSO, group creation, file upload, etc.). | `infra/scripts/journeys/` (source) |
| **Reconcilers** | DNS enumeration (mail), `provisionOnSignIn` (ERPNext), drift detection. | [`where-facts-live.md`](/design/where-facts-live) · [`app-admission-audit.md`](/design/app-admission-audit) |
| **Version-controlled plugins** | WordPress plugins mounted read-only from `assets/wordpress/`, driven by wp-cli. | [`site-plugins-and-embeds.md`](/design/site-plugins-and-embeds) · [`wordpress-migration-to-wordpress-com.md`](/design/wordpress-migration-to-wordpress-com) |

---

## The admission bar

An app joins the vetted operational set only when it clears five gates:

| Gate | What it means | Reference |
|---|---|---|
| **Mapping** | tenant ↔ group via `resource_scopes` | [`where-facts-live.md`](/design/where-facts-live) §4.1 |
| **Identity gate** | Fleet SSO reaches the app (oauth2-proxy or native OIDC) | [`member-scoped-app-access.md`](/design/member-scoped-app-access) |
| **Event leg** | The app produces typed events on the bus | [`event-bus-and-group-shapes.md`](/design/event-bus-and-group-shapes) |
| **Marker** | The app carries an immutable `group_id` in its own fields | [`declared-binding-registry.md`](/design/declared-binding-registry) §3 |
| **Reconciler** | A job repairs drift by enumerating from the authoritative side | [`app-admission-audit.md`](/design/app-admission-audit) |

**No app currently clears all five.** The gap concentrates in **marker** and **reconciler**.
Mail is the reference implementation: DNS TXT as marker, DNS enumeration as reconciler.

---

## What is designed, not yet built

| Feature | Status | Where to read more |
|---|---|---|
| **Seam drills** | Periodic provider-swap tests to verify continuity. | [`provider-seams.md`](/design/provider-seams) |
| **Dev/prod parity** | Today dev and prod share one instance. True isolation (separate instance, separate vault) is designed but not funded. | `infra/instances/` (source layout) |
| **Observability** | Metrics, alerting, SLOs. Temporal reports health; Prometheus is not deployed. | [`infra-management-monitoring.md`](/design/infra-management-monitoring) |
| **Central resource store** | Operational records (kind 5 facts) stay in the app; everything else is coop-owned. | [`central-resource-store.md`](/design/central-resource-store) · [`where-facts-live.md`](/design/where-facts-live) |

---

## Open questions

- **Who operates the stack?** Currently Robbie is the sole steward. The cooperative governance
  model says members elect stewards, but the election mechanism is designed, not implemented.
- **What happens when the steward is unavailable?** The Safe threshold requires multiple signers,
  but day-to-day ops (restart, deploy, debug) currently depend on one person.

---

## Honest limits

- The journey suite is 29/30. One test (`nocodb-write`) fails silently.
- `stack-report.py` can time out when Docker is under load.
- The Traefik → `plane_default` network connect was applied manually at runtime and is **not**
  encoded in the generator. It will be lost on proxy recreation.

See [`irl-coop-overview.md`](/design/irl-coop-overview) for how this pillar fits into the whole platform.
