"""Retrieval tool 的文件規劃、coverage 訊號與 synopsis hint helper。"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
import binascii
from dataclasses import dataclass

from sqlalchemy import select

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import Document, DocumentStatus, EvaluationQueryType
from app.services.access import require_area_access
from app.services.retrieval_assembler import AssembledContext


# agent follow-up retrieval 每次最多回傳的 planning 文件數。
MAX_PLANNING_DOCUMENTS = 5
# agent 可見的 synopsis hint 最長字元數。
MAX_SYNOPSIS_HINT_CHARS = 500
# query-time evidence cue 最長字元數。
MAX_EVIDENCE_CUE_CHARS = 220


@dataclass(slots=True)
class RetrievalPlanningDocument:
    """agent 可見的單一文件規劃資訊。"""

    # 後端核發給 agent 的文件 handle。
    handle: str
    # 文件名稱。
    document_name: str
    # 此文件是否由 query mention resolver 命中。
    mentioned_by_query: bool
    # 此文件是否在本輪 retrieval 命中。
    hit_in_current_round: bool
    # 此文件是否有可供規劃的 synopsis。
    synopsis_available: bool


@dataclass(slots=True)
class RetrievalEvidenceCue:
    """agent / debug UI 可見的 evidence cue。"""

    # 對應的 context label。
    context_label: str
    # cue 所屬文件名稱。
    document_name: str
    # 從 assembled evidence 擷取的短摘錄。
    cue_text: str


@dataclass(slots=True)
class RetrievalSynopsisHint:
    """agent 可見的 synopsis planning hint。"""

    # 對應的文件 handle。
    handle: str
    # 文件名稱。
    document_name: str
    # 摘錄後的 synopsis 文字。
    synopsis_text: str


@dataclass(slots=True)
class RetrievalCoverageSignals:
    """summary/compare follow-up 用的 coverage 訊號。"""

    # 目前缺少 citation-ready evidence 的文件名稱。
    missing_document_names: list[str]
    # 是否已具備至少兩份文件的 compare evidence。
    supports_compare: bool
    # 目前是否仍應視為證據不足。
    insufficient_evidence: bool
    # 仍缺少的 compare 面向。
    missing_compare_axes: list[str]
    # 本輪是否有新增 evidence。
    new_evidence_found: bool


def load_authorized_ready_documents(
    *,
    session,
    principal: CurrentPrincipal,
    area_id: str,
) -> list[Document]:
    """讀取目前 area 內已授權且 ready 的文件清單。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。

    回傳：
    - `list[Document]`：已授權且 `status=ready` 的文件。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    return list(
        session.scalars(
            select(Document)
            .where(Document.area_id == area_id, Document.status == DocumentStatus.ready)
            .order_by(Document.created_at.asc(), Document.file_name.asc())
        ).all()
    )


def normalize_query_variant(
    *,
    query_variant: str | None,
    settings: AppSettings,
) -> str | None:
    """清理並限制 agent follow-up 的單一 query variant。

    參數：
    - `query_variant`：原始 query variant。
    - `settings`：應用程式設定。

    回傳：
    - `str | None`：正規化後的單一 query variant；若未提供則回傳空值。
    """

    if query_variant is None:
        return None

    normalized = str(query_variant).strip()
    if not normalized:
        return None
    return normalized[: settings.chat_agentic_max_query_variant_chars]


def resolve_document_handles(
    *,
    handles: list[str] | tuple[str, ...] | None,
    authorized_document_ids: tuple[str, ...],
    settings: AppSettings,
    max_items: int | None = None,
) -> tuple[str, ...] | None:
    """將 agent 提供的安全文件 handles 解析回已授權的文件識別碼。

    參數：
    - `handles`：agent 提供的安全文件 handles。
    - `authorized_document_ids`：目前 area 內已授權且 ready 的文件識別碼。
    - `settings`：應用程式設定。
    - `max_items`：本次最多允許解析的 handle 數量。

    回傳：
    - `tuple[str, ...] | None`：驗證通過後的文件識別碼白名單。
    """

    if not handles:
        return None

    normalized_handles = [str(handle).strip() for handle in handles if str(handle).strip()]
    if not normalized_handles:
        return None

    limit = max_items or settings.chat_agentic_max_scoped_documents_per_call
    if len(normalized_handles) > limit:
        raise ValueError("document_handles 超出單次 tool call 允許上限。")

    authorized_document_id_set = set(authorized_document_ids)
    resolved_ids: list[str] = []
    for handle in normalized_handles:
        document_id = decode_document_handle(handle=handle)
        if document_id not in authorized_document_id_set:
            raise ValueError("document_handles 含有未授權或不存在的文件。")
        if document_id not in resolved_ids:
            resolved_ids.append(document_id)
    return tuple(resolved_ids)


