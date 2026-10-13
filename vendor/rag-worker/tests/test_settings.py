"""Worker 設定物件測試。"""

from worker.core.settings import WorkerSettings


def test_worker_settings_uses_defaults_for_empty_string_env_values() -> None:
    """空字串環境變數應回退為 worker 設定預設值。"""

    settings = WorkerSettings(
        _env_file=None,
        MINIO_SECURE="",
        CELERY_WORKER_POOL="",
        CELERY_WORKER_CONCURRENCY="",
        CELERY_WORKER_PREFETCH_MULTIPLIER="",
        CELERY_WORKER_MAX_TASKS_PER_CHILD="",
        CELERY_TASK_ACKS_LATE="",
        CELERY_TASK_REJECT_ON_WORKER_LOST="",
        CHUNK_MIN_PARENT_SECTION_LENGTH="",
        CHUNK_TARGET_CHILD_SIZE="",
        CHUNK_CHILD_OVERLAP="",
        CHUNK_CONTENT_PREVIEW_LENGTH="",
        CHUNK_TXT_PARENT_GROUP_SIZE="",
        CHUNK_TABLE_PRESERVE_MAX_CHARS="",
        CHUNK_TABLE_MAX_ROWS_PER_CHILD="",
        EMBEDDING_MAX_BATCH_TEXTS="",
        EMBEDDING_RETRY_MAX_ATTEMPTS="",
        EMBEDDING_RETRY_BASE_DELAY_SECONDS="",
        SELF_HOSTED_EMBEDDING_BASE_URL="",
        SELF_HOSTED_EMBEDDING_API_KEY="",
        SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS="",
        DOCUMENT_SYNOPSIS_PROVIDER="",
        DOCUMENT_SYNOPSIS_MODEL="",
        DOCUMENT_SYNOPSIS_MAX_INPUT_CHARS="",
        DOCUMENT_SYNOPSIS_MAX_OUTPUT_CHARS="",
        DOCUMENT_SYNOPSIS_MAX_OUTPUT_TOKENS="",
        DOCUMENT_SYNOPSIS_PARALLELISM="",
        DOCUMENT_SYNOPSIS_REASONING_EFFORT="",
        DOCUMENT_SYNOPSIS_TEXT_VERBOSITY="",
        OPENROUTER_HTTP_REFERER="",
        OPENROUTER_TITLE="",
        OPENDATALOADER_USE_STRUCT_TREE="",
        OPENDATALOADER_QUIET="",
        LLAMAPARSE_DO_NOT_CACHE="",
        LLAMAPARSE_MERGE_CONTINUED_TABLES="",
    )

    assert settings.minio_secure is False
    assert settings.worker_pool == "solo"
    assert settings.worker_concurrency == 1
    assert settings.worker_prefetch_multiplier == 1
    assert settings.worker_max_tasks_per_child == 1
    assert settings.task_acks_late is True
    assert settings.task_reject_on_worker_lost is True
    assert settings.chunk_min_parent_section_length == 800
    assert settings.chunk_target_child_size == 800
    assert settings.chunk_child_overlap == 120
    assert settings.chunk_content_preview_length == 120
    assert settings.chunk_txt_parent_group_size == 4
    assert settings.chunk_table_preserve_max_chars == 4000
    assert settings.chunk_table_max_rows_per_child == 20
    assert settings.embedding_max_batch_texts == 64
    assert settings.embedding_retry_max_attempts == 3
    assert settings.embedding_retry_base_delay_seconds == 2.0
    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.embedding_dimensions == 1536
    assert settings.openrouter_http_referer is None
    assert settings.openrouter_title is None
    assert settings.self_hosted_embedding_base_url is None
    assert settings.self_hosted_embedding_api_key is None
    assert settings.self_hosted_embedding_timeout_seconds == 60.0
    assert settings.document_synopsis_provider == "openai"
    assert settings.document_synopsis_model == "gpt-5.4-mini"
    assert settings.document_synopsis_max_input_chars == 6000
    assert settings.document_synopsis_max_output_chars == 1600
    assert settings.document_synopsis_max_output_tokens == 2000
    assert settings.document_synopsis_parallelism == 6
    assert settings.document_synopsis_reasoning_effort == "low"
    assert settings.document_synopsis_text_verbosity == "low"
    assert settings.opendataloader_use_struct_tree is True
    assert settings.opendataloader_quiet is True
    assert settings.llamaparse_do_not_cache is True
    assert settings.llamaparse_merge_continued_tables is False
