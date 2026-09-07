# Local AI chat — the coop's memory-stateful assistant

Status: design · Sep 2026 · Builds on knowledge-aggregation.md (the public/group/private
visibility tiers and the union query), the coop-api MCP gateway (`api.irl.coop/mcp` —
`rag.retrieve_area_contexts` with the per-call `rerank` flag), and the dashboard chat
widget (the floating-surface pattern). Part of a wider "apps behind one MCP hub"
direction that also brings a CMS (Payload) and a CRM (Twenty) — see the integration
note at the end.

## 0. The model in one paragraph

The coop's assistant is a **memory-stateful harness**, not a Q&A box: a loop of
*memory → retrieval → generation → memory*. It remembers the member — their groups, what
they're working on, what they've decided — in an **explicit, per-member, private-tier
memory** that the member can see, edit, and erase. Each turn it recalls that memory,
retrieves from the same union the search reads, generates a grounded answer with
Chrome's on-device model (the Prompt API, `window.ai`), and then *proposes* new durable facts back into memory for the member
to keep or discard. A stateless "ask a question, get an answer" surface is exactly what
the docs search already is; the harness — the memory and the loop — is what makes the
assistant worth building at all.

## 1. Principles (new)

1. **It's a harness — memory + tools + a loop.** The assistant is defined by its
   persistent memory and its loop, not by a single retrieve-then-generate call. Memory
   is the core; retrieval and generation hang off it.
2. **Memory is explicit.** Everything the harness remembers is visible to the member,
   editable, and individually erasable. The harness *proposes* facts; the member keeps,
   edits, or discards them. No silent memory — deny-by-default.
3. **Grounded, never confabulated.** Answers cite the contexts and memory facts they
   draw on; nothing relevant retrieved → the model says it doesn't know.
