"""授權、文件、chunking、retrieval 與 evaluation 使用的 ORM models。"""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.sql_types import build_embedding_type


# 所有主鍵預設使用 UUID 字串，避免在 SQLite 測試與 PostgreSQL 間切換時額外處理型別差異。
UUID_LENGTH = 36


def utc_now() -> datetime:
    """提供 UTC aware 的目前時間。"""

    return datetime.now(UTC)


def generate_uuid() -> str:
    """產生新的 UUID 字串主鍵。"""

    return str(uuid4())


class Role(str, Enum):
    """Knowledge Area 權限角色。"""

    reader = "reader"
    maintainer = "maintainer"
    admin = "admin"


class AreaVisibility(str, Enum):
    """Knowledge Area 可見性層級。"""

    public = "public"
    group = "group"
    private = "private"


class DocumentStatus(str, Enum):
    """文件處理狀態。"""

    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class IngestJobStatus(str, Enum):
    """背景索引工作的最小狀態。"""

    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class ChunkType(str, Enum):
    """文件 chunk 結構型別。"""

    parent = "parent"
    child = "child"


class ChunkStructureKind(str, Enum):
    """文件 chunk 的內容結構型別。"""

    text = "text"
    table = "table"


class EvaluationQueryType(str, Enum):
    """Retrieval evaluation 題型。"""

    fact_lookup = "fact_lookup"
    document_summary = "document_summary"
    cross_document_compare = "cross_document_compare"


class EvaluationLanguage(str, Enum):
    """Retrieval evaluation 查詢語言維度。"""

    zh_tw = "zh-TW"
    en = "en"
    mixed = "mixed"


class EvaluationRunStatus(str, Enum):
    """Retrieval evaluation run 狀態。"""

    running = "running"
    completed = "completed"
    failed = "failed"


