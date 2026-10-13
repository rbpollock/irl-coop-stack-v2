"""Retrieval ranking policy、parent-level rerank 與 candidate 轉換。"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass

from app.core.settings import AppSettings
from app.db.models import ChunkStructureKind
from app.services.reranking import RerankInputDocument, build_rerank_provider
from app.services.retrieval_query import extract_query_tokens
from app.services.retrieval_text import build_rerank_document_text, merge_chunk_contents
from app.services.retrieval_types import RankedChunkMatch, RetrievalCandidate


# rerank provider 失敗時使用的模組 logger。
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _RerankParentGroup:
    """rerank 前依 parent 聚合的候選群組。"""

    # rerank provider 使用的候選識別碼。
    candidate_id: str
    # 群組 heading。
    heading: str | None
    # 群組內容。
    content: str
    # 命中的 child chunk 內容。
    matched_child_contents: list[str]
    # 群組內所有 child matches。
    matches: list[RankedChunkMatch]
    # 原始排序。
    order: int


def apply_ranking_policy(
    *,
    matches: list[RankedChunkMatch],
    query: str,
    settings: AppSettings,
) -> list[RankedChunkMatch]:
    """套用最小 ranking policy，降低目錄噪音並保留商品名命中優勢。

    參數：
    - `matches`：已完成 Python RRF 的候選。
    - `query`：使用者查詢文字。
    - `settings`：API 執行期設定。

    回傳：
    - `list[RankedChunkMatch]`：已套用最小 ranking rules 的候選排序。
    """

    del settings
    query_tokens = extract_query_tokens(query=query)
    scored_matches = [
        (
            _ranking_policy_score(
                match=match,
                query=query,
                query_tokens=query_tokens,
            ),
            index,
            match,
        )
        for index, match in enumerate(matches)
    ]
    scored_matches.sort(
        key=lambda item: (
            -item[0],
            item[2].rrf_rank or 1_000_000,
            _best_rank(item[2]),
            item[1],
        )
    )
    return [item[2] for item in scored_matches]


def apply_rerank(*, matches: list[RankedChunkMatch], query: str, settings: AppSettings) -> list[RankedChunkMatch]:
    """將 RRF 後的 candidates 再送入 rerank，並保留 fail-open fallback。

    參數：
    - `matches`：已完成 RRF / ranking policy 的候選。
    - `query`：使用者查詢文字。
    - `settings`：API 執行期設定。

    回傳：
    - `list[RankedChunkMatch]`：rerank 後候選；provider 失敗時回原順序。
    """

    rerank_groups = _group_matches_for_parent_rerank(matches=matches)
    rerank_limit = min(settings.rerank_top_n, len(rerank_groups))
    if rerank_limit <= 0:
        return matches

    rerank_inputs = [
        RerankInputDocument(
            candidate_id=group.candidate_id,
            text=build_rerank_document_text(
                heading=group.heading,
                content=group.content,
                max_chars=settings.rerank_max_chars_per_doc,
                matched_child_contents=group.matched_child_contents,
            ),
        )
        for group in rerank_groups[:rerank_limit]
    ]

    try:
        rerank_provider = build_rerank_provider(settings)
        rerank_scores = rerank_provider.rerank(query=query, documents=rerank_inputs, top_n=rerank_limit)
    except Exception:
        LOGGER.warning(
            "Retrieval rerank provider failed; falling back to RRF order.",
            extra={
                "query": query,
                "rerank_provider": settings.rerank_provider,
                "rerank_model": settings.rerank_model,
                "candidate_count": len(rerank_inputs),
            },
            exc_info=True,
        )
        for group in rerank_groups[:rerank_limit]:
            for match in group.matches:
                match.rerank_applied = False
                match.rerank_rank = None
                match.rerank_score = None
                match.rerank_fallback_reason = "provider_error"
        return matches

    rerank_score_by_group_id = {item.candidate_id: item for item in rerank_scores}
    top_groups = rerank_groups[:rerank_limit]
    for group in top_groups:
        score = rerank_score_by_group_id.get(group.candidate_id)
        for match in group.matches:
            if score is None:
                match.rerank_applied = False
                match.rerank_score = None
                match.rerank_rank = None
                match.rerank_fallback_reason = "missing_score"
                continue
            match.rerank_applied = True
            match.rerank_score = score.score
            match.rerank_fallback_reason = None

    reranked_top_groups = sorted(
        top_groups,
        key=lambda item: (
            0 if any(match.rerank_applied for match in item.matches) else 1,
            -(
                max(match.rerank_score for match in item.matches if match.rerank_score is not None)
                if any(match.rerank_score is not None for match in item.matches)
                else float("-inf")
            ),
            item.order,
        ),
    )
    for index, group in enumerate(reranked_top_groups, start=1):
        for match in group.matches:
            if match.rerank_applied:
                match.rerank_rank = index

    ordered_matches: list[RankedChunkMatch] = []
    for group in reranked_top_groups + rerank_groups[rerank_limit:]:
        ordered_matches.extend(group.matches)
    return ordered_matches


def build_retrieval_candidate(match: RankedChunkMatch) -> RetrievalCandidate:
    """將中間結構轉為對外使用的 retrieval candidate。

    參數：
    - `match`：已完成 recall / ranking / rerank 的候選。

    回傳：
    - `RetrievalCandidate`：runtime 後續階段使用的候選。
    """

    return RetrievalCandidate(
        document_id=str(match.chunk.document_id),
        chunk_id=str(match.chunk.id),
        parent_chunk_id=str(match.chunk.parent_chunk_id) if match.chunk.parent_chunk_id is not None else None,
        structure_kind=match.chunk.structure_kind,
        heading=match.chunk.heading,
        content=match.chunk.content,
        start_offset=match.chunk.start_offset,
        end_offset=match.chunk.end_offset,
        source=resolve_candidate_source(match),
        vector_rank=match.vector_rank,
        fts_rank=match.fts_rank,
        rrf_rank=match.rrf_rank or 0,
        rrf_score=match.rrf_score,
        rerank_rank=match.rerank_rank,
        rerank_score=match.rerank_score,
        rerank_applied=match.rerank_applied,
        rerank_fallback_reason=match.rerank_fallback_reason,
    )


def resolve_candidate_source(match: RankedChunkMatch) -> str:
    """根據 rank 來源決定 candidate source 欄位。

    參數：
    - `match`：候選 match。

    回傳：
    - `str`：`hybrid`、`vector` 或 `fts`。
    """

    if match.vector_rank is not None and match.fts_rank is not None:
        return "hybrid"
    if match.vector_rank is not None:
        return "vector"
    return "fts"


def _ranking_policy_score(
    *,
    match: RankedChunkMatch,
    query: str,
    query_tokens: list[str],
) -> float:
    """計算最小 ranking policy 分數。"""

    score = match.rrf_score
    heading = (match.chunk.heading or "").strip().lower()
    content = (match.chunk.content or "").strip().lower()
    normalized_query = query.strip().lower()

    if normalized_query and normalized_query in content:
        score += 0.08
    if normalized_query and normalized_query in heading:
        score += 0.12

    if query_tokens:
        heading_token_hits = sum(1 for token in query_tokens if token and token in heading)
        content_token_hits = sum(1 for token in query_tokens if token and token in content)
        score += min(heading_token_hits, 4) * 0.025
        score += min(content_token_hits, 6) * 0.008

    if _is_table_of_contents_chunk(match):
        score -= 0.12
        if normalized_query and normalized_query in heading:
            score += 0.03

    return score


def _is_table_of_contents_chunk(match: RankedChunkMatch) -> bool:
    """判斷候選是否屬於帶有 leader dots 的目錄類噪音。"""

    content = (match.chunk.content or "").strip().lower()
    if "................................................................" in content:
        return True
    return False


def _group_matches_for_parent_rerank(*, matches: list[RankedChunkMatch]) -> list[_RerankParentGroup]:
    """依 parent 邊界將 child candidates 聚合為 rerank 群組。

    參數：
    - `matches`：已完成 RRF 的 child-level 候選。

    回傳：
    - `list[_RerankParentGroup]`：供 parent-level rerank 使用的群組列表。
    """

    grouped_matches: OrderedDict[tuple[str, str, ChunkStructureKind], list[RankedChunkMatch]] = OrderedDict()
    for match in matches:
        group_parent_id = match.chunk.parent_chunk_id or match.chunk.id
        group_key = (str(match.chunk.document_id), str(group_parent_id), match.chunk.structure_kind)
        grouped_matches.setdefault(group_key, []).append(match)

    rerank_groups: list[_RerankParentGroup] = []
    for order, records in enumerate(grouped_matches.values()):
        sorted_records = sorted(
            records,
            key=lambda item: (
                item.chunk.child_index if item.chunk.child_index is not None else -1,
                item.chunk.position,
                item.chunk.id,
            ),
        )
        heading = next((match.chunk.heading for match in sorted_records if match.chunk.heading), None)
        content = merge_chunk_contents(
            structure_kind=sorted_records[0].chunk.structure_kind,
            contents=[match.chunk.content for match in sorted_records],
        )
        rerank_groups.append(
            _RerankParentGroup(
                candidate_id=_build_parent_rerank_candidate_id(matches=sorted_records),
                heading=heading,
                content=content,
                matched_child_contents=[match.chunk.content for match in sorted_records],
                matches=sorted_records,
                order=order,
            )
        )
    return rerank_groups


def _build_parent_rerank_candidate_id(*, matches: list[RankedChunkMatch]) -> str:
    """建立 parent-level rerank 群組識別碼。"""

    first_match = matches[0]
    parent_or_chunk_id = first_match.chunk.parent_chunk_id or first_match.chunk.id
    return (
        f"{first_match.chunk.document_id}:"
        f"{parent_or_chunk_id}:"
        f"{first_match.chunk.structure_kind.value}"
    )


def _best_rank(match: RankedChunkMatch) -> int:
    """回傳候選可用 rank 中最好的那個，用於 tie-break。"""

    available_ranks = [
        rank
        for rank in (
            getattr(match, "vector_rank", None),
            getattr(match, "fts_rank", None),
            getattr(match, "rrf_rank", None),
        )
        if rank is not None
    ]
    return min(available_ranks) if available_ranks else 1_000_000
