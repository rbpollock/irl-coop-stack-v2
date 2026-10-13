"""Retrieval evaluation dataset、review 與 run API schema。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.db.models import EvaluationLanguage, EvaluationQueryType, EvaluationRunStatus
from app.evaluation.retrieval.profiles import (
    DETERMINISTIC_GATE_V1,
    GENERIC_GUARDED_ASSEMBLER_V1,
    GENERIC_GUARDED_ASSEMBLER_V1_GATE,
    GENERIC_GUARDED_ASSEMBLER_V2,
    GENERIC_GUARDED_ASSEMBLER_V2_GATE,
    PRODUCTION_LIKE_V1,
)


class EvaluationProfile(str, Enum):
    """Retrieval evaluation profile 正式型別。"""

    production_like_v1 = PRODUCTION_LIKE_V1
    deterministic_gate_v1 = DETERMINISTIC_GATE_V1
    generic_guarded_assembler_v1 = GENERIC_GUARDED_ASSEMBLER_V1
    generic_guarded_assembler_v2 = GENERIC_GUARDED_ASSEMBLER_V2
    generic_guarded_assembler_v1_gate = GENERIC_GUARDED_ASSEMBLER_V1_GATE
    generic_guarded_assembler_v2_gate = GENERIC_GUARDED_ASSEMBLER_V2_GATE


class CreateEvaluationDatasetRequest(BaseModel):
    """建立 retrieval evaluation dataset 的請求 payload。"""

    name: str = Field(min_length=1, max_length=255)
    query_type: EvaluationQueryType = EvaluationQueryType.fact_lookup

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """拒絕只有空白的 dataset 名稱。

        參數：
        - `value`：原始輸入名稱。

        回傳：
        - `str`：去除首尾空白後的名稱。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("dataset 名稱不可為空白。")
        return stripped


