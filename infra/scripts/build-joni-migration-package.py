#!/usr/bin/env python3
"""Build the migration package for jonischwartzchaney.com.

The live site runs WordPress.com **Personal**: no SFTP/SSH, no staging, no
backups, no database access — but plugin install, plugin upload and theme upload
ARE included. So the package is built for wp-admin:

  joni-books.zip        the site's custom plugin (book CPT, templates, carousel)
  design-seeder.zip     one-time plugin that applies the Blocksy design, widget
                        areas, custom CSS and global styles, since a DB dump
                        cannot be imported
  content/delta.xml     WXR carrying ONLY what live lacks — the home page, the
                        redesigned books page's source, the two Cafe events and
                        the five book CPT entries — with the host already
                        rewritten to jonischwartzchaney.com
  content/media.txt     uploads those items reference, flagged with whether live
                        already has them
  README.md             the run order, and what to check afterwards

Deliberately NOT included: the 42 posts and 6 of the 8 pages that already exist
on live. WordPress's importer creates new posts rather than updating matching
ones, so importing them would duplicate the archive.

Usage:
    python3 infra/scripts/build-joni-migration-package.py [outdir]

outdir defaults to ~/joni-migration-package. Never write the package under
infra/out/ — the generator rmtrees that directory on every run.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(REPO, "infra/instances/dev/assets/wordpress")
CONTAINER = "workflow-wordpress-1"
STAGING_HOST = "https://jonischwartz.irl.coop"
LIVE_HOST = "https://jonischwartzchaney.com"

# What live is missing. Everything else already exists there and must not be
# re-imported, or the importer duplicates it.
#
# Note page 13 (books) is deliberately ABSENT: it already exists on live, and
# the seeder replaces its content in place (see PAGES_TO_REPLACE). Importing it
# here as well would leave a duplicate at /books-2/.
CONTENT_IDS = {
    680: "page home (the redesign's front page)",
    704: "post cafe-lakay-september-10-630-pm",
    705: "post cafe-con-libros-october-7-700-pm",
    709: "book critical-faith",
    710: "book learning-to-disclose",
    711: "book race-education-and-reintegrating-formerly-incarcerated-citizens",
    712: "book healing-our-collective-wound",
    713: "book gifts-from-the-dark",
}

# Pages whose content the seeder replaces in place, by slug — because the page
# already exists on live and importing it would create a duplicate.
PAGES_TO_REPLACE = ["books"]


def wp(*args, check=True):
    p = subprocess.run(
        ["docker", "exec", "-u", "www-data", CONTAINER, "wp", "--path=/var/www/html", *args],
        capture_output=True, text=True, timeout=300)
    out = "\n".join(l for l in p.stdout.splitlines()
                    if "PHP Warning" not in l and "Undefined array key" not in l)
    if check and p.returncode != 0:
        sys.exit(f"wp {' '.join(args)} failed:\n{p.stderr[:800]}")
    return out


def q(sql):
    return wp("db", "query", sql, "--skip-column-names")


def out(*args):
    return wp("option", "get", *args)


def log(msg):
    print(f"  {msg}")


# ---------------------------------------------------------------- package root
outdir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                         else os.path.expanduser("~/joni-migration-package"))
if os.path.isdir(outdir):
    shutil.rmtree(outdir)
os.makedirs(outdir)
os.makedirs(os.path.join(outdir, "content"))
xml_dir = os.path.join(outdir, "content")

print(f"Building into {outdir}\n")

# ------------------------------------------------------------- 1. design payload
print("1. design payload (the part a WXR cannot carry)")
seeder_src = os.path.join(ASSETS, "design-seeder")
seeder_dst = os.path.join(outdir, "build/design-seeder")
shutil.copytree(seeder_src, seeder_dst)
design = os.path.join(seeder_dst, "design")
os.makedirs(design, exist_ok=True)

def write(name, content):
    with open(os.path.join(design, name), "w") as f:
        f.write(content)

write("theme_mods_blocksy.json", wp("option", "get", "theme_mods_blocksy", "--format=json"))
log(f"theme_mods_blocksy.json  {os.path.getsize(os.path.join(design, 'theme_mods_blocksy.json'))} bytes")

mods = json.loads(open(os.path.join(design, "theme_mods_blocksy.json")).read())

# Widget option rows — these are what actually render the Blocksy footer.
widget_opts = {}
for opt in q("SELECT option_name FROM wp_options WHERE option_name LIKE 'widget_%' "
             "OR option_name='sidebars_widgets' ORDER BY option_name").splitlines():
    opt = opt.strip()
    if not opt:
        continue
    raw = wp("option", "get", opt, "--format=json")
    widget_opts[opt] = json.loads(raw) if raw else None
write("widget-options.json", json.dumps(widget_opts, indent=1))
log(f"widget-options.json       {len(widget_opts)} option rows")

# custom_css_post_id is a THEME MOD, not a standalone option.
css_post_id = mods.get("custom_css_post_id")
css = wp("post", "get", str(int(css_post_id)), "--field=post_content") if css_post_id else ""
write("custom-css.css", css)
log(f"custom-css.css            {len(css)} bytes (post {css_post_id})")

gs = q("SELECT ID FROM wp_posts WHERE post_type='wp_global_styles' AND post_status='publish' "
       "AND post_name LIKE '%blocksy%' ORDER BY ID DESC LIMIT 1").strip()
if gs:
    write("global-styles.json", json.dumps({
        "post_name": "wp-global-styles-blocksy",
        "content": wp("post", "get", gs, "--field=post_content").strip(),
    }, indent=1))
    log(f"global-styles.json        from post {gs}")

# IDs in theme_mods that must be remapped rather than copied verbatim.
logo_id = mods.get("custom_logo")
logo_file = None
if logo_id:
    logo_file = q(f"SELECT meta_value FROM wp_postmeta WHERE post_id={int(logo_id)} "
                  f"AND meta_key='_wp_attached_file'").strip()
if logo_file:
    write("logo.json", json.dumps({"file": logo_file}, indent=1))
    log(f"logo.json                 custom_logo {logo_id} -> {logo_file}")

names = {}
for loc, tid in (mods.get("nav_menu_locations") or {}).items():
    if not tid:
        continue
    row = q(f"SELECT name FROM wp_terms WHERE term_id={int(tid)}").strip()
    if row:
        names[loc] = row
if names:
    write("menus.json", json.dumps(names, indent=1))
    log(f"menus.json                {names}")

# Pages to replace in place, by slug.
page_payload = {}
for slug in PAGES_TO_REPLACE:
    pid = q(f"SELECT ID FROM wp_posts WHERE post_name='{slug}' AND post_type='page' "
            f"AND post_status='publish' LIMIT 1").strip()
    if pid:
        page_payload[slug] = wp("post", "get", pid, "--field=post_content")
if page_payload:
    write("page-content.json", json.dumps(page_payload, indent=1))
    log(f"page-content.json         {list(page_payload)}")

# ------------------------------------------------------------------- 2. content
print("\n2. content delta (only what live lacks)")

# What the delta references. Two sources: URLs inside post_content, and the
# featured image on each book entry (_thumbnail_id) — the book grid renders
# covers from thumbnails, not from content, so content alone would miss them.
refs = set()
for pid in CONTENT_IDS:
    body = wp("post", "get", str(pid), "--field=post_content", check=False)
    refs.update(re.findall(r"/wp-content/uploads/([^\"'\s?&)]+)", body))
    thumb = q(f"SELECT meta_value FROM wp_postmeta WHERE post_id={pid} "
              f"AND meta_key='_thumbnail_id'").strip()
    if thumb:
        rel = q(f"SELECT meta_value FROM wp_postmeta WHERE post_id={int(thumb)} "
                f"AND meta_key='_wp_attached_file'").strip()
        if rel:
            refs.add(rel)
refs = {r for r in refs if not re.search(r"-\d+x\d+(\.\w+)$", r)}  # drop size variants

# Which of those does live already have? Only the absent ones go in the WXR —
# importing an attachment live already holds just makes a duplicate with a -1
# suffix and leaves the original untouched.
live_files = set()
page = 1
while True:
    import urllib.request
    req = urllib.request.Request(f"{LIVE_HOST}/wp-json/wp/v2/media?per_page=100&page={page}"
                                 "&_fields=source_url", headers={"User-Agent": "irl-verify/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read())
    except Exception:
        break
    if not batch:
        break
    for item in batch:
        live_files.add(item["source_url"].rsplit("/", 1)[-1])
    page += 1

att_ids, already, missing = {}, [], []
for rel in sorted(refs):
    rid = q("SELECT post_id FROM wp_postmeta WHERE meta_key='_wp_attached_file' "
            f"AND meta_value='{rel}' LIMIT 1").strip()
    if rel.rsplit("/", 1)[-1] in live_files:
        already.append(rel)
        continue
    if rid:
        att_ids[rel] = int(rid)
        missing.append(rel)

log(f"{len(refs)} uploads referenced; {len(already)} already on live, "
    f"{len(missing)} to carry")
for rel in already:
    log(f"    on live already: {rel}")
for rel in missing:
    log(f"    MISSING on live: {rel}")

ids = sorted(CONTENT_IDS) + sorted(att_ids.values())
# The export writes inside the container (the host path does not exist there),
# then we copy it out. Created as www-data so it is writable by the CLI process.
subprocess.run(["docker", "exec", "-u", "www-data", CONTAINER, "mkdir", "-p", "/tmp/joni-export"],
               check=True)
wp("export", "--dir=/tmp/joni-export", f"--post__in={','.join(str(i) for i in ids)}",
   "--post_type=any", "--filename_format=joni-delta.xml",
   "--max_file_size=-1", "--skip_comments")

xml = os.path.join(xml_dir, "joni-delta.xml")
cp = subprocess.run(["docker", "cp", f"{CONTAINER}:/tmp/joni-export/joni-delta.xml", xml],
                    capture_output=True, text=True)
if cp.returncode != 0:
    listing = wp("eval", 'foreach (glob("/tmp/joni-export/*.xml") as $f) echo basename($f), "\\n";')
    cand = [c for c in listing.splitlines() if c.strip()]
    if not cand:
        sys.exit(f"  export produced no XML (docker cp said: {cp.stderr[:300]})")
    subprocess.run(["docker", "cp", f"{CONTAINER}:/tmp/joni-export/{cand[0]}", xml], check=True)

# Rewrite the host BEFORE upload. The WP importer rewrites URLs it recognises
# while fetching attachments, but Stackable stores absolute URLs inside block
# attribute JSON, which it does not touch — so the swap has to be baked in.
raw = open(xml).read()
before = raw.count(STAGING_HOST)
raw = raw.replace(STAGING_HOST, LIVE_HOST)
open(xml, "w").write(raw)
log(f"joni-delta.xml            {len(raw)} bytes, {before} staging URLs rewritten to live")

# ------------------------------------------------------------- 3. media report
print("\n3. media report")
with open(os.path.join(outdir, "content/media.txt"), "w") as f:
    f.write("# uploads the content delta references.\n"
            "# The importer only fetches attachments that are IN the WXR, and\n"
            "# 'already on live' ones are deliberately left out so they are not\n"
            "# duplicated with a -1 suffix.\n\n")
    f.write("== already in the live media library (no action) ==\n")
    for rel in already:
        f.write(f"  {rel}\n")
    f.write("\n== carried in the WXR (missing on live) ==\n")
    for rel in missing:
        f.write(f"  {rel}\tattachment {att_ids[rel]}\t{LIVE_HOST}/wp-content/uploads/{rel}\n")
    if not missing:
        f.write("  (none)\n")
log(f"content/media.txt         {len(already)} on live, {len(missing)} carried")

# ---------------------------------------------------------------- 4. the zips
print("\n4. the two plugin zips")
books_dst = os.path.join(outdir, "build/joni-books")
shutil.copytree(os.path.join(ASSETS, "joni-books"), books_dst)

for name, folder in (("joni-books.zip", books_dst), ("design-seeder.zip", seeder_dst)):
    path = os.path.join(outdir, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        base = os.path.basename(folder)
        # Explicit directory entries, INCLUDING the plugin's own folder. Python's
        # zipfile omits them, and `wp plugin install <zip>` then unpacks fine but
        # finds no plugin ("Error: No plugins installed.") — the entry for the
        # plugin folder itself is what makes the package discoverable.
        z.writestr(zipfile.ZipInfo(base + "/"), "")
        for root, dirs, files in os.walk(folder):
            rel = os.path.relpath(root, folder)
            if rel != ".":
                z.writestr(zipfile.ZipInfo(os.path.join(base, rel) + "/"), "")
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.join(base, os.path.relpath(full, folder)))
    log(f"{name:24} {os.path.getsize(path)} bytes")

# ------------------------------------------------------- 5. manifest + readme
manifest = {
    "built_for": LIVE_HOST,
    "from": STAGING_HOST,
    "staging_plan": "WordPress.com Personal — no SSH/SFTP, no staging, no DB access",
    "content_ids": {str(k): v for k, v in CONTENT_IDS.items()},
    "attachment_ids": {k: v for k, v in att_ids.items()},
    "pages_replaced_in_place": PAGES_TO_REPLACE,
    "not_included": ("the 42 posts and 6 of 8 pages already on live — the importer "
                     "creates new posts, so importing them would duplicate the archive"),
}
with open(os.path.join(outdir, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1)

readme = f"""# Migration package — {STAGING_HOST} -> {LIVE_HOST}

