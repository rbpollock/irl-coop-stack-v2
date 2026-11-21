
# Infrastructure bring-up — reproducible dev stack

**Status: operational as of 2026-11-20.**

This document is the single source of truth for bringing the `irl.coop` dev stack
from a cold host to a fully running federation layer. It assumes you have
`development/irl-coop-stack-v2` cloned and the `secrets/` tree in place
(`master.key`, `vault-pass`, certs).

## What "reproducible" means here

The same commands, in the same order, on the same host, produce the same running
services. No manual `docker exec` SQL, no hand-typed `nft` rules, no ad-hoc
environment variables. All infrastructure state is either:

1. **In the repo** (`apps/*.yaml`, `firewall.nft`, `scripts/*.sh`, `bootstrap-keycloak.py`)
2. **Generated from the repo** (`generator.py` → `infra/out/dev/`)
3. **Secrets on disk** (`infra/instances/dev/secrets/`)

## Prerequisites

```bash
cd ~/development/irl-coop-stack-v2

# 1. Secrets tree exists
ls infra/instances/dev/secrets/master.key
ls infra/instances/dev/secrets/vault-pass
ls infra/instances/dev/certs/fullchain.pem  # or run certbot

# 2. Docker is installed and running
systemctl is-active docker

# 3. Postgres data is at /opt/app/storage/data/postgres (or will be created)
#    Do NOT point it at a dev-path override unless you intend to start fresh.
```

## The one-shot bring-up

```bash
cd ~/development/irl-coop-stack-v2

# ── 1. Regenerate all derived configs ────────────────────────────────────────
python3 infra/build/generator.py dev

# ── 2. Start storage (postgres + minio) ──────────────────────────────────────
cd infra/out/dev/compose/storage
sudo docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

# ── 3. Create the keycloak database (first run only) ────────────────────────
#    Keycloak uses the shared postgres but keeps its own database.
#    The app spec declares the connection; the DB itself must exist.
sudo docker exec storage-postgres-1 psql -U postgres -c "
  CREATE USER keycloak WITH PASSWORD '$(python3 -c '
import hmac, sys;
m = open("infra/instances/dev/secrets/master.key").read().strip();
p = hmac.new(b"irl.coop", bytes.fromhex(m), "sha256").digest();
out, t, c = b"", b"", 1;
while len(out) < 32:
  t = hmac.new(p, t + b"irlcoop/keycloak.db" + bytes([c]), "sha256").digest();
  out += t; c += 1;
print(out[:32].hex())
')';"
sudo docker exec storage-postgres-1 psql -U postgres -c "CREATE DATABASE keycloak OWNER keycloak;"
sudo docker exec storage-postgres-1 psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;"

# ── 4. Start the authentication pillar (Keycloak) ────────────────────────────
cd ../authentication
sudo docker compose up -d

# ── 5. Bootstrap the irl-coop realm (idempotent) ────────────────────────────
sleep 20
python3 ~/development/irl-coop-stack-v2/infra/scripts/bootstrap-keycloak.py

# ── 6. Start the proxy (Traefik) ────────────────────────────────────────────
cd ../proxy
sudo docker compose up -d

# ── 7. Start host apps (coop-api, dashboard) ────────────────────────────────
cd ~/development/irl-coop-stack-v2
bash infra/scripts/stack-up-hosts.sh

# ── 8. Start Hermes WebUI ───────────────────────────────────────────────────
sudo systemctl start hermes-webui

# ── 9. Apply the declarative firewall ───────────────────────────────────────
bash infra/scripts/apply-firewall.sh dev
```

### Verification

```bash
curl -k -H "Host: hermes.irl.coop" -w "hermes: %{http_code}\n" --max-time 5 https://127.0.0.1
curl -k -H "Host: auth.irl.coop"   -w "auth:   %{http_code}\n" --max-time 5 https://127.0.0.1
curl -k -H "Host: api.irl.coop"    -w "api:    %{http_code}\n" --max-time 5 https://127.0.0.1
curl -k -H "Host: irl.coop"        -w "apex:   %{http_code}\n" --max-time 5 https://127.0.0.1
```

