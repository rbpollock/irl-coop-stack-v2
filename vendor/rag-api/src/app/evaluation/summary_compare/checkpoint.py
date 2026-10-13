"""Phase 8A summary/compare evaluation checkpoint 服務。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.verifier import CurrentPrincipal
from app.chat.agent.runtime import DeepAgentsChatRuntime, build_chat_runtime
from app.chat.contracts.types import ChatAnswerBlock, ChatCitation, ChatTrace
from app.core.settings import AppSettings
from app.db.models import Document, DocumentStatus
from app.schemas.summary_compare_checkpoint import (
    SummaryCompareAggregateMetrics,
    SummaryCompareCheckpointItem,
    SummaryCompareCheckpointManifest,
    SummaryCompareJudgeCompletionPayload,
    SummaryCompareCheckpointReport,
    SummaryCompareGateMetric,
    SummaryCompareGoldSpanRef,
    SummaryComparePerItemDraft,
    SummaryCompareJudgeResult,
    SummaryCompareJudgeScores,
    SummaryComparePerItemResult,
    SummaryCompareResolvedGoldSpan,
    SummaryCompareRunMetadata,
)
from app.schemas.summary_compare_offline_judge import (
    SummaryCompareOfflineJudgeDecision,
    SummaryCompareOfflineJudgePacket,
)
from .offline_judge import load_offline_judge_decisions, load_offline_judge_packets


# checkpoint dataset manifest 檔名。
CHECKPOINT_MANIFEST_FILE = "manifest.json"
# checkpoint 題目檔名。
CHECKPOINT_QUESTIONS_FILE = "questions.jsonl"
# checkpoint 固定最多並行執行的題數。
CHECKPOINT_MAX_PARALLEL_WORKERS = 6

# compare/證據不足題回答至少要出現的提示語。
INSUFFICIENT_EVIDENCE_PATTERNS = (
    "證據不足",
    "資訊不足",
    "無法確認",
    "需要回看",
    "insufficient evidence",
    "not enough evidence",
    "cannot confirm",
    "need to verify",
)


class SummaryCompareProgressEvent(TypedDict, total=False):
    """checkpoint 執行期間的可序列化進度事件。"""

    # 事件名稱。
    event: str
    # 所屬題目識別碼。
    item_id: str
    # 目前完成題數。
    completed_items: int
    # 題目總數。
    total_items: int
    # 補充說明。
    message: str


class SummaryCompareJudge(Protocol):
    """summary/compare checkpoint judge 介面。"""

    def judge(
        self,
        *,
        item: SummaryCompareCheckpointItem,
        answer: str,
        citations: list[ChatCitation],
        trace: ChatTrace,
    ) -> SummaryCompareJudgeResult:
        """對單題結果打分。

        參數：
        - `item`：checkpoint fixture 題目。
        - `answer`：runtime 最終回答。
        - `citations`：runtime 最終 citations。
        - `trace`：runtime trace。

        回傳：
        - `SummaryCompareJudgeResult`：judge 結果。
        """


class SummaryCompareProgressReporter(Protocol):
    """checkpoint 執行期間的進度回報介面。"""

    def __call__(self, event: SummaryCompareProgressEvent) -> None:
        """回報單次 checkpoint 進度事件。

        參數：
        - `event`：可序列化的進度事件。

        回傳：
        - `None`：僅做回報。
        """


@dataclass(slots=True)
class SummaryCompareExecution:
    """單題 chat runtime 執行結果。"""

    # 最終回答文字。
    answer: str
    # 最終回答區塊。
    answer_blocks: list[ChatAnswerBlock]
    # 最終 citations。
    citations: list[ChatCitation]
    # runtime trace。
    trace: ChatTrace
    # 整體 wall-clock latency。
    latency_seconds: float
    # 是否觸發 timeout。
    timed_out: bool

    def __post_init__(self) -> None:
        """將測試或離線路徑傳入的 dict payload 正規化為正式模型。"""

        self.answer_blocks = [
            item if isinstance(item, ChatAnswerBlock) else ChatAnswerBlock.model_validate(item)
            for item in self.answer_blocks
        ]
        self.citations = [_normalize_chat_citation(citation) for citation in self.citations]
        self.trace = _normalize_chat_trace(self.trace)


@dataclass(slots=True)
class _CheckpointEvaluationContext:
    """單題 checkpoint 在 judge 前的上下文。"""

    # 單題結果 payload，尚未包含 judge_result。
    base_payload: SummaryComparePerItemDraft
    # 若已有可直接使用的 judge 結果，則不需外部 judge。
    seeded_judge_result: SummaryCompareJudgeResult | None
    # 若需外部 judge，保存 system prompt。
    system_prompt: str | None
    # 若需外部 judge，保存 user prompt。
    user_prompt: str | None


class OpenAISummaryCompareJudge:
    """使用 OpenAI Chat Completions 的 LLM-as-judge。"""

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float = 30.0, max_attempts: int = 3) -> None:
        """初始化 OpenAI judge。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：judge model 名稱。
        - `timeout_seconds`：單次請求 timeout。
        - `max_attempts`：最多重試次數。

        回傳：
        - `None`：僅保存設定與建立 client。
        """

        from openai import OpenAI

        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)

    def judge(
        self,
        *,
        item: SummaryCompareCheckpointItem,
        answer: str,
        citations: list[ChatCitation],
        trace: ChatTrace,
    ) -> SummaryCompareJudgeResult:
        """呼叫 OpenAI 對單題結果打分。

        參數：
        - `item`：checkpoint fixture 題目。
        - `answer`：runtime 最終回答。
        - `citations`：runtime 最終 citations。
        - `trace`：runtime trace。

        回傳：
        - `SummaryCompareJudgeResult`：judge 結果。
        """

        system_prompt, user_prompt = build_summary_compare_judge_prompt(
            item=item,
            answer=answer,
            citations=citations,
            trace=trace,
        )
        response = self._create_completion_with_retry(system_prompt=system_prompt, user_prompt=user_prompt)
        content = response.choices[0].message.content or "{}"
        payload = SummaryCompareJudgeCompletionPayload.model_validate(json.loads(content))
        return SummaryCompareJudgeResult(
            model=self._model,
            scores=payload.scores,
            coverage_dimension_name=(payload.coverage_dimension_name or _resolve_coverage_dimension_name(item)).strip(),
            rationale=payload.rationale.strip(),
            missing_points=[point.strip() for point in payload.missing_points if point.strip()],
        )

    def _create_completion_with_retry(self, *, system_prompt: str, user_prompt: str):
        """呼叫 OpenAI completion，必要時對可恢復錯誤重試。

        參數：
        - `system_prompt`：judge system prompt。
        - `user_prompt`：judge user prompt。

        回傳：
        - `ChatCompletion`：OpenAI 回應物件。
        """

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._client.chat.completions.create(
                    model=self._model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
            except Exception as exc:  # pragma: no cover - 具體錯誤型別由整合測試覆蓋。
                last_error = exc
                if not _is_retryable_judge_error(exc=exc) or attempt >= self._max_attempts:
                    raise
                time.sleep(min(2.0 * attempt, self._timeout_seconds))
        if last_error is not None:  # pragma: no cover - 防禦性分支。
            raise last_error
        raise RuntimeError("judge retry loop 未取得 completion 且沒有錯誤資訊。")


def build_summary_compare_judge_prompt(
    *,
    item: SummaryCompareCheckpointItem,
    answer: str,
    citations: list[ChatCitation],
    trace: ChatTrace,
) -> tuple[str, str]:
    """建立 summary/compare judge prompt。

    參數：
    - `item`：checkpoint fixture 題目。
    - `answer`：runtime 最終回答。
    - `citations`：runtime 最終 citations。
    - `trace`：runtime trace。

    回傳：
    - `tuple[str, str]`：system prompt 與 user prompt。
    """

    normalized_citations = [_normalize_chat_citation(citation) for citation in citations]
    normalized_trace = _normalize_chat_trace(trace)
    coverage_dimension_name = _resolve_coverage_dimension_name(item)
    system_prompt = (
        "你是嚴格的 RAG summary/compare checkpoint judge。"
        "你只能根據題目、回答、引用片段與 rubric 打分，不可腦補未被引用的內容。"
        "若回答超出引用證據，faithfulness_to_citations 必須降低。"
        "請輸出 JSON object，欄位固定為 "
        "`scores`、`coverage_dimension_name`、`rationale`、`missing_points`。"
        "scores 需包含 completeness、faithfulness_to_citations、structure_quality、compare_coverage，"
        "每項分數只能是 1 到 5 的數字。"
    )
    citation_payload = [
        {
            "context_label": citation.context_label,
            "document_name": citation.document_name,
            "heading": citation.heading,
            "excerpt": citation.excerpt[:800],
        }
        for citation in normalized_citations[:8]
    ]
    user_payload = {
        "question": item.question,
        "expected_query_type": item.expected_query_type.value,
        "expected_summary_strategy": item.expected_summary_strategy,
        "expected_document_names": item.expected_document_names,
        "expected_section_headings": item.expected_section_headings,
        "required_claims_or_compare_axes": item.required_claims_or_compare_axes,
        "coverage_dimension_name": coverage_dimension_name,
        "allows_insufficient_evidence": item.allows_insufficient_evidence,
        "answer": answer,
        "citations": citation_payload,
        "trace_summary": {
            "actual_query_type": normalized_trace.retrieval.get("query_type"),
            "actual_summary_strategy": normalized_trace.retrieval.get("summary_strategy"),
            "fallback_reason": normalized_trace.retrieval.get("fallback_reason"),
            "map_reduce_trace": normalized_trace.agent.get("map_reduce_trace"),
        },
        "rubric": {
            "completeness": "回答是否覆蓋 required_claims_or_compare_axes，且不遺漏主要重點。",
            "faithfulness_to_citations": "回答是否忠於 citations 提供的可見證據，不能補腦。",
            "structure_quality": "是否符合 summary/compare 的固定輸出結構與可讀性。",
            "compare_coverage": (
                f"本題第四維請評 `{coverage_dimension_name}`。"
                "若為 compare 題，檢查共通點/差異點/各文件立場/證據不足是否有被覆蓋；"
                "若非 compare 題，檢查回答是否真的聚焦到預期章節。"
            ),
        },
    }
    return system_prompt, json.dumps(user_payload, ensure_ascii=False, indent=2)


def _normalize_chat_citation(citation: ChatCitation | dict[str, object]) -> ChatCitation:
    """將正式 citation 或舊式精簡 dict 正規化為 `ChatCitation`。"""

    if isinstance(citation, ChatCitation):
        return citation

    context_index = citation.get("context_index")
    normalized_context_index = context_index if isinstance(context_index, int) else 0
    context_label = citation.get("context_label")
    normalized_context_label = (
        context_label
        if isinstance(context_label, str) and context_label.strip()
        else f"C{normalized_context_index + 1}"
    )
    page_start = citation.get("page_start")
    page_end = citation.get("page_end")
    return ChatCitation.model_validate(
        {
            "context_index": normalized_context_index,
            "context_label": normalized_context_label,
            "document_id": str(citation.get("document_id", "") or ""),
            "document_name": str(citation.get("document_name", "") or ""),
            "parent_chunk_id": (
                str(citation.get("parent_chunk_id"))
                if citation.get("parent_chunk_id") is not None
                else None
            ),
            "child_chunk_ids": [str(item) for item in citation.get("child_chunk_ids", [])],
            "heading": str(citation.get("heading")).strip() if isinstance(citation.get("heading"), str) else None,
            "structure_kind": str(citation.get("structure_kind", "text") or "text"),
            "start_offset": int(citation.get("start_offset", 0) or 0),
            "end_offset": int(citation.get("end_offset", 0) or 0),
            "excerpt": str(citation.get("excerpt", "") or ""),
            "source": str(citation.get("source", "benchmark") or "benchmark"),
            "truncated": bool(citation.get("truncated", False)),
            "page_start": page_start if isinstance(page_start, int) else None,
            "page_end": page_end if isinstance(page_end, int) else None,
            "regions": citation.get("regions", []),
        }
    )


def _normalize_chat_trace(trace: ChatTrace | dict[str, object]) -> ChatTrace:
    """將正式 trace 或舊式 dict 正規化為 `ChatTrace`。"""

    if isinstance(trace, ChatTrace):
        return trace
    retrieval = trace.get("retrieval", {})
    assembler = trace.get("assembler", {})
    agent = trace.get("agent", {})
    return ChatTrace.model_validate(
        {
            "retrieval": retrieval if isinstance(retrieval, dict) else {},
            "assembler": assembler if isinstance(assembler, dict) else {},
            "agent": agent if isinstance(agent, dict) else {},
        }
    )


def load_summary_compare_checkpoint_dataset(
    *,
    dataset_dir: Path,
) -> tuple[SummaryCompareCheckpointManifest, list[SummaryCompareCheckpointItem]]:
    """讀取 checkpoint dataset。

    參數：
    - `dataset_dir`：checkpoint dataset 目錄。

    回傳：
    - `tuple[SummaryCompareCheckpointManifest, list[SummaryCompareCheckpointItem]]`：manifest 與題目列表。
    """

    manifest_path = dataset_dir / CHECKPOINT_MANIFEST_FILE
    questions_path = dataset_dir / CHECKPOINT_QUESTIONS_FILE
    if not manifest_path.exists():
        raise ValueError(f"checkpoint dataset 缺少 {CHECKPOINT_MANIFEST_FILE}。")
    if not questions_path.exists():
        raise ValueError(f"checkpoint dataset 缺少 {CHECKPOINT_QUESTIONS_FILE}。")

    manifest = SummaryCompareCheckpointManifest.model_validate(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    items: list[SummaryCompareCheckpointItem] = []
    with questions_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            items.append(SummaryCompareCheckpointItem.model_validate(json.loads(stripped)))
    if manifest.item_count != len(items):
        raise ValueError(
            f"checkpoint manifest.item_count={manifest.item_count} 與 questions.jsonl 實際題數 {len(items)} 不一致。"
        )
    return manifest, items


def run_summary_compare_checkpoint(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    dataset_dir: Path,
    thinking_mode: bool = True,
    judge_model: str | None = None,
    judge: SummaryCompareJudge | None = None,
    progress_reporter: SummaryCompareProgressReporter | None = None,
) -> SummaryCompareCheckpointReport:
    """執行 Phase 8A summary/compare checkpoint。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：應用程式設定。
    - `area_id`：目標 area 識別碼。
    - `actor_sub`：以哪個使用者身分執行。
    - `dataset_dir`：checkpoint dataset 目錄。
    - `thinking_mode`：是否保留 thinking mode metadata。
    - `judge_model`：覆寫 judge model 名稱。
    - `judge`：可注入的 fake / custom judge。
    - `progress_reporter`：可選的進度事件回報器。

    回傳：
    - `SummaryCompareCheckpointReport`：完整 checkpoint 報表。
    """

    manifest, items = load_summary_compare_checkpoint_dataset(dataset_dir=dataset_dir)
    principal = CurrentPrincipal(sub=actor_sub, groups=())
    resolved_judge_model = judge_model or settings.summary_compare_eval_judge_model
    resolved_judge = judge or build_summary_compare_judge(settings=settings, judge_model=resolved_judge_model)
    per_item_results: list[SummaryComparePerItemResult] = []
    ready_documents = _load_ready_documents_by_name(session=session, area_id=area_id)
    session_factory = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    item_index_by_id = {item.id: index for index, item in enumerate(items, start=1)}

    with ThreadPoolExecutor(max_workers=CHECKPOINT_MAX_PARALLEL_WORKERS) as executor:
        future_to_item: dict[object, SummaryCompareCheckpointItem] = {}
        for item in items:
            future = executor.submit(
                _run_single_checkpoint_item,
                session_factory=session_factory,
                settings=settings,
                principal=principal,
                area_id=area_id,
                item=item,
                thinking_mode=thinking_mode,
                judge=resolved_judge,
                judge_model=resolved_judge_model,
                ready_documents=ready_documents,
            )
            future_to_item[future] = item
            _emit_checkpoint_progress(
                reporter=progress_reporter,
                event={
                    "type": "item_started",
                    "item_id": item.id,
                    "current": item_index_by_id[item.id],
                    "total": len(items),
                    "thinking_mode": thinking_mode,
                },
            )

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            result = future.result()
            per_item_results.append(result)
            _emit_checkpoint_progress(
                reporter=progress_reporter,
                event={
                    "type": "item_completed",
                    "item_id": item.id,
                    "current": item_index_by_id[item.id],
                    "total": len(items),
                    "thinking_mode": thinking_mode,
                    "elapsed_seconds": result.latency_seconds,
                    "task_type_matched": result.task_type_matched,
                    "summary_strategy_matched": result.summary_strategy_matched,
                    "hard_blocker_failures": result.hard_blocker_failures,
                    "judge_overall": round(result.judge_result.scores.overall, 4),
                },
            )

    per_item_results.sort(key=lambda result: item_index_by_id[result.item_id])

    return _build_checkpoint_report(
        manifest=manifest,
        settings=settings,
        area_id=area_id,
        actor_sub=actor_sub,
        thinking_mode=thinking_mode,
        judge_model=resolved_judge_model,
        per_item_results=per_item_results,
    )


def export_summary_compare_checkpoint_offline_packets(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    dataset_dir: Path,
    thinking_mode: bool = True,
    judge_label: str = "offline-codex",
) -> tuple[SummaryCompareCheckpointManifest, list[SummaryCompareOfflineJudgePacket]]:
    """執行 checkpoint runtime 並匯出離線 judge packets。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：應用程式設定。
    - `area_id`：目標 area 識別碼。
    - `actor_sub`：以哪個使用者身分執行。
    - `dataset_dir`：checkpoint dataset 目錄。
    - `thinking_mode`：是否保留 thinking mode metadata。
    - `judge_label`：離線 judge 顯示標籤。

    回傳：
    - `tuple[SummaryCompareCheckpointManifest, list[SummaryCompareOfflineJudgePacket]]`：manifest 與 packet 清單。
    """

    manifest, items = load_summary_compare_checkpoint_dataset(dataset_dir=dataset_dir)
    principal = CurrentPrincipal(sub=actor_sub, groups=())
    ready_documents = _load_ready_documents_by_name(session=session, area_id=area_id)
    session_factory = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    packets: list[SummaryCompareOfflineJudgePacket] = []
    for item in items:
        context = _evaluate_checkpoint_item_context(
            session_factory=session_factory,
            settings=settings,
            principal=principal,
            area_id=area_id,
            item=item,
            thinking_mode=thinking_mode,
            ready_documents=ready_documents,
            judge_model=judge_label,
        )
        packets.append(
            SummaryCompareOfflineJudgePacket(
                packet_id=item.id,
                judge_kind="checkpoint_rubric",
                benchmark_name=manifest.benchmark_name,
                item_id=item.id,
                model_label=judge_label,
                system_prompt=context.system_prompt or "seeded-result",
                user_prompt=context.user_prompt or "seeded-result",
                context_payload=context.base_payload.model_dump(mode="json"),
                decision_required=context.seeded_judge_result is None,
                seeded_result=(
                    context.seeded_judge_result.model_dump(mode="json")
                    if context.seeded_judge_result is not None
                    else None
                ),
            )
        )
    return manifest, packets


def run_summary_compare_checkpoint_from_offline_packets(
    *,
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    dataset_dir: Path,
    thinking_mode: bool,
    judge_packets_path: Path,
    judge_results_path: Path,
    judge_label: str = "offline-codex",
) -> SummaryCompareCheckpointReport:
    """從離線 judge packet 與回填結果產生正式 checkpoint report。

    參數：
    - `settings`：應用程式設定。
    - `area_id`：目標 area 識別碼。
    - `actor_sub`：執行者 sub。
    - `dataset_dir`：checkpoint dataset 目錄。
    - `thinking_mode`：本輪是否保留 thinking mode metadata。
    - `judge_packets_path`：先前匯出的 packet JSONL。
    - `judge_results_path`：人工 / Codex 回填結果 JSONL。
    - `judge_label`：預設離線 judge 標籤。

    回傳：
    - `SummaryCompareCheckpointReport`：完整 checkpoint report。
    """

    manifest, items = load_summary_compare_checkpoint_dataset(dataset_dir=dataset_dir)
    packets = load_offline_judge_packets(packet_path=judge_packets_path)
    decisions = load_offline_judge_decisions(decision_path=judge_results_path)
    expected_item_ids = {item.id for item in items}
    per_item_results: list[SummaryComparePerItemResult] = []
    seen_item_ids: set[str] = set()
    for packet in packets:
        if packet.item_id not in expected_item_ids:
            raise ValueError(f"離線 judge packet 含未知 item_id：{packet.item_id}")
        seen_item_ids.add(packet.item_id)
        if packet.seeded_result is not None:
            judge_result = SummaryCompareJudgeResult.model_validate(packet.seeded_result)
        else:
            decision = decisions.get(packet.packet_id)
            if decision is None:
                raise ValueError(f"缺少離線 judge decision：{packet.packet_id}")
            judge_result = _build_offline_checkpoint_judge_result(
                packet=packet,
                decision_payload=decision.result,
                model=decision.model or judge_label,
            )
        item_payload = SummaryComparePerItemDraft.model_validate(packet.context_payload)
        per_item_results.append(
            SummaryComparePerItemResult.model_validate(
                {
                    **item_payload.model_dump(mode="json"),
                    "judge_result": judge_result.model_dump(mode="json"),
                }
            )
        )
    if seen_item_ids != expected_item_ids:
        missing_item_ids = sorted(expected_item_ids - seen_item_ids)
        raise ValueError(f"離線 judge packet 缺少題目：{', '.join(missing_item_ids)}")
    return _build_checkpoint_report(
        manifest=manifest,
        settings=settings,
        area_id=area_id,
        actor_sub=actor_sub,
        thinking_mode=thinking_mode,
        judge_model=judge_label,
        per_item_results=per_item_results,
    )


def _run_single_checkpoint_item(
    *,
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    principal: CurrentPrincipal,
    area_id: str,
    item: SummaryCompareCheckpointItem,
    thinking_mode: bool,
    judge: SummaryCompareJudge,
    judge_model: str,
    ready_documents: dict[str, Document],
) -> SummaryComparePerItemResult:
    """執行單題 checkpoint，供平行 worker 呼叫。

    參數：
    - `session_factory`：建立 thread-local session 的 factory。
    - `settings`：應用程式設定。
    - `principal`：執行題目的使用者。
    - `area_id`：目標 area。
    - `item`：checkpoint fixture 題目。
    - `thinking_mode`：是否保留 thinking mode metadata。
    - `judge`：本輪使用的 judge。
    - `judge_model`：judge model 名稱。
    - `ready_documents`：當前 area 內 ready 文件映射。

    回傳：
    - `SummaryComparePerItemResult`：單題完整結果。
    """

    context = _evaluate_checkpoint_item_context(
        session_factory=session_factory,
        settings=settings,
        principal=principal,
        area_id=area_id,
        item=item,
        thinking_mode=thinking_mode,
        ready_documents=ready_documents,
        judge_model=judge_model,
    )
    judge_result = context.seeded_judge_result
    if judge_result is None:
        judge_result = judge.judge(
            item=item,
            answer=context.base_payload.answer,
            citations=context.base_payload.citations,
            trace=context.base_payload.trace,
        )
    return SummaryComparePerItemResult.model_validate(
        {
            **context.base_payload.model_dump(mode="json"),
            "judge_result": judge_result.model_dump(mode="json"),
        }
    )


def _evaluate_checkpoint_item_context(
    *,
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    principal: CurrentPrincipal,
    area_id: str,
    item: SummaryCompareCheckpointItem,
    thinking_mode: bool,
    ready_documents: dict[str, Document],
    judge_model: str,
) -> _CheckpointEvaluationContext:
    """建立單題 checkpoint 在 judge 前的上下文。

    參數：
    - `session_factory`：thread-local session factory。
    - `settings`：應用程式設定。
    - `principal`：執行者 principal。
    - `area_id`：目標 area。
    - `item`：checkpoint 題目。
    - `thinking_mode`：是否保留 thinking mode metadata。
    - `ready_documents`：ready 文件映射。
    - `judge_model`：judge 標籤或模型名稱。

    回傳：
    - `_CheckpointEvaluationContext`：judge 前上下文與可選 seeded result。
    """

    with session_factory() as item_session:
        execution_started_at = time.perf_counter()
        hard_blocker_failures: list[str] = []
        try:
            execution = execute_summary_compare_item(
                session=item_session,
                settings=settings,
                principal=principal,
                area_id=area_id,
                item=item,
                thinking_mode=thinking_mode,
            )
        except Exception as exc:
            execution = SummaryCompareExecution(
                answer="",
                answer_blocks=[],
                citations=[],
                trace=ChatTrace(retrieval={}, assembler={}, agent={}),
                latency_seconds=round(time.perf_counter() - execution_started_at, 4),
                timed_out=False,
            )
            hard_blocker_failures.append(f"runtime_error:{type(exc).__name__}")
            return _CheckpointEvaluationContext(
                base_payload=SummaryComparePerItemDraft(
                    item_id=item.id,
                    language=item.language,
                    question=item.question,
                    answer="",
                    answer_blocks=[],
                    citations=[],
                    trace=ChatTrace(retrieval={}, assembler={}, agent={}),
                    actual_query_type=None,
                    actual_summary_strategy=None,
                    task_type_matched=False,
                    summary_strategy_matched=False,
                    required_document_coverage=0.0,
                    missing_required_document_names=[],
                    section_coverage=0.0,
                    citation_coverage=0.0,
                    fallback_triggered=False,
                    latency_seconds=execution.latency_seconds,
                    total_tokens=0,
                    resolved_gold_spans=[],
                    hard_blocker_failures=hard_blocker_failures,
                ),
                seeded_judge_result=_build_runtime_error_judge_result(
                    model=judge_model,
                    error_message=str(exc),
                    item=item,
                ),
                system_prompt=None,
                user_prompt=None,
            )

        trace = execution.trace
        retrieval_trace = trace.retrieval
        agent_trace = trace.agent
        agent_map_reduce_trace = (
            agent_trace.get("map_reduce_trace")
            if isinstance(agent_trace.get("map_reduce_trace"), dict)
            else {}
        )
        actual_query_type = _coerce_optional_str(retrieval_trace.get("query_type"))
        actual_summary_strategy = _coerce_optional_str(retrieval_trace.get("summary_strategy"))
        task_type_matched = actual_query_type == item.expected_query_type.value
        summary_strategy_matched = actual_summary_strategy == item.expected_summary_strategy
        if not task_type_matched:
            hard_blocker_failures.append("task_type_mismatch")
        if not summary_strategy_matched:
            hard_blocker_failures.append("summary_strategy_mismatch")

        resolved_gold_spans, span_resolution_failures = _resolve_gold_spans(
            item=item,
            ready_documents=ready_documents,
        )
        hard_blocker_failures.extend(span_resolution_failures)

        ready_document_failures = _validate_citation_ready_documents(
            citations=execution.citations,
            ready_documents=ready_documents,
        )
        hard_blocker_failures.extend(ready_document_failures)

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

        section_coverage = _compute_section_coverage(
            expected_section_headings=item.expected_section_headings,
            citations=execution.citations,
        )
        citation_coverage = _compute_citation_coverage(
            resolved_gold_spans=resolved_gold_spans,
            citations=execution.citations,
        )
        fallback_triggered = bool(
            _coerce_optional_str(retrieval_trace.get("fallback_reason"))
            or _coerce_optional_str(agent_map_reduce_trace.get("fallback_reason"))
        )
        if execution.timed_out:
            hard_blocker_failures.append("timeout")

        total_tokens = int(agent_map_reduce_trace.get("total_tokens", 0) or 0)
        if total_tokens > settings.summary_compare_eval_max_total_tokens_per_item:
            hard_blocker_failures.append("token_budget_exceeded")

        if item.allows_insufficient_evidence and not _answer_mentions_insufficient_evidence(execution.answer):
            hard_blocker_failures.append("insufficient_evidence_not_acknowledged")

        system_prompt, user_prompt = build_summary_compare_judge_prompt(
            item=item,
            answer=execution.answer,
            citations=execution.citations,
            trace=trace,
        )
        return _CheckpointEvaluationContext(
            base_payload=SummaryComparePerItemDraft(
                item_id=item.id,
                language=item.language,
                question=item.question,
                answer=execution.answer,
                answer_blocks=execution.answer_blocks,
                citations=execution.citations,
                trace=trace,
                actual_query_type=actual_query_type,
                actual_summary_strategy=actual_summary_strategy,
                task_type_matched=task_type_matched,
                summary_strategy_matched=summary_strategy_matched,
                required_document_coverage=required_document_coverage,
                missing_required_document_names=missing_required_document_names,
                section_coverage=section_coverage,
                citation_coverage=citation_coverage,
                fallback_triggered=fallback_triggered,
                latency_seconds=execution.latency_seconds,
                total_tokens=total_tokens,
                resolved_gold_spans=resolved_gold_spans,
                hard_blocker_failures=sorted(set(hard_blocker_failures)),
            ),
            seeded_judge_result=None,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


def _build_checkpoint_report(
    *,
    manifest: SummaryCompareCheckpointManifest,
    settings: AppSettings,
    area_id: str,
    actor_sub: str,
    thinking_mode: bool,
    judge_model: str,
    per_item_results: list[SummaryComparePerItemResult],
) -> SummaryCompareCheckpointReport:
    """依單題結果建立正式 checkpoint report。

    參數：
    - `manifest`：checkpoint manifest。
    - `settings`：應用程式設定。
    - `area_id`：目標 area。
    - `actor_sub`：執行者 sub。
    - `thinking_mode`：是否保留 thinking mode metadata。
    - `judge_model`：本輪 judge 標籤。
    - `per_item_results`：所有單題結果。

    回傳：
    - `SummaryCompareCheckpointReport`：完整 checkpoint report。
    """

    aggregate_metrics = _build_aggregate_metrics(per_item_results=per_item_results)
    gate_results = _build_gate_results(settings=settings, aggregate_metrics=aggregate_metrics, per_item_results=per_item_results)
    hard_blocker_failures = [
        {"item_id": item.item_id, "reasons": item.hard_blocker_failures}
        for item in per_item_results
        if item.hard_blocker_failures
    ]
    failure_category_counts = _build_failure_category_counts(per_item_results=per_item_results)
    return SummaryCompareCheckpointReport(
        passed=all(metric.passed for metric in gate_results),
        run_metadata=SummaryCompareRunMetadata(
            benchmark_name=manifest.benchmark_name,
            benchmark_version=manifest.version,
            area_id=area_id,
            actor_sub=actor_sub,
            judge_model=judge_model,
            thinking_mode=thinking_mode,
            answer_path="deepagents_unified",
            generated_at=datetime.now(UTC),
            item_count=len(per_item_results),
        ),
        aggregate_metrics=aggregate_metrics,
        judge_scores={
            "completeness": aggregate_metrics.avg_completeness,
            "faithfulness_to_citations": aggregate_metrics.avg_faithfulness_to_citations,
            "structure_quality": aggregate_metrics.avg_structure_quality,
            "compare_coverage": aggregate_metrics.avg_compare_coverage,
            "overall": aggregate_metrics.avg_overall_score,
        },
        gate_results=gate_results,
        per_item_results=per_item_results,
        hard_blocker_failures=hard_blocker_failures,
        failure_category_counts=failure_category_counts,
        recommendations=_build_recommendations(failure_category_counts=failure_category_counts),
    )


def _build_offline_checkpoint_judge_result(
    *,
    packet: SummaryCompareOfflineJudgePacket,
    decision_payload: dict[str, object],
    model: str,
) -> SummaryCompareJudgeResult:
    """將離線 decision payload 轉成 checkpoint judge 結果。

    參數：
    - `packet`：對應的離線 judge packet。
    - `decision_payload`：人工 / Codex 回填結果。
    - `model`：要寫入 report 的 judge 標籤。

    回傳：
    - `SummaryCompareJudgeResult`：可直接放進 report 的 judge 結果。
    """

    default_coverage_dimension = (
        "compare_coverage"
        if packet.context_payload.get("actual_query_type") == "cross_document_compare"
        else "section_focus_accuracy"
    )
    payload = SummaryCompareJudgeCompletionPayload.model_validate(decision_payload)
    return SummaryCompareJudgeResult(
        model=model,
        scores=payload.scores,
        coverage_dimension_name=(payload.coverage_dimension_name or default_coverage_dimension).strip()
        or default_coverage_dimension,
        rationale=payload.rationale.strip(),
        missing_points=[point.strip() for point in payload.missing_points if point.strip()],
    )


def execute_summary_compare_item(
    *,
    session: Session,
    settings: AppSettings,
    principal: CurrentPrincipal,
    area_id: str,
    item: SummaryCompareCheckpointItem,
    thinking_mode: bool = True,
    benchmark_document_ids: tuple[str, ...] | None = None,
) -> SummaryCompareExecution:
    """執行單題 summary/compare chat runtime。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：應用程式設定。
    - `principal`：執行題目的使用者。
    - `area_id`：目標 area。
    - `item`：checkpoint fixture 題目。
    - `thinking_mode`：是否保留 thinking mode metadata。
    - `benchmark_document_ids`：benchmark/test 專用文件白名單；checkpoint 正式路徑通常不提供。

    回傳：
    - `SummaryCompareExecution`：單題執行結果。
    """

    runtime = build_chat_runtime(settings)
    if not isinstance(runtime, DeepAgentsChatRuntime):
        raise ValueError("summary/compare checkpoint 需要 `CHAT_PROVIDER=deepagents` 才能走正式 runtime。")
    started_at = time.perf_counter()
    result = runtime.run(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        question=item.question,
        thinking_mode=thinking_mode,
        conversation_messages=None,
        benchmark_document_ids=benchmark_document_ids,
    )
    latency_seconds = round(time.perf_counter() - started_at, 4)
    return SummaryCompareExecution(
        answer=result.answer,
        answer_blocks=result.answer_blocks,
        citations=result.citations,
        trace=result.trace,
        latency_seconds=latency_seconds,
        timed_out=latency_seconds > settings.chat_timeout_seconds,
    )


def build_summary_compare_judge(*, settings: AppSettings, judge_model: str) -> SummaryCompareJudge:
    """建立預設 judge。

    參數：
    - `settings`：應用程式設定。
    - `judge_model`：judge model 名稱。

    回傳：
    - `SummaryCompareJudge`：可實際執行的 judge。
    """

    if not settings.openai_api_key:
        raise ValueError("執行 summary/compare checkpoint 前必須提供 OPENAI_API_KEY。")
    return OpenAISummaryCompareJudge(
        api_key=settings.openai_api_key,
        model=judge_model,
        timeout_seconds=settings.chat_timeout_seconds,
        max_attempts=3,
    )


def write_summary_compare_checkpoint_artifacts(
    *,
    report: SummaryCompareCheckpointReport,
    output_path: Path,
) -> tuple[Path, Path]:
    """將 checkpoint 報表輸出為 JSON 與 Markdown。

    參數：
    - `report`：checkpoint report。
    - `output_path`：JSON 報表輸出路徑。

    回傳：
    - `tuple[Path, Path]`：JSON 與 Markdown 的實際輸出路徑。
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path = output_path.with_suffix(".md")
    output_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(build_summary_compare_checkpoint_markdown(report=report), encoding="utf-8")
    return output_path, markdown_path


