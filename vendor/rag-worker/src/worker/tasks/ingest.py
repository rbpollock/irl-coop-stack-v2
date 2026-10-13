"""文件 ingest、chunking 與狀態轉換。"""

from datetime import UTC, datetime
import logging
from pathlib import PurePosixPath

from sqlalchemy import delete

from worker.celery_app import celery_app
from worker.chunking import ChunkingConfig, ChunkingResult, build_chunk_tree
from worker.core.settings import get_settings
from worker.db import (
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentChunkRegion,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    create_database_engine,
    create_session_factory,
    session_scope,
)
from worker.parsers import (
    ParsedDocument,
    PdfParserConfig,
    get_reusable_parse_artifact_names,
    parse_document,
    parse_document_from_artifact,
)
from worker.storage import StorageError, build_object_storage_reader
from worker.tasks.indexing import index_document_chunks

logger = logging.getLogger(__name__)

# `document_chunks.heading` 欄位的資料庫最大長度。
MAX_CHUNK_HEADING_LENGTH = 255

# `document_chunks.content_preview` 欄位的資料庫最大長度。
MAX_CHUNK_CONTENT_PREVIEW_LENGTH = 255

# parse artifact 儲存目錄名稱。
PARSE_ARTIFACTS_DIRECTORY = "artifacts"


@celery_app.task(name="worker.tasks.ingest.process_document_ingest")
def process_document_ingest(job_id: str, force_reparse: bool = False) -> str:
    """處理單一 ingest job，並更新 document/job/chunks 狀態。

    參數：
    - `job_id`：要處理的 ingest job 識別碼。
    - `force_reparse`：若為真，忽略既有 parse artifacts 並強制重跑 parser。

    回傳：
    - `str`：本次 task 執行結果代碼，例如 `succeeded`、`failed`、`job-skipped`。
    """

    settings = get_settings()
    session_factory = create_session_factory(create_database_engine(settings))
    storage = build_object_storage_reader(settings)
    normalized_job_id = str(job_id)

    with session_scope(session_factory) as session:
        job = session.get(IngestJob, normalized_job_id)
        if job is None:
            return "job-missing"
        if job.status != IngestJobStatus.queued:
            return "job-skipped"

        document = session.get(Document, job.document_id)
        if document is None:
            job.status = IngestJobStatus.failed
            job.stage = "failed"
            job.error_message = "找不到對應的 document。"
            session.commit()
            return "document-missing"
        if document.status != DocumentStatus.uploaded:
            return "document-skipped"

        _mark_processing(session=session, document=document, job=job)
        pdf_provider = settings.pdf_parser_provider if document.file_name.lower().endswith(".pdf") else None

        try:
            job.stage = "parsing"
            session.commit()
            pdf_config = _build_pdf_parser_config(settings)
            parsed_document = None
            if not force_reparse:
                parsed_document = _load_reusable_parsed_document(
                    storage=storage,
                    document=document,
                    pdf_config=pdf_config,
                )
            if parsed_document is None:
                _clear_parse_artifacts(storage=storage, document=document)
                payload = storage.get_object(object_key=document.storage_key)
                parsed_document = parse_document(
                    file_name=document.file_name,
                    payload=payload,
                    pdf_config=pdf_config,
                )
                _persist_parse_artifacts(storage=storage, document=document, parsed_document=parsed_document)
            document.normalized_text = parsed_document.normalized_text
            job.stage = "chunking"
            session.commit()
            chunking_result = build_chunk_tree(
                parsed_document=parsed_document,
                config=_build_chunking_config(settings),
            )
            document.display_text = chunking_result.display_text
            _log_chunking_observability(
                document=document,
                job=job,
                parsed_document=parsed_document,
                chunking_result=chunking_result,
                pdf_provider=pdf_provider,
            )
            _replace_document_chunks(session=session, document=document, chunking_result=chunking_result)
            job.stage = "indexing"
            session.commit()
            index_document_chunks(session=session, document=document, settings=settings)
        except (StorageError, ValueError, UnicodeDecodeError) as exc:
            _mark_failed(
                session=session,
                document=document,
                job=job,
                message=_format_failure_message(message=str(exc), pdf_provider=pdf_provider),
            )
            return "failed"

        _mark_succeeded(session=session, document=document, job=job, chunking_result=chunking_result)
        return "succeeded"


