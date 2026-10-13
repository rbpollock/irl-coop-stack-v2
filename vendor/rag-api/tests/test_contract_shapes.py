"""REST、LangGraph stream 與 message artifact contract shape 測試。"""

from types import SimpleNamespace
from uuid import uuid4

from pydantic import TypeAdapter

from app.auth.verifier import CurrentPrincipal
from app.chat.agent.runtime import DeepAgentsChatRuntime
from app.chat.contracts.types import (
    ChatAnswerBlockPayload,
    ChatAssembledContextPayload,
    ChatCitation,
    ChatCitationPayload,
    ChatMessageArtifactPayload,
    ChatPhaseEventPayload,
    ChatReferencesEventPayload,
    ChatTokenEventPayload,
    ChatToolCallEventPayload,
    ChatTracePayload,
)
from app.chat.runtime.langgraph_agent import _run_chat_node
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, Role
from app.services.retrieval_assembler import AssembledContext


# 管理者測試 token。
ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"

# 維護者測試 token。
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def _assert_exact_keys(payload: dict[str, object], expected_keys: set[str]) -> None:
    """驗證 payload keys 完全符合 contract。

    參數：
    - `payload`：待驗證 payload。
    - `expected_keys`：預期 key 集合。

    回傳：
    - `None`：若 keys 不符會由 assert 失敗。
    """

    assert set(payload.keys()) == expected_keys


def _seed_ready_document(db_session, *, area_id: str, user_sub: str = "user-reader") -> tuple[Document, DocumentChunk, DocumentChunk]:
    """建立單一 ready 文件與一個可檢索 child chunk。

    參數：
    - `db_session`：測試資料庫 session。
    - `area_id`：文件所屬 area。
    - `user_sub`：被授權使用者 subject。

    回傳：
    - `tuple[Document, DocumentChunk, DocumentChunk]`：文件、parent、child。
    """

    area = Area(id=area_id, name="Contract Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="contract.md",
        content_type="text/markdown",
        file_size=100,
        storage_key=f"{area.id}/contract.md",
        display_text="Alpha contract evidence.",
        normalized_text="Alpha contract evidence.",
        status="ready",
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
        heading="Contract",
        content="Alpha contract evidence.",
        content_preview="Alpha contract evidence.",
        char_count=24,
        start_offset=0,
        end_offset=24,
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
        heading="Contract",
        content="Alpha contract evidence.",
        content_preview="Alpha contract evidence.",
        char_count=24,
        start_offset=0,
        end_offset=24,
        embedding=[0.1] * 1536,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub=user_sub, role=Role.reader),
            document,
            parent,
            child,
        ]
    )
    db_session.commit()
    return document, parent, child


