#!/usr/bin/env bash
# Provision the FULL per-member identity chain (A2/A3) for every real member:
#   LOGIN role  +  GRANT coop_member  +  coop_member_role(role -> sub)  +  client cert.
#
# A member without this chain falls back to the `coop` role + app.sub GUC
# injection, which has NO USAGE on the grp_* schemas -> "permission denied for
# schema grp_<uuid>" when NocoDB opens any table in a group/personal base.
#
# Idempotent: existing role/mapping/cert are left alone.
#
# Usage: infra/scripts/provision-member-certs.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

psql_super() {
  docker exec -u postgres "$PG_CONTAINER" psql -d "$PG_DB" -tA -c "$1"
}

# role name = coop_m_ + first 8 alnum chars of the sub (stable, unique-enough,
# SQL-safe identifier). Cert CN == role name (pg `cert` auth requires it).
role_for_sub() {
  echo "coop_m_$(echo "$1" | tr -cd '[:alnum:]' | cut -c1-8)"
}

# Real members: personal-group owners + collective group members. Exclude seed/test
# artifacts (seed-bot, heya, journey-*). e2e-litefarm-sub is a placeholder sub kept
# as-is; its role name is derived the same way.
subs="$(psql_super "SELECT DISTINCT sub FROM group_members WHERE sub IS NOT NULL AND sub NOT IN ('seed-bot','heya') AND sub NOT LIKE 'journey-%' UNION SELECT DISTINCT created_by FROM groups WHERE kind='personal' AND created_by NOT IN ('seed-bot','heya') AND created_by NOT LIKE 'journey-%'")"

COUNT=0
while IFS= read -r sub; do
  [ -z "$sub" ] && continue
  role="$(role_for_sub "$sub")"

  # 1. role (LOGIN, no password needed — cert auth; inherits coop_member)
  if [ "$(psql_super "SELECT count(*) FROM pg_roles WHERE rolname='$role'")" = "0" ]; then
    psql_super "CREATE ROLE $role LOGIN" >/dev/null
    echo "created role $role"
  else
    echo "role $role exists"
  fi
  # 2. inherit coop_member (group-schema USAGE + view SELECT)
  psql_super "GRANT coop_member TO $role" >/dev/null
  # 3. role -> sub mapping (RLS resolves session_user via coop_role_sub())
  psql_super "INSERT INTO coop_member_role (role_name, sub) VALUES ('$role', '$sub') ON CONFLICT (role_name) DO NOTHING" >/dev/null
  # 4. client cert (CN = role)
  "$ROOT/infra/scripts/mint-member-cert.sh" "$role" >/dev/null 2>&1 \
    && echo "  cert minted for $role -> $sub" \
    || echo "  cert already present for $role"

  COUNT=$((COUNT+1))
done <<< "$subs"

echo "provisioned $COUNT member identity chain(s)"
