"""`retrieve_area_contexts_tool` 與其 payload helper 測試。"""

from uuid import uuid4

import pytest

from app.auth.verifier import CurrentPrincipal
from app.chat.tools.retrieval import (
    retrieve_area_contexts_tool,
)
from app.chat.tools.retrieval_serialization import (
    build_agent_tool_payload,
    build_agent_tool_context_payload,
    build_assembled_context_payload,
    build_chat_citations,
    build_tool_call_output_summary,
)
from app.services.retrieval_types import RetrievalTrace
from app.services.retrieval_assembler import (
    AssembledContext,
    AssembledRetrievalResult,
    AssembledRetrievalTrace,
    AssemblerContextTrace,
    AssemblerTrace,
)
from app.db.models import (
    Area,
    AreaUserRole,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    EvaluationQueryType,
    Role,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def test_retrieve_area_contexts_tool_returns_context_level_contract(db_session, app_settings) -> None:
    """tool 應回傳 assembled-context level 的 contexts、citations 與 trace。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。

    回傳：
    - `None`：以斷言驗證 tool contract。
    """

    area = Area(id=_uuid(), name="Tool Contract")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="tool-contract.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-tool-contract/tool-contract.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Section",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
    )
    child_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Section",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Section",
        content="alpha details",
        content_preview="alpha details",
        char_count=13,
        start_offset=13,
        end_offset=26,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child_one,
            child_two,
        ]
    )
    db_session.commit()

    result = retrieve_area_contexts_tool(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        question="alpha",
    )

    assert len(result.assembled_contexts) == 1
    assert result.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert result.assembled_contexts[0].assembled_text == "alpha intro\n\nalpha details"
    assert len(result.citations) == 1
    assert result.citations[0].context_index == 0
    assert result.citations[0].context_label == "C1"
    assert result.citations[0].document_id == document.id
    assert result.citations[0].document_name == "tool-contract.md"
    assert result.citations[0].parent_chunk_id == parent.id
    assert result.citations[0].child_chunk_ids == [child_one.id, child_two.id]
    assert result.citations[0].heading == "Section"
    assert result.citations[0].structure_kind == ChunkStructureKind.text
    assert result.citations[0].source == "hybrid"
    assert result.citations[0].excerpt == "alpha intro\n\nalpha details"
    assert result.citations[0].truncated is False
    assert result.trace["retrieval"]["query"] == "alpha"
    assert result.trace["assembler"]["kept_chunk_ids"] == [child_one.id, child_two.id]
    assert result.trace["assembler"]["contexts"][0]["context_index"] == 0
    assert result.trace["assembler"]["contexts"][0]["truncated"] is False


def test_retrieve_area_contexts_tool_accepts_orthogonal_task_type_and_scope_hints(db_session, app_settings) -> None:
    """tool 應接受 task type 與 document scope 兩個正交 hint。"""

    area = Area(id=_uuid(), name="Explicit Strategy Tool Contract")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="benefits-overview.mixed.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-explicit-strategy/benefits-overview.mixed.md",
        display_text="Leave and Flexibility\nFull-time employees receive 12 days of annual leave in the first year.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Leave and Flexibility",
        content="Full-time employees receive 12 days of annual leave in the first year.",
        content_preview="Full-time employees receive 12 days",
        char_count=68,
        start_offset=0,
        end_offset=68,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Leave and Flexibility",
        content="Full-time employees receive 12 days of annual leave in the first year.",
        content_preview="Full-time employees receive 12 days",
        char_count=68,
        start_offset=0,
        end_offset=68,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child,
        ]
    )
    db_session.commit()

    result = retrieve_area_contexts_tool(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        question="Summarize the key points of Benefits Overview, including the Chinese onboarding note.",
        task_type=EvaluationQueryType.document_summary,
        document_scope="single_document",
        summary_strategy="document_overview",
    )

    assert result.trace["retrieval"]["query_type"] == "document_summary"
    assert result.trace["retrieval"]["query_type_source"] == "explicit"
    assert result.trace["retrieval"]["document_scope"] == "single_document"
    assert result.trace["retrieval"]["summary_strategy"] == "document_overview"
    assert result.trace["retrieval"]["summary_strategy_source"] == "explicit"


def test_retrieve_area_contexts_tool_rejects_raw_document_id_override(db_session, app_settings) -> None:
    """public tool contract 不應接受原始 `document_id` override。"""

    area = Area(id=_uuid(), name="No Raw Document ID")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.commit()

    with pytest.raises(TypeError):
        retrieve_area_contexts_tool(  # type: ignore[call-arg]
            session=db_session,
            principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
            settings=app_settings,
            area_id=area.id,
            question="alpha",
            document_ids=("some-document-id",),
        )


