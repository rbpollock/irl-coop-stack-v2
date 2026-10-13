"""LangGraph public graph，負責將 thread state 交給正式 Deep Agents chat runtime。"""

from __future__ import annotations

from operator import add
from typing import Annotated, NotRequired, TypedDict

from langgraph.graph.message import add_messages
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.auth.verifier import CurrentPrincipal
from app.chat.agent.runtime import (
    DeepAgentsChatRuntime,
    build_chat_runtime,
    extract_final_assistant_message,
)
from app.chat.contracts.types import (
    AssistantMessagePayload,
    ChatAnswerBlockPayload,
    ChatAssembledContextPayload,
    ChatCitationPayload,
    ChatMessageArtifactPayload,
    ChatTracePayload,
    PrincipalPayload,
)
from app.chat.tools.retrieval import retrieve_area_contexts_tool
from app.chat.tools.retrieval_serialization import build_assembled_context_payload
from app.core.settings import get_settings
from app.db.session import create_database_engine, create_session_factory


# LangGraph default endpoint 使用的全域 settings。
GRAPH_SETTINGS = get_settings()
# LangGraph default endpoint 使用的全域資料庫 engine。
GRAPH_ENGINE = create_database_engine(GRAPH_SETTINGS)
# LangGraph default endpoint 使用的全域 session factory。
GRAPH_SESSION_FACTORY = create_session_factory(GRAPH_ENGINE)


class ChatGraphState(TypedDict):
    """單輪 chat graph state。"""

    # LangGraph thread 持久化的完整對話訊息列表。
    messages: Annotated[list[AssistantMessagePayload], add_messages]
    # 要提問的 area 識別碼。
    area_id: str
    # 使用者提問。
    question: str
    # 是否啟用 thinking mode。
    thinking_mode: NotRequired[bool]
    # 目前已驗證使用者。
    principal: PrincipalPayload
    # 最終回答文字。
    answer: str
    # 最終回答區塊。
    answer_blocks: list[ChatAnswerBlockPayload]
    # 最終 context references。
    citations: list[ChatCitationPayload]
    # 最終 assembled contexts。
    assembled_contexts: list[ChatAssembledContextPayload]
    # 每個 assistant turn 的持久化 UI artifacts。
    message_artifacts: Annotated[list[ChatMessageArtifactPayload], add]
    # 本輪是否使用知識庫。
    used_knowledge_base: bool
    # 最終 trace。
    trace: ChatTracePayload
    # 測試與本機覆寫用的可選 settings。
    settings: NotRequired[object]
    # 測試與本機覆寫用的可選 session factory。
    session_factory: NotRequired[object]


def _run_chat_node(state: ChatGraphState) -> ChatGraphState:
    """Graph 節點：執行單輪 chat 並回填輸出。"""

    runtime_settings = state.get("settings", GRAPH_SETTINGS)
    session_factory = state.get("session_factory", GRAPH_SESSION_FACTORY)
    principal_payload = state["principal"]
    principal = CurrentPrincipal(
        sub=str(principal_payload["sub"]),
        groups=tuple(str(group) for group in principal_payload.get("groups", [])),
        authenticated=bool(principal_payload.get("authenticated", True)),
    )
    session = session_factory()
    try:
        runtime = build_chat_runtime(runtime_settings)
        if isinstance(runtime, DeepAgentsChatRuntime):
            result = runtime.run(
                session=session,
                principal=principal,
                settings=runtime_settings,
                area_id=state["area_id"],
                question=state["question"],
                thinking_mode=bool(state.get("thinking_mode", False)),
                conversation_messages=list(state.get("messages", [])),
                writer=get_stream_writer(),
            )
            final_assistant_message = extract_final_assistant_message(result.raw_result)
            return {
                **state,
                "messages": [final_assistant_message] if final_assistant_message is not None else [],
                "answer": result.answer,
                "answer_blocks": [item.model_dump(mode="json") for item in result.answer_blocks],
                "citations": [item.model_dump(mode="json") for item in result.citations],
                "assembled_contexts": [item.model_dump(mode="json") for item in result.assembled_contexts],
                "message_artifacts": [result.message_artifact.model_dump(mode="json")],
                "used_knowledge_base": result.used_knowledge_base,
                "trace": result.trace.model_dump(mode="json"),
            }

        retrieval_tool_result = retrieve_area_contexts_tool(
            session=session,
            principal=principal,
            settings=runtime_settings,
            area_id=state["area_id"],
            question=state["question"],
        )
        answer, _ = runtime.generate_answer(
            question=state["question"],
            assembled_contexts=retrieval_tool_result.assembled_contexts,
        )
        return {
            **state,
            "messages": [{"role": "assistant", "content": answer}],
            "answer": answer,
            "answer_blocks": [{"text": answer, "citation_context_indices": [], "display_citations": []}],
            "citations": [item.model_dump(mode="json") for item in retrieval_tool_result.citations],
            "assembled_contexts": build_assembled_context_payload(session, retrieval_tool_result),
            "message_artifacts": [
                {
                    "assistant_turn_index": _count_assistant_turns(state.get("messages")),
                    "answer": answer,
                    "answer_blocks": [{"text": answer, "citation_context_indices": [], "display_citations": []}],
                    "citations": [item.model_dump(mode="json") for item in retrieval_tool_result.citations],
                    "used_knowledge_base": bool(retrieval_tool_result.citations),
                }
            ],
            "used_knowledge_base": bool(retrieval_tool_result.citations),
            "trace": {
                "retrieval": retrieval_tool_result.trace["retrieval"],
                "assembler": retrieval_tool_result.trace["assembler"],
                "agent": {
                    "provider": runtime.provider_name,
                    "model": runtime.model,
                    "contexts_count": len(retrieval_tool_result.assembled_contexts),
                    "used_fallback": len(retrieval_tool_result.assembled_contexts) == 0,
                    "answer_path": "deepagents_unified",
                    "thinking_mode": False,
                    "thinking_mode_ignored": False,
                },
            },
        }
    finally:
        session.close()


def build_graph(_config=None):
    """建立 LangGraph public graph。"""

    workflow = StateGraph(ChatGraphState)
    workflow.add_node("run_chat", _run_chat_node)
    workflow.add_edge(START, "run_chat")
    workflow.add_edge("run_chat", END)
    return workflow.compile()


# 對外匯出的 compiled graph。
graph = build_graph()


def _count_assistant_turns(messages: object) -> int:
    """計算目前 thread state 中已存在的 assistant 訊息數量。

    參數：
    - `messages`：LangGraph thread state 內的 messages 欄位。

    回傳：
    - `int`：既有 assistant 訊息數量。
    """

    if not isinstance(messages, list):
        return 0
    count = 0
    for message in messages:
        if isinstance(message, dict):
            message_type = message.get("type")
            role = message.get("role")
            if message_type == "ai" or role == "assistant":
                count += 1
    return count
