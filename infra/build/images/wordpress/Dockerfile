# irlcoop/wordpress — the upstream WordPress Apache image plus WP-CLI.
#
# Why: the Joni Schwartz-Chaney author site (jonischwartz.irl.coop) is a
# WordPress 7.1 install that has to be edited regularly. WP-CLI is the only
# sane way to drive it from the shell (content, options, plugins, users, DB
# search-replace) without clicking through wp-admin, and the upstream image
# ships no `wp`. Layering it here keeps the install in the declarative tree —
# a container recreate brings it back, unlike installing it by hand into a
# running container.
#
# The phar is a self-contained PHP archive (shebang `#!/usr/bin/env php`), so
# `docker exec -u www-data <container> wp …` is all that is needed. Run it as
# www-data, NOT root: WP-CLI writes files into /var/www/html, and root-owned
# files break the Apache worker's ability to update plugins/themes/uploads.

FROM wordpress:7.1-php8.2-apache

# The MySQL client (mysql + mysqldump). WP-CLI shells out to these for
# `wp db query` / `wp db export` / `wp db import` and fails with
# "env: 'mysql': No such file or directory" without them. `wp db export` is the
# migration path off this install, so the client is not optional here.
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-mysql-client \
 && rm -rf /var/lib/apt/lists/*

# ADD from a URL lands the file with mode 0600 — the chmod is what makes it
# executable. Pinned to a RELEASE ASSET, not the `gh-pages` phar: the builds
# repo's gh-pages branch is a moving target with no versioned ref to pin, so a
# rebuild off it would silently drift.
ADD https://github.com/wp-cli/wp-cli/releases/download/v2.12.0/wp-cli-2.12.0.phar /usr/local/bin/wp
RUN chmod 0755 /usr/local/bin/wp \
 && su -s /bin/sh www-data -c 'HOME=/tmp /usr/local/bin/wp --version' \
 && mysqldump --version