def build_summary_compare_checkpoint_markdown(*, report: SummaryCompareCheckpointReport) -> str:
    """建立 checkpoint Markdown summary。

    參數：
    - `report`：checkpoint report。

    回傳：
    - `str`：Markdown summary。
    """

    gate_lines = [
        f"- `{metric.name}`: {'PASS' if metric.passed else 'FAIL'} "
        f"(actual={metric.actual:.4f} {metric.comparator} threshold={metric.threshold:.4f})"
        for metric in report.gate_results
    ]
    failed_items = [
        f"- `{item.item_id}`: blockers={', '.join(item.hard_blocker_failures) or 'none'}; "
        f"overall={item.judge_result.scores.overall:.2f}"
        for item in report.per_item_results
        if item.hard_blocker_failures or item.judge_result.scores.overall < 3.0
    ]
    recommendation_lines = [f"- {recommendation}" for recommendation in report.recommendations] or ["- 無"]
    return "\n".join(
        [
            "# Phase 8A Summary / Compare Checkpoint",
            "",
            f"- Passed: `{report.passed}`",
            f"- Benchmark: `{report.run_metadata.benchmark_name}` `{report.run_metadata.benchmark_version}`",
            f"- Area ID: `{report.run_metadata.area_id}`",
            f"- Judge Model: `{report.run_metadata.judge_model}`",
            f"- Thinking Mode: `{report.run_metadata.thinking_mode}`",
            f"- Answer Path: `{report.run_metadata.answer_path}`",
            f"- Item Count: `{report.run_metadata.item_count}`",
            "",
            "## Aggregate Metrics",
            "",
            f"- Task Type Accuracy: `{report.aggregate_metrics.task_type_accuracy:.4f}`",
            f"- Summary Strategy Accuracy: `{report.aggregate_metrics.summary_strategy_accuracy:.4f}`",
            f"- Required Document Coverage: `{report.aggregate_metrics.required_document_coverage:.4f}`",
            f"- Citation Coverage: `{report.aggregate_metrics.citation_coverage:.4f}`",
            f"- Section Coverage: `{report.aggregate_metrics.section_coverage:.4f}`",
            f"- Fallback Rate: `{report.aggregate_metrics.fallback_rate:.4f}`",
            f"- Avg Faithfulness: `{report.aggregate_metrics.avg_faithfulness_to_citations:.4f}`",
            f"- Avg Overall Score: `{report.aggregate_metrics.avg_overall_score:.4f}`",
            f"- p95 Latency: `{report.aggregate_metrics.p95_latency_seconds:.4f}`",
            f"- Timeout Count: `{report.aggregate_metrics.timeout_count}`",
            "",
            "## Gates",
            "",
            *gate_lines,
            "",
            "## Recommendations",
            "",
            *recommendation_lines,
            "",
            "## Failed Items",
            "",
            *(failed_items or ["- 無"]),
        ]
    )


