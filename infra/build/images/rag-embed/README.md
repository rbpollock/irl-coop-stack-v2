# rag-embed overlay — 1024-dim local embeddings (self-hosted bge-large)

## Why this exists
The `irlcoop/rag-*:0.1.0` images **hard-code `DEFAULT_EMBEDDING_DIMENSIONS = 1536`**
(worker `db_types.py`, api `app/db/sql_types.py` + `app/core/settings.py`); the
embedding provider refuses any other dimension. A 1536-dim store is incompatible
with local CPU self-hosted embedders (which top out ~1024), and the previous
setup paired a **1536 store with a 384-dim `bge-small`** embedder — degrading
every query. These overlays move the contract to **1024** so the store, index,
and the local `bge-large-en-v1.5` embedder all agree.

## Images
- `irlcoop/rag-worker:0.1.0-1024`
- `irlcoop/rag-api:0.1.0-1024`

`rag-migrate` uses the api image.

## What the overlay patches (keep both reasons in mind)

1. **Embedding dimension 1536 → 1024** — `app/core/settings.py`, `app/db/sql_types.py`
   (worker: `db/worker/db_types.py`).
2. **Retrieval relevance is surfaced, not discarded** (server-side, added for the
   search UI's per-result relevance badge) — `app/routes/mcp.py`,
   `app/services/retrieval_assembler.py`:
   - `AssembledContext` gains `score` / `score_kind` / `score_rank`.
   - `_resolve_context_score()` in the assembler fills them from the best-ranked
     child kept in the context: the rerank score when the cross-encoder actually
     ran, else the RRF score. **The two scales are not comparable and are never
     mixed** — `score_kind` says which one it is; do not average or compare them
     across kinds.
   - `_serialize_retrieval()` in `mcp.py` emits the three fields (via `getattr`,
     so it stays safe against an unpatched assembler).

   The runtime always computed these and dropped them at the MCP boundary; the
   overlay only carries them through. The dashboard reads `score_kind` to label a
   reranker percentage vs a plain "related" (RRF-only) result.

**Revert the score patch in one command** (the tag is made before every rebuild):
```sh
docker tag irlcoop/rag-api:0.1.0-1024-prescores irlcoop/rag-api:0.1.0-1024
docker compose -f infra/out/dev/compose/workflow/docker-compose.yml \
  -f infra/out/dev/compose/workflow/docker-compose.override.yml up -d rag-api
```
Tag the current image aside BEFORE rebuilding, i.e.
`docker tag irlcoop/rag-api:0.1.0-1024 irlcoop/rag-api:0.1.0-1024-prescores`.

## How to build (host images are LOCAL; no registry)
The overlay **does NOT pull a base from a registry** — it `FROM`s the existing
local `irlcoop/rag-*:0.1.0` image, so that base must be present on the daemon
first (`docker image exists` / was loaded). Then:

```sh
cd infra/build/images/rag-embed
docker build -f worker-overlay/Dockerfile -t irlcoop/rag-worker:0.1.0-1024 worker-overlay
docker build -f api-overlay/Dockerfile     -t irlcoop/rag-api:0.1.0-1024   api-overlay
```

Each overlay only overrides the constant file(s); the rest of the base is kept.

## Reinforce the invariant (keep it working)
- `EMBEDDING_DIMENSIONS` must stay `1024` (it's in the `rag-{api,worker,migrate}` specs).
- `EMBED_MODEL` (inference) must stay a **1024-dim** model (`BAAI/bge-large-en-v1.5`), never 1536, never a 384 small.
- DB vector column dim, the HNSW index, and the embedder must all be 1024.

## Rebuild from here after a restore that lost the images
`docker load` the `-1024` images (see infra backups) first, then the build above
is a no-op re-tag; if daemon is empty, load the base `0.1.0` images and rebuild
the overlays.