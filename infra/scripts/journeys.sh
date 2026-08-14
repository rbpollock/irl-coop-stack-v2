#!/usr/bin/env bash
# Journey-based test suite for the irl.coop stack.
#
# Part 1 (host): identity-isolation — each user sees exactly their own personal
#   group and anonymous sees nothing (RLS contrast, run as the `coop` role so
#   FORCE ROW LEVEL SECURITY actually applies; the postgres superuser bypasses it).
# Part 2 (browser-runner): the SSO / groups / NocoDB user journeys.
#
# Usage:  infra/scripts/journeys.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
E2E_USER="${E2E_USER:-e2e-test@irl.coop}"
MASTER="$ROOT/infra/instances/dev/secrets/master.key"
PG_HOST="${PG_HOST:-127.0.0.1}"
PG_CONTAINER="${PG_CONTAINER:-storage-postgres-1}"
PG_DB="${PG_DB:-irlcoop}"

derive() { # derive <name> -> 64-hex secret (HKDF-SHA256, salt irl.coop, info irlcoop/<name>)
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

E2E_PASSWORD="$(derive keycloak.e2e-test)"
COOP_PW="$(derive postgres.coop)"

psql_coop() { # run SQL as the coop role (RLS applies); never aborts the suite
  docker exec -e PGPASSWORD="$COOP_PW" "$PG_CONTAINER" \
    psql -h "$PG_HOST" -U coop -d "$PG_DB" -tA -c "$1" 2>/dev/null || true
}

psql_admin() { # superuser — enumerate across RLS boundaries (metadata only)
  docker exec -u postgres "$PG_CONTAINER" psql -d "$PG_DB" -tA -c "$1" 2>/dev/null || true
}

FAIL=0

# ---- Part 1: identity isolation (RLS contrast) ------------------------------
echo "== identity-isolation: RLS contrast (as coop role)"
# Enumerate personal-group owners as SUPERUSER (the coop role can't see across
# RLS — with no app.sub set it sees zero rows, which is itself the point of RLS).
subs="$(psql_admin "SELECT DISTINCT created_by FROM groups WHERE kind='personal'")"
if [ -z "$subs" ]; then
  echo "  FAIL no personal groups found"
  FAIL=1
else
  while IFS= read -r sub; do
    [ -z "$sub" ] && continue
    n="$(psql_coop "SELECT set_config('app.sub','$sub',false); SELECT count(*) FROM groups WHERE kind='personal'" | tail -1)"
    if [ "$n" = "1" ]; then
      echo "  PASS $sub sees exactly its own personal group [1]"
    else
      echo "  FAIL $sub personal-group scope [$n]"
      FAIL=1
    fi
  done <<< "$subs"
fi

anon="$(psql_coop "SELECT set_config('app.sub','anonymous',false); SELECT count(*) FROM groups" | tail -1)"
if [ "$anon" = "0" ]; then
  echo "  PASS anonymous sees 0 groups [0]"
else
  echo "  FAIL anonymous sees groups [$anon]"
  FAIL=1
fi

# ---- Part 2: SSO / groups / NocoDB user journeys ----------------------------
echo ""
# Mount as a SUBDIRECTORY of /app so the image's node_modules (playwright) stays
# resolvable; mounting over /app would shadow it.
docker run --rm \
  -v "$ROOT/infra/scripts/journeys:/app/journeys" \
  -w /app \
  -e "E2E_USER=$E2E_USER" -e "E2E_PASSWORD=$E2E_PASSWORD" \
  irlcoop/browser-runner node journeys/run.mjs 2>&1 | grep -vE "Fontconfig|DevTools|Download the|host.docker"
BR_EXIT=${PIPESTATUS[0]}

# Cleanup: drop journey-created test groups (projection + members + scopes via
# FK cascade; the on-chain Safe lives on the disposable local Hardhat node).
psql_admin "DELETE FROM groups WHERE name LIKE 'journey-%'" >/dev/null

echo ""
if [ "$FAIL" = "1" ] || [ "${BR_EXIT:-0}" != "0" ]; then
  echo "SUITE FAILED"
  exit 1
fi
echo "SUITE PASSED"
