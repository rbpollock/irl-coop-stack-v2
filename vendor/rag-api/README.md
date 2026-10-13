# API Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the project's FastAPI service. It currently provides:
- Minimal landing and health routes
- JWT / Keycloak authentication scaffolding
- `sub` / `groups` claim parsing
- A minimal Knowledge Area create/list/detail slice
- Area access management APIs
- An area access-check verification slice
- Document upload / list / detail APIs
- Ingest job detail APIs
- LangGraph Server built-in thread/run chat runtime
- An external benchmark curation CLI that converts `QASPER` / `UDA`-style datasets into the existing retrieval evaluation snapshot format
- SQLAlchemy ORM models and metadata

## How to Start

- Local Python run:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - If you plan to use local Hugging Face rerank or embeddings, install `pip install -e .[dev,local-huggingface]`
  - (Note: Alembic is the single schema migration source of truth. Run `python -m app.db.migration_runner` before starting the API against a fresh or existing PostgreSQL database.)
  - `langgraph dev --config langgraph.json --host 0.0.0.0 --port 18000 --no-browser`
- Export the current REST OpenAPI schema for frontend contract generation:
  - `python -m app.scripts.export_openapi --output -`
- Export the current chat/runtime contract schema for frontend contract generation:
  - `python -m app.scripts.export_chat_contracts --output -`
- Run tests locally:
  - `pytest`