def _load_ready_documents_by_name(*, session: Session, area_id: str) -> dict[str, Document]:
    """載入指定 area 內的 ready 文件。

    參數：
    - `session`：目前資料庫 session。
    - `area_id`：目標 area。

    回傳：
    - `dict[str, Document]`：以檔名為 key 的 ready 文件映射。
    """

    documents = session.scalars(
        select(Document).where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
        )
    ).all()
    return {document.file_name: document for document in documents}


def _resolve_gold_spans(
    *,
    item: SummaryCompareCheckpointItem,
    ready_documents: dict[str, Document],
) -> tuple[list[SummaryCompareResolvedGoldSpan], list[str]]:
    """將 fixture gold span refs 對回當前 area 的 ready 文件。

    參數：
    - `item`：checkpoint fixture 題目。
    - `ready_documents`：當前 area 內 ready 文件映射。

    回傳：
    - `tuple[list[SummaryCompareResolvedGoldSpan], list[str]]`：成功對回的 spans 與失敗原因。
    """

    resolved: list[SummaryCompareResolvedGoldSpan] = []
    failures: list[str] = []
    for gold_ref in item.gold_span_refs:
        document = ready_documents.get(gold_ref.file_name)
        if document is None:
            failures.append(f"gold_span_document_missing:{gold_ref.file_name}")
            continue
        if document.display_text is None:
            failures.append(f"gold_span_display_text_missing:{gold_ref.file_name}")
            continue
        start_offset, end_offset = _resolve_single_gold_span_ref(document=document, gold_ref=gold_ref)
        if start_offset is None or end_offset is None:
            failures.append(f"gold_span_unresolved:{gold_ref.file_name}")
            continue
        resolved.append(
            SummaryCompareResolvedGoldSpan(
                file_name=gold_ref.file_name,
                document_id=document.id,
                start_offset=start_offset,
                end_offset=end_offset,
                quote=gold_ref.quote,
            )
        )
    return resolved, failures