Built from the staging site for a **WordPress.com Personal** plan: there is no
SFTP/SSH, no staging site, no database access and no self-service backup. Plugin
install, plugin *upload* and theme upload are all included on Personal, so the
whole migration goes through wp-admin. Nothing here needs shell access.

## What is in here

| file | what it is |
|---|---|
| `joni-books.zip` | the site's custom plugin — `book` CPT, `book_category` taxonomy, book/event templates, homepage carousel |
| `design-seeder.zip` | one-time plugin that applies the Blocksy design, widget areas, custom CSS and global styles, and swaps the `/books/` page content in place |
| `content/joni-delta.xml` | WXR with ONLY what live lacks: the `home` page, the two Cafe events, the five book entries, and one attachment |
| `content/media.txt` | which uploads the delta references, and which live already has |
| `manifest.json` | what was included and what was deliberately not |

The design does **not** travel in the WXR. It lives in `wp_options` (a {len(mods)}-key
`theme_mods_blocksy` row plus the widget option rows), a `custom_css` post and a
`wp_global_styles` post — which is why `design-seeder.zip` exists.

## Run order

Do these in order. Steps 0 and 1 change nothing on the live site.

**0. Back up the live site first — two independent layers.** This is the step that
matters most, because Personal has no self-service restore and no one-click
rollback.

