"""Deep Agents 使用的 retrieval tool orchestration。"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.auth.verifier import CurrentPrincipal
from app.chat.contracts.types import AgentLoopTracePayload, ChatCitation, RetrievalToolTracePayload
from app.chat.tools.retrieval_planning import (
    RetrievalCoverageSignals,
    RetrievalEvidenceCue,
    RetrievalPlanningDocument,
    RetrievalSynopsisHint,
    build_coverage_signals,
    build_evidence_cue_texts,
    build_next_best_followups,
    build_planning_documents,
    build_synopsis_hints,
    load_authorized_ready_documents,
    normalize_query_variant,
    resolve_document_handles,
)
from app.chat.tools.retrieval_serialization import build_chat_citations, build_context_label
from app.core.settings import AppSettings
from app.db.models import EvaluationQueryType
from app.services.retrieval_assembler import AssembledContext, assemble_retrieval_result
from app.services.retrieval_routing import DocumentScope, SummaryStrategy, build_query_routing_decision
from app.services.retrieval_runtime import retrieve_area_candidates


@dataclass(slots=True)
class RetrievalToolResult:
    """retrieval pipeline 封裝為單一 tool 的輸出。"""

    # chat-ready contexts。
    assembled_contexts: list[AssembledContext]
    # assembled-context reference metadata。
    citations: list[ChatCitation]
    # agent follow-up 規劃可見的文件資訊。
    planning_documents: list[RetrievalPlanningDocument]
    # compare / multi-document 題的 coverage 訊號。
    coverage_signals: RetrievalCoverageSignals | None
    # 建議 agent 下一步如何補查。
    next_best_followups: list[str]
    # 供 agent / debug UI 快速理解的短 cue。
    evidence_cue_texts: list[RetrievalEvidenceCue]
    # agent 要求檢視時回傳的 synopsis hints。
    synopsis_hints: list[RetrievalSynopsisHint]
    # 單回合 follow-up trace 增量。
    loop_trace_delta: AgentLoopTracePayload
    # retrieval 與 assembler trace。
    trace: RetrievalToolTracePayload


def retrieve_area_contexts_tool(
    *,
    session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    question: str,
    task_type: EvaluationQueryType | str | None = None,
    document_scope: DocumentScope | str | None = None,
    summary_strategy: SummaryStrategy | str | None = None,
    query_variant: str | None = None,
    document_handles: list[str] | tuple[str, ...] | None = None,
    inspect_synopsis_handles: list[str] | tuple[str, ...] | None = None,
    followup_reason: str | None = None,
    rerank: bool = True,
) -> RetrievalToolResult:
    """將 retrieval、rerank 與 assembler 包成單一 tool-shaped capability。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：檢索所屬 area。
    - `question`：使用者提問。
    - `task_type`：可選的任務類型提示；不提供時由後端自動 routing。
    - `document_scope`：可選的文件範圍提示；不得攜帶 document ids，實際 ids 仍由後端解析。
    - `summary_strategy`：可選的摘要策略提示；只在 `document_summary` 下有效。
    - `query_variant`：agent follow-up 使用的單一 query variant。
    - `document_handles`：agent follow-up 使用的安全文件 handles。
    - `inspect_synopsis_handles`：要查看 synopsis hint 的安全文件 handles。
    - `followup_reason`：本次 follow-up 的簡短原因。

    回傳：
    - `RetrievalToolResult`：contexts、citations 與 trace。

    前置條件：
    - 此 tool 必須始終維持 SQL gate、same-404 與 ready-only。
    """

    return _retrieve_area_contexts_internal(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        question=question,
        task_type=task_type,
        document_scope=document_scope,
        summary_strategy=summary_strategy,
        query_variant=query_variant,
        document_handles=document_handles,
        inspect_synopsis_handles=inspect_synopsis_handles,
        followup_reason=followup_reason,
        rerank=rerank,
        allowed_document_ids_override=None,
    )


def _retrieve_area_contexts_internal(
    *,
    session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    question: str,
    task_type: EvaluationQueryType | str | None = None,
    document_scope: DocumentScope | str | None = None,
    summary_strategy: SummaryStrategy | str | None = None,
    query_variant: str | None = None,
    document_handles: list[str] | tuple[str, ...] | None = None,
    inspect_synopsis_handles: list[str] | tuple[str, ...] | None = None,
    followup_reason: str | None = None,
    allowed_document_ids_override: tuple[str, ...] | None = None,
    rerank: bool = True,
) -> RetrievalToolResult:
    """建立供 runtime 與 benchmark 共用的 internal retrieval helper。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：檢索所屬 area。
    - `question`：使用者提問。
    - `task_type`：可選的任務類型提示。
    - `document_scope`：可選的文件範圍提示。
    - `summary_strategy`：可選的摘要策略提示。
    - `query_variant`：agent follow-up 使用的單一 query variant。
    - `document_handles`：agent follow-up 使用的安全文件 handles。
    - `inspect_synopsis_handles`：要求檢視 synopsis hint 的安全文件 handles。
    - `followup_reason`：本次 follow-up 的簡短原因。
    - `allowed_document_ids_override`：benchmark/test 專用文件白名單；public tool 不應傳入。

    回傳：
    - `RetrievalToolResult`：contexts、citations 與 trace。

    前置條件：
    - benchmark/test 若傳入 `allowed_document_ids_override`，必須先完成權限與 `ready` 驗證。
    """

    authorized_ready_documents = load_authorized_ready_documents(
        session=session,
        principal=principal,
        area_id=area_id,
    )
    document_name_by_id = {
        str(document.id): str(document.file_name)
        for document in authorized_ready_documents
    }
    authorized_document_ids = tuple(document_name_by_id.keys())
    normalized_query_variant = normalize_query_variant(
        query_variant=query_variant,
        settings=settings,
    )
    scoped_document_ids = resolve_document_handles(
        handles=document_handles,
        authorized_document_ids=authorized_document_ids,
        settings=settings,
    )
    synopsis_document_ids = resolve_document_handles(
        handles=inspect_synopsis_handles,
        authorized_document_ids=authorized_document_ids,
        settings=settings,
        max_items=settings.chat_agentic_max_synopsis_inspections_per_turn,
    )
    effective_query = normalized_query_variant or question
    explicit_query_type = _coerce_optional_query_type(task_type=task_type)
    retrieval_result = retrieve_area_candidates(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        query=effective_query,
        document_scope=document_scope,
        summary_strategy=summary_strategy,
        query_type=explicit_query_type,
        allowed_document_ids_override=allowed_document_ids_override or scoped_document_ids,
        rerank=rerank,
    )
    effective_settings = build_query_routing_decision(
        settings=settings,
        query=question,
        explicit_document_scope=document_scope,
        explicit_summary_strategy=summary_strategy,
        explicit_query_type=EvaluationQueryType(retrieval_result.trace.query_type),
        session=session,
        principal=principal,
        area_id=area_id,
    ).effective_settings
    assembled_result = assemble_retrieval_result(
        session=session,
        settings=effective_settings,
        retrieval_result=retrieval_result,
    )
    retrieval_trace_payload = asdict(assembled_result.trace.retrieval)
    return RetrievalToolResult(
        assembled_contexts=assembled_result.assembled_contexts,
        citations=build_chat_citations(
            session=session,
            assembled_result=assembled_result,
            max_items=effective_settings.assembler_max_contexts,
        ),
        planning_documents=build_planning_documents(
            authorized_ready_documents=authorized_ready_documents,
            retrieval_trace=retrieval_result.trace,
            assembled_contexts=assembled_result.assembled_contexts,
        ),
        coverage_signals=build_coverage_signals(
            retrieval_trace=retrieval_trace_payload,
            assembled_contexts=assembled_result.assembled_contexts,
            document_name_by_id=document_name_by_id,
        ),
        next_best_followups=build_next_best_followups(
            retrieval_trace=retrieval_trace_payload,
            assembled_contexts=assembled_result.assembled_contexts,
            document_name_by_id=document_name_by_id,
        ),
        evidence_cue_texts=build_evidence_cue_texts(
            assembled_contexts=assembled_result.assembled_contexts,
            document_name_by_id=document_name_by_id,
            build_context_label=build_context_label,
        ),
        synopsis_hints=build_synopsis_hints(
            authorized_ready_documents=authorized_ready_documents,
            synopsis_document_ids=synopsis_document_ids,
        ),
        loop_trace_delta={
            "base_question": question,
            "effective_query": effective_query,
            "query_variant": normalized_query_variant or "",
            "scoped_document_ids": list(scoped_document_ids or ()),
            "inspect_synopsis_document_ids": list(synopsis_document_ids or ()),
            "followup_reason": (followup_reason or "").strip(),
        },
        trace={
            "retrieval": retrieval_trace_payload,
            "assembler": asdict(assembled_result.trace.assembler),
        },
    )


def _coerce_optional_query_type(*, task_type: EvaluationQueryType | str | None) -> EvaluationQueryType | None:
    """將 tool task type hint 轉成正式 enum。

    參數：
    - `task_type`：agent 或內部呼叫提供的任務類型提示。

    回傳：
    - `EvaluationQueryType | None`：成功解析後的 query type；未提供時回傳空值。
    """

    if task_type is None:
        return None
    if isinstance(task_type, EvaluationQueryType):
        return task_type
    normalized = str(task_type).strip()
    if not normalized:
        return None
    return EvaluationQueryType(normalized)
