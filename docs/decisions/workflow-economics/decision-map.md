# Decision map (D1–D9) and phase-0 discovery findings

## Phase-0 finding: what Hermes actually exposes (verified, not assumed)

All paths are absolute under `/home/service/.hermes/hermes-agent/` unless noted.

### Extension points (plugin API)

- **Plugin model (AGENTS.md §Plugins, L774–823):** a standalone plugin is
  `~/.hermes/plugins/<name>/plugin.yaml` + `__init__.py` exposing `register(ctx)`.
  It can register lifecycle hooks
  (`pre_tool_call`, `post_tool_call`, `pre_llm_call`, `post_llm_call`,
  `on_session_start`, `on_session_end`), new tools (`ctx.register_tool`), and
  CLI subcommands (`ctx.register_cli_command` → `hermes <plugname> <subcmd>`).
  Discovery sources: bundled `plugins/`, `$HERMES_HOME/plugins/`,
  `./.hermes/plugins/` (opt-in), pip entry points.
- **Full hook set observed** in `plugins/observability/langfuse/plugin.yaml`:
  `pre_api_request`, `post_api_request`, `api_request_error`, `pre_llm_call`,
  `post_llm_call`, `pre_tool_call`, `post_tool_call`, `on_session_finalize`,
  `on_session_end`, `subagent_start`, `subagent_stop`.
- **Standalone-observability policy (AGENTS.md L830–885):** observability /
  vendor / dashboard plugins must **not** land in-tree. They ship as standalone
  repos installed into `~/.hermes/plugins/`. That is precisely "our" home.
- **Ground rules (AGENTS.md + RFC):** plugins may not modify core files;
  keep additive; prompt-cache-stable; plugin cost. RFC
  [2026-07-plugin-architecture-lessons-pi-opencode.md](https://github.com/NousResearch/hermes-agent/blob/main/docs/rfcs/2026-07-plugin-architecture-lessons-pi-opencode.md)
  shows the failure classes: **no hook timeouts in any peer system**, hooks can
  hang a turn; observer hooks fail open; wire-up drift goes silent. Any plugin
  we ship must be small, timeout-budgeted, and test that its hooks fire.

### Cost/usage data — **already persisted locally** (most important finding)

- Table `session_model_usage` in `~/.hermes/state.db` records **per-call, per
  model** usage. Columns: `session_id, model, billing_provider,
  billing_base_url, billing_mode, task, api_call_count, input_tokens,
  output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens,
  estimated_cost_usd, actual_cost_usd, cost_status, cost_source, first_seen,
  last_seen`. PK =
  `(session_id, model, billing_provider, billing_base_url, billing_mode, task)`.
  Schema: `hermes_state_schema.py:879`. Writer: `hermes_state.py:9055`
  (`update_llm_token_counts`) and `hermes_state.py:9149`
  (`record_auxiliary_usage`, for aux task names).
- `task` = `''` for the main agent loop; `title_generation`,
  `background_review`, `compression`, `vision`, etc. for aux calls.
- **`agent/insights.py` → `InsightsEngine`** already aggregates this:
  `generate(days, source)` / `get_usage_breakdown`. Surfaced via the `/insights`
  slash command (`cli.py:12709`, `_show_insights` at `cli.py:14224`) and the
  dashboard usage breakdown (`web_server.py:15602,15764`).
- **So the raw cost/token data is already local and queryable WITHOUT a plugin.**
  A plugin is not needed to see cost.

### Cost caveats (measured, live data)

- `estimated_cost_usd` is **unreliable for some routes.** Real rows for this
  install's Telnyx→DeepSeek V4-Flash route show `estimated_cost_usd` =
  `191516`, `360516`, `4372866` (USD) for single sessions — absurd, while
  `actual_cost_usd` = `0.0` and `cost_status = 'estimated'` /
  `cost_source = 'provider_models_api'`. The deepseek/telnyx price lookup is
  wrong; a correct local price model would fix attribution.
- `actual_cost_usd` is always `0.0` — Hermes never sees the real bill. Every
  "cost reduced" claim must come from corrected token×price math, not provider
  reports.

### Relevant existing plugins (inspected)

- **observability/langfuse** — the telemetry precedent. Always captures
  structural metadata (IDs, roles, tool names, **token usage, cost, timing**);
  content is a configurable capture mode (`metadata`/`sanitized`/`full`). It
  proves the cost/usage extraction is exposed to hooks.
- **hermes-achievements** — a local observability plugin that reads session
  history and renders a dashboard tab. Proof that a local (non-exporting)
  plugin surface works without an external service.
- **router-provider** (model-providers/router) — a model-router **gateway
  plugin**. Not local routing; a hosted gateway. Relevant only for D8 context.

## Decisions D1–D9 and dependencies

| # | Decision | Meaning | Depends on | Suggested order |
|---|---|---|---|---|
| D1 | Boundary / form factor: plugin vs standalone service vs repo tool vs combo | Where the deliverable lives and what it may touch | none (gate) | **1st (this phase)** |
| D2 | What v1 optimizes first | scopes everything else | D1 | 2nd (accepted) |
| D3 | What data can safely+realistically be observed in v1 | already largely answered by findings above | D1 | 3rd (accepted) |
| D4 | Storage: metadata only vs opt-in redacted vs rich task records | D1, D3 | 4th (accepted) |
| D5 | Smallest report/interaction surface | D1, D2 | 5th (accepted) |
| D6 | One low-risk task class for the first local-model experiment | D2 | 6th (accepted) |
| D7 | Mandatory deterministic safety/approval boundaries | none (hard constraint) | **blocks D8/D9** (accepted) |
| D8 | Classifier for routing: local decision model vs structured output vs deterministic | **proposed** (O4/hybrid: deterministic + local) — 0008 | D2, D5, D6, D7 | after RAG fix (now fixed) |
| D9 | Success metrics + thresholds | define with D2 | D2, D3 | 7th |

> **Unparked 2026-09-22:** D8 is proposed (0008) — hybrid local model
> (deterministic + Open-Jex). RAG fix completed (1024-dim), so the D-im blame
> gate is satisfied; D8 final asks D6-bench acceptance data before lock-in.

**Key dependency note:** D1 (boundary) is a thin gate that does **not** block
D2–D7 in principle, but the user's "one decision at a time" rule means we
sequence: D1 → then D2/D3/D4/D5 (D3 largely pre-answered), D6, D7, then D8/D9
(routing only after gates exist).

This workspace intentionally keeps D9 visible from the start so D2 doesn't
recommend a metric that can't later be measured.