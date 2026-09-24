#!/usr/bin/env bash
# Capture the gated irl.coop surfaces (needs/offers, calls, dashboard, cinny)
# by deriving the e2e-test keycloak password in-memory (never echoed) and
# running the passkey login inside the browser-runner container.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
E2E_USER="${E2E_USER:-e2e-test@irl.coop}"
OUT="${1:-$ROOT/docs/design/session-story/render/art}"

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

mkdir -p "$OUT"
docker run --rm \
  -v "$ROOT/apps/web/irl-dashboard/e2e/capture-gated.mjs:/app/capture.mjs:ro" \
  -v "$OUT:/app/out" \
  -w /app \
  -e "E2E_USER=$E2E_USER" -e "E2E_PASSWORD=$E2E_PASSWORD" \
  -e "E2E_OUT_DIR=/app/out" \
  irlcoop/browser-runner node capture.mjs 2>&1 | grep -vE "Fontconfig|DevTools|Download the|host.docker|dbus|GLib|GLES|VAAPI"
echo "captures -> $OUT"