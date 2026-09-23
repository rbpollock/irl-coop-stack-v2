#!/usr/bin/env bash
# Enforce the NocoDB visibility model: members see ONLY their own group bases.
#
# NocoDB's base list has two access paths: (1) an explicit per-base grant in
# nc_base_users_v2 (what sync-base-members maintains from group membership), and
# (2) a workspace-level-role fallback that includes EVERY base in the workspace
# for any user whose workspace_user.roles != 'workspace-level-no-access'.
#
# So a member with a stale workspace role (owner/viewer/etc) sees every base in
# the workspace — a cross-tenant visibility leak. The correct state:
#   - members (canonical identities)  -> workspace-level-no-access
#   - the super admin (broker identity) -> workspace-level-owner (sole admin)
#
# Idempotent. Run after any bootstrap that might mint workspace roles.
#
# Usage: infra/scripts/enforce-nocodb-visibility.sh
set -euo pipefail

PG_CONTAINER="${PG_CONTAINER:-storage-postgres-1}"
NOC_DB="${NOC_DB:-nocodb}"

NOC_PW="$(grep -oE 'p=[0-9a-f]+' /home/service/development/irl-coop-stack-v2/infra/out/dev/compose/storage/docker-compose.yml | head -1 | cut -d= -f2)"

psql_noc() {
  docker exec -e PGPASSWORD="$NOC_PW" "$PG_CONTAINER" \
    psql -h 127.0.0.1 -U nocodb -d "$NOC_DB" -tA -c "$1"
}

echo "=== BEFORE ==="
psql_noc "SELECT u.email, wu.roles FROM workspace_user wu JOIN nc_users_v2 u ON u.id=wu.fk_user_id ORDER BY u.email;"

# 1. Members (everyone who is NOT the super admin) -> no-access.
psql_noc "
UPDATE workspace_user wu
SET roles = 'workspace-level-no-access'
FROM nc_users_v2 u
WHERE wu.fk_user_id = u.id
  AND u.roles NOT LIKE '%super%'
  AND wu.roles IS DISTINCT FROM 'workspace-level-no-access';
"

# 2. Super admin -> workspace-level-owner (normalize the legacy 'owner' value).
psql_noc "
UPDATE workspace_user wu
SET roles = 'workspace-level-owner'
FROM nc_users_v2 u
WHERE wu.fk_user_id = u.id
  AND u.roles LIKE '%super%'
  AND wu.roles IS DISTINCT FROM 'workspace-level-owner';
"

echo "=== AFTER ==="
psql_noc "SELECT u.email, wu.roles FROM workspace_user wu JOIN nc_users_v2 u ON u.id=wu.fk_user_id ORDER BY u.email;"
