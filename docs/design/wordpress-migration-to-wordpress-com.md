# Migrating jonischwartz.irl.coop → jonischwartzchaney.com

Status: **staging verified and migration-ready; cutover not started.** The
"Verified state" section is fact, checked against both sites. Nothing has touched
the live site.

## The two sites

| | staging | live |
|---|---|---|
| URL | jonischwartz.irl.coop | jonischwartzchaney.com |
| where | our Docker stack (`workflow-wordpress-1`) | **WordPress.com Atomic** |
| theme | Blocksy 2.1.50 + Companion | `canard` (old WP.com theme) |
| front page | static page `home` (680) | reverse-chronological blog list |
| pages / posts / media | 8 / 44 / 125 | 8 / 42 / 80 |
| custom code | `joni-books` plugin — `book` CPT, `book_category` taxonomy, book + event templates, homepage carousel | none |

Live is the **old** site; staging is the redesign. Staging's database is a direct
descendant of live's — most page IDs are identical (411, 399, 345, 16, 15, 13,
11) and it began life as a WP Engine / LocalWP copy (`admin`'s email is
`dev-email@wpengine.local`).

### The plan tier decides everything — and it is **Personal**

The live site returns `x-ac: … _atomic_dca`, so it runs on WordPress.com's modern
platform — but it is on the **Personal** plan, and backups being upgrade-gated is
what surfaced it. The tier is decisive, so here it is exactly:

| | Personal (current) | Business |
|---|---|---|
| install plugins from the directory | ✅ | ✅ |
| **upload a plugin you built yourself** | ✅ | ✅ |
| upload any theme | ✅ | ✅ |
| custom CSS / custom code | ✅ | ✅ |
| SFTP / SSH / WP-CLI | ❌ | ✅ |
| staging site + push to production | ❌ | ✅ |
| backups + one-click restore | ❌ | ✅ |
| database access | ❌ | ✅ |

The plugin and theme lines are the ones that matter, and they are the reason no
upgrade is required. Straight from the Personal plan feature page:

> **Install plugins** — "You can install from over 50,000 available plugins,
> upload plugins you've found elsewhere, or build a plugin yourself."
>
> **Theme uploads** — "Upload any WordPress theme from the many thousands of
> designs by any theme creator, or upload a theme you designed yourself."

So `joni-books.zip` and the Blocksy theme both install through wp-admin on the
plan the site is already on.

What Personal costs us is the **safety net**: no self-service backup, no staging,
no rollback. Recovery on Personal is "our systems behind the scenes ensure your
content is kept safe" — i.e. not something we can trigger. The migration is
therefore designed to be additive and reversible instead (see below).

**Every dependency is free and on wordpress.org** — Blocksy, Blocksy Companion,
Stackable, WPForms Lite, mb-custom-post-type. Nothing is premium, so nothing needs
relicensing to move.

## The design travels in the database, not in an export

The entire look is a 34 KB `theme_mods_blocksy` row in `wp_options` (plus a
regenerable `_transient_blocksy_dynamic_styles_descriptor`, a `custom_css` post
and a `wp_global_styles` post). A WXR content export does **not** carry any of it
— and on Personal there is no database access to import it with either. Carrying
the design across therefore needs the seeder approach in the migration path.

## Verified state (staging)

These were checked and fixed, in this order:

1. **WP-CLI installed the declarative way.** `infra/build/images/wordpress/Dockerfile`
   derives from `wordpress:7.1-php8.2-apache`, adds the MySQL client (WP-CLI
   shells out to `mysql`/`mysqldump` for `wp db query`/`export`/`import` and
   dies with `env: 'mysql': No such file or directory` without it) and pins
   WP-CLI to the **v2.12.0 release asset** — not the `gh-pages` phar, which is a
   moving target with no versioned ref to pin. Wired into
   `infra/scripts/build-images.sh`; the app spec points at
   `irlcoop/wordpress:7.1-php8.2-wpcli`.

