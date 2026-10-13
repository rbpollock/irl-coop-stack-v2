"""Documents、ingest jobs 與全文 preview API schema。"""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel

from app.db.models import ChunkStructureKind, DocumentStatus, IngestJobStatus


class ChunkSummary(BaseModel):
    """文件或 ingest job 的 chunk 摘要資訊。"""

    # chunk 總數。
    total_chunks: int
    # parent chunk 數量。
    parent_chunks: int
    # child chunk 數量。
    child_chunks: int
    # 由多種 child 結構組成的 parent 數量。
    mixed_structure_parents: int
    # child 順序為 `text/table/text` 的 parent 數量。
    text_table_text_clusters: int
    # 最近一次成功完成 indexing 的時間。
    last_indexed_at: datetime | None


class DocumentSummary(BaseModel):
    """文件摘要資料。"""

    model_config = {"from_attributes": True}

    # 文件唯一識別碼。
    id: UUID
    # 文件所屬 Knowledge Area 識別碼。
    area_id: UUID
    # 使用者上傳時的原始檔名。
    file_name: str
    # 上傳時記錄的 MIME 類型。
    content_type: str
    # 原始檔案大小，單位為 bytes。
    file_size: int
    # 文件目前處理狀態。
    status: DocumentStatus
    # 文件 chunking 結果摘要。
    chunk_summary: ChunkSummary
    # 文件建立時間。
    created_at: datetime
    # 文件最後更新時間。
    updated_at: datetime


class IngestJobSummary(BaseModel):
    """背景 ingest job 摘要資料。"""

    model_config = {"from_attributes": True}

    # 背景 job 唯一識別碼。
    id: UUID
    # 此 job 對應的文件識別碼。
    document_id: UUID
    # job 目前狀態。
    status: IngestJobStatus
    # job 目前執行階段。
    stage: str
    # 本次 job 產生或觀測到的 chunk 摘要。
    chunk_summary: ChunkSummary
    # job 失敗時記錄的可讀錯誤訊息。
    error_message: str | None
    # job 建立時間。
    created_at: datetime
    # job 最後更新時間。
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """指定 area 的文件清單。"""

    # 目前使用者在指定 area 可見的文件列表。
    items: list[DocumentSummary]


class UploadDocumentResponse(BaseModel):
    """文件上傳成功後回傳的 document 與 job。"""

    # 剛建立的文件摘要。
    document: DocumentSummary
    # 與本次上傳對應的 ingest job 摘要。
    job: IngestJobSummary


class ReindexDocumentResponse(BaseModel):
    """文件重建索引後回傳的 document 與 job。"""

    # 重新派送後的文件摘要。
    document: DocumentSummary
    # 新建立的 ingest job 摘要。
    job: IngestJobSummary


class DocumentPreviewChunk(BaseModel):
    """全文 preview 使用的 child chunk 邊界資料。"""

    class PreviewRegion(BaseModel):
        """單一 child chunk 的 PDF locator。"""

        # 所屬頁碼。
        page_number: int
        # 同一 chunk 內的區域順序。
        region_order: int
        # 左邊界座標。
        bbox_left: float
        # 下邊界座標。
        bbox_bottom: float
        # 右邊界座標。
        bbox_right: float
        # 上邊界座標。
        bbox_top: float

    # chunk 唯一識別碼。
    chunk_id: UUID
    # chunk 所屬 parent chunk 識別碼。
    parent_chunk_id: UUID | None
    # parent 下 child 順序。
    child_index: int | None
    # chunk 所屬 heading。
    heading: str | None
    # chunk 內容結構型別。
    structure_kind: ChunkStructureKind
    # chunk 在全文 display_text 的起始 offset。
    start_offset: int
    # chunk 在全文 display_text 的結束 offset。
    end_offset: int
    # chunk 涵蓋的起始頁碼。
    page_start: int | None = None
    # chunk 涵蓋的結束頁碼。
    page_end: int | None = None
    # chunk 關聯的 PDF locator。
    regions: list[PreviewRegion] = []


class DocumentPreviewResponse(BaseModel):
    """全文 preview API 回傳內容。"""

    # 文件唯一識別碼。
    document_id: UUID
    # 使用者上傳時的原始檔名。
    file_name: str
    # 上傳時記錄的 MIME 類型。
    content_type: str
    # 供全文 preview 與 offset 基準使用的完整顯示文字內容。
    display_text: str
    # 依 child chunk 排序的全文 chunk map。
    chunks: list[DocumentPreviewChunk]
