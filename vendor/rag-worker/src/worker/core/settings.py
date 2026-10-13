"""Celery 骨架 worker 使用的設定物件。"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 本機開發命令預設使用的環境變數檔名稱。
ENV_FILE_NAME = ".env"


EMPTY_STRING_ENV_KEYS = {
    "MINIO_SECURE",
    "CELERY_WORKER_POOL",
    "CELERY_WORKER_CONCURRENCY",
    "CELERY_WORKER_PREFETCH_MULTIPLIER",
    "CELERY_WORKER_MAX_TASKS_PER_CHILD",
    "CELERY_TASK_ACKS_LATE",
    "CELERY_TASK_REJECT_ON_WORKER_LOST",
    "CHUNK_MIN_PARENT_SECTION_LENGTH",
    "CHUNK_TARGET_CHILD_SIZE",
    "CHUNK_CHILD_OVERLAP",
    "CHUNK_CONTENT_PREVIEW_LENGTH",
    "CHUNK_TXT_PARENT_GROUP_SIZE",
    "CHUNK_TABLE_PRESERVE_MAX_CHARS",
    "CHUNK_TABLE_MAX_ROWS_PER_CHILD",
    "CHUNK_FACT_HEAVY_REFINEMENT_ENABLED",
    "EMBEDDING_MAX_BATCH_TEXTS",
    "EMBEDDING_RETRY_MAX_ATTEMPTS",
    "EMBEDDING_RETRY_BASE_DELAY_SECONDS",
    "EMBEDDING_DIMENSIONS",
    "OPENROUTER_HTTP_REFERER",
    "OPENROUTER_TITLE",
    "SELF_HOSTED_EMBEDDING_BASE_URL",
    "SELF_HOSTED_EMBEDDING_API_KEY",
    "SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS",
    "DOCUMENT_SYNOPSIS_ENABLED",
    "DOCUMENT_SYNOPSIS_PROVIDER",
    "DOCUMENT_SECTION_SYNOPSIS_ENABLED",
    "DOCUMENT_SYNOPSIS_MODEL",
    "DOCUMENT_SYNOPSIS_MAX_INPUT_CHARS",
    "DOCUMENT_SYNOPSIS_MAX_OUTPUT_CHARS",
    "DOCUMENT_SYNOPSIS_MAX_OUTPUT_TOKENS",
    "DOCUMENT_SYNOPSIS_PARALLELISM",
    "DOCUMENT_SYNOPSIS_REASONING_EFFORT",
    "DOCUMENT_SYNOPSIS_TEXT_VERBOSITY",
    "OPENDATALOADER_USE_STRUCT_TREE",
    "OPENDATALOADER_QUIET",
    "OPENDATALOADER_JSON_BLOCK_INPUTS_ENABLED",
    "LLAMAPARSE_DO_NOT_CACHE",
    "LLAMAPARSE_MERGE_CONTINUED_TABLES",
}


def _drop_empty_string_env_values(data: Any) -> Any:
    """移除值為空字串的設定輸入，讓欄位回退預設值。

    Args:
        data: Pydantic 在 model 驗證前收到的原始輸入資料。

    Returns:
        若輸入為 dict，會移除指定欄位中的空字串值；否則保留原值。
    """

    if not isinstance(data, dict):
        return data

    normalized_data = dict(data)
    for key in EMPTY_STRING_ENV_KEYS:
        value = normalized_data.get(key)
        if isinstance(value, str) and value.strip() == "":
            normalized_data.pop(key)
    return normalized_data


class WorkerSettings(BaseSettings):
    """Celery 骨架 worker 的執行期設定。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE_NAME, env_file_encoding="utf-8", extra="ignore")

    service_name: Annotated[str, Field(alias="WORKER_SERVICE_NAME")] = "deep-agent-worker"
    database_url: Annotated[str, Field(alias="DATABASE_URL")] = "postgresql://postgres:postgres@postgres:5432/deep_agent_rag"
    broker_url: Annotated[str, Field(alias="CELERY_BROKER_URL")] = "redis://redis:6379/0"
    result_backend: Annotated[str, Field(alias="CELERY_RESULT_BACKEND")] = "redis://redis:6379/1"
    broker_path: Annotated[Path, Field(alias="CELERY_BROKER_PATH")] = Path(".celery-broker")
    worker_pool: Annotated[str, Field(alias="CELERY_WORKER_POOL")] = "solo"
    worker_concurrency: Annotated[int, Field(alias="CELERY_WORKER_CONCURRENCY")] = 1
    worker_prefetch_multiplier: Annotated[int, Field(alias="CELERY_WORKER_PREFETCH_MULTIPLIER")] = 1
    worker_max_tasks_per_child: Annotated[int, Field(alias="CELERY_WORKER_MAX_TASKS_PER_CHILD")] = 1
    task_acks_late: Annotated[bool, Field(alias="CELERY_TASK_ACKS_LATE")] = True
    task_reject_on_worker_lost: Annotated[bool, Field(alias="CELERY_TASK_REJECT_ON_WORKER_LOST")] = True
    storage_backend: Annotated[str, Field(alias="STORAGE_BACKEND")] = "minio"
    minio_endpoint: Annotated[str, Field(alias="MINIO_ENDPOINT")] = "http://minio:9000"
    minio_access_key: Annotated[str, Field(alias="MINIO_ACCESS_KEY")] = "minio"
    minio_secret_key: Annotated[str, Field(alias="MINIO_SECRET_KEY")] = "minio123"
    minio_secure: Annotated[bool, Field(alias="MINIO_SECURE")] = False
    minio_bucket: Annotated[str, Field(alias="MINIO_BUCKET")] = "documents"
    local_storage_path: Annotated[Path, Field(alias="LOCAL_STORAGE_PATH")] = Path(".local-storage")
    chunk_min_parent_section_length: Annotated[int, Field(alias="CHUNK_MIN_PARENT_SECTION_LENGTH")] = 800
    chunk_target_child_size: Annotated[int, Field(alias="CHUNK_TARGET_CHILD_SIZE")] = 800
    chunk_child_overlap: Annotated[int, Field(alias="CHUNK_CHILD_OVERLAP")] = 120
    chunk_content_preview_length: Annotated[int, Field(alias="CHUNK_CONTENT_PREVIEW_LENGTH")] = 120
    chunk_txt_parent_group_size: Annotated[int, Field(alias="CHUNK_TXT_PARENT_GROUP_SIZE")] = 4
    chunk_table_preserve_max_chars: Annotated[int, Field(alias="CHUNK_TABLE_PRESERVE_MAX_CHARS")] = 4000
    chunk_table_max_rows_per_child: Annotated[int, Field(alias="CHUNK_TABLE_MAX_ROWS_PER_CHILD")] = 20
    chunk_fact_heavy_refinement_enabled: Annotated[bool, Field(alias="CHUNK_FACT_HEAVY_REFINEMENT_ENABLED")] = False
    pdf_parser_provider: Annotated[str, Field(alias="PDF_PARSER_PROVIDER")] = "opendataloader"
    opendataloader_use_struct_tree: Annotated[bool, Field(alias="OPENDATALOADER_USE_STRUCT_TREE")] = True
    opendataloader_quiet: Annotated[bool, Field(alias="OPENDATALOADER_QUIET")] = True
    opendataloader_json_block_inputs_enabled: Annotated[
        bool, Field(alias="OPENDATALOADER_JSON_BLOCK_INPUTS_ENABLED")
    ] = False
    llamaparse_api_key: Annotated[str | None, Field(alias="LLAMAPARSE_API_KEY")] = None
    llamaparse_do_not_cache: Annotated[bool, Field(alias="LLAMAPARSE_DO_NOT_CACHE")] = True
    llamaparse_merge_continued_tables: Annotated[bool, Field(alias="LLAMAPARSE_MERGE_CONTINUED_TABLES")] = False
    embedding_provider: Annotated[str, Field(alias="EMBEDDING_PROVIDER")] = "openai"
    embedding_model: Annotated[str, Field(alias="EMBEDDING_MODEL")] = "text-embedding-3-small"
    embedding_max_batch_texts: Annotated[int, Field(alias="EMBEDDING_MAX_BATCH_TEXTS")] = 64
    embedding_retry_max_attempts: Annotated[int, Field(alias="EMBEDDING_RETRY_MAX_ATTEMPTS")] = 3
    embedding_retry_base_delay_seconds: Annotated[float, Field(alias="EMBEDDING_RETRY_BASE_DELAY_SECONDS")] = 2.0
    embedding_dimensions: Annotated[int, Field(alias="EMBEDDING_DIMENSIONS")] = 1536
    openai_api_key: Annotated[str | None, Field(alias="OPENAI_API_KEY")] = None
    openrouter_api_key: Annotated[str | None, Field(alias="OPENROUTER_API_KEY")] = None
    openrouter_http_referer: Annotated[str | None, Field(alias="OPENROUTER_HTTP_REFERER")] = None
    openrouter_title: Annotated[str | None, Field(alias="OPENROUTER_TITLE")] = None
    self_hosted_embedding_base_url: Annotated[str | None, Field(alias="SELF_HOSTED_EMBEDDING_BASE_URL")] = None
    self_hosted_embedding_api_key: Annotated[str | None, Field(alias="SELF_HOSTED_EMBEDDING_API_KEY")] = None
    self_hosted_embedding_timeout_seconds: Annotated[
        float | None, Field(alias="SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS")
    ] = 60.0
    document_synopsis_enabled: Annotated[bool, Field(alias="DOCUMENT_SYNOPSIS_ENABLED")] = True
    document_synopsis_provider: Annotated[str, Field(alias="DOCUMENT_SYNOPSIS_PROVIDER")] = "openai"
    document_section_synopsis_enabled: Annotated[bool, Field(alias="DOCUMENT_SECTION_SYNOPSIS_ENABLED")] = False
    document_synopsis_model: Annotated[str, Field(alias="DOCUMENT_SYNOPSIS_MODEL")] = "gpt-5.4-mini"
    document_synopsis_max_input_chars: Annotated[int, Field(alias="DOCUMENT_SYNOPSIS_MAX_INPUT_CHARS")] = 6000
    document_synopsis_max_output_chars: Annotated[int, Field(alias="DOCUMENT_SYNOPSIS_MAX_OUTPUT_CHARS")] = 1600
    document_synopsis_max_output_tokens: Annotated[int, Field(alias="DOCUMENT_SYNOPSIS_MAX_OUTPUT_TOKENS")] = 2000
    document_synopsis_parallelism: Annotated[int, Field(alias="DOCUMENT_SYNOPSIS_PARALLELISM")] = 6
    document_synopsis_reasoning_effort: Annotated[str, Field(alias="DOCUMENT_SYNOPSIS_REASONING_EFFORT")] = "low"
    document_synopsis_text_verbosity: Annotated[str, Field(alias="DOCUMENT_SYNOPSIS_TEXT_VERBOSITY")] = "low"
    @model_validator(mode="before")
    @classmethod
    def normalize_empty_string_env(cls, data: Any) -> Any:
        """將 compose 注入的空字串欄位移除，避免覆蓋預設值。

        Args:
            data: model 驗證前收到的原始設定輸入。

        Returns:
            已移除空字串設定的輸入資料。
        """

        return _drop_empty_string_env_values(data)


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    """回傳快取後的設定物件，確保同一個行程內設定一致。

    參數：
    - 無

    回傳：
    - `WorkerSettings`：目前行程共用的 worker 執行期設定。
    """

    return WorkerSettings()
