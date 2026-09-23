# Phase-1 scope (consolidated from accepted D2–D9)

A read-only local **workbench** (D1 O4) that turns Hermes' persisted usage into
a **model-routing recommendation card**, in-session (D5), without ever applying
anything (D7 G0). Phase-1 builds only the engine + a thin CLI; a GUI tab or an
auto-apply are out of scope.

## What it does (v1)

1. Reads `$HERMES_HOME/state.db` → `session_model_usage` (metadata only, D3/D4).
2. **Corrects cost** (D3 finding): recomputes `$c $ from tokens × local price
   cards per (model, provider); ignores broken `provider_models` estimates.
3. Adds task attribution from the `task` column (main loop + aux classes).
4. **Router** (D8 hybrid, deterministic first): a rule layer maps (task-class,
   cost/cache/texture) → a recommended model; a local Open-Jev call (if warm)
   may adjust the tie-break; otherwise rules decide.
5. Renders a **decision card** (D5): per class — current model, recommended,
   corrected cost, cache fraction, confidence, and the D9 fields M1–M8 it can
   currently see; and appends it to the local ledger for the window metrics.

## Explicitly NOT in scope (v1)

- Auto-route / apply (D7 G0).
- Content capture / non-metadata.
- A dashboard UI (D5 chose in-session card).
- Changing provider/spend/creds (never).

## The file here

`tools/wf_workbench.py` — stdlib-only, runs against a real Hermes `state.db`,
prints the decision card + metrics; read-only. That is the working phase-1
artifact that the in-session card (D5) will later call.