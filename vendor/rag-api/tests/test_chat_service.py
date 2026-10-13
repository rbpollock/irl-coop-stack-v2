"""Chat runtime 與 Deep Agents 路徑測試。"""

import json
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
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
from app.chat.agent.runtime import (
    DeepAgentsChatRuntime,
    DeterministicChatRuntime,
    _build_answer_blocks_from_markers,
    _build_agent_input_messages,
    build_chat_runtime,
)
from app.chat.agent.deep_agents import DEEP_AGENTS_SYSTEM_PROMPT
from app.services.retrieval_assembler import AssembledContext


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def _build_fake_retrieval_result(
    *,
    assembled_contexts: list[object],
    citations: list[object],
    trace: dict[str, object],
    planning_documents: list[object] | None = None,
    coverage_signals: object | None = None,
    next_best_followups: list[object] | None = None,
    evidence_cue_texts: list[object] | None = None,
    synopsis_hints: list[object] | None = None,
    loop_trace_delta: dict[str, object] | None = None,
) -> SimpleNamespace:
    """建立符合目前 retrieval tool 最小 contract 的假結果。

    參數：
    - `assembled_contexts`：assembler 輸出的 contexts。
    - `citations`：citation 列表。
    - `trace`：retrieval / assembler trace。
    - `planning_documents`：planning documents；預設空列表。
    - `coverage_signals`：可選 coverage signals。
    - `next_best_followups`：建議 follow-up 列表。
    - `evidence_cue_texts`：可選 evidence cue 列表。
    - `synopsis_hints`：可選 synopsis hints。
    - `loop_trace_delta`：loop trace 摘要。

    回傳：
    - `SimpleNamespace`：可供 runtime 與 payload builder 使用的假結果。
    """

    return SimpleNamespace(
        assembled_contexts=assembled_contexts,
        citations=citations,
        trace=trace,
        planning_documents=planning_documents or [],
        coverage_signals=coverage_signals,
        next_best_followups=next_best_followups or [],
        evidence_cue_texts=evidence_cue_texts or [],
        synopsis_hints=synopsis_hints or [],
        loop_trace_delta=loop_trace_delta or {},
    )


@dataclass
class FakePlanningDocument:
    """模擬 retrieval planning document 的最小 dataclass。"""

    document_name: str
    mentioned_by_query: bool
    hit_in_current_round: bool
    synopsis_available: bool


def test_deterministic_runtime_factory_returns_deterministic_runtime() -> None:
    """`CHAT_PROVIDER=deterministic` 應建立 deterministic runtime。

    參數：
    - 無

    回傳：
    - `None`：僅驗證 provider factory 結果型別。
    """

    settings = AppSettings(
        CHAT_PROVIDER="deterministic",
        CHAT_MODEL="deterministic-answer",
    )

    provider = build_chat_runtime(settings)

    assert isinstance(provider, DeterministicChatRuntime)
    assert provider.provider_name == "deterministic"


def test_deepagents_runtime_factory_returns_real_deepagents_runtime() -> None:
    """`CHAT_PROVIDER=deepagents` 應建立真正的 Deep Agents runtime。

    參數：
    - 無

    回傳：
    - `None`：僅驗證 provider factory 結果型別。
    """

    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=1024,
        CHAT_TIMEOUT_SECONDS=60,
        OPENAI_API_KEY="test-key",
    )

    provider = build_chat_runtime(settings)

    assert isinstance(provider, DeepAgentsChatRuntime)
    assert provider.provider_name == "deepagents"


