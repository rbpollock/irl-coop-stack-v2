#!/usr/bin/env python3
"""Build the ONE-CLICK migration package for jonischwartzchaney.com.

The live site is WordPress.com on the **Personal** plan: no SSH, SFTP, WP-CLI or
database access. The only code that can run on it is code that arrives as a
plugin. So this builds a single plugin — `joni-installer.zip` — which installs
everything else itself using WordPress's own APIs:

  theme      Blocksy, from wordpress.org
  plugins    Blocksy Companion, Stackable (WPForms and mb-custom-post-type are
             deliberately NOT included: WPForms is an orphan from the WP Engine
             copy — trashed page, zero published references, form placed nowhere —
             and mb-custom-post-type defines nothing at all)
  joni-books bundled inside the package, installed by the plugin
  media      the images the redesign needs, placed at their original paths
  content    the home page, the two Cafe events and the five book entries,
             with their meta, thumbnails and taxonomy terms
  menus      the "Main Menu" built against this site's own post/term IDs
  design     the Blocksy design — a 23 KB theme_mods row plus 20 widget option
             rows, custom CSS and global styles — applied through the APIs,
             because it lives in wp_options and a WXR cannot carry it

Everything is idempotent and resumable, step by step, one AJAX request each.

Usage:
    python3 infra/scripts/build-joni-installer.py [outdir]

outdir defaults to ~/joni-installer-package. Never write it under infra/out/ —
the generator rmtrees that directory.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(REPO, "infra/instances/dev/assets/wordpress")
CONTAINER = "workflow-wordpress-1"
STAGING_HOST = "https://jonischwartz.irl.coop"
LIVE_HOST = "https://jonischwartzchaney.com"

# The content that does not exist on live yet. Everything else already does, and
# WordPress's importer/creator would duplicate it rather than update it.
CONTENT = [
    {"id": 680, "type": "page", "keep_page_template": True},
    {"id": 704, "type": "post"},
    {"id": 705, "type": "post"},
    {"id": 709, "type": "book"},
    {"id": 710, "type": "book"},
    {"id": 711, "type": "book"},
    {"id": 712, "type": "book"},
    {"id": 713, "type": "book"},
]

# Meta worth carrying, as prefixes. Deliberately excludes _thumbnail_id (carried
# as thumb_file so it can be remapped), the editor lock/date rows, and the
# Stackable/Blocksy import bookkeeping that is regenerated per site.
META_PREFIXES = ("_book_", "_event_", "_wp_old_slug")
META_EXACT = ("blocksy_post_meta_options",)
META_SKIP = ("_edit_lock", "_edit_last", "_thumbnail_id", "_wp_page_template",
             "stackable_optimized_css", "stackable_optimized_css_raw",
             "blocksy_demos_imported_post", "wpforms_entries_count",
             "wpforms_entries_count_previous_week", "wpforms_form_locations")

# The redesigned /books/ page is a REPLACEMENT of an existing page, not a new
# page — so its content is applied in place rather than created.
PAGES_TO_REPLACE = ["books"]

THEME = "blocksy"
PLUGINS = ["blocksy-companion", "stackable-ultimate-gutenberg-blocks"]
FRONT_PAGE_SLUG = "home"

# Staging menu -> resolved by slug/term on the target. Titles left empty display
# the linked object's own title, which is what the staging menu does.
MENU_CREATE = {
    "Main Menu": [
        {"type": "post_type", "object": "page", "slug": "home", "title": "HOME", "order": 0},
        {"type": "post_type", "object": "page", "slug": "news", "title": "", "order": 2},
        {"type": "taxonomy", "object": "category", "slug": "events", "title": "EVENTS", "order": 3},
        {"type": "post_type", "object": "page", "slug": "books", "title": "", "order": 4},
        {"type": "post_type", "object": "page", "slug": "other-writing", "title": "", "order": 5},
        {"type": "post_type", "object": "page", "slug": "prison-project", "title": "", "order": 6},
        {"type": "post_type", "object": "page", "slug": "about-joni", "title": "", "order": 7},
    ]
}
MENU_LOCATIONS = {"menu_1": "Main Menu", "menu_mobile": "Main Menu"}


def wp(*args, check=True):
    p = subprocess.run(
        ["docker", "exec", "-u", "www-data", CONTAINER, "wp", "--path=/var/www/html", *args],
        capture_output=True, text=True, timeout=300)
    # NB: do NOT soften this on stderr warnings. wp-cli exits 0 for the WPForms
    # warnings this site emits, so a non-zero exit is always a real failure —
    # an earlier version ignored it and silently returned empty results.
    if check and p.returncode != 0:
        sys.exit(f"wp {' '.join(a for a in args[:3])} failed (exit {p.returncode}):\n{p.stderr[:800]}")
    return "\n".join(l for l in p.stdout.splitlines()
                     if "PHP Warning" not in l and "Undefined array key" not in l)


def q(sql):
    return wp("db", "query", sql, "--skip-column-names")


def post_meta(pid):
    """All meta for a post as decoded values.

    Uses PHP's own serializer round-trip rather than pulling raw rows: serialized
    values (Blocksy's per-page options) come back as real structures, and
    update_post_meta re-serializes them on the far side. Base64 through the CLI
    was tried first and is a dead end — MySQL wraps it at 76 chars and wp-cli
    mis-detects the query.
    """
    raw = wp("eval",
             f'$o=[]; foreach(get_post_meta({pid}) as $k=>$v){{ $o[$k]=maybe_unserialize($v[0]); }} '
             f'echo json_encode($o);')
    raw = raw.strip()
    return json.loads(raw) if raw else {}


def log(m):
    print(f"  {m}")


outdir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                         else os.path.expanduser("~/joni-installer-package"))
if os.path.isdir(outdir):
    shutil.rmtree(outdir)
plugin_dir = os.path.join(outdir, "build/joni-installer")
payload_dir = os.path.join(plugin_dir, "payload")
os.makedirs(os.path.join(payload_dir, "media"))
print(f"Building into {outdir}\n")

# ------------------------------------------------------------- 1. content delta
print("1. content (only what live lacks)")
items = []
for spec in CONTENT:
    pid = spec["id"]
    row = q(f"SELECT post_type, post_name, post_title, post_status, post_date, menu_order "
            f"FROM wp_posts WHERE ID={pid}").split("\t")
    ptype, slug, title, status, date, order = (row + [""] * 6)[:6]

    # meta, with serialized values (Blocksy's per-page options) decoded to real
    # structures — update_post_meta re-serializes them on the far side.
    meta = {}
    for k, v in post_meta(pid).items():
        if k in META_SKIP:
            continue
        if k.startswith(META_PREFIXES) or k in META_EXACT:
            meta[k] = v

    # terms, by slug
    terms = {}
    for line in q("SELECT tt.taxonomy, t.slug FROM wp_term_relationships tr "
                  "JOIN wp_term_taxonomy tt ON tt.term_taxonomy_id=tr.term_taxonomy_id "
                  "JOIN wp_terms t ON t.term_id=tt.term_id "
                  f"WHERE tr.object_id={pid}").splitlines():
        if "\t" in line:
            tax, tslug = line.split("\t", 1)
            terms.setdefault(tax, []).append(tslug.strip())

    # featured image, carried as a filename so the id can be remapped
    thumb = q(f"SELECT a.meta_value FROM wp_postmeta t JOIN wp_postmeta a "
              f"ON a.post_id=t.meta_value AND a.meta_key='_wp_attached_file' "
              f"WHERE t.post_id={pid} AND t.meta_key='_thumbnail_id' LIMIT 1").strip()

    items.append({
        "type": ptype, "slug": slug, "title": title, "status": status,
        "date": date, "menu_order": int(order or 0),
        "content": wp("post", "get", str(pid), "--field=post_content"),
        "meta": meta, "terms": terms, "thumb_file": thumb,
    })
    log(f"{ptype:<5} {slug:<60} meta={len(meta)} terms={sum(len(v) for v in terms.values())} "
        f"thumb={'yes' if thumb else 'no'}")

# ------------------------------------------------------------- 2. media to carry
print("\n2. media")
wanted = set()
for it in items:
    if it["thumb_file"]:
        wanted.add(it["thumb_file"])
    wanted.update(re.findall(r"/wp-content/uploads/([^\"'\s?&)]+)", it["content"]))
wanted = {w for w in wanted if not re.search(r"-\d+x\d+(\.\w+)$", w)}
# the home page's Stackable background lives in block attributes, not an <img>
wanted.update(re.findall(r"/wp-content/uploads/([^\"'\s?&)]+)",
                         wp("post", "get", "680", "--field=post_content")))

live_files = set()
page = 1
while True:
    req = urllib.request.Request(
        f"{LIVE_HOST}/wp-json/wp/v2/media?per_page=100&page={page}&_fields=source_url",
        headers={"User-Agent": "irl-verify/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read())
    except Exception:
        break
    if not batch:
        break
    live_files.update(i["source_url"].rsplit("/", 1)[-1] for i in batch)
    page += 1

carried, present = [], []
for rel in sorted(wanted):
    (present if rel.rsplit("/", 1)[-1] in live_files else carried).append(rel)
for rel in carried:
    src = f"/var/www/html/wp-content/uploads/{rel}"
    dest = os.path.join(payload_dir, "media", rel.rsplit("/", 1)[-1])
    cp = subprocess.run(["docker", "cp", f"{CONTAINER}:{src}", dest], capture_output=True, text=True)
    if cp.returncode != 0:
        sys.exit(f"  could not copy {rel}: {cp.stderr[:200]}")
    log(f"carried  {rel}  ({os.path.getsize(dest)} bytes)")
for rel in present:
    log(f"on live  {rel}")
log(f"{len(carried)} carried, {len(present)} already on live")

# --------------------------------------------------------------- 3. the design
print("\n3. design payload")
mods = json.loads(wp("option", "get", "theme_mods_blocksy", "--format=json"))
SPECIAL = ("custom_logo", "custom_css_post_id", "nav_menu_locations", "sidebars_widgets", "0")
design_mods = {k: v for k, v in mods.items() if k not in SPECIAL}
log(f"theme_mods       {len(design_mods)} of {len(mods)} keys "
    f"(dropped: {sorted(set(mods) & set(SPECIAL))})")

widgets = {}
for name in q("SELECT option_name FROM wp_options WHERE option_name LIKE 'widget_%' "
              "OR option_name='sidebars_widgets' ORDER BY option_name").splitlines():
    name = name.strip()
    if not name:
        continue
    raw = wp("option", "get", name, "--format=json")
    widgets[name] = json.loads(raw) if raw else None
log(f"widget options   {len(widgets)} rows")

css_post = mods.get("custom_css_post_id")
custom_css = wp("post", "get", str(int(css_post)), "--field=post_content") if css_post else ""
log(f"custom CSS       {len(custom_css)} bytes")

gs_id = q("SELECT ID FROM wp_posts WHERE post_type='wp_global_styles' AND post_status='publish' "
          "AND post_name LIKE '%blocksy%' ORDER BY ID DESC LIMIT 1").strip()
global_styles = {}
if gs_id:
    global_styles = {"post_name": "wp-global-styles-blocksy",
                     "content": wp("post", "get", gs_id, "--field=post_content").strip()}
    log(f"global styles    from post {gs_id}")

logo_id = mods.get("custom_logo")
logo_file = ""
if logo_id:
    logo_file = q(f"SELECT meta_value FROM wp_postmeta WHERE post_id={int(logo_id)} "
                  f"AND meta_key='_wp_attached_file'").strip()
    log(f"logo             custom_logo {logo_id} -> {logo_file}")
    if logo_file and logo_file.rsplit("/", 1)[-1] not in live_files and logo_file not in carried:
        src = f"/var/www/html/wp-content/uploads/{logo_file}"
        dest = os.path.join(payload_dir, "media", logo_file.rsplit("/", 1)[-1])
        subprocess.run(["docker", "cp", f"{CONTAINER}:{src}", dest], capture_output=True)
        wanted.add(logo_file)
        carried.append(logo_file)
        log(f"                 logo carried too")

page_content = {}
for slug in PAGES_TO_REPLACE:
    pid = q(f"SELECT ID FROM wp_posts WHERE post_name='{slug}' AND post_type='page' "
            f"AND post_status='publish' LIMIT 1").strip()
    if pid:
        page_content[slug] = wp("post", "get", pid, "--field=post_content")
log(f"page_content     replaces in place: {list(page_content)}")

# --------------------------------- 4b. categories, and which post is in which
print("\n3b. categories")
cats = {}
for line in wp("eval",
               'foreach (get_terms(["taxonomy"=>"category","hide_empty"=>false]) as $t) '
               'printf("%s\\t%s\\t%d\\n", $t->slug, $t->name, $t->count);').splitlines():
    parts = line.split("\t")
    if len(parts) >= 2 and parts[0]:
        cats[parts[0]] = parts[1]
log(f"categories       {len(cats)}: " + ", ".join(f"{s}({cats[s]})" for s in sorted(cats)))

# Categories are NOT part of a content export, and the live site had every post in
# "uncategorized" with no News or Reviews term at all — which is why the news page
# and events archive rendered empty. Carried explicitly, matched on post slug.
post_cats = {}
for line in q("SELECT p.post_name, t.slug FROM wp_posts p "
              "JOIN wp_term_relationships tr ON tr.object_id=p.ID "
              "JOIN wp_term_taxonomy tt ON tt.term_taxonomy_id=tr.term_taxonomy_id "
              "  AND tt.taxonomy='category' "
              "JOIN wp_terms t ON t.term_id=tt.term_id "
              "WHERE p.post_type='post' AND p.post_status='publish'").splitlines():
    if "\t" in line:
        pslug, cslug = line.split("\t", 1)
        post_cats.setdefault(pslug.strip(), []).append(cslug.strip())
tally = {}
for v in post_cats.values():
    for c in v:
        tally[c] = tally.get(c, 0) + 1
log(f"post_categories  {len(post_cats)} posts mapped  {tally}")

# ------------------------------------------------------------- 4. site.json
site = {
    "built_from": STAGING_HOST,
    "built_for": LIVE_HOST,
    "settings": {"theme": THEME, "plugins": PLUGINS, "front_page_slug": FRONT_PAGE_SLUG},
    "content": items,
    "categories": cats,
    "post_categories": post_cats,
    "media": sorted(set(carried) | set(present)),
    "menus": {"create": MENU_CREATE, "locations": MENU_LOCATIONS},
    "design": {
        "theme_mods": design_mods,
        "widgets": widgets,
        "custom_css": custom_css,
        "global_styles": global_styles,
        "logo_file": logo_file,
        "page_content": page_content,
    },
}
site_json = json.dumps(site, indent=1)
# The payload must not point at the staging host anywhere in content or design
# values — Stackable stores absolute URLs inside block attributes. applied here
# rather than per-field so nothing is missed.
site = json.loads(site_json.replace(STAGING_HOST, LIVE_HOST))
site["built_from"] = STAGING_HOST          # provenance, not a URL to rewrite
site_json = json.dumps(site, indent=1)
open(os.path.join(payload_dir, "site.json"), "w").write(site_json)
log(f"site.json        {len(site_json)} bytes")

# ------------------------------------------------- 5. plugin copy + workspace
shutil.copy(os.path.join(ASSETS, "joni-installer/joni-installer.php"),
            os.path.join(plugin_dir, "joni-installer.php"))

# joni-books, built fresh from the tracked source
books_src = os.path.join(ASSETS, "joni-books")
books_zip = os.path.join(payload_dir, "joni-books.zip")
with zipfile.ZipFile(books_zip, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(zipfile.ZipInfo("joni-books/"), "")
    for root, _dirs, files in os.walk(books_src):
        rel = os.path.relpath(root, books_src)
        if rel != ".":
            z.writestr(zipfile.ZipInfo(f"joni-books/{rel}/"), "")
        for fn in files:
            full = os.path.join(root, fn)
            z.write(full, f"joni-books/{os.path.relpath(full, books_src)}")
log(f"joni-books.zip   {os.path.getsize(books_zip)} bytes")

# Also ship the plugin as plain files. The installer tries a direct copy first —
# plain PHP filesystem calls, no upgrader, no temp directory — because that is the
# path that survives a host whose own filesystem layer is what's unavailable.
books_plain = os.path.join(payload_dir, "joni-books")
shutil.copytree(books_src, books_plain)
plain_files = sum(len(f) for _r, _d, f in os.walk(books_plain))
log(f"joni-books/      {plain_files} files (direct-copy payload)")

# ---------------------------------------------------------------- 6. the zip
print("\n4. packaging")
installer_zip = os.path.join(outdir, "joni-installer.zip")
with zipfile.ZipFile(installer_zip, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(zipfile.ZipInfo("joni-installer/"), "")
    for root, dirs, files in os.walk(plugin_dir):
        rel = os.path.relpath(root, plugin_dir)
        if rel != ".":
            z.writestr(zipfile.ZipInfo(f"joni-installer/{rel}/"), "")
        for fn in files:
            full = os.path.join(root, fn)
            z.write(full, f"joni-installer/{os.path.relpath(full, plugin_dir)}")
log(f"joni-installer.zip  {os.path.getsize(installer_zip)} bytes")

readme = f"""# Joni site migration — one upload, one click

Built {__import__('datetime').date.today().isoformat()} for {LIVE_HOST} from {STAGING_HOST}.

Live is on the WordPress.com **Personal** plan: no SSH, SFTP, WP-CLI or database
access. The only code that can run there is code that arrives as a plugin — so
the plugin *is* the automation.

## Before you start

You said you have a backup. Check it is actually somewhere you can reach, not
just that the backup ran. On Personal there is no self-service restore, so that
archive is the only way back.

Nothing here touches your users. It never reads or writes `wp_users` or
`wp_usermeta`, so your WordPress.com login keeps working.

## The migration

**1. Upload the plugin.** wp-admin -> **Plugins -> Add New Plugin -> Upload
Plugin** -> `joni-installer.zip` -> **Install Now** -> **Activate**.

**2. Open it.** **Tools -> Joni Site Installer**. Eight steps are listed, each
marked not yet run.

**3. Click "Run all".** Each step is its own request, so nothing times out.
Running it again is safe — it skips what is already done.

**4. Read the log.** Worth checking: the `media` step should report nothing
missing, and the `menus` step should list all seven menu items.

**5. Look at the site.** Open the homepage in a new tab: the hero image, the
book grid, the Cafe events.

**6. Delete the installer.** Plugins -> Installed Plugins -> deactivate and
delete **Joni Site Installer**. It is a delivery tool. The `joni-books` plugin
it installed **is** permanent — leave that one.

## The steps

| Step | What happens |
|---|---|
| Install the Blocksy theme | Blocksy, from wordpress.org |
| Install Blocksy Companion + Stackable | the two plugins the design needs, from wordpress.org |
| Install the joni-books plugin | the book listings — shipped both as a zip and as plain files, placed by whichever method works on the host |
| Place the images the redesign needs | matches existing images by filename; uploads only what live lacks |
| Create the new pages, events and book entries | homepage, two Cafe events, five books — with meta, covers and categories |
| Build the navigation menu | creates "Main Menu" against *this* site's own page and category IDs |
| Apply the Blocksy design | theme settings, widgets, custom CSS, global styles, logo |
| Activate the theme and set the homepage | makes Blocksy live, points the front page at the new homepage |

## Changing the hero image

The homepage hero is driven by the **Featured Image** on the Home page — no block
editing needed:

1. wp-admin -> **Pages -> Home -> Edit**
2. Right sidebar -> **Featured image** -> Set featured image -> upload or pick one
3. **Update**

To go back to the image baked into the page, just remove the featured image.
Use 1920x1200 or larger; it is displayed full width with `cover` cropping, so the
middle of the picture is what shows.

## If something looks wrong

Reopen **Tools -> Joni Site Installer**. **Revert** puts the design back the way
it was before the Apply step — it took a snapshot first and shows you what it
saved.

**If a step fails, re-running is safe.** Every step checks the current state
first and skips what is already done. Click **Run all** again; finished steps
report as already present and it resumes from the failure.

**If a step fails again, the log says why.** A PHP error is reported with its
message and file, rather than a bare "Unexpected token" line. Copy that line
and send it on.

Order of undoing, worst case first:

1. **Revert** in the installer.
2. **Appearance -> Themes** -> switch back to Canard.
3. **Plugins** -> deactivate whatever was added.
4. **Restore your backup.**

## What it deliberately does not do

- **It never touches users.** Your administrator account and its link to your
  WordPress.com account stay exactly as they are.
- **It never deletes content.** Everything it creates is new; the one page it
  changes is `/books/`, replaced in place. That swap is the intended change.
- **It does not install WPForms or a custom-post-type plugin.** Neither is
  needed: WPForms is an orphan from the old host copy (its only traces are a
  trashed page and an empty placement record), and the custom-post-type plugin
  defines nothing at all. The book listings come from `joni-books`.

## Contents

`manifest.json` records exactly what is in the package and what was left out
and why. Inside the zip: `payload/site.json` (design + content),
`payload/media/` (the two images live doesn't have), `payload/joni-books/`
and `payload/joni-books.zip` (the plugin, in both forms).
"""
open(os.path.join(outdir, "README.md"), "w").write(readme)
log(f"README.md        {len(readme)} bytes")

manifest = {
    "built_for": LIVE_HOST, "built_from": STAGING_HOST,
    "plan_constraint": "WordPress.com Personal — no SSH/SFTP/WP-CLI/DB access",
    "installs": {"theme": THEME, "plugins_from_org": PLUGINS, "bundled_plugin": "joni-books"},
    "excluded_plugins": {
        "wpforms-lite": "orphan — its only references are a trashed page and a revision; "
                        "wpforms_form_locations is empty; no published content uses it",
        "mb-custom-post-type": "defines nothing — 0 mb-post-type and 0 mb-taxonomy rows",
    },
    "content_created": [f"{i['type']}:{i['slug']}" for i in items],
    "pages_replaced_in_place": PAGES_TO_REPLACE,
    "media_carried": carried, "media_already_on_live": present,
    "design": {"theme_mods": len(design_mods), "widget_options": len(widgets),
               "custom_css_bytes": len(custom_css), "global_styles": bool(global_styles)},
}
json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w"), indent=1)

shutil.rmtree(os.path.join(outdir, "build"))

print(f"\nDone. {installer_zip}")
print(f"  content items : {len(items)}")
print(f"  media carried : {len(carried)}")
print(f"  design        : {len(design_mods)} theme mods, {len(widgets)} widget rows")