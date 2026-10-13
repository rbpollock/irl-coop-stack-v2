# API 模組

[English README](README.md)

## 模組目的

此模組包含專案的 FastAPI 服務。它目前提供：
- 最小 landing route 與 health route
- JWT / Keycloak 驗證骨架
- `sub` / `groups` claims 解析
- Knowledge Area create/list/detail 最小切片
- area access management API
- area access-check 驗證切片
- documents upload / list / detail API
- ingest jobs detail API
- LangGraph Server built-in thread/run chat runtime
- 外部 benchmark curation CLI，可將 `QASPER` / `UDA` 類資料轉成現有 retrieval evaluation snapshot
- SQLAlchemy ORM 模型與 metadata

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - 若要使用本機 Hugging Face rerank 或 embedding，請改裝 `pip install -e .[dev,local-huggingface]`
  - (註：Alembic 是唯一正式 schema migration 來源；無論 fresh 或既有 PostgreSQL，都先執行 `python -m app.db.migration_runner` 再啟動 API)
  - `langgraph dev --config langgraph.json --host 0.0.0.0 --port 18000 --no-browser`
- 匯出目前 REST OpenAPI schema，供前端產生 contract types：
  - `python -m app.scripts.export_openapi --output -`
- 匯出目前 chat/runtime contract schema，供前端產生 contract types：
  - `python -m app.scripts.export_chat_contracts --output -`
