"""雙語 summary/compare benchmark suite、package 與報表資料契約。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.chat.contracts.types import ChatAnswerBlock, ChatCitation, ChatTrace
from app.db.models import EvaluationLanguage, EvaluationQueryType
from app.schemas.summary_compare_checkpoint import SummaryCompareGoldSpanRef, SummaryCompareResolvedGoldSpan


# metric `standard_level` 合法值。
SUMMARY_COMPARE_STANDARD_LEVELS = ("standard", "semi_standard", "project_contract")
# retrieval scope `mode` 合法值。
SUMMARY_COMPARE_RETRIEVAL_SCOPE_MODES = ("routing", "explicit_document_ids")
# 單題 metric 狀態合法值。
SUMMARY_COMPARE_METRIC_STATUSES = ("scored", "not_applicable", "judge_failed")


class SummaryCompareBenchmarkRetrievalScope(BaseModel):
    """單題 benchmark 的 retrieval scope contract。"""

    # scope 模式；`explicit_document_ids` 僅供 benchmark/test 使用。
    mode: Literal["routing", "explicit_document_ids"] = "routing"
    # 若 package 尚未綁定實際 area 文件 id，可先以檔名解析。
    document_file_names: list[str] = Field(default_factory=list)
    # 若已在 benchmark area 內建立固定文件，可直接指定 document ids。
    document_ids: list[str] = Field(default_factory=list)

    @field_validator("document_file_names", "document_ids")
    @classmethod
    def validate_identifier_list(cls, values: list[str]) -> list[str]:
        """清理 retrieval scope 識別碼清單。

        參數：
        - `values`：原始識別碼清單。

        回傳：
        - `list[str]`：去空白、去重複後的識別碼清單。
        """

        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized

    @model_validator(mode="after")
    def validate_scope_mode(self) -> "SummaryCompareBenchmarkRetrievalScope":
        """驗證 `routing` 與 `explicit_document_ids` 的欄位組合是否合法。

        參數：
        - 無。

        回傳：
        - `SummaryCompareBenchmarkRetrievalScope`：驗證通過的 scope。
        """

        if self.mode == "routing":
            if self.document_file_names or self.document_ids:
                raise ValueError("routing scope 不可攜帶 document ids 或 document file names。")
            return self
        if not self.document_file_names and not self.document_ids:
            raise ValueError("explicit_document_ids scope 至少要提供 document_ids 或 document_file_names。")
        return self


class SummaryCompareBenchmarkItemBase(BaseModel):
    """summary/compare benchmark 單題共用欄位。"""

    # 題目唯一識別碼。
    id: str = Field(min_length=1)
    # 題目語言。
    language: EvaluationLanguage
    # 題目文字。
    question: str = Field(min_length=1)
    # benchmark 期待的證據文件。
    expected_document_names: list[str]
    # benchmark 期待覆蓋的 claims 或 compare axes。
    required_claims_or_axes: list[str]
    # citation coverage 的 gold evidence refs。
    gold_span_refs: list[SummaryCompareGoldSpanRef]
    # benchmark/test retrieval scope。
    retrieval_scope: SummaryCompareBenchmarkRetrievalScope = Field(default_factory=SummaryCompareBenchmarkRetrievalScope)
    # 若題目允許證據不足，回答必須承認不確定性。
    allows_insufficient_evidence: bool = False
    # 題目參考答案。
    reference_answer: str = Field(min_length=1)

    @field_validator("id", "question", "reference_answer")
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
            raise ValueError("benchmark fixture 必填欄位不可為空白。")
        return stripped

    @field_validator("expected_document_names", "required_claims_or_axes")
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
            raise ValueError("benchmark fixture 的字串清單欄位不可為空。")
        return normalized


class SummaryBenchmarkItem(SummaryCompareBenchmarkItemBase):
    """summary benchmark 單題資料。"""

    # 固定為 summary 題。
    task_type: Literal["document_summary"] = "document_summary"
    # summary strategy。
    summary_strategy: Literal["document_overview", "section_focused", "multi_document_theme"]
    # 預期章節標題片段；若為整體摘要可為空。
    expected_section_headings: list[str] = Field(default_factory=list)

    @field_validator("expected_section_headings")
    @classmethod
    def validate_section_headings(cls, values: list[str]) -> list[str]:
        """清理 section heading 清單。

        參數：
        - `values`：原始標題片段。

        回傳：
        - `list[str]`：清理後的標題片段。
        """

        return [value.strip() for value in values if value.strip()]


class CompareBenchmarkItem(SummaryCompareBenchmarkItemBase):
    """compare benchmark 單題資料。"""

    # 固定為 compare 題。
    task_type: Literal["cross_document_compare"] = "cross_document_compare"
    # compare 題的比較面向。
    comparison_axes: list[str]

    @field_validator("comparison_axes")
    @classmethod
    def validate_comparison_axes(cls, values: list[str]) -> list[str]:
        """清理 comparison axes 清單。

        參數：
        - `values`：原始比較面向清單。

        回傳：
        - `list[str]`：清理後的比較面向。
        """

        normalized = [value.strip() for value in values if value.strip()]
        if not normalized:
            raise ValueError("compare benchmark 必須提供 comparison_axes。")
        return normalized


SummaryCompareBenchmarkItem = SummaryBenchmarkItem | CompareBenchmarkItem


class SummaryCompareBenchmarkPackageManifest(BaseModel):
    """單一 benchmark package 的 manifest。"""

    # package 名稱。
    benchmark_name: str = Field(min_length=1)
    # package 版本。
    version: str = Field(min_length=1)
    # package 說明。
    description: str = Field(min_length=1)
    # package 主要語言。
    language: EvaluationLanguage
    # 任務族群。
    task_family: Literal["summary", "compare"]
    # 預期題數。
    item_count: int = Field(ge=1)


class SummaryCompareBenchmarkSuiteManifest(BaseModel):
    """summary/compare benchmark suite manifest。"""

    # suite 名稱。
    benchmark_name: str = Field(min_length=1)
    # suite 版本。
    version: str = Field(min_length=1)
    # suite 說明。
    description: str = Field(min_length=1)
    # 相對於 suite 目錄的 package 路徑。
    dataset_packages: list[str]

    @field_validator("dataset_packages")
    @classmethod
    def validate_dataset_packages(cls, values: list[str]) -> list[str]:
        """清理 package 路徑清單。

        參數：
        - `values`：原始路徑清單。

        回傳：
        - `list[str]`：去空白、去重複後的路徑清單。
        """

        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        if not normalized:
            raise ValueError("summary/compare benchmark suite 至少要包含一個 package。")
        return normalized


class SummaryCompareMetricRegistryEntry(BaseModel):
    """單一 metric 的 registry 定義。"""

    # metric 名稱。
    metric_name: str
    # 方法來源。
    source_method: str
    # 方法標準等級。
    standard_level: Literal["standard", "semi_standard", "project_contract"]
    # 此 metric 適用的任務族群或 task type。
    applies_to: list[str]


class SummaryCompareMetricResult(BaseModel):
    """單一 metric 的分數或狀態。"""

    # metric 狀態。
    status: Literal["scored", "not_applicable", "judge_failed"] = "scored"
    # 分數值；若未成功計分則為空。
    value: float | None = None
    # 狀態原因。
    reason: str | None = None


class SummaryCompareScopeValidationResult(BaseModel):
    """單題 benchmark retrieval scope 驗證結果。"""

    # scope 模式。
    mode: Literal["routing", "explicit_document_ids"]
    # 題目原始要求的 document ids。
    requested_document_ids: list[str] = Field(default_factory=list)
    # 題目原始要求的 document file names。
    requested_document_file_names: list[str] = Field(default_factory=list)
    # 驗證後可用的 document ids。
    resolved_document_ids: list[str] = Field(default_factory=list)
    # 驗證狀態。
    validation_status: Literal["validated", "routing", "invalid"] = "routing"
    # 驗證失敗原因。
    validation_errors: list[str] = Field(default_factory=list)


class SummaryCompareJudgeRubricScores(BaseModel):
    """supporting rubric judge 四維分數。"""

    # 完整性分數。
    completeness: float = Field(ge=1.0, le=5.0)
    # 忠實度分數。
    faithfulness_to_citations: float = Field(ge=1.0, le=5.0)
    # 結構品質分數。
    structure_quality: float = Field(ge=1.0, le=5.0)
    # coverage 分數。
    compare_coverage: float = Field(ge=1.0, le=5.0)

    @property
    def overall(self) -> float:
        """計算四維平均分數。

        參數：
        - 無。

        回傳：
        - `float`：四維平均值。
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