def test_retrieve_area_contexts_tool_uses_summary_profile_budget_for_assembler(db_session, app_settings) -> None:
    """summary query 應讓 chat tool 的 assembler 使用 summary profile 的 context budget。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。

    回傳：
    - `None`：以斷言驗證 chat tool 不可回退到原始 assembler budget。
    """

    settings = app_settings.model_copy(update={"assembler_max_contexts": 2})
    area = Area(id=_uuid(), name="Summary Budget Tool Contract")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))

    parent_ids: list[str] = []
    for index in range(4):
        document = Document(
            id=_uuid(),
            area_id=area.id,
            file_name=f"summary-{index}.md",
            content_type="text/markdown",
            file_size=100,
            storage_key=f"area/summary-{index}.md",
            status=DocumentStatus.ready,
        )
        parent = DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.parent,
            structure_kind=ChunkStructureKind.text,
            position=index * 2,
            section_index=index,
            child_index=None,
            heading=f"Summary Section {index}",
            content=f"總結 文件 {index}",
            content_preview=f"總結 文件 {index}",
            char_count=len(f"總結 文件 {index}"),
            start_offset=0,
            end_offset=len(f"總結 文件 {index}"),
        )
        child = DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=parent.id,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=(index * 2) + 1,
            section_index=index,
            child_index=0,
            heading=f"Summary Section {index}",
            content=f"總結 文件 {index}",
            content_preview=f"總結 文件 {index}",
            char_count=len(f"總結 文件 {index}"),
            start_offset=0,
            end_offset=len(f"總結 文件 {index}"),
            embedding=[0.1] * settings.embedding_dimensions,
        )
        parent_ids.append(parent.id)
        db_session.add_all([document, parent, child])
    db_session.commit()

    result = retrieve_area_contexts_tool(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        question="總結這些文件",
    )

    assert result.trace["retrieval"]["selected_profile"] == "document_summary_multi_document_diversified_v1"
    assert result.trace["retrieval"]["summary_scope"] == "multi_document"
    assert result.trace["retrieval"]["selection_applied"] is True
    assert result.trace["retrieval"]["selected_document_count"] == 4
    assert result.trace["assembler"]["max_contexts"] == 12
    assert len(result.assembled_contexts) == 4
    assert len(result.citations) == 4


def test_retrieval_tool_payload_builders_follow_runtime_contract(db_session, app_settings) -> None:
    """payload helper 應輸出 runtime 與 debug UI 需要的固定欄位。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。

    回傳：
    - `None`：以斷言驗證 helper contract。
    """

    settings = app_settings.model_copy(update={"assembler_max_chars_per_context": 10})
    area = Area(id=_uuid(), name="Tool Payload")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="tool-payload.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-tool-payload/tool-payload.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Payload Section",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Payload Section",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child,
        ]
    )
    db_session.commit()

    result = retrieve_area_contexts_tool(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        question="alpha",
    )

    assembled_payload = build_assembled_context_payload(db_session, result)
    llm_payload = build_agent_tool_context_payload(db_session, result)
    summary_payload = build_tool_call_output_summary(db_session, result)

    assert assembled_payload == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "tool-payload.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child.id],
            "structure_kind": "text",
            "heading": "Payload Section",
            "excerpt": "alpha intr",
            "assembled_text": "alpha intr",
            "source": "hybrid",
            "start_offset": 0,
            "end_offset": 11,
            "page_start": None,
            "page_end": None,
            "regions": [],
            "truncated": True,
        }
    ]
    assert llm_payload == [
        {
            "context_label": "C1",
            "context_index": 0,
            "document_name": "tool-payload.md",
            "heading": "Payload Section",
            "assembled_text": "alpha intr",
        }
    ]
    assert summary_payload["contexts_count"] == 1
    assert summary_payload["citations_count"] == 1
    assert summary_payload["query_type"] == "fact_lookup"
    assert summary_payload["query_type_language"] == "en"
    assert summary_payload["query_type_source"] == "fallback"
    assert summary_payload["query_type_confidence"] == 0.0
    assert summary_payload["query_type_matched_rules"] == []
    assert summary_payload["query_type_rule_hits"] == []
    assert summary_payload["query_type_top_label"] is not None
    assert summary_payload["query_type_runner_up_label"] is not None
    assert summary_payload["query_type_embedding_margin"] >= 0.0
    assert summary_payload["query_type_fallback_used"] is False
    assert summary_payload["query_type_fallback_reason"] == "llm_fallback_unavailable"
    assert summary_payload["summary_scope"] is None
    assert summary_payload["summary_strategy"] is None
    assert summary_payload["summary_strategy_source"] == "not_applicable"
    assert summary_payload["summary_strategy_confidence"] == 0.0
    assert summary_payload["summary_strategy_rule_hits"] == []
    assert summary_payload["summary_strategy_embedding_scores"] == []
    assert summary_payload["summary_strategy_top_label"] is None
    assert summary_payload["summary_strategy_runner_up_label"] is None
    assert summary_payload["summary_strategy_embedding_margin"] == 0.0
    assert summary_payload["summary_strategy_fallback_used"] is False
    assert summary_payload["summary_strategy_fallback_reason"] is None
    assert summary_payload["document_scope"] == "area"
    assert summary_payload["resolved_document_ids"] == []
    assert summary_payload["document_mention_source"] == "none"
    assert summary_payload["document_mention_confidence"] == 0.0
    assert summary_payload["document_mention_candidates"] == []
    assert summary_payload["selected_profile"] == "fact_lookup_precision_v1"
    assert summary_payload["fallback_reason"] is None
    assert summary_payload["selection_applied"] is False
    assert summary_payload["selection_strategy"] == "disabled"
    assert summary_payload["selected_document_count"] == 1
    assert summary_payload["selected_parent_count"] == 1
    assert summary_payload["selected_document_ids"] == [document.id]
    assert summary_payload["selected_parent_ids"] == [parent.id]
    assert summary_payload["dropped_by_diversity"] == []
    assert summary_payload["profile_settings"]["vector_top_k"] == settings.retrieval_vector_top_k
    assert summary_payload["profile_settings"]["task_type_embedding_scores"]
    assert summary_payload["profile_settings"]["task_type_embedding_margin"] >= 0.0
    assert summary_payload["profile_settings"]["task_type_fallback_used"] is False
    assert summary_payload["contexts"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "tool-payload.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child.id],
            "heading": "Payload Section",
            "structure_kind": "text",
            "source": "hybrid",
            "truncated": True,
            "excerpt": "alpha intr",
        }
    ]


