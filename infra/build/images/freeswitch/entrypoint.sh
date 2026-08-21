#!/bin/sh
# Combine the mounted *.irl.coop wildcard cert into FreeSWITCH's wss.pem
# (cert chain + private key in one PEM — mod_sofia's WSS convention) so the
# browser SIP.js client trusts the WSS endpoint. Falls back to FreeSWITCH's
# self-generated cert when no wildcard is mounted (standalone spike).
set -e

WSS_PEM="/usr/local/freeswitch/certs/wss.pem"
SRC_DIR="/etc/freeswitch/tls"

if [ -f "$SRC_DIR/fullchain.pem" ] && [ -f "$SRC_DIR/privkey.pem" ]; then
  mkdir -p "$(dirname "$WSS_PEM")"
  cat "$SRC_DIR/fullchain.pem" "$SRC_DIR/privkey.pem" > "$WSS_PEM"
  chmod 600 "$WSS_PEM"
  echo "[entrypoint] wrote $WSS_PEM from mounted wildcard cert ($SRC_DIR)"
else
  echo "[entrypoint] no wildcard cert at $SRC_DIR — FreeSWITCH will self-generate wss.pem"
fi

exec /usr/local/freeswitch/bin/freeswitch "$@"
