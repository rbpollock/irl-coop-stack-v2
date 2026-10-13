"""Chat runtime：Deep Agents 正式路徑與 deterministic 測試 adapter。"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from typing import Any

from app.auth.verifier import CurrentPrincipal
from app.chat.agent.deep_agents import build_main_agent
from app.chat.contracts.types import (
    AgentLoopTracePayload,
    AgentToolContextPayload,
    AgentToolPayload,
    AssistantMessagePayload,
    ChatAnswerBlock,
    ChatAssembledContext,
    ChatAssembledContextPayload,
    ChatCitation,
    ChatCitationPayload,
    ChatMessageArtifact,
    ChatPhaseEventPayload,
    ChatReferencesEventPayload,
    ChatRuntimeResult,
    ChatTokenEventPayload,
    ChatToolCallEventPayload,
    ChatToolCallInputPayload,
    ChatTrace,
    ChatTracePayload,
    LangSmithMetadataPayload,
)
from app.chat.tools.retrieval import (
    RetrievalToolResult,
    _retrieve_area_contexts_internal,
)
from app.chat.tools.retrieval_serialization import (
    build_agent_tool_payload,
    build_assembled_context_payload,
    build_tool_call_output_summary,
)
from app.core.settings import AppSettings
from app.services.retrieval_assembler import AssembledContext

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
    tool = None  # type: ignore[assignment]

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
    ChatOpenAI = None  # type: ignore[assignment]

try:
    from langsmith import tracing_context
except ImportError:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
    tracing_context = None  # type: ignore[assignment]


# chat streaming debug 使用的模組 logger。
LOGGER = logging.getLogger(__name__)

# 回答中的 citation marker，例如 `[[C1]]` 或 `[[C1,C2]]`。
CITATION_MARKER_PATTERN = re.compile(r"\[\[(?P<labels>C\d+(?:\s*,\s*C\d+)*)\]\]")
# summary/compare 與一般 context answer 屬於低複雜度整理任務，固定採最小 reasoning effort。
OPENAI_REASONING_EFFORT = "low"


@dataclass(slots=True)
class AgentTrace:
    """answer layer 與 Deep Agents 的最小 trace。"""

    # 使用的 provider 名稱。
    provider: str
    # 使用的模型名稱。
    model: str
    # 傳入 answer layer 的 context 數量。
    contexts_count: int
    # 此次是否使用 fallback。
    used_fallback: bool
    # 本輪保留的 agent 執行摘要；目前未額外拆 task。
    agent_tasks: list[str]
    # 此次是否實際執行 retrieval。
    retrieval_invoked: bool
    # 實際啟用的 sub-agent 名稱。
    sub_agents_invoked: list[str]
    # 本輪正式回答路徑。
    answer_path: str = "deepagents_unified"
    # 本輪是否明確啟用 thinking mode。
    thinking_mode: bool = False
    # 本輪 thinking mode 是否被忽略。
    thinking_mode_ignored: bool = False
    # 本輪整體 runtime latency，單位為毫秒。
    runtime_latency_ms: float | None = None
    # summary/compare map-reduce 的最小 trace。
    map_reduce_trace: dict[str, object] | None = None


class DeterministicChatRuntime:
    """供測試與離線環境使用的穩定 answer runtime。"""

    def __init__(self, *, model: str) -> None:
        """初始化 deterministic chat runtime。

        參數：
        - `model`：用於 trace 的模型名稱。

        回傳：
        - `None`：此建構子只保存設定。
        """

        self.provider_name = "deterministic"
        self.model = model

    def generate_answer(self, *, question: str, assembled_contexts: list[AssembledContext]) -> tuple[str, AgentTrace]:
        """根據 contexts 產生穩定回答。

        參數：
        - `question`：使用者提問。
        - `assembled_contexts`：已組裝的 contexts。

        回傳：
        - `tuple[str, AgentTrace]`：回答文字與 trace。
        """

        if not assembled_contexts:
            return (
                "目前可用的已授權文件中沒有足夠內容可以回答這個問題。",
                AgentTrace(
                    provider=self.provider_name,
                    model=self.model,
                    contexts_count=0,
                    used_fallback=False,
                    agent_tasks=[],
                    retrieval_invoked=True,
                    sub_agents_invoked=[],
                ),
            )

        context_text = " ".join(context.assembled_text.replace("\n", " ").strip() for context in assembled_contexts[:2]).strip()
        headings = [context.heading for context in assembled_contexts if context.heading]
        heading_text = "、".join(dict.fromkeys(headings[:3])) if headings else "相關段落"
        return (
            f"根據目前已授權且完成索引的內容，問題「{question}」可參考 {heading_text}。重點如下：{context_text[:320]}",
            AgentTrace(
                provider=self.provider_name,
                model=self.model,
                contexts_count=len(assembled_contexts),
                used_fallback=False,
                agent_tasks=[],
                retrieval_invoked=True,
                sub_agents_invoked=[],
            ),
        )

    def stream_answer(self, *, question: str, assembled_contexts: list[AssembledContext]) -> Iterator[str]:
        """以穩定回答模擬串流輸出。

        參數：
        - `question`：使用者提問。
        - `assembled_contexts`：已組裝的 contexts。

        回傳：
        - `Iterator[str]`：單段回答文字。
        """

        answer, _ = self.generate_answer(question=question, assembled_contexts=assembled_contexts)
        yield answer


class DeepAgentsChatRuntime:
    """使用 Deep Agents 執行正式 area-scoped chat 的 runtime。"""

    def __init__(self, *, model: str, api_key: str, max_output_tokens: int, timeout_seconds: int) -> None:
        """初始化 Deep Agents runtime。

        參數：
        - `model`：要使用的 chat model 名稱。
        - `api_key`：OpenAI API key。
        - `max_output_tokens`：回答輸出上限。
        - `timeout_seconds`：OpenAI API timeout 秒數。

        回傳：
        - `None`：此建構子只保存設定。
        """

        self.provider_name = "deepagents"
        self.model = model
        self._api_key = api_key
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds

    def _build_langsmith_tags(self, *, settings: AppSettings) -> list[str]:
        """建立本次 chat invocation 的 LangSmith tags。

        參數：
        - `settings`：API 執行期設定。

        回傳：
        - `list[str]`：LangSmith UI 可篩選的 tags。
        """

        return [
            "deepagents",
            "langgraph",
            f"chat_provider:{self.provider_name}",
            f"chat_model:{settings.chat_model}",
        ]

    def _build_langsmith_metadata(
        self,
        *,
        principal: CurrentPrincipal,
        settings: AppSettings,
        area_id: str,
        question: str,
    ) -> LangSmithMetadataPayload:
        """建立本次 chat invocation 的 LangSmith metadata。

        參數：
        - `principal`：目前已驗證使用者。
        - `settings`：API 執行期設定。
        - `area_id`：目標 area。
        - `question`：使用者提問。

        回傳：
        - `dict[str, object]`：供 LangSmith trace 篩選與除錯使用的 metadata。
        """

        return {
            "area_id": area_id,
            "principal_sub": principal.sub,
            "principal_groups_count": len(principal.groups),
            "chat_provider": self.provider_name,
            "chat_model": settings.chat_model,
            "question_length": len(question),
        }

    def run(
        self,
        *,
        session,
        principal: CurrentPrincipal,
        settings: AppSettings,
        area_id: str,
        question: str,
        thinking_mode: bool = False,
        conversation_messages: list[object] | None = None,
        writer: Callable[[object], None] | None = None,
        benchmark_document_ids: tuple[str, ...] | None = None,
    ) -> ChatRuntimeResult:
        """執行 Deep Agents 回答，並回傳最終 graph state payload。

        參數：
        - `session`：目前資料庫 session。
        - `principal`：目前已驗證使用者。
        - `settings`：API 執行期設定。
        - `area_id`：目標 area。
        - `question`：使用者提問。
        - `thinking_mode`：是否啟用 thinking mode；目前僅保留為相容 metadata。
        - `conversation_messages`：目前 thread 已累積的對話訊息；若無則回退為單輪輸入。
        - `writer`：LangGraph custom event writer。
        - `benchmark_document_ids`：benchmark/test 專用文件白名單；public chat 不應傳入。

        回傳：
        - `dict[str, object]`：最終回答、references 與 trace。
        """

        if ChatOpenAI is None or tool is None:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
            raise RuntimeError("缺少 langchain-openai 或 langchain-core 依賴，無法建立 Deep Agents runtime。")

        retrieval_invoked = False
        retrieval_result: RetrievalToolResult | None = None
        citations_payload: list[ChatCitationPayload] = []
        assembled_contexts_payload: list[ChatAssembledContextPayload] = []
        llm_tool_contexts_payload: list[AgentToolContextPayload] = []
        latest_retrieval_result: RetrievalToolResult | None = None
        latest_loop_trace_delta: AgentLoopTracePayload = {}
        aggregated_contexts_by_key: dict[tuple[object, ...], ChatAssembledContextPayload] = {}
        agentic_round_summaries: list[dict[str, object]] = []
        tool_call_count = 0
        followup_call_count = 0
        synopsis_inspection_count = 0
        latency_budget_status = "normal"
        last_agentic_stop_reason = "not_started"
        stream_started_at = time.perf_counter()
        first_token_emitted = False

        def log_stream_debug(*, event: str, **fields: object) -> None:
            """在啟用 debug 時記錄 chat stream 關鍵時間點。

            參數：
            - `event`：事件名稱。
            - `**fields`：附帶欄位。

            回傳：
            - `None`：僅記錄 debug log。
            """

            if not settings.chat_stream_debug:
                return
            elapsed_ms = round((time.perf_counter() - stream_started_at) * 1000, 1)
            LOGGER.info(
                "chat_stream_debug event=%s elapsed_ms=%s area_id=%s question=%r fields=%s",
                event,
                elapsed_ms,
                area_id,
                question,
                fields,
            )

        def emit_phase(*, phase: str, status: str, message: str) -> None:
            """透過 LangGraph custom stream 發送高層 chat 階段事件。"""

            log_stream_debug(event="phase", phase=phase, status=status, message=message)
            if writer is None:
                return
            payload: ChatPhaseEventPayload = {
                "type": "phase",
                "phase": phase,
                "status": status,
                "message": message,
            }
            writer(payload)

        def emit_tool_call(
            *,
            name: str,
            status: str,
            input_payload: ChatToolCallInputPayload,
            output_payload: dict[str, object] | None = None,
        ) -> None:
            """透過 LangGraph custom stream 發送工具呼叫事件。"""

            log_stream_debug(event="tool_call", name=name, status=status)
            if writer is None:
                return
            payload: ChatToolCallEventPayload = {
                "type": "tool_call",
                "name": name,
                "status": status,
                "input": input_payload,
                "output": output_payload,
            }
            writer(payload)

        def emit_token(delta: str) -> None:
            """透過 LangGraph custom stream 發送回答 token 增量。

            參數：
            - `delta`：本次新增的回答文字片段。

            回傳：
            - `None`：僅將 token delta 寫入 custom stream。
            """

            if not delta:
                return
            log_stream_debug(event="token", delta_length=len(delta), delta_preview=delta[:80])
            if writer is None:
                return
            payload: ChatTokenEventPayload = {"type": "token", "delta": delta}
            writer(payload)

        def emit_references(references: list[ChatAssembledContextPayload]) -> None:
            """透過 LangGraph custom stream 提前發送 citation / context metadata。

            參數：
            - `references`：可供前端提早建立引用按鈕的 assembled context metadata。

            回傳：
            - `None`：僅將 references 寫入 custom stream。
            """

            log_stream_debug(event="references", references_count=len(references))
            if writer is None:
                return
            payload: ChatReferencesEventPayload = {
                "type": "references",
                "references": references,
            }
            writer(payload)

        agentic_followup_enabled = bool(settings.chat_agentic_enabled)

        def resolve_latency_budget_status() -> str:
            """計算目前回合的 latency budget 狀態。

            參數：
            - 無。

            回傳：
            - `str`：`normal | degraded | warning`。
            """

            elapsed_seconds = time.perf_counter() - stream_started_at
            if elapsed_seconds > settings.chat_agentic_max_latency_seconds:
                return "warning"
            if elapsed_seconds > settings.chat_agentic_target_latency_seconds:
                return "degraded"
            return "normal"

        def merge_retrieval_result(round_result: RetrievalToolResult) -> tuple[int, list[str]]:
            """將單回合 retrieval 結果合併為全 turn 穩定引用集合。

            參數：
            - `round_result`：本輪 retrieval 結果。

            回傳：
            - `tuple[int, list[str]]`：新增 contexts 數量與新增文件名稱。
            """

            nonlocal citations_payload
            nonlocal assembled_contexts_payload
            nonlocal llm_tool_contexts_payload
            nonlocal latest_retrieval_result
            nonlocal latest_loop_trace_delta

            round_contexts_payload = build_assembled_context_payload(session, round_result)
            new_document_names: list[str] = []
            new_context_count = 0
            for context in round_contexts_payload:
                context_key = (
                    context.get("document_id"),
                    context.get("parent_chunk_id"),
                    context.get("start_offset"),
                    context.get("end_offset"),
                )
                if context_key in aggregated_contexts_by_key:
                    continue
                context_index = len(aggregated_contexts_by_key)
                merged_context = {
                    **context,
                    "context_index": context_index,
                    "context_label": f"C{context_index + 1}",
                }
                aggregated_contexts_by_key[context_key] = merged_context
                new_context_count += 1
                document_name = str(merged_context.get("document_name") or "")
                if document_name and document_name not in new_document_names:
                    new_document_names.append(document_name)

            assembled_contexts_payload = list(aggregated_contexts_by_key.values())
            citations_payload = [
                {
                    "context_index": int(context["context_index"]),
                    "context_label": str(context["context_label"]),
                    "document_id": str(context["document_id"]),
                    "document_name": str(context["document_name"]),
                    "parent_chunk_id": context["parent_chunk_id"],
                    "child_chunk_ids": list(context["child_chunk_ids"]),
                    "heading": context["heading"],
                    "structure_kind": context["structure_kind"],
                    "start_offset": int(context["start_offset"]),
                    "end_offset": int(context["end_offset"]),
                    "excerpt": str(context["excerpt"]),
                    "source": str(context["source"]),
                    "truncated": bool(context["truncated"]),
                    "page_start": context.get("page_start"),
                    "page_end": context.get("page_end"),
                    "regions": list(context.get("regions", [])),
                }
                for context in assembled_contexts_payload
            ]
            llm_tool_contexts_payload = [
                {
                    "context_label": str(context["context_label"]),
                    "context_index": int(context["context_index"]),
                    "document_name": str(context["document_name"]),
                    "heading": context.get("heading"),
                    "assembled_text": str(context.get("assembled_text") or context.get("excerpt") or ""),
                }
                for context in assembled_contexts_payload
            ]
            latest_retrieval_result = round_result
            latest_loop_trace_delta = dict(round_result.loop_trace_delta)
            return new_context_count, new_document_names

        def build_current_agent_payload(*, stop_reason_override: str | None = None) -> AgentToolPayload:
            """建立回傳給 agent 的當前整體 tool payload。

            參數：
            - `stop_reason_override`：若有額外 stop reason，覆蓋目前回合的 stop reason。

            回傳：
            - `dict[str, object]`：序列化前的 agent payload。
            """

            return build_agent_tool_payload(
                session,
                latest_retrieval_result,
                assembled_contexts_payload=llm_tool_contexts_payload,
                loop_trace_delta=latest_loop_trace_delta,
                tool_call_count=tool_call_count,
                followup_call_count=followup_call_count,
                synopsis_inspection_count=synopsis_inspection_count,
                latency_budget_status=latency_budget_status,
                stop_reason=stop_reason_override or last_agentic_stop_reason,
            )

        def execute_retrieval_round(
            *,
            query_variant: str | None = None,
            document_handles: list[str] | None = None,
            inspect_synopsis_handles: list[str] | None = None,
            followup_reason: str | None = None,
        ) -> RetrievalToolResult:
            """執行單回合 retrieval，並更新全 turn 聚合狀態。

            參數：
            - `query_variant`：本輪 follow-up 的單一 query variant。
            - `document_handles`：本輪限定的文件 handles。
            - `inspect_synopsis_handles`：本輪想查看 synopsis 的文件 handles。
            - `followup_reason`：本輪補查原因。

            回傳：
            - `RetrievalToolResult`：本輪 retrieval 結果。
            """

            nonlocal retrieval_invoked
            nonlocal retrieval_result
            nonlocal tool_call_count
            nonlocal followup_call_count
            nonlocal synopsis_inspection_count
            nonlocal latency_budget_status
            nonlocal last_agentic_stop_reason

            tool_input: ChatToolCallInputPayload = {
                "area_id": area_id,
                "question": question,
                "query_variant": (query_variant or "").strip(),
                "document_handles": list(document_handles or []),
                "inspect_synopsis_handles": list(inspect_synopsis_handles or []),
                "followup_reason": (followup_reason or "").strip(),
            }
            emit_phase(phase="tool_calling", status="started", message="正在呼叫知識庫工具")
            emit_phase(phase="searching", status="started", message="正在搜尋知識庫內容")
            emit_tool_call(name="retrieve_area_contexts", status="started", input_payload=tool_input)
            round_result = _retrieve_area_contexts_internal(
                session=session,
                principal=principal,
                settings=settings,
                area_id=area_id,
                question=question,
                query_variant=query_variant,
                document_handles=document_handles,
                inspect_synopsis_handles=inspect_synopsis_handles,
                followup_reason=followup_reason,
                allowed_document_ids_override=benchmark_document_ids,
            )
            retrieval_result = round_result
            retrieval_invoked = True
            tool_call_count += 1
            if any((query_variant, document_handles, inspect_synopsis_handles, followup_reason)):
                followup_call_count += 1
            synopsis_inspection_count += len(inspect_synopsis_handles or [])
            latency_budget_status = resolve_latency_budget_status()
            new_context_count, new_document_names = merge_retrieval_result(round_result)
            coverage_signals = latest_retrieval_result.coverage_signals if latest_retrieval_result is not None else None
            if coverage_signals is not None and not bool(coverage_signals.insufficient_evidence):
                last_agentic_stop_reason = "coverage_satisfied"
            elif tool_call_count >= settings.chat_agentic_max_tool_calls_per_turn:
                last_agentic_stop_reason = "tool_call_limit_reached"
            elif any((query_variant, document_handles, inspect_synopsis_handles, followup_reason)) and new_context_count == 0:
                last_agentic_stop_reason = "no_new_evidence"
            else:
                last_agentic_stop_reason = "continue"
            latest_loop_trace_delta.update(
                {
                    "tool_call_index": tool_call_count,
                    "new_context_count": new_context_count,
                    "new_document_names": new_document_names,
                }
            )
            round_summary = {
                "tool_call_index": tool_call_count,
                "followup": bool(any((query_variant, document_handles, inspect_synopsis_handles, followup_reason))),
                "query_variant": (query_variant or "").strip(),
                "scoped_document_count": len(document_handles or []),
                "synopsis_inspection_count": len(inspect_synopsis_handles or []),
                "new_context_count": new_context_count,
                "new_document_names": new_document_names,
                "latency_budget_status": latency_budget_status,
                "stop_reason": last_agentic_stop_reason,
            }
            agentic_round_summaries.append(round_summary)
            emit_references(assembled_contexts_payload)
            log_stream_debug(
                event="retrieval_complete",
                contexts_count=len(assembled_contexts_payload),
                citations_count=len(citations_payload),
                tool_call_index=tool_call_count,
                latency_budget_status=latency_budget_status,
            )
            emit_phase(
                phase="searching",
                status="completed",
                message=f"知識庫搜尋完成，累積 {len(assembled_contexts_payload)} 個候選片段",
            )
            emit_phase(
                phase="tool_calling",
                status="completed",
                message=f"知識庫工具呼叫完成，累積 {len(citations_payload)} 則引用",
            )
            tool_output = build_tool_call_output_summary(session, round_result)
            tool_output.setdefault("agentic_tool_call_index", tool_call_count)
            tool_output.setdefault("tool_call_count", tool_call_count)
            tool_output.setdefault("followup_call_count", followup_call_count)
            tool_output.setdefault("synopsis_inspection_count", synopsis_inspection_count)
            tool_output.setdefault("latency_budget_status", latency_budget_status)
            tool_output.setdefault("stop_reason", last_agentic_stop_reason)
            tool_output.setdefault("new_context_count", new_context_count)
            tool_output.setdefault("new_document_names", new_document_names)
            emit_tool_call(
                name="retrieve_area_contexts",
                status="completed",
                input_payload=tool_input,
                output_payload=tool_output,
            )
            return round_result

        @tool
        def retrieve_area_contexts(
            query_variant: str | None = None,
            document_handles: list[str] | None = None,
            inspect_synopsis_handles: list[str] | None = None,
            followup_reason: str | None = None,
        ) -> str:
            """回傳目前 area 與問題的 assembled contexts、planning signals 與 trace。

            參數：
            - `query_variant`：agent follow-up 使用的單一 query variant。第一次呼叫通常不要提供；只有在需要換角度補查 compare / multi-document 缺口時才提供，且應保持明確簡短。
            - `document_handles`：agent follow-up 使用的文件 handles。當你已知缺的是特定文件 coverage，而不是整體查詢角度時，優先使用這個欄位縮小範圍。
            - `inspect_synopsis_handles`：要查看 synopsis hint 的文件 handles。只用於判斷下一步是否值得補查某份文件，不可把 synopsis hint 當成 citation 或最終結論。
            - `followup_reason`：本次 follow-up 的簡短原因。只有在你真的要做第二次以上的補查時才提供；若沒有新的 `query_variant`、`document_handles` 或 `inspect_synopsis_handles`，不要再次呼叫同一工具。

            回傳：
            - `str`：序列化後的 assembled context 與 planning payload。第一次呼叫通常只讀 `assembled_contexts`；之後可根據 `planning_documents`、`next_best_followups`、`evidence_cue_texts`、`coverage_signals` 與可選 `synopsis_hints` 規劃 follow-up。

            Follow-up 決策規則：
            - 若 `next_best_followups` 非空，且你尚未達到工具或 budget 限制，通常應優先再呼叫一次 `retrieve_area_contexts`，而不是立刻收斂成「證據不足」回答。
            - 若已知缺的是特定文件 coverage，優先使用 `document_handles`；若缺的是比較面向或提問角度，再使用單一且明確的 `query_variant`。
            - 只有在 `loop_trace_delta.stop_reason` 已明確顯示無新證據、已達工具上限、已達 synopsis 檢視上限，或你無法提出新的 follow-up 參數時，才直接承認證據不足並結束。

            使用範例：
            - 第一次呼叫：`retrieve_area_contexts()`
            - 若缺少特定文件 coverage：`retrieve_area_contexts(document_handles=["<tool 回傳的 handle>"], followup_reason="補查缺少的文件直接證據")`
            - 若缺少比較面向：`retrieve_area_contexts(query_variant="理賠審核需要哪些核准條件", followup_reason="補查 compare 缺少的審核面向")`
            - 若想先看 synopsis hint 再決定是否補查：`retrieve_area_contexts(inspect_synopsis_handles=["<tool 回傳的 handle>"], followup_reason="先看 synopsis 判斷是否值得補查")`
            """

            nonlocal last_agentic_stop_reason
            nonlocal latency_budget_status

            followup_requested = bool(any((query_variant, document_handles, inspect_synopsis_handles, followup_reason)))
            projected_synopsis_count = synopsis_inspection_count + len(inspect_synopsis_handles or [])
            if tool_call_count >= settings.chat_agentic_max_tool_calls_per_turn:
                last_agentic_stop_reason = "tool_call_limit_reached"
                latency_budget_status = resolve_latency_budget_status()
                return json.dumps(build_current_agent_payload(), ensure_ascii=False)
            if retrieval_result is not None and not followup_requested:
                last_agentic_stop_reason = "duplicate_initial_call_cached"
                latency_budget_status = resolve_latency_budget_status()
                return json.dumps(build_current_agent_payload(), ensure_ascii=False)
            if followup_requested and not agentic_followup_enabled:
                last_agentic_stop_reason = "followup_not_allowed"
                latency_budget_status = resolve_latency_budget_status()
                return json.dumps(build_current_agent_payload(), ensure_ascii=False)
            if projected_synopsis_count > settings.chat_agentic_max_synopsis_inspections_per_turn:
                last_agentic_stop_reason = "synopsis_inspection_limit_reached"
                latency_budget_status = resolve_latency_budget_status()
                return json.dumps(build_current_agent_payload(), ensure_ascii=False)

            execute_retrieval_round(
                query_variant=query_variant,
                document_handles=document_handles,
                inspect_synopsis_handles=inspect_synopsis_handles,
                followup_reason=followup_reason,
            )
            emit_phase(phase="thinking", status="started", message="正在根據檢索結果思考答案")
            return json.dumps(build_current_agent_payload(), ensure_ascii=False)

        llm_kwargs: dict[str, object] = {
            "model": self.model,
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
            "max_tokens": self._max_output_tokens,
            "streaming": True,
        }
        reasoning_effort = _resolve_openai_reasoning_effort(model_name=self.model)
        if reasoning_effort is not None:
            llm_kwargs["reasoning_effort"] = reasoning_effort
        llm = ChatOpenAI(**llm_kwargs)
        tracing_manager = nullcontext()
        emit_phase(phase="preparing", status="started", message="正在建立回答流程")
        if settings.langsmith_tracing:
            if tracing_context is None:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
                raise RuntimeError("缺少 langsmith 依賴，無法啟用 LangSmith tracing。")
            if not settings.langsmith_api_key:
                raise ValueError("啟用 LangSmith tracing 前必須提供 LANGSMITH_API_KEY。")
            tracing_manager = tracing_context(
                enabled=True,
                project_name=settings.langsmith_project,
                tags=self._build_langsmith_tags(settings=settings),
                metadata=self._build_langsmith_metadata(
                    principal=principal,
                    settings=settings,
                    area_id=area_id,
                    question=question,
                ),
            )

        emit_phase(phase="preparing", status="completed", message="回答流程準備完成")
        emit_phase(phase="thinking", status="started", message="正在思考如何回答")
        main_agent = build_main_agent(model=llm, retrieve_area_contexts_tool=retrieve_area_contexts)
        log_stream_debug(event="agent_stream_start")

        result: object | None = None
        streamed_answer_parts: list[str] = []
        with tracing_manager:
            for stream_item in main_agent.stream(
                {
                    "messages": _build_agent_input_messages(
                        question=question,
                        conversation_messages=conversation_messages,
                    )
                },
                stream_mode=["messages", "values"],
            ):
                stream_mode, stream_payload = _normalize_agent_stream_item(stream_item)
                if stream_mode == "messages":
                    text_delta = _extract_stream_message_text(stream_payload)
                    if text_delta:
                        if not first_token_emitted:
                            first_token_emitted = True
                            emit_phase(phase="drafting", status="started", message="正在生成回答內容")
                            log_stream_debug(
                                event="first_answer_token",
                                delta_preview=text_delta[:80],
                                delta_length=len(text_delta),
                            )
                        streamed_answer_parts.append(text_delta)
                        emit_token(text_delta)
                    continue
                if stream_mode == "values" and isinstance(stream_payload, dict):
                    log_stream_debug(
                        event="agent_values",
                        message_count=(
                            len(stream_payload.get("messages", []))
                            if isinstance(stream_payload.get("messages"), list)
                            else 0
                        ),
                        has_answer=bool(_extract_final_answer_text(stream_payload)),
                    )
                    result = stream_payload

        raw_answer = _extract_final_answer_text(result) or "".join(streamed_answer_parts).strip() or "目前無法根據現有內容生成穩定回答。"
        if (
            latest_retrieval_result is not None
            and latest_retrieval_result.coverage_signals is not None
            and bool(latest_retrieval_result.coverage_signals.insufficient_evidence)
            and not _answer_mentions_insufficient_evidence(raw_answer)
        ):
            raw_answer = (
                f"{raw_answer}\n\n目前引用內容仍不足以完成完整比較；以下僅整理目前可直接支持的證據。"
            ).strip()
        answer, answer_blocks = _build_answer_blocks_from_markers(
            answer=raw_answer,
            citations_payload=citations_payload,
        )
        used_knowledge_base = bool(citations_payload) or retrieval_invoked
        log_stream_debug(
            event="answer_complete",
            token_events=len(streamed_answer_parts),
            answer_length=len(answer),
            retrieval_invoked=retrieval_invoked,
            tool_call_count=tool_call_count,
            latency_budget_status=latency_budget_status,
        )
        emit_phase(phase="drafting", status="completed", message="回答草稿已完成")
        emit_phase(phase="thinking", status="completed", message="回答內容已整理完成")

        runtime_latency_ms = round((time.perf_counter() - stream_started_at) * 1000, 2)
        agent_trace_payload = asdict(
            AgentTrace(
                provider=self.provider_name,
                model=self.model,
                contexts_count=len(assembled_contexts_payload),
                used_fallback=False,
                agent_tasks=[],
                retrieval_invoked=retrieval_invoked,
                sub_agents_invoked=[],
                answer_path="deepagents_unified",
                thinking_mode=thinking_mode,
                thinking_mode_ignored=bool(thinking_mode),
                runtime_latency_ms=runtime_latency_ms,
            )
        )
        agent_trace_payload["agentic_loop"] = {
            "enabled": agentic_followup_enabled,
            "tool_call_count": tool_call_count,
            "followup_call_count": followup_call_count,
            "synopsis_inspection_count": synopsis_inspection_count,
            "latency_budget_status": latency_budget_status,
            "stop_reason": last_agentic_stop_reason,
            "rounds": agentic_round_summaries,
        }
        trace: ChatTracePayload = {
            "retrieval": retrieval_result.trace["retrieval"] if retrieval_result is not None else {},
            "assembler": retrieval_result.trace["assembler"] if retrieval_result is not None else {"contexts": []},
            "agent": agent_trace_payload,
        }
        citations = [ChatCitation.model_validate(item) for item in citations_payload]
        assembled_contexts = [ChatAssembledContext.model_validate(item) for item in assembled_contexts_payload]
        message_artifact = ChatMessageArtifact(
            assistant_turn_index=_count_assistant_turns(conversation_messages),
            answer=answer,
            answer_blocks=answer_blocks,
            citations=citations,
            used_knowledge_base=used_knowledge_base,
        )
        return ChatRuntimeResult(
            answer=answer,
            answer_blocks=answer_blocks,
            citations=citations,
            assembled_contexts=assembled_contexts,
            message_artifact=message_artifact,
            used_knowledge_base=used_knowledge_base,
            trace=ChatTrace.model_validate(trace),
            raw_result=result,
        )


def _build_answer_blocks_from_markers(
    *,
    answer: str,
    citations_payload: list[ChatCitationPayload],
) -> tuple[str, list[ChatAnswerBlock]]:
    """將回答中的 citation markers 解析為 UI 可用的 answer blocks。

    參數：
    - `answer`：LLM 產出的原始回答文字。
    - `citations_payload`：目前回合的 citation payload。

    回傳：
    - `tuple[str, list[ChatAnswerBlock]]`：去除 marker 的回答與解析後區塊。
    """

    citation_by_label = {
        str(citation["context_label"]): citation
        for citation in citations_payload
        if isinstance(citation.get("context_label"), str)
    }
    raw_blocks = re.split(r"\n\s*\n", answer.strip())
    answer_blocks: list[ChatAnswerBlock] = []

    for raw_block in raw_blocks:
        labels: list[str] = []

        def replace_marker(match: re.Match[str]) -> str:
            """擷取 marker 中的 labels，並在輸出文字中移除 marker。

            參數：
            - `match`：命中的 marker regex。

            回傳：
            - `str`：固定回傳空字串，代表移除 marker 本身。
            """

            for label in [item.strip() for item in match.group("labels").split(",")]:
                if label and label not in labels:
                    labels.append(label)
            return ""

        cleaned_text = CITATION_MARKER_PATTERN.sub(replace_marker, raw_block).strip()
        cleaned_text = re.sub(r"[ \t]{2,}", " ", cleaned_text)
        if not cleaned_text:
            continue
        display_citations = [citation_by_label[label] for label in labels if label in citation_by_label]
        answer_blocks.append(
            ChatAnswerBlock.model_validate(
                {
                    "text": cleaned_text,
                    "citation_context_indices": [
                        int(item["context_index"])
                        for item in display_citations
                        if isinstance(item.get("context_index"), int)
                    ],
                    "display_citations": display_citations,
                }
            )
        )

    if answer_blocks:
        clean_answer = "\n\n".join(block.text for block in answer_blocks)
        return clean_answer, answer_blocks

    fallback_answer = CITATION_MARKER_PATTERN.sub("", answer).strip()
    fallback_text = fallback_answer or answer.strip()
    return fallback_text, [ChatAnswerBlock(text=fallback_text, citation_context_indices=[], display_citations=[])]


def _answer_mentions_insufficient_evidence(answer: str) -> bool:
    """判斷回答是否已明確承認證據不足。

    參數：
    - `answer`：目前回答文字。

    回傳：
    - `bool`：若回答已包含證據不足語句則為 `True`。
    """

    normalized = answer.lower()
    return any(
        phrase in normalized
        for phrase in (
            "證據不足",
            "資訊不足",
            "無法確認",
            "目前引用內容仍不足",
            "insufficient evidence",
            "not enough evidence",
            "cannot confirm",
        )
    )


def _resolve_openai_reasoning_effort(*, model_name: str) -> str | None:
    """依模型名稱選擇可接受的 reasoning effort。

    參數：
    - `model_name`：目前使用的 OpenAI chat model 名稱。

    回傳：
    - `str | None`：對應模型可接受的 reasoning effort；若應省略則回傳空值。
    """

    normalized = model_name.strip().lower()
    if normalized.startswith("gpt-5.4"):
        return None
    return OPENAI_REASONING_EFFORT


def _count_assistant_turns(conversation_messages: list[object] | None) -> int:
    """計算目前 thread 中既有 assistant turn 數量。

    參數：
    - `conversation_messages`：目前 thread 已累積的訊息列表。

    回傳：
    - `int`：本輪 assistant artifact 應使用的 turn index。
    """

    if not isinstance(conversation_messages, list):
        return 0

    assistant_turns = 0
    for message in conversation_messages:
        if isinstance(message, dict):
            message_type = message.get("type")
            role = message.get("role")
            if message_type == "ai" or role == "assistant":
                assistant_turns += 1
    return assistant_turns


def build_chat_runtime(settings: AppSettings) -> DeterministicChatRuntime | DeepAgentsChatRuntime:
    """依照設定建立 chat runtime。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - runtime：deterministic 或 Deep Agents runtime。
    """

    provider_name = settings.chat_provider.strip().lower()
    if provider_name == "deterministic":
        return DeterministicChatRuntime(model=settings.chat_model)
    if provider_name == "deepagents":
        if not settings.openai_api_key:
            raise ValueError("使用 Deep Agents runtime 前必須提供 OPENAI_API_KEY。")
        return DeepAgentsChatRuntime(
            model=settings.chat_model,
            api_key=settings.openai_api_key,
            max_output_tokens=settings.chat_max_output_tokens,
            timeout_seconds=settings.chat_timeout_seconds,
        )
    raise ValueError(f"不支援的 chat provider：{settings.chat_provider}；僅支援 deterministic 與 deepagents。")


def _build_agent_input_messages(*, question: str, conversation_messages: list[object] | None) -> list[object]:
    """建立送進 Deep Agents 的對話訊息列表。

    參數：
    - `question`：目前這一輪的使用者問題。
    - `conversation_messages`：thread 內已累積的訊息列表。

    回傳：
    - `list[object]`：可直接送入 Deep Agents 的 message payload。
    """

    if isinstance(conversation_messages, list) and conversation_messages:
        return conversation_messages
    return [{"role": "user", "content": question}]


def _extract_final_answer_text(result: object) -> str:
    """依官方建議，從 agent 最終 `messages` 取最後一則回答文字。"""

    if not isinstance(result, dict):
        return ""
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return ""
    final_message = messages[-1]
    if isinstance(final_message, dict):
        content = final_message.get("content")
    else:
        content = getattr(final_message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return _flatten_message_content(content)
    return ""


def extract_final_assistant_message(result: object) -> AssistantMessagePayload | None:
    """從 Deep Agents 最終結果擷取最後一則助理訊息。

    參數：
    - `result`：Deep Agents `values` stream 最終 payload。

    回傳：
    - `dict[str, Any] | None`：可回寫到 LangGraph thread state 的助理訊息；若不存在則回傳 `None`。
    """

    if not isinstance(result, dict):
        return None
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    final_message = messages[-1]
    if isinstance(final_message, dict):
        message_type = final_message.get("type")
        role = final_message.get("role")
        if message_type == "ai" or role == "assistant":
            return final_message
        return None

    message_type = getattr(final_message, "type", None)
    message_content = getattr(final_message, "content", None)
    if message_type != "ai":
        return None
    return {
        "type": "ai",
        "role": "assistant",
        "content": message_content,
    }


def _normalize_agent_stream_item(stream_item: object) -> tuple[str | None, object]:
    """將 Deep Agents stream item 正規化為 `(stream_mode, payload)`。"""

    if isinstance(stream_item, tuple) and len(stream_item) == 2 and isinstance(stream_item[0], str):
        return stream_item[0], stream_item[1]
    return None, stream_item


def _extract_stream_message_text(stream_payload: object) -> str:
    """從 Deep Agents `messages` stream payload 擷取本次文字增量。"""

    if not isinstance(stream_payload, tuple) or not stream_payload:
        return ""
    message_like = stream_payload[0]
    if isinstance(message_like, dict):
        content = message_like.get("content")
    else:
        content = getattr(message_like, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _flatten_message_content(content)
    return ""


def _flatten_message_content(content: list[object]) -> str:
    """將最後一則 message 的 content block 列表展平成純文字。"""

    text_parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            text_parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        text_value = item.get("text")
        if isinstance(text_value, str):
            text_parts.append(text_value)
            continue
        if item.get("type") == "text" and isinstance(item.get("content"), str):
            text_parts.append(str(item["content"]))
    return "".join(text_parts)
