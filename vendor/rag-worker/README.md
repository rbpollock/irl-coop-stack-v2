# Worker Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the project's Celery worker. It currently provides the minimal ingest task flow, document status transitions, and parser routing scaffolding while leaving room for future indexing expansion.

## How to Start

- Local Python run:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - If you plan to use local Hugging Face embeddings, install `pip install -e .[dev,local-huggingface]`
  - `PDF_PARSER_PROVIDER=opendataloader` is the default path and requires `Java 11+`
  - This repository follows the official OpenDataLoader `json,markdown` recommendation and keeps AI safety filters enabled
  - `celery -A worker.celery_app.celery_app worker --loglevel=INFO`
- Local health check:
  - `python -m worker.scripts.healthcheck`
- Docker Compose:
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up worker`

## Environment Variables

- `WORKER_SERVICE_NAME`
- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CELERY_WORKER_POOL`
- `CELERY_WORKER_CONCURRENCY`
- `CELERY_WORKER_PREFETCH_MULTIPLIER`
- `CELERY_WORKER_MAX_TASKS_PER_CHILD`
- `CELERY_TASK_ACKS_LATE`
- `CELERY_TASK_REJECT_ON_WORKER_LOST`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `PDF_PARSER_PROVIDER`
- `OPENDATALOADER_USE_STRUCT_TREE`
- `OPENDATALOADER_QUIET`
- `LLAMAPARSE_API_KEY`
- `LLAMAPARSE_DO_NOT_CACHE`
- `LLAMAPARSE_MERGE_CONTINUED_TABLES`
- `CHUNK_MIN_PARENT_SECTION_LENGTH`
- `CHUNK_TARGET_CHILD_SIZE`
- `CHUNK_CHILD_OVERLAP`
- `CHUNK_CONTENT_PREVIEW_LENGTH`
- `CHUNK_TXT_PARENT_GROUP_SIZE`
- `CHUNK_TABLE_PRESERVE_MAX_CHARS`
- `CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- `CHUNK_FACT_HEAVY_REFINEMENT_ENABLED`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDING_MAX_BATCH_TEXTS`
- `EMBEDDING_RETRY_MAX_ATTEMPTS`
- `EMBEDDING_RETRY_BASE_DELAY_SECONDS`
- `EMBEDDING_DIMENSIONS`
- `DOCUMENT_SYNOPSIS_PROVIDER`
- `DOCUMENT_SYNOPSIS_MODEL`
- `DOCUMENT_SYNOPSIS_MAX_INPUT_CHARS`
- `DOCUMENT_SYNOPSIS_MAX_OUTPUT_CHARS`
- `DOCUMENT_SYNOPSIS_MAX_OUTPUT_TOKENS`
- `DOCUMENT_SYNOPSIS_PARALLELISM`
- `DOCUMENT_SYNOPSIS_REASONING_EFFORT`
- `DOCUMENT_SYNOPSIS_TEXT_VERBOSITY`
- `SELF_HOSTED_EMBEDDING_BASE_URL`
- `SELF_HOSTED_EMBEDDING_API_KEY`
- `SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_HTTP_REFERER`
- `OPENROUTER_TITLE`

## Main Directory Structure

- `src/worker/celery_app.py`: Celery application entry point
- `src/worker/tasks`: health, ingest, and indexing task modules
- `src/worker/core`: worker settings and shared helpers
- `src/worker/db.py`: minimal DB models and session helpers used by the worker
- `src/worker/storage.py`: object storage access abstraction
- `src/worker/parsers.py`: minimal parser router
- `src/worker/scripts`: operational helper scripts

## Public Interfaces

- Celery task: `worker.tasks.health.ping`
- Celery task: `worker.tasks.ingest.process_document_ingest`
- Health check script: `python -m worker.scripts.healthcheck`

## Troubleshooting

