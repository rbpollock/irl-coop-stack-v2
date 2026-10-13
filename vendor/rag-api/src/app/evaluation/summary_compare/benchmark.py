"""雙語 summary/compare benchmark suite runner、scorer 與 artifact 服務。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.verifier import CurrentPrincipal
from app.chat.contracts.types import ChatCitation, ChatTrace
from app.core.settings import AppSettings
from app.db.models import Document, DocumentStatus, EvaluationLanguage, EvaluationQueryType
from app.schemas.summary_compare_benchmark import (
    CompareBenchmarkItem,
    SummaryBenchmarkItem,
    SummaryCompareBenchmarkItem,
    SummaryCompareBenchmarkItemDraft,
    SummaryCompareBenchmarkOverview,
    SummaryCompareBenchmarkPackageManifest,
    SummaryComparePairwiseCompletionPayload,
    SummaryCompareBenchmarkPerItemResult,
    SummaryCompareBenchmarkReport,
    SummaryCompareBenchmarkRunMetadata,
    SummaryCompareBenchmarkSuiteManifest,
    SummaryCompareDatasetScoreSummary,
    SummaryCompareExecutionSummary,
    SummaryCompareMetricRegistryEntry,
    SummaryCompareMetricResult,
    SummaryComparePairwiseJudgeResult,
    SummaryCompareJudgeRubricScores,
    SummaryCompareRubricJudgeResult,
    SummaryCompareScopeValidationResult,
)
from app.schemas.summary_compare_checkpoint import SummaryCompareCheckpointItem, SummaryCompareJudgeScores
from app.schemas.summary_compare_checkpoint import SummaryCompareJudgeCompletionPayload
from app.schemas.summary_compare_offline_judge import (
    SummaryCompareOfflineJudgeDecision,
    SummaryCompareOfflineJudgePacket,
)
from .checkpoint import (
    OpenAISummaryCompareJudge,
    SummaryCompareExecution,
    _answer_mentions_insufficient_evidence,
    _coerce_optional_str,
    _compute_citation_coverage,
    _collect_missing_required_document_names,
    _compute_required_document_coverage,
    _compute_section_coverage,
    _load_ready_documents_by_name,
    _resolve_gold_spans,
    _validate_citation_ready_documents,
    build_summary_compare_judge_prompt,
    execute_summary_compare_item,
)
from .offline_judge import load_offline_judge_decisions, load_offline_judge_packets


# suite manifest 檔名。
SUMMARY_COMPARE_SUITE_MANIFEST_FILE = "manifest.json"
# package 題目檔名。
SUMMARY_COMPARE_PACKAGE_QUESTIONS_FILE = "questions.jsonl"
# package reference summary 檔名。
SUMMARY_COMPARE_REFERENCE_RUN_SUMMARY_FILE = "reference_run_summary.json"
# summary/compare benchmark 最大並行 worker。
SUMMARY_COMPARE_MAX_PARALLEL_WORKERS = 6
# compare 主分數 metric 名稱。
COMPARE_MAIN_SCORE_METRIC = "pairwise_rubric_judge_win_rate"
# summary 主分數 metric 名稱。
SUMMARY_MAIN_SCORE_METRIC = "bert_score_f1"


# 正式 metric registry；所有對外 metric 都必須在此定義方法來源與標準等級。
SUMMARY_COMPARE_METRIC_REGISTRY: dict[str, SummaryCompareMetricRegistryEntry] = {
    "bert_score_f1": SummaryCompareMetricRegistryEntry(
        metric_name="bert_score_f1",
        source_method="BERTScore (Zhang et al., 2019)",
        standard_level="standard",
        applies_to=["summary"],
    ),
    "qafacteval_score": SummaryCompareMetricRegistryEntry(
        metric_name="qafacteval_score",
        source_method="QAFactEval (Fabbri et al., 2021)",
        standard_level="semi_standard",
        applies_to=["summary"],
    ),
    "pairwise_rubric_judge_win_rate": SummaryCompareMetricRegistryEntry(
        metric_name="pairwise_rubric_judge_win_rate",
        source_method="LLM-as-a-judge rubric / pairwise evaluation",
        standard_level="semi_standard",
        applies_to=["compare"],
    ),
    "required_document_coverage": SummaryCompareMetricRegistryEntry(
        metric_name="required_document_coverage",
        source_method="product evidence contract",
        standard_level="project_contract",
        applies_to=["summary", "compare"],
    ),
    "citation_coverage": SummaryCompareMetricRegistryEntry(
        metric_name="citation_coverage",
        source_method="product evidence contract",
        standard_level="project_contract",
        applies_to=["summary", "compare"],
    ),
    "section_coverage": SummaryCompareMetricRegistryEntry(
        metric_name="section_coverage",
        source_method="product evidence contract",
        standard_level="project_contract",
        applies_to=["summary", "compare"],
    ),
    "required_document_not_cited_rate": SummaryCompareMetricRegistryEntry(
        metric_name="required_document_not_cited_rate",
        source_method="product evidence contract",
        standard_level="project_contract",
        applies_to=["summary", "compare"],
    ),
    "insufficient_evidence_not_acknowledged_rate": SummaryCompareMetricRegistryEntry(
        metric_name="insufficient_evidence_not_acknowledged_rate",
        source_method="product evidence contract",
        standard_level="project_contract",
        applies_to=["summary", "compare"],
    ),
    "avg_overall_score": SummaryCompareMetricRegistryEntry(
        metric_name="avg_overall_score",
        source_method="LLM judge rubric aggregate",
        standard_level="project_contract",
        applies_to=["summary", "compare"],
    ),
}


class SummaryReferenceScorer(Protocol):
    """summary 主分數 scorer 介面。"""

    def score(
        self,
        *,
        item: SummaryBenchmarkItem,
        answer: str,
    ) -> SummaryCompareMetricResult:
        """對單題 summary answer 計分。

        參數：
        - `item`：summary benchmark 題目。
        - `answer`：模型回答。

        回傳：
        - `SummaryCompareMetricResult`：主分數或失敗狀態。
        """


class SupportingMetricScorer(Protocol):
    """supporting metric scorer 介面。"""

    def score(
        self,
        *,
        item: SummaryBenchmarkItem,
        answer: str,
        citations: list[ChatCitation],
    ) -> SummaryCompareMetricResult:
        """對單題 supporting metric 計分。

        參數：
        - `item`：summary benchmark 題目。
        - `answer`：模型回答。
        - `citations`：引用列表。

        回傳：
        - `SummaryCompareMetricResult`：分數或狀態。
        """


class RubricJudge(Protocol):
    """supporting rubric judge 介面。"""

    def judge(
        self,
        *,
        item: SummaryCompareCheckpointItem,
        answer: str,
        citations: list[ChatCitation],
        trace: ChatTrace,
    ):
        """對單題結果打 supporting rubric 分數。

        參數：
        - `item`：checkpoint 相容題目。
        - `answer`：模型回答。
        - `citations`：引用列表。
        - `trace`：runtime trace。

        回傳：
        - 任意具備 `model`、`scores`、`rationale`、`missing_points` 欄位的結果。
        """


class PairwiseJudge(Protocol):
    """compare 主分數用 pairwise judge 介面。"""

    def judge(
        self,
        *,
        item: CompareBenchmarkItem,
        answer: str,
        citations: list[ChatCitation],
    ) -> SummaryComparePairwiseJudgeResult:
        """比較 candidate 與 reference answer。

        參數：
        - `item`：compare benchmark 題目。
        - `answer`：模型回答。
        - `citations`：引用列表。

        回傳：
        - `SummaryComparePairwiseJudgeResult`：pairwise 勝負結果。
        """


class BertScoreSummaryScorer:
    """使用 `bert-score` 套件計算 summary 主分數。"""

    def score(
        self,
        *,
        item: SummaryBenchmarkItem,
        answer: str,
    ) -> SummaryCompareMetricResult:
        """使用 BERTScore F1 計算單題 summary 分數。

        參數：
        - `item`：summary benchmark 題目。
        - `answer`：模型回答。

        回傳：
        - `SummaryCompareMetricResult`：BERTScore F1；依賴缺失時回傳 `not_applicable`。
        """

        try:
            from bert_score import score as bert_score
        except ImportError:
            return SummaryCompareMetricResult(status="not_applicable", reason="缺少 bert-score 依賴。")
        if not answer.strip():
            return SummaryCompareMetricResult(status="not_applicable", reason="回答為空，無法計算 BERTScore。")

        lang = "zh" if item.language == EvaluationLanguage.zh_tw else "en"
        try:
            _, _, f1 = bert_score(
                [answer],
                [item.reference_answer],
                lang=lang,
                verbose=False,
                rescale_with_baseline=False,
            )
        except Exception as exc:  # pragma: no cover - 依賴細節由整合環境決定。
            return SummaryCompareMetricResult(status="not_applicable", reason=f"BERTScore 執行失敗：{type(exc).__name__}")
        return SummaryCompareMetricResult(value=round(float(f1.mean().item()), 6))


class UnsupportedQAFactEvalScorer:
    """目前先回傳 `not_applicable` 的 QAFactEval scorer。"""

    def score(
        self,
        *,
        item: SummaryBenchmarkItem,
        answer: str,
        citations: list[ChatCitation],
    ) -> SummaryCompareMetricResult:
        """回傳目前階段的 QAFactEval `not_applicable` 狀態。

        參數：
        - `item`：summary benchmark 題目。
        - `answer`：模型回答。
        - `citations`：引用列表。

        回傳：
        - `SummaryCompareMetricResult`：固定 `not_applicable`。
        """

        del item, answer, citations
        return SummaryCompareMetricResult(status="not_applicable", reason="目前未整合 QAFactEval scorer。")


class OpenAIPairwiseJudge:
    """compare 主分數用的 OpenAI pairwise judge。"""

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float = 30.0, max_attempts: int = 3) -> None:
        """初始化 OpenAI pairwise judge。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：judge model 名稱。
        - `timeout_seconds`：單次 timeout 秒數。
        - `max_attempts`：最多重試次數。

        回傳：
        - `None`：僅建立 client。
        """

        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._max_attempts = max(1, max_attempts)
        self._timeout_seconds = timeout_seconds

    def judge(
        self,
        *,
        item: CompareBenchmarkItem,
        answer: str,
        citations: list[ChatCitation],
    ) -> SummaryComparePairwiseJudgeResult:
        """對 compare 題執行 pairwise judge。

        參數：
        - `item`：compare benchmark 題目。
        - `answer`：模型回答。
        - `citations`：引用列表。

        回傳：
        - `SummaryComparePairwiseJudgeResult`：勝負結果。
        """

        system_prompt, user_prompt = build_pairwise_compare_judge_prompt(
            item=item,
            answer=answer,
            citations=citations,
        )
        payload = self._create_json_completion(system_prompt=system_prompt, user_prompt=user_prompt)
        verdict = payload.verdict
        score = 1.0 if verdict == "candidate" else 0.5 if verdict == "tie" else 0.0
        return SummaryComparePairwiseJudgeResult(
            model=self._model,
            verdict=verdict,
            rationale=payload.rationale.strip(),
            score=score,
        )

    def _create_json_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> SummaryComparePairwiseCompletionPayload:
        """呼叫 OpenAI 並以 JSON 解析結果。

        參數：
        - `system_prompt`：system prompt。
        - `user_prompt`：user prompt。

        回傳：
        - `SummaryComparePairwiseCompletionPayload`：judge JSON 結果。
        """

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return SummaryComparePairwiseCompletionPayload.model_validate(
                    json.loads(response.choices[0].message.content or "{}")
                )
            except Exception as exc:  # pragma: no cover - 依賴細節由整合環境決定。
                last_error = exc
                if attempt >= self._max_attempts:
                    raise
                time.sleep(min(2.0 * attempt, self._timeout_seconds))
        if last_error is not None:  # pragma: no cover - 防禦性分支。
            raise last_error
        raise RuntimeError("pairwise judge 未取得 completion 且沒有錯誤資訊。")


@dataclass(slots=True)
class _BenchmarkPackage:
    """單一 benchmark package 的記憶體表示。"""

    manifest: SummaryCompareBenchmarkPackageManifest
    items: list[SummaryCompareBenchmarkItem]
    dataset_dir: Path


@dataclass(slots=True)
class _SingleItemExecutionResult:
    """單題 benchmark worker 回傳值。"""

    item_result: SummaryCompareBenchmarkPerItemResult
    judge_attempted: bool
    judge_failed: bool


@dataclass(slots=True)
class _BenchmarkEvaluationContext:
    """單題 benchmark 在 judge 前的上下文。"""

    # 不含 judge 結果的單題 payload。
    item_payload: SummaryCompareBenchmarkItemDraft
    # checkpoint 相容題目，供 rubric judge 使用。
    checkpoint_item: SummaryCompareCheckpointItem
    # compare 題原始資料；summary 題為空值。
    compare_item: CompareBenchmarkItem | None
    # 本題 runtime 執行結果。
    execution: SummaryCompareExecution
    # 需要輸出的離線 judge packets。
    judge_packets: list[SummaryCompareOfflineJudgePacket]


def build_pairwise_compare_judge_prompt(
    *,
    item: CompareBenchmarkItem,
    answer: str,
    citations: list[ChatCitation],
) -> tuple[str, str]:
    """建立 compare 主分數用的 pairwise judge prompt。

    參數：
    - `item`：compare benchmark 題目。
    - `answer`：模型回答。
    - `citations`：引用列表。

    回傳：
    - `tuple[str, str]`：system prompt 與 user prompt。
    """

    citation_payload = [
        {
            "document_name": citation.document_name,
            "heading": citation.heading,
            "excerpt": citation.excerpt[:600],
        }
        for citation in citations[:8]
    ]
    system_prompt = (
        "你是嚴格的 compare benchmark judge。"
        "請比較 candidate answer 與 reference answer，"
        "只根據題目、比較面向與 citations 判斷哪個答案更好。"
        "若 candidate 過度超出 citations，應判 reference 或 tie。"
        "輸出 JSON，欄位固定為 `verdict` 與 `rationale`。"
        "verdict 只能是 `candidate`、`reference`、`tie`。"
    )
    user_prompt = json.dumps(
        {
            "question": item.question,
            "comparison_axes": item.comparison_axes,
            "required_claims_or_axes": item.required_claims_or_axes,
            "reference_answer": item.reference_answer,
            "candidate_answer": answer,
            "citations": citation_payload,
        },
        ensure_ascii=False,
        indent=2,
    )
    return system_prompt, user_prompt


def load_summary_compare_benchmark_suite(
    *,
    dataset_dir: Path,
) -> tuple[SummaryCompareBenchmarkSuiteManifest, list[_BenchmarkPackage]]:
    """讀取 summary/compare benchmark suite 或單一 package。

    參數：
    - `dataset_dir`：suite 或 package 目錄。

    回傳：
    - `tuple[SummaryCompareBenchmarkSuiteManifest, list[_BenchmarkPackage]]`：suite manifest 與 package 列表。
    """

    manifest_path = dataset_dir / SUMMARY_COMPARE_SUITE_MANIFEST_FILE
    if not manifest_path.exists():
        raise ValueError(f"summary/compare benchmark 缺少 {SUMMARY_COMPARE_SUITE_MANIFEST_FILE}。")

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "dataset_packages" in manifest_payload:
        suite_manifest = SummaryCompareBenchmarkSuiteManifest.model_validate(manifest_payload)
        packages = [
            _load_benchmark_package(dataset_dir=(dataset_dir / relative_path).resolve())
            for relative_path in suite_manifest.dataset_packages
        ]
        return suite_manifest, packages

    package = _load_benchmark_package(dataset_dir=dataset_dir)
    suite_manifest = SummaryCompareBenchmarkSuiteManifest(
        benchmark_name=package.manifest.benchmark_name,
        version=package.manifest.version,
        description=package.manifest.description,
        dataset_packages=["."],
    )
    return suite_manifest, [package]


def _load_benchmark_package(*, dataset_dir: Path) -> _BenchmarkPackage:
    """讀取單一 benchmark package。

    參數：
    - `dataset_dir`：package 目錄。

    回傳：
    - `_BenchmarkPackage`：package manifest 與 items。
    """

    manifest_path = dataset_dir / SUMMARY_COMPARE_SUITE_MANIFEST_FILE
    questions_path = dataset_dir / SUMMARY_COMPARE_PACKAGE_QUESTIONS_FILE
    manifest = SummaryCompareBenchmarkPackageManifest.model_validate(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    items: list[SummaryCompareBenchmarkItem] = []
    with questions_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            task_type = payload.get("task_type")
            if task_type == EvaluationQueryType.cross_document_compare.value:
                items.append(CompareBenchmarkItem.model_validate(payload))
            else:
                items.append(SummaryBenchmarkItem.model_validate(payload))
    if len(items) != manifest.item_count:
        raise ValueError(
            f"benchmark package `{manifest.benchmark_name}` manifest.item_count={manifest.item_count} "
            f"與 questions.jsonl 實際題數 {len(items)} 不一致。"
        )
    return _BenchmarkPackage(manifest=manifest, items=items, dataset_dir=dataset_dir)


def build_default_rubric_judge(*, settings: AppSettings, judge_model: str | None) -> RubricJudge | None:
    """建立預設 supporting rubric judge。

    參數：
    - `settings`：應用程式設定。
    - `judge_model`：可選的 judge model 覆寫。

    回傳：
    - `RubricJudge | None`：有 OpenAI key 時回傳實例，否則回傳空值。
    """

    if not settings.openai_api_key:
        return None
    return OpenAISummaryCompareJudge(
        api_key=settings.openai_api_key,
        model=judge_model or settings.summary_compare_eval_judge_model,
        timeout_seconds=settings.chat_timeout_seconds,
        max_attempts=3,
    )


def build_default_pairwise_judge(*, settings: AppSettings, judge_model: str | None) -> PairwiseJudge | None:
    """建立預設 compare pairwise judge。

    參數：
    - `settings`：應用程式設定。
    - `judge_model`：可選的 judge model 覆寫。

    回傳：
    - `PairwiseJudge | None`：有 OpenAI key 時回傳實例，否則回傳空值。
    """

    if not settings.openai_api_key:
        return None
    return OpenAIPairwiseJudge(
        api_key=settings.openai_api_key,
        model=judge_model or settings.summary_compare_eval_judge_model,
        timeout_seconds=settings.chat_timeout_seconds,
        max_attempts=3,
    )


def run_summary_compare_benchmark(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    dataset_dir: Path,
    judge_model: str | None = None,
    max_parallel_workers: int = SUMMARY_COMPARE_MAX_PARALLEL_WORKERS,
    summary_scorer: SummaryReferenceScorer | None = None,
    qafacteval_scorer: SupportingMetricScorer | None = None,
    rubric_judge: RubricJudge | None = None,
    pairwise_judge: PairwiseJudge | None = None,
    progress_reporter: callable | None = None,
) -> SummaryCompareBenchmarkReport:
    """執行 summary/compare benchmark suite。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：應用程式設定。
    - `area_id`：目標 area。
    - `actor_sub`：執行者 sub。
    - `dataset_dir`：suite 或 package 目錄。
    - `judge_model`：可選的 judge model 名稱。
    - `max_parallel_workers`：並行 item lanes 數，最大不得超過 6。
    - `summary_scorer`：可注入的 summary 主分數 scorer。
    - `qafacteval_scorer`：可注入的 QAFactEval scorer。
    - `rubric_judge`：可注入的 supporting rubric judge。
    - `pairwise_judge`：可注入的 compare pairwise judge。
    - `progress_reporter`：可選的進度回報器。

    回傳：
    - `SummaryCompareBenchmarkReport`：完整 benchmark 報表。
    """

    if max_parallel_workers < 1 or max_parallel_workers > SUMMARY_COMPARE_MAX_PARALLEL_WORKERS:
        raise ValueError(f"--max-parallel-workers 只支援 1 到 {SUMMARY_COMPARE_MAX_PARALLEL_WORKERS}。")

    suite_manifest, packages = load_summary_compare_benchmark_suite(dataset_dir=dataset_dir)
    ready_documents_by_name = _load_ready_documents_by_name(session=session, area_id=area_id)
    ready_documents_by_id = _load_ready_documents_by_id(session=session, area_id=area_id)
    principal = CurrentPrincipal(sub=actor_sub, groups=())
    session_factory = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    resolved_summary_scorer = summary_scorer or BertScoreSummaryScorer()
    resolved_qafacteval_scorer = qafacteval_scorer or UnsupportedQAFactEvalScorer()
    resolved_rubric_judge = rubric_judge or build_default_rubric_judge(settings=settings, judge_model=judge_model)
    resolved_pairwise_judge = pairwise_judge or build_default_pairwise_judge(settings=settings, judge_model=judge_model)

    per_item_results: list[SummaryCompareBenchmarkPerItemResult] = []
    judge_items_count = 0
    judge_failed_count = 0
    partial_items_count = 0

    work_items: list[tuple[_BenchmarkPackage, SummaryCompareBenchmarkItem, int, int]] = []
    for package in packages:
        for index, item in enumerate(package.items, start=1):
            work_items.append((package, item, index, len(package.items)))
    item_index_by_key = {
        (package.manifest.benchmark_name, item.id): global_index
        for global_index, (package, item, _, _) in enumerate(work_items, start=1)
    }

    with ThreadPoolExecutor(max_workers=max_parallel_workers) as executor:
        future_to_work_item: dict[object, tuple[_BenchmarkPackage, SummaryCompareBenchmarkItem, int, int]] = {}
        for package, item, item_index, item_total in work_items:
            future = executor.submit(
                _run_single_benchmark_item,
                session_factory=session_factory,
                settings=settings,
                principal=principal,
                area_id=area_id,
                package=package,
                item=item,
                ready_documents_by_name=ready_documents_by_name,
                ready_documents_by_id=ready_documents_by_id,
                summary_scorer=resolved_summary_scorer,
                qafacteval_scorer=resolved_qafacteval_scorer,
                rubric_judge=resolved_rubric_judge,
                pairwise_judge=resolved_pairwise_judge,
            )
            future_to_work_item[future] = (package, item, item_index, item_total)
            _emit_progress(
                reporter=progress_reporter,
                event={
                    "type": "item_started",
                    "benchmark_name": package.manifest.benchmark_name,
                    "item_id": item.id,
                    "package_current": item_index,
                    "package_total": item_total,
                },
            )

        for future in as_completed(future_to_work_item):
            package, item, item_index, item_total = future_to_work_item[future]
            result = future.result()
            per_item_results.append(result.item_result)
            if result.judge_attempted:
                judge_items_count += 1
            if result.judge_failed:
                judge_failed_count += 1
            if result.item_result.partial:
                partial_items_count += 1
            _emit_progress(
                reporter=progress_reporter,
                event={
                    "type": "item_completed",
                    "benchmark_name": package.manifest.benchmark_name,
                    "item_id": item.id,
                    "package_current": item_index,
                    "package_total": item_total,
                    "partial": result.item_result.partial,
                    "latency_seconds": result.item_result.latency_seconds,
                },
            )

    per_item_results.sort(
        key=lambda item_result: item_index_by_key[(item_result.benchmark_name, item_result.item_id)]
    )
    per_dataset_scores = _build_per_dataset_scores(packages=packages, per_item_results=per_item_results)
    task_family_scores = _build_task_family_scores(per_dataset_scores=per_dataset_scores)
    language_rollups = _build_language_rollups(per_dataset_scores=per_dataset_scores)
    aggregate_metrics = _build_aggregate_metrics(per_item_results=per_item_results)
    baseline_compare = _build_baseline_compare(packages=packages, per_dataset_scores=per_dataset_scores)
    return _build_benchmark_report(
        suite_manifest=suite_manifest,
        packages=packages,
        settings=settings,
        area_id=area_id,
        actor_sub=actor_sub,
        judge_model=judge_model or settings.summary_compare_eval_judge_model if settings.openai_api_key else None,
        per_item_results=per_item_results,
        judge_items_count=judge_items_count,
        judge_failed_count=judge_failed_count,
        partial_items_count=partial_items_count,
        parallel_workers=max_parallel_workers,
    )


def export_summary_compare_benchmark_offline_packets(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    dataset_dir: Path,
    judge_label: str = "offline-codex",
    max_parallel_workers: int = SUMMARY_COMPARE_MAX_PARALLEL_WORKERS,
    summary_scorer: SummaryReferenceScorer | None = None,
    qafacteval_scorer: SupportingMetricScorer | None = None,
) -> tuple[SummaryCompareBenchmarkSuiteManifest, list[_BenchmarkPackage], list[SummaryCompareOfflineJudgePacket]]:
    """執行 benchmark runtime 並匯出離線 judge packets。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：應用程式設定。
    - `area_id`：目標 area。
    - `actor_sub`：執行者 sub。
    - `dataset_dir`：suite 或 package 目錄。
    - `judge_label`：離線 judge 顯示標籤。
    - `max_parallel_workers`：保留與正式 runner 一致的並行上限驗證。
    - `summary_scorer`：可注入的 summary 主分數 scorer。
    - `qafacteval_scorer`：可注入的 supporting scorer。

    回傳：
    - `tuple[SummaryCompareBenchmarkSuiteManifest, list[_BenchmarkPackage], list[SummaryCompareOfflineJudgePacket]]`：suite manifest、package 清單與 packet 清單。
    """

    if max_parallel_workers < 1 or max_parallel_workers > SUMMARY_COMPARE_MAX_PARALLEL_WORKERS:
        raise ValueError(f"--max-parallel-workers 只支援 1 到 {SUMMARY_COMPARE_MAX_PARALLEL_WORKERS}。")
    suite_manifest, packages = load_summary_compare_benchmark_suite(dataset_dir=dataset_dir)
    ready_documents_by_name = _load_ready_documents_by_name(session=session, area_id=area_id)
    ready_documents_by_id = _load_ready_documents_by_id(session=session, area_id=area_id)
    principal = CurrentPrincipal(sub=actor_sub, groups=())
    session_factory = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    resolved_summary_scorer = summary_scorer or BertScoreSummaryScorer()
    resolved_qafacteval_scorer = qafacteval_scorer or UnsupportedQAFactEvalScorer()
    packets: list[SummaryCompareOfflineJudgePacket] = []
    for package in packages:
        for item in package.items:
            context = _evaluate_benchmark_item_context(
                session_factory=session_factory,
                settings=settings,
                principal=principal,
                area_id=area_id,
                package=package,
                item=item,
                ready_documents_by_name=ready_documents_by_name,
                ready_documents_by_id=ready_documents_by_id,
                summary_scorer=resolved_summary_scorer,
                qafacteval_scorer=resolved_qafacteval_scorer,
                judge_label=judge_label,
            )
            packets.extend(context.judge_packets)
    return suite_manifest, packages, packets


def run_summary_compare_benchmark_from_offline_packets(
    *,
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    dataset_dir: Path,
    judge_packets_path: Path,
    judge_results_path: Path,
    judge_label: str = "offline-codex",
) -> SummaryCompareBenchmarkReport:
    """從離線 judge packet 與回填結果產生正式 benchmark report。

    參數：
    - `settings`：應用程式設定。
    - `area_id`：目標 area。
    - `actor_sub`：執行者 sub。
    - `dataset_dir`：suite 或 package 目錄。
    - `judge_packets_path`：離線 judge packet JSONL。
    - `judge_results_path`：人工 / Codex 回填結果 JSONL。
    - `judge_label`：預設離線 judge 標籤。

    回傳：
    - `SummaryCompareBenchmarkReport`：完整 benchmark report。
    """

    suite_manifest, packages = load_summary_compare_benchmark_suite(dataset_dir=dataset_dir)
    packets = load_offline_judge_packets(packet_path=judge_packets_path)
    decisions = load_offline_judge_decisions(decision_path=judge_results_path)
    package_names = {package.manifest.benchmark_name for package in packages}
    per_item_payloads: dict[tuple[str, str], SummaryCompareBenchmarkItemDraft] = {}
    judge_packets_by_item: dict[tuple[str, str], list[SummaryCompareOfflineJudgePacket]] = defaultdict(list)
    for packet in packets:
        if packet.benchmark_name not in package_names:
            raise ValueError(f"離線 judge packet 含未知 benchmark_name：{packet.benchmark_name}")
        item_key = (packet.benchmark_name, packet.item_id)
        if item_key not in per_item_payloads:
            per_item_payloads[item_key] = SummaryCompareBenchmarkItemDraft.model_validate(packet.context_payload)
        judge_packets_by_item[item_key].append(packet)

    ordered_item_results: list[SummaryCompareBenchmarkPerItemResult] = []
    judge_items_count = 0
    judge_failed_count = 0
    partial_items_count = 0
    for package in packages:
        for item in package.items:
            item_key = (package.manifest.benchmark_name, item.id)
            item_payload = per_item_payloads.get(item_key)
            if item_payload is None:
                raise ValueError(f"離線 judge packet 缺少題目：{package.manifest.benchmark_name}/{item.id}")
            final_item_result, judge_attempted, judge_failed = _finalize_benchmark_item_from_offline_packets(
                item_payload=item_payload,
                judge_packets=judge_packets_by_item.get(item_key, []),
                decisions=decisions,
                judge_label=judge_label,
            )
            ordered_item_results.append(final_item_result)
            if judge_attempted:
                judge_items_count += 1
            if judge_failed:
                judge_failed_count += 1
            if final_item_result.partial:
                partial_items_count += 1

    return _build_benchmark_report(
        suite_manifest=suite_manifest,
        packages=packages,
        settings=settings,
        area_id=area_id,
        actor_sub=actor_sub,
        judge_model=judge_label,
        per_item_results=ordered_item_results,
        judge_items_count=judge_items_count,
        judge_failed_count=judge_failed_count,
        partial_items_count=partial_items_count,
        parallel_workers=1,
    )


def _run_single_benchmark_item(
    *,
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    principal: CurrentPrincipal,
    area_id: str,
    package: _BenchmarkPackage,
    item: SummaryCompareBenchmarkItem,
    ready_documents_by_name: dict[str, Document],
    ready_documents_by_id: dict[str, Document],
    summary_scorer: SummaryReferenceScorer,
    qafacteval_scorer: SupportingMetricScorer,
    rubric_judge: RubricJudge | None,
    pairwise_judge: PairwiseJudge | None,
) -> _SingleItemExecutionResult:
    """執行單題 benchmark worker。

    參數：
    - `session_factory`：thread-local session factory。
    - `settings`：應用程式設定。
    - `principal`：執行者 principal。
    - `area_id`：目標 area。
    - `package`：所屬 benchmark package。
    - `item`：benchmark 題目。
    - `ready_documents_by_name`：以檔名索引的 ready 文件。
    - `ready_documents_by_id`：以 id 索引的 ready 文件。
    - `summary_scorer`：summary 主分數 scorer。
    - `qafacteval_scorer`：summary supporting scorer。
    - `rubric_judge`：supporting rubric judge。
    - `pairwise_judge`：compare 主分數 pairwise judge。

    回傳：
    - `_SingleItemExecutionResult`：單題結果與 judge 統計。
    """

    context = _evaluate_benchmark_item_context(
        session_factory=session_factory,
        settings=settings,
        principal=principal,
        area_id=area_id,
        package=package,
        item=item,
        ready_documents_by_name=ready_documents_by_name,
        ready_documents_by_id=ready_documents_by_id,
        summary_scorer=summary_scorer,
        qafacteval_scorer=qafacteval_scorer,
        judge_label=(
            getattr(rubric_judge, "_model", None)
            or getattr(pairwise_judge, "_model", None)
            or settings.summary_compare_eval_judge_model
        ),
    )
    item_payload = context.item_payload.model_copy(deep=True)
    rubric_result = None
    rubric_judge_failed = False
    pairwise_result = None
    pairwise_judge_failed = False
    for packet in context.judge_packets:
        if packet.judge_kind == "benchmark_rubric":
            rubric_result, rubric_judge_failed = _run_rubric_judge(
                rubric_judge=rubric_judge,
                checkpoint_item=context.checkpoint_item,
                execution=context.execution,
            )
            item_payload.rubric_judge_result = rubric_result
            item_metrics = dict(item_payload.metrics)
            item_metrics["avg_overall_score"] = (
                SummaryCompareMetricResult(value=rubric_result.scores.overall)
                if rubric_result is not None
                else SummaryCompareMetricResult(
                    status="judge_failed" if rubric_judge_failed else "not_applicable",
                    reason="supporting rubric judge unavailable。",
                )
            )
            item_payload.metrics = item_metrics
        elif packet.judge_kind == "benchmark_pairwise":
            if pairwise_judge is None:
                pairwise_result = None
                pairwise_judge_failed = True
            else:
                try:
                    pairwise_result = pairwise_judge.judge(
                        item=context.compare_item,
                        answer=context.execution.answer,
                        citations=context.execution.citations,
                    )
                except Exception:  # pragma: no cover - 依賴細節由整合環境決定。
                    pairwise_result = None
                    pairwise_judge_failed = True
            item_payload.pairwise_judge_result = pairwise_result
            item_metrics = dict(item_payload.metrics)
            item_metrics[COMPARE_MAIN_SCORE_METRIC] = (
                SummaryCompareMetricResult(value=pairwise_result.score)
                if pairwise_result is not None
                else SummaryCompareMetricResult(
                    status="judge_failed",
                    reason="缺少 compare pairwise judge。" if pairwise_judge is None else "pairwise judge 失敗。",
                )
            )
            item_payload.metrics = item_metrics
    finalized_item_result = SummaryCompareBenchmarkPerItemResult.model_validate(
        _finalize_benchmark_item_payload(item_payload=item_payload).model_dump(mode="json")
    )
    judge_attempted = bool(context.judge_packets)
    return _SingleItemExecutionResult(
        item_result=finalized_item_result,
        judge_attempted=judge_attempted,
        judge_failed=finalized_item_result.partial,
    )


def _evaluate_benchmark_item_context(
    *,
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    principal: CurrentPrincipal,
    area_id: str,
    package: _BenchmarkPackage,
    item: SummaryCompareBenchmarkItem,
    ready_documents_by_name: dict[str, Document],
    ready_documents_by_id: dict[str, Document],
    summary_scorer: SummaryReferenceScorer,
    qafacteval_scorer: SupportingMetricScorer,
    judge_label: str,
) -> _BenchmarkEvaluationContext:
    """建立單題 benchmark 在 judge 前的上下文。

    參數：
    - `session_factory`：thread-local session factory。
    - `settings`：應用程式設定。
    - `principal`：執行者 principal。
    - `area_id`：目標 area。
    - `package`：所屬 benchmark package。
    - `item`：benchmark 題目。
    - `ready_documents_by_name`：以檔名索引的 ready 文件。
    - `ready_documents_by_id`：以 id 索引的 ready 文件。
    - `summary_scorer`：summary 主分數 scorer。
    - `qafacteval_scorer`：summary supporting scorer。
    - `judge_label`：離線或線上 judge 顯示標籤。

    回傳：
    - `_BenchmarkEvaluationContext`：單題 payload 與 judge packets。
    """

    scope_validation = _validate_item_retrieval_scope(
        item=item,
        ready_documents_by_name=ready_documents_by_name,
        ready_documents_by_id=ready_documents_by_id,
    )
    checkpoint_item = _build_checkpoint_item_from_benchmark_item(item=item)
    hard_blocker_failures = list(scope_validation.validation_errors)
    execution = SummaryCompareExecution(
        answer="",
        answer_blocks=[],
        citations=[],
        trace=ChatTrace(retrieval={}, assembler={}, agent={}),
        latency_seconds=0.0,
        timed_out=False,
    )

    with session_factory() as item_session:
        if scope_validation.validation_status != "invalid":
            execution = execute_summary_compare_item(
                session=item_session,
                settings=settings,
                principal=principal,
                area_id=area_id,
                item=checkpoint_item,
                thinking_mode=True,
                benchmark_document_ids=tuple(scope_validation.resolved_document_ids) or None,
            )

    resolved_gold_spans, span_resolution_failures = _resolve_gold_spans(
        item=checkpoint_item,
        ready_documents=ready_documents_by_name,
    )
    hard_blocker_failures.extend(span_resolution_failures)
    hard_blocker_failures.extend(
        _validate_citation_ready_documents(
            citations=execution.citations,
            ready_documents=ready_documents_by_name,
        )
    )

    required_document_coverage = _compute_required_document_coverage(
        expected_document_names=item.expected_document_names,
        citations=execution.citations,
    )
    missing_required_document_names = _collect_missing_required_document_names(
        expected_document_names=item.expected_document_names,
        citations=execution.citations,
    )
    if required_document_coverage < 1.0:
        hard_blocker_failures.append("required_document_not_cited")

    section_headings = item.expected_section_headings if isinstance(item, SummaryBenchmarkItem) else []
    section_coverage = _compute_section_coverage(
        expected_section_headings=section_headings,
        citations=execution.citations,
    )
    citation_coverage = _compute_citation_coverage(
        resolved_gold_spans=resolved_gold_spans,
        citations=execution.citations,
    )
    retrieval_trace = execution.trace.retrieval
    agent_trace = execution.trace.agent
    map_reduce_trace = agent_trace.get("map_reduce_trace", {})
    if not isinstance(map_reduce_trace, dict):
        map_reduce_trace = {}

    fallback_triggered = bool(_coerce_optional_str(retrieval_trace.get("fallback_reason")))
    total_tokens = int(map_reduce_trace.get("total_tokens", 0) or 0)
    if item.allows_insufficient_evidence and not _answer_mentions_insufficient_evidence(execution.answer):
        hard_blocker_failures.append("insufficient_evidence_not_acknowledged")

    metrics: dict[str, SummaryCompareMetricResult] = {
        "required_document_coverage": SummaryCompareMetricResult(value=round(required_document_coverage, 6)),
        "citation_coverage": SummaryCompareMetricResult(value=round(citation_coverage, 6)),
        "section_coverage": SummaryCompareMetricResult(value=round(section_coverage, 6)),
        "required_document_not_cited_rate": SummaryCompareMetricResult(
            value=1.0 if required_document_coverage < 1.0 else 0.0
        ),
        "insufficient_evidence_not_acknowledged_rate": SummaryCompareMetricResult(
            value=1.0 if "insufficient_evidence_not_acknowledged" in hard_blocker_failures else 0.0
        ),
    }
    if isinstance(item, SummaryBenchmarkItem):
        metrics[SUMMARY_MAIN_SCORE_METRIC] = summary_scorer.score(item=item, answer=execution.answer)
        metrics["qafacteval_score"] = qafacteval_scorer.score(
            item=item,
            answer=execution.answer,
            citations=execution.citations,
        )

    rubric_system_prompt, rubric_user_prompt = build_summary_compare_judge_prompt(
        item=checkpoint_item,
        answer=execution.answer,
        citations=execution.citations,
        trace=execution.trace,
    )
    judge_packets = [
        SummaryCompareOfflineJudgePacket(
            packet_id=f"{package.manifest.benchmark_name}:{item.id}:rubric",
            judge_kind="benchmark_rubric",
            benchmark_name=package.manifest.benchmark_name,
            item_id=item.id,
            model_label=judge_label,
            system_prompt=rubric_system_prompt,
            user_prompt=rubric_user_prompt,
            context_payload={},
        )
    ]
    if isinstance(item, CompareBenchmarkItem):
        pairwise_system_prompt, pairwise_user_prompt = build_pairwise_compare_judge_prompt(
            item=item,
            answer=execution.answer,
            citations=execution.citations,
        )
        judge_packets.append(
            SummaryCompareOfflineJudgePacket(
                packet_id=f"{package.manifest.benchmark_name}:{item.id}:pairwise",
                judge_kind="benchmark_pairwise",
                benchmark_name=package.manifest.benchmark_name,
                item_id=item.id,
                model_label=judge_label,
                system_prompt=pairwise_system_prompt,
                user_prompt=pairwise_user_prompt,
                context_payload={},
            )
        )

    item_payload = SummaryCompareBenchmarkItemDraft(
        benchmark_name=package.manifest.benchmark_name,
        item_id=item.id,
        language=item.language,
        task_type=item.task_type,
        summary_strategy=item.summary_strategy if isinstance(item, SummaryBenchmarkItem) else None,
        question=item.question,
        answer=execution.answer,
        answer_blocks=execution.answer_blocks,
        citations=execution.citations,
        trace=execution.trace,
        latency_seconds=execution.latency_seconds,
        total_tokens=total_tokens,
        resolved_gold_spans=resolved_gold_spans,
        benchmark_document_scope=scope_validation,
        required_document_coverage=required_document_coverage,
        missing_required_document_names=missing_required_document_names,
        section_coverage=section_coverage,
        citation_coverage=citation_coverage,
        fallback_triggered=fallback_triggered,
        hard_blocker_failures=sorted(set(hard_blocker_failures)),
        rubric_judge_result=None,
        pairwise_judge_result=None,
        metrics=metrics,
        partial=True,
    )
    for packet in judge_packets:
        packet.context_payload = item_payload.model_dump(mode="json")
    return _BenchmarkEvaluationContext(
        item_payload=item_payload,
        checkpoint_item=checkpoint_item,
        compare_item=item if isinstance(item, CompareBenchmarkItem) else None,
        execution=execution,
        judge_packets=judge_packets,
    )


def _finalize_benchmark_item_from_offline_packets(
    *,
    item_payload: SummaryCompareBenchmarkItemDraft,
    judge_packets: list[SummaryCompareOfflineJudgePacket],
    decisions: dict[str, SummaryCompareOfflineJudgeDecision],
    judge_label: str,
) -> tuple[SummaryCompareBenchmarkPerItemResult, bool, bool]:
    """將離線 decisions 套回單題 benchmark payload。

    參數：
    - `item_payload`：匯出時保存的單題 payload。
    - `judge_packets`：該題對應的 judge packets。
    - `decisions`：`packet_id -> decision` 對照表。
    - `judge_label`：預設離線 judge 標籤。

    回傳：
    - `tuple[SummaryCompareBenchmarkPerItemResult, bool, bool]`：正式單題結果、是否需要 judge、是否 judge 失敗。
    """

    patched_payload = item_payload.model_copy(deep=True)
    metrics = dict(patched_payload.metrics)
    judge_failed = False
    for packet in judge_packets:
        decision = decisions.get(packet.packet_id)
        if decision is None:
            raise ValueError(f"缺少離線 judge decision：{packet.packet_id}")
        if packet.judge_kind == "benchmark_rubric":
            rubric_result = _build_offline_rubric_result(
                decision_payload=decision.result,
                model=decision.model or judge_label,
            )
            patched_payload.rubric_judge_result = rubric_result
            metrics["avg_overall_score"] = SummaryCompareMetricResult(value=rubric_result.scores.overall)
        elif packet.judge_kind == "benchmark_pairwise":
            pairwise_result = _build_offline_pairwise_result(
                decision_payload=decision.result,
                model=decision.model or judge_label,
            )
            patched_payload.pairwise_judge_result = pairwise_result
            metrics[COMPARE_MAIN_SCORE_METRIC] = SummaryCompareMetricResult(value=pairwise_result.score)
    patched_payload.metrics = metrics
    finalized_payload = _finalize_benchmark_item_payload(item_payload=patched_payload)
    finalized_item_result = SummaryCompareBenchmarkPerItemResult.model_validate(finalized_payload.model_dump(mode="json"))
    if finalized_item_result.partial:
        judge_failed = True
    return finalized_item_result, bool(judge_packets), judge_failed


def _finalize_benchmark_item_payload(
    *,
    item_payload: SummaryCompareBenchmarkItemDraft,
) -> SummaryCompareBenchmarkItemDraft:
    """依 metric 狀態回填 benchmark item 的 partial 欄位。

    參數：
    - `item_payload`：尚未定稿的單題 payload。

    回傳：
    - `SummaryCompareBenchmarkItemDraft`：已完成 partial 判定的 builder model。
    """

    payload = item_payload.model_copy(deep=True)
    metrics = {
        metric_name: (
            metric_value
            if isinstance(metric_value, SummaryCompareMetricResult)
            else SummaryCompareMetricResult.model_validate(metric_value)
        )
        for metric_name, metric_value in payload.metrics.items()
    }
    main_metric_name = (
        SUMMARY_MAIN_SCORE_METRIC
        if payload.task_type == EvaluationQueryType.document_summary
        else COMPARE_MAIN_SCORE_METRIC
    )
    payload.partial = any(
        metrics[metric_name].status != "scored"
        for metric_name in [main_metric_name, "avg_overall_score"]
    )
    payload.metrics = metrics
    return payload


def _build_benchmark_report(
    *,
    suite_manifest: SummaryCompareBenchmarkSuiteManifest,
    packages: list[_BenchmarkPackage],
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    judge_model: str | None,
    per_item_results: list[SummaryCompareBenchmarkPerItemResult],
    judge_items_count: int,
    judge_failed_count: int,
    partial_items_count: int,
    parallel_workers: int,
) -> SummaryCompareBenchmarkReport:
    """依單題結果建立正式 benchmark report。

    參數：
    - `suite_manifest`：suite manifest。
    - `packages`：benchmark packages。
    - `settings`：應用程式設定。
    - `area_id`：目標 area。
    - `actor_sub`：執行者 sub。
    - `judge_model`：judge 模型或標籤。
    - `per_item_results`：所有單題結果。
    - `judge_items_count`：需要 judge 的題數。
    - `judge_failed_count`：judge 失敗題數。
    - `partial_items_count`：partial 題數。
    - `parallel_workers`：本輪並行 worker 數。

    回傳：
    - `SummaryCompareBenchmarkReport`：完整 benchmark report。
    """

    del settings
    per_dataset_scores = _build_per_dataset_scores(packages=packages, per_item_results=per_item_results)
    task_family_scores = _build_task_family_scores(per_dataset_scores=per_dataset_scores)
    language_rollups = _build_language_rollups(per_dataset_scores=per_dataset_scores)
    aggregate_metrics = _build_aggregate_metrics(per_item_results=per_item_results)
    baseline_compare = _build_baseline_compare(packages=packages, per_dataset_scores=per_dataset_scores)
    return SummaryCompareBenchmarkReport(
        run_metadata=SummaryCompareBenchmarkRunMetadata(
            benchmark_name=suite_manifest.benchmark_name,
            benchmark_version=suite_manifest.version,
            area_id=area_id,
            actor_sub=actor_sub,
            judge_model=judge_model,
            generated_at=datetime.now(UTC),
            dataset_count=len(packages),
            item_count=len(per_item_results),
        ),
        execution=SummaryCompareExecutionSummary(
            parallel_workers=parallel_workers,
            judge_items_count=judge_items_count,
            judge_failed_count=judge_failed_count,
            partial_items_count=partial_items_count,
        ),
        metric_registry=SUMMARY_COMPARE_METRIC_REGISTRY,
        per_dataset_scores=per_dataset_scores,
        task_family_scores=task_family_scores,
        language_rollups=language_rollups,
        benchmark_overview=SummaryCompareBenchmarkOverview(
            summary_benchmark_score=task_family_scores.get(
                "summary_benchmark_score",
                SummaryCompareMetricResult(status="not_applicable"),
            ),
            compare_benchmark_score=task_family_scores.get(
                "compare_benchmark_score",
                SummaryCompareMetricResult(status="not_applicable"),
            ),
            dataset_count=len(packages),
            not_applicable_metrics=sorted(
                metric_name
                for metric_name, result in aggregate_metrics.items()
                if result.status != "scored"
            ),
        ),
        aggregate_metrics=aggregate_metrics,
        per_item_results=per_item_results,
        baseline_compare=baseline_compare,
    )


def _build_offline_rubric_result(
    *,
    decision_payload: dict[str, object],
    model: str,
) -> SummaryCompareRubricJudgeResult:
    """將離線 decision 轉成 benchmark rubric judge 結果。

    參數：
    - `decision_payload`：離線回填結果。
    - `model`：judge 標籤。

    回傳：
    - `SummaryCompareRubricJudgeResult`：rubric judge 結果。
    """

    payload = SummaryCompareJudgeCompletionPayload.model_validate(decision_payload)
    return SummaryCompareRubricJudgeResult(
        model=model,
        scores=SummaryCompareJudgeRubricScores(
            completeness=payload.scores.completeness,
            faithfulness_to_citations=payload.scores.faithfulness_to_citations,
            structure_quality=payload.scores.structure_quality,
            compare_coverage=payload.scores.compare_coverage,
        ),
        rationale=payload.rationale.strip(),
        missing_points=[point.strip() for point in payload.missing_points if point.strip()],
    )


def _build_offline_pairwise_result(
    *,
    decision_payload: dict[str, object],
    model: str,
) -> SummaryComparePairwiseJudgeResult:
    """將離線 decision 轉成 benchmark pairwise judge 結果。

    參數：
    - `decision_payload`：離線回填結果。
    - `model`：judge 標籤。

    回傳：
    - `SummaryComparePairwiseJudgeResult`：pairwise judge 結果。
    """

    payload = SummaryComparePairwiseCompletionPayload.model_validate(decision_payload)
    verdict = payload.verdict
    score = 1.0 if verdict == "candidate" else 0.5 if verdict == "tie" else 0.0
    return SummaryComparePairwiseJudgeResult(
        model=model,
        verdict=verdict,
        rationale=payload.rationale.strip(),
        score=score,
    )


def _run_rubric_judge(
    *,
    rubric_judge: RubricJudge | None,
    checkpoint_item: SummaryCompareCheckpointItem,
    execution: SummaryCompareExecution,
) -> tuple[SummaryCompareRubricJudgeResult | None, bool]:
    """執行 supporting rubric judge 並轉成新 schema。

    參數：
    - `rubric_judge`：可選 judge。
    - `checkpoint_item`：checkpoint 相容題目。
    - `execution`：runtime 執行結果。

    回傳：
    - `tuple[SummaryCompareRubricJudgeResult | None, bool]`：judge 結果與是否失敗。
    """

    if rubric_judge is None:
        return None, True
    try:
        result = rubric_judge.judge(
            item=checkpoint_item,
            answer=execution.answer,
            citations=execution.citations,
            trace=execution.trace,
        )
    except Exception:  # pragma: no cover - 依賴細節由整合環境決定。
        return None, True
    return (
        SummaryCompareRubricJudgeResult(
            model=result.model,
            scores=SummaryCompareJudgeRubricScores(
                completeness=result.scores.completeness,
                faithfulness_to_citations=result.scores.faithfulness_to_citations,
                structure_quality=result.scores.structure_quality,
                compare_coverage=result.scores.compare_coverage,
            ),
            rationale=result.rationale,
            missing_points=list(result.missing_points),
        ),
        False,
    )


def _build_checkpoint_item_from_benchmark_item(*, item: SummaryCompareBenchmarkItem) -> SummaryCompareCheckpointItem:
    """將新 benchmark item 轉為 checkpoint 相容 item。

    參數：
    - `item`：新 benchmark 題目。

    回傳：
    - `SummaryCompareCheckpointItem`：供共用 execution/judge 流程使用的 item。
    """

    return SummaryCompareCheckpointItem.model_validate(
        {
            "id": item.id,
            "language": item.language.value,
            "question": item.question,
            "expected_query_type": item.task_type,
            "expected_summary_strategy": item.summary_strategy if isinstance(item, SummaryBenchmarkItem) else None,
            "expected_document_names": item.expected_document_names,
            "expected_section_headings": (
                item.expected_section_headings if isinstance(item, SummaryBenchmarkItem) and item.expected_section_headings else ["document"]
            ) if isinstance(item, SummaryBenchmarkItem) else ["compare"],
            "required_claims_or_compare_axes": item.required_claims_or_axes,
            "gold_span_refs": [gold_ref.model_dump(mode="json") for gold_ref in item.gold_span_refs],
            "allows_insufficient_evidence": item.allows_insufficient_evidence,
        }
    )


def _validate_item_retrieval_scope(
    *,
    item: SummaryCompareBenchmarkItem,
    ready_documents_by_name: dict[str, Document],
    ready_documents_by_id: dict[str, Document],
) -> SummaryCompareScopeValidationResult:
    """驗證 benchmark/test explicit document scope。

    參數：
    - `item`：benchmark 題目。
    - `ready_documents_by_name`：以檔名索引的 ready 文件。
    - `ready_documents_by_id`：以 id 索引的 ready 文件。

    回傳：
    - `SummaryCompareScopeValidationResult`：驗證結果。
    """

    scope = item.retrieval_scope
    if scope.mode == "routing":
        return SummaryCompareScopeValidationResult(mode="routing")

    validation_errors: list[str] = []
    resolved_document_ids: list[str] = []
    for document_id in scope.document_ids:
        document = ready_documents_by_id.get(document_id)
        if document is None:
            validation_errors.append(f"invalid_document_id:{document_id}")
            continue
        resolved_document_ids.append(document.id)
    for file_name in scope.document_file_names:
        document = ready_documents_by_name.get(file_name)
        if document is None:
            validation_errors.append(f"invalid_document_file_name:{file_name}")
            continue
        resolved_document_ids.append(document.id)

    deduplicated_document_ids = list(dict.fromkeys(resolved_document_ids))
    return SummaryCompareScopeValidationResult(
        mode="explicit_document_ids",
        requested_document_ids=list(scope.document_ids),
        requested_document_file_names=list(scope.document_file_names),
        resolved_document_ids=deduplicated_document_ids,
        validation_status="invalid" if validation_errors else "validated",
        validation_errors=validation_errors,
    )


def _load_ready_documents_by_id(*, session: Session, area_id: str) -> dict[str, Document]:
    """載入指定 area 內的 ready 文件並以 id 建索引。

    參數：
    - `session`：目前資料庫 session。
    - `area_id`：目標 area。

    回傳：
    - `dict[str, Document]`：以文件 id 為 key 的 ready 文件映射。
    """

    documents = session.scalars(
        select(Document).where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
        )
    ).all()
    return {document.id: document for document in documents}


def _build_per_dataset_scores(
    *,
    packages: list[_BenchmarkPackage],
    per_item_results: list[SummaryCompareBenchmarkPerItemResult],
) -> list[SummaryCompareDatasetScoreSummary]:
    """依 package 聚合 benchmark 分數。

    參數：
    - `packages`：benchmark packages。
    - `per_item_results`：所有單題結果。

    回傳：
    - `list[SummaryCompareDatasetScoreSummary]`：每個 package 的分數摘要。
    """

    per_package_items: dict[str, list[SummaryCompareBenchmarkPerItemResult]] = defaultdict(list)
    for item_result in per_item_results:
        per_package_items[item_result.benchmark_name].append(item_result)

    summaries: list[SummaryCompareDatasetScoreSummary] = []
    for package in packages:
        item_results = per_package_items[package.manifest.benchmark_name]
        main_metric = SUMMARY_MAIN_SCORE_METRIC if package.manifest.task_family == "summary" else COMPARE_MAIN_SCORE_METRIC
        main_score = _average_metric_results(
            metric_results=[item_result.metrics[main_metric] for item_result in item_results],
        )
        supporting_metrics = {
            metric_name: _average_metric_results(
                metric_results=[item_result.metrics[metric_name] for item_result in item_results if metric_name in item_result.metrics]
            )
            for metric_name in (
                "qafacteval_score",
                "required_document_coverage",
                "citation_coverage",
                "section_coverage",
                "required_document_not_cited_rate",
                "insufficient_evidence_not_acknowledged_rate",
                "avg_overall_score",
            )
            if any(metric_name in item_result.metrics for item_result in item_results)
        }
        summaries.append(
            SummaryCompareDatasetScoreSummary(
                benchmark_name=package.manifest.benchmark_name,
                benchmark_version=package.manifest.version,
                language=package.manifest.language,
                task_family=package.manifest.task_family,
                item_count=len(item_results),
                main_score_metric=main_metric,
                main_score=main_score,
                supporting_metrics=supporting_metrics,
                partial=any(item_result.partial for item_result in item_results),
            )
        )
    return summaries


def _average_metric_results(*, metric_results: list[SummaryCompareMetricResult]) -> SummaryCompareMetricResult:
    """將單題 metric 結果做平均。

    參數：
    - `metric_results`：單題 metric 結果列表。

    回傳：
    - `SummaryCompareMetricResult`：平均後的 metric 結果。
    """

    scored_values = [metric_result.value for metric_result in metric_results if metric_result.status == "scored" and metric_result.value is not None]
    if scored_values:
        return SummaryCompareMetricResult(value=round(sum(scored_values) / len(scored_values), 6))
    if any(metric_result.status == "judge_failed" for metric_result in metric_results):
        return SummaryCompareMetricResult(status="judge_failed", reason="至少一題 judge 必要 metric 失敗。")
    return SummaryCompareMetricResult(status="not_applicable", reason="沒有可平均的有效 metric。")


def _build_task_family_scores(
    *,
    per_dataset_scores: list[SummaryCompareDatasetScoreSummary],
) -> dict[str, SummaryCompareMetricResult]:
    """建立 summary / compare 任務族群主分數。

    參數：
    - `per_dataset_scores`：各套件分數摘要。

    回傳：
    - `dict[str, SummaryCompareMetricResult]`：任務族群主分數。
    """

    summary_scores = [dataset.main_score for dataset in per_dataset_scores if dataset.task_family == "summary"]
    compare_scores = [dataset.main_score for dataset in per_dataset_scores if dataset.task_family == "compare"]
    return {
        "summary_benchmark_score": _average_metric_results(metric_results=summary_scores),
        "compare_benchmark_score": _average_metric_results(metric_results=compare_scores),
    }


def _build_language_rollups(
    *,
    per_dataset_scores: list[SummaryCompareDatasetScoreSummary],
) -> dict[str, SummaryCompareMetricResult]:
    """依語言與任務族群建立 rollup 分數。

    參數：
    - `per_dataset_scores`：各套件分數摘要。

    回傳：
    - `dict[str, SummaryCompareMetricResult]`：語言 rollup 分數。
    """

    buckets: dict[str, list[SummaryCompareMetricResult]] = defaultdict(list)
    for dataset in per_dataset_scores:
        key = f"{dataset.language.value}_{dataset.task_family}_score"
        buckets[key].append(dataset.main_score)
    return {
        key: _average_metric_results(metric_results=value)
        for key, value in sorted(buckets.items())
    }


def _build_aggregate_metrics(
    *,
    per_item_results: list[SummaryCompareBenchmarkPerItemResult],
) -> dict[str, SummaryCompareMetricResult]:
    """建立全 suite supporting aggregate metrics。

    參數：
    - `per_item_results`：所有單題結果。

    回傳：
    - `dict[str, SummaryCompareMetricResult]`：supporting aggregate metrics。
    """

    metric_names = (
        "qafacteval_score",
        "required_document_coverage",
        "citation_coverage",
        "section_coverage",
        "required_document_not_cited_rate",
        "insufficient_evidence_not_acknowledged_rate",
        "avg_overall_score",
    )
    return {
        metric_name: _average_metric_results(
            metric_results=[item_result.metrics[metric_name] for item_result in per_item_results if metric_name in item_result.metrics]
        )
        for metric_name in metric_names
        if any(metric_name in item_result.metrics for item_result in per_item_results)
    }


def _build_baseline_compare(
    *,
    packages: list[_BenchmarkPackage],
    per_dataset_scores: list[SummaryCompareDatasetScoreSummary],
) -> dict[str, object]:
    """建立與 package reference summary 的 baseline compare。

    參數：
    - `packages`：benchmark packages。
    - `per_dataset_scores`：各套件分數摘要。

    回傳：
    - `dict[str, object]`：per-dataset 與 task-family 的 baseline delta。
    """

    current_by_name = {summary.benchmark_name: summary for summary in per_dataset_scores}
    dataset_deltas: dict[str, object] = {}
    reference_task_family_values: dict[str, list[float]] = defaultdict(list)
    current_task_family_values: dict[str, list[float]] = defaultdict(list)

    for package in packages:
        current_summary = current_by_name[package.manifest.benchmark_name]
        current_main_value = current_summary.main_score.value
        if current_main_value is not None:
            current_task_family_values[package.manifest.task_family].append(current_main_value)
        reference_path = package.dataset_dir / SUMMARY_COMPARE_REFERENCE_RUN_SUMMARY_FILE
        if not reference_path.exists():
            dataset_deltas[package.manifest.benchmark_name] = {"delta": None, "reference": None, "current": current_main_value}
            continue
        payload = json.loads(reference_path.read_text(encoding="utf-8"))
        reference_value = payload.get("main_score")
        if isinstance(reference_value, (int, float)):
            reference_task_family_values[package.manifest.task_family].append(float(reference_value))
            delta = round(float(current_main_value) - float(reference_value), 6) if current_main_value is not None else None
        else:
            delta = None
            reference_value = None
        dataset_deltas[package.manifest.benchmark_name] = {
            "current": current_main_value,
            "reference": reference_value,
            "delta": delta,
        }

    task_family_delta: dict[str, object] = {}
    for task_family in ("summary", "compare"):
        current_values = current_task_family_values.get(task_family, [])
        reference_values = reference_task_family_values.get(task_family, [])
        if not current_values or not reference_values:
            task_family_delta[task_family] = {"current": None, "reference": None, "delta": None}
            continue
        current_average = round(sum(current_values) / len(current_values), 6)
        reference_average = round(sum(reference_values) / len(reference_values), 6)
        task_family_delta[task_family] = {
            "current": current_average,
            "reference": reference_average,
            "delta": round(current_average - reference_average, 6),
        }
    return {
        "per_dataset": dataset_deltas,
        "task_family": task_family_delta,
    }


def write_summary_compare_benchmark_artifacts(
    *,
    report: SummaryCompareBenchmarkReport,
    output_path: Path,
) -> tuple[Path, Path]:
    """將 benchmark report 輸出為 JSON 與 Markdown。

    參數：
    - `report`：benchmark report。
    - `output_path`：JSON 報表路徑。

    回傳：
    - `tuple[Path, Path]`：JSON 與 Markdown 路徑。
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path = output_path.with_suffix(".md")
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(build_summary_compare_benchmark_markdown(report=report), encoding="utf-8")
    return output_path, markdown_path