def _resolve_single_gold_span_ref(
    *,
    document: Document,
    gold_ref: SummaryCompareGoldSpanRef,
) -> tuple[int | None, int | None]:
    """對回單一 gold span ref。

    參數：
    - `document`：目標文件。
    - `gold_ref`：gold span ref。

    回傳：
    - `tuple[int | None, int | None]`：成功時回傳 offset；失敗時回傳空值。
    """

    if gold_ref.start_offset is not None and gold_ref.end_offset is not None:
        if gold_ref.end_offset <= len(document.display_text or ""):
            return gold_ref.start_offset, gold_ref.end_offset
        return None, None

    if gold_ref.quote:
        start_offset = (document.display_text or "").find(gold_ref.quote)
        if start_offset >= 0:
            return start_offset, start_offset + len(gold_ref.quote)
    return None, None


def _validate_citation_ready_documents(
    *,
    citations: list[ChatCitation],
    ready_documents: dict[str, Document],
) -> list[str]:
    """驗證 citations 是否都來自 ready 文件。

    參數：
    - `citations`：runtime citations。
    - `ready_documents`：ready 文件映射。

    回傳：
    - `list[str]`：所有失敗原因。
    """

    ready_by_id = {document.id: document for document in ready_documents.values()}
    failures: list[str] = []
    for citation in citations:
        if citation.document_id not in ready_by_id:
            failures.append("citation_not_from_ready_document")
    return failures