def _mark_processing(*, session, document: Document, job: IngestJob) -> None:
    """將 document 與 job 標記為 processing。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要更新狀態的文件。
    - `job`：要更新狀態的 ingest job。

    回傳：
    - `None`：此函式只負責更新狀態。
    """

    job.status = IngestJobStatus.processing
    job.stage = "processing"
    job.error_message = None
    job.parent_chunk_count = 0
    job.child_chunk_count = 0
    document.status = DocumentStatus.processing
    document.normalized_text = None
    document.display_text = None
    document.synopsis_text = None
    document.synopsis_embedding = None
    document.synopsis_updated_at = None
    session.commit()


def _persist_parse_artifacts(*, storage, document: Document, parsed_document) -> None:
    """將 parse 過程產生的中介 artifact 寫入物件儲存。"""

    for artifact in parsed_document.artifacts:
        storage.put_object(
            object_key=_build_parse_artifact_object_key(
                storage_key=document.storage_key,
                artifact_file_name=artifact.file_name,
            ),
            payload=artifact.payload,
            content_type=artifact.content_type,
        )


def _load_reusable_parsed_document(
    *,
    storage,
    document: Document,
    pdf_config: PdfParserConfig,
) -> ParsedDocument | None:
    """優先從既有 parse artifacts 重建 ParsedDocument，避免重跑 parser。

    參數：
    - `storage`：物件儲存介面。
    - `document`：目前處理中的文件。
    - `pdf_config`：PDF parser provider 設定。

    回傳：
    - `ParsedDocument | None`：若找到可重用 artifact 則回傳 ParsedDocument，否則回傳空值。
    """

    artifact_names = get_reusable_parse_artifact_names(file_name=document.file_name, pdf_config=pdf_config)
    for artifact_name in artifact_names:
        artifact_object_key = _build_parse_artifact_object_key(
            storage_key=document.storage_key,
            artifact_file_name=artifact_name,
        )
        try:
            artifact_payload = storage.get_object(object_key=artifact_object_key)
        except StorageError:
            continue
        return parse_document_from_artifact(
            file_name=document.file_name,
            artifact_file_name=artifact_name,
            payload=artifact_payload,
            pdf_config=pdf_config,
        )
    return None


def _clear_parse_artifacts(*, storage, document: Document) -> None:
    """清除同一文件既有的 parse artifacts，避免 reindex 殘留舊檔。"""

    storage.delete_prefix(prefix=_build_parse_artifact_prefix(storage_key=document.storage_key))


def _build_parse_artifact_object_key(*, storage_key: str, artifact_file_name: str) -> str:
    """依文件 storage key 建立 parse artifact 的固定儲存路徑。"""

    return str(PurePosixPath(storage_key).parent / PARSE_ARTIFACTS_DIRECTORY / artifact_file_name)


def _build_parse_artifact_prefix(*, storage_key: str) -> str:
    """依文件 storage key 建立 parse artifact 的固定前綴路徑。"""

    return str(PurePosixPath(storage_key).parent / PARSE_ARTIFACTS_DIRECTORY)


