# FusionPBX — the ops/admin web UI over the source-compiled FreeSWITCH.
# php-fpm 8.2 + nginx serving the FusionPBX PHP app. TLS is terminated by the
# edge (Traefik wildcard), so this image only listens on :80. It reaches
# FreeSWITCH over mod_event_socket (172.17.0.1:8021) and stores its config in a
# `fusionpbx` DB on the shared Citus — both wired at deploy time, not baked here.
FROM debian:12
ENV DEBIAN_FRONTEND=noninteractive

# PHP 8.2 (FusionPBX 5.5) + extensions + nginx + postgres client.
# (inotify is PECL/SURY-only and omitted — FusionPBX runs without live-reload.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    php8.2 php8.2-common php8.2-cli php8.2-dev php8.2-fpm \
    php8.2-pgsql php8.2-sqlite3 php8.2-odbc php8.2-curl php8.2-imap \
    php8.2-xml php8.2-gd php8.2-mbstring php8.2-ldap php8.2-snmp \
    postgresql-client git curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# FusionPBX app (pinned release tag).
RUN git clone --depth 1 -b 5.5.7 https://github.com/fusionpbx/fusionpbx.git /var/www/fusionpbx \
  && mkdir -p /var/cache/fusionpbx \
  && chown -R www-data:www-data /var/www/fusionpbx /var/cache/fusionpbx

# nginx site (minimal port-80; Traefik terminates TLS upstream).
COPY nginx-fusionpbx.conf /etc/nginx/sites-available/fusionpbx
RUN ln -sf /etc/nginx/sites-available/fusionpbx /etc/nginx/sites-enabled/fusionpbx \
  && rm -f /etc/nginx/sites-enabled/default

# entrypoint: php-fpm (bg) + nginx (fg).
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