def test_deepagents_runtime_exposes_single_retrieval_tool_without_keyword_gate(monkeypatch) -> None:
    """Deep Agents 主 agent 應自行決定是否呼叫單一 retrieval tool。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證單一 tool 暴露與無 keyword gate 強制檢索。
    """

    captured_tools: list[object] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    class FakeAgent:
        """模擬主 agent，且本案例刻意不呼叫 retrieval tool。"""

        def stream(self, _input, *, stream_mode):
            """輸出固定串流結果，模擬 agent 自行決定不查知識庫。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定的 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            return iter(
                [
                    ("messages", ({"content": "這是直接回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是直接回答。"}]}),
                ]
            )

    def fake_create_deep_agent(**kwargs):
        """記錄主 agent 暴露的 tools，並回傳假 agent。

        參數：
        - `**kwargs`：建立 agent 的參數。

        回傳：
        - `FakeAgent`：固定輸出回答的假 agent。
        """

        captured_tools.extend(kwargs.get("tools", []))
        return FakeAgent()

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", fake_create_deep_agent)

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據上傳文件回答知識區域是做什麼的？",
    )

    assert len(captured_tools) == 1
    assert result.answer == "這是直接回答。"
    assert result.trace.agent["retrieval_invoked"] is False


def test_deep_agents_system_prompt_requires_split_retrieval_for_multiple_subjects() -> None:
    """system prompt 應要求多主體題目分次呼叫 retrieval tool。

    參數：
    - 無

    回傳：
    - `None`：以字串斷言鎖住 prompt 規則。
    """

    assert "有兩個以上主體" in DEEP_AGENTS_SYSTEM_PROMPT
    assert "分別為不同主體呼叫 `retrieve_area_contexts`" in DEEP_AGENTS_SYSTEM_PROMPT
    assert "最終回答預設使用使用者提問語言" in DEEP_AGENTS_SYSTEM_PROMPT
    assert "不要把 `required_document_names`、coverage gap、tool 狀態" in DEEP_AGENTS_SYSTEM_PROMPT


def test_build_agent_input_messages_prefers_thread_history() -> None:
    """Deep Agents 輸入應優先使用 LangGraph thread 已累積的歷史訊息。

    參數：
    - 無

    回傳：
    - `None`：僅驗證歷史訊息優先順序。
    """

    history_messages = [
        {"role": "user", "content": "第一輪問題"},
        {"role": "assistant", "content": "第一輪回答"},
        {"role": "user", "content": "第二輪追問"},
    ]

    assert (
        _build_agent_input_messages(
            question="這個欄位不應被拿來覆蓋 history",
            conversation_messages=history_messages,
        )
        == history_messages
    )


def test_build_answer_blocks_from_markers_parses_context_labels() -> None:
    """回答 marker 應被解析為 answer blocks 與 display citations。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證 marker parse 結果。
    """

    clean_answer, answer_blocks = _build_answer_blocks_from_markers(
        answer="第一段重點 [[C1]]\n\n第二段綜合整理 [[C1,C2]]",
        citations_payload=[
            {
                "context_index": 0,
                "context_label": "C1",
                "document_id": "doc-1",
                "document_name": "policy.md",
                "heading": "Section A",
                "parent_chunk_id": "parent-1",
                "child_chunk_ids": ["child-1"],
                "structure_kind": "text",
                "start_offset": 0,
                "end_offset": 10,
                "excerpt": "alpha",
                "source": "hybrid",
                "truncated": False,
            },
            {
                "context_index": 1,
                "context_label": "C2",
                "document_id": "doc-1",
                "document_name": "policy.md",
                "heading": "Section B",
                "parent_chunk_id": "parent-2",
                "child_chunk_ids": ["child-2"],
                "structure_kind": "text",
                "start_offset": 20,
                "end_offset": 30,
                "excerpt": "beta",
                "source": "hybrid",
                "truncated": False,
            },
        ],
    )

    assert clean_answer == "第一段重點\n\n第二段綜合整理"
    assert [block.text for block in answer_blocks] == ["第一段重點", "第二段綜合整理"]
    assert answer_blocks[0].citation_context_indices == [0]
    assert [item.context_label for item in answer_blocks[1].display_citations] == ["C1", "C2"]



def test_deepagents_runtime_uses_conversation_history_as_agent_input(monkeypatch) -> None:
    """Deep Agents runtime 應把 LangGraph thread 累積的 messages 傳給主 agent。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證多輪對話輸入來源。
    """

    captured_inputs: list[object] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    class FakeAgent:
        """記錄 agent 輸入並回傳固定答案。"""

        def stream(self, agent_input, *, stream_mode):
            """記錄主 agent 取得的輸入內容。

            參數：
            - `agent_input`：主 agent 的輸入 payload。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定串流結果。
            """

            captured_inputs.append(agent_input)
            assert stream_mode == ["messages", "values"]
            return iter(
                [
                    ("messages", ({"content": "這是多輪回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是多輪回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent())

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )
    conversation_messages = [
        {"role": "user", "content": "第一輪：知識區域是什麼？"},
        {"role": "assistant", "content": "第一輪：知識區域是文件集合。"},
        {"role": "user", "content": "第二輪：那它的權限怎麼控管？"},
    ]

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="第二輪：那它的權限怎麼控管？",
        conversation_messages=conversation_messages,
    )

    assert result.answer == "這是多輪回答。"
    assert captured_inputs == [{"messages": conversation_messages}]


def test_deepagents_runtime_emits_phase_tool_call_and_token_custom_events(monkeypatch) -> None:
    """Deep Agents 應透過 writer 發出階段、工具呼叫與 token 事件。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證 custom phase event contract。
    """

    emitted_events: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_tool(**kwargs):
        """模擬 retrieval tool 結果。

        參數：
        - `**kwargs`：retrieval tool 參數。

        回傳：
        - `SimpleNamespace`：最小 retrieval 結果。
        """

        return _build_fake_retrieval_result(
            assembled_contexts=[],
            citations=[],
            trace={"retrieval": {"query": kwargs["question"]}, "assembler": {"contexts": []}},
        )

    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_tool)

    class FakeAgent:
        """模擬主 agent，並主動呼叫 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用的工具列表。

            回傳：
            - `None`：僅保存工具列表。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先呼叫 retrieval tool，再回傳固定串流回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定的 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            self.tools[0]()
            return iter(
                [
                    ("messages", ({"content": "這是帶搜尋流程的回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是帶搜尋流程的回答。"}]}),
                ]
            )

    def fake_create_deep_agent(**kwargs):
        """回傳會主動呼叫 retrieval tool 的假 agent。

        參數：
        - `**kwargs`：建立 agent 的參數。

        回傳：
        - `FakeAgent`：固定輸出的假 agent。
        """

        return FakeAgent(kwargs.get("tools", []))

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", fake_create_deep_agent)

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
        writer=emitted_events.append,
    )

    assert result.answer == "這是帶搜尋流程的回答。"
    phase_events = [event for event in emitted_events if event["type"] == "phase"]
    tool_events = [event for event in emitted_events if event["type"] == "tool_call"]
    assert [event["phase"] for event in phase_events] == [
        "preparing",
        "preparing",
        "thinking",
        "tool_calling",
        "searching",
        "searching",
        "tool_calling",
        "thinking",
        "drafting",
        "drafting",
        "thinking",
    ]
    assert [event["status"] for event in tool_events] == ["started", "completed"]
    assert tool_events[0]["name"] == "retrieve_area_contexts"
    assert tool_events[0]["input"]["area_id"] == "area-1"
    assert tool_events[0]["input"]["question"] == "請根據文件回答 reader policy"
    assert tool_events[0]["input"]["query_variant"] == ""
    assert tool_events[0]["input"]["document_handles"] == []
    assert tool_events[0]["input"]["inspect_synopsis_handles"] == []
    assert tool_events[0]["input"]["followup_reason"] == ""
    assert tool_events[1]["output"]["contexts_count"] == 0
    assert tool_events[1]["output"]["citations_count"] == 0
    assert tool_events[1]["output"]["query_type"] is None
    assert tool_events[1]["output"]["query_type_language"] is None
    assert tool_events[1]["output"]["query_type_source"] is None
    assert tool_events[1]["output"]["query_type_confidence"] is None
    assert tool_events[1]["output"]["query_type_matched_rules"] == []
    assert tool_events[1]["output"]["query_type_rule_hits"] == []
    assert tool_events[1]["output"]["query_type_embedding_scores"] == []
    assert tool_events[1]["output"]["query_type_top_label"] is None
    assert tool_events[1]["output"]["query_type_runner_up_label"] is None
    assert tool_events[1]["output"]["query_type_embedding_margin"] is None
    assert tool_events[1]["output"]["query_type_fallback_used"] is None
    assert tool_events[1]["output"]["query_type_fallback_reason"] is None
    assert tool_events[1]["output"]["summary_scope"] is None
    assert tool_events[1]["output"]["summary_strategy"] is None
    assert tool_events[1]["output"]["summary_strategy_source"] is None
    assert tool_events[1]["output"]["summary_strategy_confidence"] is None
    assert tool_events[1]["output"]["summary_strategy_rule_hits"] == []
    assert tool_events[1]["output"]["summary_strategy_embedding_scores"] == []
    assert tool_events[1]["output"]["summary_strategy_top_label"] is None
    assert tool_events[1]["output"]["summary_strategy_runner_up_label"] is None
    assert tool_events[1]["output"]["summary_strategy_embedding_margin"] is None
    assert tool_events[1]["output"]["summary_strategy_fallback_used"] is None
    assert tool_events[1]["output"]["summary_strategy_fallback_reason"] is None
    assert tool_events[1]["output"]["document_scope"] is None
    assert tool_events[1]["output"]["resolved_document_ids"] == []
    assert tool_events[1]["output"]["document_mention_source"] is None
    assert tool_events[1]["output"]["document_mention_confidence"] is None
    assert tool_events[1]["output"]["document_mention_candidates"] == []
    assert tool_events[1]["output"]["selected_profile"] is None
    assert tool_events[1]["output"]["fallback_reason"] is None
    assert tool_events[1]["output"]["selection_applied"] is None
    assert tool_events[1]["output"]["selection_strategy"] is None
    assert tool_events[1]["output"]["selected_document_count"] is None
    assert tool_events[1]["output"]["selected_parent_count"] is None
    assert tool_events[1]["output"]["selected_document_ids"] == []
    assert tool_events[1]["output"]["selected_parent_ids"] == []
    assert tool_events[1]["output"]["dropped_by_diversity"] == []
    assert tool_events[1]["output"]["profile_settings"] == {}
    assert tool_events[1]["output"]["contexts"] == []
    reference_events = [event for event in emitted_events if event["type"] == "references"]
    assert reference_events == [{"type": "references", "references": []}]
    token_events = [event for event in emitted_events if event["type"] == "token"]
    assert token_events == [{"type": "token", "delta": "這是帶搜尋流程的回答。"}]


