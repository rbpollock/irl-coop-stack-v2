"""Chat answer、citation 與 trace 的資料契約。"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict

from app.db.models import ChunkStructureKind


class ChatCitationRegion(BaseModel):
    """單一 citation 的 PDF locator。"""

    # 所屬頁碼。
    page_number: int
    # 同一 citation/chunk 內的區域順序。
    region_order: int
    # 左邊界座標。
    bbox_left: float
    # 下邊界座標。
    bbox_bottom: float
    # 右邊界座標。
    bbox_right: float
    # 上邊界座標。
    bbox_top: float


class ChatDisplayCitation(BaseModel):
    """前端顯示用的單一 citation chip。"""

    # 引用對應的 context 順序。
    context_index: int
    # 提供給回答與 UI 共用的穩定引用標籤。
    context_label: str
    # 引用所屬文件識別碼。
    document_id: str
    # 引用所屬文件名稱。
    document_name: str
    # 引用所屬段落標題。
    heading: str | None
    # 引用涵蓋的起始頁碼。
    page_start: int | None = None
    # 引用涵蓋的結束頁碼。
    page_end: int | None = None


class ChatAnswerBlock(BaseModel):
    """回答中的單一可顯示文字區塊。"""

    # 區塊純文字內容。
    text: str
    # 此區塊引用的 context 順序列表。
    citation_context_indices: list[int]
    # 提供 UI 句尾 chips 使用的 citation 清單。
    display_citations: list[ChatDisplayCitation]


class ChatCitation(BaseModel):
    """單一 assembled-context reference。"""

    # context 在回傳列表中的順序。
    context_index: int
    # 提供給回答與 UI 共用的穩定引用標籤。
    context_label: str
    # context 所屬文件識別碼。
    document_id: str
    # context 所屬文件名稱。
    document_name: str
    # context 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 合併進此 context 的 child chunk 識別碼。
    child_chunk_ids: list[str]
    # context 所屬段落標題。
    heading: str | None
    # context 內容結構型別。
    structure_kind: ChunkStructureKind
    # context 在 normalized text 的起始 offset。
    start_offset: int
    # context 在 normalized text 的結束 offset。
    end_offset: int
    # context 組裝後可直接送入 LLM 的文字。
    excerpt: str
    # context 來源，可能為 vector、fts 或 hybrid。
    source: str
    # 此 context 是否發生文字裁切。
    truncated: bool
    # context 涵蓋的起始頁碼。
    page_start: int | None = None
    # context 涵蓋的結束頁碼。
    page_end: int | None = None
    # context 關聯的 PDF locator。
    regions: list[ChatCitationRegion] = []


class ChatTrace(BaseModel):
    """整合 retrieval、assembler 與 agent 的 trace。"""

    # retrieval trace metadata。
    retrieval: dict[str, Any]
    # assembler trace metadata。
    assembler: dict[str, Any]
    # answer layer trace metadata。
    agent: dict[str, Any]


class ChatMessageArtifact(BaseModel):
    """持久化於 LangGraph thread state 的 assistant turn UI artifact。"""

    # assistant turn 在 thread 內的順序。
    assistant_turn_index: int
    # 乾淨回答文字。
    answer: str
    # 解析後的回答區塊。
    answer_blocks: list[ChatAnswerBlock]
    # 對應此 turn 的 assembled-context references。
    citations: list[ChatCitation]
    # 此回合是否使用知識庫內容。
    used_knowledge_base: bool


class ChatAssembledContext(BaseModel):
    """前端與 LangGraph state 共用的 assembled context 契約。"""

    # context 在回傳列表中的順序。
    context_index: int
    # 提供給回答與 UI 共用的穩定引用標籤。
    context_label: str
    # context 所屬文件識別碼。
    document_id: str
    # context 所屬文件名稱。
    document_name: str
    # context 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 合併進此 context 的 child chunk 識別碼。
    child_chunk_ids: list[str]
    # context 內容結構型別。
    structure_kind: ChunkStructureKind
    # context 所屬段落標題。
    heading: str | None
    # context 摘錄文字。
    excerpt: str
    # context 完整 assembled 文字。
    assembled_text: str
    # context 來源，可能為 vector、fts 或 hybrid。
    source: str
    # context 在 normalized text 的起始 offset。
    start_offset: int
    # context 在 normalized text 的結束 offset。
    end_offset: int
    # context 涵蓋的起始頁碼。
    page_start: int | None = None
    # context 涵蓋的結束頁碼。
    page_end: int | None = None
    # context 關聯的 PDF locator。
    regions: list[ChatCitationRegion] = []
    # context 是否發生裁切。
    truncated: bool


class ChatRuntimeResult(BaseModel):
    """正式 chat runtime 的跨模組回傳契約。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 最終回答文字。
    answer: str
    # 解析後的回答區塊。
    answer_blocks: list[ChatAnswerBlock]
    # 對應此回合的 citation 清單。
    citations: list[ChatCitation]
    # 對應此回合的 assembled contexts。
    assembled_contexts: list[ChatAssembledContext]
    # 需持久化到 LangGraph thread state 的 UI artifact。
    message_artifact: ChatMessageArtifact
    # 此回合是否使用知識庫內容。
    used_knowledge_base: bool
    # retrieval、assembler 與 agent trace。
    trace: ChatTrace
    # Deep Agents stream `values` 最終 payload；只供 thread state 萃取最後訊息時使用。
    raw_result: object | None = None


