#!/usr/bin/env bash
# Run the NocoDB diagnostic (diag-nocodb.mjs) as e2e-test via the browser-runner.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
E2E_USER="${E2E_USER:-e2e-test@irl.coop}"

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

docker run --rm -v "$ROOT/infra/scripts/diag-nocodb.mjs:/app/diag.mjs" \
  -w /app -e "E2E_USER=$E2E_USER" -e "E2E_PASSWORD=$E2E_PASSWORD" \
  irlcoop/browser-runner node diag.mjs 2>&1 | grep -vE "Fontconfig|DevTools|Download the|host.docker"