def test_retrieval_tool_payload_builders_accept_none() -> None:
    """payload helper 在缺少 tool result 時應回傳安全的空結構。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證空值處理。
    """

    assert build_assembled_context_payload(None, None) == []
    assert build_agent_tool_context_payload(None, None) == []
    summary_payload = build_tool_call_output_summary(None, None)

    assert summary_payload["contexts_count"] == 0
    assert summary_payload["citations_count"] == 0
    assert summary_payload["query_type"] is None
    assert summary_payload["query_type_language"] is None
    assert summary_payload["query_type_source"] is None
    assert summary_payload["query_type_confidence"] is None
    assert summary_payload["query_type_matched_rules"] == []
    assert summary_payload["query_type_rule_hits"] == []
    assert summary_payload["query_type_embedding_scores"] == []
    assert summary_payload["query_type_top_label"] is None
    assert summary_payload["query_type_runner_up_label"] is None
    assert summary_payload["query_type_embedding_margin"] is None
    assert summary_payload["query_type_fallback_used"] is None
    assert summary_payload["query_type_fallback_reason"] is None
    assert summary_payload["summary_scope"] is None
    assert summary_payload["summary_strategy"] is None
    assert summary_payload["summary_strategy_source"] is None
    assert summary_payload["summary_strategy_confidence"] is None
    assert summary_payload["summary_strategy_rule_hits"] == []
    assert summary_payload["summary_strategy_embedding_scores"] == []
    assert summary_payload["summary_strategy_top_label"] is None
    assert summary_payload["summary_strategy_runner_up_label"] is None
    assert summary_payload["summary_strategy_embedding_margin"] is None
    assert summary_payload["summary_strategy_fallback_used"] is None
    assert summary_payload["summary_strategy_fallback_reason"] is None
    assert summary_payload["document_scope"] is None
    assert summary_payload["resolved_document_ids"] == []
    assert summary_payload["document_mention_source"] is None
    assert summary_payload["document_mention_confidence"] is None
    assert summary_payload["document_mention_candidates"] == []
    assert summary_payload["selected_profile"] is None
    assert summary_payload["fallback_reason"] is None
    assert summary_payload["selection_applied"] is None
    assert summary_payload["selection_strategy"] is None
    assert summary_payload["selected_document_count"] is None
    assert summary_payload["selected_parent_count"] is None
    assert summary_payload["selected_document_ids"] == []
    assert summary_payload["selected_parent_ids"] == []
    assert summary_payload["dropped_by_diversity"] == []
    assert summary_payload["profile_settings"] == {}
    assert summary_payload["contexts"] == []