- 本機執行測試：
  - `pytest`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up api`

## 環境變數

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

## Rerank Provider 支援模式

internal retrieval service 現在透過同一個 `RerankProvider` contract 支援四種主要 rerank provider 模式：

- `huggingface`
  - 可選的本機模型 provider
  - 建議 model：`BAAI/bge-reranker-v2-m3`、`Qwen/Qwen3-Reranker-0.6B`
  - 以本機 `torch + transformers` 推論實作
  - 首次使用若本機尚未快取權重，會先下載模型，之後直接使用目前 API 行程的 CPU / GPU 資源推論
- `cohere`
  - 可選的 hosted provider
  - 需要 `COHERE_API_KEY`
- `self-hosted`
  - 目前 runtime 預設的 hosted provider，對接自架 `/v1/rerank` 服務
  - 預設 model：`BAAI/bge-reranker-v2-m3`
  - 需要 `SELF_HOSTED_RERANK_BASE_URL` 與 `SELF_HOSTED_RERANK_API_KEY`
  - 以 `SELF_HOSTED_RERANK_TIMEOUT_SECONDS` 控制 HTTP timeout；預設為 `60s`
- `deterministic`
  - 供離線測試 / 本機 regression 使用的穩定 provider

補充說明：
- 這次變更後，`self-hosted` 是預設 runtime 選擇。
- `huggingface` 是建議使用的本機 / 自架 provider 名稱；舊的 `bge`、`qwen` 值仍會映射到同一條本機實作。
- 本機 Hugging Face 依賴刻意保持 optional，不放進預設安裝路徑。

## 主要目錄結構

- `src/app/main.py`：FastAPI 應用程式進入點
- `src/app/core`：設定與共用執行期輔助元件
- `src/app/auth`：JWT 驗證、principal 解析與 auth dependency
- `src/app/chat`：Deep Agents 主 agent、agent tools 與 LangGraph runtime glue
- `src/app/db`：SQLAlchemy models、session 與 metadata
- `src/app/routes`: HTTP routes
- `src/app/services`：授權、storage、task dispatch、internal retrieval 與 assembler service
- `src/app/scripts`：benchmark import/export/run、外部 benchmark curation CLI、OpenAPI 匯出工具與 chat contract 匯出工具
- `langgraph.json`：LangGraph Server 內建 thread/run runtime 的 loader 設定
- `tests`：授權與 API 測試

## 對外介面

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

## 疑難排解

- 若 API 行程無法啟動，請先確認已安裝 `langgraph-cli[inmem]`，且 `apps/api` 內存在 `langgraph.json`。
- 若前端需要重產 `apps/web/src/generated/rest.ts`，請使用 `python -m app.scripts.export_openapi --output -` 匯出目前 API contract。
- 若前端需要重產 `apps/web/src/generated/chat.ts`，請使用 `python -m app.scripts.export_chat_contracts --output -` 匯出目前 chat/runtime contract。
- 若本機只想跑測試，可啟用 `AUTH_TEST_MODE=true`，以 `Bearer test::<sub>::<group1,group2>` 驗證 auth flow。
- `GET /areas/{area_id}`、`PUT /areas/{area_id}`、`DELETE /areas/{area_id}` 與 `GET /areas/{area_id}/access` 對未授權與不存在資源都會回 `404`，此為 deny-by-default 的既定語意。
- `AUTH_TEST_MODE=true` 常搭配 `STORAGE_BACKEND=filesystem` 供 API 測試使用；Playwright E2E 應一併啟動 API 與 worker。
- upload 與 reindex route 只負責建立 `documents=status=uploaded` 與 `ingest_jobs=status=queued`；parse、chunking、indexing 與最終狀態推進都由 worker 負責。
- reindex、delete 與新的 ingest 執行前都會先清理文件範圍內的 `artifacts/` 前綴，避免殘留舊 parse 產物。
- area delete 採 hard delete；API 會先清掉 area 內每份文件的原始檔與 parse artifacts，再刪除 area 與 cascaded database rows。
- `document_chunks` 已包含 `structure_kind=text|table`，供後續 retrieval 與 observability 直接辨識內容結構。
- 文字 child 會以 `LangChain RecursiveCharacterTextSplitter` 切分；表格 child 則採整表保留或 row-group split。
- `ready` 現在代表 chunk tree、embedding 與可供 PGroonga 使用的 retrieval content 都已完成。
- `retrieve_area_contexts` 仍是 agent 唯一可見的 retrieval tool。當 `CHAT_AGENTIC_ENABLED=true` 時，compare 與 multi-document summary 題可透過同一工具做 bounded follow-up，使用單一 `query_variant`、scoped `document_handles` 與可選 `synopsis_hints`，但最終 citations 仍只來自 assembled contexts。
- `CHAT_AGENTIC_TARGET_LATENCY_SECONDS=20` 與 `CHAT_AGENTIC_MAX_LATENCY_SECONDS=40` 目前只作 trace / benchmark / debug 的 warning threshold，不會硬中止 API 或主動結束 chat session。
- `documents` 現已正式持久化 `synopsis_text`、`synopsis_embedding` 與 `synopsis_updated_at`，作為 Phase 8.3 的 document-level representation contract。
- 目前預設 embedding 路徑仍為 `EMBEDDING_PROVIDER=openai` 與 `EMBEDDING_MODEL=text-embedding-3-small`，而 retrieval schema 固定使用 `1536` 維。
- `EMBEDDING_PROVIDER=huggingface` 可作為本機 / 自架 embedding 路徑，建議模型為 `Qwen/Qwen3-Embedding-0.6B`；provider 會對 query 自動套用官方 instruction 格式，將模型原生 `1024` 維向量零補齊到目前 `1536` 維 schema，並直接使用目前 API 行程的 CPU / GPU 資源。
- 可選的 self-hosted embedding 路徑會走 `POST /v1/embeddings` 與 Bearer auth，並使用 `SELF_HOSTED_EMBEDDING_*` 設定；建議模型為 `Qwen/Qwen3-Embedding-0.6B`。
- `1536` 維 schema 仍位於 pgvector `hnsw` 支援範圍內，因此主線向量召回可以維持 ANN index。
- 本模組目前已具備 internal retrieval foundation，涵蓋 SQL gate、vector recall、PGroonga FTS recall、Python 層 `RRF`、minimal rerank 與 table-aware retrieval assembler，但尚未公開為 HTTP API。
- assembler 會將 rerank 後的 child chunks 組裝為 chat-ready contexts 與 citation-ready metadata，並以 budget guardrails 控制成本。
- rerank 可用 `RERANK_PROVIDER=deterministic` 做離線測試。
- 目前 compose/runtime 預設 rerank 路徑為 `RERANK_PROVIDER=self-hosted` 與 `RERANK_MODEL=BAAI/bge-reranker-v2-m3`。
- `RERANK_PROVIDER=huggingface` 可作為本機 / 自架 rerank 路徑，支援 `BAAI/bge-reranker-v2-m3` 與 `Qwen/Qwen3-Reranker-0.6B`；舊的 `bge` / `qwen` 設定值仍會被當成 alias。
- `RERANK_PROVIDER=cohere` 仍可作為可選 hosted provider，前提是有提供 `COHERE_API_KEY`。
- `RERANK_PROVIDER=self-hosted` 可對接自架 `POST /v1/rerank` 服務，需同時設定 `SELF_HOSTED_RERANK_BASE_URL`、`SELF_HOSTED_RERANK_API_KEY`、`SELF_HOSTED_RERANK_TIMEOUT_SECONDS`，並以 `BAAI/bge-reranker-v2-m3` 作為建議的自架 rerank model。
- 若 API 跑在 Docker Compose，且要啟用本機 Hugging Face provider，請在重建 image 前設定 `API_INSTALL_OPTIONAL_GROUPS=local-huggingface`，避免預設容器路徑額外安裝 `torch` / `transformers`。
- 若要把 `QASPER` / `UDA` / `MS MARCO` / `Natural Questions` 類資料集收斂到現有 benchmark，可使用 `python -m app.scripts.prepare_external_benchmark` 依序執行 `prepare-source`、`filter-items`、`align-spans`、`build-snapshot` 與 `report`。
- 本模組目前只啟用 LlamaParse 的標準 Markdown 轉換路徑，未來才會再評估 agentic mode。
- 未支援格式仍維持受控 `failed`。
- chat 現已透過 LangGraph Server built-in thread/run endpoints 與 custom auth 提供；retrieval pipeline 仍維持 SQL gate 與 ready-only 邊界後才進入 answer layer。
