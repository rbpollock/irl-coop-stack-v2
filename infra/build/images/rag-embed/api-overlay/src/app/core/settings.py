"""FastAPI 服務的執行期設定與設定依賴。"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi import Request


# 本機開發命令預設使用的環境變數檔名稱。
ENV_FILE_NAME = ".env"

EMPTY_STRING_ENV_KEYS = {
    "MINIO_SECURE",
    "MAX_UPLOAD_SIZE_BYTES",
    "CHUNK_MIN_PARENT_SECTION_LENGTH",
    "CHUNK_TARGET_CHILD_SIZE",
    "CHUNK_CHILD_OVERLAP",
    "CHUNK_CONTENT_PREVIEW_LENGTH",
    "CHUNK_TXT_PARENT_GROUP_SIZE",
    "CHUNK_TABLE_PRESERVE_MAX_CHARS",
    "CHUNK_TABLE_MAX_ROWS_PER_CHILD",
    "EMBEDDING_DIMENSIONS",
    "OPENROUTER_HTTP_REFERER",
    "OPENROUTER_TITLE",
    "SELF_HOSTED_RERANK_BASE_URL",
    "SELF_HOSTED_RERANK_API_KEY",
    "SELF_HOSTED_RERANK_TIMEOUT_SECONDS",
    "SELF_HOSTED_EMBEDDING_BASE_URL",
    "SELF_HOSTED_EMBEDDING_API_KEY",
    "SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS",
    "RETRIEVAL_VECTOR_TOP_K",
    "RETRIEVAL_FTS_TOP_K",
    "RETRIEVAL_MAX_CANDIDATES",
    "RETRIEVAL_DOCUMENT_RECALL_ENABLED",
    "RETRIEVAL_DOCUMENT_RECALL_TOP_K",
    "RETRIEVAL_RRF_K",
    "RETRIEVAL_HNSW_EF_SEARCH",
    "RERANK_TOP_N",
    "RERANK_MAX_CHARS_PER_DOC",
    "RERANK_RETRY_ON_429_ATTEMPTS",
    "RERANK_RETRY_ON_429_BACKOFF_SECONDS",
    "ASSEMBLER_MAX_CONTEXTS",
    "ASSEMBLER_MAX_CHARS_PER_CONTEXT",
    "ASSEMBLER_MAX_CHILDREN_PER_PARENT",
    "CHAT_PROVIDER",
    "CHAT_MODEL",
    "CHAT_MAX_OUTPUT_TOKENS",
    "CHAT_TIMEOUT_SECONDS",
    "CHAT_STREAM_CHUNK_SIZE",
    "CHAT_STREAM_DEBUG",
    "CHAT_AGENTIC_ENABLED",
    "CHAT_AGENTIC_MAX_TOOL_CALLS_PER_TURN",
    "CHAT_AGENTIC_MAX_QUERY_VARIANT_CHARS",
    "CHAT_AGENTIC_MAX_SCOPED_DOCUMENTS_PER_CALL",
    "CHAT_AGENTIC_MAX_SYNOPSIS_INSPECTIONS_PER_TURN",
    "CHAT_AGENTIC_TARGET_LATENCY_SECONDS",
    "CHAT_AGENTIC_MAX_LATENCY_SECONDS",
    "LANGGRAPH_API_URL",
    "SUMMARY_COMPARE_EVAL_JUDGE_MODEL",
    "SUMMARY_COMPARE_EVAL_MAX_P95_LATENCY_SECONDS",
    "SUMMARY_COMPARE_EVAL_MAX_TOTAL_TOKENS_PER_ITEM",
    "SUMMARY_COMPARE_EVAL_PASS_MIN_AVG_SCORE",
    "LANGGRAPH_SERVICE_PORT",
    "LANGSMITH_API_KEY",
    "LANGSMITH_ENDPOINT",
    "LANGSMITH_WORKSPACE_ID",
    "LANGSMITH_TRACING",
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


class AppSettings(BaseSettings):
    """FastAPI 服務的執行期設定。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE_NAME, env_file_encoding="utf-8", extra="ignore")

    service_name: Annotated[str, Field(alias="API_SERVICE_NAME")] = "deep-agent-api"
    version: Annotated[str, Field(alias="API_VERSION")] = "0.1.0"
    host: Annotated[str, Field(alias="API_HOST")] = "0.0.0.0"
    port: Annotated[int, Field(alias="API_PORT")] = 8000
    cors_origins: Annotated[str, Field(alias="API_CORS_ORIGINS")] = "http://localhost:3000,http://localhost:13000"
    database_url: Annotated[str, Field(alias="DATABASE_URL")] = "postgresql://postgres:postgres@postgres:5432/deep_agent_rag"
    database_echo: Annotated[bool, Field(alias="DATABASE_ECHO")] = False
    redis_url: Annotated[str, Field(alias="REDIS_URL")] = "redis://redis:6379/0"
    storage_backend: Annotated[str, Field(alias="STORAGE_BACKEND")] = "minio"
    minio_endpoint: Annotated[str, Field(alias="MINIO_ENDPOINT")] = "http://minio:9000"
    minio_access_key: Annotated[str, Field(alias="MINIO_ACCESS_KEY")] = "minio"
    minio_secret_key: Annotated[str, Field(alias="MINIO_SECRET_KEY")] = "minio123"
    minio_secure: Annotated[bool, Field(alias="MINIO_SECURE")] = False
    minio_bucket: Annotated[str, Field(alias="MINIO_BUCKET")] = "documents"
    local_storage_path: Annotated[Path, Field(alias="LOCAL_STORAGE_PATH")] = Path(".local-storage")
    max_upload_size_bytes: Annotated[int, Field(alias="MAX_UPLOAD_SIZE_BYTES")] = 5 * 1024 * 1024
    chunk_min_parent_section_length: Annotated[int, Field(alias="CHUNK_MIN_PARENT_SECTION_LENGTH")] = 800
    chunk_target_child_size: Annotated[int, Field(alias="CHUNK_TARGET_CHILD_SIZE")] = 800
    chunk_child_overlap: Annotated[int, Field(alias="CHUNK_CHILD_OVERLAP")] = 120
    chunk_content_preview_length: Annotated[int, Field(alias="CHUNK_CONTENT_PREVIEW_LENGTH")] = 120
    chunk_txt_parent_group_size: Annotated[int, Field(alias="CHUNK_TXT_PARENT_GROUP_SIZE")] = 4
    chunk_table_preserve_max_chars: Annotated[int, Field(alias="CHUNK_TABLE_PRESERVE_MAX_CHARS")] = 4000
    chunk_table_max_rows_per_child: Annotated[int, Field(alias="CHUNK_TABLE_MAX_ROWS_PER_CHILD")] = 20
    celery_broker_url: Annotated[str, Field(alias="CELERY_BROKER_URL")] = "redis://redis:6379/0"
    celery_result_backend: Annotated[str, Field(alias="CELERY_RESULT_BACKEND")] = "redis://redis:6379/1"
    celery_broker_path: Annotated[Path, Field(alias="CELERY_BROKER_PATH")] = Path(".celery-broker")
    keycloak_url: Annotated[str, Field(alias="KEYCLOAK_URL")] = "http://keycloak:8080"
    keycloak_issuer: Annotated[str, Field(alias="KEYCLOAK_ISSUER")] = "http://localhost:18080/realms/deep-agent-dev"
    keycloak_jwks_url: Annotated[str, Field(alias="KEYCLOAK_JWKS_URL")] = (
        "http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs"
    )
    keycloak_groups_claim: Annotated[str, Field(alias="KEYCLOAK_GROUPS_CLAIM")] = "groups"
    keycloak_admin_user: Annotated[str, Field(alias="KEYCLOAK_ADMIN")] = "admin"
    keycloak_admin_password: Annotated[str, Field(alias="KEYCLOAK_ADMIN_PASSWORD")] = "admin"
    keycloak_realm: Annotated[str, Field(alias="KEYCLOAK_REALM")] = "deep-agent-dev"
    # irl.coop fleet JWT (coop-api-minted): same sub+groups, issuer api.irl.coop.
    # Trusted alongside the realm so MCP / server-to-server calls authenticate
    # without a second Keycloak bounce. Set to empty string to disable.
    coop_jwt_issuer: Annotated[str, Field(alias="COOP_JWT_ISSUER")] = "https://api.irl.coop"
    coop_jwt_jwks_url: Annotated[str, Field(alias="COOP_JWT_JWKS_URL")] = "https://api.irl.coop/jwks"
    auth_test_mode: Annotated[bool, Field(alias="AUTH_TEST_MODE")] = False
    embedding_provider: Annotated[str, Field(alias="EMBEDDING_PROVIDER")] = "openai"
    embedding_model: Annotated[str, Field(alias="EMBEDDING_MODEL")] = "text-embedding-3-small"
    embedding_dimensions: Annotated[int, Field(alias="EMBEDDING_DIMENSIONS")] = 1024
    openai_api_key: Annotated[str | None, Field(alias="OPENAI_API_KEY")] = None
    openrouter_api_key: Annotated[str | None, Field(alias="OPENROUTER_API_KEY")] = None
    openrouter_http_referer: Annotated[str | None, Field(alias="OPENROUTER_HTTP_REFERER")] = None
    openrouter_title: Annotated[str | None, Field(alias="OPENROUTER_TITLE")] = None
    self_hosted_embedding_base_url: Annotated[str | None, Field(alias="SELF_HOSTED_EMBEDDING_BASE_URL")] = None
    self_hosted_embedding_api_key: Annotated[str | None, Field(alias="SELF_HOSTED_EMBEDDING_API_KEY")] = None
    self_hosted_embedding_timeout_seconds: Annotated[
        float | None, Field(alias="SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS")
    ] = 60.0
    retrieval_vector_top_k: Annotated[int, Field(alias="RETRIEVAL_VECTOR_TOP_K")] = 30
    retrieval_fts_top_k: Annotated[int, Field(alias="RETRIEVAL_FTS_TOP_K")] = 30
    retrieval_max_candidates: Annotated[int, Field(alias="RETRIEVAL_MAX_CANDIDATES")] = 30
    retrieval_document_recall_enabled: Annotated[bool, Field(alias="RETRIEVAL_DOCUMENT_RECALL_ENABLED")] = False
    retrieval_document_recall_top_k: Annotated[int, Field(alias="RETRIEVAL_DOCUMENT_RECALL_TOP_K")] = 6
    retrieval_rrf_k: Annotated[int, Field(alias="RETRIEVAL_RRF_K")] = 60
    retrieval_hnsw_ef_search: Annotated[int, Field(alias="RETRIEVAL_HNSW_EF_SEARCH")] = 100
    rerank_provider: Annotated[str, Field(alias="RERANK_PROVIDER")] = "self-hosted"
    rerank_model: Annotated[str, Field(alias="RERANK_MODEL")] = "BAAI/bge-reranker-v2-m3"
    cohere_api_key: Annotated[str | None, Field(alias="COHERE_API_KEY")] = None
    self_hosted_rerank_base_url: Annotated[str | None, Field(alias="SELF_HOSTED_RERANK_BASE_URL")] = (
        "http://easypinex.duckdns.org:8000"
    )
    self_hosted_rerank_api_key: Annotated[str | None, Field(alias="SELF_HOSTED_RERANK_API_KEY")] = None
    self_hosted_rerank_timeout_seconds: Annotated[float, Field(alias="SELF_HOSTED_RERANK_TIMEOUT_SECONDS")] = 60.0
    rerank_top_n: Annotated[int, Field(alias="RERANK_TOP_N")] = 30
    rerank_max_chars_per_doc: Annotated[int, Field(alias="RERANK_MAX_CHARS_PER_DOC")] = 2000
    rerank_retry_on_429_attempts: Annotated[int, Field(alias="RERANK_RETRY_ON_429_ATTEMPTS")] = 4
    rerank_retry_on_429_backoff_seconds: Annotated[float, Field(alias="RERANK_RETRY_ON_429_BACKOFF_SECONDS")] = 16.0
    assembler_max_contexts: Annotated[int, Field(alias="ASSEMBLER_MAX_CONTEXTS")] = 9
    assembler_max_chars_per_context: Annotated[int, Field(alias="ASSEMBLER_MAX_CHARS_PER_CONTEXT")] = 3000
    assembler_max_children_per_parent: Annotated[int, Field(alias="ASSEMBLER_MAX_CHILDREN_PER_PARENT")] = 7
    chat_provider: Annotated[str, Field(alias="CHAT_PROVIDER")] = "deepagents"
    chat_model: Annotated[str, Field(alias="CHAT_MODEL")] = "gpt-5.4"
    chat_max_output_tokens: Annotated[int, Field(alias="CHAT_MAX_OUTPUT_TOKENS")] = 700
    chat_timeout_seconds: Annotated[int, Field(alias="CHAT_TIMEOUT_SECONDS")] = 30
    chat_include_trace: Annotated[bool, Field(alias="CHAT_INCLUDE_TRACE")] = False
    chat_stream_chunk_size: Annotated[int, Field(alias="CHAT_STREAM_CHUNK_SIZE")] = 64
    chat_stream_debug: Annotated[bool, Field(alias="CHAT_STREAM_DEBUG")] = False
    chat_agentic_enabled: Annotated[bool, Field(alias="CHAT_AGENTIC_ENABLED")] = True
    chat_agentic_max_tool_calls_per_turn: Annotated[
        int, Field(alias="CHAT_AGENTIC_MAX_TOOL_CALLS_PER_TURN")
    ] = 6
    chat_agentic_max_query_variant_chars: Annotated[
        int, Field(alias="CHAT_AGENTIC_MAX_QUERY_VARIANT_CHARS")
    ] = 160
    chat_agentic_max_scoped_documents_per_call: Annotated[
        int, Field(alias="CHAT_AGENTIC_MAX_SCOPED_DOCUMENTS_PER_CALL")
    ] = 3
    chat_agentic_max_synopsis_inspections_per_turn: Annotated[
        int, Field(alias="CHAT_AGENTIC_MAX_SYNOPSIS_INSPECTIONS_PER_TURN")
    ] = 2
    chat_agentic_target_latency_seconds: Annotated[
        float, Field(alias="CHAT_AGENTIC_TARGET_LATENCY_SECONDS")
    ] = 20.0
    chat_agentic_max_latency_seconds: Annotated[
        float, Field(alias="CHAT_AGENTIC_MAX_LATENCY_SECONDS")
    ] = 40.0
    summary_compare_eval_judge_model: Annotated[str, Field(alias="SUMMARY_COMPARE_EVAL_JUDGE_MODEL")] = "gpt-5.4-mini"
    summary_compare_eval_max_p95_latency_seconds: Annotated[
        float, Field(alias="SUMMARY_COMPARE_EVAL_MAX_P95_LATENCY_SECONDS")
    ] = 30.0
    summary_compare_eval_max_total_tokens_per_item: Annotated[
        int, Field(alias="SUMMARY_COMPARE_EVAL_MAX_TOTAL_TOKENS_PER_ITEM")
    ] = 12000
    summary_compare_eval_pass_min_avg_score: Annotated[
        float, Field(alias="SUMMARY_COMPARE_EVAL_PASS_MIN_AVG_SCORE")
    ] = 4.2
    langgraph_service_port: Annotated[int, Field(alias="LANGGRAPH_SERVICE_PORT")] = 8000
    langgraph_api_url: Annotated[str, Field(alias="LANGGRAPH_API_URL")] = "http://127.0.0.1:8000"
    langsmith_tracing: Annotated[bool, Field(alias="LANGSMITH_TRACING")] = False
    langsmith_api_key: Annotated[str | None, Field(alias="LANGSMITH_API_KEY")] = None
    langsmith_project: Annotated[str, Field(alias="LANGSMITH_PROJECT")] = "deep-agent-rag-stack"
    langsmith_endpoint: Annotated[str | None, Field(alias="LANGSMITH_ENDPOINT")] = None
    langsmith_workspace_id: Annotated[str | None, Field(alias="LANGSMITH_WORKSPACE_ID")] = None

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
def get_settings() -> AppSettings:
    """回傳快取後的設定物件，確保同一個行程內設定一致。

    參數：
    - 無

    回傳：
    - `AppSettings`：目前行程共用的 API 執行期設定。
    """

    return AppSettings()


def get_app_settings(request: Request) -> AppSettings:
    """從應用程式狀態讀取設定。

    參數：
    - `request`：目前 HTTP request；用來讀取 `app.state.settings`。

    回傳：
    - `AppSettings`：目前 request 所屬應用程式的設定物件。

    前置條件：
    - `app.main.create_app()` 必須已將 `settings` 放入 `app.state`。

    風險：
    - 若繞過此 dependency 直接呼叫 `get_settings()`，測試或多實例情境可能讀到錯誤設定。
    """

    return request.app.state.settings
