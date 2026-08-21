#!/bin/sh
set -e
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
