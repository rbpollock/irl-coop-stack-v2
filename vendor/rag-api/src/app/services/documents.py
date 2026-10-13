"""Documents、document chunks、ingest jobs 與全文 preview service。"""

from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import (
    ChunkType,
    Document,
    DocumentChunk,
    DocumentChunkRegion,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    Role,
)
from app.schemas.documents import (
    ChunkSummary,
    DocumentPreviewChunk,
    DocumentPreviewResponse,
    DocumentSummary,
    IngestJobSummary,
)
from app.services.access import require_area_access, require_minimum_area_role
from app.services.storage import ObjectStorage
from app.services.tasks import dispatch_document_ingest


# Phase 3.5 真正支援解析的副檔名。
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}

# 產品範圍內但本 phase 尚未真正處理的副檔名。
RECOGNIZED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx", ".html", ".xlsx"}

# 若瀏覽器沒有帶 content type，退回使用的 MIME 類型。
DEFAULT_TEXT_CONTENT_TYPE = "text/plain"

# parse artifact 儲存目錄名稱。
PARSE_ARTIFACTS_DIRECTORY = "artifacts"


def create_document_upload(
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    storage: ObjectStorage,
    celery_client: Any,
    *,
    area_id: str,
    upload: UploadFile,
) -> tuple[DocumentSummary, IngestJobSummary]:
    """驗證、寫入儲存、建立 document/job，並派送 ingest。

    參數：
    - `session`：用來建立文件與 job 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `storage`：原始檔物件儲存介面。
    - `celery_client`：用來派送 ingest task 的 Celery client。
    - `area_id`：文件所屬 area 識別碼。
    - `upload`：上傳的單一檔案。

    回傳：
    - `tuple[DocumentSummary, IngestJobSummary]`：剛建立的文件與 ingest job 摘要。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)

    file_name, content_type, payload = _read_validated_upload(settings=settings, upload=upload)
    document_id = str(uuid4())
    storage_key = str(PurePosixPath(area_id) / document_id / file_name)
    storage.put_object(object_key=storage_key, payload=payload, content_type=content_type)

    document = Document(
        id=document_id,
        area_id=area_id,
        file_name=file_name,
        content_type=content_type,
        file_size=len(payload),
        storage_key=storage_key,
        display_text=None,
        normalized_text=None,
        synopsis_text=None,
        synopsis_embedding=None,
        status=DocumentStatus.uploaded,
        indexed_at=None,
        synopsis_updated_at=None,
    )
    job = IngestJob(
        document_id=document.id,
        status=IngestJobStatus.queued,
        stage="queued",
        parent_chunk_count=0,
        child_chunk_count=0,
    )
    session.add_all([document, job])
    session.commit()
    session.refresh(document)
    session.refresh(job)
    dispatch_document_ingest(celery_client=celery_client, job_id=job.id)
    return build_document_summary(session=session, document=document), build_ingest_job_summary(
        session=session,
        document=document,
        job=job,
    )


def list_area_documents(session: Session, principal: CurrentPrincipal, *, area_id: str) -> list[DocumentSummary]:
    """列出指定 area 內文件。

    參數：
    - `session`：用來查詢文件的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要查詢的 area 識別碼。

    回傳：
    - `list[DocumentSummary]`：指定 area 內可見的文件清單。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    documents = session.scalars(
        select(Document).where(Document.area_id == area_id).order_by(Document.created_at.desc())
    ).all()
    chunk_summary_by_document_id = _load_chunk_summaries(session=session, document_ids=[document.id for document in documents])
    return [
        build_document_summary(
            session=session,
            document=document,
            chunk_summary=chunk_summary_by_document_id.get(document.id),
        )
        for document in documents
    ]