All should return `302`, `200`, or `307`.

## The three declarative systems

### 1. App specs → generated compose

Every deployable unit is declared in `infra/instances/dev/apps/*.yaml`.

```yaml
# infra/instances/dev/apps/keycloak.yaml
name: keycloak
pillar: authentication
type: image
image: quay.io/keycloak/keycloak:25.0.6
command: start-dev
ports:
  - "8081:8081"
env:
  KC_DB: postgres
  KC_DB_URL: jdbc:postgresql://storage-postgres-1:5432/keycloak
  # ...
proxy:
  hostname: auth.${DOMAIN}
  port: 8081
```

`generator.py` reads all `apps/*.yaml`, resolves `${SECRET:name}` and `${DOMAIN}`,
and emits:

- `infra/out/dev/compose/<pillar>/docker-compose.yml`
- `infra/out/dev/compose/proxy/dynamic.yml` (Traefik routers)
- `infra/out/dev/keycloak/clients.yaml` (OIDC client registry)
- `infra/out/dev/secrets.env` (resolved secrets for host processes)

**Regenerate after every app change:**

```bash
python3 infra/build/generator.py dev
```

### 2. Declarative firewall

`infra/instances/dev/firewall.nft` is the base template. It declares:

- `policy drop` on the `inet filter` table
- Accept loopback, established/related, ICMP
- Accept SSH from the LAN (`192.168.18.0/24`)
- Accept HTTP/HTTPS from anywhere (Traefik edge)
- Accept Tailnet (`100.64.0.0/10`, `fd7a:115c:a1e0::/48`)
- Accept Docker bridge traffic TO a set of backend ports

The backend ports are generated dynamically by reading every `apps/*.yaml`:

```bash
python3 infra/build/generate-firewall.py dev
# emits: backend_ports = { 3000, 3001, 3010, 8787, 8081 }
```

Then applied and persisted:

```bash
bash infra/scripts/apply-firewall.sh dev
```

This disables UFW's conflicting `ip filter` table, loads the rules, and saves
them to `/etc/nftables.d/irl-coop.nft` so they survive reboot.

**Why not blanket `docker0 accept`?**
Any compromised container could reach every host service. The explicit port list
is the smallest surface — only ports Traefik back-ends to are reachable from the
bridge.

### 3. Keycloak realm bootstrap

The realm is programmatic. `bootstrap-keycloak.py` is idempotent:

- Creates the `irl-coop` realm if missing
- Creates every OIDC client from `clients.yaml` + `web-app`
- Grants `realm-management/manage-users` to the coop-api service account
- Copies the `browser` flow to `browser-passkey`
- Adds a flat `webauthn-authenticator-passwordless` execution at the top
- Sets the RP policy (`auth.irl.coop`, ES256)
- Wires the realm to use `browser-passkey`

Run it after every Keycloak recreation or client change:

```bash
python3 infra/scripts/bootstrap-keycloak.py
```

## Networking model

The stack uses three network scopes:

| Scope | Who | How |
|---|---|---|
| **Host loopback** | Traefik → backend via `http://172.17.0.1:<port>` | Docker bridge gateway; backend port must be in `backend_ports` set |
| **Container names** | Cross-compose service discovery | Containers join each others' networks via `external: true`; see `authentication/docker-compose.override.yml` |
| **Tailscale** | Remote access | `tailnet-only` Traefik middleware allows `100.64.0.0/10` etc |

### The postgres connection story

Keycloak originally used `jdbc:postgresql://172.17.0.1:5432/keycloak`. After the
storage pillar was consolidated, this broke — `172.17.0.1:5432` is only valid
if postgres publishes that port to the host. The fix: Keycloak now connects to
`storage-postgres-1:5432` by joining the `storage_default` network.

```yaml
# authentication/docker-compose.override.yml
services:
  keycloak:
    networks:
      - storage_default
      - default
networks:
  storage_default:
    external: true
```

This means postgres **does not need** to publish 5432 on the host for Keycloak
to work. It still does publish 5432 for host processes (coop-api dev server),
which is fine.

## Known gaps

These are stated, not hidden.