def encode_document_handle(*, document_id: str) -> str:
    """將文件識別碼編碼為 agent 可見的安全 handle。

    參數：
    - `document_id`：原始文件識別碼。

    回傳：
    - `str`：不可直接看出原始識別碼的 handle。
    """

    encoded = urlsafe_b64encode(document_id.encode("utf-8")).decode("ascii").rstrip("=")
    return f"doc_{encoded}"


def decode_document_handle(*, handle: str) -> str:
    """將安全文件 handle 解回原始文件識別碼。

    參數：
    - `handle`：agent 提供的文件 handle。

    回傳：
    - `str`：解碼後的文件識別碼。
    """

    normalized = str(handle).strip()
    if not normalized.startswith("doc_"):
        raise ValueError("document_handles 只能使用後端核發的安全 handle。")
    payload = normalized.removeprefix("doc_")
    try:
        padding = "=" * (-len(payload) % 4)
        return urlsafe_b64decode(f"{payload}{padding}".encode("ascii")).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("document_handles 格式無效。") from exc


def build_planning_documents(
    *,
    authorized_ready_documents: list[Document],
    retrieval_trace,
    assembled_contexts: list[AssembledContext],
) -> list[RetrievalPlanningDocument]:
    """建立 agent follow-up 規劃使用的文件清單。

    參數：
    - `authorized_ready_documents`：目前 area 內已授權且 ready 的文件。
    - `retrieval_trace`：本輪 retrieval trace。
    - `assembled_contexts`：本輪 assembled contexts。

    回傳：
    - `list[RetrievalPlanningDocument]`：規劃文件清單。
    """

    mention_candidates = retrieval_trace.document_mention_candidates or []
    mentioned_document_ids = {
        str(candidate.get("document_id"))
        for candidate in mention_candidates
        if isinstance(candidate, dict) and isinstance(candidate.get("document_id"), str)
    }
    hit_document_ids = {str(context.document_id) for context in assembled_contexts}
    candidate_documents = [
        document
        for document in authorized_ready_documents
        if document.id in mentioned_document_ids or document.id in hit_document_ids
    ]
    if not candidate_documents:
        candidate_documents = authorized_ready_documents[:MAX_PLANNING_DOCUMENTS]

    return [
        RetrievalPlanningDocument(
            handle=encode_document_handle(document_id=str(document.id)),
            document_name=str(document.file_name),
            mentioned_by_query=document.id in mentioned_document_ids,
            hit_in_current_round=document.id in hit_document_ids,
            synopsis_available=bool((document.synopsis_text or "").strip()),
        )
        for document in candidate_documents[:MAX_PLANNING_DOCUMENTS]
    ]