class LangSmithMetadataPayload(TypedDict):
    """LangSmith metadata payload。"""

    # 本次 chat 所屬 area。
    area_id: str
    # 目前使用者 sub。
    principal_sub: str
    # 目前使用者群組數量。
    principal_groups_count: int
    # chat provider 名稱。
    chat_provider: str
    # chat model 名稱。
    chat_model: str
    # 使用者問題字元數。
    question_length: int


class PrincipalPayload(TypedDict, total=False):
    """LangGraph state 與 auth middleware 共用的 principal payload。"""

    # 使用者 sub。
    sub: str
    # 使用者 groups claim。
    groups: list[str]
    # 是否已完成驗證。
    authenticated: bool
    # 顯示名稱。
    name: str | None
    # 偏好使用者名稱。
    preferred_username: str | None


class AssistantMessagePayload(TypedDict, total=False):
    """可回寫到 LangGraph thread state 的 assistant message。"""

    # LangChain / LangGraph message type。
    type: str
    # 對話角色。
    role: str
    # 最終訊息內容；可能為純文字或 content blocks。
    content: str | list[object] | None


class ChatCitationRegionPayload(TypedDict):
    """JSON-friendly citation region payload。"""

    # 所屬頁碼。
    page_number: int
    # 區域順序。
    region_order: int
    # 左邊界座標。
    bbox_left: float
    # 下邊界座標。
    bbox_bottom: float
    # 右邊界座標。
    bbox_right: float
    # 上邊界座標。
    bbox_top: float


class ChatDisplayCitationPayload(TypedDict):
    """JSON-friendly display citation payload。"""

    # 引用對應的 context 順序。
    context_index: int
    # 穩定引用標籤。
    context_label: str
    # 文件識別碼。
    document_id: str
    # 文件名稱。
    document_name: str
    # 段落標題。
    heading: str | None
    # 起始頁碼。
    page_start: int | None
    # 結束頁碼。
    page_end: int | None


class ChatAnswerBlockPayload(TypedDict):
    """JSON-friendly answer block payload。"""

    # 區塊文字內容。
    text: str
    # 此區塊引用的 context 順序列表。
    citation_context_indices: list[int]
    # 句尾 citation chips。
    display_citations: list[ChatDisplayCitationPayload]