| Gap | Impact | Workaround |
|---|---|---|
| Keycloak DB is not auto-created by `generator.py` | Manual step 3 above required on first bring-up | Script block in this doc; could be added to `generator.py` or a DB init migration |
| `bootstrap-keycloak.py` does not configure Google broker secrets | Google SSO won't work after bootstrap | Log into admin console, set client ID/secret manually; or extend `bootstrap-keycloak.py` to read vault |
| No `k8s` path | Docker-only today | The pillar + compose model porting cleanly to a k8s operator is the intended next step |
| Backup does not include Keycloak realm data | Realm must be re-bootstrapped on full restore | `bootstrap-keycloak.py` + users re-provision via invite-on-first-signin (coop-api) |

## Design decisions

### Why `backend_ports` derives from `apps/*.yaml`?

Because the alternative is a manual step every time a new service is added.
With the generated list, adding a new app to `apps/*.yaml` and regenerating
the compose also updates the firewall. One source of truth.

### Why container names instead of `172.17.0.1` for cross-pillar DB?

Because it removes the need for host-published ports between containers,
reduces surface, and makes the compose files valid regardless of whether the
host bridge gateway is at `.1` or another address.

### Why not add `service` to the `docker` group?

Docker socket access is root-equivalent. During the 2026-11-08 incident, the
attacker held `service` for ~3 hours. A `docker exec` into any container
would have given them full host access. Keeping `sudo` as a deliberate barrier
is the right trade-off for a single-operator dev box.

### Why no `keycloak-db` sidecar?

The original v1/v2 compose had one. Deleting it and using the shared postgres
is simpler: one data volume, one backup target, one health check. The cost is
the manual `CREATE DATABASE` step on first bring-up.

## Troubleshooting

**`auth.irl.coop => 502` or `000`**
- Keycloak container down: `sudo docker logs authentication-keycloak-1`
- Keycloak DB missing: check `\\l` in postgres for `keycloak`
- Wrong postgres connection: verify `KC_DB_URL` points to `storage-postgres-1:5432`

**`hermes.irl.coop => 403`**
- `tailnet-only` middleware active; verify client IP is in the allow list
- Docker-published-port source IP is in RFC1918, not `127.0.0.1` — the
  middleware allows `10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16` for this reason

**`hermes.irl.coop => 000` (timeout)**
- `backend_ports` in `firewall.nft` missing the Hermes WebUI port (8787)
- Re-run `bash infra/scripts/apply-firewall.sh dev`

**Postgres port 5432 not listening**
- Storage compose override missing the port mapping
- Verify `infra/out/dev/compose/storage/docker-compose.override.yml` has
  `ports: ['0.0.0.0:5432:5432']`

## Files that matter

| File | What it is | Edit this? |
|---|---|---|
| `infra/instances/dev/apps/*.yaml` | App manifest specs | **Yes** — the source of truth |
| `infra/build/generator.py` | Compose/dynamic/proxy generator | Only to add new generators |
| `infra/instances/dev/firewall.nft` | Firewall base template | **Yes** — for policy changes |
| `infra/build/generate-firewall.py` | Emits `backend_ports` from app specs | Only to change the port heuristic |
| `infra/scripts/apply-firewall.sh` | Generate + apply + persist | **Yes** — for persist logic |
| `infra/scripts/bootstrap-keycloak.py` | Keycloak realm bootstrap | **Yes** — to add realm features |
| `infra/instances/dev/instance.yaml` | Pillar assignment + domain | **Yes** — to add/remove pillars |
| `infra/out/dev/compose/**` | Generated compose files | **No** — regenerate instead |
| `infra/out/dev/compose/**/docker-compose.override.yml` | Dev overrides (volumes, networks) | **Yes, carefully** — these augment the generated base |

## Changelog

- **2026-11-20** — Documented the full bring-up after the 2026-11-08 incident.
  Keycloak migrated from dedicated container to shared postgres;
  `backend_ports` now includes 8787 (Hermes WebUI);
  `bootstrap-keycloak.py` written as idempotent automation;
  networking switched from `172.17.0.1` to container-name discovery.
