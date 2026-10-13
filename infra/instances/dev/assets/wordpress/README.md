# joni-books — the Joni Schwartz-Chaney site plugin

The custom code behind `jonischwartz.irl.coop` / `jonischwartzchaney.com`: the
`book` custom post type, the `book_category` taxonomy, book meta boxes, the
book-detail and event templates, the homepage book carousel, and the purple
header / 3D book-cover CSS.

## Why it lives here

It was previously an **mu-plugin** (`wp-content/mu-plugins/joni-books.php`)
that existed *only inside the `wordpress-html` Docker volume* — not in git, not
in any backup, one `docker volume rm` from gone. It was also the single biggest
obstacle to migrating the site, because mu-plugins cannot be installed through
wp-admin: there is no upload UI for them, only SFTP/SSH. The live site is a
WordPress.com **Atomic** install whose SFTP/SSH access we may not have, so
"install this custom code" had to become an ordinary plugin upload.

The plugin needed **no code changes** to move: it already carried a proper
`Plugin Name` header, and its template loader resolves paths with
`plugin_dir_path( __FILE__ )`, which is correct from either location.

The only edit on import was adding an `ABSPATH` guard to the four templates in
`templates/`. As an mu-plugin they were not directly web-reachable in a way that
mattered; as a plugin they sit under `wp-content/plugins/`, which is served
over HTTP, so a direct request to `templates/single-book.php` would execute the
file with WordPress unloaded. The guard exits cleanly instead.

## Mount

`infra/instances/dev/apps/wordpress.yaml` mounts this directory read-only:

    ./assets/wordpress/joni-books:/var/www/html/wp-content/plugins/joni-books:ro

Read-only is deliberate — the deployed plugin must not be edited through
wp-admin, because the next container recreate would silently discard that edit
and the repo copy is the source of truth. Activate it once with

    wp plugin activate joni-books

## Shipping it to the live site

Build a wp-admin-installable zip from this directory:

    cd infra/instances/dev/assets/wordpress
    zip -r joni-books.zip joni-books -x '*/.DS_Store'

Then upload it on the live site via Plugins → Add New → Upload Plugin.