def test_rest_payload_shapes_for_core_resources(client, db_session) -> None:
    """REST 核心端點應回傳穩定 payload shape，而不只行為正確。

    參數：
    - `client`：FastAPI 測試 client。
    - `db_session`：測試資料庫 session。

    回傳：
    - `None`：以 exact keys 與型別斷言驗證 contract。
    """

    auth_response = client.get("/auth/context", headers={"Authorization": ADMIN_TOKEN})
    assert auth_response.status_code == 200
    auth_payload = auth_response.json()
    _assert_exact_keys(auth_payload, {"sub", "groups", "authenticated", "name", "preferred_username"})
    assert auth_payload["sub"] == "user-admin"
    assert isinstance(auth_payload["groups"], list)
    assert auth_payload["authenticated"] is True

    area_response = client.post(
        "/areas",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Contract Area", "description": "REST shape"},
    )
    assert area_response.status_code == 201
    area_payload = area_response.json()
    _assert_exact_keys(area_payload, {"id", "name", "description", "effective_role", "created_at", "updated_at"})
    assert isinstance(area_payload["id"], str)
    assert area_payload["effective_role"] == "admin"

    db_session.add(AreaUserRole(area_id=area_payload["id"], user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()
    upload_response = client.post(
        f"/areas/{area_payload['id']}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("contract.md", b"# Contract\nAlpha", "text/markdown")},
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.json()
    _assert_exact_keys(upload_payload, {"document", "job"})
    _assert_exact_keys(
        upload_payload["document"],
        {"id", "area_id", "file_name", "content_type", "file_size", "status", "chunk_summary", "created_at", "updated_at"},
    )
    _assert_exact_keys(
        upload_payload["document"]["chunk_summary"],
        {
            "total_chunks",
            "parent_chunks",
            "child_chunks",
            "mixed_structure_parents",
            "text_table_text_clusters",
            "last_indexed_at",
        },
    )
    _assert_exact_keys(
        upload_payload["job"],
        {"id", "document_id", "status", "stage", "chunk_summary", "error_message", "created_at", "updated_at"},
    )
    assert upload_payload["document"]["status"] == "uploaded"
    assert upload_payload["job"]["status"] == "queued"


def test_langgraph_values_and_message_artifacts_match_contract(app, app_settings, db_session) -> None:
    """LangGraph values state 與 message_artifacts 應符合正式 contract shape。

    參數：
    - `app`：測試 FastAPI app。
    - `app_settings`：測試設定。
    - `db_session`：測試資料庫 session。

    回傳：
    - `None`：以 TypedDict/Pydantic contract 驗證 shape。
    """

    area_id = _uuid()
    _seed_ready_document(db_session, area_id=area_id)

    result = _run_chat_node(
        {
            "messages": [{"role": "user", "content": "Alpha?"}],
            "area_id": area_id,
            "question": "Alpha?",
            "principal": {"sub": "user-reader", "groups": ["/group/reader"], "authenticated": True},
            "settings": app_settings,
            "session_factory": app.state.session_factory,
        }
    )

    _assert_exact_keys(
        result,
        {
            "messages",
            "area_id",
            "question",
            "principal",
            "settings",
            "session_factory",
            "answer",
            "answer_blocks",
            "citations",
            "assembled_contexts",
            "message_artifacts",
            "used_knowledge_base",
            "trace",
        },
    )
    assert result["messages"] and result["messages"][0]["role"] == "assistant"
    TypeAdapter(ChatAnswerBlockPayload).validate_python(result["answer_blocks"][0])
    TypeAdapter(ChatCitationPayload).validate_python(result["citations"][0])
    TypeAdapter(ChatAssembledContextPayload).validate_python(result["assembled_contexts"][0])
    TypeAdapter(ChatMessageArtifactPayload).validate_python(result["message_artifacts"][0])
    TypeAdapter(ChatTracePayload).validate_python(result["trace"])

    artifact = result["message_artifacts"][0]
    _assert_exact_keys(artifact, {"assistant_turn_index", "answer", "answer_blocks", "citations", "used_knowledge_base"})
    assert artifact["answer"] == result["answer"]
    assert artifact["citations"] == result["citations"]
    assert artifact["used_knowledge_base"] is True


def test_deepagents_custom_events_match_contract(monkeypatch, app_settings) -> None:
    """LangGraph custom stream events 應符合 phase/tool/references/token contract shape。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。
    - `app_settings`：測試設定。

    回傳：
    - `None`：以 exact keys 與 TypeAdapter 驗證 custom events。
    """

    emitted_events: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存參數。
            """

            self.kwargs = kwargs

    class FakeAgent:
        """模擬主 agent，會呼叫 retrieval tool 並輸出 messages/values。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用工具列表。

            回傳：
            - `None`：僅保存工具。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """呼叫 tool 後回傳固定 stream。

            參數：
            - `_input`：agent input。
            - `stream_mode`：要求 stream mode。

            回傳：
            - `Iterator[tuple[str, object]]`：固定 stream events。
            """

            assert stream_mode == ["messages", "values"]
            self.tools[0]()
            return iter(
                [
                    ("messages", ({"content": "Alpha answer. "}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "Alpha answer. [[C1]]"}]}),
                ]
            )

    def fake_create_deep_agent(**kwargs):
        """回傳會主動呼叫 retrieval tool 的假 agent。"""

        return FakeAgent(kwargs.get("tools", []))

    def fake_retrieve_area_contexts_internal(**kwargs):
        """回傳最小但完整的 retrieval result contract。"""

        del kwargs
        context = AssembledContext(
            document_id="document-1",
            parent_chunk_id="parent-1",
            chunk_ids=["child-1"],
            structure_kind=ChunkStructureKind.text,
            heading="Contract",
            assembled_text="Alpha evidence.",
            source="hybrid",
            start_offset=0,
            end_offset=15,
            regions=[],
        )
        citation = ChatCitation(
            context_index=0,
            context_label="C1",
            document_id="document-1",
            document_name="contract.md",
            parent_chunk_id="parent-1",
            child_chunk_ids=["child-1"],
            heading="Contract",
            structure_kind=ChunkStructureKind.text,
            start_offset=0,
            end_offset=15,
            excerpt="Alpha evidence.",
            source="hybrid",
            truncated=False,
            page_start=None,
            page_end=None,
            regions=[],
        )
        return SimpleNamespace(
            assembled_contexts=[context],
            citations=[citation],
            trace={
                "retrieval": {"query": "Alpha?", "query_type": "fact_lookup"},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}]},
            },
            planning_documents=[],
            coverage_signals=None,
            next_best_followups=[],
            evidence_cue_texts=[],
            synopsis_hints=[],
            loop_trace_delta={"base_question": "Alpha?", "effective_query": "Alpha?"},
        )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("app.chat.agent.runtime._retrieve_area_contexts_internal", fake_retrieve_area_contexts_internal)

    runtime = DeepAgentsChatRuntime(
        model="gpt-5.4-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    runtime.run(
        session=None,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",), authenticated=True),
        settings=app_settings.model_copy(
            update={
                "chat_provider": "deepagents",
                "chat_model": "gpt-5.4-mini",
                "chat_agentic_enabled": True,
                "openai_api_key": "test-key",
            }
        ),
        area_id="area-1",
        question="Alpha?",
        writer=emitted_events.append,
    )

    phase_event = next(event for event in emitted_events if event["type"] == "phase")
    tool_started = next(event for event in emitted_events if event["type"] == "tool_call" and event["status"] == "started")
    tool_completed = next(event for event in emitted_events if event["type"] == "tool_call" and event["status"] == "completed")
    references_event = next(event for event in emitted_events if event["type"] == "references")
    token_event = next(event for event in emitted_events if event["type"] == "token")

    _assert_exact_keys(phase_event, {"type", "phase", "status", "message"})
    TypeAdapter(ChatPhaseEventPayload).validate_python(phase_event)
    _assert_exact_keys(tool_started, {"type", "name", "status", "input", "output"})
    _assert_exact_keys(tool_started["input"], {"area_id", "question", "query_variant", "document_handles", "inspect_synopsis_handles", "followup_reason"})
    TypeAdapter(ChatToolCallEventPayload).validate_python(tool_started)
    _assert_exact_keys(tool_completed, {"type", "name", "status", "input", "output"})
    assert {"contexts_count", "citations_count", "contexts", "loop_trace_delta"}.issubset(tool_completed["output"].keys())
    TypeAdapter(ChatToolCallEventPayload).validate_python(tool_completed)
    _assert_exact_keys(references_event, {"type", "references"})
    TypeAdapter(ChatReferencesEventPayload).validate_python(references_event)
    TypeAdapter(ChatAssembledContextPayload).validate_python(references_event["references"][0])
    _assert_exact_keys(token_event, {"type", "delta"})
    TypeAdapter(ChatTokenEventPayload).validate_python(token_event)
