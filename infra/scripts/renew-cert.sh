#!/usr/bin/env bash
# irl.coop wildcard cert renewal — Gandi LiveDNS DNS-01 via acme.sh (docker).
#
# Renews BOTH wildcards served by the edge:
#   - *.irl.coop          (apex + every single-label app subdomain)
#   - *.studio.irl.coop   (Webstudio canvas previews, p-<projectId>.studio.irl.coop)
#
# Renewal-window guard (for the daily cron): each cert only RUNS inside the
# 3-day window around its own renewal date (day before / day of / day after),
# where the renewal date = cert expiry - 30 days (matches the CA's ARI window).
# Emergency fallback: renew if a cert expires within 10 days (missed window),
# or if the cert files are missing entirely (fresh issuance).
# The edge (traefik) is restarted ONLY when the cert files actually change.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTANCE="$ROOT/instances/dev"
LEGO_STATE="$INSTANCE/certs/lego"
DAY=86400
CHANGED=0

# Gandi LiveDNS v5 API key (secrets: kept in this script, like the other dev creds).
# NOTE: Gandi now issues 40-char keys; lego's gandi provider still enforces the
# old 24-char format, so we use acme.sh instead. The current provider id is
# dns_gandi_livedns (the old `dns_gandi` id no longer ships in the image).
export GANDI_API_KEY="742b0202c573115a1bf7e992baff6406400a11ab"
# the dns_gandi_livedns hook reads GANDI_LIVEDNS_KEY (not GANDI_API_KEY)
export GANDI_LIVEDNS_KEY="$GANDI_API_KEY"

mkdir -p "$LEGO_STATE"

# issue_cert <name> <wildcard> [extra -d domains...]
# The WILDCARD is the acme.sh cert-dir name (a literal `*.`-prefixed path).
issue_cert() {
  local name="$1"
  local first="$2"
  shift 2
  local CERTDIR="$INSTANCE/certs/$name"

  # --- renewal-window guard ----------------------------------------------
  if [ -f "$CERTDIR/fullchain.pem" ]; then
    local END_DATE RENEW_EPOCH EXPIRE_EPOCH TODAY_EPOCH IN_WINDOW
    END_DATE="$(openssl x509 -in "$CERTDIR/fullchain.pem" -noout -enddate | cut -d= -f2)"
    RENEW_EPOCH="$(date -d "$END_DATE -30 days" +%s)"
    EXPIRE_EPOCH="$(date -d "$END_DATE" +%s)"
    TODAY_EPOCH="$(date +%s)"
    IN_WINDOW=0
    # the 3-day window: the day before, the day of, the day after the renewal date
    if [ "$TODAY_EPOCH" -ge $((RENEW_EPOCH - DAY)) ] && [ "$TODAY_EPOCH" -le $((RENEW_EPOCH + DAY)) ]; then
      IN_WINDOW=1
    fi
    # emergency catch-up: the cert is about to expire (the window was missed)
    if [ "$TODAY_EPOCH" -ge $((EXPIRE_EPOCH - 10 * DAY)) ]; then
      IN_WINDOW=1
    fi
    if [ "$IN_WINDOW" != 1 ]; then
      echo "$(date -Is) $name not in the renewal window — no-op"
      return 0
    fi
  else
    echo "$(date -Is) $name cert missing — issuing fresh"
  fi

  echo "$(date -Is) $name in the renewal window — renewing"
  local before after
  before="$(sha256sum "$CERTDIR/fullchain.pem" "$CERTDIR/privkey.pem" 2>/dev/null || true)"
  mkdir -p "$CERTDIR"

  local DOMAIN_ARGS=(-d "$first")
  local extra
  for extra in "$@"; do
    DOMAIN_ARGS+=(-d "$extra")
  done

  docker run --rm \
    --user "$(id -u):$(id -g)" \
    -e GANDI_API_KEY \
    -e GANDI_LIVEDNS_KEY \
    -v "$LEGO_STATE":/acme.sh \
    -v "$ROOT/scripts/dns_gandi_livedns.sh":/acmebin/dnsapi/dns_gandi_livedns.sh:ro \
    neilpang/acme.sh \
    --issue --dns dns_gandi_livedns --server letsencrypt \
    "${DOMAIN_ARGS[@]}" \
    --keylength ec-256

  # acme.sh layout: <state>/<first-domain>_ecc/{fullchain.cer, <first-domain>.key}
  # (the dir is named after the FIRST domain, which is the literal wildcard `*.`).
  # Literal (quoted) paths — the leading `*` is a filename char, NOT a glob.
  local SRC="$LEGO_STATE/${first}_ecc"
  cp "$SRC/fullchain.cer" "$CERTDIR/fullchain.pem"
  cp "$SRC/${first}.key" "$CERTDIR/privkey.pem"
  chmod 600 "$CERTDIR/privkey.pem"

  after="$(sha256sum "$CERTDIR/fullchain.pem" "$CERTDIR/privkey.pem" 2>/dev/null)"
  if [ "$before" != "$after" ]; then
    CHANGED=1
    echo "$(date -Is) $name renewed"
  else
    echo "$(date -Is) $name unchanged"
  fi
}

issue_cert "irl.coop" "*.irl.coop" "irl.coop"
issue_cert "studio.irl.coop" "*.studio.irl.coop"

if [ "$CHANGED" = 1 ]; then
  echo "cert files changed — restarting the edge"
  # traefik re-reads the cert files on restart (a file-provider config touch
  # with identical content does NOT trigger a reload — traefik compares bytes)
  docker restart proxy-traefik-1 >/dev/null 2>&1 || true
  # FreeSWITCH serves WSS from the SAME *.irl.coop wildcard: restart it so its
  # entrypoint re-combines fullchain+privkey into wss.pem and mod_sofia re-reads
  # the cert. (A surgical `sofia profile internal restart` is possible but drops
  # the profile's active calls anyway; renewal is ~60d so a full restart is fine.)
  docker restart communication-freeswitch-1 >/dev/null 2>&1 || true
else
  echo "no cert changed — no edge restart needed"
fi

echo "renewal pass complete"
