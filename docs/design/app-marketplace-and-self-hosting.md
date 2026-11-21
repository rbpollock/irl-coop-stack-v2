
# App marketplace and self-hosted extensions

**Status: design · 2026-11-20.**

How does a node operator add apps? How does the federation agree on "canonical"
software? How does a developer ship a new app into the ecosystem?

## Two kinds of apps

| | Canonical apps | Self-hosted extensions |
|---|---|---|
| **What** | Curated, federation-approved apps in `infra/instances/dev/apps/*.yaml` | Custom apps a group builds or installs for themselves |
| **Who decides** | The `app-stewards` subgroup (Safe threshold vote) | The group itself, no external approval |
| **Where they run** | On any node that opts in | Only on that group's node |
| **Trust model** | Blessed by Safe vote, reproducible builds, attested digests | Self-attested; group takes full responsibility |
| **Example** | Keycloak, Plane, NocoDB, Temporal, the whole declared stack | A custom inventory tracker, a local-only CRM, a bespoke payment adapter |
| **Discovery** | Shown in every node's dashboard | Not shown; installed by URL or file upload |

## Canonical app lifecycle

### 1. Proposal (any developer)

A developer writes an app spec and opens a PR:

```yaml
# apps/proposals/soil-sensor-hub.yaml
name: soil-sensor-hub
pillar: environmental
type: image
image: docker.io/example/soil-sensor-hub:v1.2.3@sha256:abc...
# ↑ pinned by digest, not tag
ports:
  - "9090:9090"
env:
  API_KEY: ${SECRET:soil-sensor.api_key}
proxy:
  hostname: soil.${DOMAIN}
  port: 9090
dev:
  volumes:
    - "./assets/soil-sensor/config.json:/app/config.json:ro"
```

The PR includes:
- `apps/proposals/*.yaml` — the app spec
- `docs/design/proposals/soil-sensor-hub.md` — integration design
- `infra/build/images/soil-sensor-hub/Dockerfile` — reproducible build
- `apps/coop-api/src/integrations/soil-sensor-hub.ts` — coop-api integration (if any)
- `apps/web/irl-dashboard/src/app/(dashboard-layout)/apps/soil-sensor-hub/page.tsx`— dashboard page

### 2. Review (app-stewards subgroup)

The `app-stewards` subgroup is a Safe with threshold governance. Members are:
- One infrastructure engineer
- One security reviewer  
- One community representative
- Threshold: 2-of-3 to bless a release

They evaluate:
- **Security:** Does the app need excessive permissions? Can it run in a restricted network?
- **Integration:** Does it follow the event bus schema? Does it respect RLS?
- **Reproducibility:** Is the Dockerfile deterministic? Is the base image pinned by digest?
- **Privacy:** Does it phone home? Does it need external APIs?
- **Sustainability:** Can the app be maintained if the original developer leaves?

The review outcome is recorded on-chain:

```solidity
// CoopRegistry.sol
struct AppBlessing {
    bytes20 gitCommit;
    bytes32 imageDigest;
    bytes20 approvedBy;       // Safe address of app-stewards
    uint256 approvedAt;
    uint8 trustTier;          // 1=experimental, 2=stable, 3=critical
}
mapping(string => AppBlessing) public blessedApps;
// key = app name (e.g. "soil-sensor-hub")
```

### 3. Blessing (Safe vote)

The app-stewards Safe proposes: `"Bless soil-sensor-hub at commit abc123, digest sha256:xyz..., tier 2."`

Threshold members review and sign. On execution:
1. The `AppBlessing` is written to `CoopRegistry.sol`.
2. The app spec is moved from `apps/proposals/` to `infra/instances/dev/apps/`.
3. The dashboard renders the app in the official app list.
4. The app is added to the `generate-firewall.py` port extraction.

### 4. Node adoption (operator choice)

Node operators see blessed apps in their dashboard:

```
Available apps:
  [✓] Keycloak           (tier 3, blessed 2026-10-01)
  [✓] Plane              (tier 3, blessed 2026-09-15)
  [ ] soil-sensor-hub    (tier 2, blessed 2026-11-20) ← NEW
  [ ] zulip-chat         (tier 1, blessed 2026-11-18) ← EXPERIMENTAL

[Install selected] [View details] [Propose new app]
```

Installing an app:
1. Operator checks the box.
2. The app spec is added to `instance.yaml` (or an operator override file).
3. `generator.py dev` regenerates the compose.
4. `docker compose up -d` starts the app.
5. `apply-firewall.sh dev` opens the port.

**Operators can skip blessed apps.** A node might run only 10 of 30 canonical
apps. There is no requirement to install everything.

### 5. Revocation (if needed)

If a blessed app is found vulnerable or abandoned:
1. App-stewards propose revocation.
2. Safe threshold signs.
3. `CoopRegistry` marks the blessing as revoked.
4. Dashboards show a warning: "soil-sensor-hub revoked (CVE-2026-1234). Uninstall?"
5. Operators who installed it see the warning and can uninstall in one click.

