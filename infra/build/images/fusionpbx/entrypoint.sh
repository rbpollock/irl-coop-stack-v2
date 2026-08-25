#!/bin/sh
set -e

# Render /etc/fusionpbx/config.conf from the mounted template + derived-secret
# env vars. The declarative tree holds __PLACEHOLDER__ templates only (no
# secrets in git); the generator resolves ${SECRET:...} into the container env
# and we materialize the real file here.
TMPL="/etc/fusionpbx/templates/config.conf"
if [ -f "$TMPL" ] && [ -n "$FUSIONPBX_DB_PASSWORD" ] && [ -n "$ESL_PASSWORD" ]; then
  mkdir -p /etc/fusionpbx
  sed -e "s|__FUSIONPBX_DB_PASSWORD__|$FUSIONPBX_DB_PASSWORD|g" \
      -e "s|__ESL_PASSWORD__|$ESL_PASSWORD|g" \
      "$TMPL" > /etc/fusionpbx/config.conf
  # PHP (php-fpm) runs as www-data and must read the config (DB + ESL creds);
  # keep it out of other-readable with 640 root:www-data.
  chown root:www-data /etc/fusionpbx/config.conf
  chmod 640 /etc/fusionpbx/config.conf
  echo "[entrypoint] rendered /etc/fusionpbx/config.conf from env"
else
  echo "[entrypoint] FUSIONPBX_DB_PASSWORD/ESL_PASSWORD not set — no config rendered"
fi

mkdir -p /run/php
# php-fpm in the background (default pool listens on /run/php/php8.2-fpm.sock)
/usr/sbin/php-fpm8.2 --nodaemonize --fpm-config /etc/php/8.2/fpm/php-fpm.conf &
# wait for the socket to come up
for _ in $(seq 1 40); do
  [ -S /run/php/php8.2-fpm.sock ] && break
  sleep 0.25
done
# nginx in the foreground
exec nginx -g 'daemon off;'
