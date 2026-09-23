#!/usr/bin/env python3
"""Pilot: turn Hermes session history into a storyboard of beats.

Reads the local sessions table (metadata only, no message content), buckets the
work into date-adjacent "beats", and out storyboard.json with each beat's title,
magnitude (token spend), month/date, and act. Confidence is a deterministic
placeholder now; next step swaps it for Open-Jev scene+act scoring.

Usage:  python3 story_decisions.py [days] [--json storyboard.json]
"""
import json, os, sqlite3, sys
from datetime import datetime, timedelta

HOME = os.path.expanduser("~/.hermes/state.db")
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 14
OUT = "storyboard.json"
if "--json" in sys.argv:
    OUT = sys.argv[sys.argv.index("--json") + 1]

def main():
    db = sqlite3.connect(HOME)
    cur = db.cursor()
    since = datetime.utcnow() - timedelta(days=DAYS)
    rows = cur.execute(
            "SELECT title, started_at, message_count, input_tokens, output_tokens, "
            "cache_read_tokens, git_repo_root FROM sessions "
            "WHERE started_at IS NOT NULL ORDER BY started_at"
        ).fetchall()
    db.close()

    beats = []
    for title, started, msg, itok, otok, cache, repo in rows:
        try:
            t = datetime.fromtimestamp(float(started))
        except Exception:
            continue
        if t < since:
            continue
        mag = (itok or 0) + (otok or 0) + (cache or 0) // 100  # cache dominates
        beats.append({
            "title": (title or "untitled").strip()[:60],
            "date": t.strftime("%Y-%m-%d"),
            "magnitude": mag,
            "messages": msg or 0,
            "repo": (repo or "").split("/")[-1] or None,
        })

    # chronological order
    beats.sort(key=lambda b: b["date"])
    # dedupe adjacent same-day + same-title into one beat
    collapsed = []
    for b in beats:
        if collapsed and collapsed[-1]["date"] == b["date"] and collapsed[-1]["title"] == b["title"]:
            collapsed[-1]["magnitude"] += b["magnitude"]
            collapsed[-1]["messages"] += b["messages"]
        else:
            collapsed.append(b)
    beats = collapsed

    n = len(beats)
    # 3-act by chronology (even split), placeholder confidence by log-magnitude
    for i, b in enumerate(beats):
        act = "I" if i < n / 3 else ("II" if i < 2 * n / 3 else "III")
        c = min(0.95, 0.35 + (b["magnitude"] or 0) / 1e9 * 0.5)  # placeholder
        b["act"] = act
        b["confidence"] = round(min(c, 0.95), 2)
        b["_source"] = "deterministic-placeholder"  # replaced by Jev next

    storyboard = {"days": DAYS, "beats": beats,
                  "story": "A working story from your session history — pending Jev scene scoring."}
    with open(OUT, "w") as f:
        import json
        json.dump(storyboard, f, indent=2, ensure_ascii=False)

    print(f"storyboard.json: {n} beats over {DAYS}d")
    for b in beats:
        print(f"  [{b['act']}] {b['date']} {b['magnitude']:>12,} | {b['title'][:58]}  conf {b['confidence']}")

if __name__ == "__main__":
    main()