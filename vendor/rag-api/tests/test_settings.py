"""API 設定物件測試。"""

from app.core.settings import AppSettings


def test_app_settings_uses_defaults_for_empty_string_env_values(monkeypatch) -> None:
    """空字串環境變數應回退為 API 設定預設值。"""

    monkeypatch.delenv("RERANK_PROVIDER", raising=False)
    monkeypatch.delenv("RERANK_MODEL", raising=False)

    settings = AppSettings(
        _env_file=None,
        MINIO_SECURE="",
        MAX_UPLOAD_SIZE_BYTES="",
        CHUNK_MIN_PARENT_SECTION_LENGTH="",
        CHUNK_TARGET_CHILD_SIZE="",
        CHUNK_CHILD_OVERLAP="",
        CHUNK_CONTENT_PREVIEW_LENGTH="",
        CHUNK_TXT_PARENT_GROUP_SIZE="",
        CHUNK_TABLE_PRESERVE_MAX_CHARS="",
        CHUNK_TABLE_MAX_ROWS_PER_CHILD="",
        OPENROUTER_HTTP_REFERER="",
        OPENROUTER_TITLE="",
        SELF_HOSTED_EMBEDDING_BASE_URL="",
        SELF_HOSTED_EMBEDDING_API_KEY="",
        SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS="",
        RETRIEVAL_DOCUMENT_RECALL_ENABLED="",
        RETRIEVAL_DOCUMENT_RECALL_TOP_K="",
        SELF_HOSTED_RERANK_BASE_URL="",
        SELF_HOSTED_RERANK_API_KEY="",
        SELF_HOSTED_RERANK_TIMEOUT_SECONDS="",
        RERANK_TOP_N="",
        RERANK_MAX_CHARS_PER_DOC="",
        ASSEMBLER_MAX_CONTEXTS="",
        ASSEMBLER_MAX_CHARS_PER_CONTEXT="",
        ASSEMBLER_MAX_CHILDREN_PER_PARENT="",
        CHAT_AGENTIC_MAX_TOOL_CALLS_PER_TURN="",
        CHAT_AGENTIC_MAX_QUERY_VARIANT_CHARS="",
        SUMMARY_COMPARE_EVAL_JUDGE_MODEL="",
        SUMMARY_COMPARE_EVAL_MAX_P95_LATENCY_SECONDS="",
        SUMMARY_COMPARE_EVAL_MAX_TOTAL_TOKENS_PER_ITEM="",
        SUMMARY_COMPARE_EVAL_PASS_MIN_AVG_SCORE="",
    )

    assert settings.minio_secure is False
    assert settings.max_upload_size_bytes == 5 * 1024 * 1024
    assert settings.chunk_min_parent_section_length == 800
    assert settings.chunk_target_child_size == 800
    assert settings.chunk_child_overlap == 120
    assert settings.chunk_content_preview_length == 120
    assert settings.chunk_txt_parent_group_size == 4
    assert settings.chunk_table_preserve_max_chars == 4000
    assert settings.chunk_table_max_rows_per_child == 20
    assert settings.openrouter_http_referer is None
    assert settings.openrouter_title is None
    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.embedding_dimensions == 1536
    assert settings.self_hosted_embedding_base_url is None
    assert settings.self_hosted_embedding_api_key is None
    assert settings.self_hosted_embedding_timeout_seconds == 60.0
    assert settings.retrieval_document_recall_enabled is False
    assert settings.retrieval_document_recall_top_k == 6
    assert settings.rerank_provider == "self-hosted"
    assert settings.rerank_model == "BAAI/bge-reranker-v2-m3"
    assert settings.self_hosted_rerank_base_url == "http://easypinex.duckdns.org:8000"
    assert settings.self_hosted_rerank_api_key is None
    assert settings.self_hosted_rerank_timeout_seconds == 60.0
    assert settings.rerank_top_n == 30
    assert settings.rerank_max_chars_per_doc == 2000
    assert settings.assembler_max_contexts == 9
    assert settings.assembler_max_chars_per_context == 3000
    assert settings.assembler_max_children_per_parent == 7
    assert settings.chat_provider == "deepagents"
    assert settings.chat_model == "gpt-5.4"
    assert settings.chat_agentic_enabled is True
    assert settings.chat_agentic_max_tool_calls_per_turn == 6
    assert settings.chat_agentic_max_query_variant_chars == 160
    assert settings.summary_compare_eval_judge_model == "gpt-5.4-mini"
    assert settings.summary_compare_eval_max_p95_latency_seconds == 30.0
    assert settings.summary_compare_eval_max_total_tokens_per_item == 12000
    assert settings.summary_compare_eval_pass_min_avg_score == 4.2