## Self-hosted extensions

### How a group adds their own app

No approval needed. The group edits their local `instance.yaml`:

```yaml
# infra/instances/dev/instance.yaml (local override)
apps:
  - name: custom-inventory-tracker
    pillar: custom
    type: image
    image: myregistry.com/inventory:v1@sha256:abc...
    ports:
      - "9999:9999"
    proxy:
      hostname: inventory.${DOMAIN}
      port: 9999
```

Or they mount a source directory:

```yaml
  - name: bespoke-crm
    pillar: custom
    type: source
    source: /home/mygroup/bespoke-crm
    command: npm start
    ports:
      - "9998:3000"
```

**The dashboard shows self-hosted apps separately:**

```
Installed apps:
  Canonical:     [Keycloak] [Plane] [NocoDB] ...
  Self-hosted:   [inventory] [bespoke-crm]
```

### Self-hosted app risks (stated honestly)

| Risk | Mitigation |
|---|---|
| Image not pinned by digest | Warning in dashboard; operator must confirm |
| No reproducible build | Not blocked, but flagged |
| Excessive permissions | Dashboard warns if app requests host network or privileged mode |
| No coop-api integration | Works standalone; no group data access |
| Security audit absent | Operator assumes full risk; liability is theirs |

## The app manifest format

The common language between canonical and self-hosted apps:

```yaml
name: string          # unique identifier
pillar: string        # which subsystem (auth, data, communication, etc.)
type: image | source  # prebuilt image or local source
dependencies:         # other apps this one needs
  - postgres
  - redis
image: string         # for type: image, with digest pin
source: string        # for type: source, absolute path
command: string       # override default container command
ports: [string]       # host:container mappings
env: {string: string} # environment variables, ${SECRET:name} supported
volumes: [string]     # host:container mounts
dev:
  volumes: [string]   # dev-only mounts (not in production)
proxy:
  hostname: string    # Traefik router hostname
  port: int           # backend service port
  middlewares: [string] # Traefik middlewares (tailnet-only, etc.)
federation:
  compatible: bool    # can this app federate across nodes?
  event_types: [string] # which bus events it produces/consumes
```

## The developer experience

### To propose a canonical app:

1. Fork `irl-coop-stack-v2`.
2. Write the app spec + integration code.
3. Open a PR against `main`.
4. The app-stewards review. If approved, the PR is merged and the app is blessed.
5. Your app appears in every node's "available apps" list.

### To ship a self-hosted app:

1. Write the app spec.
2. Place it in your node's `instance.yaml` or an override file.
3. `generator.py dev && docker compose up -d`.
4. It works. No approval, no blessing, no waiting.

### To build an app that integrates with coop-api:

1. Read the event bus schema (`docs/design/event-bus-and-group-shapes.md`).
2. Listen for events your app cares about.
3. Produce events that other apps might care about.
4. Use the coop-api GraphQL endpoint for structured data.
5. Authenticate via the standard OIDC flow (same as every other app).

## Discoverability

### For canonical apps

The dashboard queries `CoopRegistry.sol` for blessed apps and renders them.
Filtering: by pillar, by trust tier, by popularity (how many nodes installed it).

### For self-hosted apps

There is no central index. Discovery is social:
- A group publishes their app spec on their website.
- Other groups copy the spec and adapt it.
- Word spreads via Matrix, Mastodon, in-person.
- Popular self-hosted apps may graduate to canonical status through the blessing process.

## Economics

| Who pays | For what |
|---|---|
| Developer | Their time building the app. No platform fee. |
| App-stewards | Their time reviewing. Compensated by the irl.coop steward group (treasury). |
| Node operator | Hosting costs for the apps they install. |
| User | Nothing directly. Apps are infrastructure, not SaaS. |

There is no app store tax. No platform rent. The irl.coop model is:
**cooperative infrastructure, not extractive marketplace.**

## Open questions

1. **Should canonical apps be forced open-source?** The blessing process could
   require source availability for reproducible builds. But some apps might be
   proprietary yet still federate-friendly. Where is the line?

2. **How does a group fork a canonical app?** If Plane is blessed but a group
   wants a modified Plane, do they (a) maintain a fork as self-hosted, (b) propose
   the modification upstream, or (c) run the official Plane and patch via config?

3. **What is the revocation process for critical apps?** If Keycloak has a CVE,
   can app-stewards unilaterally revoke it, or does the irl.coop main group
   vote? The main group has higher threshold and slower response.

4. **Can a canonical app be deprecated?** What happens to nodes running an old
   Plane version when the blessed version moves forward? Auto-update? Warning?
   Grace period?

5. **How do self-hosted apps federate?** A self-hosted CRM on Detroit might want
to share data with Portland. Does it use the same federation gateway as canonical
apps, or does it need its own integration?