2. **The custom code is now a real plugin, and it is in git.** It was an
   mu-plugin (`wp-content/mu-plugins/joni-books.php`, 53 KB, plus four templates)
   living *only inside the `wordpress-html` Docker volume* — untracked, unbacked,
   one `docker volume rm` from gone. It now lives at
   `infra/instances/dev/assets/wordpress/joni-books/` and is mounted read-only by
   `apps/wordpress.yaml` under `dev.volumes`.

   It needed no code changes: it already had a `Plugin Name` header and loads its
   templates via `plugin_dir_path( __FILE__ )`, which resolves correctly from
   either location. The only edit was adding an `ABSPATH` guard to the four
   templates — as a plugin they sit under web-served `wp-content/plugins/`,
   where a direct request would otherwise execute them with WordPress unloaded.

   **This is what unblocks the migration.** mu-plugins cannot be installed
   through wp-admin at all — there is no upload UI, only SFTP/SSH. As an ordinary
   plugin it installs with a .zip upload.

3. **URL parity is complete.** Live's sitemap carries 61 URLs; all 61 now resolve
   on staging. Three separate problems had to be fixed:

   - **Permalink structure.** Staging used `/%postname%/`; live uses
     `/%year%/%monthnum%/%day%/%postname%/`. That alone 404'd all 42 post URLs.
     Staging now matches live.
   - **Five drifted slugs.** Staging had `186-2`, `228-2`, `283-2`, `327-2` and
     `hello-world-2` where live has `186`, `228`, `283`, `327`, `hello-world`.
     Nothing held the clean slugs, so this was a pure rename with no collision.
   - **`sample-page`.** Live has it; staging had it trashed (as
     `sample-page-2__trashed`, ID 494). Untrashed and the slug reset.

   Regression check: `python3 infra/scripts/verify-joni-url-parity.py` — exit 0
   when every live URL resolves on staging. Re-run it after ANY change to the
   permalink structure, post slugs, or front-page setting.

## Content: staging is a superset — the apparent divergence was a false alarm

Comparing every post and page by slug and modification time first suggested **both
sites had been edited, in different directions**: `news`, `other-writing` and
`prison-project` were newer on live, `about-joni` and `books` newer on staging,
and 7 of the 42 posts had differing timestamps.

**Re-checking against the rendered text rather than the timestamps disproved it.**
WordPress.com rewrites post content on the way out — CDN-rewriting every image to
`i0.wp.com`, injecting `data-attachment-id` / `data-permalink` / `data-recalc-dims`,
capping widths at 720, expanding bare URLs through oEmbed, running `wp-block-code`
through CodeMirror — and those passes bump `post_modified`. Strip that noise and
compare authored text only:

| | result |
|---|---|
| `news` | **text identical** — no merge needed |
| `other-writing` | **text identical** — no merge needed |
| `prison-project` | identical apart from an oEmbed-expanded URL carrying a `?fbclid=` param on live |
| `about-joni` | identical apart from an en-dash and one oEmbed-expanded link |
| all 4 divergent posts | **text identical** — no merge needed |

So **nothing has to be merged, and nothing has to be rescued from staging.** Every
live post and page exists on staging under the same slug, and the only real
content difference is `/books/`:

- **staging** — the new design: a book grid/carousel driven by the `book` CPT
  (804 characters of page copy).
- **live** — the old Canard-era page: 4,918 characters of long-form description,
  one book after another.

The book entries in staging do carry real descriptions of their own, and that was
verified against the old page rather than assumed. Normalising punctuation (the
old page uses curly quotes, staging straight ones) and comparing sentence by
sentence:

| book | sentences carried over from the old page |
|---|---|
| `critical-faith` | 6/6 |
| `learning-to-disclose` | 7/8 — one new opener |
| `race-education-and-reintegrating-formerly-incarcerated-citizens` | 4/4 |
| `gifts-from-the-dark` | 5/5 |
| `healing-our-collective-wound` | 0/4 — all new; it is the forthcoming 2026 book, which the old page never described |

So the copy was **redistributed onto the CPT, not dropped**, and `books` is
confirmed a straight replacement — the new grid supersedes the old long-form page.
The only old-page lines with no counterpart are `PUBLISHER`/title-publisher
citations that now live in structured meta (`_book_publisher`, `_book_isbn`).

## Automation — one upload, one click (current approach)

The migration is **a single plugin that installs everything else itself**.
Built by `infra/scripts/build-joni-installer.py` into `~/joni-installer-package/`
as `joni-installer.zip`; source at
`infra/instances/dev/assets/wordpress/joni-installer/joni-installer.php`.

The plan tier is what forces this shape. Personal gives no SSH, SFTP, WP-CLI or
database access, so the only code that can run on live is code that arrives as a
plugin — therefore the plugin *is* the automation, not a wrapper around one.