def test_build_agent_tool_payload_returns_consolidated_llm_contract(db_session, app_settings) -> None:
    """LLM tool payload 應集中由單一 helper 產生。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。

    回傳：
    - `None`：以斷言驗證提供給 LLM 的欄位契約。
    """

    area = Area(id=_uuid(), name="LLM Payload Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="llm-payload.md",
        storage_key="documents/llm-payload.md",
        content_type="text/markdown",
        file_size=123,
        status=DocumentStatus.ready,
        synopsis_text="這份文件主要描述 alpha policy。",
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Alpha Policy",
        content="alpha intro alpha detail",
        content_preview="alpha intro alpha detail",
        char_count=24,
        start_offset=0,
        end_offset=24,
        embedding=None,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Alpha Policy",
        content="alpha intro alpha detail",
        content_preview="alpha intro alpha detail",
        char_count=24,
        start_offset=0,
        end_offset=24,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child,
        ]
    )
    db_session.commit()

    result = retrieve_area_contexts_tool(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        question="compare alpha policy",
        task_type=EvaluationQueryType.cross_document_compare,
    )

    payload = build_agent_tool_payload(
        db_session,
        result,
        tool_call_count=2,
        followup_call_count=1,
        synopsis_inspection_count=0,
        latency_budget_status="degraded",
        stop_reason="continue",
    )

    assert payload["assembled_contexts"] == [
        {
            "context_label": "C1",
            "context_index": 0,
            "document_name": "llm-payload.md",
            "heading": "Alpha Policy",
            "assembled_text": "alpha intro alpha detail",
        }
    ]
    assert payload["planning_documents"] == [
        {
            "handle": result.planning_documents[0].handle,
            "document_name": "llm-payload.md",
            "mentioned_by_query": False,
            "hit_in_current_round": True,
            "synopsis_available": True,
        }
    ]
    assert payload["coverage_signals"] == {
        "missing_document_names": [],
        "supports_compare": False,
        "insufficient_evidence": True,
        "missing_compare_axes": ["共同點與差異都缺少雙邊直接證據"],
        "new_evidence_found": True,
    }
    assert payload["next_best_followups"] == ["優先找出每份文件對同一 compare 面向的直接引文，再整理共同點與差異。"]
    assert payload["evidence_cue_texts"] == [
        {
            "context_label": "C1",
            "document_name": "llm-payload.md",
            "cue_text": "alpha intro alpha detail",
        }
    ]
    assert payload["synopsis_hints"] == []
    assert payload["loop_trace_delta"]["tool_call_count"] == 2
    assert payload["loop_trace_delta"]["followup_call_count"] == 1
    assert payload["loop_trace_delta"]["latency_budget_status"] == "degraded"
    assert payload["response_contract"]["task_type"] == "cross_document_compare"


def test_build_chat_citations_normalizes_uuid_ids() -> None:
    """citation builder 應接受 PostgreSQL `UUID` 並正規化為字串。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證 UUID 正規化。
    """

    document_id = uuid4()
    parent_chunk_id = uuid4()
    child_chunk_ids = [uuid4(), uuid4()]
    assembled_result = AssembledRetrievalResult(
        assembled_contexts=[
            AssembledContext(
                document_id=document_id,  # type: ignore[arg-type]
                parent_chunk_id=parent_chunk_id,  # type: ignore[arg-type]
                chunk_ids=child_chunk_ids,  # type: ignore[arg-type]
                structure_kind=ChunkStructureKind.text,
                heading="UUID Section",
                assembled_text="uuid normalize",
                source="hybrid",
                start_offset=0,
                end_offset=14,
            )
        ],
        citations=[],
        trace=AssembledRetrievalTrace(
            retrieval=RetrievalTrace(
                query="uuid normalize",
                vector_top_k=8,
                fts_top_k=8,
                max_candidates=8,
                rerank_top_n=8,
                candidates=[],
            ),
            assembler=AssemblerTrace(
                max_contexts=4,
                max_chars_per_context=4000,
                max_children_per_parent=4,
                kept_chunk_ids=[str(item) for item in child_chunk_ids],
                dropped_chunk_ids=[],
                contexts=[
                    AssemblerContextTrace(
                        context_index=0,
                        parent_chunk_id=str(parent_chunk_id),
                        kept_chunk_ids=[str(item) for item in child_chunk_ids],
                        dropped_chunk_ids=[],
                        truncated=False,
                    )
                ],
            ),
        ),
    )

    citations = build_chat_citations(session=None, assembled_result=assembled_result, max_items=4)

    assert len(citations) == 1
    assert citations[0].context_label == "C1"
    assert citations[0].document_id == str(document_id)
    assert citations[0].parent_chunk_id == str(parent_chunk_id)
    assert citations[0].child_chunk_ids == [str(item) for item in child_chunk_ids]
