#!/usr/bin/env bash
# Run the Postiz SSO journey (generic OIDC -> Keycloak -> Postiz) in the
# browser-runner. Derives the e2e-test password from master.key, then mounts
# the journeys dir as a SUBDIRECTORY of /app (so the image's playwright
# node_modules stays resolvable).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

derive() {
  python3 - "$1" <<'PY'
import hmac as hm, sys
master = open("/home/service/development/irl-coop-stack-v2/infra/instances/dev/secrets/master.key").read().strip()
name = sys.argv[1]
prk = hm.new(b"irl.coop", bytes.fromhex(master), "sha256").digest()
out, t, c = b"", b"", 1
info = b"irlcoop/" + name.encode()
while len(out) < 32:
    t = hm.new(prk, t + info + bytes([c]), "sha256").digest()
    out += t; c += 1
print(out[:32].hex())
PY
}

E2E_USER="${E2E_USER:-e2e-test@irl.coop}"
E2E_PASSWORD="$(derive keycloak.e2e-test)"

docker run --rm \
  -v "$ROOT/infra/scripts/journeys:/app/journeys" \
  -w /app \
  -e "E2E_USER=$E2E_USER" -e "E2E_PASSWORD=$E2E_PASSWORD" \
  irlcoop/browser-runner node journeys/postiz-oauth.mjs 2>&1 | grep -vE "Fontconfig|DevTools|Download the|host.docker|GPU|swiftshader|dbus|GL implementation"
exit "${PIPESTATUS[0]}"