def _compute_required_document_coverage(
    *,
    expected_document_names: list[str],
    citations: list[ChatCitation],
) -> float:
    """計算必需文件覆蓋率。

    參數：
    - `expected_document_names`：題目要求至少引用的文件。
    - `citations`：runtime citations。

    回傳：
    - `float`：0 到 1 的覆蓋率。
    """

    cited_document_names = {citation.document_name.strip() for citation in citations if citation.document_name.strip()}
    matched = sum(1 for file_name in expected_document_names if file_name in cited_document_names)
    return round(matched / max(1, len(expected_document_names)), 4)


def _collect_missing_required_document_names(
    *,
    expected_document_names: list[str],
    citations: list[ChatCitation],
) -> list[str]:
    """列出尚未出現在 citations 中的必需文件名稱。

    參數：
    - `expected_document_names`：題目要求至少應引用到的文件名稱。
    - `citations`：runtime citations。

    回傳：
    - `list[str]`：依 fixture 原順序保留的缺失文件名稱清單。
    """

    cited_document_names = {citation.document_name.strip() for citation in citations if citation.document_name.strip()}
    return [document_name for document_name in expected_document_names if document_name not in cited_document_names]


def _compute_section_coverage(
    *,
    expected_section_headings: list[str],
    citations: list[ChatCitation],
) -> float:
    """計算題目預期章節的覆蓋率。

    參數：
    - `expected_section_headings`：題目要求涵蓋的章節標題片段。
    - `citations`：runtime citations。
    回傳：
    - `float`：0 到 1 的覆蓋率。
    """

    observed: list[str] = []
    for citation in citations:
        if citation.heading:
            observed.append(citation.heading.casefold())
    matched = sum(1 for heading in expected_section_headings if any(heading.casefold() in item for item in observed))
    return round(matched / max(1, len(expected_section_headings)), 4)