class SummaryCompareRubricJudgeResult(BaseModel):
    """supporting rubric judge 結果。"""

    # judge 模型名稱。
    model: str
    # rubric 分數。
    scores: SummaryCompareJudgeRubricScores
    # judge 簡短理由。
    rationale: str
    # judge 指出的缺漏。
    missing_points: list[str]


class SummaryComparePairwiseJudgeResult(BaseModel):
    """compare 主分數用的 pairwise judge 結果。"""

    # judge 模型名稱。
    model: str
    # 勝方；`candidate`、`reference` 或 `tie`。
    verdict: Literal["candidate", "reference", "tie"]
    # judge 簡短理由。
    rationale: str
    # 此題 pairwise 主分數。
    score: float = Field(ge=0.0, le=1.0)


class SummaryComparePairwiseCompletionPayload(BaseModel):
    """pairwise judge completion 的受控 JSON payload。"""

    # 勝方；`candidate`、`reference` 或 `tie`。
    verdict: Literal["candidate", "reference", "tie"] = "reference"
    # judge 簡短理由。
    rationale: str = ""


class SummaryCompareBenchmarkPerItemResult(BaseModel):
    """單題 benchmark 執行結果。"""

    # 套件名稱。
    benchmark_name: str
    # 題目識別碼。
    item_id: str
    # 題目語言。
    language: EvaluationLanguage
    # 題目類型。
    task_type: EvaluationQueryType
    # summary strategy；compare 題為空。
    summary_strategy: str | None = None
    # 題目文字。
    question: str
    # 回答文字。
    answer: str
    # 回答區塊。
    answer_blocks: list[dict[str, object]]
    # citations。
    citations: list[dict[str, object]]
    # trace。
    trace: dict[str, object]
    # wall-clock latency。
    latency_seconds: float = Field(ge=0.0)
    # token 統計。
    total_tokens: int = Field(ge=0)
    # 對回後的 gold spans。
    resolved_gold_spans: list[SummaryCompareResolvedGoldSpan]
    # scope 驗證結果。
    benchmark_document_scope: SummaryCompareScopeValidationResult
    # 必需文件覆蓋率。
    required_document_coverage: float = Field(ge=0.0, le=1.0)
    # 尚未被引用到的必需文件名稱。
    missing_required_document_names: list[str] = Field(default_factory=list)
    # section 覆蓋率。
    section_coverage: float = Field(ge=0.0, le=1.0)
    # citation 覆蓋率。
    citation_coverage: float = Field(ge=0.0, le=1.0)
    # 是否觸發 fallback。
    fallback_triggered: bool
    # blocker 或 validation 失敗原因。
    hard_blocker_failures: list[str]
    # supporting rubric judge 結果。
    rubric_judge_result: SummaryCompareRubricJudgeResult | None = None
    # compare 主分數用 pairwise judge 結果。
    pairwise_judge_result: SummaryComparePairwiseJudgeResult | None = None
    # 單題 metrics。
    metrics: dict[str, SummaryCompareMetricResult]
    # 是否為 partial 題。
    partial: bool = False