class Area(Base):
    """Knowledge Area 基本資料。"""

    __tablename__ = "areas"

    # Area 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # Area 顯示名稱。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Area 補充說明。
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # Area 可見性層級：public = 任何已驗證成員可讀；group = 群組/直接角色；private = 僅直接角色。
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="group", server_default="group")
    # Area 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # Area 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AreaUserRole(Base):
    """Area 與直接使用者角色映射。"""

    __tablename__ = "area_user_roles"
    __table_args__ = (UniqueConstraint("area_id", "user_sub", name="uq_area_user_roles_area_subject"),)

    # 角色映射唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 角色映射所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # 被授權使用者的 `sub`。
    user_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    # 直接指派給使用者的角色。
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False), nullable=False)
    # 角色映射建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AreaGroupRole(Base):
    """Area 與 Keycloak group path 角色映射。"""

    __tablename__ = "area_group_roles"
    __table_args__ = (UniqueConstraint("area_id", "group_path", name="uq_area_group_roles_area_group_path"),)

    # 群組角色映射唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 角色映射所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # 被授權 Keycloak group path。
    group_path: Mapped[str] = mapped_column(String(255), nullable=False)
    # 指派給群組的角色。
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False), nullable=False)
    # 角色映射建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AreaChatSession(Base):
    """Knowledge Area 內 chat session metadata。"""

    __tablename__ = "area_chat_sessions"
    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_area_chat_sessions_thread_id"),
    )

    # session 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # session 所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # 建立此 session 的使用者 `sub`。
    owner_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    # LangGraph thread 識別碼。
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # 前端顯示用 session 標題。
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # session 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # session 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class Document(Base):
    """文件上傳與 ingest 流程使用的文件資料。"""

    __tablename__ = "documents"

    # 文件唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 文件所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # 使用者上傳時的原始檔名。
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 上傳時記錄的 MIME 類型。
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    # 原始檔大小，單位為 bytes。
    file_size: Mapped[int] = mapped_column(nullable=False)
    # 原始檔在物件儲存中的鍵值。
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # 供全文 preview 與 offset 基準使用的完整顯示文字內容。
    display_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # parser 正規化後、供內部解析與 chunking 使用的完整文字內容。
    normalized_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 以全文件 parent coverage 生成的 document-level synopsis 文字。
    synopsis_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # synopsis 對應的 document-level embedding 向量。
    synopsis_embedding: Mapped[list[float] | None] = mapped_column(build_embedding_type(), nullable=True)
    # 文件目前處理狀態。
    status: Mapped[DocumentStatus] = mapped_column(SqlEnum(DocumentStatus, native_enum=False), nullable=False)
    # 最近一次成功完成 chunking 的時間。
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 最近一次成功更新 document synopsis 的時間。
    synopsis_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 文件建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # 文件最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class IngestJob(Base):
    """背景 ingest 工作狀態資料。"""

    __tablename__ = "ingest_jobs"

    # 背景 job 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 此 job 對應的文件識別碼。
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    # job 目前狀態。
    status: Mapped[IngestJobStatus] = mapped_column(SqlEnum(IngestJobStatus, native_enum=False), nullable=False)
    # job 目前執行階段。
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    # job 失敗時的可讀錯誤訊息。
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 本次 job 產生的 parent chunk 數量。
    parent_chunk_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # 本次 job 產生的 child chunk 數量。
    child_chunk_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # job 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # job 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class DocumentChunk(Base):
    """文件 parent-child chunk tree 的持久化資料。"""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "position", name="uq_document_chunks_document_position"),
        UniqueConstraint("document_id", "section_index", "child_index", name="uq_document_chunks_document_section_child"),
    )

    # chunk 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # chunk 所屬文件。
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    # child chunk 對應的 parent chunk；parent 為空值。
    parent_chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
    )
    # chunk 型別。
    chunk_type: Mapped[ChunkType] = mapped_column(SqlEnum(ChunkType, native_enum=False), nullable=False)
    # chunk 內容結構型別。
    structure_kind: Mapped[ChunkStructureKind] = mapped_column(
        SqlEnum(ChunkStructureKind, native_enum=False),
        nullable=False,
        default=ChunkStructureKind.text,
    )
    # chunk 在整份文件中的穩定排序位置。
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    # parent section 順序。
    section_index: Mapped[int] = mapped_column(Integer(), nullable=False)
    # parent 下的 child 順序；parent 本身為空值。
    child_index: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # markdown section 標題；TXT 或無標題時為空值。
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # parent/section 的層級路徑文字；child 預設為空值。
    heading_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 供 section recall 使用的 path-aware section 文字；child 預設為空值。
    section_path_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # section 對應的 heading level；child 或未知時為空值。
    heading_level: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # chunk 原始內容。
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    # 供 UI 與 observability 使用的內容摘要。
    content_preview: Mapped[str] = mapped_column(String(255), nullable=False)
    # chunk 內容長度，單位為字元數。
    char_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    # chunk 在 display_text 內容中的起始 offset。
    start_offset: Mapped[int] = mapped_column(Integer(), nullable=False)
    # chunk 在 display_text 內容中的結束 offset。
    end_offset: Mapped[int] = mapped_column(Integer(), nullable=False)
    # 僅 child chunk 使用的 embedding 向量；parent 固定為空值。
    embedding: Mapped[list[float] | None] = mapped_column(build_embedding_type(), nullable=True)
    # 以 parent/section 為單位生成的 section-level synopsis 文字；child 固定為空值。
    section_synopsis_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # section synopsis 對應的 embedding 向量；child 固定為空值。
    section_synopsis_embedding: Mapped[list[float] | None] = mapped_column(build_embedding_type(), nullable=True)
    # 最近一次成功更新 section synopsis 的時間；child 固定為空值。
    section_synopsis_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # chunk 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # chunk 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class DocumentChunkRegion(Base):
    """PDF chunk 的 SQL-first 頁碼與 bounding box locator。"""

    __tablename__ = "document_chunk_regions"
    __table_args__ = (
        UniqueConstraint("chunk_id", "region_order", name="uq_document_chunk_regions_chunk_order"),
    )

    # region 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 所屬 child chunk。
    chunk_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 所屬頁碼，從 1 開始。
    page_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    # 在同一 chunk 內的穩定順序。
    region_order: Mapped[int] = mapped_column(Integer(), nullable=False)
    # 左邊界座標。
    bbox_left: Mapped[float] = mapped_column(Float(), nullable=False)
    # 下邊界座標。
    bbox_bottom: Mapped[float] = mapped_column(Float(), nullable=False)
    # 右邊界座標。
    bbox_right: Mapped[float] = mapped_column(Float(), nullable=False)
    # 上邊界座標。
    bbox_top: Mapped[float] = mapped_column(Float(), nullable=False)
    # 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RetrievalEvalDataset(Base):
    """Area 範圍內的 retrieval evaluation dataset。"""

    __tablename__ = "retrieval_eval_datasets"

    # Dataset 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # Dataset 所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # Dataset 顯示名稱。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Dataset 對應的 query type。
    query_type: Mapped[EvaluationQueryType] = mapped_column(
        SqlEnum(EvaluationQueryType, native_enum=False),
        nullable=False,
        default=EvaluationQueryType.fact_lookup,
    )
    # 建立此 dataset 的使用者 sub。
    created_by_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    # 目前指定的 baseline run。
    baseline_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("retrieval_eval_runs.id", ondelete="SET NULL", use_alter=True, name="fk_retrieval_eval_datasets_baseline_run"),
        nullable=True,
    )
    # 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class RetrievalEvalItem(Base):
    """Dataset 內單一 retrieval evaluation 題目。"""

    __tablename__ = "retrieval_eval_items"

    # 題目唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 題目所屬 dataset。
    dataset_id: Mapped[str] = mapped_column(ForeignKey("retrieval_eval_datasets.id", ondelete="CASCADE"), nullable=False)
    # 題目對應的 query type。
    query_type: Mapped[EvaluationQueryType] = mapped_column(
        SqlEnum(EvaluationQueryType, native_enum=False),
        nullable=False,
        default=EvaluationQueryType.fact_lookup,
    )
    # 題目查詢文字。
    query_text: Mapped[str] = mapped_column(Text(), nullable=False)
    # 題目語言維度。
    language: Mapped[EvaluationLanguage] = mapped_column(SqlEnum(EvaluationLanguage, native_enum=False), nullable=False)
    # 題目補充說明。
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class RetrievalEvalItemSpan(Base):
    """Retrieval evaluation 題目的 gold source span。"""

    __tablename__ = "retrieval_eval_item_spans"
    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "document_id",
            "start_offset",
            "end_offset",
            "is_retrieval_miss",
            name="uq_retrieval_eval_item_spans_span",
        ),
    )

    # Source span 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 所屬題目。
    item_id: Mapped[str] = mapped_column(ForeignKey("retrieval_eval_items.id", ondelete="CASCADE"), nullable=False)
    # 對應文件；retrieval miss 時可為空值。
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    # span 在 display_text 的起始 offset。
    start_offset: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # span 在 display_text 的結束 offset。
    end_offset: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # 第一版 relevance 僅支援 3/2。
    relevance_grade: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # 是否標記為 retrieval miss。
    is_retrieval_miss: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    # 建立此 span 的使用者 sub。
    created_by_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    # 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class RetrievalEvalRun(Base):
    """單次 retrieval evaluation benchmark run。"""

    __tablename__ = "retrieval_eval_runs"

    # Run 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # Run 所屬 dataset。
    dataset_id: Mapped[str] = mapped_column(ForeignKey("retrieval_eval_datasets.id", ondelete="CASCADE"), nullable=False)
    # 目前 run 狀態。
    status: Mapped[EvaluationRunStatus] = mapped_column(SqlEnum(EvaluationRunStatus, native_enum=False), nullable=False)
    # 本次 run 使用的 baseline run。
    baseline_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("retrieval_eval_runs.id", ondelete="SET NULL", use_alter=True, name="fk_retrieval_eval_runs_baseline_run"),
        nullable=True,
    )
    # 建立此 run 的使用者 sub。
    created_by_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    # 本次 run 評估題數。
    total_items: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # 本次 benchmark 使用的 evaluation profile。
    evaluation_profile: Mapped[str] = mapped_column(String(64), nullable=False, default="production_like_v1")
    # 本次 benchmark 固定下來的設定快照 JSON。
    config_snapshot: Mapped[str] = mapped_column("config_snapshot_json", Text(), nullable=False, default="{}")
    # 錯誤訊息。
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # 完成時間。
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RetrievalEvalRunArtifact(Base):
    """單次 run 的完整 JSON 報表與 baseline compare artifact。"""

    __tablename__ = "retrieval_eval_run_artifacts"

    # Artifact 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 所屬 run。
    run_id: Mapped[str] = mapped_column(ForeignKey("retrieval_eval_runs.id", ondelete="CASCADE"), nullable=False)
    # 完整 benchmark report JSON。
    report_json: Mapped[str] = mapped_column(Text(), nullable=False)
    # 與 baseline run 的 compare JSON。
    baseline_compare_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
