#!/usr/bin/env python3
"""Compare the live jonischwartzchaney.com URL surface against staging.

The point of the migration is to replace the live site without breaking a single
existing URL. This asserts that, and is the check to re-run after any change to
staging's permalink structure, post slugs, or front-page setting.

Exit 0 = every live URL resolves on staging.
"""
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error

LIVE = "https://jonischwartzchaney.com"
STAGING = "https://jonischwartz.irl.coop"
UA = {"User-Agent": "irl-verify/1.0"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def live_urls():
    _, idx = get(f"{LIVE}/sitemap.xml")
    subs = re.findall(r"<loc>([^<]+)</loc>", idx)
    if not subs:
        sys.exit("could not read live sitemap.xml")
    # post sitemap first (the one that carries content URLs), then the rest
    urls = set()
    for s in subs:
        _, body = get(s)
        urls.update(re.findall(r"<loc>([^<]+)</loc>", body))
    return sorted(urls)


def wp(*args):
    p = subprocess.run(
        ["docker", "exec", "-u", "www-data", "workflow-wordpress-1",
         "wp", "--path=/var/www/html", *args],
        capture_output=True, text=True, timeout=180)
    return "\n".join(l for l in p.stdout.splitlines()
                     if "PHP Warning" not in l and "Undefined array key" not in l).strip()


fails = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        fails.append(name)


print("== live URL parity ==")
urls = live_urls()
print(f"  live sitemap carries {len(urls)} URLs")

# Permalink structure must match live's date-based form, or all 42 post URLs 404.
struct = wp("option", "get", "permalink_structure")
check("permalink structure matches live",
      struct == "/%year%/%monthnum%/%day%/%postname%/", struct)
check("static front page set", wp("option", "get", "show_on_front") == "page")
check("front page is the home page",
      wp("option", "get", "page_on_front") == "680",
      wp("option", "get", "page_on_front"))

broken = []
for u in urls:
    path = u.replace(LIVE, "") or "/"
    code, _ = get(f"{STAGING}{path}")
    if not (200 <= code < 400):
        broken.append((code, path))

check(f"all {len(urls)} live URLs resolve on staging", not broken,
      "" if not broken else f"{len(broken)} broken")
for code, path in broken:
    print(f"        {code}  {path}")

print()
if fails:
    print(f"FAILED: {fails}")
    sys.exit(1)
print("ALL CHECKS PASSED — every live URL resolves on staging")