def _compute_citation_coverage(
    *,
    resolved_gold_spans: list[SummaryCompareResolvedGoldSpan],
    citations: list[ChatCitation],
) -> float:
    """計算 citation 對 gold spans 的覆蓋率。

    參數：
    - `resolved_gold_spans`：已對回的 gold spans。
    - `citations`：runtime citations。

    回傳：
    - `float`：0 到 1 的覆蓋率。
    """

    if not resolved_gold_spans:
        return 0.0

    matched = 0
    for gold_span in resolved_gold_spans:
        if any(_citation_overlaps_gold_span(citation=citation, gold_span=gold_span) for citation in citations):
            matched += 1
    return round(matched / len(resolved_gold_spans), 4)


def _citation_overlaps_gold_span(
    *,
    citation: ChatCitation,
    gold_span: SummaryCompareResolvedGoldSpan,
) -> bool:
    """判斷 citation 是否命中 gold span。

    參數：
    - `citation`：單一 citation。
    - `gold_span`：單一 gold span。

    回傳：
    - `bool`：若 citation 與 gold span 同文件且 offset overlap，回傳真值。
    """

    if citation.document_id != gold_span.document_id:
        return False
    return citation.start_offset < gold_span.end_offset and citation.end_offset > gold_span.start_offset


def _build_aggregate_metrics(
    *,
    per_item_results: list[SummaryComparePerItemResult],
) -> SummaryCompareAggregateMetrics:
    """根據單題結果計算 aggregate metrics。

    參數：
    - `per_item_results`：所有單題結果。

    回傳：
    - `SummaryCompareAggregateMetrics`：聚合指標。
    """

    count = max(1, len(per_item_results))
    task_type_accuracy = round(sum(1 for item in per_item_results if item.task_type_matched) / count, 4)
    summary_strategy_accuracy = round(sum(1 for item in per_item_results if item.summary_strategy_matched) / count, 4)
    required_document_coverage = round(sum(item.required_document_coverage for item in per_item_results) / count, 4)
    citation_coverage = round(sum(item.citation_coverage for item in per_item_results) / count, 4)
    section_coverage = round(sum(item.section_coverage for item in per_item_results) / count, 4)
    fallback_rate = round(sum(1 for item in per_item_results if item.fallback_triggered) / count, 4)
    avg_completeness = round(sum(item.judge_result.scores.completeness for item in per_item_results) / count, 4)
    avg_faithfulness = round(
        sum(item.judge_result.scores.faithfulness_to_citations for item in per_item_results) / count, 4
    )
    avg_structure_quality = round(sum(item.judge_result.scores.structure_quality for item in per_item_results) / count, 4)
    avg_compare_coverage = round(sum(item.judge_result.scores.compare_coverage for item in per_item_results) / count, 4)
    avg_overall_score = round(sum(item.judge_result.scores.overall for item in per_item_results) / count, 4)
    latencies = sorted(item.latency_seconds for item in per_item_results)
    p95_latency_seconds = round(_percentile(latencies, 0.95), 4)
    timeout_count = sum(1 for item in per_item_results if "timeout" in item.hard_blocker_failures)
    return SummaryCompareAggregateMetrics(
        task_type_accuracy=task_type_accuracy,
        summary_strategy_accuracy=summary_strategy_accuracy,
        required_document_coverage=required_document_coverage,
        citation_coverage=citation_coverage,
        section_coverage=section_coverage,
        fallback_rate=fallback_rate,
        avg_completeness=avg_completeness,
        avg_faithfulness_to_citations=avg_faithfulness,
        avg_structure_quality=avg_structure_quality,
        avg_compare_coverage=avg_compare_coverage,
        avg_overall_score=avg_overall_score,
        p95_latency_seconds=p95_latency_seconds,
        timeout_count=timeout_count,
    )


