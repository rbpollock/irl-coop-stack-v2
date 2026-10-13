"""Phase 8A summary/compare checkpoint 的 fixture 與報表資料契約。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.chat.contracts.types import ChatAnswerBlock, ChatCitation, ChatTrace
from app.db.models import EvaluationLanguage, EvaluationQueryType


class SummaryCompareGoldSpanRef(BaseModel):
    """單一 gold evidence 參照。"""

    # 目標文件檔名。
    file_name: str = Field(min_length=1)
    # 若使用 quote-first 對齊，提供可在 display_text 中搜尋的片段。
    quote: str | None = None
    # 若已知固定 offset，可直接提供起始位置。
    start_offset: int | None = Field(default=None, ge=0)
    # 若已知固定 offset，可直接提供結束位置。
    end_offset: int | None = Field(default=None, gt=0)

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        """清理檔名欄位。

        參數：
        - `value`：原始檔名字串。

        回傳：
        - `str`：去除首尾空白後的檔名。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("gold_span_refs.file_name 不可為空白。")
        return stripped

    @field_validator("quote")
    @classmethod
    def validate_quote(cls, value: str | None) -> str | None:
        """清理 quote 欄位。

        參數：
        - `value`：原始 quote。

        回傳：
        - `str | None`：清理後的 quote。
        """

        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("end_offset")
    @classmethod
    def validate_offsets(cls, value: int | None, info) -> int | None:
        """驗證 offset 區間是否合法。

        參數：
        - `value`：結束 offset。
        - `info`：validator context。

        回傳：
        - `int | None`：驗證通過的結束 offset。
        """

        start_offset = info.data.get("start_offset")
        if value is not None and start_offset is not None and value <= start_offset:
            raise ValueError("gold_span_refs.end_offset 必須大於 start_offset。")
        return value


