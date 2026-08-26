#!/usr/bin/env bash
# One-off issuance of the *.studio.irl.coop wildcard cert (Webstudio canvas
# preview subdomains p-<projectId>.studio.irl.coop). Reuses the same acme.sh +
# Gandi LiveDNS DNS-01 mechanism as renew-cert.sh (the key is sourced from
# there, never echoed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTANCE="$ROOT/instances/dev"
LEGO_STATE="$INSTANCE/certs/lego"
CERTDIR="$INSTANCE/certs/studio.irl.coop"

# Reuse the Gandi key already held in renew-cert.sh (no new secrets, never printed).
GANDI_API_KEY="$(grep -oP 'GANDI_API_KEY="\K[^"]+' "$ROOT/scripts/renew-cert.sh" | head -1)"
export GANDI_API_KEY
export GANDI_LIVEDNS_KEY="$GANDI_API_KEY"

mkdir -p "$CERTDIR" "$LEGO_STATE"

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e GANDI_API_KEY \
  -e GANDI_LIVEDNS_KEY \
  -v "$LEGO_STATE":/acme.sh \
  -v "$ROOT/scripts/dns_gandi_livedns.sh":/acmebin/dnsapi/dns_gandi_livedns.sh:ro \
  neilpang/acme.sh \
  --issue --dns dns_gandi_livedns --server letsencrypt \
  -d '*.studio.irl.coop' \
  --keylength ec-256

cp "$LEGO_STATE"/*.studio.irl.coop_ecc/fullchain.cer "$CERTDIR/fullchain.pem"
cp "$LEGO_STATE"/*.studio.irl.coop_ecc/*.studio.irl.coop.key "$CERTDIR/privkey.pem"
chmod 600 "$CERTDIR/privkey.pem"

echo "issued -> $CERTDIR"
openssl x509 -in "$CERTDIR/fullchain.pem" -noout -subject -dates
