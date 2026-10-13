"""Retrieval tool 結果的 chat/runtime payload serialization helper。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy import select

from app.chat.contracts.types import (
    AgentLoopTracePayload,
    AgentResponseContractPayload,
    AgentToolContextPayload,
    AgentToolPayload,
    ChatAssembledContextPayload,
    ChatCitation,
    ChatCitationRegion,
    ChatCitationRegionPayload,
    RetrievalCoverageSignalsPayload,
    RetrievalEvidenceCuePayload,
    RetrievalPlanningDocumentPayload,
    RetrievalSynopsisHintPayload,
)
from app.db.models import Document, EvaluationQueryType
from app.services.retrieval_assembler import AssembledRetrievalResult


# compare 題固定回答模板。
COMPARE_ANSWER_TEMPLATE = [
    "先逐一說明每份文件的直接證據與立場。",
    "再整理共同點與差異；只有雙方都有直接證據時才能寫成共同點。",
    "若目前已具備雙邊直接證據，直接完成比較，不要加入 required documents 或 tool coverage 狀態前言；只有真的缺少其中一方證據時，才簡短說明證據不足。",
]


def build_context_label(context_index: int) -> str:
    """建立穩定的 context 引用標籤。

    參數：
    - `context_index`：assembled context 在回傳列表中的索引。

    回傳：
    - `str`：提供給回答與 UI 使用的標籤，例如 `C1`。
    """

    return f"C{context_index + 1}"


def build_assembled_context_payload(
    session,
    retrieval_result: Any | None,
) -> list[ChatAssembledContextPayload]:
    """將 retrieval tool result 轉成前端可直接顯示的 assembled context payload。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：assembled context 列表。
    """

    if retrieval_result is None:
        return []

    fallback_document_names = collect_document_names_from_citations(retrieval_result.citations)
    document_name_by_id = load_document_names(
        session=session,
        document_ids=[str(context.document_id) for context in retrieval_result.assembled_contexts],
        fallback_names=fallback_document_names,
    )
    truncated_by_index = {
        item["context_index"]: item["truncated"]
        for item in retrieval_result.trace["assembler"]["contexts"]
    }
    payload: list[ChatAssembledContextPayload] = []
    for index, context in enumerate(retrieval_result.assembled_contexts):
        regions: list[ChatCitationRegionPayload] = [
            {
                "page_number": region.page_number,
                "region_order": region.region_order,
                "bbox_left": region.bbox_left,
                "bbox_bottom": region.bbox_bottom,
                "bbox_right": region.bbox_right,
                "bbox_top": region.bbox_top,
            }
            for region in context.regions
        ]
        payload.append(
            {
                "context_index": index,
                "context_label": build_context_label(index),
                "document_id": str(context.document_id),
                "document_name": document_name_by_id.get(str(context.document_id), ""),
                "parent_chunk_id": str(context.parent_chunk_id) if context.parent_chunk_id is not None else None,
                "child_chunk_ids": [str(chunk_id) for chunk_id in context.chunk_ids],
                "structure_kind": context.structure_kind.value,
                "heading": context.heading,
                "excerpt": context.assembled_text,
                "assembled_text": context.assembled_text,
                "source": context.source,
                "start_offset": context.start_offset,
                "end_offset": context.end_offset,
                "page_start": min((region.page_number for region in context.regions), default=None),
                "page_end": max((region.page_number for region in context.regions), default=None),
                "regions": regions,
                "truncated": truncated_by_index.get(index, False),
            }
        )
    return payload


def build_agent_tool_context_payload(
    session,
    retrieval_result: Any | None,
) -> list[AgentToolContextPayload]:
    """建立回傳給 LLM 的最小 assembled context payload。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：僅含回答所需最小欄位的 context 列表。
    """

    if retrieval_result is None:
        return []

    fallback_document_names = collect_document_names_from_citations(retrieval_result.citations)
    document_name_by_id = load_document_names(
        session=session,
        document_ids=[str(context.document_id) for context in retrieval_result.assembled_contexts],
        fallback_names=fallback_document_names,
    )

    return [
        {
            "context_label": build_context_label(index),
            "context_index": index,
            "document_name": document_name_by_id.get(str(context.document_id), ""),
            "heading": context.heading,
            "assembled_text": context.assembled_text,
        }
        for index, context in enumerate(retrieval_result.assembled_contexts)
    ]


def build_agent_tool_payload(
    session,
    retrieval_result: Any | None,
    *,
    assembled_contexts_payload: list[AgentToolContextPayload] | None = None,
    loop_trace_delta: AgentLoopTracePayload | None = None,
    tool_call_count: int,
    followup_call_count: int,
    synopsis_inspection_count: int,
    latency_budget_status: str,
    stop_reason: str,
) -> AgentToolPayload:
    """建立 `retrieve_area_contexts` 回傳給 LLM 的正式 payload。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。
    - `assembled_contexts_payload`：可選的累積 context payload；未提供時使用本次 round 結果。
    - `loop_trace_delta`：可選的 runtime 級 loop trace 覆寫。
    - `tool_call_count`：目前回合已執行的 tool call 次數。
    - `followup_call_count`：目前回合的 follow-up 次數。
    - `synopsis_inspection_count`：目前回合已檢視的 synopsis 次數。
    - `latency_budget_status`：目前 latency budget 狀態。
    - `stop_reason`：目前 agentic loop stop reason。

    回傳：
    - `dict[str, object]`：提供給 LLM 的單一 tool payload。
    """

    tool_contexts_payload = (
        list(assembled_contexts_payload)
        if assembled_contexts_payload is not None
        else build_agent_tool_context_payload(session, retrieval_result)
    )
    effective_loop_trace_delta = (
        dict(loop_trace_delta)
        if loop_trace_delta is not None
        else dict(retrieval_result.loop_trace_delta)
        if retrieval_result is not None
        else {}
    )
    include_loop_trace = bool(
        effective_loop_trace_delta
        or followup_call_count > 0
        or synopsis_inspection_count > 0
        or latency_budget_status != "normal"
        or stop_reason not in {"not_started", "continue"}
    )
    payload: AgentToolPayload = {
        "assembled_contexts": tool_contexts_payload,
        "coverage_signals": build_agent_coverage_signals_payload(retrieval_result),
        "planning_documents": build_agent_planning_documents_payload(retrieval_result),
        "next_best_followups": list(retrieval_result.next_best_followups) if retrieval_result is not None else [],
        "evidence_cue_texts": build_agent_evidence_cue_payload(retrieval_result),
        "synopsis_hints": build_agent_synopsis_hints_payload(retrieval_result),
        "loop_trace_delta": (
            {
                **effective_loop_trace_delta,
                "tool_call_count": tool_call_count,
                "followup_call_count": followup_call_count,
                "synopsis_inspection_count": synopsis_inspection_count,
                "latency_budget_status": latency_budget_status,
                "stop_reason": stop_reason,
            }
            if include_loop_trace
            else {}
        ),
    }
    response_contract = build_agent_response_contract_payload(session, retrieval_result)
    if response_contract is not None:
        payload["response_contract"] = response_contract
    return payload


def build_agent_response_contract_payload(
    session,
    retrieval_result: Any | None,
) -> AgentResponseContractPayload | None:
    """建立給 LLM 的回答契約提示。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `dict[str, object] | None`：僅在需要額外回答 guardrail 時回傳契約 payload。
    """

    del session
    if retrieval_result is None:
        return None

    retrieval_trace = retrieval_result.trace["retrieval"] if retrieval_result is not None else {}
    if retrieval_trace.get("query_type") != EvaluationQueryType.cross_document_compare.value:
        return None

    required_document_names = list(
        dict.fromkeys(
            document.document_name
            for document in retrieval_result.planning_documents
            if document.mentioned_by_query or document.hit_in_current_round
        )
    )
    return {
        "task_type": EvaluationQueryType.cross_document_compare.value,
        "required_document_names": required_document_names,
        "compare_answer_template": list(COMPARE_ANSWER_TEMPLATE),
    }


def build_tool_call_output_summary(
    session,
    retrieval_result: Any | None,
) -> dict[str, object]:
    """建立 custom `tool_call.completed` 事件的 debug-safe 摘要。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `dict[str, object]`：前端工具檢視可使用的摘要。
    """

    assembled_contexts_payload = build_assembled_context_payload(session, retrieval_result)
    retrieval_trace = retrieval_result.trace["retrieval"] if retrieval_result is not None else {}
    response_contract = build_agent_response_contract_payload(session, retrieval_result)
    payload = {
        "contexts_count": len(assembled_contexts_payload),
        "citations_count": len(retrieval_result.citations) if retrieval_result is not None else 0,
        "query_type": retrieval_trace.get("query_type"),
        "query_type_language": retrieval_trace.get("query_type_language"),
        "query_type_source": retrieval_trace.get("query_type_source"),
        "query_type_confidence": retrieval_trace.get("query_type_confidence"),
        "query_type_matched_rules": retrieval_trace.get("query_type_matched_rules", []),
        "query_type_rule_hits": retrieval_trace.get("query_type_rule_hits", []),
        "query_type_embedding_scores": retrieval_trace.get("query_type_embedding_scores", []),
        "query_type_top_label": retrieval_trace.get("query_type_top_label"),
        "query_type_runner_up_label": retrieval_trace.get("query_type_runner_up_label"),
        "query_type_embedding_margin": retrieval_trace.get("query_type_embedding_margin"),
        "query_type_fallback_used": retrieval_trace.get("query_type_fallback_used"),
        "query_type_fallback_reason": retrieval_trace.get("query_type_fallback_reason"),
        "summary_scope": retrieval_trace.get("summary_scope"),
        "summary_strategy": retrieval_trace.get("summary_strategy"),
        "summary_strategy_source": retrieval_trace.get("summary_strategy_source"),
        "summary_strategy_confidence": retrieval_trace.get("summary_strategy_confidence"),
        "summary_strategy_rule_hits": retrieval_trace.get("summary_strategy_rule_hits", []),
        "summary_strategy_embedding_scores": retrieval_trace.get("summary_strategy_embedding_scores", []),
        "summary_strategy_top_label": retrieval_trace.get("summary_strategy_top_label"),
        "summary_strategy_runner_up_label": retrieval_trace.get("summary_strategy_runner_up_label"),
        "summary_strategy_embedding_margin": retrieval_trace.get("summary_strategy_embedding_margin"),
        "summary_strategy_fallback_used": retrieval_trace.get("summary_strategy_fallback_used"),
        "summary_strategy_fallback_reason": retrieval_trace.get("summary_strategy_fallback_reason"),
        "document_scope": retrieval_trace.get("document_scope"),
        "resolved_document_ids": retrieval_trace.get("resolved_document_ids", []),
        "document_mention_source": retrieval_trace.get("document_mention_source"),
        "document_mention_confidence": retrieval_trace.get("document_mention_confidence"),
        "document_mention_candidates": retrieval_trace.get("document_mention_candidates", []),
        "selected_profile": retrieval_trace.get("selected_profile"),
        "fallback_reason": retrieval_trace.get("fallback_reason"),
        "selection_applied": retrieval_trace.get("selection_applied"),
        "selection_strategy": retrieval_trace.get("selection_strategy"),
        "selected_document_count": retrieval_trace.get("selected_document_count"),
        "selected_parent_count": retrieval_trace.get("selected_parent_count"),
        "selected_document_ids": retrieval_trace.get("selected_document_ids", []),
        "selected_parent_ids": retrieval_trace.get("selected_parent_ids", []),
        "dropped_by_diversity": retrieval_trace.get("dropped_by_diversity", []),
        "profile_settings": retrieval_trace.get("profile_settings", {}),
        "coverage_signals": (
            asdict(retrieval_result.coverage_signals)
            if retrieval_result is not None and retrieval_result.coverage_signals is not None
            else None
        ),
        "planning_documents": [
            {
                "document_name": item.document_name,
                "mentioned_by_query": item.mentioned_by_query,
                "hit_in_current_round": item.hit_in_current_round,
                "synopsis_available": item.synopsis_available,
            }
            for item in (retrieval_result.planning_documents if retrieval_result is not None else [])
        ],
        "next_best_followups": retrieval_result.next_best_followups if retrieval_result is not None else [],
        "evidence_cue_texts": [
            asdict(item)
            for item in (retrieval_result.evidence_cue_texts if retrieval_result is not None else [])
        ],
        "synopsis_hints": [
            {
                "document_name": item.document_name,
                "synopsis_text": item.synopsis_text,
            }
            for item in (retrieval_result.synopsis_hints if retrieval_result is not None else [])
        ],
        "loop_trace_delta": retrieval_result.loop_trace_delta if retrieval_result is not None else {},
        "contexts": [
            {
                "context_index": item["context_index"],
                "context_label": item["context_label"],
                "document_id": item["document_id"],
                "document_name": item["document_name"],
                "parent_chunk_id": item["parent_chunk_id"],
                "child_chunk_ids": item["child_chunk_ids"],
                "heading": item["heading"],
                "structure_kind": item["structure_kind"],
                "source": item["source"],
                "truncated": item["truncated"],
                "excerpt": item["excerpt"],
            }
            for item in assembled_contexts_payload
        ],
    }
    if response_contract is not None:
        payload["response_contract"] = response_contract
    return payload


def build_chat_citations(
    *,
    session,
    assembled_result: AssembledRetrievalResult,
    max_items: int,
) -> list[ChatCitation]:
    """將 assembler 輸出轉成 context-level references。

    參數：
    - `session`：目前資料庫 session。
    - `assembled_result`：assembler 的完整輸出。
    - `max_items`：允許保留的最大 context 數量。

    回傳：
    - `list[ChatCitation]`：一筆對應一個 assembled context 的 reference 列表。
    """

    if max_items <= 0 or not assembled_result.assembled_contexts:
        return []

    truncated_by_index = {
        context_trace.context_index: context_trace.truncated
        for context_trace in assembled_result.trace.assembler.contexts
    }
    document_name_by_id = load_document_names(
        session=session,
        document_ids=[str(context.document_id) for context in assembled_result.assembled_contexts[:max_items]],
    )
    references: list[ChatCitation] = []
    for index, context in enumerate(assembled_result.assembled_contexts[:max_items]):
        references.append(
            ChatCitation(
                context_index=index,
                context_label=build_context_label(index),
                document_id=str(context.document_id),
                document_name=document_name_by_id.get(str(context.document_id), ""),
                parent_chunk_id=str(context.parent_chunk_id) if context.parent_chunk_id is not None else None,
                child_chunk_ids=[str(chunk_id) for chunk_id in context.chunk_ids],
                heading=context.heading,
                structure_kind=context.structure_kind,
                start_offset=context.start_offset,
                end_offset=context.end_offset,
                excerpt=context.assembled_text,
                source=context.source,
                truncated=truncated_by_index.get(index, False),
                page_start=min((region.page_number for region in context.regions), default=None),
                page_end=max((region.page_number for region in context.regions), default=None),
                regions=[
                    ChatCitationRegion(
                        page_number=region.page_number,
                        region_order=region.region_order,
                        bbox_left=region.bbox_left,
                        bbox_bottom=region.bbox_bottom,
                        bbox_right=region.bbox_right,
                        bbox_top=region.bbox_top,
                    )
                    for region in context.regions
                ],
            )
        )
    return references


def build_agent_planning_documents_payload(
    retrieval_result: Any | None,
) -> list[RetrievalPlanningDocumentPayload]:
    """建立提供給 LLM 的 planning documents 欄位。"""

    if retrieval_result is None:
        return []

    payload: list[RetrievalPlanningDocumentPayload] = []
    for item in retrieval_result.planning_documents:
        planning_document = {
            "document_name": str(getattr(item, "document_name", "") or ""),
            "mentioned_by_query": bool(getattr(item, "mentioned_by_query", False)),
            "hit_in_current_round": bool(getattr(item, "hit_in_current_round", False)),
            "synopsis_available": bool(getattr(item, "synopsis_available", False)),
        }
        handle = getattr(item, "handle", None)
        if isinstance(handle, str) and handle:
            planning_document["handle"] = handle
        payload.append(planning_document)
    return payload


def build_agent_coverage_signals_payload(
    retrieval_result: Any | None,
) -> RetrievalCoverageSignalsPayload | None:
    """建立提供給 LLM 的 coverage signals 欄位。"""

    if retrieval_result is None or retrieval_result.coverage_signals is None:
        return None

    coverage_signals = retrieval_result.coverage_signals
    if isinstance(coverage_signals, dict):
        return {
            "missing_document_names": list(coverage_signals.get("missing_document_names", [])),
            "supports_compare": bool(coverage_signals.get("supports_compare", False)),
            "insufficient_evidence": bool(coverage_signals.get("insufficient_evidence", False)),
            "missing_compare_axes": list(coverage_signals.get("missing_compare_axes", [])),
            "new_evidence_found": bool(coverage_signals.get("new_evidence_found", False)),
        }

    return {
        "missing_document_names": list(getattr(coverage_signals, "missing_document_names", [])),
        "supports_compare": bool(getattr(coverage_signals, "supports_compare", False)),
        "insufficient_evidence": bool(getattr(coverage_signals, "insufficient_evidence", False)),
        "missing_compare_axes": list(getattr(coverage_signals, "missing_compare_axes", [])),
        "new_evidence_found": bool(getattr(coverage_signals, "new_evidence_found", False)),
    }


def build_agent_evidence_cue_payload(
    retrieval_result: Any | None,
) -> list[RetrievalEvidenceCuePayload]:
    """建立提供給 LLM 的 evidence cues 欄位。"""

    if retrieval_result is None:
        return []

    return [
        {
            "context_label": str(getattr(item, "context_label", "") or ""),
            "document_name": str(getattr(item, "document_name", "") or ""),
            "cue_text": str(getattr(item, "cue_text", "") or ""),
        }
        for item in retrieval_result.evidence_cue_texts
    ]


def build_agent_synopsis_hints_payload(
    retrieval_result: Any | None,
) -> list[RetrievalSynopsisHintPayload]:
    """建立提供給 LLM 的 synopsis hints 欄位。"""

    if retrieval_result is None:
        return []

    payload: list[RetrievalSynopsisHintPayload] = []
    for item in retrieval_result.synopsis_hints:
        synopsis_hint = {
            "document_name": str(getattr(item, "document_name", "") or ""),
            "synopsis_text": str(getattr(item, "synopsis_text", "") or ""),
        }
        handle = getattr(item, "handle", None)
        if isinstance(handle, str) and handle:
            synopsis_hint["handle"] = handle
        payload.append(synopsis_hint)
    return payload


def collect_document_names_from_citations(citations: list[object]) -> dict[str, str]:
    """從既有 citation payload 擷取文件名稱對照。

    參數：
    - `citations`：目前回合的 citation 清單。

    回傳：
    - `dict[str, str]`：以文件識別碼為鍵的檔名對照表。
    """

    document_name_by_id: dict[str, str] = {}
    for citation in citations:
        document_id = getattr(citation, "document_id", None)
        document_name = getattr(citation, "document_name", None)
        if isinstance(citation, dict):
            document_id = citation.get("document_id")
            document_name = citation.get("document_name")
        if isinstance(document_id, str) and isinstance(document_name, str) and document_name:
            document_name_by_id[document_id] = document_name
    return document_name_by_id


def load_document_names(
    *,
    session,
    document_ids: list[str],
    fallback_names: dict[str, str] | None = None,
) -> dict[str, str]:
    """依文件識別碼讀取檔名對照表。

    參數：
    - `session`：目前資料庫 session。
    - `document_ids`：要查詢檔名的文件識別碼列表。
    - `fallback_names`：當前 context 已知的檔名對照表。

    回傳：
    - `dict[str, str]`：以文件識別碼為鍵的檔名對照表。
    """

    unique_ids = list(dict.fromkeys(document_ids))
    if not unique_ids:
        return {}
    if session is None:
        return {
            document_id: document_name
            for document_id, document_name in (fallback_names or {}).items()
            if document_id in unique_ids
        }

    rows = session.execute(select(Document.id, Document.file_name).where(Document.id.in_(unique_ids))).all()
    document_name_by_id = {str(document_id): str(file_name) for document_id, file_name in rows}
    for document_id, document_name in (fallback_names or {}).items():
        document_name_by_id.setdefault(document_id, document_name)
    return document_name_by_id
