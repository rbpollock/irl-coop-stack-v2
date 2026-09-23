#!/usr/bin/env python3
"""stats.py — real statistics for the 'wrapped' from ~/.hermes/state.db.

Hours of communication, AI tokens, top models, longest push, cache win, the
hard topics (heavy back-and-forth), major design decisions, major artifacts.
Metadata only — no message content leaves the host.
"""
import json, os, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path

HOME = os.path.expanduser("~/.hermes/state.db")
OUT = Path(__file__).resolve().parent / "stats.json"
ROOT = OUT.parent
DAYS = 45
DECISION_RE = re.compile(r"(decid|about to|design|architecture|proposal|adr| graph|group|federation)", re.I)


def _fmt(n):
    n = int(n or 0)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            return f"{n/div:.1f}{suf}".replace(".0", "")
    return str(n)


def main():
    db = sqlite3.connect(HOME); db.row_factory = sqlite3.Row
    cur = db.cursor()
    now = datetime.now(timezone.utc).timestamp()
    lo = now - DAYS * 86400

    rows = cur.execute(
        "SELECT started_at, ended_at, last_activity_at, model, message_count, "
        "tool_call_count, input_tokens, output_tokens, cache_read_tokens, "
        "cache_write_tokens, reasoning_tokens, title FROM sessions "
        "WHERE started_at IS NOT NULL").fetchall()

    hours = itok = otok = ctok = rtok = n = 0.0
    maxdur = (0, "")
    model = {}
    chall = []
    for r in rows:
        t = float(r["started_at"])
        if not (lo <= t <= now):
            continue
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
        if dur > maxdur[0]:
            maxdur = (dur, r["title"] or "")
        score = (r["message_count"] or 0) + 3 * (r["tool_call_count"] or 0)
        if r["title"]:
            chall.append((score, r["title"]))

    tol = itok + otok + ctok
    cache_pct = 100.0 * ctok / max(1.0, tol)
    heavy = [t for _, t in sorted(chall, reverse=True)[:6]]
    decisions = [t for t in heavy if DECISION_RE.search(t)][:4]
    model_top = sorted(model.items(), key=lambda kv: -kv[1][1])[:4]
    longest = {"hours": round(maxdur[0] / 3600, 1), "title": maxdur[1]}

    # artifacts: the committed things you actually produced this season
    import subprocess
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
        days=DAYS, sessions=int(n),
        hours=round(hours, 1),
        tokens=_fmt(tol), tokens_raw=int(tol),
        cache_pct=round(cache_pct),
        reasoning_pct=round(100.0 * rtok / max(1, tol)),
        models=[{"model": m, "calls": v[0], "tokens": v[1]} for m, v in model_top],
        longest={"hours": round(maxdur[0] / 3600, 1), "title": maxdur[1]},
        challenging=heavy,
        decisions=decisions,
        artifacts=major,
    )
    OUT.write_text(json.dumps(stat, ensure_ascii=False, indent=2))
    print(json.dumps(stat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()