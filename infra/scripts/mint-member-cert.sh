#!/usr/bin/env bash
# Mint a per-member Postgres client certificate for cert-based auth.
#
# A2/A3 (NocoDB per-user identity): each member is a LOGIN Postgres role whose
# client cert CN == role name. The role inherits coop_member (NOLOGIN group)
# for projection table privileges; RLS scopes rows via coop_role_sub() ->
# session_user. This script mints ONE member cert.
#
# Usage: infra/scripts/mint-member-cert.sh <role_name> [days]
#
# Layout (all under infra/instances/dev/secrets/pg-client-certs/ — gitignored):
#   ca/ca.key, ca/ca.crt     — the coop client-auth CA (ca.key NEVER leaves host)
#   members/<role>.key       — the member's EC P-256 private key (their vault/passkey key class)
#   members/<role>.crt       — the member's signed client cert (CN = role name)
#
# The CA is created once (idempotent). Cert CN == role name because Postgres
# `cert` auth compares the cert CN to the requested database username.

set -euo pipefail

ROLE="${1:?usage: mint-member-cert.sh <role_name> [days]}"
DAYS="${2:-365}"

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTDIR="$BASE/instances/dev/secrets/pg-client-certs"
CADIR="$CERTDIR/ca"
MEMDIR="$CERTDIR/members"

mkdir -p "$CADIR" "$MEMDIR"
chmod 700 "$CERTDIR" "$CADIR" "$MEMDIR"

# --- CA (once) -------------------------------------------------------------
if [ ! -f "$CADIR/ca.crt" ]; then
  openssl ecparam -name prime256v1 -genkey -noout -out "$CADIR/ca.key"
  chmod 600 "$CADIR/ca.key"
  openssl req -x509 -new -key "$CADIR/ca.key" -sha256 -days 3650 \
    -subj "/CN=irl.coop pg-client CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -out "$CADIR/ca.crt"
  echo "created CA: $CADIR/ca.crt"
fi

# --- member key + cert -----------------------------------------------------
if [ -f "$MEMDIR/$ROLE.crt" ] || [ -f "$MEMDIR/$ROLE.key" ]; then
  echo "cert/key already exist for role '$ROLE' — refusing to overwrite" >&2
  exit 1
fi

openssl ecparam -name prime256v1 -genkey -noout -out "$MEMDIR/$ROLE.key"
chmod 600 "$MEMDIR/$ROLE.key"

openssl req -new -key "$MEMDIR/$ROLE.key" -sha256 \
  -subj "/CN=$ROLE" \
  -out "$MEMDIR/$ROLE.csr"

openssl x509 -req -in "$MEMDIR/$ROLE.csr" \
  -CA "$CADIR/ca.crt" -CAkey "$CADIR/ca.key" -CAcreateserial \
  -days "$DAYS" -sha256 \
  -extfile <(printf "basicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=clientAuth\nsubjectAltName=DNS:%s\n" "$ROLE") \
  -out "$MEMDIR/$ROLE.crt"

rm -f "$MEMDIR/$ROLE.csr"

echo "minted:"
echo "  cert: $MEMDIR/$ROLE.crt"
echo "  key : $MEMDIR/$ROLE.key"
openssl x509 -in "$MEMDIR/$ROLE.crt" -noout -subject -enddate