def _replace_document_chunks(*, session, document: Document, chunking_result: ChunkingResult) -> None:
    """以 replace-all 方式重建文件 chunks。

    參數：
    - `session`：目前資料庫 session。
    - `document`：本次要重建 chunks 的文件。
    - `chunking_result`：已建立完成的 chunk tree 草稿。

    回傳：
    - `None`：此函式只負責刪除舊 chunks 並寫入新 chunks。
    """

    parent_id_by_section: dict[int, str] = {}
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

    for draft in chunking_result.parent_chunks:
        chunk = DocumentChunk(
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.parent,
            structure_kind=ChunkStructureKind(draft.structure_kind),
            position=draft.position,
            section_index=draft.section_index,
            child_index=None,
            heading=_sanitize_chunk_heading(draft.heading),
            heading_path=draft.heading_path,
            section_path_text=draft.section_path_text,
            heading_level=draft.heading_level,
            content=draft.content,
            content_preview=_sanitize_content_preview(draft.content_preview),
            char_count=draft.char_count,
            start_offset=draft.start_offset,
            end_offset=draft.end_offset,
        )
        session.add(chunk)
        session.flush()
        parent_id_by_section[draft.section_index] = chunk.id

    for draft in chunking_result.child_chunks:
        chunk = DocumentChunk(
            document_id=document.id,
            parent_chunk_id=parent_id_by_section[draft.section_index],
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind(draft.structure_kind),
            position=draft.position,
            section_index=draft.section_index,
            child_index=draft.child_index,
            heading=_sanitize_chunk_heading(draft.heading),
            heading_path=draft.heading_path,
            section_path_text=draft.section_path_text,
            heading_level=draft.heading_level,
            content=draft.content,
            content_preview=_sanitize_content_preview(draft.content_preview),
            char_count=draft.char_count,
            start_offset=draft.start_offset,
            end_offset=draft.end_offset,
        )
        session.add(chunk)
        session.flush()
        if draft.regions:
            for region in draft.regions:
                session.add(
                    DocumentChunkRegion(
                        chunk_id=chunk.id,
                        page_number=region.page_number,
                        region_order=region.region_order,
                        bbox_left=region.bbox_left,
                        bbox_bottom=region.bbox_bottom,
                        bbox_right=region.bbox_right,
                        bbox_top=region.bbox_top,
                    )
                )

    session.flush()


def _sanitize_chunk_heading(heading: str | None) -> str | None:
    """將 chunk heading 裁切到資料庫欄位可接受的長度。

    參數：
    - `heading`：chunk 草稿上的 heading。

    回傳：
    - `str | None`：可安全寫入資料庫的 heading；若原值為空則回傳空值。
    """

    if heading is None:
        return None
    return heading[:MAX_CHUNK_HEADING_LENGTH]


def _sanitize_content_preview(content_preview: str) -> str:
    """將 chunk 摘要裁切到資料庫欄位可接受的長度。

    參數：
    - `content_preview`：chunk 草稿上的摘要文字。

    回傳：
    - `str`：可安全寫入資料庫的摘要文字。
    """

    return content_preview[:MAX_CHUNK_CONTENT_PREVIEW_LENGTH]


def _mark_failed(*, session, document: Document, job: IngestJob, message: str) -> None:
    """將 document 與 job 標為 failed，並清掉殘留 chunks。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要標記失敗的文件。
    - `job`：要標記失敗的 ingest job。
    - `message`：可讀失敗原因。

    回傳：
    - `None`：此函式只負責更新失敗狀態。
    """

    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    job.status = IngestJobStatus.failed
    job.stage = "failed"
    job.error_message = message
    job.parent_chunk_count = 0
    job.child_chunk_count = 0
    document.status = DocumentStatus.failed
    document.normalized_text = None
    document.display_text = None
    document.indexed_at = None
    session.commit()


def _mark_succeeded(*, session, document: Document, job: IngestJob, chunking_result: ChunkingResult) -> None:
    """將 document 與 job 標為成功完成 chunking。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要標記完成的文件。
    - `job`：要標記完成的 ingest job。
    - `chunking_result`：本次產生的 chunk tree 草稿。

    回傳：
    - `None`：此函式只負責更新成功狀態。
    """

    indexed_at = datetime.now(UTC)
    job.stage = "finalizing"
    job.parent_chunk_count = len(chunking_result.parent_chunks)
    job.child_chunk_count = len(chunking_result.child_chunks)
    session.flush()
    job.status = IngestJobStatus.succeeded
    job.stage = "succeeded"
    job.error_message = None
    document.status = DocumentStatus.ready
    document.indexed_at = indexed_at
    session.commit()