- Docker Compose:
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up api`

## Environment Variables

- `API_SERVICE_NAME`
- `API_VERSION`
- `API_HOST`
- `API_PORT`
- `API_CORS_ORIGINS`
- `DATABASE_URL`
- `DATABASE_ECHO`
- `REDIS_URL`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `MAX_UPLOAD_SIZE_BYTES`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_HTTP_REFERER`
- `OPENROUTER_TITLE`
- `RERANK_PROVIDER`
- `RERANK_MODEL`
- `COHERE_API_KEY`
- `SELF_HOSTED_EMBEDDING_BASE_URL`
- `SELF_HOSTED_EMBEDDING_API_KEY`
- `SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS`
- `SELF_HOSTED_RERANK_BASE_URL`
- `SELF_HOSTED_RERANK_API_KEY`
- `SELF_HOSTED_RERANK_TIMEOUT_SECONDS`
- `RERANK_TOP_N`
- `RERANK_MAX_CHARS_PER_DOC`
- `ASSEMBLER_MAX_CONTEXTS`
- `ASSEMBLER_MAX_CHARS_PER_CONTEXT`
- `ASSEMBLER_MAX_CHILDREN_PER_PARENT`
- `RETRIEVAL_VECTOR_TOP_K`
- `RETRIEVAL_FTS_TOP_K`
- `RETRIEVAL_MAX_CANDIDATES`
- `RETRIEVAL_DOCUMENT_RECALL_ENABLED`
- `RETRIEVAL_DOCUMENT_RECALL_TOP_K`
- `RETRIEVAL_RRF_K`
- `RETRIEVAL_HNSW_EF_SEARCH`
- `KEYCLOAK_URL`
- `KEYCLOAK_ISSUER`
- `KEYCLOAK_JWKS_URL`
- `KEYCLOAK_GROUPS_CLAIM`
- `AUTH_TEST_MODE`
- `CHAT_PROVIDER`
- `CHAT_MODEL`
- `CHAT_MAX_OUTPUT_TOKENS`
- `CHAT_TIMEOUT_SECONDS`
- `CHAT_INCLUDE_TRACE`
- `CHAT_STREAM_CHUNK_SIZE`
- `CHAT_STREAM_DEBUG`
- `CHAT_AGENTIC_ENABLED`
- `CHAT_AGENTIC_MAX_TOOL_CALLS_PER_TURN`
- `CHAT_AGENTIC_MAX_QUERY_VARIANT_CHARS`
- `CHAT_AGENTIC_MAX_SCOPED_DOCUMENTS_PER_CALL`
- `CHAT_AGENTIC_MAX_SYNOPSIS_INSPECTIONS_PER_TURN`
- `CHAT_AGENTIC_TARGET_LATENCY_SECONDS`
- `CHAT_AGENTIC_MAX_LATENCY_SECONDS`
- `LANGGRAPH_SERVICE_PORT`
- `LANGSMITH_TRACING`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_WORKSPACE_ID`

## Rerank Provider Support Modes

The internal retrieval service now supports four main rerank provider modes behind the same `RerankProvider` contract:

- `huggingface`
  - optional local-model provider
  - recommended models: `BAAI/bge-reranker-v2-m3`, `Qwen/Qwen3-Reranker-0.6B`
  - implemented with local `torch + transformers` inference
  - downloads weights on first use unless the model is already cached locally, then runs on the current API process CPU / GPU
- `cohere`
  - optional hosted provider
  - requires `COHERE_API_KEY`
- `self-hosted`
  - default runtime provider for a self-hosted `/v1/rerank` service
  - default model: `BAAI/bge-reranker-v2-m3`
  - requires `SELF_HOSTED_RERANK_BASE_URL` and `SELF_HOSTED_RERANK_API_KEY`
  - uses `SELF_HOSTED_RERANK_TIMEOUT_SECONDS` to control HTTP timeout; the default is `60s`
- `deterministic`
  - offline test / fallback-friendly provider for local regression tests

Notes:
- `self-hosted` is the default runtime choice after this change.
- `huggingface` is the recommended local/self-hosted provider name; legacy `bge` and `qwen` values still map to the same local implementation.
- Local Hugging Face dependencies are intentionally optional, not part of the default install path.

## Main Directory Structure

- `src/app/main.py`: FastAPI application entry point
- `src/app/core`: settings and shared runtime helpers
- `src/app/auth`: JWT validation, principal parsing, and auth dependencies
- `src/app/chat`: Deep Agents main agent, agent tools, and LangGraph runtime glue
- `src/app/db`: SQLAlchemy models, sessions, and metadata
- `src/app/routes`: HTTP routes
- `src/app/services`: authorization, storage, task dispatch, internal retrieval, and assembler services
- `src/app/scripts`: benchmark import/export/run utilities, external benchmark curation CLI, OpenAPI export helpers, and chat contract export helpers
- `langgraph.json`: LangGraph Server loader config for the built-in thread/run runtime
- `tests`: authorization and API tests

## Public Interfaces

- `GET /`
- `GET /health`
- `GET /auth/context`
- `POST /areas`
- `GET /areas`
- `GET /areas/{area_id}`
- `PUT /areas/{area_id}`
- `DELETE /areas/{area_id}`
- `GET /areas/{area_id}/access`
- `PUT /areas/{area_id}/access`
- `GET /areas/{area_id}/access-check`
- `POST /areas/{area_id}/documents`
- `GET /areas/{area_id}/documents`
- `GET /documents/{document_id}`
- `POST /documents/{document_id}/reindex`
- `DELETE /documents/{document_id}`
- `GET /ingest-jobs/{job_id}`

## Troubleshooting

- If the API process does not start, verify that `langgraph-cli[inmem]` is installed and `langgraph.json` is present in `apps/api`.
- Use `python -m app.scripts.export_openapi --output -` when the frontend needs to regenerate `apps/web/src/generated/rest.ts` from the current API contract.
- Use `python -m app.scripts.export_chat_contracts --output -` when the frontend needs to regenerate `apps/web/src/generated/chat.ts` from the current chat/runtime contract.
- For local auth tests, enable `AUTH_TEST_MODE=true` and use `Bearer test::<sub>::<group1,group2>`.
- `GET /areas/{area_id}`, `PUT /areas/{area_id}`, `DELETE /areas/{area_id}`, and `GET /areas/{area_id}/access` return `404` for both unauthorized and missing resources by design to preserve `deny-by-default`.
- `AUTH_TEST_MODE=true` is commonly used together with `STORAGE_BACKEND=filesystem` for API tests; Playwright E2E should start both the API and the worker.
- Upload and reindex routes only create `documents=status=uploaded` and `ingest_jobs=status=queued`; parsing, chunking, indexing, and final status transitions are worker-owned.
- Reindex and delete still clear the document-scoped `artifacts/` prefix before the worker writes new parse artifacts.
- Area delete is a hard delete: the API first removes each document's source object and parse artifacts, then deletes the area and cascaded database rows.
- `document_chunks` include `structure_kind=text|table` for downstream retrieval and observability.
- Text children are split with `LangChain RecursiveCharacterTextSplitter`; table children preserve whole tables or split by row groups.
- `ready` now means chunk tree, embeddings, and PGroonga-indexed retrieval content have all been written.
- `retrieve_area_contexts` remains the only agent-visible retrieval tool. When `CHAT_AGENTIC_ENABLED=true`, compare and multi-document summary questions may trigger bounded follow-up retrieval with a single `query_variant`, scoped `document_handles`, and optional `synopsis_hints`, but final citations still come only from assembled contexts.
- `CHAT_AGENTIC_TARGET_LATENCY_SECONDS=20` and `CHAT_AGENTIC_MAX_LATENCY_SECONDS=40` are warning thresholds for trace / benchmark visibility. They do not hard-stop the API or terminate an active chat session.
- `documents` now persist `synopsis_text`, `synopsis_embedding`, and `synopsis_updated_at`; these fields are part of the formal Phase 8.3 document-level representation contract.
- The default embedding path remains `EMBEDDING_PROVIDER=openai` with `EMBEDDING_MODEL=text-embedding-3-small`, and the retrieval schema expects `1536` dimensions.
- `EMBEDDING_PROVIDER=huggingface` is available for local/self-hosted embedding with `Qwen/Qwen3-Embedding-0.6B`; the provider applies the official query instruction format for query embeddings, zero-pads the model's `1024`-dim output into the current `1536`-dim schema, and uses the current process CPU / GPU resources.
- The optional self-hosted embedding path uses `POST /v1/embeddings` with Bearer auth and the `SELF_HOSTED_EMBEDDING_*` settings; the recommended self-hosted model is `Qwen/Qwen3-Embedding-0.6B`.
- The `1536`-dimension schema still fits pgvector `hnsw`, so the mainline vector recall path can keep ANN indexing enabled.
- This module now includes an internal retrieval foundation with SQL gate, vector recall, PGroonga FTS recall, Python-layer `RRF`, minimal rerank, and a table-aware retrieval assembler, but it is not exposed as a public HTTP route yet.
- The assembler turns reranked child chunks into chat-ready contexts and citation-ready metadata with explicit budget guardrails.
- Use `RERANK_PROVIDER=deterministic` for offline tests.
- The default compose/runtime rerank path is `RERANK_PROVIDER=self-hosted` with `RERANK_MODEL=BAAI/bge-reranker-v2-m3`.
- `RERANK_PROVIDER=huggingface` is available for local/self-hosted rerank with `BAAI/bge-reranker-v2-m3` or `Qwen/Qwen3-Reranker-0.6B`; legacy `bge` / `qwen` values still work as aliases.
- `RERANK_PROVIDER=cohere` remains available as an optional hosted provider when `COHERE_API_KEY` is configured.
- `RERANK_PROVIDER=self-hosted` is available for self-hosted rerank services that expose `POST /v1/rerank`; configure `SELF_HOSTED_RERANK_BASE_URL`, `SELF_HOSTED_RERANK_API_KEY`, `SELF_HOSTED_RERANK_TIMEOUT_SECONDS`, and use `BAAI/bge-reranker-v2-m3` as the recommended self-hosted rerank model.
- If you run the API in Docker Compose with local Hugging Face providers, set `API_INSTALL_OPTIONAL_GROUPS=local-huggingface` before rebuilding the image so the default container path does not pull `torch` / `transformers` unnecessarily.
- To fold `QASPER` / `UDA` / `MS MARCO` / `Natural Questions`-style datasets into the existing benchmark contract, use `python -m app.scripts.prepare_external_benchmark` and run `prepare-source`, `filter-items`, `align-spans`, `build-snapshot`, and `report` in sequence.
- Agentic LlamaParse modes are not enabled in this module yet; only the standard Markdown conversion path is implemented.
- Unsupported formats still move into controlled `failed`.
- Chat now runs through LangGraph Server built-in thread/run endpoints with custom auth; the retrieval pipeline remains SQL-gated and ready-only before the answer layer.