class SummaryCompareBenchmarkItemDraft(BaseModel):
    """benchmark 單題在 finalize 前的 builder model。"""

    # 套件名稱。
    benchmark_name: str
    # 題目識別碼。
    item_id: str
    # 題目語言。
    language: EvaluationLanguage
    # 題目類型。
    task_type: EvaluationQueryType
    # summary strategy；compare 題為空。
    summary_strategy: str | None = None
    # 題目文字。
    question: str
    # 回答文字。
    answer: str
    # 回答區塊。
    answer_blocks: list[ChatAnswerBlock]
    # citations。
    citations: list[ChatCitation]
    # trace。
    trace: ChatTrace
    # wall-clock latency。
    latency_seconds: float = Field(ge=0.0)
    # token 統計。
    total_tokens: int = Field(ge=0)
    # 對回後的 gold spans。
    resolved_gold_spans: list[SummaryCompareResolvedGoldSpan]
    # scope 驗證結果。
    benchmark_document_scope: SummaryCompareScopeValidationResult
    # 必需文件覆蓋率。
    required_document_coverage: float = Field(ge=0.0, le=1.0)
    # 尚未被引用到的必需文件名稱。
    missing_required_document_names: list[str] = Field(default_factory=list)
    # section 覆蓋率。
    section_coverage: float = Field(ge=0.0, le=1.0)
    # citation 覆蓋率。
    citation_coverage: float = Field(ge=0.0, le=1.0)
    # 是否觸發 fallback。
    fallback_triggered: bool
    # blocker 或 validation 失敗原因。
    hard_blocker_failures: list[str]
    # supporting rubric judge 結果。
    rubric_judge_result: SummaryCompareRubricJudgeResult | None = None
    # compare 主分數用 pairwise judge 結果。
    pairwise_judge_result: SummaryComparePairwiseJudgeResult | None = None
    # 單題 metrics。
    metrics: dict[str, SummaryCompareMetricResult]
    # 是否為 partial 題。
    partial: bool = False


