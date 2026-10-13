# RAG retrieval eval — do not tune the reranker by feel

The design-docs search has two knobs that are invisible from the outside
(`RERANK_MODEL`, `RERANK_TOP_N`) and both change the ranking. Guessing at them
produced a config that was **worse than not reranking at all** while costing 5x
the latency. This harness exists so that never happens silently again.

## Run it

```sh
cd infra/scripts/rag-eval
python3 run-eval.py "<label>" --rerank true|false [--json out.json]
```

It posts through the public edge (`https://api.irl.coop/mcp`), so it measures
what the search box on `/design` actually returns — not an internal API.

## What is scored

`query-set.json` holds 21 questions a member could plausibly type, each paired
with the real section of the corpus that answers it, so **ground truth is a fact
about the corpus, not a taste judgement**. Questions are deliberately
paraphrased: they must not reuse the target section's distinctive wording, or
the eval would only measure keyword matching rather than retrieval quality.

- **doc-level** (primary) — is the answering document among the returned
  contexts, at what rank. Robust across the 47-doc / 1142-chunk corpus.
- **section-level** — is the answering *section* present (heading match). Only
  meaningful for markdown docs; the generated HTML docs have repeated heading
  paths, so their items carry `section_key: null`.
- **latency** — median per query, measured alongside, because the whole point is
  the quality/latency trade.

Before trusting a run, confirm every `doc` in the query set is actually indexed;
a label pointing at an unindexed document scores as a permanent miss that no
config can fix (`money-in-and-out.md` was exactly this — the doc is published on
the site but absent from the search area).

## Measured (2026-10, this host, 8 CPU cores)

| config | hit@1 | hit@3 | hit@9 | MRR@9 | section@9 | median |
|---|---|---|---|---|---|---|
| rerank off (RRF only) | 47.6% | 76.2% | 90.5% | 0.630 | 71.4% | **0.44s** |
| bge-reranker-base, 16 cands | 42.9% | 71.4% | 85.7% | 0.584 | 66.7% | 2.52s |
| **bge-reranker-v2-m3, 8 cands** (shipped) | 66.7% | 81.0% | 90.5% | 0.746 | 76.2% | 3.73s |
| bge-reranker-v2-m3, 16 cands | 71.4% | 76.2% | 90.5% | 0.766 | 76.2% | 7.58s |
| bge-reranker-v2-m3, 30 cands (= the old ~17s config) | 71.4% | 81.0% | 90.5% | 0.765 | 66.7% | 12.24s |

Readings:

1. **The reranker is worth having, but only the strong model.** v2-m3 is +23.8pp
   hit@1 over no reranking.
2. **The small reranker is worse than no reranker** and still 5x slower. Model
   size here is not a dial you can trade against latency — it is a
   correct/incorrect choice.
3. **Above ~8 candidates the pool buys nothing.** 8 vs 16 vs 30 differ by at most
   one query on hit@1/MRR (and 8 leads on hit@3), while latency goes
   3.7s -> 7.6s -> 12.2s. The old 30-candidate config that took ~17s scored the
   same hit@1 as 8 candidates and was WORSE at section level. Cutting the pool
   from 30 to 8 is a 3.3x speedup for no measurable quality loss.
4. **If zero quality risk against the old config is required**, set
   `RERANK_TOP_N=16`: identical hit@1/MRR to 30 at ~1.6x less latency. The
   8-vs-16 gap is one query, i.e. below the noise floor of this set.
5. n=21 means one query is ~4.8pp, so treat single-query differences as noise and
   only trust multi-query gaps.

## Known corpus defects this eval surfaced

- **Most HTML documents are effectively unsearchable.** Of 10 HTML docs in the
  area, 8 have 0-4 chunks despite being 15-47 KB of source (`onboarding-prototype.html`
  has **zero**; `irl-coop-architecture.html` and `irl-coop-services-and-storage.html`
  have 2 chunks each, ~1 embedded). Every query targeting them misses in every
  config — an ingestion failure, not a ranking one. Markdown docs average 26
  chunks / ~20k chars by comparison.
- **`money-in-and-out.md` is published on `/design` but absent from the search
  area** — visitors can read it but search can never return it.

Fix the ingestion, then re-run this harness: both defects currently cap the score
rather than reflect it.