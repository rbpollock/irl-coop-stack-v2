#!/usr/bin/env bash
# Create the shared "Coop" NocoDB base as a LIVE external source over the
# irlcoop projection (groups / group_members / resource_scopes). The bundle
# patch (2026.08.4) injects the caller's sub as app.sub, so Postgres RLS scopes
# rows per-user through NocoDB.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
E2E_USER="${E2E_USER:-e2e-test@irl.coop}"

# derive the e2e-test keycloak password in-memory (never echoed)
E2E_PASSWORD="$(python3 - <<'PY'
import hmac as hm
master = open("/home/service/development/irl-coop-stack-v2/infra/instances/dev/secrets/master.key").read().strip()
prk = hm.new(b"irl.coop", bytes.fromhex(master), "sha256").digest()
out, t, c = b"", b"", 1
info = b"irlcoop/keycloak.e2e-test"
while len(out) < 32:
    t = hm.new(prk, t + info + bytes([c]), "sha256").digest()
    out += t; c += 1
print(out[:32].hex())
PY
)"

# derive the coop Postgres role password from master.key — same HKDF as the
# generator's ${SECRET:postgres.coop} (templated config). In-memory, never echoed.
COOP_DB_PASSWORD="$(python3 - <<'PY'
import hmac as hm
master = open("/home/service/development/irl-coop-stack-v2/infra/instances/dev/secrets/master.key").read().strip()
prk = hm.new(b"irl.coop", bytes.fromhex(master), "sha256").digest()
out, t, c = b"", b"", 1
info = b"irlcoop/postgres.coop"
while len(out) < 32:
    t = hm.new(prk, t + info + bytes([c]), "sha256").digest()
    out += t; c += 1
print(out[:32].hex())
PY
)"

docker run --rm -v "$ROOT/infra/scripts/create-coop-source.mjs:/app/create.mjs" \
  -w /app -e "E2E_USER=$E2E_USER" -e "E2E_PASSWORD=$E2E_PASSWORD" \
  -e "COOP_DB_HOST=postgres" -e "COOP_DB_PORT=5432" -e "COOP_DB_USER=coop" \
  -e "COOP_DB_PASSWORD=$COOP_DB_PASSWORD" -e "COOP_DB_NAME=irlcoop" \
  irlcoop/browser-runner node create.mjs 2>&1 | grep -vE "Fontconfig|DevTools|Download the|host.docker"