def test_deepagents_runtime_summary_queries_use_unified_answer_path(monkeypatch) -> None:
    """summary query 應不再分 lane，而是統一走 Deep Agents answer path。"""

    captured_llm_kwargs: list[dict[str, object]] = []
    captured_inputs: list[object] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。"""

            self.kwargs = kwargs
            captured_llm_kwargs.append(dict(kwargs))

    class FakeAgent:
        """模擬主 agent，會主動呼叫 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, agent_input, *, stream_mode):
            """先執行 retrieval tool，再回傳固定回答。"""

            captured_inputs.append(agent_input)
            assert stream_mode == ["messages", "values"]
            self.tools[0]()
            return iter(
                [
                    ("messages", ({"content": "這是統一路徑摘要回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是統一路徑摘要回答。"}]}),
                ]
            )

    def fake_create_deep_agent(**kwargs):
        """建立固定假 agent。"""

        return FakeAgent(kwargs.get("tools", []))

    def fake_retrieve_area_contexts_tool(**kwargs):
        """回傳最小 retrieval 結果。"""

        return _build_fake_retrieval_result(
            assembled_contexts=[],
            citations=[],
            trace={"retrieval": {"query": kwargs["question"]}, "assembler": {"contexts": []}},
        )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)
    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_tool)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", fake_create_deep_agent)

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    result_false = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="Summarize the document",
        thinking_mode=False,
    )
    result_true = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="Summarize the section",
        thinking_mode=True,
    )

    assert result_false.answer == "這是統一路徑摘要回答。"
    assert result_true.answer == "這是統一路徑摘要回答。"
    assert result_false.trace.agent["answer_path"] == "deepagents_unified"
    assert result_true.trace.agent["answer_path"] == "deepagents_unified"
    assert result_false.trace.agent["thinking_mode"] is False
    assert result_true.trace.agent["thinking_mode"] is True
    assert result_false.trace.agent["thinking_mode_ignored"] is False
    assert result_true.trace.agent["thinking_mode_ignored"] is True
    assert "reasoning_effort" not in captured_llm_kwargs[0]
    assert all(item == {"messages": [{"role": "user", "content": "Summarize the document"}]} or item == {"messages": [{"role": "user", "content": "Summarize the section"}]} for item in captured_inputs)


