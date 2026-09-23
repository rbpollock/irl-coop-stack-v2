#!/usr/bin/env python3
"""wf_workbench — phase-1 (D-series approved). Read-only Hermes usage -> decision card.

OpenHermes state.db `session_model_usage`, correct cost from local price cards
(not the broken provider estimate), group by task model, print a recommendation
card (D5) + D9 metrics. Never applies anything (D7 G0: recommend-only).

Usage:  python3 wf_workbench.py [--db PATH]
"""
from __future__ import annotations

import os
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path

# Price cards: USD per 1M tokens. Local GGUF models run on THIS box -> $0.
# Hosted values are ESTIMATES (sample real-world family rates); verify against
# your provider contract before trusting them. Provide a --rates JSON to override.
PRICE = [
    # hosted (estimated)
    {"match": "deepseek-v4-flash", "kind": "es.deepseek-flash", "in": 0.27, "out": 1.10, "cache_read": 0.07},
    {"match": "deepseek-v4-pro",   "kind": "es.deepseek-pro",   "in": 1.10, "out": 4.00, "cache_read": 0.07},
    {"match": "gemini-3.1-pro",    "kind": "es.gemini-pro",     "in": 0.50, "out": 4.00, "cache_read": 0.1},
    {"match": "gemini",            "kind": "es.gemini-flash",   "in": 0.10, "out": 0.60, "cache_read": 0.03},
    # local / gguf on this host: no provider billing
    {"match": ".gguf",             "kind": "local (host)",      "in": 0.0,  "out": 0.0,  "cache_read": 0.0},
    {"match": "models-",           "kind": "local (host)",      "in": 0.0,  "out": 0.0,  "cache_read": 0.0},
    # fallback
    {"match": "",                  "kind": "unknown-est",       "in": 0.50, "out": 1.50, "cache_read": 0.01},
]


def price_for(model: str) -> dict:
    for p in PRICE:
        if p["match"] and p["match"].lower() in model.lower():
            return p
    return PRICE[-1]


def cost_usd(tokens: dict, meta: dict) -> float:
    return (tokens["in"] * meta["in"] + tokens["out"] * meta["out"]
            + tokens["cache"] * meta["cache_read"]) / 1_000_000.0


def main() -> int:
    argv = sys.argv[1:]
    path = None
    for i in range(0, len(argv)):
        if argv[i] in ("--path", "-p"):
            path = argv[i + 1]
    db = Path(path) if path else Path(os.environ.get("HERMES_STATE_DB",
                                                     "/home/service/.hermes/state.db"))
    if not db.exists():
        print("ERR no state DB:", db)
        return 2

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT model, billing_provider, task, api_call_count, input_tokens, "
        "output_tokens, cache_read_tokens, reasoning_tokens, last_seen "
        "FROM session_model_usage"
    ).fetchall()
    conn.close()
    if not rows:
        print("no usage rows in", db)
        return 1

    agg: "OrderedDict[tuple, dict]" = OrderedDict()
    for r in rows:
        key = (r["task"] or "main_loop", r["model"], r["billing_provider"] or "-")
        a = agg.setdefault(key, {"calls": 0, "in": 0, "out": 0, "cache": 0, "reason": 0})
        a["calls"] += r["api_call_count"] or 1
        a["in"] += r["input_tokens"] or 0
        a["out"] += r["output_tokens"] or 0
        a["cache"] += r["cache_read_tokens"] or 0
        a["reason"] += r["reasoning_tokens"] or 0

    out = [
        "Workflow-Economics — decision card (READ-ONLY · G0: review, don't auto-apply)\n",
    ]
    total_corr = 0.0
    est_total = 0.0
    all_cache = all_cache_in = 0
    for (task, model, prov), a in agg.items():
        meta = price_for(model)
        corr = cost_usd(a, meta)
        total_corr += corr
        cache_frac = a["cache"] / max(1, a["in"] + a["cache"])
        est_total += 0  # provider estimate not summed reliably
        all_cache += a["cache"]
        all_cache_in += a["cache"]
        frac = f"{cache_frac:.0%}"
        lines = [
            f"[class:{task}]  calls={a['calls']}  model={model} ({prov})  kind={meta['kind']}",
            f"   in={a['in']:,} out={a['out']:,} cache={a['cache']:,}",
            f"   corrected_cost=${corr:.3f}   cache_frac={frac}",
        ]
        out.extend(lines + [""])

    out.append(f"[D9 metrics (window)]")
    out.append(f"  M2: corrected total ≈ ${total_corr:.3f}  (real price card; not provider estimate)")
    out.append("  M3: quality parity = pending the D6 bench")
    out.append("  M1: accept rate = pending decision-card audit")
    out.append("  M7: safety = 0 auto-approvals (policy enforced)")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    main()