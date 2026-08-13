#!/usr/bin/env bash
# Seed NocoDB with prepopulated bases (Coop Groups, Projects) from the live
# projection: irlcoop.groups/group_members/resource_scopes + plane-db projects.
# Idempotent-ish: find-or-create bases/tables, append rows, link every workspace
# user as owner so all members see them. Re-run after a data wipe.
#
#   infra/scripts/seed-nocodb-bases.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
E2E_USER="${E2E_USER:-e2e-test@irl.coop}"

# 1. derive the e2e-test keycloak password (never echoed)
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

# 2. snapshot the live projection -> /tmp/nocodb-seed-data.json
python3 - <<'PY'
import json, subprocess
def psql(db, sql):
    if db == "irlcoop":
        cmd = ["docker","exec","-u","postgres","storage-postgres-1","psql","-d","irlcoop","-t","-A","-F","|","-c",sql]
    else:
        cmd = ["docker","exec","-u","postgres","plane-db","psql","-U","plane","-d","plane","-t","-A","-F","|","-c",sql]
    out = subprocess.check_output(cmd, text=True).strip()
    return [l.split("|") for l in out.splitlines()] if out else []
def d(columns, rows):
    return [dict(zip(columns, list(r) + [""]*(len(columns)-len(r)))) for r in rows]
json.dump({
    "groups": d(["Name","Safe Address","Privacy","Description"], psql("irlcoop","SELECT name, safe_address, privacy, COALESCE(description,'') FROM groups ORDER BY created_at")),
    "members": d(["Group","Sub","Roles","Alias","Visibility"], psql("irlcoop","SELECT g.name, gm.sub, array_to_string(gm.roles,','), COALESCE(gm.alias,''), gm.visibility FROM group_members gm JOIN groups g ON g.id=gm.group_id ORDER BY gm.created_at")),
    "resources": d(["Group","App","Resource Key"], psql("irlcoop","SELECT g.name, rs.app, rs.resource_key FROM resource_scopes rs JOIN groups g ON g.id=rs.group_id ORDER BY rs.scoped_at")),
    "projects": d(["Name","Identifier","Visibility","Safe Address"], psql("plane","SELECT name, identifier, network, COALESCE(safe_address,'') FROM projects WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 50")),
}, open("/tmp/nocodb-seed-data.json","w"))
print("projection snapshot written")
PY

# 3. seed via the browser-runner (token + gate cookie live in the browser)
docker run --rm -v /tmp:/tmp -v "$ROOT/infra/scripts/seed-nocodb-bases.mjs:/app/seed.mjs" \
  -w /app -e "E2E_USER=$E2E_USER" -e "E2E_PASSWORD=$E2E_PASSWORD" \
  irlcoop/browser-runner node seed.mjs 2>&1 | grep -vE "Fontconfig|DevTools|Download the|host.docker"

# 4. link every workspace user as owner of the seeded bases (so all members see them)
docker exec -u postgres storage-postgres-1 psql -d nocodb -c "
INSERT INTO nc_base_users_v2 (base_id, fk_user_id, roles)
SELECT b.id, wu.fk_user_id, 'owner'
FROM nc_bases_v2 b
CROSS JOIN workspace_user wu
WHERE b.title IN ('Coop Groups','Projects')
ON CONFLICT DO NOTHING;
" >/dev/null
echo "base users linked"