def test_deepagents_tool_call_completed_event_includes_context_excerpt(monkeypatch) -> None:
    """有 retrieval context 時，tool completed 事件應包含 excerpt 與 assembled_text。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證 tool output 的 context payload shape。
    """

    emitted_events: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @dataclass
    class FakeCitation:
        """模擬 citation 的最小 `model_dump` 介面。"""

        context_index: int
        context_label: str
        document_id: str
        document_name: str
        parent_chunk_id: str | None
        child_chunk_ids: list[str]
        heading: str | None
        structure_kind: str
        start_offset: int
        end_offset: int
        excerpt: str
        source: str
        truncated: bool
        page_start: int | None = None
        page_end: int | None = None
        regions: list[dict[str, object]] | None = None

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            """回傳與 Pydantic model 類似的 dump 結果。

            參數：
            - `mode`：序列化模式。

            回傳：
            - `dict[str, object]`：序列化後字典。
            """

            assert mode == "json"
            return {
                "context_index": self.context_index,
                "context_label": self.context_label,
                "document_id": self.document_id,
                "document_name": self.document_name,
                "parent_chunk_id": self.parent_chunk_id,
                "child_chunk_ids": self.child_chunk_ids,
                "heading": self.heading,
                "structure_kind": self.structure_kind,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                    "excerpt": self.excerpt,
                    "source": self.source,
                    "truncated": self.truncated,
                    "page_start": self.page_start,
                    "page_end": self.page_end,
                    "regions": self.regions or [],
                }

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_tool(**kwargs):
        """回傳包含單一 assembled context 的 retrieval 結果。"""

        return _build_fake_retrieval_result(
            assembled_contexts=[
                AssembledContext(
                    document_id="doc-1",
                    parent_chunk_id="parent-1",
                    chunk_ids=["child-1", "child-2"],
                        structure_kind=ChunkStructureKind.text,
                    heading="Reader Policy",
                    assembled_text="這是一段組裝後的內容。",
                    source="業務規格書.md",
                    start_offset=10,
                    end_offset=40,
                )
            ],
            citations=[
                FakeCitation(
                    context_index=0,
                    context_label="C1",
                    document_id="doc-1",
                    document_name="reader-policy.md",
                    parent_chunk_id="parent-1",
                    child_chunk_ids=["child-1", "child-2"],
                    heading="Reader Policy",
                    structure_kind="text",
                    start_offset=10,
                    end_offset=40,
                    excerpt="這是一段組裝後的內容。",
                    source="hybrid",
                    truncated=False,
                )
            ],
            trace={
                "retrieval": {"query": kwargs["question"]},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}]},
            },
        )

    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_tool)

    class FakeAgent:
        """模擬主 agent，並主動呼叫 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval，再回傳固定回答。"""

            assert stream_mode == ["messages", "values"]
            self.tools[0]()
            return iter(
                [
                    ("messages", ({"content": "這是回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
        writer=emitted_events.append,
    )

    completed_tool_event = [
        event for event in emitted_events if event["type"] == "tool_call" and event["status"] == "completed"
    ][-1]
    context_payload = completed_tool_event["output"]["contexts"][0]

    assert context_payload["excerpt"] == "這是一段組裝後的內容。"
    assert "assembled_text" not in context_payload


def test_deepagents_runtime_accepts_phase8c_tool_summary_and_preserves_debug_safe_planning_fields(monkeypatch) -> None:
    """Phase 8C rich tool summary 應可進 debug event，且 planning payload 不得帶出 raw id。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 debug summary 與 LLM payload 邊界。
    """

    emitted_events: list[dict[str, object]] = []
    captured_tool_result: dict[str, object] = {}

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @dataclass
    class FakeCitation:
        """模擬 citation 的最小 `model_dump` 介面。"""

        context_index: int
        context_label: str
        document_id: str
        document_name: str
        parent_chunk_id: str | None
        child_chunk_ids: list[str]
        heading: str | None
        structure_kind: str
        start_offset: int
        end_offset: int
        excerpt: str
        source: str
        truncated: bool
        page_start: int | None = None
        page_end: int | None = None
        regions: list[dict[str, object]] | None = None

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            """回傳與 Pydantic model 類似的 dump 結果。

            參數：
            - `mode`：序列化模式。

            回傳：
            - `dict[str, object]`：序列化後字典。
            """

            assert mode == "json"
            return {
                "context_index": self.context_index,
                "context_label": self.context_label,
                "document_id": self.document_id,
                "document_name": self.document_name,
                "parent_chunk_id": self.parent_chunk_id,
                "child_chunk_ids": self.child_chunk_ids,
                "heading": self.heading,
                "structure_kind": self.structure_kind,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                "excerpt": self.excerpt,
                "source": self.source,
                "truncated": self.truncated,
                "page_start": self.page_start,
                "page_end": self.page_end,
                "regions": self.regions or [],
            }

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_internal(**kwargs):
        """回傳 compare query 的最小 retrieval 結果。"""

        return _build_fake_retrieval_result(
            assembled_contexts=[
                AssembledContext(
                    document_id="doc-1",
                    parent_chunk_id="parent-1",
                    chunk_ids=["child-1"],
                    structure_kind=ChunkStructureKind.text,
                    heading="Travel Policy",
                    assembled_text="Travel Policy 規定出差前需取得主管同意。",
                    source="travel-policy.md",
                    start_offset=0,
                    end_offset=28,
                )
            ],
            citations=[
                FakeCitation(
                    context_index=0,
                    context_label="C1",
                    document_id="doc-1",
                    document_name="travel-policy.md",
                    parent_chunk_id="parent-1",
                    child_chunk_ids=["child-1"],
                    heading="Travel Policy",
                    structure_kind="text",
                    start_offset=0,
                    end_offset=28,
                    excerpt="Travel Policy 規定出差前需取得主管同意。",
                    source="hybrid",
                    truncated=False,
                )
            ],
            trace={
                "retrieval": {"query": kwargs["question"], "query_type": "cross_document_compare"},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}]},
            },
            planning_documents=[
                FakePlanningDocument(
                    document_name="travel-policy.md",
                    mentioned_by_query=True,
                    hit_in_current_round=True,
                    synopsis_available=True,
                )
            ],
        )

    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_internal)
    monkeypatch.setattr(
        "app.chat.agent.runtime.build_tool_call_output_summary",
        lambda _session, _result: {
            "contexts_count": 1,
            "citations_count": 1,
            "tool_call_count": 2,
            "followup_call_count": 1,
            "synopsis_inspection_count": 1,
            "latency_budget_status": "degraded",
            "stop_reason": "latency_budget_soft_limit",
            "coverage_signals": {
                "missing_document_names": ["employee-handbook.md"],
                "supports_compare": True,
                "insufficient_evidence": True,
                "missing_compare_axes": ["approval requirement"],
                "new_evidence_found": False,
            },
            "planning_documents": [
                {
                    "handle": "doc-handle-1",
                    "document_name": "travel-policy.md",
                    "mentioned_by_query": True,
                    "hit_in_current_round": True,
                    "synopsis_available": True,
                }
            ],
            "next_best_followups": ["補查 employee handbook 是否明示 approval requirement"],
            "contexts": [
                {
                    "context_index": 0,
                    "context_label": "C1",
                    "document_id": "doc-1",
                    "document_name": "travel-policy.md",
                    "parent_chunk_id": "parent-1",
                    "child_chunk_ids": ["child-1"],
                    "heading": "Travel Policy",
                    "structure_kind": "text",
                    "source": "hybrid",
                    "truncated": False,
                    "excerpt": "Travel Policy 規定出差前需取得主管同意。",
                }
            ],
        },
    )

    class FakeAgent:
        """模擬主 agent，並擷取 tool 回傳字串。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用工具。

            回傳：
            - `None`：僅保存工具列表。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval，再回傳證據不足的比較回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定串流結果。
            """

            assert stream_mode == ["messages", "values"]
            captured_tool_result.update(json.loads(self.tools[0]()))
            return iter(
                [
                    ("messages", ({"content": "目前引用內容不足以完成完整比較。[[C1]]"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "目前引用內容不足以完成完整比較。[[C1]]"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="Compare the travel policy and employee handbook approval rules.",
        writer=emitted_events.append,
    )

    completed_tool_event = [
        event for event in emitted_events if event["type"] == "tool_call" and event["status"] == "completed"
    ][-1]
    reference_event = [event for event in emitted_events if event["type"] == "references"][0]

    assert result.answer == "目前引用內容不足以完成完整比較。"
    assert completed_tool_event["output"]["tool_call_count"] >= 1
    assert completed_tool_event["output"]["followup_call_count"] >= 0
    assert completed_tool_event["output"]["synopsis_inspection_count"] >= 0
    assert isinstance(completed_tool_event["output"]["latency_budget_status"], str)
    assert completed_tool_event["output"]["stop_reason"]
    assert completed_tool_event["output"]["coverage_signals"]["insufficient_evidence"] is True
    assert completed_tool_event["output"]["planning_documents"] == [
        {
            "handle": "doc-handle-1",
            "document_name": "travel-policy.md",
            "mentioned_by_query": True,
            "hit_in_current_round": True,
            "synopsis_available": True,
        }
    ]
    assert reference_event["references"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": "doc-1",
            "document_name": "travel-policy.md",
            "parent_chunk_id": "parent-1",
            "child_chunk_ids": ["child-1"],
            "structure_kind": "text",
            "heading": "Travel Policy",
            "excerpt": "Travel Policy 規定出差前需取得主管同意。",
            "assembled_text": "Travel Policy 規定出差前需取得主管同意。",
            "source": "travel-policy.md",
            "start_offset": 0,
            "end_offset": 28,
            "page_start": None,
            "page_end": None,
            "regions": [],
            "truncated": False,
        }
    ]
    assert set(captured_tool_result.keys()) >= {
        "assembled_contexts",
        "coverage_signals",
        "planning_documents",
        "next_best_followups",
        "evidence_cue_texts",
        "loop_trace_delta",
        "response_contract",
    }
    assert captured_tool_result["assembled_contexts"] == [
        {
            "context_label": "C1",
            "context_index": 0,
            "document_name": "travel-policy.md",
            "heading": "Travel Policy",
            "assembled_text": "Travel Policy 規定出差前需取得主管同意。",
        }
    ]
    assert captured_tool_result["response_contract"]["task_type"] == "cross_document_compare"
    assert captured_tool_result["response_contract"]["required_document_names"] == ["travel-policy.md"]
    assert captured_tool_result["planning_documents"] == [
        {
            "document_name": "travel-policy.md",
            "mentioned_by_query": True,
            "hit_in_current_round": True,
            "synopsis_available": True,
        }
    ]
    assert "document_id" not in captured_tool_result["planning_documents"][0]


def test_deepagents_runtime_returns_debug_safe_tool_payload_to_llm(monkeypatch) -> None:
    """Deep Agents tool 回傳給 LLM 時應維持 debug-safe，且不暴露 raw 文件識別碼。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證餵給 LLM 的 tool payload 已瘦身。
    """

    captured_tool_result: dict[str, object] = {}

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @dataclass
    class FakeCitation:
        """模擬 citation 的最小 `model_dump` 介面。"""

        context_index: int
        context_label: str
        document_id: str
        document_name: str
        parent_chunk_id: str | None
        child_chunk_ids: list[str]
        heading: str | None
        structure_kind: str
        start_offset: int
        end_offset: int
        excerpt: str
        source: str
        truncated: bool
        page_start: int | None = None
        page_end: int | None = None
        regions: list[dict[str, object]] | None = None

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            """回傳與 Pydantic model 類似的 dump 結果。

            參數：
            - `mode`：序列化模式。

            回傳：
            - `dict[str, object]`：序列化後字典。
            """

            assert mode == "json"
            return {
                "context_index": self.context_index,
                "context_label": self.context_label,
                "document_id": self.document_id,
                "document_name": self.document_name,
                "parent_chunk_id": self.parent_chunk_id,
                "child_chunk_ids": self.child_chunk_ids,
                "heading": self.heading,
                "structure_kind": self.structure_kind,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                    "excerpt": self.excerpt,
                    "source": self.source,
                    "truncated": self.truncated,
                    "page_start": self.page_start,
                    "page_end": self.page_end,
                    "regions": self.regions or [],
                }

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_tool(**kwargs):
        """回傳包含單一 assembled context 的 retrieval 結果。"""

        return _build_fake_retrieval_result(
            assembled_contexts=[
                AssembledContext(
                    document_id="doc-1",
                    parent_chunk_id="parent-1",
                    chunk_ids=["child-1"],
                    structure_kind=ChunkStructureKind.text,
                    heading="Reader Policy",
                    assembled_text="這是一段組裝後的內容。",
                    source="業務規格書.md",
                    start_offset=10,
                    end_offset=40,
                )
            ],
            citations=[
                FakeCitation(
                    context_index=0,
                    context_label="C1",
                    document_id="doc-1",
                    document_name="reader-policy.md",
                    parent_chunk_id="parent-1",
                    child_chunk_ids=["child-1"],
                    heading="Reader Policy",
                    structure_kind="text",
                    start_offset=10,
                    end_offset=40,
                    excerpt="這是一段組裝後的內容。",
                    source="hybrid",
                    truncated=False,
                )
            ],
            trace={
                "retrieval": {"query": kwargs["question"]},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}]},
            },
        )

    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_tool)

    class FakeAgent:
        """模擬主 agent，並擷取 tool 回傳字串。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval，再回傳固定回答。"""

            assert stream_mode == ["messages", "values"]
            captured_tool_result.update(json.loads(self.tools[0]()))
            return iter(
                [
                    ("messages", ({"content": "這是回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
    )

    assert captured_tool_result["assembled_contexts"] == [
        {
            "context_label": "C1",
            "context_index": 0,
            "document_name": "reader-policy.md",
            "heading": "Reader Policy",
            "assembled_text": "這是一段組裝後的內容。",
        }
    ]
    assert captured_tool_result["coverage_signals"] is None
    assert all("document_id" not in item for item in captured_tool_result["planning_documents"])
    assert captured_tool_result["next_best_followups"] == []
    assert captured_tool_result["evidence_cue_texts"] == []
    assert captured_tool_result.get("synopsis_hints", []) == []
    assert captured_tool_result["loop_trace_delta"]["latency_budget_status"] == "normal"
    assert captured_tool_result["loop_trace_delta"]["followup_call_count"] == 0


def test_deepagents_runtime_short_circuits_duplicate_initial_tool_call(monkeypatch) -> None:
    """重複的空參數 tool call 應直接回 cached payload，而不是重跑 retrieval。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 duplicate initial call 會 short-circuit。
    """

    retrieval_call_count = 0
    captured_first_payload: dict[str, object] = {}
    captured_second_payload: dict[str, object] = {}

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @dataclass
    class FakeCitation:
        """模擬 citation 的最小 `model_dump` 介面。"""

        context_index: int
        context_label: str
        document_id: str
        document_name: str
        parent_chunk_id: str | None
        child_chunk_ids: list[str]
        heading: str | None
        structure_kind: str
        start_offset: int
        end_offset: int
        excerpt: str
        source: str
        truncated: bool

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            """回傳與 Pydantic model 類似的 dump 結果。

            參數：
            - `mode`：序列化模式。

            回傳：
            - `dict[str, object]`：序列化後字典。
            """

            assert mode == "json"
            return {
                "context_index": self.context_index,
                "context_label": self.context_label,
                "document_id": self.document_id,
                "document_name": self.document_name,
                "parent_chunk_id": self.parent_chunk_id,
                "child_chunk_ids": self.child_chunk_ids,
                "heading": self.heading,
                "structure_kind": self.structure_kind,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                "excerpt": self.excerpt,
                "source": self.source,
                "truncated": self.truncated,
                "page_start": None,
                "page_end": None,
                "regions": [],
            }

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_internal(**kwargs):
        """建立最小 retrieval 結果，並統計實際執行次數。"""

        nonlocal retrieval_call_count
        retrieval_call_count += 1
        return _build_fake_retrieval_result(
            assembled_contexts=[
                AssembledContext(
                    document_id="doc-1",
                    parent_chunk_id="parent-1",
                    chunk_ids=["child-1"],
                    structure_kind=ChunkStructureKind.text,
                    heading="Reader Policy",
                    assembled_text="這是一段組裝後的內容。",
                    source="reader-policy.md",
                    start_offset=10,
                    end_offset=40,
                )
            ],
            citations=[
                FakeCitation(
                    context_index=0,
                    context_label="C1",
                    document_id="doc-1",
                    document_name="reader-policy.md",
                    parent_chunk_id="parent-1",
                    child_chunk_ids=["child-1"],
                    heading="Reader Policy",
                    structure_kind="text",
                    start_offset=10,
                    end_offset=40,
                    excerpt="這是一段組裝後的內容。",
                    source="hybrid",
                    truncated=False,
                )
            ],
            trace={
                "retrieval": {"query": kwargs["question"]},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}]},
            },
        )

    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_internal)

    class FakeAgent:
        """模擬主 agent，連續呼叫兩次空參數 tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先後執行兩次空參數 tool call，再回傳固定回答。"""

            assert stream_mode == ["messages", "values"]
            captured_first_payload.update(json.loads(self.tools[0]()))
            captured_second_payload.update(json.loads(self.tools[0]()))
            return iter(
                [
                    ("messages", ({"content": "這是回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
    )

    assert retrieval_call_count == 1
    assert captured_first_payload["assembled_contexts"] == captured_second_payload["assembled_contexts"]
    assert captured_second_payload["loop_trace_delta"]["stop_reason"] == "duplicate_initial_call_cached"


def test_deepagents_runtime_allows_followup_tool_calls_when_agentic_enabled(monkeypatch) -> None:
    """只要 `CHAT_AGENTIC_ENABLED=true`，非 compare 題也應允許 follow-up tool call。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以呼叫次數與 payload 驗證第 4 次呼叫未被舊上限擋下。
    """

    retrieval_call_count = 0
    captured_payloads: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    def fake_retrieve_area_contexts_internal(**kwargs):
        """每次呼叫都回傳最小 retrieval 結果，並記錄實際執行次數。

        參數：
        - `**kwargs`：retrieval tool 參數。

        回傳：
        - `SimpleNamespace`：最小 retrieval 結果。
        """

        nonlocal retrieval_call_count
        retrieval_call_count += 1
        return _build_fake_retrieval_result(
            assembled_contexts=[],
            citations=[],
            trace={
                "retrieval": {
                    "query": kwargs["question"],
                    "query_type": EvaluationQueryType.fact_lookup.value,
                },
                "assembler": {"contexts": []},
            },
            loop_trace_delta={"effective_query": kwargs["question"]},
        )

    class FakeAgent:
        """模擬主 agent，連續呼叫 4 次 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用工具。

            回傳：
            - `None`：僅保存工具列表。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """連續執行 4 次 tool call，再回傳固定回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定串流結果。
            """

            assert stream_mode == ["messages", "values"]
            captured_payloads.append(json.loads(self.tools[0]()))
            captured_payloads.append(
                json.loads(
                    self.tools[0](
                        query_variant="reader policy 的例外條件",
                        followup_reason="補查例外情況",
                    )
                )
            )
            captured_payloads.append(
                json.loads(
                    self.tools[0](
                        query_variant="reader policy 的申請流程",
                        followup_reason="補查申請流程",
                    )
                )
            )
            captured_payloads.append(
                json.loads(
                    self.tools[0](
                        query_variant="reader policy 的限制條件",
                        followup_reason="補查限制條件",
                    )
                )
            )
            return iter(
                [
                    ("messages", ({"content": "這是回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)
    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_internal)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
        CHAT_AGENTIC_ENABLED=True,
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
    )

    assert retrieval_call_count == 4
    assert captured_payloads[-1]["loop_trace_delta"]["tool_call_count"] == 4
    assert captured_payloads[-1]["loop_trace_delta"]["stop_reason"] != "tool_call_limit_reached"


def test_deepagents_runtime_blocks_followup_tool_calls_when_agentic_disabled(monkeypatch) -> None:
    """`CHAT_AGENTIC_ENABLED=false` 時，follow-up tool call 應被拒絕。"""

    retrieval_call_count = 0
    captured_payloads: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    def fake_retrieve_area_contexts_internal(**kwargs):
        """每次真正執行 retrieval 時回傳最小結果。"""

        nonlocal retrieval_call_count
        retrieval_call_count += 1
        return _build_fake_retrieval_result(
            assembled_contexts=[],
            citations=[],
            trace={
                "retrieval": {
                    "query": kwargs["question"],
                    "query_type": EvaluationQueryType.fact_lookup.value,
                },
                "assembler": {"contexts": []},
            },
            loop_trace_delta={"effective_query": kwargs["question"]},
        )

    class FakeAgent:
        """模擬主 agent，先做首次檢索，再嘗試一次 follow-up。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用工具。

            回傳：
            - `None`：僅保存工具列表。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行首次檢索，再嘗試 follow-up 工具呼叫。"""

            assert stream_mode == ["messages", "values"]
            captured_payloads.append(json.loads(self.tools[0]()))
            captured_payloads.append(
                json.loads(
                    self.tools[0](
                        query_variant="reader policy 的例外條件",
                        followup_reason="補查例外情況",
                    )
                )
            )
            return iter(
                [
                    ("messages", ({"content": "這是回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)
    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_internal)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
        CHAT_AGENTIC_ENABLED=False,
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
    )

    assert retrieval_call_count == 1
    assert captured_payloads[-1]["loop_trace_delta"]["tool_call_count"] == 1
    assert captured_payloads[-1]["loop_trace_delta"]["stop_reason"] == "followup_not_allowed"


def test_deepagents_runtime_compare_queries_include_response_contract(monkeypatch) -> None:
    """compare query 餵給 LLM 的 tool payload 應包含逐文件比較契約。"""

    captured_tool_result: dict[str, object] = {}

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @dataclass
    class FakeCitation:
        """模擬 citation 的最小 `model_dump` 介面。"""

        context_index: int
        context_label: str
        document_id: str
        document_name: str
        parent_chunk_id: str | None
        child_chunk_ids: list[str]
        heading: str | None
        structure_kind: str
        start_offset: int
        end_offset: int
        excerpt: str
        source: str
        truncated: bool
        page_start: int | None = None
        page_end: int | None = None
        regions: list[dict[str, object]] | None = None

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            """回傳與 Pydantic model 類似的 dump 結果。

            參數：
            - `mode`：序列化模式。

            回傳：
            - `dict[str, object]`：序列化後字典。
            """

            assert mode == "json"
            return {
                "context_index": self.context_index,
                "context_label": self.context_label,
                "document_id": self.document_id,
                "document_name": self.document_name,
                "parent_chunk_id": self.parent_chunk_id,
                "child_chunk_ids": self.child_chunk_ids,
                "heading": self.heading,
                "structure_kind": self.structure_kind,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                "excerpt": self.excerpt,
                "source": self.source,
                "truncated": self.truncated,
                "page_start": self.page_start,
                "page_end": self.page_end,
                "regions": self.regions or [],
            }

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_internal(**kwargs):
        """回傳 compare query 的最小 retrieval 結果。"""

        return _build_fake_retrieval_result(
            assembled_contexts=[
                AssembledContext(
                    document_id="doc-1",
                    parent_chunk_id="parent-1",
                    chunk_ids=["child-1"],
                    structure_kind=ChunkStructureKind.text,
                    heading="Approval Flow",
                    assembled_text="Domestic travel needs manager approval.",
                    source="travel-policy.md",
                    start_offset=0,
                    end_offset=40,
                ),
                AssembledContext(
                    document_id="doc-2",
                    parent_chunk_id="parent-2",
                    chunk_ids=["child-2"],
                    structure_kind=ChunkStructureKind.text,
                    heading="Remote Work",
                    assembled_text="Employees may work remotely up to three days per week.",
                    source="employee-handbook.md",
                    start_offset=0,
                    end_offset=56,
                ),
            ],
            citations=[
                FakeCitation(
                    context_index=0,
                    context_label="C1",
                    document_id="doc-1",
                    document_name="travel-policy.md",
                    parent_chunk_id="parent-1",
                    child_chunk_ids=["child-1"],
                    heading="Approval Flow",
                    structure_kind="text",
                    start_offset=0,
                    end_offset=40,
                    excerpt="Domestic travel needs manager approval.",
                    source="hybrid",
                    truncated=False,
                ),
                FakeCitation(
                    context_index=1,
                    context_label="C2",
                    document_id="doc-2",
                    document_name="employee-handbook.md",
                    parent_chunk_id="parent-2",
                    child_chunk_ids=["child-2"],
                    heading="Remote Work",
                    structure_kind="text",
                    start_offset=0,
                    end_offset=56,
                    excerpt="Employees may work remotely up to three days per week.",
                    source="hybrid",
                    truncated=False,
                ),
            ],
            trace={
                "retrieval": {"query": kwargs["question"], "query_type": "cross_document_compare"},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}, {"context_index": 1, "truncated": False}]},
            },
            planning_documents=[
                FakePlanningDocument(
                    document_name="travel-policy.md",
                    mentioned_by_query=True,
                    hit_in_current_round=True,
                    synopsis_available=True,
                ),
                FakePlanningDocument(
                    document_name="employee-handbook.md",
                    mentioned_by_query=True,
                    hit_in_current_round=True,
                    synopsis_available=True,
                ),
            ],
        )

    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_internal)

    class FakeAgent:
        """模擬主 agent，並擷取 tool 回傳字串。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval，再回傳固定回答。"""

            assert stream_mode == ["messages", "values"]
            captured_tool_result.update(json.loads(self.tools[0]()))
            return iter(
                [
                    ("messages", ({"content": "這是比較回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是比較回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="Compare the travel policy and employee handbook.",
    )

    assert captured_tool_result["response_contract"]["task_type"] == "cross_document_compare"
    assert captured_tool_result["response_contract"]["required_document_names"] == [
        "travel-policy.md",
        "employee-handbook.md",
    ]
    assert captured_tool_result["response_contract"]["compare_answer_template"] == [
        "先逐一說明每份文件的直接證據與立場。",
        "再整理共同點與差異；只有雙方都有直接證據時才能寫成共同點。",
        "若目前已具備雙邊直接證據，直接完成比較，不要加入 required documents 或 tool coverage 狀態前言；只有真的缺少其中一方證據時，才簡短說明證據不足。",
    ]
    assert "coverage_signals" not in captured_tool_result["response_contract"]


def test_deepagents_runtime_runs_real_retrieval_tool_and_returns_context_contract(
    db_session,
    app_settings,
    monkeypatch,
) -> None:
    """Deep Agents runtime 應可走真實 retrieval tool 並回傳 assembled-context contract。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 Deep Agents 與 retrieval tool 的整合契約。
    """

    area = Area(id=_uuid(), name="Deep Agents Tool Integration")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="reader-policy.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-reader-policy/reader-policy.md",
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
        heading="Reader Policy",
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
        heading="Reader Policy",
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
        heading="Reader Policy",
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

    captured_tool_result: dict[str, object] = {}
    emitted_events: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    class FakeAgent:
        """模擬主 agent，並主動呼叫真實 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用工具列表。

            回傳：
            - `None`：僅保存工具列表。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval tool，再回傳固定回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `Iterator[tuple[str, object]]`：固定 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            captured_tool_result.update(json.loads(self.tools[0]()))
            return iter(
                [
                    ("messages", ({"content": "這是帶真實檢索的回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是帶真實檢索的回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = app_settings.model_copy(
        update={
            "chat_provider": "deepagents",
            "chat_model": "gpt-5.4-mini",
            "chat_max_output_tokens": 512,
            "chat_timeout_seconds": 30,
            "openai_api_key": "test-key",
        }
    )

    result = provider.run(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id=area.id,
        question="請根據文件回答 alpha",
        writer=emitted_events.append,
    )

    assert result.answer == "這是帶真實檢索的回答。"
    assert [item.model_dump(mode="json") for item in result.answer_blocks] == [
        {
            "text": "這是帶真實檢索的回答。",
            "citation_context_indices": [],
            "display_citations": [],
        }
    ]
    assert [item.model_dump(mode="json") for item in result.citations] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "heading": "Reader Policy",
            "structure_kind": "text",
            "start_offset": 0,
            "end_offset": 27,
            "excerpt": "alpha intro\n\nalpha details",
            "source": "hybrid",
            "truncated": False,
            "page_start": None,
            "page_end": None,
            "regions": [],
        }
    ]
    assert [item.model_dump(mode="json") for item in result.assembled_contexts] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "structure_kind": "text",
            "heading": "Reader Policy",
            "excerpt": "alpha intro\n\nalpha details",
            "assembled_text": "alpha intro\n\nalpha details",
            "source": "hybrid",
            "start_offset": 0,
            "end_offset": 27,
            "page_start": None,
            "page_end": None,
            "regions": [],
            "truncated": False,
        }
    ]
    assert result.trace.retrieval["query"] == "請根據文件回答 alpha"
    assert result.trace.assembler["kept_chunk_ids"] == [child_one.id, child_two.id]
    assert result.trace.agent["retrieval_invoked"] is True
    assert result.trace.agent["contexts_count"] == 1
    assert result.used_knowledge_base is True
    assert result.message_artifact.assistant_turn_index == 0
    assert result.message_artifact.used_knowledge_base is True
    assert captured_tool_result["assembled_contexts"] == [
        {
            "context_label": "C1",
            "context_index": 0,
            "document_name": "reader-policy.md",
            "heading": "Reader Policy",
            "assembled_text": "alpha intro\n\nalpha details",
        }
    ]
    assert captured_tool_result["coverage_signals"] is None
    assert captured_tool_result["planning_documents"]
    assert all("document_id" not in item for item in captured_tool_result["planning_documents"])
    completed_tool_event = [
        event for event in emitted_events if event["type"] == "tool_call" and event["status"] == "completed"
    ][0]
    reference_event = [event for event in emitted_events if event["type"] == "references"][0]
    assert reference_event["references"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "structure_kind": "text",
            "heading": "Reader Policy",
            "excerpt": "alpha intro\n\nalpha details",
            "assembled_text": "alpha intro\n\nalpha details",
            "source": "hybrid",
            "start_offset": 0,
            "end_offset": 27,
            "page_start": None,
            "page_end": None,
            "regions": [],
            "truncated": False,
        }
    ]
    assert completed_tool_event["output"]["contexts_count"] == 1
    assert completed_tool_event["output"]["citations_count"] == 1
    assert completed_tool_event["output"]["query_type"] == "fact_lookup"
    assert completed_tool_event["output"]["query_type_language"] == "mixed"
    assert completed_tool_event["output"]["query_type_source"] == "fallback"
    assert completed_tool_event["output"]["query_type_confidence"] == 0.0
    assert completed_tool_event["output"]["query_type_matched_rules"] == []
    assert completed_tool_event["output"]["query_type_rule_hits"] == []
    assert completed_tool_event["output"]["query_type_embedding_scores"]
    assert completed_tool_event["output"]["query_type_embedding_margin"] >= 0.0
    assert completed_tool_event["output"]["query_type_fallback_used"] is False
    assert completed_tool_event["output"]["query_type_fallback_reason"] == "llm_fallback_unavailable"
    assert completed_tool_event["output"]["summary_scope"] is None
    assert completed_tool_event["output"]["document_scope"] == "area"
    assert completed_tool_event["output"]["resolved_document_ids"] == []
    assert completed_tool_event["output"]["document_mention_source"] == "none"
    assert completed_tool_event["output"]["document_mention_confidence"] == 0.0
    assert completed_tool_event["output"]["document_mention_candidates"] == []
    assert completed_tool_event["output"]["selected_profile"] == "fact_lookup_precision_v1"
    assert completed_tool_event["output"]["selection_applied"] is False
    assert completed_tool_event["output"]["selection_strategy"] == "disabled"
    assert completed_tool_event["output"]["selected_document_count"] == 1
    assert completed_tool_event["output"]["selected_parent_count"] == 1
    assert completed_tool_event["output"]["selected_document_ids"] == [document.id]
    assert completed_tool_event["output"]["selected_parent_ids"] == [parent.id]
    assert completed_tool_event["output"]["dropped_by_diversity"] == []
    assert completed_tool_event["output"]["summary_strategy"] is None
    assert completed_tool_event["output"]["summary_strategy_source"] == "not_applicable"
    assert completed_tool_event["output"]["summary_strategy_confidence"] == 0.0
    assert completed_tool_event["output"]["summary_strategy_rule_hits"] == []
    assert completed_tool_event["output"]["summary_strategy_embedding_scores"] == []
    assert completed_tool_event["output"]["summary_strategy_top_label"] is None
    assert completed_tool_event["output"]["summary_strategy_runner_up_label"] is None
    assert completed_tool_event["output"]["summary_strategy_embedding_margin"] == 0.0
    assert completed_tool_event["output"]["summary_strategy_fallback_used"] is False
    assert completed_tool_event["output"]["summary_strategy_fallback_reason"] is None
    assert completed_tool_event["output"]["fallback_reason"] is None
    assert completed_tool_event["output"]["profile_settings"]["vector_top_k"] == settings.retrieval_vector_top_k
    assert completed_tool_event["output"]["profile_settings"]["task_type_embedding_scores"]
    assert completed_tool_event["output"]["contexts"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "heading": "Reader Policy",
            "structure_kind": "text",
            "source": "hybrid",
            "truncated": False,
            "excerpt": "alpha intro\n\nalpha details",
        }
    ]


def test_deepagents_runtime_wraps_invocation_in_langsmith_tracing_context(monkeypatch) -> None:
    """啟用 LangSmith tracing 時，Deep Agents invocation 應包在 tracing context 內。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證 tracing context 參數與包覆範圍。
    """

    captured_context: dict[str, object] = {}

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @contextmanager
    def fake_tracing_context(**kwargs):
        """記錄 tracing context 參數，並模擬 context manager。

        參數：
        - `**kwargs`：傳入 tracing context 的設定。

        回傳：
        - context manager：供測試包覆 Deep Agents invocation。
        """

        captured_context["kwargs"] = kwargs
        captured_context["entered"] = True
        try:
            yield
        finally:
            captured_context["exited"] = True

    class FakeAgent:
        """模擬主 agent。"""

        def stream(self, _input, *, stream_mode):
            """回傳固定串流回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `Iterator[tuple[str, object]]`：固定的 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            assert captured_context.get("entered") is True
            return iter(
                [
                    ("messages", ({"content": "這是 traced 回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是 traced 回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tracing_context", fake_tracing_context)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent())

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
        LANGSMITH_TRACING=True,
        LANGSMITH_API_KEY="langsmith-test-key",
        LANGSMITH_PROJECT="deep-agent-rag-stack-test",
    )

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
    )

    assert result.answer == "這是 traced 回答。"
    assert captured_context["kwargs"] == {
        "enabled": True,
        "project_name": "deep-agent-rag-stack-test",
        "tags": [
            "deepagents",
            "langgraph",
            "chat_provider:deepagents",
            "chat_model:gpt-5.4-mini",
        ],
        "metadata": {
            "area_id": "area-1",
            "principal_sub": "user-1",
            "principal_groups_count": 1,
            "chat_provider": "deepagents",
            "chat_model": "gpt-5.4-mini",
            "question_length": len("請根據文件回答 reader policy"),
        },
    }
    assert captured_context["exited"] is True


def test_deepagents_runtime_rejects_langsmith_tracing_without_api_key(monkeypatch) -> None:
    """啟用 LangSmith tracing 但未提供 API key 時應提早失敗。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證缺少必要設定時的錯誤訊息。
    """

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)

    provider = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5.4-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
        LANGSMITH_TRACING=True,
        LANGSMITH_API_KEY="",
    )

    try:
        provider.run(
            session=None,
            principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
            settings=settings,
            area_id="area-1",
            question="請根據文件回答 reader policy",
        )
    except ValueError as exc:
        assert "LANGSMITH_API_KEY" in str(exc)
    else:
        raise AssertionError("預期缺少 LANGSMITH_API_KEY 時應拋出 ValueError。")
