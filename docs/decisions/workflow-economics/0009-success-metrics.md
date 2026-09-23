# 0009 — Success metrics & thresholds (D9)

Status: **accepted** · Owner: Robbie · Date: 2026-09-22
Depends: D2 (routing workbench), D3 (metadata-only observe), D6 (commit/title bench), D8 (hybrid router).

## Decision statement

**What success metrics and thresholds prove this actually improves the workflow — not merely that total visible API cost went down?**

## Context

The goal (D2) is a local decision/routing workbench that makes work better AND cheaper AND stays local. The risk is that anyone can lower cost by swapping to a worse model; a "win" must be measured as outcomes, not just dollars. D9 fixes the bar the D6 bench and the whole routing premise is judged against.

## Non-negotiable

1. Cost is a consequence, not the sole success gate. "Spent less" alone is a fail if task quality drops.
2. Quality parity is a precondition of any cost win (D7/D8).
3. Everything measurable from the D4 local task ledger + a decision audit — no new content capture.
4. Thresholds are deterministic and auditable; no "vibes."

## Success metrics (over a window)

| # | Metric | Source (D4 ledger + audit) |
|---|--------|------------------------------|
| M1 | **Accept rate** | approved decision cards / all cards shown |
| M2 | **Corrected cost per task-class** | tokens × true local price, per (task, model) |
| M3 | **Quality parity** | D6 paired bench: accept of cheap/local vs incumbent (same inputs) |
| M4 | **Cache fraction** | cache_read / total input tokens (prompt-cache stable) |
| M5 | **Latency delta** | only if a timing hook lands; exempt in v1 |
| M6 | **Coverage** | share of tasks the router made a recommendation for |
| M7 | **Safety** | zero auto-approvals outside the allowlist (D7 audit); zero content leak |
| M8 | **Regret** | rollbacks/reverts of routed actions in the window |

## Thresholds (phase one, clean 2–4 week window vs baseline)

- **M1 ≥ 0.60** accept rate (recommender isn't noise).
- **M2 ≥ 10%** corrected-cost reduction vs always-current-model, over the *same* task set (not a pick).
- **M3**: routed cheap/local output accepted ≥ incumbent (within ±5%); a cost win on a quality loss is a **FAIL**.
- **M7 = 0 violations**, always (hard gate).

Ship/keep the router = **all of** M7, M1, M2, M3 pass. Cost-only-win-with-quality-loss → revert routing and re-open D8.

## Revisit
Any D7 gate change; any metric uncomputable from the local ledger; or an experiment that changes the (task, model) allowlist.

## Implementation
- The workbench appends M1–M8 to every decision card and accumulates them in the D4 ledger + audit; the D6 bench produces M3. No content capture, no new security scope.