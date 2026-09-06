# Local AI chat — the coop's conversational assistant

Status: design · Sep 2026 · Builds on knowledge-aggregation.md (the public/group/private
visibility tiers and the union query), the coop-api MCP gateway (`api.irl.coop/mcp` —
`rag.retrieve_area_contexts` with the per-call `rerank` flag), and the dashboard chat
widget (the floating-surface pattern). Part of a wider "apps behind one MCP hub"
direction that also brings a CMS (Payload) and a CRM (Twenty) — see the integration
note at the end.

## 0. The model in one paragraph

A member asks the coop a question in plain language. The chat is a **thin loop —
retrieve, then generate** — over the MCP: the question is turned into context by the
existing RAG retrieval (the same union query the docs search already runs), and a
**self-hosted generation model** writes an answer grounded in that context, with
citations back to the source. The retrieval is already built; the new pieces are the
local generation model and the conversational surface. The chat stores nothing — it is
a projection over the same knowledge areas the search reads, and it inherits their
visibility tiers (an anonymous guest gets public answers; a member gets their world-doc
union).

## 1. Principles (new)

1. **Retrieve, then generate — no new store.** The chat adds a generation step over the
   existing retrieval. It does not index, cache, or own knowledge; the RAG areas remain
   the single source of truth.
2. **Grounded, never confabulated.** Every answer cites the contexts it drew on. No
   retrieved context → the model says it doesn't know rather than inventing. Grounding
   is the entire point of building on the RAG instead of a raw model.
3. **Same visibility, same union.** The chat reads exactly what the search reads — the
   public tier for guests, the member's union when authed. No chat-only widening. The
   stale-token 401 → anonymous-retry fallback is inherited from the docs search.
4. **Local generation, by default.** The generation model is self-hosted on the same
   inference path as the embeddings and reranker, so coop knowledge never leaves the host.

## 2. The loop — retrieve, then generate

```
question
  → rag.retrieve_area_contexts(question, rerank: false)   // context + citations
  → prompt = system + contexts + question                  // assemble
  → local LLM (generation)                                 // answer
  → answer + citations                                     // render
```

Two steps, two calls: one MCP round-trip for retrieval, one to the local model for
generation. Retrieval reuses the `rerank: false` path the docs search already takes
(measured 653ms on CPU over the full corpus), so latency is dominated by generation.
The chat holds no server state between turns — a conversation is the client replaying
the prior turns into the prompt, and the retrieval is per-turn, stateless.

## 3. The generation model — the one new inference piece

The RAG stack already serves embeddings (bge-small) and the reranker (bge-reranker-v2-m3)
from `rag-inference`. Generation is a **second model on the same inference service** — a
self-hosted instruction model (a GGUF via llama.cpp, or a vLLM-served model), exposed as
a plain OpenAI-compatible `POST /v1/chat/completions`. The chat client calls it directly
after retrieval; coop-api does not proxy generation — it stays the *retrieval* gateway.

- **Interface:** the same OpenAI-compatible shape the stack already uses for embeddings
  (`{"model", "messages"}` → `{"choices":[{"message":{"content"}}]}`).
- **Model choice is deliberately un-pinned** (the local GPU/CPU budget decides it) — the
  contract is what matters: anything serving that endpoint works, and it can be swapped
  without touching the chat.
- **Streaming** is the one open question — token-by-token streaming is expected UX for a
  chat, but it is an inference-service capability, not a chat-logic decision.

## 4. The surface

The chat is a **dashboard surface, not a new app**. It reuses the floating-widget pattern
of the existing chat widget: a bottom-corner button that opens a panel with the
conversation, history in the client, and a plain input. It starts as a sibling of the
docs search (search = one-shot retrieval; chat = the conversational form), and the two
share the same MCP call path. When the CMS + CRM land, the same surface gains `cms.*`
and `crm.*` tools — the chat is the front door to everything the MCP hub exposes.

## 5. Visibility — anonymous guests and the union

The chat inherits the retrieval's tier logic unchanged:

- **Anonymous guest** → the public tier, no follow-up, the "sign in to ask follow-ups and
  see your group's knowledge" affordance (the existing copy).
- **Authed member** → their world-doc union (public + every group they hold a seat in +
  direct grants), so a group's private knowledge answers *that member* but never leaks to
  a guest.
- **Stale token** → the 401 → anonymous-retry fallback already in the docs search, so a
  lapsed session degrades to public answers instead of erroring.

The chat is a *consumer* of the same visibility rules as search — no new tier, no new
query, no new leak surface.

## 6. Grounding and citations

Each answer is rendered with its sources — the `document_name` / `heading` / `text` the
retrieval returned — linked through the same `/design/<slug>` and `/groups/<slug>` routes
the search already resolves. The model is prompted to answer *from the contexts* and to
say "not in the coop's knowledge" when the retrieval returns nothing relevant; the
client-side check is `contexts.length === 0` → no LLM call at all. Grounding is
machine-enforced at the boundary (no context → no generation), not trusted to the model.

## 7. Out of scope for v1

- **The CMS + CRM tools** (`cms.*`, `crm.*`) — separate specs, following the same
  MCP-hub pattern; the chat is ready for them but does not ship them.
- **Long-running / agentic behavior** — v1 is question → answer, not a tool-using agent
  that mutates state.
- **Per-group model fine-tuning or memory** — the chat is stateless per turn; any
  personalization is just the retrieval union.
- **Streaming** — desirable, deferred until the inference service exposes it.

## Worked example

A member of a hidden care-circle group asks "how did another coop cover a compost need?"
The chat retrieves from the public tier (the Solutions library is public) + the member's
own union (their group's private stories). The local model answers from the cited
stories, and the citations link to the public Solutions-library entries — while the
group's private story stays cited only for that member. An anonymous guest asking the
same question gets the same public answer, minus the private story.

## Integration note — the wider "one MCP hub" direction

This chat is the first consumer of a pattern that also covers a CMS and a CRM. Payload
(CMS) becomes the content layer (the blueprint library, the Solutions library, published
pages) and Twenty (CRM) the member/relationship layer — each an OIDC client of the realm
and a new app in the declarative tree, each exposing its data as MCP tools (`cms.*`,
`crm.*`) behind the single `api.irl.coop/mcp` gateway. The chat is how a member asks
across all three without knowing which system holds the answer. Those two apps are
separate specs; this doc is the chat that will reach them.