*(a) A full backup with UpdraftPlus.* It is in the WordPress.com plugin directory
and plugin install is included on Personal. Install it, then UpdraftPlus ->
Backup/Restore -> **Backup now**, ticking both **database** and **files**, with
Dropbox or Google Drive as the destination.

Then **confirm the archive actually appears in that destination before going any
further** — an unverified backup is not a backup. Once confirmed, a restore is
three clicks from the same screen, and the backup files themselves are ordinary
zip and .sql files that can be restored by hand if the plugin breaks.

Keep UpdraftPlus installed afterwards. On Personal it is the only self-service
backup you will have, and this site has no other one.

*(b) A content export as a second, independent copy.* Tools -> Export -> All
content. Note WordPress.com's own caveat: the export carries posts, pages and
comments but **not** the theme design, customisations or plugins. That gap is
exactly what `design-seeder.zip` carries.

Take both **before** installing Blocksy or any other plugin (UpdraftPlus itself
excepted), so the backup captures the site as it stands now. A third copy exists
outside WordPress.com already: our staging database holds live's content from the
copy date.

**1. Install the theme and plugins, activating nothing yet.**

- Appearance -> Themes -> Add New -> search "Blocksy" -> Install. Do not activate.
- Plugins -> Add New: install **Blocksy Companion**, **Stackable**, **WPForms Lite**,
  **mb-custom-post-type** (all from the directory).