def build_summary_compare_benchmark_markdown(
    *,
    report: SummaryCompareBenchmarkReport,
) -> str:
    """建立 benchmark Markdown summary。

    參數：
    - `report`：benchmark report。

    回傳：
    - `str`：Markdown summary。
    """

    dataset_lines = [
        f"- `{dataset.benchmark_name}`: metric=`{dataset.main_score_metric}` "
        f"value=`{dataset.main_score.value if dataset.main_score.value is not None else dataset.main_score.status}` "
        f"partial=`{dataset.partial}`"
        for dataset in report.per_dataset_scores
    ]
    return "\n".join(
        [
            "# Summary / Compare Benchmark",
            "",
            f"- Benchmark: `{report.run_metadata.benchmark_name}` `{report.run_metadata.benchmark_version}`",
            f"- Dataset Count: `{report.run_metadata.dataset_count}`",
            f"- Item Count: `{report.run_metadata.item_count}`",
            f"- Summary Benchmark Score: `{report.benchmark_overview.summary_benchmark_score.value if report.benchmark_overview.summary_benchmark_score.value is not None else report.benchmark_overview.summary_benchmark_score.status}`",
            f"- Compare Benchmark Score: `{report.benchmark_overview.compare_benchmark_score.value if report.benchmark_overview.compare_benchmark_score.value is not None else report.benchmark_overview.compare_benchmark_score.status}`",
            f"- Parallel Workers: `{report.execution.parallel_workers}`",
            f"- Judge Failed Count: `{report.execution.judge_failed_count}`",
            f"- Partial Item Count: `{report.execution.partial_items_count}`",
            "",
            "## Per Dataset Scores",
            "",
            *(dataset_lines or ["- 無"]),
            "",
            "## Baseline Delta",
            "",
            f"```json\n{json.dumps(report.baseline_compare, ensure_ascii=False, indent=2)}\n```",
        ]
    )


def _emit_progress(*, reporter, event: dict[str, object]) -> None:
    """回報 benchmark runner 進度事件。

    參數：
    - `reporter`：可選進度回報器。
    - `event`：可序列化事件 payload。

    回傳：
    - `None`：僅在有 reporter 時呼叫。
    """

    if reporter is None:
        return
    reporter(event)