It runs as eight steps, one AJAX request each so no step can time out, and every
step is idempotent and re-runnable.

| step | does | mechanism |
|---|---|---|
| `theme` | Blocksy | `themes_api()` + `Theme_Upgrader` |
| `plugins` | Blocksy Companion, Stackable | `plugins_api()` + `Plugin_Upgrader` |
| `joni-books` | the bundled `joni-books.zip` | `Plugin_Upgrader` on the local zip |
| `media` | only the images live lacks | matched to existing attachments by filename; unmatched ones written to their original `uploads/` path |
| `content` | homepage, 2 events, 5 books | `wp_insert_post`/`wp_update_post` by slug, plus meta, terms and thumbnails |
| `menus` | "Main Menu" | `wp_create_nav_menu` + `wp_update_nav_menu_item`, resolving staging's references against live's own page/term IDs |
| `design` | the Blocksy design | `set_theme_mod`, widget rows, `wp_update_custom_css_post()`, global styles, logo remap, `/books/` content |
| `finish` | activation + homepage | `switch_theme`, `page_on_front`, `flush_rewrite_rules` |

**Verified on staging by running the full sequence twice** — both passes produced
byte-identical logs, so re-running cannot duplicate anything. All 8 steps, 7
images resolved, 8 posts upserted with terms, 7 menu items with locations set,
35 theme mods + 20 widget rows applied, and the 61-URL parity check still passes
afterwards.

Four bugs were found only by running it, all worth recording:

- **Stackable's main file is not `<slug>/<slug>.php`** — it is
  `stackable-ultimate-gutenberg-blocks/plugin.php`. Assuming the slug-shaped
  path makes activation fail with *"Plugin file does not exist."* Resolve the
  real file from `get_plugins()` instead.
- **Menu dedupe must key on `$item->object`, not `$item->type`.** Existing items
  report `object` = `page`/`category` and `type` = `post_type`/`taxonomy`;
  comparing type against object made every existing item look new and duplicated
  the entire menu. Caught by running the step on a site that already had one.
- **A post type cannot be checked on the request that activates its plugin.**
  `plugins_loaded` has already fired before an admin-ajax handler runs, so
  `post_type_exists('book')` is false even on a perfectly good install. The step
  treated that as a hard failure and reported an error after installing
  successfully. Report it as "registers on the next request" instead.
- **A PHP fatal in a step returns WordPress's HTML error page**, and the browser
  could only report `SyntaxError: Unexpected token '<'` — which names the symptom
  and hides the cause. Two fixes: a shutdown handler plus `try/catch (Throwable)`
  in the AJAX wrapper so fatals, exceptions and stray output all come back as
  JSON; and the JS parses the body as text first, so a non-JSON response is
  shown rather than swallowed.

### Placing a plugin on a host you cannot inspect

The `joni-books` step tries three ways, **cheapest machinery first**:

1. **direct file copy** — plain PHP `copy()`, no `WP_Filesystem`, no temp dir
2. **`unzip_file()`** into `WP_PLUGIN_DIR`
3. **`Plugin_Upgrader`** on the bundled zip

The upgrader is last on purpose: it needs a writable `wp-content/upgrade`, and if
it raises a fatal the request ends before any fallback can run — so the fallbacks
must come first. That is also why the payload ships the plugin **twice**: as
`payload/joni-books/` (plain files, for step 1) and `payload/joni-books.zip`.
When all three fail the error names each attempt and reports whether
`wp-content/plugins` is writable, so the next run is diagnostic rather than
another guess.

### The builder `rmtree`s its own output

`build-joni-installer.py` deletes `~/joni-installer-package/` before rebuilding,
so a hand-written `README.md` placed there is silently destroyed on the next run.
The README is therefore generated *by* the builder. Same trap as `infra/out/`
under `generator.py dev`.

### Three defects the live run exposed

The migration ran on live and looked mostly right — but the nav showed seven flat
items instead of four plus a "More" dropdown, the header button was Search instead
of "Preorder", the logo fell back to faded text, and both the news page and the
events archive rendered empty while `/books/` worked. Three separate causes:

**1. Theme mods are stored per ACTIVE theme.** The step order applies the design
(step 6) *before* the step that activates the theme (step 8). `set_theme_mod()`
writes `theme_mods_<current stylesheet>`, so on live — still running Canard —
every theme setting was written into `theme_mods_canard` and silently discarded.
That is precisely the header design, the logo and the header button: the
theme_mod-driven parts. Content and `/books/` looked fine because they are not
theme mods. Reproduced by switching a working install to another theme and running
the step: the design (39 keys) landed in `theme_mods_twentytwentyfour`. Fixed with
`joni_ensure_theme()`, called before any `set_theme_mod()` — in both the design
and the menus step, since `nav_menu_locations` is a theme mod too. The snapshot
key is now per-theme (`joni_installer_snapshot_<stylesheet>`) so Revert targets
the right option.

**2. `joni-books` hardcoded staging's term IDs.** `category-events.php` and the
news sidebar queried `'cat' => 21`; `page-news.php` queried
`'category__in' => array( 13, 20 )`; the template loader matched `is_category(21)`
and `is_page(11)`. Those are staging's News/Reviews/Events IDs. On live, `21` was
not the events category, so the loop returned nothing and the page rendered empty
**with no error anywhere** — the failure is silent by construction. Now resolved by
slug via `joni_category_id()` / `joni_category_ids()`, with a `post__in => [0]`
guard so a missing term yields an empty result rather than an unfiltered one.

**3. Categories are not part of a content export.** Live had all 44 posts in
`uncategorized` and no News or Reviews term at all, so even correct queries would
have found nothing. A new `categories` step creates the terms and restores each
post's categories, matched on post slug (all 44 posts match 1:1 between the two
sites). `wp_set_object_terms()` replaces, so `uncategorized` drops away.

Also: **"already present" is not "up to date".** The plugin step skipped whenever
`joni-books.php` existed, so a fixed build could never reach a site that already
had the old one. It now compares the installed file against the bundled copy and
replaces when they differ.

### Diagnosing a site you cannot log into

Every one of these was found without shell access to live, by comparing the two
installs where they can be compared:

- **its public REST API** — `pages?slug=news&_fields=template`, `categories?slug=events`
  and the events' own `categories` fields gave the live facts directly
- **the rendered HTML** — fetching `/news/` and `/category/events/` and counting
  post links per site showed 17/9 on staging against 0/0 on live
- **the browser** — the header difference was invisible in markup (both sites emit
  seven menu items) and only showed up in a screenshot: staging renders four plus
  a Blocksy-generated "More" dropdown, live renders seven flat

One caution from the same pass: a search for `Cafe Lakay` reported "absent" on a
page that does render it — the site uses `Café`. Match on bytes, or the check
lies.

### Two traps when editing design-borne content

- **Widget/block content lives in `innerContent`, not `innerHTML`.** `parse_blocks()`
  populates both, but `serialize_blocks()` rebuilds a block from `innerContent`
  (an array of strings and sub-blocks). Patching only `innerHTML` updates the
  block's attributes while silently leaving the rendered body unchanged — the
  saved content then looks half-updated, which is exactly how it presents.
  Patch `innerContent` and mirror it back into `innerHTML`.
- **Attribute values and rendered HTML escape `&` differently.** Block-comment
  JSON escapes it as `\u0026` (`JSON_HEX_AMP` in `serialize_block_attributes()`);
  the HTML body uses `&amp;`. A plain string replace across the whole block
  corrupts whichever form it did not expect, so go through
  `parse_blocks()`/`serialize_blocks()` rather than editing the raw string.

### Live-only edits get reverted by design

Anything the package carries — widget options, page content, theme mods — is
overwritten on the next run. A pullquote edited directly on live *was* the
placeholder on staging, so a re-run would have restored the placeholder. When
content the package carries is changed, change it on staging (or hand it over to
be synced) rather than on the live site. `wp_delete_attachment()` also cannot
unlink files owned by another uid — the record goes, the files stay, and they
need removing separately.

### Deliberately not installed

Both by checking rather than assuming:

- **WPForms** — an orphan from the WP Engine copy. Its only traces are a
  *trashed* page (`contact__trashed`), a revision, and
  `wpforms_form_locations` = `a:0:{}`; no published content contains the
  shortcode. An earlier count of "2 references" was a false match on non-published
  rows — the same class of error as the earlier `post_modified` false alarm.
- **mb-custom-post-type** — defines nothing: 0 `mb-post-type` and 0
  `mb-taxonomy` rows. The `book` CPT comes from `joni-books`.