4. **Same visibility, same union — plus the private memory.** The retrieval union is
   unchanged (public for guests, the member's union when authed), and the memory is a
   per-member private-tier area that only that member's harness reads and writes.
5. **On-device generation.** The answer is produced by Chrome's built-in Prompt API on
   the member's own machine — the only server-side inference is the retrieval
   (embeddings + reranker). No generation tokens leave the device.

## 2. Memory — the harness's state

Two tiers, both explicit:

- **Short-term memory** — the conversation thread. Ephemeral, scoped to the current
  thread; it is what makes "…and transport?" a follow-up instead of a fresh question.
- **Long-term memory** — durable facts: "member of the care-circle", "looking for shared
  land", "the compost leg went through the coop truck". These persist across sessions
  and are what personalize the assistant.

The two tiers live in two stores, split by their shape:

- **Durable facts** → Postgres (`member_memory`, RLS-scoped to `sub`) — short, queryable,
  the "everything I remember" list the member curates and erases.
- **The conversation transcript** → MinIO `chat/{sub}/…` — append-only, bigger, survives
  reloads. Object storage for the write-shaped data; Postgres for the query-shaped data.

The transcript is **the member's own object, written with their own credentials** — no
shared service user. Access is a *session key*: MinIO STS (`AssumeRoleWithWebIdentity`
against the member's OIDC identity, via the existing s3-bridge) mints short-lived,
scoped credentials for `chat/{sub}/*`, and the browser uses them to read/write its own
prefix directly. That is delegation, not custody — the coop holds no key that can read
every member's chat.

The MCP tools (`memory.recall` / `remember` / `forget`) cover the facts; the transcript
append/history is a separate object-store path (browser-direct to MinIO with the scoped
STS credentials), same per-member scoping.

Explicitness is enforced at the write boundary, not trusted to the model: a fact only
becomes memory after the member lets it through, and any fact can be inspected or
erased at any time.

## 3. The loop

```
question
  → memory.recall                    // short-term thread + long-term facts
  → rag.retrieve_area_contexts       // the union + the member's memory area
  → prompt = memory + contexts + question
  → Chrome Prompt API (window.ai)      // on-device, grounded answer
  → memory.remember (propose)        // surfaced, member-gated
  → answer + citations + memory proposals
```

The write-back is the harness part: a turn may end with one or more proposed facts
("I'll remember you're part of the care-circle — keep it?"), which the member accepts or
discards inline. Nothing about the loop is stateless except the retrieval itself.

## 4. The generation model — Chrome's on-device Prompt API

Generation runs **in the member's browser**, not on a server: Chrome's built-in Prompt
API (`window.ai`, the on-device model) turns the assembled prompt into the answer. The
harness opens a text session (`await window.ai.createTextSession()`) and prompts it with
memory + retrieved contexts + question; the reply streams back client-side. The
embeddings and reranker stay on `rag-inference` (shared retrieval infrastructure), but
the *answer* is produced on the member's own device — coop knowledge never leaves the
browser for the generation step.

- **No model to pin or serve.** The harness depends only on the `window.ai` interface;
  whatever Chrome ships locally is the model. No GGUF, no vLLM, no `rag-inference`
  generation endpoint.
- **Streaming comes free** from the Prompt API's streaming surface — no deferred
  inference-service work.
- **Capability check** — `if (!window.ai)` the chat degrades to retrieval-only (shows the
  cited contexts, no answer) and says the on-device model isn't available.
- **Client-side means client-side.** The token, the memory, and the retrieved contexts
  stay in the browser's JS context for the generation step; nothing round-trips a server
  for the answer.

The chat queries the MCP with `fetch` from the browser — the token rides in the session
and CORS already allows `https://irl.coop`, so no Next.js API-route wrapper is needed;
there is nothing server-side to proxy or hide.

## 5. The surface

The chat is a **dashboard surface, not a new app**. It reuses the floating-widget pattern
of the existing chat widget: a bottom-corner button that opens a panel with the
conversation, the memory (a "what I remember" list the member can edit), and a plain
input. It starts as a sibling of the docs search — search is the one-shot retrieval, chat
is the memory-stateful form — and the two share the same MCP call path. When the CMS +
CRM land, the same surface gains `cms.*` and `crm.*` tools: the harness's memory grows a
"who I am in the coop" that reaches those stores too.

## 6. Visibility — anonymous guests and the union

The chat inherits the retrieval's tier logic unchanged:

- **Anonymous guest** → the public tier, no memory, the "sign in to ask follow-ups and
  see your group's knowledge" affordance (memory is a member privilege — a guest has no
  private area to write).
- **Authed member** → their world-doc union (public + every group they hold a seat in +
  direct grants) *plus* their own private memory area, so a group's private knowledge
  answers *that member* but never leaks to a guest.
- **Stale token** → the 401 → anonymous-retry fallback already in the docs search.

The memory area is a consumer of the same visibility rules as every knowledge area —
private-tier, `scoped_by sub`, member-owned.

## 7. Grounding and citations

Each answer is rendered with its sources — the `document_name` / `heading` / `text` the
retrieval returned, plus any memory facts it drew on — linked through the same
`/design/<slug>` and `/groups/<slug>` routes the search already resolves. The model is
prompted to answer *from the contexts and memory* and to say "not in the coop's
knowledge" when the retrieval returns nothing relevant; the client-side check is
`contexts.length === 0 && memory.length === 0` → no LLM call at all. Grounding is
machine-enforced at the boundary, not trusted to the model.

## 8. Out of scope for v1

- **The CMS + CRM tools** (`cms.*`, `crm.*`) — separate specs, following the same
  MCP-hub pattern; the harness is ready for them but does not ship them.
- **Agentic state-mutation beyond memory** — the harness reads and writes its *own*
  memory, but v1 does not mutate other coop state (no "create the group", "post the
  need", "send the message"). That is the v2 agent, gated by the delegation/session-key
  model.
- **Per-group model fine-tuning** — personalization is the memory + the union, not a
  tuned model.

## Worked example

A member of a hidden care-circle group asks "how did another coop cover a compost need?"
The harness recalls: they're in the care-circle (long-term memory), and they'd asked
earlier about winter storage (short-term thread). It retrieves the public Solutions
library + the care-circle's private stories + the member's memory. The local model
answers from the cited stories, and the citations link to the public entries — while the
group's private story stays cited only for that member. The turn ends with a proposal:
"remember: you're part of the care-circle" — already known, so nothing new; or "remember:
looking for winter storage" if that was new. The member keeps or discards it inline. An
anonymous guest asking the same question gets the same public answer, no memory, and no
private story.

## Integration note — the wider "one MCP hub" direction

This chat is the first consumer of a pattern that also covers a CMS and a CRM. Payload
(CMS) becomes the content layer (the blueprint library, the Solutions library, published
pages) and Twenty (CRM) the member/relationship layer — each an OIDC client of the realm
and a new app in the declarative tree, each exposing its data as MCP tools (`cms.*`,
`crm.*`) behind the single `api.irl.coop/mcp` gateway. The harness is how a member asks
across all three — and, over time, how its memory comes to know who the member is across
the coop's systems. Those two apps are separate specs; this doc is the harness that will
reach them.