- Plugins -> Add New -> **Upload Plugin** -> `joni-books.zip` -> Activate.
  (`joni-books` must be active *before* the import below, or the importer will not
  recognise the `book` post type and the five book entries will be dropped.)

**2. Import the content delta.** Tools -> Import -> WordPress -> upload
`content/joni-delta.xml`. On the import screen pick an existing author rather than
creating new users, and leave "download and import file attachments" ticked so the
hero image comes across.

**3. Apply the design.** Plugins -> Add New -> Upload Plugin -> `design-seeder.zip`
-> Activate, then Tools -> **Joni Design Seeder**. The page lists exactly what it
will set, what it will skip, and anything needing a manual step. Click
**Apply the design**.

It records a snapshot of every value it overwrites, so **Revert** restores the
pre-seeder state. When the design looks right, deactivate and delete it.

It will skip the logo if `2022/06/logo-dark.svg` is not in the live media library,
and will say so. Upload that file by hand if it reports the skip.

**4. Switch the site over.** Activate Blocksy. Then Settings -> Reading -> set the
homepage to the imported **Home** page (static page, not the blog list), and
Appearance -> Menus -> assign the menu to the primary and mobile locations.

**5. Verify.**

- `/` renders the new homepage, `/books/` the book grid, `/category/events/` the
  events archive, `/news/` the news page, `/book/critical-faith/` a book detail.
- Every one of the 61 URLs on the old site still resolves — the URL surface was
  matched to live before this package was built, including the date-based
  permalink structure (`/%year%/%monthnum%/%day%/%postname%/`).

## Why the archive is not in here

Live already has all 42 posts and 6 of the 8 pages. WordPress's importer creates
*new* posts rather than updating matching ones, so importing them would duplicate
the entire archive. Only the genuinely new items are in `joni-delta.xml`.

The `/books/` page is the one existing page whose content changes: rather than
importing it (which would leave a stray `/books-2/`), the seeder replaces live's
page content in place.

## If something goes wrong

In order of increasing force:

1. **Deactivate the plugins.** Nothing here deletes content.
2. **Switch the theme back to Canard** in Appearance -> Themes. The site returns
   to how it looked before in one click, and the imported content stays.
3. **Revert in the Design Seeder** — undoes the design settings, the widget areas,
   the custom CSS and the `/books/` content, from the snapshot it took.
4. **Restore from UpdraftPlus.** The full rollback. Choose the pre-migration
   backup from step 0 and restore — files and database both go back.
"""
with open(os.path.join(outdir, "README.md"), "w") as f:
    f.write(readme)

shutil.rmtree(os.path.join(outdir, "build"))

print(f"\nDone. Package at {outdir}")
for entry in sorted(os.listdir(outdir)):
    p = os.path.join(outdir, entry)
    size = os.path.getsize(p) if os.path.isfile(p) else "-"
    print(f"  {entry:24} {size}")