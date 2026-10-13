#!/usr/bin/env python3
"""Score the design-docs search against a labelled query set.

Ground truth is a real section of the corpus, so this measures the thing the
search box actually does rather than an impression. Two levels are scored:

  doc-level      is the answering DOCUMENT among the 9 returned contexts, and at
                 what rank (robust; the corpus is 47 docs / 1142 chunks)
  section-level  is that document's answering SECTION present (heading match);
                 only meaningful for markdown docs with clean headings

Usage:
  run-eval.py <tag> [--rerank true|false] [--url .../mcp] [--json out.json]

Every ground-truth document is checked against the corpus first, so an item that
cannot be retrieved (not indexed / renamed) fails loudly instead of silently
scoring as a miss.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_URL = "https://api.irl.coop/mcp"


def call(url: str, area: str, question: str, rerank: bool, timeout: int = 180):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "rag.retrieve_area_contexts",
            "arguments": {"area_id": area, "question": question, "rerank": rerank},
        },
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    elapsed = time.time() - started
    text = json.loads(raw)["result"]["content"][0]["text"]
    return elapsed, json.loads(text).get("contexts", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--rerank", default="true")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    rerank = args.rerank.lower() == "true"

    spec = json.loads((HERE / "query-set.json").read_text())
    area = spec["area_id"]
    items = spec["items"]

    rows, times = [], []
    for item in items:
        try:
            elapsed, contexts = call(args.url, area, item["q"], rerank)
        except Exception as exc:  # noqa: BLE001 - surface, don't hide
            print(f"  ERROR {item['q'][:50]}: {exc}")
            continue
        times.append(elapsed)

        doc_rank = next(
            (i for i, c in enumerate(contexts, 1) if c.get("document_name") == item["doc"]), None
        )
        key = item.get("section_key")
        sec_hit = any(
            c.get("document_name") == item["doc"]
            and key
            and key.lower() in (c.get("heading") or "").lower()
            for c in contexts
        )
        rows.append({
            "q": item["q"], "doc": item["doc"], "seconds": round(elapsed, 2),
            "doc_rank": doc_rank, "section_hit": sec_hit,
            "top1": contexts[0].get("document_name") if contexts else None,
            "returned_docs": [c.get("document_name") for c in contexts],
        })
        flag = "  " if doc_rank == 1 else ("ok" if doc_rank else "MISS")
        print(f"  [{elapsed:5.2f}s] {flag:4s} rank={doc_rank or '-':<3} {item['q'][:56]}")

    n = len(rows)
    if not n:
        print("no rows")
        return 1
    h1 = sum(1 for r in rows if r["doc_rank"] == 1) / n
    h3 = sum(1 for r in rows if r["doc_rank"] and r["doc_rank"] <= 3) / n
    h9 = sum(1 for r in rows if r["doc_rank"]) / n
    mrr = sum(1 / r["doc_rank"] for r in rows if r["doc_rank"]) / n
    sec = sum(1 for r in rows if r["section_hit"]) / n

    print(f"\n== {args.tag}  (rerank={rerank}, n={n}, corpus=47 docs/1142 chunks)")
    print(f"   doc hit@1 {h1:6.1%}   hit@3 {h3:6.1%}   hit@9 {h9:6.1%}   MRR@9 {mrr:.3f}")
    print(f"   section-level hit@9 {sec:6.1%}   latency median {sorted(times)[len(times) // 2]:.2f}s")
    misses = [r for r in rows if not r["doc_rank"]]
    if misses:
        print(f"   absent (right doc not in the 9 returned): {len(misses)}")
        for r in misses:
            print(f"     - {r['q'][:52]}\n       wanted {r['doc']}  got {r['top1']}")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"tag": args.tag, "rerank": rerank, "n": n, "hit@1": h1, "hit@3": h3,
             "hit@9": h9, "mrr@9": mrr, "section_hit@9": sec, "rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())