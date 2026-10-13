# Worker 模組

[English README](README.md)

## 模組目的

此模組包含專案的 Celery worker。它目前提供最小 ingest 任務、文件狀態轉換與 parser routing 骨架，並保留後續 indexing 擴充空間。

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - 若要使用本機 Hugging Face embeddings，請改裝 `pip install -e .[dev,local-huggingface]`
  - `PDF_PARSER_PROVIDER=opendataloader` 已是預設路徑，執行 worker 的主機必須先安裝 `Java 11+`
  - 本 repo 依 OpenDataLoader 官方建議採用 `json,markdown` 雙輸出，並維持 AI safety filters 開啟
  - `celery -A worker.celery_app.celery_app worker --loglevel=INFO`
- 本機健康檢查命令：
  - `python -m worker.scripts.healthcheck`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up worker`

## 環境變數

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

## 主要目錄結構

- `src/worker/celery_app.py`：Celery 應用程式進入點
- `src/worker/tasks`：health、ingest 與 indexing task 模組
- `src/worker/core`：worker 設定與共用輔助元件
- `src/worker/db.py`：worker 使用的最小 DB model 與 session helper
- `src/worker/storage.py`：物件儲存讀取抽象
- `src/worker/parsers.py`：最小 parser router
- `src/worker/scripts`：給操作人員使用的輔助腳本

## 對外介面

- Celery task：`worker.tasks.health.ping`
- Celery task：`worker.tasks.ingest.process_document_ingest`
- 健康檢查腳本：`python -m worker.scripts.healthcheck`

## 疑難排解

- 若 worker 無法連到 Redis，請確認 `CELERY_BROKER_URL`。
- `CELERY_TASK_REJECT_ON_WORKER_LOST=true` 會在 worker 行程異常中止時把尚未完成的案件退回 queue，避免案件在「尚未做完但已被視為接收」的狀態下遺失。
- 若 ingest task 無法更新資料庫，請確認 `DATABASE_URL` 指向與 API 相同的資料庫。
- 若正式環境無法讀取文件內容，請確認 `MINIO_*` 與 `MINIO_BUCKET` 一致。
- 若沒有 task 被註冊，請確認 `worker.tasks` 套件有被 Celery 載入。
- `TXT`、`Markdown`、`HTML` 與 `PDF` 目前都會建立 SQL-first 的 parent-child chunks。
- `PDF_PARSER_PROVIDER=opendataloader` 已是預設路徑。worker 會以 `format=json,markdown`、`use_struct_tree=true`、`image_output=off`、`hybrid=off` 執行 OpenDataLoader，並持久化 `opendataloader.json` 與 `opendataloader.cleaned.md`。
- Windows 本地開發可使用 `scripts/start-worker-marker.ps1 -Mode hybrid` 讓基礎服務維持在 Docker Compose、Celery 跑在專案根目錄 `.venv`；若要直接啟動 container worker，改用 `-Mode compose`。worker 固定與主專案共用同一個虛擬環境。
- 若 OpenDataLoader 在本機一開始就失敗，請先確認 `java -version` 能解析到 Java 11 以上版本。
- `PDF_PARSER_PROVIDER=local` 會使用 `Unstructured partition_pdf(strategy="fast")` 作為自架 fallback；`PDF_PARSER_PROVIDER=llamaparse` 則會先把 PDF 轉成 Markdown，再交給既有 Markdown parser 與 chunk tree。
- `.xlsx` 會使用 `unstructured.partition_xlsx`，優先採用 worksheet `text_as_html`，再回接既有 HTML table-aware parser 與 chunk tree。
- `.docx` 與 `.pptx` 會使用 `unstructured.partition_docx` / `partition_pptx`，再把 Unstructured elements 映射回既有 `text/table` block-aware parser contract。
- `LLAMAPARSE_DO_NOT_CACHE=true` 是企業文件建議的安全預設；`LLAMAPARSE_MERGE_CONTINUED_TABLES=false` 則讓跨頁表格合併維持 opt-in。
- 每次新的 ingest 執行前都會先清理文件範圍內的 `artifacts/` 前綴，避免殘留舊 parse 產物。
- `document_chunks` 已包含 `structure_kind=text|table`，可明確區分一般文字與表格內容。
- 文字 child 會由 `LangChain RecursiveCharacterTextSplitter` 切分；大型表格則依 row groups 切分並重複表頭。
- `CHUNK_FACT_HEAVY_REFINEMENT_ENABLED=true` 可啟用針對 `dataset`、`experimental setup`、`evaluation metrics` 這類 fact-heavy heading 的 evidence-centric child refinement；此路徑目前仍存在於 repo，但預設不屬於 current benchmark baseline。
- `ready` 現在代表 chunking、child embedding、document synopsis 與 synopsis embedding 都已完成。
- worker 目前已負責 child chunk 的 embedding。
- worker 現在會在 ingest / reindex 期間以全 parent coverage 生成 document-level synopsis，寫入 `synopsis_text`，再建立 synopsis embedding，供 Phase 8.3 document recall 使用。
- 目前預設 embedding 路徑仍為 `EMBEDDING_PROVIDER=openai` 與 `EMBEDDING_MODEL=text-embedding-3-small`，而儲存 schema 固定使用 `1536` 維。
- `EMBEDDING_PROVIDER=huggingface` 可作為本機 / 自架 embedding 路徑，建議模型為 `Qwen/Qwen3-Embedding-0.6B`；worker 會在首次使用時視需要下載模型，之後重用本機 Hugging Face cache，並將模型原生 `1024` 維向量零補齊到目前 `1536` 維 schema。
- 可選的 self-hosted 路徑會走 `POST /v1/embeddings` 與 Bearer auth，並使用獨立的 `SELF_HOSTED_EMBEDDING_*` 設定；建議模型為 `Qwen/Qwen3-Embedding-0.6B`。
- 目前主線 embedding 模型與 schema 維度一致，因此 worker 不再依賴先前 `4096` 維路徑的零補齊 workaround。
- OpenAI embeddings 現在會依 `EMBEDDING_MAX_BATCH_TEXTS` 分批送出；若單批仍因 request size 超限被拒絕，worker 會自動再將該批二分後重送。
- OpenAI embeddings 目前只會對暫時性失敗（例如 `429`、`5xx`、連線/timeout）做有限次 backoff retry；`400` 這類永久性錯誤會直接轉成受控 failed，避免 task 以 unexpected exception 結束。
- 若 worker 跑在 Docker Compose，且要啟用本機 Hugging Face embeddings，請在重建 image 前設定 `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface`，避免預設容器路徑額外安裝 `torch` / `transformers`。
- 本模組目前只啟用 LlamaParse 的標準 Markdown 轉換路徑，未來才會再評估 agentic mode。
- 尚未實作的檔案型別仍維持受控 `failed`。
- retrieval API、rerank 與 chat orchestration 不在此模組內實作。