def build_coverage_signals(
    *,
    retrieval_trace: dict[str, object],
    assembled_contexts: list[AssembledContext],
    document_name_by_id: dict[str, str],
) -> RetrievalCoverageSignals | None:
    """建立 compare / multi-document follow-up 需要的 coverage 訊號。

    參數：
    - `retrieval_trace`：本輪 retrieval trace。
    - `assembled_contexts`：本輪 assembled contexts。
    - `document_name_by_id`：文件名稱對照表。

    回傳：
    - `RetrievalCoverageSignals | None`：本輪 coverage 訊號。
    """

    query_type = str(retrieval_trace.get("query_type", ""))
    summary_scope = str(retrieval_trace.get("summary_scope") or "")
    if query_type != EvaluationQueryType.cross_document_compare.value and summary_scope != "multi_document":
        return None

    resolved_document_ids = [
        str(document_id)
        for document_id in (retrieval_trace.get("resolved_document_ids") or [])
        if isinstance(document_id, str)
    ]
    cited_document_ids = list(dict.fromkeys(str(context.document_id) for context in assembled_contexts))
    missing_document_names = [
        document_name_by_id[document_id]
        for document_id in resolved_document_ids
        if document_id in document_name_by_id and document_id not in cited_document_ids
    ]
    supports_compare = len(cited_document_ids) >= 2
    return RetrievalCoverageSignals(
        missing_document_names=missing_document_names,
        supports_compare=supports_compare,
        insufficient_evidence=bool(missing_document_names) or not supports_compare,
        missing_compare_axes=[] if supports_compare else ["共同點與差異都缺少雙邊直接證據"],
        new_evidence_found=bool(assembled_contexts),
    )


def build_next_best_followups(
    *,
    retrieval_trace: dict[str, object],
    assembled_contexts: list[AssembledContext],
    document_name_by_id: dict[str, str],
) -> list[str]:
    """建立 agent 下一步 follow-up 建議。

    參數：
    - `retrieval_trace`：本輪 retrieval trace。
    - `assembled_contexts`：本輪 assembled contexts。
    - `document_name_by_id`：文件名稱對照表。

    回傳：
    - `list[str]`：下一步 follow-up 建議。
    """

    coverage_signals = build_coverage_signals(
        retrieval_trace=retrieval_trace,
        assembled_contexts=assembled_contexts,
        document_name_by_id=document_name_by_id,
    )
    if coverage_signals is None:
        return []

    followups = [
        f"補查文件「{document_name}」的直接 compare 證據。"
        for document_name in coverage_signals.missing_document_names
    ]
    if not coverage_signals.supports_compare:
        followups.append("優先找出每份文件對同一 compare 面向的直接引文，再整理共同點與差異。")
    return followups


def build_evidence_cue_texts(
    *,
    assembled_contexts: list[AssembledContext],
    document_name_by_id: dict[str, str],
    build_context_label,
) -> list[RetrievalEvidenceCue]:
    """從 assembled contexts 建立短 evidence cues。

    參數：
    - `assembled_contexts`：本輪 assembled contexts。
    - `document_name_by_id`：文件名稱對照表。
    - `build_context_label`：建立 context label 的 callable。

    回傳：
    - `list[RetrievalEvidenceCue]`：短 cue 清單。
    """

    cues: list[RetrievalEvidenceCue] = []
    for index, context in enumerate(assembled_contexts[:3]):
        cues.append(
            RetrievalEvidenceCue(
                context_label=build_context_label(index),
                document_name=document_name_by_id.get(str(context.document_id), ""),
                cue_text=context.assembled_text.replace("\n", " ").strip()[:MAX_EVIDENCE_CUE_CHARS],
            )
        )
    return cues


def build_synopsis_hints(
    *,
    authorized_ready_documents: list[Document],
    synopsis_document_ids: tuple[str, ...] | None,
) -> list[RetrievalSynopsisHint]:
    """建立 agent 可見的 synopsis planning hints。

    參數：
    - `authorized_ready_documents`：目前 area 內已授權且 ready 的文件。
    - `synopsis_document_ids`：要求查看 synopsis 的文件識別碼。

    回傳：
    - `list[RetrievalSynopsisHint]`：synopsis hint 清單。
    """

    if not synopsis_document_ids:
        return []

    documents_by_id = {str(document.id): document for document in authorized_ready_documents}
    hints: list[RetrievalSynopsisHint] = []
    for document_id in synopsis_document_ids:
        document = documents_by_id.get(document_id)
        if document is None:
            continue
        synopsis_text = (document.synopsis_text or "").strip()
        if not synopsis_text:
            continue
        hints.append(
            RetrievalSynopsisHint(
                handle=encode_document_handle(document_id=document_id),
                document_name=str(document.file_name),
                synopsis_text=synopsis_text[:MAX_SYNOPSIS_HINT_CHARS],
            )
        )
    return hints
