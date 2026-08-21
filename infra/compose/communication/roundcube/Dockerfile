# irl.coop webmail — Roundcube with OAuth2 (core, since 1.5) wired to Keycloak
# (realm irl-coop, client `roundcube`) and XOAUTH2 to Stalwart.
# NOTE: the entrypoint copies /usr/src/roundcubemail -> /var/www/html on an
# empty volume — config must live in the dist source, not /var/www/html, or it
# is clobbered on first boot.
# Build: docker build -t irlcoop/roundcube-oidc:1.6 infra/compose/communication/roundcube
FROM roundcube/roundcubemail:latest
COPY config.inc.php /usr/src/roundcubemail/config/config.inc.php
# The shadcn-mail skin (extends elastic via meta.json) — shipped in-image so the
# ROUNDCUBEMAIL_SKIN env can select it without a volume mount.
COPY skins/shadcn-mail /usr/src/roundcubemail/skins/shadcn-mail
# the dist copy preserves source perms — the host file can be 0600, and
# www-data must be able to read the config (else Roundcube falls back to a
# mysql DSN and the sqlite init fails with SQLSTATE[HY000] [2002])
RUN chmod 0644 /usr/src/roundcubemail/config/config.inc.php