class CreateEvaluationItemRequest(BaseModel):
    """建立 retrieval evaluation 題目的請求 payload。"""

    query_text: str = Field(min_length=1)
    language: EvaluationLanguage
    query_type: EvaluationQueryType | None = None
    notes: str | None = None

    @field_validator("query_text")
    @classmethod
    def validate_query_text(cls, value: str) -> str:
        """拒絕只有空白的 query。

        參數：
        - `value`：原始 query 文字。

        回傳：
        - `str`：清理後的 query。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("query_text 不可為空白。")
        return stripped


class MarkEvaluationSpanRequest(BaseModel):
    """新增 gold source span 的請求 payload。"""

    document_id: UUID
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    relevance_grade: int = Field()

    @field_validator("relevance_grade")
    @classmethod
    def validate_relevance_grade(cls, value: int) -> int:
        """限制 relevance 僅支援 2 或 3。

        參數：
        - `value`：使用者指定的 relevance。

        回傳：
        - `int`：驗證通過的 relevance。
        """

        if value not in {2, 3}:
            raise ValueError("relevance_grade 只支援 2 或 3。")
        return value

    @field_validator("end_offset")
    @classmethod
    def validate_offsets(cls, value: int, info) -> int:
        """確保結束 offset 大於起始 offset。

        參數：
        - `value`：結束 offset。
        - `info`：Pydantic validator context。

        回傳：
        - `int`：驗證通過的結束 offset。
        """

        start_offset = info.data.get("start_offset", 0)
        if value <= start_offset:
            raise ValueError("end_offset 必須大於 start_offset。")
        return value


class RunEvaluationDatasetRequest(BaseModel):
    """執行 benchmark run 的請求 payload。"""

    top_k: int = Field(default=10, ge=1, le=20)
    evaluation_profile: EvaluationProfile = EvaluationProfile.production_like_v1


class EvaluationDatasetSummary(BaseModel):
    """Retrieval evaluation dataset 摘要。"""

    model_config = {"from_attributes": True}

    id: UUID
    area_id: UUID
    name: str
    query_type: EvaluationQueryType
    baseline_run_id: UUID | None
    created_by_sub: str
    created_at: datetime
    updated_at: datetime
    item_count: int


class EvaluationDatasetListResponse(BaseModel):
    """指定 area 的 dataset 清單。"""

    items: list[EvaluationDatasetSummary]


class EvaluationItemSpanResponse(BaseModel):
    """單一 gold span 回應。"""

    model_config = {"from_attributes": True}

    id: UUID
    document_id: UUID | None
    start_offset: int
    end_offset: int
    relevance_grade: int | None
    is_retrieval_miss: bool
    created_by_sub: str
    created_at: datetime


class EvaluationItemSummary(BaseModel):
    """單一 evaluation 題目摘要。"""

    model_config = {"from_attributes": True}

    id: UUID
    dataset_id: UUID
    query_type: EvaluationQueryType
    query_text: str
    language: EvaluationLanguage
    notes: str | None
    created_at: datetime
    updated_at: datetime
    spans: list[EvaluationItemSpanResponse]


class EvaluationDocumentSearchHit(BaseModel):
    """文件內搜尋命中的簡化結果。"""

    document_id: UUID
    document_name: str
    chunk_id: UUID
    heading: str | None
    start_offset: int
    end_offset: int
    excerpt: str


class EvaluationStageCandidate(BaseModel):
    """單一階段候選結果。"""

    document_id: UUID
    document_name: str
    parent_chunk_id: UUID | None
    child_chunk_ids: list[UUID]
    heading: str | None
    start_offset: int
    end_offset: int
    excerpt: str
    source: str
    rank: int
    vector_rank: int | None = None
    fts_rank: int | None = None
    rrf_rank: int | None = None
    rerank_rank: int | None = None
    matched_relevance: int | None


class EvaluationCandidateStageResponse(BaseModel):
    """單一評估階段回應。"""

    stage: str
    first_hit_rank: int | None
    full_hit_rank: int | None = None
    # 是否已成功套用 rerank provider；非 rerank stage 時固定為空值。
    rerank_applied: bool | None = None
    # rerank fail-open 的原因；非 rerank stage 或未 fallback 時固定為空值。
    fallback_reason: str | None = None
    items: list[EvaluationStageCandidate]


class EvaluationQueryRoutingDetail(BaseModel):
    """單題 query routing 明細。"""

    query_type: EvaluationQueryType
    language: str
    confidence: float
    source: str
    matched_rules: list[str]
    query_type_rule_hits: list[dict[str, object]] = []
    query_type_embedding_scores: list[dict[str, object]] = []
    query_type_top_label: str | None = None
    query_type_runner_up_label: str | None = None
    query_type_embedding_margin: float = 0.0
    query_type_fallback_used: bool = False
    query_type_fallback_reason: str | None = None
    summary_scope: str | None = None
    summary_strategy: str | None = None
    summary_strategy_source: str = "not_applicable"
    summary_strategy_confidence: float = 0.0
    summary_strategy_rule_hits: list[dict[str, object]] = []
    summary_strategy_embedding_scores: list[dict[str, object]] = []
    summary_strategy_top_label: str | None = None
    summary_strategy_runner_up_label: str | None = None
    summary_strategy_embedding_margin: float = 0.0
    summary_strategy_fallback_used: bool = False
    summary_strategy_fallback_reason: str | None = None
    resolved_document_ids: list[str]
    document_mention_source: str
    document_mention_confidence: float
    document_mention_candidates: list[dict[str, object]]
    selected_profile: str
    resolved_settings: dict[str, object]


class EvaluationSelectionDetail(BaseModel):
    """單題 diversified selection 明細。"""

    applied: bool
    strategy: str
    selected_document_count: int
    selected_parent_count: int
    selected_document_ids: list[str]
    selected_parent_ids: list[str]
    dropped_by_diversity: list[dict[str, object]]


class EvaluationCandidatePreviewResponse(BaseModel):
    """人工複核用 candidate preview 回應。"""

    dataset: EvaluationDatasetSummary
    item: EvaluationItemSummary
    query_routing: EvaluationQueryRoutingDetail
    selection: EvaluationSelectionDetail | None = None
    recall: EvaluationCandidateStageResponse
    rerank: EvaluationCandidateStageResponse
    assembled: EvaluationCandidateStageResponse
    document_search_hits: list[EvaluationDocumentSearchHit]


class EvaluationPreviewDebugRequest(BaseModel):
    """單題 preview 的臨時調參請求。"""

    top_k: int = Field(default=20, ge=1, le=300)
    retrieval_vector_top_k: int | None = Field(default=None, ge=1, le=300)
    retrieval_fts_top_k: int | None = Field(default=None, ge=1, le=300)
    retrieval_max_candidates: int | None = Field(default=None, ge=1, le=300)
    rerank_top_n: int | None = Field(default=None, ge=1, le=300)
    apply_rerank: bool = True


class EvaluationStageMetricSummary(BaseModel):
    """單一 stage 的 summary metrics。"""

    nDCG_at_k: float
    recall_at_k: float
    mrr_at_k: float
    precision_at_k: float
    document_coverage_at_k: float


class EvaluationSummaryByDimension(BaseModel):
    """依維度切分的 metrics。"""

    dimension: str
    value: str
    metrics: dict[str, EvaluationStageMetricSummary]


class EvaluationPerQueryStageDetail(BaseModel):
    """單題單階段明細。"""

    first_hit_rank: int | None
    matched_core_evidence: bool
    matched_relevance: int | None
    # 是否已成功套用 rerank provider；非 rerank stage 時固定為空值。
    rerank_applied: bool | None = None
    # rerank fail-open 的原因；非 rerank stage 或未 fallback 時固定為空值。
    fallback_reason: str | None = None


class EvaluationPerQueryDetail(BaseModel):
    """單題 benchmark 詳細結果。"""

    item_id: UUID
    query_text: str
    language: EvaluationLanguage
    retrieval_miss: bool
    gold_spans: list[EvaluationItemSpanResponse]
    query_routing: EvaluationQueryRoutingDetail
    # benchmark-only 文件範圍；特定外部資料集會用 gold document id 模擬原始指定文件上下文。
    benchmark_document_scope: dict[str, object] | None = None
    selection: EvaluationSelectionDetail | None = None
    recall: EvaluationPerQueryStageDetail
    rerank: EvaluationPerQueryStageDetail
    assembled: EvaluationPerQueryStageDetail
    baseline_delta: dict[str, float | None]


class EvaluationRunSummary(BaseModel):
    """單次 benchmark run 摘要。"""

    model_config = {"from_attributes": True}

    id: UUID
    dataset_id: UUID
    status: EvaluationRunStatus
    baseline_run_id: UUID | None
    created_by_sub: str
    total_items: int
    evaluation_profile: EvaluationProfile
    config_snapshot: dict[str, object]
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class EvaluationRunReportResponse(BaseModel):
    """Benchmark run 完整報表。"""

    run: EvaluationRunSummary
    dataset: EvaluationDatasetSummary
    summary_metrics: dict[str, EvaluationStageMetricSummary]
    breakdowns: list[EvaluationSummaryByDimension]
    per_query: list[EvaluationPerQueryDetail]
    baseline_compare: dict[str, object] | None


class EvaluationDatasetDetailResponse(BaseModel):
    """Dataset 詳細資料。"""

    dataset: EvaluationDatasetSummary
    items: list[EvaluationItemSummary]
    runs: list[EvaluationRunSummary]