def get_document_detail(session: Session, principal: CurrentPrincipal, *, document_id: str) -> DocumentSummary:
    """取得單一文件詳情。

    參數：
    - `session`：用來查詢文件的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `document_id`：要查詢的文件識別碼。

    回傳：
    - `DocumentSummary`：指定文件的摘要資料。
    """

    document = session.get(Document, document_id)
    if document is None:
        raise _build_document_not_found_error()
    try:
        require_area_access(session=session, principal=principal, area_id=document.area_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise _build_document_not_found_error() from exc
        raise
    return build_document_summary(session=session, document=document)


def get_document_preview(session: Session, principal: CurrentPrincipal, *, document_id: str) -> DocumentPreviewResponse:
    """取得單一 ready 文件的全文 preview。

    參數：
    - `session`：用來查詢文件與 chunks 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `document_id`：要查詢的文件識別碼。

    回傳：
    - `DocumentPreviewResponse`：指定文件的全文 preview 與 chunk map。

    前置條件：
    - 僅 `status=ready` 且已通過 area access 檢查的文件可讀取全文 preview。
    """

    document = _get_authorized_ready_document_for_preview(session=session, principal=principal, document_id=document_id)
    if not document.display_text:
        raise _build_document_not_found_error()

    chunks = session.scalars(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.chunk_type == ChunkType.child,
        )
        .order_by(DocumentChunk.section_index.asc(), DocumentChunk.child_index.asc(), DocumentChunk.position.asc())
    ).all()
    chunk_ids = [chunk.id for chunk in chunks]
    regions = session.scalars(
        select(DocumentChunkRegion)
        .where(DocumentChunkRegion.chunk_id.in_(chunk_ids))
        .order_by(DocumentChunkRegion.chunk_id.asc(), DocumentChunkRegion.region_order.asc())
    ).all() if chunk_ids else []
    regions_by_chunk_id: dict[str, list[DocumentChunkRegion]] = {}
    for region in regions:
        regions_by_chunk_id.setdefault(region.chunk_id, []).append(region)
    return DocumentPreviewResponse(
        document_id=document.id,
        file_name=document.file_name,
        content_type=document.content_type,
        display_text=document.display_text,
        chunks=[
            DocumentPreviewChunk(
                chunk_id=chunk.id,
                parent_chunk_id=chunk.parent_chunk_id,
                child_index=chunk.child_index,
                heading=chunk.heading,
                structure_kind=chunk.structure_kind,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                page_start=min((region.page_number for region in regions_by_chunk_id.get(chunk.id, [])), default=None),
                page_end=max((region.page_number for region in regions_by_chunk_id.get(chunk.id, [])), default=None),
                regions=[
                    DocumentPreviewChunk.PreviewRegion(
                        page_number=region.page_number,
                        region_order=region.region_order,
                        bbox_left=region.bbox_left,
                        bbox_bottom=region.bbox_bottom,
                        bbox_right=region.bbox_right,
                        bbox_top=region.bbox_top,
                    )
                    for region in regions_by_chunk_id.get(chunk.id, [])
                ],
            )
            for chunk in chunks
        ],
    )