That leaves three directory items plus one bundled plugin, which is why the
whole migration fits in one upload.

## The earlier package — superseded

Kept in `~/joni-migration-package/` for reference; the runbook below is replaced
by the one-click installer. Its `README.md` documents the manual route.

Built by `infra/scripts/build-joni-migration-package.py` into
`~/joni-migration-package/`. Nothing here needs shell access on the live site.

| file | what it is |
|---|---|
| `joni-books.zip` | the custom plugin — `book` CPT, `book_category`, book/event templates, homepage carousel |
| `design-seeder.zip` | one-time plugin carrying the design payload: a 22,774-byte `theme_mods_blocksy`, 20 widget option rows, the custom CSS, the global styles, the logo and menu maps, and the `/books/` page content |
| `content/joni-delta.xml` | WXR with **only** what live lacks — the `home` page, the two Café events, the five `book` entries, one attachment — with the host already rewritten (23 staging URLs → live, 0 remaining) |
| `content/media.txt` | the delta's uploads: 5 already in live's library, 1 to carry |
| `README.md`, `manifest.json` | run order and the record of what was and was not included |

### Why a seeder plugin rather than a database import

The look is not content. It is `wp_options` plus two posts, and Personal has no
database access, so it is applied through the WordPress APIs instead:
`set_theme_mod()` per key, the widget option rows, `wp_update_custom_css_post()`,
the global styles row.

Verified on staging by running the real cycle: **plan → apply → revert**.

- Plan lists 61 settings, and correctly *skips* the four keys that must not be
  copied verbatim — `custom_logo`, `custom_css_post_id`, `nav_menu_locations`,
  `sidebars_widgets` — plus the artifact `[0]` key that `json_decode` turns into
  an int.
- Apply made all 61 changes, including remapping the logo to the live attachment
  for the same file, remapping both menu locations by menu *name*, and replacing
  the `/books/` page content in place (importing that page instead would have
  left a stray `/books-2/`).
- It recorded a snapshot of the 40 theme mods, 20 options and 1 page it
  overwrote, and **Revert restored them** — theme mods intact, front page
  unchanged, and the 61-URL parity check still passing afterwards.

### What the delta deliberately excludes

The 42 posts and 6 of the 8 pages already exist on live. WordPress's importer
**creates new posts rather than updating matching ones**, so importing them would
duplicate the whole archive. Only the genuinely new items travel.

### A staging quirk worth knowing

`wp-content/plugins` in this stack is owned by uid `197609` (the LocalWP export)
and is not writable by `www-data`, so `wp plugin install` as `www-data` fails
with a misleading `Error: No plugins installed.` — the extraction silently does
nothing. Installing as root with `--allow-root` and then `chown`-ing the result
works. This is a property of our staging volume, not of the package or of the
live site.

## If the Personal-plan path is judged too risky

The alternative is Business, purely for the migration: real-time backups, a
staging clone, and SFTP/SSH all become available, and the cutover happens on a
clone with one-click rollback to production. Worth pricing, but note WordPress.com
downgrades generally take effect at renewal, so "just for a month" may not be
purchasable as such. A third option is moving the site off WordPress.com to
hosting we control — full control, but it makes Joni's public site an operational
responsibility of this stack, which is a much bigger commitment than a migration.

## Open items

- **The backup is the next action, and the only irreversible-risk step.** Live has
  no self-service restore on Personal, so step 0 of the package README installs
  UpdraftPlus (it is in the WordPress.com directory) for a real files+database
  backup to Robbie's own cloud storage, plus a native Tools → Export for a second
  independent copy. Confirm the archive lands in the destination before touching
  anything else.
- Deliberately **not committed to git** (Robbie's call): this is specific to the
  jonischwartz project and the WordPress instance only happens to run in the coop
  stack. Note the `joni-books` source — rescued from a Docker volume — exists only
  in the working tree and inside `joni-books.zip`; keeping the package is what
  keeps that source recoverable.
- `admin`/`admin` is the staging credential and `/wp-login.php` is on the open
  internet. Not yet changed. Staging is public and ungated by design (it is
  modelled on a public site), but the credential is a default.
- Staging runs WordPress 7.1 / PHP 8.2 from the derived image; WordPress.com pins
  core and Jetpack itself. The two will not stay on identical core versions.