class ChatCitationPayload(TypedDict):
    """JSON-friendly citation payload。"""

    # context 順序。
    context_index: int
    # 穩定引用標籤。
    context_label: str
    # 文件識別碼。
    document_id: str
    # 文件名稱。
    document_name: str
    # parent chunk 識別碼。
    parent_chunk_id: str | None
    # child chunk 識別碼列表。
    child_chunk_ids: list[str]
    # 段落標題。
    heading: str | None
    # 結構型別字串。
    structure_kind: str
    # 起始 offset。
    start_offset: int
    # 結束 offset。
    end_offset: int
    # 摘錄文字。
    excerpt: str
    # 來源。
    source: str
    # 是否裁切。
    truncated: bool
    # 起始頁碼。
    page_start: int | None
    # 結束頁碼。
    page_end: int | None
    # PDF locator 清單。
    regions: list[ChatCitationRegionPayload]


class ChatAssembledContextPayload(TypedDict):
    """JSON-friendly assembled context payload。"""

    # context 順序。
    context_index: int
    # 穩定引用標籤。
    context_label: str
    # 文件識別碼。
    document_id: str
    # 文件名稱。
    document_name: str
    # parent chunk 識別碼。
    parent_chunk_id: str | None
    # child chunk 識別碼列表。
    child_chunk_ids: list[str]
    # 結構型別字串。
    structure_kind: str
    # 段落標題。
    heading: str | None
    # 摘錄文字。
    excerpt: str
    # 組裝後完整文字。
    assembled_text: str
    # 來源。
    source: str
    # 起始 offset。
    start_offset: int
    # 結束 offset。
    end_offset: int
    # 起始頁碼。
    page_start: int | None
    # 結束頁碼。
    page_end: int | None
    # PDF locator 清單。
    regions: list[ChatCitationRegionPayload]
    # 是否裁切。
    truncated: bool


class ChatTracePayload(TypedDict):
    """JSON-friendly chat trace payload。"""

    # retrieval trace metadata。
    retrieval: dict[str, Any]
    # assembler trace metadata。
    assembler: dict[str, Any]
    # answer layer trace metadata。
    agent: dict[str, Any]


class RetrievalToolTracePayload(TypedDict):
    """retrieval tool 對外暴露的 trace payload。"""

    # retrieval trace metadata。
    retrieval: dict[str, Any]
    # assembler trace metadata。
    assembler: dict[str, Any]


class ChatMessageArtifactPayload(TypedDict):
    """JSON-friendly message artifact payload。"""

    # assistant turn 順序。
    assistant_turn_index: int
    # 乾淨回答文字。
    answer: str
    # 解析後的回答區塊。
    answer_blocks: list[ChatAnswerBlockPayload]
    # 對應此 turn 的 citations。
    citations: list[ChatCitationPayload]
    # 是否使用知識庫。
    used_knowledge_base: bool


class RetrievalPlanningDocumentPayload(TypedDict, total=False):
    """LLM 可見的 planning document payload。"""

    # 安全文件 handle。
    handle: str
    # 文件名稱。
    document_name: str
    # 是否由 query mention 命中。
    mentioned_by_query: bool
    # 是否在本輪 retrieval 命中。
    hit_in_current_round: bool
    # 是否有 synopsis 可供檢視。
    synopsis_available: bool


class RetrievalCoverageSignalsPayload(TypedDict):
    """LLM 可見的 coverage signals payload。"""

    # 目前缺少 citation-ready evidence 的文件名稱。
    missing_document_names: list[str]
    # 是否已具備 compare 所需的雙邊證據。
    supports_compare: bool
    # 是否仍屬證據不足。
    insufficient_evidence: bool
    # 仍缺少的 compare 面向。
    missing_compare_axes: list[str]
    # 本輪是否有新增 evidence。
    new_evidence_found: bool


class RetrievalEvidenceCuePayload(TypedDict):
    """LLM 可見的 evidence cue payload。"""

    # 對應的 context label。
    context_label: str
    # 所屬文件名稱。
    document_name: str
    # 短摘錄文字。
    cue_text: str


class RetrievalSynopsisHintPayload(TypedDict, total=False):
    """LLM 可見的 synopsis hint payload。"""

    # 安全文件 handle。
    handle: str
    # 文件名稱。
    document_name: str
    # synopsis 摘錄文字。
    synopsis_text: str