def get_ingest_job_detail(session: Session, principal: CurrentPrincipal, *, job_id: str) -> IngestJobSummary:
    """取得單一 ingest job 詳情。

    參數：
    - `session`：用來查詢 ingest job 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `job_id`：要查詢的 ingest job 識別碼。

    回傳：
    - `IngestJobSummary`：指定 ingest job 的摘要資料。
    """

    job = session.get(IngestJob, job_id)
    if job is None:
        raise _build_job_not_found_error()
    document = session.get(Document, job.document_id)
    if document is None:
        raise _build_job_not_found_error()
    try:
        require_area_access(session=session, principal=principal, area_id=document.area_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise _build_job_not_found_error() from exc
        raise
    return build_ingest_job_summary(session=session, document=document, job=job)


def reindex_document(
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    storage: ObjectStorage,
    celery_client: Any,
    *,
    document_id: str,
    force_reparse: bool = False,
) -> tuple[DocumentSummary, IngestJobSummary]:
    """重新建立既有文件的 ingest job 與 chunk tree。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `storage`：原始檔物件儲存介面。
    - `celery_client`：用來派送 ingest task 的 Celery client。
    - `document_id`：要重建索引的文件識別碼。
    - `force_reparse`：若為真，要求 worker 忽略既有 parse artifacts 並重跑 parser。

    回傳：
    - `tuple[DocumentSummary, IngestJobSummary]`：重建後的文件與新 job 摘要。
    """

    document = _get_authorized_document_for_write(session=session, principal=principal, document_id=document_id)
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    document.status = DocumentStatus.uploaded
    document.display_text = None
    document.normalized_text = None
    document.synopsis_text = None
    document.synopsis_embedding = None
    document.indexed_at = None
    document.synopsis_updated_at = None
    job = IngestJob(
        document_id=document.id,
        status=IngestJobStatus.queued,
        stage="queued",
        parent_chunk_count=0,
        child_chunk_count=0,
    )
    session.add(job)
    session.commit()
    session.refresh(document)
    session.refresh(job)
    dispatch_document_ingest(celery_client=celery_client, job_id=job.id, force_reparse=force_reparse)
    return build_document_summary(session=session, document=document), build_ingest_job_summary(
        session=session,
        document=document,
        job=job,
    )


def delete_document(
    session: Session,
    principal: CurrentPrincipal,
    storage: ObjectStorage,
    *,
    document_id: str,
) -> None:
    """刪除文件、相關 jobs、chunks 與原始檔。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `storage`：原始檔物件儲存介面。
    - `document_id`：要刪除的文件識別碼。

    回傳：
    - `None`：此函式只負責完成刪除流程。
    """

    document = _get_authorized_document_for_write(session=session, principal=principal, document_id=document_id)
    storage.delete_prefix(prefix=_build_parse_artifact_prefix(storage_key=document.storage_key))
    storage.delete_object(object_key=document.storage_key)
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    session.execute(delete(IngestJob).where(IngestJob.document_id == document.id))
    session.delete(document)
    session.commit()


def build_document_summary(
    *,
    session: Session,
    document: Document,
    chunk_summary: ChunkSummary | None = None,
) -> DocumentSummary:
    """將 document model 轉成 API schema。

    參數：
    - `session`：用來查詢 chunk 摘要的資料庫 session。
    - `document`：ORM document model。
    - `chunk_summary`：若已預先查好，直接沿用的 chunk 摘要。

    回傳：
    - `DocumentSummary`：可供 API 回傳的文件摘要資料。
    """

    resolved_chunk_summary = chunk_summary or _build_document_chunk_summary(session=session, document=document)
    return DocumentSummary(
        id=document.id,
        area_id=document.area_id,
        file_name=document.file_name,
        content_type=document.content_type,
        file_size=document.file_size,
        status=document.status,
        chunk_summary=resolved_chunk_summary,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _build_parse_artifact_prefix(*, storage_key: str) -> str:
    """依文件 storage key 建立 parse artifact 的固定前綴路徑。"""

    return str(PurePosixPath(storage_key).parent / PARSE_ARTIFACTS_DIRECTORY)


def build_ingest_job_summary(*, session: Session, document: Document, job: IngestJob) -> IngestJobSummary:
    """將 ingest job model 轉成 API schema。

    參數：
    - `session`：用來查詢 persisted chunk 摘要的資料庫 session。
    - `document`：此 job 對應的 document。
    - `job`：ORM ingest job model。

    回傳：
    - `IngestJobSummary`：可供 API 回傳的 ingest job 摘要資料。
    """

    resolved_chunk_summary = _build_document_chunk_summary(session=session, document=document)
    return IngestJobSummary(
        id=job.id,
        document_id=job.document_id,
        status=job.status,
        stage=job.stage,
        chunk_summary=resolved_chunk_summary,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _build_document_chunk_summary(session: Session, document: Document) -> ChunkSummary:
    """查詢單一文件的 chunk 摘要。

    參數：
    - `session`：用來查詢 document_chunks 的資料庫 session。
    - `document`：要查詢 chunk 摘要的文件。

    回傳：
    - `ChunkSummary`：指定文件的 chunk 摘要資訊。
    """

    return _load_chunk_summaries(session=session, document_ids=[document.id]).get(
        document.id,
        ChunkSummary(
            total_chunks=0,
            parent_chunks=0,
            child_chunks=0,
            mixed_structure_parents=0,
            text_table_text_clusters=0,
            last_indexed_at=document.indexed_at,
        ),
    )


def _load_chunk_summaries(session: Session, *, document_ids: list[str]) -> dict[str, ChunkSummary]:
    """批次查詢多份文件的 chunk 摘要。

    參數：
    - `session`：用來查詢 chunk 資料的資料庫 session。
    - `document_ids`：要查詢的文件識別碼列表。

    回傳：
    - `dict[str, ChunkSummary]`：以 document id 為鍵的 chunk 摘要映射。
    """

    if not document_ids:
        return {}

    documents = {
        document.id: document
        for document in session.scalars(select(Document).where(Document.id.in_(document_ids))).all()
    }
    count_rows = session.execute(
        select(
            DocumentChunk.document_id,
            DocumentChunk.chunk_type,
            func.count(DocumentChunk.id),
        )
        .where(DocumentChunk.document_id.in_(document_ids))
        .group_by(DocumentChunk.document_id, DocumentChunk.chunk_type)
    ).all()

    counts_by_document_id = {document_id: {"parent": 0, "child": 0} for document_id in document_ids}
    for document_id, chunk_type, chunk_count in count_rows:
        chunk_type_key = chunk_type.value if isinstance(chunk_type, ChunkType) else str(chunk_type)
        counts_by_document_id.setdefault(document_id, {"parent": 0, "child": 0})[chunk_type_key] = chunk_count

    child_rows = session.execute(
        select(
            DocumentChunk.document_id,
            DocumentChunk.section_index,
            DocumentChunk.child_index,
            DocumentChunk.structure_kind,
        )
        .where(
            DocumentChunk.document_id.in_(document_ids),
            DocumentChunk.chunk_type == ChunkType.child,
        )
        .order_by(DocumentChunk.document_id.asc(), DocumentChunk.section_index.asc(), DocumentChunk.child_index.asc())
    ).all()
    diagnostics_by_document_id = _build_chunk_summary_diagnostics(child_rows=child_rows, document_ids=document_ids)

    return {
        document_id: ChunkSummary(
            total_chunks=counts["parent"] + counts["child"],
            parent_chunks=counts["parent"],
            child_chunks=counts["child"],
            mixed_structure_parents=diagnostics_by_document_id[document_id]["mixed_structure_parents"],
            text_table_text_clusters=diagnostics_by_document_id[document_id]["text_table_text_clusters"],
            last_indexed_at=documents[document_id].indexed_at if document_id in documents else None,
        )
        for document_id, counts in counts_by_document_id.items()
    }


def _build_chunk_summary_diagnostics(*, child_rows, document_ids: list[str]) -> dict[str, dict[str, int]]:
    """依 persisted child chunks 計算 chunk summary 的觀測指標。

    參數：
    - `child_rows`：child chunk 的 `(document_id, section_index, child_index, structure_kind)` 查詢結果。
    - `document_ids`：要輸出的文件識別碼列表。

    回傳：
    - `dict[str, dict[str, int]]`：每份文件的 mixed parent 與 cluster 計數。
    """

    kinds_by_parent: dict[tuple[str, int], list[str]] = {}
    for document_id, section_index, _child_index, structure_kind in child_rows:
        structure_kind_value = structure_kind.value if hasattr(structure_kind, "value") else str(structure_kind)
        kinds_by_parent.setdefault((document_id, section_index), []).append(structure_kind_value)

    diagnostics_by_document_id = {
        document_id: {
            "mixed_structure_parents": 0,
            "text_table_text_clusters": 0,
        }
        for document_id in document_ids
    }
    for (document_id, _section_index), kinds in kinds_by_parent.items():
        if len(set(kinds)) > 1:
            diagnostics_by_document_id[document_id]["mixed_structure_parents"] += 1
        if kinds == ["text", "table", "text"]:
            diagnostics_by_document_id[document_id]["text_table_text_clusters"] += 1
    return diagnostics_by_document_id


def _get_authorized_document_for_write(session: Session, principal: CurrentPrincipal, *, document_id: str) -> Document:
    """讀取可寫文件並套用 same-404 與最小角色檢查。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `document_id`：目標文件識別碼。

    回傳：
    - `Document`：已通過 maintainter 以上權限檢查的文件。
    """

    document = session.get(Document, document_id)
    if document is None:
        raise _build_document_not_found_error()
    try:
        require_minimum_area_role(
            session=session,
            principal=principal,
            area_id=document.area_id,
            minimum_role=Role.maintainer,
        )
    except HTTPException as exc:
        if exc.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN}:
            raise _build_document_not_found_error() from exc
        raise
    return document


def _get_authorized_ready_document_for_preview(
    session: Session,
    principal: CurrentPrincipal,
    *,
    document_id: str,
) -> Document:
    """讀取可供全文 preview 的 ready 文件，並套用 same-404。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `document_id`：目標文件識別碼。

    回傳：
    - `Document`：已通過存取與 ready 檢查的文件。
    """

    document = session.get(Document, document_id)
    if document is None or document.status != DocumentStatus.ready:
        raise _build_document_not_found_error()
    try:
        require_area_access(session=session, principal=principal, area_id=document.area_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise _build_document_not_found_error() from exc
        raise
    return document


def _read_validated_upload(settings: AppSettings, upload: UploadFile) -> tuple[str, str, bytes]:
    """驗證上傳檔案並回傳標準化資訊。

    參數：
    - `settings`：包含上傳大小限制等設定的應用程式設定。
    - `upload`：待驗證的上傳檔案。

    回傳：
    - `tuple[str, str, bytes]`：標準化後的檔名、content type 與原始位元組內容。
    """

    file_name = (upload.filename or "").strip()
    if not file_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="檔名不可為空。")

    extension = _extract_extension(file_name)
    if extension not in RECOGNIZED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="目前不支援此檔案類型。")

    payload = upload.file.read()
    if not payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="上傳檔案不可為空。")
    if len(payload) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="檔案超過上傳大小限制。")

    content_type = (upload.content_type or DEFAULT_TEXT_CONTENT_TYPE).strip() or DEFAULT_TEXT_CONTENT_TYPE
    return file_name, content_type, payload


def _extract_extension(file_name: str) -> str:
    """取得標準化副檔名。

    參數：
    - `file_name`：待解析副檔名的檔名。

    回傳：
    - `str`：標準化副檔名；若無法識別則回傳空字串。
    """

    lower_name = file_name.lower()
    for extension in sorted(RECOGNIZED_EXTENSIONS, key=len, reverse=True):
        if lower_name.endswith(extension):
            return extension
    return ""


def _build_document_not_found_error() -> HTTPException:
    """建立文件不存在或未授權時共用的 404。

    參數：
    - 無

    回傳：
    - `HTTPException`：用來隱藏文件存在性的 404 例外。
    """

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 document。")


def _build_job_not_found_error() -> HTTPException:
    """建立 ingest job 不存在或未授權時共用的 404。

    參數：
    - 無

    回傳：
    - `HTTPException`：用來隱藏 ingest job 存在性的 404 例外。
    """

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 ingest job。")