def _log_chunking_observability(
    *,
    document: Document,
    job: IngestJob,
    parsed_document,
    chunking_result: ChunkingResult,
    pdf_provider: str | None,
) -> None:
    """記錄 ingest/chunking 的觀測資訊，方便診斷 PDF 路徑。

    參數：
    - `document`：目前處理中的文件。
    - `job`：目前 ingest job。
    - `parsed_document`：parser 產出的標準化文件。
    - `chunking_result`：chunking 結果。
    - `pdf_provider`：若為 PDF，實際使用的 provider。

    回傳：
    - `None`：此函式只負責輸出 log。
    """

    diagnostics = _collect_chunking_diagnostics(chunking_result=chunking_result)
    logger.info(
        "ingest chunking completed file=%s job_id=%s source_format=%s pdf_provider=%s parent_chunks=%s child_chunks=%s text_table_text_clusters=%s mixed_structure_parents=%s",
        document.file_name,
        job.id,
        parsed_document.source_format,
        pdf_provider or "n/a",
        len(chunking_result.parent_chunks),
        len(chunking_result.child_chunks),
        diagnostics["text_table_text_clusters"],
        diagnostics["mixed_structure_parents"],
    )


def _collect_chunking_diagnostics(*, chunking_result: ChunkingResult) -> dict[str, int]:
    """彙整 chunk tree 的最小診斷資訊。

    參數：
    - `chunking_result`：已建立完成的 chunk tree。

    回傳：
    - `dict[str, int]`：供 log 與觀測使用的診斷計數。
    """

    child_kinds_by_section: dict[int, list[str]] = {}
    for child in chunking_result.child_chunks:
        child_kinds_by_section.setdefault(child.section_index, []).append(child.structure_kind)

    mixed_structure_parents = 0
    text_table_text_clusters = 0
    for kinds in child_kinds_by_section.values():
        unique_kinds = set(kinds)
        if len(unique_kinds) > 1:
            mixed_structure_parents += 1
        if kinds == ["text", "table", "text"]:
            text_table_text_clusters += 1

    return {
        "mixed_structure_parents": mixed_structure_parents,
        "text_table_text_clusters": text_table_text_clusters,
    }


def _format_failure_message(*, message: str, pdf_provider: str | None) -> str:
    """在失敗訊息中補上 PDF parser 路徑，方便從 DB 直接診斷。

    參數：
    - `message`：原始可讀失敗訊息。
    - `pdf_provider`：若為 PDF，實際使用的 provider。

    回傳：
    - `str`：補上 provider 前綴後的失敗訊息。
    """

    if not pdf_provider:
        return message
    return f"[pdf_provider={pdf_provider}] {message}"


def _build_chunking_config(settings) -> ChunkingConfig:
    """將 worker 設定物件映射為 chunking 參數。

    參數：
    - `settings`：目前 worker 執行期設定。

    回傳：
    - `ChunkingConfig`：供 chunking 流程使用的參數物件。
    """

    return ChunkingConfig(
        min_parent_section_length=settings.chunk_min_parent_section_length,
        target_child_chunk_size=settings.chunk_target_child_size,
        child_chunk_overlap=settings.chunk_child_overlap,
        content_preview_length=settings.chunk_content_preview_length,
        txt_parent_group_size=settings.chunk_txt_parent_group_size,
        table_preserve_max_chars=settings.chunk_table_preserve_max_chars,
        table_max_rows_per_child=settings.chunk_table_max_rows_per_child,
        fact_heavy_refinement_enabled=settings.chunk_fact_heavy_refinement_enabled,
    )


def _build_pdf_parser_config(settings) -> PdfParserConfig:
    """將 worker 設定物件映射為 PDF parser 參數。

    參數：
    - `settings`：目前 worker 執行期設定。

    回傳：
    - `PdfParserConfig`：供 PDF parser provider 使用的參數物件。
    """

    return PdfParserConfig(
        provider=settings.pdf_parser_provider,
        opendataloader_use_struct_tree=settings.opendataloader_use_struct_tree,
        opendataloader_quiet=settings.opendataloader_quiet,
        llamaparse_api_key=settings.llamaparse_api_key,
        llamaparse_do_not_cache=settings.llamaparse_do_not_cache,
        llamaparse_merge_continued_tables=settings.llamaparse_merge_continued_tables,
    )
