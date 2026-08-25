#!/bin/sh
# Combine the mounted *.irl.coop wildcard cert into FreeSWITCH's wss.pem
# (cert chain + private key in one PEM — mod_sofia's WSS convention) so the
# browser SIP.js client trusts the WSS endpoint. Falls back to FreeSWITCH's
# self-generated cert when no wildcard is mounted (standalone spike).
#
# Also renders the secret-bearing configs from derived-secret env vars: the
# declarative tree holds __PLACEHOLDER__ templates only (no secrets in git);
# the generator resolves ${SECRET:...} into the container env, and here we
# materialize the real files. config.lua checks /usr/local/etc/fusionpbx/
# BEFORE /etc/fusionpbx/, so render the rendered config.conf there.
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

# Render FusionPBX config.conf + event_socket.conf.xml from derived secrets.
TMPL="/etc/freeswitch/templates"
if [ -n "$FUSIONPBX_DB_PASSWORD" ] && [ -n "$ESL_PASSWORD" ]; then
  if [ -f "$TMPL/config.conf" ]; then
    mkdir -p /usr/local/etc/fusionpbx
    sed -e "s|__FUSIONPBX_DB_PASSWORD__|$FUSIONPBX_DB_PASSWORD|g" \
        -e "s|__ESL_PASSWORD__|$ESL_PASSWORD|g" \
        "$TMPL/config.conf" > /usr/local/etc/fusionpbx/config.conf
    chmod 600 /usr/local/etc/fusionpbx/config.conf
    echo "[entrypoint] rendered /usr/local/etc/fusionpbx/config.conf from env"
  fi
  if [ -f "$TMPL/event_socket.conf.xml" ]; then
    mkdir -p /usr/local/freeswitch/conf/autoload_configs
    sed "s|__ESL_PASSWORD__|$ESL_PASSWORD|g" \
        "$TMPL/event_socket.conf.xml" > /usr/local/freeswitch/conf/autoload_configs/event_socket.conf.xml
    chmod 600 /usr/local/freeswitch/conf/autoload_configs/event_socket.conf.xml
    echo "[entrypoint] rendered event_socket.conf.xml (ESL password from env)"
  fi
else
  echo "[entrypoint] FUSIONPBX_DB_PASSWORD/ESL_PASSWORD not set — skipping config render"
fi

exec /usr/local/freeswitch/bin/freeswitch "$@"