class SummaryCompareDatasetScoreSummary(BaseModel):
    """單一 package 的 benchmark 分數摘要。"""

    # 套件名稱。
    benchmark_name: str
    # 套件版本。
    benchmark_version: str
    # 主要語言。
    language: EvaluationLanguage
    # 任務族群。
    task_family: Literal["summary", "compare"]
    # 題數。
    item_count: int = Field(ge=1)
    # 主分數使用的 metric 名稱。
    main_score_metric: str
    # 套件主分數。
    main_score: SummaryCompareMetricResult
    # supporting metrics。
    supporting_metrics: dict[str, SummaryCompareMetricResult]
    # 是否有 partial 題。
    partial: bool = False


class SummaryCompareExecutionSummary(BaseModel):
    """整體 execution 摘要。"""

    # 並行 worker 數。
    parallel_workers: int = Field(ge=1, le=6)
    # 需要 judge 的題數。
    judge_items_count: int = Field(ge=0)
    # judge 失敗題數。
    judge_failed_count: int = Field(ge=0)
    # partial 題數。
    partial_items_count: int = Field(ge=0)


class SummaryCompareBenchmarkRunMetadata(BaseModel):
    """summary/compare benchmark run metadata。"""

    # suite 名稱。
    benchmark_name: str
    # suite 版本。
    benchmark_version: str
    # area id。
    area_id: str
    # actor sub。
    actor_sub: str
    # judge model 名稱。
    judge_model: str | None = None
    # 產出時間。
    generated_at: datetime
    # 套件數。
    dataset_count: int = Field(ge=1)
    # 題目總數。
    item_count: int = Field(ge=1)


class SummaryCompareBenchmarkOverview(BaseModel):
    """benchmark 總覽主結果。"""

    # summary 主分數。
    summary_benchmark_score: SummaryCompareMetricResult
    # compare 主分數。
    compare_benchmark_score: SummaryCompareMetricResult
    # 納入的套件數。
    dataset_count: int = Field(ge=1)
    # not applicable metrics 清單。
    not_applicable_metrics: list[str]


class SummaryCompareBenchmarkReport(BaseModel):
    """完整 summary/compare benchmark report。"""

    # run metadata。
    run_metadata: SummaryCompareBenchmarkRunMetadata
    # execution 摘要。
    execution: SummaryCompareExecutionSummary
    # metric registry。
    metric_registry: dict[str, SummaryCompareMetricRegistryEntry]
    # 各套件分數。
    per_dataset_scores: list[SummaryCompareDatasetScoreSummary]
    # 任務族群分數。
    task_family_scores: dict[str, SummaryCompareMetricResult]
    # 語言 rollup 分數。
    language_rollups: dict[str, SummaryCompareMetricResult]
    # benchmark 總覽。
    benchmark_overview: SummaryCompareBenchmarkOverview
    # supporting aggregate metrics。
    aggregate_metrics: dict[str, SummaryCompareMetricResult]
    # 單題結果。
    per_item_results: list[SummaryCompareBenchmarkPerItemResult]
    # baseline compare。
    baseline_compare: dict[str, object]
