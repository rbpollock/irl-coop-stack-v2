# 0008 — Routing classifier (D8)

Status: **proposed** · Owner: Robbie · Date: 2026-09-22
Recovered from PARK: RAG retrieval is now fixed + verified (1024-dim local
end-to-end), satisfying the revist trigger. `feats redepend` on: D2 (workbench),
D5 (in-session tool), D6 (commit/title bench), D7 (G0 gates).

## Decision statement

**How should the v1 workbench decide which model to route a task to — fully
deterministic rules (no model), a local decision/classifier model (e.g.
Open-Jev 2B/9B), structured output from hosted DeepSeek, or a hybrid?**

## Context

- The workbench (D2) proposes *model-per-task* recommendations. Under D7 G0
  those are **recommendations only** — a human still approves every route, so
  the classifier can be imperfect and still safe.
- This is used in-session (D5), metadata-only (D3/D4), local-first.
- The RAG fix proved the local-install model philosophy works and left a local
  embed-inference infra (FastAPI/transformers) that can host a small local
  classifier cheaply.
- Open-Jev (Qwen-based decision head) is a local candidate and Jev-style by
  nature; a deterministic rules layer captures what is near-zero-irritation.

## Non-negotiable

1. **Deterministic authorization, always.** D7: a model step may *recommend*,
   never *authorize*; the human gates any route (G0 in v1).
2. Local-first: no classifier egress; hosted DeepSeek classification allowed
   only as an audited, explicit extra (not default).
3. Metadata only (D3); no prompts/queries.
4. Simple + reversible: classifier is an additive thing a workbench reads, with
   a deterministic fallback that keeps v1 working even if the model is down.

## Options

| id | Option | Mechanic |
|----|--------|----------|
| S_det | Deterministic rules | task-class lookup (task name, cache, token rect) → model; pure rules, no app call |
| S_local | Local decision model | a small local classifier/decision model (e.g. Open-Jev 2B/9B) hosted on the RAG inference host or a tiny add), scoring candidate models |
| S_hosted | Structured output from hosted DeepSeek | call the hosted DeepSeek to classify + recommend (JSON) |
| S_hybrid | deterministic base + local model tiebreak | rules decide; a local model only refines when rules are uncertain, falling back to deterministic |

## Evidence

| # | Claim | Source | Conf |
|----|-------|--------|------|
| e1 | v1 route is recommendation-only (D7 G0) → classifier imperfect is safe | 0007 record | high |
| e2 | Local self-hosted inference infra already runs (embeddings) and can host a small head | rag-inference service (verified) | high |
| e3 | Hosted DeepSeek is not local-first; adds latency/cost per classification | user's local-first priority | high |
| e4 | Deterministic-first is the repo rule; authorizing step is never a model | AGENTS/operating rules | high |

## Assumptions / unknowns

- Task classes are differentiated enough in the D4 ledger for rules to fire most
  of the time (depends on task-label quality; D6 bench will tell). Medium.
- Open-Jev (or a local classifier) is accurate for our few task classes;
  unmeasured → gate by D6 bench verdict. Medium/Low.

## Scored (stable rubric, 0–5; direction only ⚠)

| Crt | S_det | S_local | S_hosted | S_hybrid |
|---|---|---|---|---|
| workflow_leverage | 3 | 4 | 4 | 5 |
| cost_impact | 3 | 4 | 2 | 4 |
| quality_pres | 3 | 4 | 4 | 5 |
| local_first | 5 | 5 | 1 | 5 |
| reversibility | 5 | 4 | 3 | 4 |
| complexity | 5 | 3 | 3 | 3 |
| time_to_value | 5 | 3 | 3 | 4 |
| observability | 4 | 4 | 3 | 5 |
| extensibility | 4 | 5 | 4 | 5 |

**Weighted**: S_hybrid 4.50 · S_det 4.05 · S_local 4.05 · S_hosted 3.10.

`S_hybrid` lead is real: the deterministic layer gives reversibility/simplicity
(D7-friendly), the local model (Open-Jev) adds quality one away from first.

## Recommendation

**Accept S_hybrid as the router's shape**: start with a **deterministic** base
(local task/peers → model) that already works with no ML, and slot a **local
model (Open-Jev 2B/9B) only as a scoring refinement**, guarded by a deterministic
fallback (rules returns result when the model is off or low). Hosting DeepSeek
structured output is NOT recommended now (non-local, higher cost/latency) —
revisit only if local classifier quality over the D6 bench is decisively weak.

Because D7/G0 holds, the classifier never decides: it produces a recommendation
card in-session; you hit approve. Any Open-Jte rollout does not touch D5's
approve-button.

## Human decision required

- Approve the hybrid shape (deterministic base + local Open-Jev tie-break) as
  the v1 classifier, with deterministic fallback and G0 approval — yes/no.
- Confirm you want to trial Open-Jev on the local inference host (D6-class bench)
  rather than on a separate box.

## Implementation consequences (if accepted)

- Deterministic layer: rule table using (task, model, token/cache ratios) from
  the D4 ledger. Zero model.
- Local Jev head: small service on/inference, exposing /classify (task+features
  → candidate scores). `open-jev-serve`.
- In-session decision card (D5) shows rules → model rank + classifier reason,
  plus human approve (D7 G0).

## Validation

- Behind D7: classification accuracy should beat random on a hold-out of the D6
  bench; measure on the same commit/title class first.
- Metric: % of times the top-1 route is accepted by a human in the D6 bench,
  and cost delta of routes actually approved. Threshold: ≥ 75% accept and a
  measurable cost/quality win vs. always-current-model.

## Feasibility probe (2026-09-22, this 8-core/61GB no-GPU host)

Ran **Open-Jev-2B** (Qwen3.5-2B base) on CPU:

- deps in an ephemeral venv; checkpoint + base fetched from HF
- `DecisionModel.load(..., device=cpu)` → **load 41.5s** (one-time)
- commit-title decision request (`choice` + `noul`) → **infer 23.7s for 2 records** (~12s/record), 880 input tokens, 0 output
- calibrated typed output:
  - `route_model` → **local_flash 0.72** (hosted 0.07, cheapest 0.21), confidence 0.58
  - `cheap_ok` → **0.77** (yes: cheap/local adequate for this class)

**Verdict: feasible.** Loads + scores on CPU; returns calibrated typed probabilities and a sane answer. Caveats: ~12s/record on 8 cores → keep the model warm for an in-session card (D5 is on-demand, not hot path); shares CPU/RAM with the host's RAG inference. Feasibility only — accuracy still needs the D6 bench.

## Revisit

- Re-open after D6 bench (task labeling quality) and after Open-Jev 27B mature /
  a local classifier; if local classifier (Open-Jev) quality is poor → consider
  S_hosted with explicit approval per-run.