def _build_gate_results(
    *,
    settings: AppSettings,
    aggregate_metrics: SummaryCompareAggregateMetrics,
    per_item_results: list[SummaryComparePerItemResult],
) -> list[SummaryCompareGateMetric]:
    """建立所有 gate 結果。

    參數：
    - `settings`：應用程式設定。
    - `aggregate_metrics`：聚合指標。
    - `per_item_results`：所有單題結果。

    回傳：
    - `list[SummaryCompareGateMetric]`：所有 gate 結果。
    """

    min_overall_score = min((item.judge_result.scores.overall for item in per_item_results), default=0.0)
    hard_blocker_count = sum(len(item.hard_blocker_failures) for item in per_item_results)
    return [
        _gate_metric(name="task_type_accuracy", actual=aggregate_metrics.task_type_accuracy, threshold=1.0, comparator=">="),
        _gate_metric(
            name="summary_strategy_accuracy",
            actual=aggregate_metrics.summary_strategy_accuracy,
            threshold=0.875,
            comparator=">=",
        ),
        _gate_metric(
            name="required_document_coverage",
            actual=aggregate_metrics.required_document_coverage,
            threshold=0.9,
            comparator=">=",
        ),
        _gate_metric(name="citation_coverage", actual=aggregate_metrics.citation_coverage, threshold=0.9, comparator=">="),
        _gate_metric(name="section_coverage", actual=aggregate_metrics.section_coverage, threshold=0.8, comparator=">="),
        _gate_metric(name="fallback_rate", actual=aggregate_metrics.fallback_rate, threshold=0.1, comparator="<="),
        _gate_metric(
            name="avg_faithfulness_to_citations",
            actual=aggregate_metrics.avg_faithfulness_to_citations,
            threshold=4.5,
            comparator=">=",
        ),
        _gate_metric(
            name="avg_overall_score",
            actual=aggregate_metrics.avg_overall_score,
            threshold=settings.summary_compare_eval_pass_min_avg_score,
            comparator=">=",
        ),
        _gate_metric(name="min_per_item_overall_score", actual=min_overall_score, threshold=3.0, comparator=">="),
        _gate_metric(
            name="p95_latency_seconds",
            actual=aggregate_metrics.p95_latency_seconds,
            threshold=settings.summary_compare_eval_max_p95_latency_seconds,
            comparator="<=",
        ),
        _gate_metric(name="timeout_count", actual=float(aggregate_metrics.timeout_count), threshold=0.0, comparator="=="),
        _gate_metric(name="hard_blocker_failures", actual=float(hard_blocker_count), threshold=0.0, comparator="=="),
    ]


