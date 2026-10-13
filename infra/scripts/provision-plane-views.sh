#!/usr/bin/env bash
# Provision per-member group-scoped VIEWS over Plane's tables.
#
# No mirror, no copy: the view is a WHERE clause on Plane's own rows, scoped to
# (a) public projects in a workspace the member belongs to, (b) projects they are
# a direct member of, and (c) projects owned by a coop group they hold a seat in.
# The member's group list is resolved HERE, from the coop DB, at view-creation
# time — nothing about membership is duplicated into Plane's schema.
#
# Re-run after a membership change; it is idempotent (CREATE OR REPLACE).
#
# Usage: infra/scripts/provision-plane-views.sh [consumer_role]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PG="${PG_CONTAINER:-storage-postgres-1}"
COOP_DB="${COOP_DB:-irlcoop}"
PLANE_DB="${PLANE_DB:-plane}"
CONSUMER="${2:-${CONSUMER:-nocodb}}"
TEMPLATE="$ROOT/infra/compose/storage/scripts/plane_user_view.sql"

# Coop side reads as the owner (this is PROVISIONING, not runtime).
coop_q() { docker exec "$PG" psql -U irlcoop -d "$COOP_DB" -tA -c "$1"; }
# Plane side runs as the plane role (owns the schema it creates views in).
plane_q() { docker exec "$PG" psql -U plane -d "$PLANE_DB" -tA -c "$1"; }

echo "== provision group-scoped Plane views (consumer: $CONSUMER) =="
subs=$(coop_q "SELECT DISTINCT sub FROM group_members
                WHERE sub IS NOT NULL AND sub NOT IN ('seed-bot','heya')
                  AND sub NOT LIKE 'journey-%'
                  AND sub NOT LIKE 'journey-invitee-%'")

N=0
while IFS= read -r sub; do
  [ -z "$sub" ] && continue
  # the member's group ids (personal groups simply never match a project group_id)
  gids=$(coop_q "SELECT COALESCE('ARRAY[' || string_agg(quote_literal(group_id::text), ',') || ']::uuid[]', 'ARRAY[]::uuid[]')
                   FROM group_members WHERE sub = '$sub'")
  # NOTE: the template already carries the `plane_projects__` prefix, so this is
  # the SANITIZED SUB ONLY (double-prefixing also blew past the 63-char identifier
  # limit and silently truncated the view name).
  name="$(printf '%s' "$sub" | tr -c '[:alnum:]' '_')"

  # substitute into the template (python for safe quoting, then apply)
  python3 - "$TEMPLATE" "$sub" "$name" "$gids" <<'PY' > /tmp/plane-view.sql
import sys, pathlib
tpl, sub, name, gids = sys.argv[1:5]
sql = pathlib.Path(tpl).read_text()
sql = sql.replace("%SUB_SANITIZED%", name).replace("%SUB%", sub).replace("%GROUP_IDS%", gids)
print(sql)
PY
  out=$(docker exec -i "$PG" psql -U plane -d "$PLANE_DB" -v ON_ERROR_STOP=1 < /tmp/plane-view.sql 2>&1 | tail -1)
  case "$out" in
    CREATE\ VIEW) echo "  ok   $name"; N=$((N+1)) ;;
    *) echo "  FAIL $name -> $out" ;;
  esac
  # grant to the consumer role when that role exists (NocoDB's external source)
  if [ -n "$(plane_q "SELECT 1 FROM pg_roles WHERE rolname='$CONSUMER'")" ]; then
    plane_q "GRANT SELECT ON plane_projects__$name TO $CONSUMER" >/dev/null 2>&1 && true
  fi
done <<< "$subs"
rm -f /tmp/plane-view.sql

echo "provisioned $N view(s)"