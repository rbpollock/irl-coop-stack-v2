#!/usr/bin/env python3
"""stats.py — stats for the 'wrapped', scoped to the irl-coop-stack repo.

Reads ~/.hermes/state.db sessions that reference the irl.coop stack (cwd /
git_repo_root / title) across ALL time, and writes stats.json. No content.
"""
import json, os, re, sqlite3, subprocess
from pathlib import Path

HOME = os.path.expanduser("~/.hermes/state.db")
OUT = Path(__file__).resolve().parent / "stats.json"
DECISION_RE = re.compile(r"(decid|design|architecture|proposal|adr| plan |group|rag|federation)", re.I)

_DONE = {
    "identity": "one Keycloak realm · SSO everywhere",
    "edge": "wildcard TLS · live routes",
    "cache": "shared, prefixed lanes",
    "data": "one Postgres · RLS-scoped",
    "mail": "Stalwart · DKIM'd, under your roof",
    "workflow": "Temporal · jobs that don't drop",
}
_CHAL = {
    "identity": "the broker & service-account roles kept honest",
    "edge": "cert renewal + atomic route rewrites",
    "cache": "prompt-cache is where the spend hid",
    "data": "the 384-vs-1536 embedding war → fixed at 1024",
    "mail": "the OIDC directory & DKIM path",
    "workflow": "the gate sidecars that self-heal",
}


def _fmt(n):
    n = int(n)
    if n >= 1e9:
        return f"{n/1e9:.1f}B"
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    return f"{n:,}"


def is_irl(r):
    blob = " ".join([r["cwd"] or "", r["git_repo_root"] or "", r["title"] or ""])
    for k in ("irl-coop-stack", "irlcoop", "irl.coop"):
        if k in blob:
            return True
    return False


def main():
    db = sqlite3.connect(HOME)
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    rows = cur.execute(
        "SELECT started_at, ended_at, last_activity_at, model, message_count, "
        "tool_call_count, input_tokens, output_tokens, cache_read_tokens, "
        "cache_write_tokens, reasoning_tokens, title, cwd, git_repo_root "
        "FROM sessions WHERE started_at IS NOT NULL").fetchall()

    hours = itok = otok = ctok = rtok = 0.0
    n = 0
    model = {}
    chall = []
    maxdur = (0, "")
    tmin = tmax = None
    for r in rows:
        t = float(r["started_at"])
        tmin = t if tmin is None else min(tmin, t)
        tmax = t if tmax is None else max(tmax, t)
        n += 1
        end = float(r["ended_at"] or r["last_activity_at"] or t)
        dur = max(0.0, end - t)
        hours += min(dur, 12 * 3600) / 3600
        itok += r["input_tokens"] or 0
        otok += r["output_tokens"] or 0
        ctok += r["cache_read_tokens"] or 0
        rtok += r["reasoning_tokens"] or 0
        m = r["model"] or "?"
        a = model.setdefault(m, [0, 0])
        a[0] += 1
        a[1] += (r["input_tokens"] or 0) + (r["output_tokens"] or 0)
        dur2 = max(0.0, end - t)
        if dur2 > maxdur[0]:
            maxdur = (dur2, r["title"] or "")
        score = (r["message_count"] or 0) + 3 * (r["tool_call_count"] or 0)
        if r["title"]:
            chall.append((score, r["title"]))

    spans = round((tmax - tmin) / 86400) if (tmin and tmax) else 0
    tol = itok + otok + ctok
    cache_pct = 100.0 * ctok / max(1.0, tol)
    heavy = [t for _, t in sorted(chall, reverse=True)[:6]]
    decisions = [t for t in heavy if DECISION_RE.search(t)][:4]
    model_top = sorted(model.items(), key=lambda kv: -kv[1][1])[:4]

    # bucket per vertical pillar
    VERT = [
        ("identity", "Keycloak", ["keycloak", "identity", "oauth", "oauth2", "sso", " realm",
                                  "broker", "authorization", "authorize", "google", "saml"]),
        ("edge", "Traefik", ["traefik", "edge", "proxy", "route", "cert", "tls", "caddy",
                             "nginx", "wildcard", "dns", "proxy-traefik"]),
        ("cache", "Redis", ["redis", "cache", "prompt-cache", "semantic"]),
        ("data", "Postgres", ["postgres", "database", "citus", "store", "sql", "pg", "rls",
                             "vector", "embed", "index", "schema", "backfill", "rag", "noco",
                             "query", "bulk", "citus"]),
        ("mail", "Stalwart", ["stalwart", "mail", "smtp", "imap", "imap", "dkim", "roundcube", "email"]),
        ("workflow", "Temporal", ["temporal", "workflow", "outbox", "worker", "cron", "job", "digest"]),
    ]
    vert = {k: {"h": 0.0, "t": 0, "n": 0} for k, _, _ in VERT}
    for r in rows:
        blob = " ".join([r["title"] or "", r["cwd"] or "", r["git_repo_root"] or ""]).lower()
        hit = None
        for k, _, words in VERT:
            if any(w in blob for w in words):
                hit = k
                break
        if not hit:
            continue
        t0 = float(r["started_at"])
        end = float(r["ended_at"] or r["last_activity_at"] or t0)
        vert[hit]["h"] += min(max(0.0, end - t0), 12 * 3600) / 3600
        vert[hit]["t"] += (r["input_tokens"] or 0) + (r["output_tokens"] or 0) + (r["cache_read_tokens"] or 0)
        vert[hit]["n"] += 1
    verticals = [dict(name=k, comp=c, hours=round(vert[k]["h"], 1),
                      tokens=_fmt(vert[k]["t"]), calls=vert[k]["n"],
                      done=_DONE[k], chal=_CHAL[k])
                 for k, c, _ in VERT]

    # artifacts: git-tracked outputs of this repo
    ROOT = OUT.parent
    repo = ROOT
    while repo != repo.parent and not (repo / ".git").exists():
        repo = repo.parent
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files"],
                             capture_output=True, text=True, timeout=20).stdout.splitlines()
    except Exception:
        out = []
    seen, major = set(), []
    pref = ("docs/design/", "docs/decisions/", "infra/build/images/rag-embed/")
    for f in out:
        if f.startswith(pref) or ("session-story" in f and f.endswith(".py")):
            base = f.split("/")[-1]
            if base not in seen:
                seen.add(base)
                major.append(f)
    major = major[:8]

    stat = dict(
        days=spans, sessions=n, hours=round(hours, 1),
        tokens=_fmt(tol), tokens_raw=int(tol), cache_pct=round(cache_pct),
        reasoning_pct=round(100.0 * rtok / max(1, tol)),
        models=[{"model": m, "calls": v[0], "tokens": v[1]} for m, v in model_top],
        longest={"hours": round(maxdur[0] / 3600, 1), "title": maxdur[1]},
        challenging=heavy,
        decisions=decisions,
        artifacts=major,
        vertical=verticals,
    )
    OUT.write_text(json.dumps(stat, ensure_ascii=False, indent=2))
    print(json.dumps(stat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()