def _gate_metric(*, name: str, actual: float, threshold: float, comparator: str) -> SummaryCompareGateMetric:
    """建立單一 gate metric。

    參數：
    - `name`：指標名稱。
    - `actual`：實際值。
    - `threshold`：門檻值。
    - `comparator`：比較運算子。

    回傳：
    - `SummaryCompareGateMetric`：單一 gate metric。
    """

    if comparator == ">=":
        passed = actual >= threshold
    elif comparator == "<=":
        passed = actual <= threshold
    elif comparator == "==":
        passed = actual == threshold
    else:  # pragma: no cover - 內部固定 comparator 不應走到此分支。
        raise ValueError(f"不支援的 comparator：{comparator}")
    return SummaryCompareGateMetric(
        name=name,
        actual=round(actual, 4),
        threshold=round(threshold, 4),
        comparator=comparator,
        passed=passed,
    )


def _build_failure_category_counts(
    *,
    per_item_results: list[SummaryComparePerItemResult],
) -> dict[str, int]:
    """彙總失敗原因分類。

    參數：
    - `per_item_results`：所有單題結果。

    回傳：
    - `dict[str, int]`：失敗原因 -> 次數。
    """

    counter: Counter[str] = Counter()
    for item in per_item_results:
        counter.update(item.hard_blocker_failures)
        if item.judge_result.scores.faithfulness_to_citations < 4.5:
            counter["judge_low_faithfulness"] += 1
        if item.judge_result.scores.completeness < 4.0:
            counter["judge_low_completeness"] += 1
        if item.judge_result.scores.structure_quality < 4.0:
            counter["judge_low_structure_quality"] += 1
        if item.judge_result.scores.compare_coverage < 4.0:
            counter["judge_low_coverage"] += 1
    return dict(counter)


def _build_recommendations(*, failure_category_counts: dict[str, int]) -> list[str]:
    """根據失敗分類產生回修建議。

    參數：
    - `failure_category_counts`：失敗原因統計。

    回傳：
    - `list[str]`：建議回修方向。
    """

    recommendations: list[str] = []
    if failure_category_counts.get("task_type_mismatch", 0):
        recommendations.append("優先調整 query type classifier 與 compare/summary cue，避免 task routing 走錯 lane。")
    if failure_category_counts.get("summary_strategy_mismatch", 0):
        recommendations.append("檢查 single-document mention resolver 與 section_focused 規則，避免摘要策略誤判。")
    if failure_category_counts.get("required_document_not_cited", 0):
        recommendations.append("檢查 document recall 與 diversified selection，確保必需文件都有代表 context 進入 synthesis。")
    if failure_category_counts.get("judge_low_faithfulness", 0):
        recommendations.append("優先收緊 synthesis 與 compare 文案，避免回答超出 citations 可支持的內容。")
    if failure_category_counts.get("judge_low_completeness", 0):
        recommendations.append("檢查 map/reduce 是否有遺漏 required claims 或 compare axes，必要時增加 refine 或 coverage guardrail。")
    if failure_category_counts.get("judge_low_coverage", 0):
        recommendations.append("檢查 section recall 與 section synopsis 命中情況，避免 section-focused 題目抓到錯章節。")
    if failure_category_counts.get("fallback_rate", 0) or failure_category_counts.get("timeout", 0):
        recommendations.append("檢查 runtime budget、section recall 與 retrieval fallback，降低 checkpoint lane 的 timeout 與 fallback。")
    return recommendations


def _resolve_coverage_dimension_name(item: SummaryCompareCheckpointItem) -> str:
    """決定本題 judge 第四維的實際名稱。

    參數：
    - `item`：checkpoint fixture 題目。

    回傳：
    - `str`：本題第四維評分名稱。
    """

    if item.expected_query_type.value == "cross_document_compare":
        return "compare_coverage"
    return "section_focus_accuracy"


def _build_runtime_error_judge_result(
    *,
    model: str,
    error_message: str,
    item: SummaryCompareCheckpointItem,
) -> SummaryCompareJudgeResult:
    """建立 runtime 失敗時的保底 judge 結果。

    參數：
    - `model`：judge model 名稱。
    - `error_message`：runtime 錯誤訊息。
    - `item`：checkpoint fixture 題目。

    回傳：
    - `SummaryCompareJudgeResult`：保底低分結果。
    """

    return SummaryCompareJudgeResult(
        model=model,
        scores=SummaryCompareJudgeScores(
            completeness=1.0,
            faithfulness_to_citations=1.0,
            structure_quality=1.0,
            compare_coverage=1.0,
        ),
        coverage_dimension_name=_resolve_coverage_dimension_name(item),
        rationale=f"runtime failed: {error_message}",
        missing_points=["runtime failure"],
    )


def _emit_checkpoint_progress(
    *,
    reporter: SummaryCompareProgressReporter | None,
    event: dict[str, object],
) -> None:
    """安全發送 checkpoint 進度事件。

    參數：
    - `reporter`：可選的進度事件回報器。
    - `event`：要送出的進度事件。

    回傳：
    - `None`：僅做回報。
    """

    if reporter is None:
        return
    reporter(event)


def _answer_mentions_insufficient_evidence(answer: str) -> bool:
    """判斷回答是否明確承認證據不足。

    參數：
    - `answer`：最終回答。

    回傳：
    - `bool`：若命中常見證據不足提示語則回傳真值。
    """

    lowered = answer.casefold()
    return any(pattern in lowered for pattern in INSUFFICIENT_EVIDENCE_PATTERNS)


def _coerce_optional_str(value: object) -> str | None:
    """將欄位安全轉成可選字串。

    參數：
    - `value`：任意輸入值。

    回傳：
    - `str | None`：清理後字串；若無值則回傳空值。
    """

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _is_retryable_judge_error(*, exc: Exception) -> bool:
    """判斷 judge 錯誤是否值得重試。

    參數：
    - `exc`：單次 OpenAI judge 錯誤。

    回傳：
    - `bool`：若屬於暫時性或 provider-side malformed-body 類錯誤則回傳真值。
    """

    message = str(exc).casefold()
    if "timed out" in message or "timeout" in message:
        return True
    if "could not parse the json body" in message:
        return True
    if "rate limit" in message or "429" in message:
        return True
    return False


def _percentile(values: list[float], percentile: float) -> float:
    """計算百分位數。

    參數：
    - `values`：已排序或未排序的數值列表。
    - `percentile`：0 到 1 之間的百分位。

    回傳：
    - `float`：指定百分位數。
    """

    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = max(0, math.ceil(len(sorted_values) * percentile) - 1)
    return float(sorted_values[index])