- If the worker cannot connect to Redis, verify `CELERY_BROKER_URL`.
- `CELERY_TASK_REJECT_ON_WORKER_LOST=true` pushes an unfinished job back to the queue if the worker process dies unexpectedly, instead of letting the job disappear after it was already reserved.
- If ingest tasks cannot update the database, make sure `DATABASE_URL` points to the same database used by the API.
- If the runtime cannot read document content, confirm that `MINIO_*` and `MINIO_BUCKET` match the deployment settings.
- If no tasks are registered, make sure the `worker.tasks` package is loaded by Celery.
- `TXT`, `Markdown`, `HTML`, and `PDF` files now produce SQL-first parent-child chunks.
- `PDF_PARSER_PROVIDER=opendataloader` is the default path. It runs OpenDataLoader with `format=json,markdown`, `use_struct_tree=true`, `image_output=off`, and `hybrid=off`, then persists `opendataloader.json` and `opendataloader.cleaned.md`.
- Windows local development can use `scripts/start-worker-marker.ps1 -Mode hybrid` to keep Docker Compose for infra while running Celery from the project root `.venv`, or `-Mode compose` to start the containerized worker. The worker shares the same virtual environment as the main project.
- If OpenDataLoader fails immediately on the local machine, check `java -version` first; the worker now requires Java 11+ for the default PDF path.
- `PDF_PARSER_PROVIDER=local` uses `Unstructured partition_pdf(strategy="fast")` as the self-hosted fallback; `PDF_PARSER_PROVIDER=llamaparse` converts PDFs to Markdown through LlamaParse and then reuses the existing Markdown parser and chunk tree.
- `.xlsx` files use `unstructured.partition_xlsx`, prefer worksheet `text_as_html`, and then reuse the existing HTML table-aware parser and chunk tree.
- `.docx` and `.pptx` files use `unstructured.partition_docx` / `partition_pptx`, then map Unstructured elements back into the existing `text/table` block-aware parser contract.
- `LLAMAPARSE_DO_NOT_CACHE=true` is the recommended default for enterprise documents, and `LLAMAPARSE_MERGE_CONTINUED_TABLES=false` keeps cross-page table merges opt-in.
- Fresh ingest runs clear the document-scoped `artifacts/` prefix before writing new parse artifacts.
- `document_chunks` include `structure_kind=text|table`, so table-aware results remain visible to the API and later retrieval layers.
- Text children are split by `LangChain RecursiveCharacterTextSplitter`; large tables are split by row groups with repeated headers.
- `CHUNK_FACT_HEAVY_REFINEMENT_ENABLED=true` enables an optional evidence-centric child refinement path for fact-heavy headings such as `dataset`, `experimental setup`, and `evaluation metrics`; this path exists in the repo but is not part of the current benchmark baseline by default.
- `ready` now means chunking, child embeddings, document synopsis, and synopsis embedding have all been completed.
- The worker is now responsible for child-chunk embeddings.
- The worker now builds document-level synopsis from full parent coverage during ingest/reindex, stores `synopsis_text`, and then writes a synopsis embedding for Phase 8.3 document recall.
- The default embedding path remains `EMBEDDING_PROVIDER=openai` with `EMBEDDING_MODEL=text-embedding-3-small`, and the storage schema expects `1536` dimensions.
- `EMBEDDING_PROVIDER=huggingface` is available for local/self-hosted embedding with `Qwen/Qwen3-Embedding-0.6B`; the worker downloads the model on first use when needed, reuses the local Hugging Face cache afterwards, and zero-pads the model's `1024`-dim output into the current `1536`-dim schema.
- The optional self-hosted path uses `POST /v1/embeddings` with Bearer auth and dedicated `SELF_HOSTED_EMBEDDING_*` settings; the recommended self-hosted model is `Qwen/Qwen3-Embedding-0.6B`.
- The mainline embedding model now matches the schema width directly, so the worker no longer depends on the `4096`-dimension padding workaround.
- OpenAI embeddings are now sent in batches controlled by `EMBEDDING_MAX_BATCH_TEXTS`; if a batch is still rejected for request-size overflow, the worker recursively splits that batch and retries with smaller requests.
- OpenAI embeddings now retry only transient failures such as `429`, `5xx`, and connection/timeout errors with bounded backoff. Permanent `400`-class request errors become controlled failed jobs instead of unexpected task crashes.
- If the worker runs in Docker Compose with local Hugging Face embeddings, set `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface` before rebuilding the image so the default container path does not install `torch` / `transformers` unnecessarily.
- Agentic LlamaParse modes are not enabled in this module yet; only the standard Markdown conversion path is implemented.
- File types outside the implemented parser set still move into controlled `failed` status.
- Public retrieval APIs, rerank, and chat orchestration remain outside this module.