class AgentToolContextPayload(TypedDict):
    """提供給 LLM 的最小 assembled context payload。"""

    # 穩定引用標籤。
    context_label: str
    # context 順序。
    context_index: int
    # 文件名稱。
    document_name: str
    # 段落標題。
    heading: str | None
    # context 組裝後文字。
    assembled_text: str


class AgentLoopTracePayload(TypedDict, total=False):
    """agentic loop 可序列化摘要。"""

    # 使用者原始問題。
    base_question: str
    # 本輪實際檢索查詢。
    effective_query: str
    # follow-up query variant。
    query_variant: str
    # 本輪限制的文件識別碼。
    scoped_document_ids: list[str]
    # 本輪要求檢視 synopsis 的文件識別碼。
    inspect_synopsis_document_ids: list[str]
    # 本輪 follow-up 原因。
    followup_reason: str
    # 本輪已執行工具次數。
    tool_call_count: int
    # 本輪 follow-up 次數。
    followup_call_count: int
    # 本輪 synopsis 檢視次數。
    synopsis_inspection_count: int
    # 目前 latency budget 狀態。
    latency_budget_status: str
    # 目前 stop reason。
    stop_reason: str
    # 本次工具呼叫序號。
    tool_call_index: int
    # 本輪新增 context 數量。
    new_context_count: int
    # 本輪新增文件名稱。
    new_document_names: list[str]


class AgentResponseContractPayload(TypedDict):
    """提供給 LLM 的回答 guardrail payload。"""

    # 任務類型。
    task_type: str
    # 回答至少應覆蓋的文件名稱。
    required_document_names: list[str]
    # compare 題固定回答模板。
    compare_answer_template: list[str]


class AgentToolPayload(TypedDict, total=False):
    """`retrieve_area_contexts` 工具回傳給 LLM 的正式 payload。"""

    # 可供回答使用的 assembled contexts。
    assembled_contexts: list[AgentToolContextPayload]
    # compare / multi-document coverage 訊號。
    coverage_signals: RetrievalCoverageSignalsPayload | None
    # 規劃用的文件資訊。
    planning_documents: list[RetrievalPlanningDocumentPayload]
    # 建議 follow-up 清單。
    next_best_followups: list[str]
    # evidence cue 清單。
    evidence_cue_texts: list[RetrievalEvidenceCuePayload]
    # synopsis hints 清單。
    synopsis_hints: list[RetrievalSynopsisHintPayload]
    # 本輪 loop trace 摘要。
    loop_trace_delta: AgentLoopTracePayload
    # 可選的回答 guardrail。
    response_contract: AgentResponseContractPayload


class ChatPhaseEventPayload(TypedDict):
    """LangGraph custom stream 的 phase event。"""

    # custom event 類型。
    type: str
    # chat phase 名稱。
    phase: str
    # phase 狀態。
    status: str
    # 顯示訊息。
    message: str


class ChatToolCallInputPayload(TypedDict):
    """LangGraph custom stream 的 tool input payload。"""

    # 目前 area 識別碼。
    area_id: str
    # 使用者原始問題。
    question: str
    # 可選 query variant。
    query_variant: str
    # 文件 handles。
    document_handles: list[str]
    # synopsis handles。
    inspect_synopsis_handles: list[str]
    # follow-up 原因。
    followup_reason: str


class ChatToolCallEventPayload(TypedDict, total=False):
    """LangGraph custom stream 的 tool call event。"""

    # custom event 類型。
    type: str
    # 工具名稱。
    name: str
    # 工具執行狀態。
    status: str
    # 工具輸入 payload。
    input: ChatToolCallInputPayload
    # 工具輸出摘要。
    output: dict[str, object] | None


class ChatTokenEventPayload(TypedDict):
    """LangGraph custom stream 的 token event。"""

    # custom event 類型。
    type: str
    # 本次 token 增量。
    delta: str


class ChatReferencesEventPayload(TypedDict):
    """LangGraph custom stream 的 references event。"""

    # custom event 類型。
    type: str
    # assembled contexts 清單。
    references: list[ChatAssembledContextPayload]
