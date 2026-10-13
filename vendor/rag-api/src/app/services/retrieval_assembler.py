"""將 retrieval candidates 組裝為 chat-ready context 與 citation metadata。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.db.models import ChunkStructureKind, ChunkType, DocumentChunk, DocumentChunkRegion
from app.services.retrieval_text import merge_chunk_contents
from app.services.retrieval_types import RetrievalCandidate, RetrievalResult, RetrievalTrace


@dataclass(slots=True)
class Citation:
    """單一 assembler citation 資料。"""

    # citation 所屬文件識別碼。
    document_id: str
    # citation 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # citation 對應的 child chunk 識別碼。
    chunk_id: str
    # citation 所屬段落標題。
    heading: str | None
    # citation 內容結構型別。
    structure_kind: ChunkStructureKind
    # citation 在 normalized text 的起始 offset。
    start_offset: int
    # citation 在 normalized text 的結束 offset。
    end_offset: int
    # citation 摘錄文字。
    excerpt: str
    # citation 關聯的 PDF locator。
    regions: list[DocumentChunkRegion] = field(default_factory=list)


@dataclass(slots=True)
class AssembledContext:
    """組裝後的單一 prompt-ready context。"""

    # context 所屬文件識別碼。
    document_id: str
    # context 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 合併進此 context 的 child chunk 識別碼。
    chunk_ids: list[str]
    # context 內容結構型別。
    structure_kind: ChunkStructureKind
    # context 所屬段落標題。
    heading: str | None
    # 組裝後可直接送入後續 chat 的文字。
    assembled_text: str
    # context 來源，可能為 vector、fts 或 hybrid。
    source: str
    # context 在 normalized text 的起始 offset。
    start_offset: int
    # context 在 normalized text 的結束 offset。
    end_offset: int
    # context 關聯的 PDF locator。
    regions: list[DocumentChunkRegion] = field(default_factory=list)


@dataclass(slots=True)
class AssemblerContextTrace:
    """單一組裝 context 的 trace metadata。"""

    # context 在回傳列表中的順序。
    context_index: int
    # context 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 保留在此 context 的 child chunk 識別碼。
    kept_chunk_ids: list[str]
    # 因 children 上限被捨棄的 child chunk 識別碼。
    dropped_chunk_ids: list[str]
    # 此 context 是否發生文字裁切。
    truncated: bool


@dataclass(slots=True)
class AssemblerTrace:
    """assembler 執行過程的 trace metadata。"""

    # 最多保留的 assembled contexts 數量。
    max_contexts: int
    # 每個 assembled context 的最大字元數。
    max_chars_per_context: int
    # 同一 parent 最多保留的 child 數量。
    max_children_per_parent: int
    # 被保留的 child chunk 識別碼。
    kept_chunk_ids: list[str]
    # 被捨棄的 child chunk 識別碼。
    dropped_chunk_ids: list[str]
    # 各 assembled context 的 trace。
    contexts: list[AssemblerContextTrace]


@dataclass(slots=True)
class AssembledRetrievalTrace:
    """整合 retrieval 與 assembler 的 trace metadata。"""

    # 原始 retrieval trace。
    retrieval: RetrievalTrace
    # assembler trace。
    assembler: AssemblerTrace


@dataclass(slots=True)
class AssembledRetrievalResult:
    """assembler 的完整輸出結果。"""

    # 組裝後的 contexts。
    assembled_contexts: list[AssembledContext]
    # citation-ready metadata。
    citations: list[Citation]
    # retrieval + assembler trace。
    trace: AssembledRetrievalTrace


@dataclass(slots=True)
class _CandidateRecord:
    """assembler 使用的候選 chunk 補查結果。"""

    # retrieval candidate 的原始順序。
    order: int
    # retrieval candidate。
    candidate: RetrievalCandidate
    # 資料庫補查出的 child chunk。
    chunk: DocumentChunk


def assemble_retrieval_result(
    *,
    session: Session,
    settings: AppSettings,
    retrieval_result: RetrievalResult,
) -> AssembledRetrievalResult:
    """將 rerank 後的 retrieval result 組裝為 chat-ready contexts。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `retrieval_result`：已完成 SQL gate、recall、RRF 與 rerank 的 retrieval 結果。

    回傳：
    - `AssembledRetrievalResult`：組裝後的 contexts、citations 與 trace。
    """

    if not retrieval_result.candidates:
        return AssembledRetrievalResult(
            assembled_contexts=[],
            citations=[],
            trace=AssembledRetrievalTrace(
                retrieval=retrieval_result.trace,
                assembler=AssemblerTrace(
                    max_contexts=settings.assembler_max_contexts,
                    max_chars_per_context=settings.assembler_max_chars_per_context,
                    max_children_per_parent=settings.assembler_max_children_per_parent,
                    kept_chunk_ids=[],
                    dropped_chunk_ids=[],
                    contexts=[],
                ),
            ),
        )

    candidate_ids = [candidate.chunk_id for candidate in retrieval_result.candidates]
    chunk_by_id = _load_child_chunks(session=session, chunk_ids=candidate_ids)
    parent_chunk_by_id = _load_parent_chunks(
        session=session,
        parent_chunk_ids=[candidate.parent_chunk_id for candidate in retrieval_result.candidates if candidate.parent_chunk_id],
    )
    children_by_parent_id = _load_children_by_parent_chunks(
        session=session,
        parent_chunk_ids=[candidate.parent_chunk_id for candidate in retrieval_result.candidates if candidate.parent_chunk_id],
    )
    regions_by_chunk_id = _load_regions_by_chunk_ids(session=session, chunk_ids=candidate_ids)

    grouped_records: OrderedDict[tuple[str, str | None], list[_CandidateRecord]] = OrderedDict()
    for order, candidate in enumerate(retrieval_result.candidates):
        chunk = chunk_by_id.get(candidate.chunk_id)
        if chunk is None:
            raise ValueError(f"找不到 retrieval candidate 對應的 child chunk：{candidate.chunk_id}")
        group_key = (candidate.document_id, candidate.parent_chunk_id)
        grouped_records.setdefault(group_key, []).append(_CandidateRecord(order=order, candidate=candidate, chunk=chunk))

    assembled_contexts: list[AssembledContext] = []
    citations: list[Citation] = []
    kept_chunk_ids: list[str] = []
    dropped_chunk_ids: list[str] = []
    context_traces: list[AssemblerContextTrace] = []

    for records in grouped_records.values():
        if len(assembled_contexts) >= settings.assembler_max_contexts:
            dropped_chunk_ids.extend(record.candidate.chunk_id for record in records)
            continue

        kept_records, dropped_records = _select_anchor_records(
            records=records,
            query=_extract_retrieval_query(trace=retrieval_result.trace),
            max_children_per_parent=settings.assembler_max_children_per_parent,
        )

        if not kept_records:
            dropped_chunk_ids.extend(record.candidate.chunk_id for record in records)
            continue

        parent_chunk = parent_chunk_by_id.get(kept_records[0].candidate.parent_chunk_id or "")
        included_chunks, assembled_text, truncated = _materialize_context(
            kept_records=kept_records,
            dropped_records=dropped_records,
            parent_chunk=parent_chunk,
            parent_children=children_by_parent_id.get(kept_records[0].candidate.parent_chunk_id or "", []),
            max_chars=settings.assembler_max_chars_per_context,
        )
        context_source = _resolve_context_source(records=kept_records)
        heading = kept_records[0].candidate.heading or (parent_chunk.heading if parent_chunk is not None else None)
        start_offset = (
            parent_chunk.start_offset
            if parent_chunk is not None and _should_use_full_parent(parent_chunk=parent_chunk, max_chars=settings.assembler_max_chars_per_context)
            else min(chunk.start_offset for chunk in included_chunks)
        )
        end_offset = (
            parent_chunk.end_offset
            if parent_chunk is not None and _should_use_full_parent(parent_chunk=parent_chunk, max_chars=settings.assembler_max_chars_per_context)
            else max(chunk.end_offset for chunk in included_chunks)
        )
        chunk_ids = [str(chunk.id) for chunk in included_chunks]
        structure_kind = parent_chunk.structure_kind if parent_chunk is not None else kept_records[0].candidate.structure_kind

        assembled_contexts.append(
            AssembledContext(
                document_id=str(kept_records[0].candidate.document_id),
                parent_chunk_id=(
                    str(kept_records[0].candidate.parent_chunk_id)
                    if kept_records[0].candidate.parent_chunk_id is not None
                    else None
                ),
                chunk_ids=chunk_ids,
                structure_kind=structure_kind,
                heading=heading,
                assembled_text=assembled_text,
                source=context_source,
                start_offset=start_offset,
                end_offset=end_offset,
                regions=[region for chunk in included_chunks for region in regions_by_chunk_id.get(str(chunk.id), [])],
            )
        )
        citations.extend(
            Citation(
                document_id=str(record.candidate.document_id),
                parent_chunk_id=str(record.candidate.parent_chunk_id) if record.candidate.parent_chunk_id is not None else None,
                chunk_id=str(record.candidate.chunk_id),
                heading=record.candidate.heading or heading,
                structure_kind=record.candidate.structure_kind,
                start_offset=record.candidate.start_offset,
                end_offset=record.candidate.end_offset,
                excerpt=record.candidate.content,
                regions=regions_by_chunk_id.get(str(record.candidate.chunk_id), []),
            )
            for record in kept_records
        )
        kept_chunk_ids.extend(chunk_ids)
        dropped_chunk_ids.extend(record.candidate.chunk_id for record in dropped_records)
        context_traces.append(
            AssemblerContextTrace(
                context_index=len(assembled_contexts) - 1,
                parent_chunk_id=(
                    str(kept_records[0].candidate.parent_chunk_id)
                    if kept_records[0].candidate.parent_chunk_id is not None
                    else None
                ),
                kept_chunk_ids=chunk_ids,
                dropped_chunk_ids=[record.candidate.chunk_id for record in dropped_records],
                truncated=truncated,
            )
        )

    return AssembledRetrievalResult(
        assembled_contexts=assembled_contexts,
        citations=citations,
        trace=AssembledRetrievalTrace(
            retrieval=retrieval_result.trace,
            assembler=AssemblerTrace(
                max_contexts=settings.assembler_max_contexts,
                max_chars_per_context=settings.assembler_max_chars_per_context,
                max_children_per_parent=settings.assembler_max_children_per_parent,
                kept_chunk_ids=kept_chunk_ids,
                dropped_chunk_ids=dropped_chunk_ids,
                contexts=context_traces,
            ),
        ),
    )


def _load_child_chunks(*, session: Session, chunk_ids: list[str]) -> dict[str, DocumentChunk]:
    """依 chunk ids 補查 child chunk。

    參數：
    - `session`：目前資料庫 session。
    - `chunk_ids`：要補查的 child chunk ids。

    回傳：
    - `dict[str, DocumentChunk]`：以 chunk id 為鍵的 child chunk 對照表。
    """

    if not chunk_ids:
        return {}

    chunks = session.scalars(
        select(DocumentChunk).where(
            DocumentChunk.id.in_(chunk_ids),
            DocumentChunk.chunk_type == ChunkType.child,
        )
    ).all()
    return {str(chunk.id): chunk for chunk in chunks}


def _load_regions_by_chunk_ids(*, session: Session, chunk_ids: list[str]) -> dict[str, list[DocumentChunkRegion]]:
    """依 chunk ids 補查 PDF locator regions。"""

    if not chunk_ids:
        return {}

    regions = session.scalars(
        select(DocumentChunkRegion)
        .where(DocumentChunkRegion.chunk_id.in_(chunk_ids))
        .order_by(DocumentChunkRegion.chunk_id.asc(), DocumentChunkRegion.region_order.asc())
    ).all()
    regions_by_chunk_id: dict[str, list[DocumentChunkRegion]] = {}
    for region in regions:
        regions_by_chunk_id.setdefault(str(region.chunk_id), []).append(region)
    return regions_by_chunk_id


def _load_parent_chunks(*, session: Session, parent_chunk_ids: list[str]) -> dict[str, DocumentChunk]:
    """依 parent chunk ids 補查 parent chunk。

    參數：
    - `session`：目前資料庫 session。
    - `parent_chunk_ids`：要補查的 parent chunk ids。

    回傳：
    - `dict[str, DocumentChunk]`：以 parent chunk id 為鍵的對照表。
    """

    if not parent_chunk_ids:
        return {}

    parent_chunks = session.scalars(
        select(DocumentChunk).where(
            DocumentChunk.id.in_(parent_chunk_ids),
            DocumentChunk.chunk_type == ChunkType.parent,
        )
    ).all()
    return {str(chunk.id): chunk for chunk in parent_chunks}


def _load_children_by_parent_chunks(*, session: Session, parent_chunk_ids: list[str]) -> dict[str, list[DocumentChunk]]:
    """補查指定 parent 下的所有 child chunks。

    參數：
    - `session`：目前資料庫 session。
    - `parent_chunk_ids`：要補查的 parent chunk ids。

    回傳：
    - `dict[str, list[DocumentChunk]]`：以 parent chunk id 為鍵、依 child 順序排序的 children。
    """

    if not parent_chunk_ids:
        return {}

    children = session.scalars(
        select(DocumentChunk).where(
            DocumentChunk.parent_chunk_id.in_(parent_chunk_ids),
            DocumentChunk.chunk_type == ChunkType.child,
        )
        .order_by(DocumentChunk.parent_chunk_id.asc(), DocumentChunk.child_index.asc(), DocumentChunk.position.asc())
    ).all()
    grouped: dict[str, list[DocumentChunk]] = {}
    for child in children:
        grouped.setdefault(str(child.parent_chunk_id), []).append(child)
    return grouped


def _materialize_context(
    *,
    kept_records: list[_CandidateRecord],
    dropped_records: list[_CandidateRecord],
    parent_chunk: DocumentChunk | None,
    parent_children: list[DocumentChunk],
    max_chars: int,
) -> tuple[list[DocumentChunk], str, bool]:
    """依精準度優先策略將命中點展開為 context。

    參數：
    - `kept_records`：同一 parent 內、保留用於 materialization 的命中 child。
    - `dropped_records`：同一 parent 內因 guardrail 被捨棄的命中 child。
    - `parent_chunk`：此 context 對應的 parent chunk。
    - `parent_children`：此 parent 下的完整 child 列表。
    - `max_chars`：單一 context 可用的最大字元數。

    回傳：
    - `tuple[list[DocumentChunk], str, bool]`：納入的 child、assembled text 與是否發生裁切。
    """

    if parent_chunk is not None and _should_use_full_parent(parent_chunk=parent_chunk, max_chars=max_chars):
        included_chunks = parent_children or [record.chunk for record in kept_records]
        normalized_text = parent_chunk.content.strip()
        return included_chunks, normalized_text[:max_chars], len(normalized_text) > max_chars

    included_chunks = _expand_context_children(
        kept_records=kept_records,
        dropped_records=dropped_records,
        parent_children=parent_children,
        max_chars=max_chars,
    )
    assembled_text = _merge_children_contents(children=included_chunks)
    normalized_text = assembled_text.strip()
    if len(normalized_text) <= max_chars:
        return included_chunks, normalized_text, False
    return included_chunks, normalized_text[:max_chars], True


def _select_anchor_records(
    *,
    records: list[_CandidateRecord],
    query: str,
    max_children_per_parent: int,
) -> tuple[list[_CandidateRecord], list[_CandidateRecord]]:
    """依 query-aware anchor score 與既有 rank 訊號挑選 parent 內保留 child。

    參數：
    - `records`：同一 parent 下的候選 child records。
    - `query`：本次 retrieval query。
    - `max_children_per_parent`：同一 parent 最多保留幾個 hit children。

    回傳：
    - `tuple[list[_CandidateRecord], list[_CandidateRecord]]`：保留與捨棄的 child records。
    """

    if max_children_per_parent <= 0:
        return [], list(records)

    ranked_records = sorted(
        records,
        key=lambda record: (
            -_compute_anchor_score(query=query, record=record),
            record.candidate.rerank_rank if record.candidate.rerank_rank is not None else 1_000_000,
            record.candidate.rrf_rank if record.candidate.rrf_rank is not None else 1_000_000,
            record.candidate.vector_rank if record.candidate.vector_rank is not None else 1_000_000,
            record.candidate.fts_rank if record.candidate.fts_rank is not None else 1_000_000,
            record.chunk.child_index if record.chunk.child_index is not None else 1_000_000,
            record.order,
        ),
    )
    return ranked_records[:max_children_per_parent], ranked_records[max_children_per_parent:]


def _extract_retrieval_query(*, trace: RetrievalTrace | dict[str, object]) -> str:
    """從 retrieval trace 讀出 query，兼容 dataclass 與 dict 形式。

    參數：
    - `trace`：retrieval trace；可能是 dataclass 或可序列化 dict。

    回傳：
    - `str`：本次 retrieval query；缺少時回空字串。
    """

    if isinstance(trace, dict):
        query = trace.get("query")
        return query if isinstance(query, str) else ""
    return trace.query


def _compute_anchor_score(*, query: str, record: _CandidateRecord) -> float:
    """計算單一 child record 在 parent 內作為 assembler anchor 的分數。

    參數：
    - `query`：本次 retrieval query。
    - `record`：待評分的 child record。

    回傳：
    - `float`：anchor 分數；越高代表越應優先保留。
    """

    normalized_query = query.strip().casefold()
    normalized_heading = (record.chunk.heading or "").strip().casefold()
    normalized_content = (record.chunk.content or "").strip().casefold()
    query_tokens = _tokenize_anchor_query(query=query)

    score = 0.0
    if normalized_query:
        if normalized_query in normalized_heading:
            score += 10.0
        if normalized_query in normalized_content:
            score += 8.0

    if query_tokens:
        heading_token_hits = sum(1 for token in query_tokens if token in normalized_heading)
        content_token_hits = sum(1 for token in query_tokens if token in normalized_content)
        score += min(heading_token_hits, 6) * 2.0
        score += min(content_token_hits, 12) * 1.0

    return score


def _tokenize_anchor_query(*, query: str) -> list[str]:
    """將 query 切成供 assembler anchor scoring 使用的 tokens。

    參數：
    - `query`：本次 retrieval query。

    回傳：
    - `list[str]`：去重後的 query tokens。
    """

    normalized_query = query.casefold()
    raw_tokens = re.split(r"[\s,.;:!?()\[\]{}\"'`/\\|]+", normalized_query)
    tokens: list[str] = []
    for token in raw_tokens:
        stripped = token.strip()
        if len(stripped) < 2:
            continue
        if stripped not in tokens:
            tokens.append(stripped)
    return tokens


def _should_use_full_parent(*, parent_chunk: DocumentChunk, max_chars: int) -> bool:
    """判斷此 parent 是否可直接作為完整 context。

    參數：
    - `parent_chunk`：候選 parent chunk。
    - `max_chars`：單一 context 的最大字元數。

    回傳：
    - `bool`：若 parent 長度未超過 context budget 則回傳真值。
    """

    return parent_chunk.char_count <= max_chars


def _expand_context_children(
    *,
    kept_records: list[_CandidateRecord],
    dropped_records: list[_CandidateRecord],
    parent_children: list[DocumentChunk],
    max_chars: int,
) -> list[DocumentChunk]:
    """以命中 child 為中心做 budget-aware 的 sibling expansion。

    參數：
    - `kept_records`：保留的命中 child。
    - `dropped_records`：被 guardrail 捨棄的命中 child。
    - `parent_children`：此 parent 下所有 child chunks。
    - `max_chars`：單一 context 可用的最大字元數。

    回傳：
    - `list[DocumentChunk]`：排序後納入 context 的 child 列表。
    """

    if not parent_children:
        return [record.chunk for record in kept_records]

    children_by_id = {str(child.id): child for child in parent_children}
    blocked_ids = {str(record.chunk.id) for record in dropped_records}
    required_ids = {str(record.chunk.id) for record in kept_records}
    ordered_children = list(parent_children)
    index_by_id = {str(child.id): index for index, child in enumerate(ordered_children)}
    required_indices = {index_by_id[chunk_id] for chunk_id in required_ids if chunk_id in index_by_id}

    if not required_indices:
        return [record.chunk for record in kept_records]

    if any(children_by_id[chunk_id].structure_kind == ChunkStructureKind.table for chunk_id in required_ids):
        for chunk_id in list(required_ids):
            child = children_by_id[chunk_id]
            if child.structure_kind != ChunkStructureKind.table:
                continue
            table_index = index_by_id[chunk_id]
            for candidate_index in _contiguous_table_indices(children=ordered_children, start_index=table_index):
                candidate = ordered_children[candidate_index]
                if str(candidate.id) not in blocked_ids:
                    required_ids.add(str(candidate.id))
                    required_indices.add(candidate_index)

    expanded = _fit_children_within_budget(
        children=ordered_children,
        included_ids=required_ids,
        blocked_ids=blocked_ids,
        max_chars=max_chars,
    )
    return expanded or [record.chunk for record in kept_records]


def _contiguous_table_indices(*, children: list[DocumentChunk], start_index: int) -> list[int]:
    """找出與命中 table 相鄰的完整 table row-group 範圍。

    參數：
    - `children`：同一 parent 下的 child 列表。
    - `start_index`：命中 table child 的索引。

    回傳：
    - `list[int]`：需一併納入的 table child 索引。
    """

    indices = [start_index]
    index = start_index - 1
    while index >= 0 and children[index].structure_kind == ChunkStructureKind.table:
        indices.insert(0, index)
        index -= 1
    index = start_index + 1
    while index < len(children) and children[index].structure_kind == ChunkStructureKind.table:
        indices.append(index)
        index += 1
    return indices


def _fit_children_within_budget(
    *,
    children: list[DocumentChunk],
    included_ids: set[str],
    blocked_ids: set[str],
    max_chars: int,
) -> list[DocumentChunk]:
    """在不超過 budget 的前提下，自命中點向外擴張 child。

    參數：
    - `children`：同一 parent 下依順序排列的 child 列表。
    - `included_ids`：目前已必須納入的 child ids。
    - `blocked_ids`：不可再納入的 child ids。
    - `max_chars`：單一 context 的最大字元數。

    回傳：
    - `list[DocumentChunk]`：完成 budget-aware expansion 的 child 列表。
    """

    included = {str(chunk.id) for chunk in children if str(chunk.id) in included_ids}
    if not included:
        return []

    best = [chunk for chunk in children if str(chunk.id) in included]
    if len(_merge_children_contents(children=best).strip()) > max_chars:
        return best

    left = min(index for index, chunk in enumerate(children) if str(chunk.id) in included) - 1
    right = max(index for index, chunk in enumerate(children) if str(chunk.id) in included) + 1

    while left >= 0 or right < len(children):
        candidates: list[tuple[str, int]] = []
        if left >= 0 and str(children[left].id) not in blocked_ids:
            candidates.append(("left", left))
        if right < len(children) and str(children[right].id) not in blocked_ids:
            candidates.append(("right", right))
        if not candidates:
            break

        chosen_direction = None
        for direction, index in sorted(candidates, key=lambda item: 0 if children[item[1]].structure_kind == ChunkStructureKind.text else 1):
            trial_ids = included | {str(children[index].id)}
            trial_children = [chunk for chunk in children if str(chunk.id) in trial_ids]
            if len(_merge_children_contents(children=trial_children).strip()) <= max_chars:
                included = trial_ids
                best = trial_children
                chosen_direction = direction
                break
        if chosen_direction is None:
            break
        if chosen_direction == "left":
            left -= 1
        else:
            right += 1

    return best


def _merge_children_contents(*, children: list[DocumentChunk]) -> str:
    """將 child chunks 依連續結構分組後組成 context 文字。

    參數：
    - `children`：依 child 順序排列的 children。

    回傳：
    - `str`：可送入 LLM 的 assembled text。
    """

    if not children:
        return ""

    merged_parts: list[str] = []
    run_kind = children[0].structure_kind
    run_contents: list[str] = []
    for child in children:
        if child.structure_kind != run_kind and run_contents:
            merged_parts.append(merge_chunk_contents(structure_kind=run_kind, contents=run_contents))
            run_kind = child.structure_kind
            run_contents = [child.content]
            continue
        run_contents.append(child.content)

    if run_contents:
        merged_parts.append(merge_chunk_contents(structure_kind=run_kind, contents=run_contents))

    return "\n\n".join(part.strip() for part in merged_parts if part and part.strip()).strip()


def _resolve_context_source(*, records: list[_CandidateRecord]) -> str:
    """決定 assembled context 的來源欄位。

    參數：
    - `records`：同一 context 的候選 child chunks。

    回傳：
    - `str`：`vector`、`fts` 或 `hybrid`。
    """

    sources = {record.candidate.source for record in records}
    if "hybrid" in sources or len(sources) > 1:
        return "hybrid"
    return next(iter(sources), "fts")