class SummaryCompareCheckpointItem(BaseModel):
    """單一 summary/compare checkpoint 題目。"""

    # 題目唯一識別碼。
    id: str = Field(min_length=1)
    # 本題語言維度。
    language: EvaluationLanguage
    # 要送進 chat runtime 的問題。
    question: str = Field(min_length=1)
    # 預期命中的第一層 task type。
    expected_query_type: EvaluationQueryType
    # 預期命中的第二層 summary strategy；compare 題固定為空值。
    expected_summary_strategy: str | None = None
    # 題目至少應引用到的文件檔名。
    expected_document_names: list[str]
    # 題目至少應涵蓋的章節標題片段。
    expected_section_headings: list[str]
    # judge 應確認有回答到的 claim 或比較面向。
    required_claims_or_compare_axes: list[str]
    # 用於 citation coverage 的 gold evidence 參照。
    gold_span_refs: list[SummaryCompareGoldSpanRef]
    # 若題目允許證據不足/資訊矛盾，回答不可硬編結論。
    allows_insufficient_evidence: bool = False

    @field_validator("id", "question")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """清理必要文字欄位。

        參數：
        - `value`：原始字串。

        回傳：
        - `str`：清理後的字串。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("checkpoint fixture 必填欄位不可為空白。")
        return stripped

    @field_validator("expected_document_names", "expected_section_headings", "required_claims_or_compare_axes")
    @classmethod
    def validate_string_list(cls, values: list[str]) -> list[str]:
        """清理字串清單欄位。

        參數：
        - `values`：原始字串清單。

        回傳：
        - `list[str]`：去空白、去空值後的清單。
        """

        normalized = [value.strip() for value in values if value.strip()]
        if not normalized:
            raise ValueError("checkpoint fixture 的字串清單欄位不可為空。")
        return normalized


class SummaryCompareCheckpointManifest(BaseModel):
    """checkpoint dataset manifest。"""

    # benchmark 套件名稱。
    benchmark_name: str = Field(min_length=1)
    # benchmark 版本字串。
    version: str = Field(min_length=1)
    # 套件簡述。
    description: str = Field(min_length=1)
    # 預期題目數。
    item_count: int = Field(ge=1)


class SummaryCompareJudgeScores(BaseModel):
    """LLM judge 的四維分數。"""

    # 摘要/比較是否完整回答題意。
    completeness: float = Field(ge=1.0, le=5.0)
    # 回答是否忠於引用內容。
    faithfulness_to_citations: float = Field(ge=1.0, le=5.0)
    # 結構是否符合 summary/compare 預期格式。
    structure_quality: float = Field(ge=1.0, le=5.0)
    # compare 題評比較覆蓋；非 compare 題改評 section_focus_accuracy。
    compare_coverage: float = Field(ge=1.0, le=5.0)

    @property
    def overall(self) -> float:
        """計算四維分數平均值。

        參數：
        - 無。

        回傳：
        - `float`：四維平均分數。
        """

        return round(
            (
                self.completeness
                + self.faithfulness_to_citations
                + self.structure_quality
                + self.compare_coverage
            )
            / 4.0,
            4,
        )


class SummaryCompareJudgeResult(BaseModel):
    """單題 judge 結果。"""

    # judge 使用的模型名稱。
    model: str
    # 四維分數。
    scores: SummaryCompareJudgeScores
    # 第四維實際代表的評分名稱。
    coverage_dimension_name: str
    # judge 的簡短理由摘要。
    rationale: str
    # judge 指出的主要缺口。
    missing_points: list[str]


class SummaryCompareJudgeCompletionPayload(BaseModel):
    """LLM judge completion 的受控 JSON payload。"""

    # 四維分數。
    scores: SummaryCompareJudgeScores
    # 第四維實際代表的評分名稱。
    coverage_dimension_name: str | None = None
    # judge 的簡短理由摘要。
    rationale: str = ""
    # judge 指出的主要缺口。
    missing_points: list[str] = Field(default_factory=list)


class SummaryCompareGateMetric(BaseModel):
    """單一 gate 指標結果。"""

    # 指標名稱。
    name: str
    # 實際量測值。
    actual: float
    # 門檻值。
    threshold: float
    # 比較運算子，例如 `>=` 或 `<=`。
    comparator: str
    # 是否通過。
    passed: bool


class SummaryCompareResolvedGoldSpan(BaseModel):
    """將 gold evidence 對齊到當前文件後的實體 span。"""

    # 對應的檔名。
    file_name: str
    # 對回後的文件識別碼。
    document_id: str
    # 對回後的起始 offset。
    start_offset: int
    # 對回後的結束 offset。
    end_offset: int
    # 對回使用的 quote；若採 offset-first 對回則可能為空值。
    quote: str | None = None


class SummaryComparePerItemResult(BaseModel):
    """單題 checkpoint 執行結果。"""

    # 題目識別碼。
    item_id: str
    # 題目語言。
    language: EvaluationLanguage
    # 題目文字。
    question: str
    # runtime 輸出的乾淨答案。
    answer: str
    # 最終回答區塊。
    answer_blocks: list[dict[str, object]]
    # 最終 citations。
    citations: list[dict[str, object]]
    # 整體 trace。
    trace: dict[str, object]
    # 本題實際命中的 query type。
    actual_query_type: str | None
    # 本題實際命中的 summary strategy。
    actual_summary_strategy: str | None
    # task type 是否命中 fixture 預期。
    task_type_matched: bool
    # summary strategy 是否命中 fixture 預期。
    summary_strategy_matched: bool
    # 必需文件是否都有被引用。
    required_document_coverage: float = Field(ge=0.0, le=1.0)
    # 尚未被引用到的必需文件名稱。
    missing_required_document_names: list[str] = Field(default_factory=list)
    # section heading 是否都有被命中。
    section_coverage: float = Field(ge=0.0, le=1.0)
    # citation 與 gold spans 的覆蓋率。
    citation_coverage: float = Field(ge=0.0, le=1.0)
    # 是否發生 retrieval fallback。
    fallback_triggered: bool
    # 本題 wall-clock latency。
    latency_seconds: float = Field(ge=0.0)
    # 本題 summary/compare trace 估算的總 token。
    total_tokens: int = Field(ge=0)
    # 對回後的 gold spans。
    resolved_gold_spans: list[SummaryCompareResolvedGoldSpan]
    # deterministic blocker 失敗原因。
    hard_blocker_failures: list[str]
    # judge 結果。
    judge_result: SummaryCompareJudgeResult


class SummaryComparePerItemDraft(BaseModel):
    """checkpoint 單題在寫入 judge 結果前的 builder model。"""

    # 題目識別碼。
    item_id: str
    # 題目語言。
    language: EvaluationLanguage
    # 題目文字。
    question: str
    # runtime 輸出的乾淨答案。
    answer: str
    # 最終回答區塊。
    answer_blocks: list[ChatAnswerBlock]
    # 最終 citations。
    citations: list[ChatCitation]
    # 整體 trace。
    trace: ChatTrace
    # 本題實際命中的 query type。
    actual_query_type: str | None
    # 本題實際命中的 summary strategy。
    actual_summary_strategy: str | None
    # task type 是否命中 fixture 預期。
    task_type_matched: bool
    # summary strategy 是否命中 fixture 預期。
    summary_strategy_matched: bool
    # 必需文件是否都有被引用。
    required_document_coverage: float = Field(ge=0.0, le=1.0)
    # 尚未被引用到的必需文件名稱。
    missing_required_document_names: list[str] = Field(default_factory=list)
    # section heading 是否都有被命中。
    section_coverage: float = Field(ge=0.0, le=1.0)
    # citation 與 gold spans 的覆蓋率。
    citation_coverage: float = Field(ge=0.0, le=1.0)
    # 是否發生 retrieval fallback。
    fallback_triggered: bool
    # 本題 wall-clock latency。
    latency_seconds: float = Field(ge=0.0)
    # 本題 summary/compare trace 估算的總 token。
    total_tokens: int = Field(ge=0)
    # 對回後的 gold spans。
    resolved_gold_spans: list[SummaryCompareResolvedGoldSpan]
    # deterministic blocker 失敗原因。
    hard_blocker_failures: list[str]


class SummaryCompareAggregateMetrics(BaseModel):
    """checkpoint aggregate metrics。"""

    # task type 準確率。
    task_type_accuracy: float = Field(ge=0.0, le=1.0)
    # summary strategy 準確率。
    summary_strategy_accuracy: float = Field(ge=0.0, le=1.0)
    # 必需文件覆蓋率。
    required_document_coverage: float = Field(ge=0.0, le=1.0)
    # citation 覆蓋率。
    citation_coverage: float = Field(ge=0.0, le=1.0)
    # section 覆蓋率。
    section_coverage: float = Field(ge=0.0, le=1.0)
    # fallback rate。
    fallback_rate: float = Field(ge=0.0, le=1.0)
    # 平均完整度分數。
    avg_completeness: float = Field(ge=1.0, le=5.0)
    # 平均忠實度分數。
    avg_faithfulness_to_citations: float = Field(ge=1.0, le=5.0)
    # 平均結構品質分數。
    avg_structure_quality: float = Field(ge=1.0, le=5.0)
    # 平均 coverage 分數。
    avg_compare_coverage: float = Field(ge=1.0, le=5.0)
    # 平均 overall 分數。
    avg_overall_score: float = Field(ge=1.0, le=5.0)
    # latency p95。
    p95_latency_seconds: float = Field(ge=0.0)
    # timeout 題數。
    timeout_count: int = Field(ge=0)


class SummaryCompareRunMetadata(BaseModel):
    """checkpoint run metadata。"""

    # benchmark 名稱。
    benchmark_name: str
    # benchmark 版本。
    benchmark_version: str
    # 目標 area。
    area_id: str
    # 執行者 sub。
    actor_sub: str
    # judge model 名稱。
    judge_model: str
    # 本輪 checkpoint 是否啟用 thinking mode。
    thinking_mode: bool
    # 本輪實際驗證的正式 answer path。
    answer_path: str
    # 產出時間。
    generated_at: datetime
    # 題目數量。
    item_count: int


class SummaryCompareCheckpointReport(BaseModel):
    """完整 checkpoint report。"""

    # 最終是否過關。
    passed: bool
    # run metadata。
    run_metadata: SummaryCompareRunMetadata
    # aggregate metrics。
    aggregate_metrics: SummaryCompareAggregateMetrics
    # judge aggregate scores。
    judge_scores: dict[str, float]
    # 各 gate 結果。
    gate_results: list[SummaryCompareGateMetric]
    # 單題結果。
    per_item_results: list[SummaryComparePerItemResult]
    # 所有 hard blocker failure 的摘要。
    hard_blocker_failures: list[dict[str, object]]
    # 失敗原因分類統計。
    failure_category_counts: dict[str, int]
    # 建議回修方向。
    recommendations: list[str]
