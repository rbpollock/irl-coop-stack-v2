"""Retrieval evaluation 專用 stage runner adapter。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import Document, DocumentChunk, RetrievalEvalItem, RetrievalEvalItemSpan
from app.evaluation.retrieval.mapping import CandidateWindow, GoldSpan, first_hit_rank, match_gold_relevance, match_gold_relevance_for_windows
from app.schemas.evaluation import (
    EvaluationCandidateStageResponse,
    EvaluationQueryRoutingDetail,
    EvaluationSelectionDetail,
    EvaluationStageCandidate,
)
from app.services.retrieval_assembler import assemble_retrieval_result
from app.services.retrieval_recall import apply_python_rrf, recall_ranked_candidates
from app.services.retrieval_rerank import apply_ranking_policy, apply_rerank as apply_rerank_stage, build_retrieval_candidate
from app.services.retrieval_routing import QueryRoutingDecision, build_query_routing_decision
from app.services.retrieval_selection import RetrievalSelectionResult, apply_scope_aware_selection
from app.services.retrieval_types import RetrievalResult, RetrievalTrace


@dataclass(slots=True)
class ItemStageEvaluationResult:
    """單題 retrieval evaluation 的共用 stage 計算結果。"""

    item: RetrievalEvalItem
    gold_spans: list[GoldSpan]
    query_routing: EvaluationQueryRoutingDetail
    selection: EvaluationSelectionDetail
    recall_stage: EvaluationCandidateStageResponse
    rerank_stage: EvaluationCandidateStageResponse
    assembled_stage: EvaluationCandidateStageResponse

def evaluate_item_stage_outputs(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    item: RetrievalEvalItem,
    spans: list[RetrievalEvalItemSpan],
    top_k: int,
    apply_rerank: bool = True,
    allowed_document_ids_override: tuple[str, ...] | None = None,
) -> ItemStageEvaluationResult:
    """建立單題共用的 recall/rerank/assembled stage 結果。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `area_id`：目標 area。
    - `item`：目前題目。
    - `spans`：該題 gold spans。
    - `top_k`：stage 回傳上限。
    - `apply_rerank`：是否套用 rerank stage。
    - `allowed_document_ids_override`：benchmark-only 文件白名單；用於具備原始文件上下文的資料集。

    回傳：
    - `ItemStageEvaluationResult`：可供 preview 與 benchmark 共用的 stage 結果。
    """

    routing_decision = build_query_routing_decision(
        settings=settings,
        query=item.query_text,
        explicit_query_type=item.query_type,
        session=session,
        principal=principal,
        area_id=area_id,
    )
    effective_settings = routing_decision.effective_settings
    retrieval_query = item.query_text
    scoped_document_ids = allowed_document_ids_override or routing_decision.resolved_document_ids or None

    recall_matches = apply_ranking_policy(
        matches=apply_python_rrf(
            matches=recall_ranked_candidates(
                session=session,
                settings=effective_settings,
                area_id=area_id,
                query=retrieval_query,
                allowed_document_ids=scoped_document_ids,
                allowed_parent_ids=None,
            ),
            settings=effective_settings,
        ),
        query=item.query_text,
        settings=effective_settings,
    )
    rerank_matches = (
        apply_rerank_stage(matches=recall_matches, query=item.query_text, settings=effective_settings)
        if apply_rerank
        else recall_matches
    )
    reranked_candidates = [build_retrieval_candidate(match) for match in rerank_matches]
    selection_result = apply_scope_aware_selection(
        candidates=reranked_candidates,
        selected_profile=routing_decision.selected_profile,
        resolved_document_ids=scoped_document_ids or (),
        max_contexts=effective_settings.assembler_max_contexts,
    )
    retrieval_result = RetrievalResult(
        candidates=selection_result.candidates,
        trace=_build_empty_trace(
            query=item.query_text,
            settings=effective_settings,
            total_candidates=len(rerank_matches),
            routing_decision=routing_decision,
            selection_result=selection_result,
        ),
    )
    assembled_result = assemble_retrieval_result(session=session, settings=effective_settings, retrieval_result=retrieval_result)
    gold_spans = [
        GoldSpan(
            document_id=span.document_id,
            start_offset=span.start_offset,
            end_offset=span.end_offset,
            relevance_grade=span.relevance_grade,
            is_retrieval_miss=span.is_retrieval_miss,
        )
        for span in spans
    ]
    document_names = _load_document_names(session=session, area_id=area_id)
    return ItemStageEvaluationResult(
        item=item,
        gold_spans=gold_spans,
        query_routing=_build_query_routing_detail(routing_decision=routing_decision),
        selection=_build_selection_detail(selection_result=selection_result),
        recall_stage=_build_recall_stage(
            matches=recall_matches,
            gold_spans=gold_spans,
            document_names=document_names,
            top_k=top_k,
        ),
        rerank_stage=_build_rerank_stage(
            candidates=retrieval_result.candidates,
            gold_spans=gold_spans,
            document_names=document_names,
            top_k=top_k,
            apply_rerank=apply_rerank,
        ),
        assembled_stage=_build_assembled_stage(
            session=session,
            contexts=assembled_result.assembled_contexts,
            gold_spans=gold_spans,
            document_names=document_names,
            top_k=top_k,
        ),
    )


def _build_empty_trace(
    *,
    query: str,
    settings: AppSettings,
    total_candidates: int,
    routing_decision: QueryRoutingDecision,
    selection_result: RetrievalSelectionResult,
) -> RetrievalTrace:
    """建立 assembler 需要的最小 trace 物件。

    參數：
    - `query`：題目 query。
    - `settings`：應用程式設定。
    - `total_candidates`：候選總數。
    - `routing_decision`：本次 query routing 決策。
    - `selection_result`：本次 diversified selection 結果。

    回傳：
    - `RetrievalTrace`：最小 retrieval trace dataclass。
    """

    return RetrievalTrace(
        query=query,
        vector_top_k=settings.retrieval_vector_top_k,
        fts_top_k=settings.retrieval_fts_top_k,
        max_candidates=settings.retrieval_max_candidates,
        rerank_top_n=min(settings.rerank_top_n, total_candidates),
        query_type=routing_decision.query_type.value,
        query_type_language=routing_decision.language,
        query_type_source=routing_decision.source,
        query_type_confidence=routing_decision.confidence,
        query_type_matched_rules=list(routing_decision.matched_rules),
        query_type_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.query_type_rule_hits
        ],
        query_type_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.query_type_embedding_scores
        ],
        query_type_top_label=routing_decision.query_type_top_label,
        query_type_runner_up_label=routing_decision.query_type_runner_up_label,
        query_type_embedding_margin=routing_decision.query_type_embedding_margin,
        query_type_fallback_used=routing_decision.query_type_fallback_used,
        query_type_fallback_reason=routing_decision.query_type_fallback_reason,
        summary_scope=routing_decision.summary_scope,
        summary_strategy=routing_decision.summary_strategy,
        summary_strategy_source=routing_decision.summary_strategy_source,
        summary_strategy_confidence=routing_decision.summary_strategy_confidence,
        summary_strategy_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.summary_strategy_rule_hits
        ],
        summary_strategy_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.summary_strategy_embedding_scores
        ],
        summary_strategy_top_label=routing_decision.summary_strategy_top_label,
        summary_strategy_runner_up_label=routing_decision.summary_strategy_runner_up_label,
        summary_strategy_embedding_margin=routing_decision.summary_strategy_embedding_margin,
        summary_strategy_fallback_used=routing_decision.summary_strategy_fallback_used,
        summary_strategy_fallback_reason=routing_decision.summary_strategy_fallback_reason,
        resolved_document_ids=list(routing_decision.resolved_document_ids),
        document_mention_source=routing_decision.document_mention_source,
        document_mention_confidence=routing_decision.document_mention_confidence,
        document_mention_candidates=[dict(candidate) for candidate in routing_decision.document_mention_candidates],
        selected_profile=routing_decision.selected_profile,
        profile_settings=routing_decision.resolved_settings,
        selection_applied=selection_result.applied,
        selection_strategy=selection_result.strategy,
        selected_document_count=len(selection_result.selected_document_ids),
        selected_parent_count=len(selection_result.selected_parent_ids),
        selected_document_ids=list(selection_result.selected_document_ids),
        selected_parent_ids=list(selection_result.selected_parent_ids),
        dropped_by_diversity=[
            {
                "document_id": entry.document_id,
                "parent_chunk_id": entry.parent_chunk_id,
                "chunk_id": entry.chunk_id,
                "drop_reason": entry.drop_reason,
            }
            for entry in selection_result.dropped_by_diversity
        ],
        candidates=[],
    )


def _build_query_routing_detail(
    *,
    routing_decision: QueryRoutingDecision,
) -> EvaluationQueryRoutingDetail:
    """將 query routing 決策轉為 evaluation API detail。

    參數：
    - `routing_decision`：本次 query routing 決策。
    回傳：
    - `EvaluationQueryRoutingDetail`：preview 與 benchmark 共用的 routing detail。
    """

    return EvaluationQueryRoutingDetail(
        query_type=routing_decision.query_type,
        language=routing_decision.language,
        confidence=routing_decision.confidence,
        source=routing_decision.source,
        matched_rules=list(routing_decision.matched_rules),
        query_type_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.query_type_rule_hits
        ],
        query_type_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.query_type_embedding_scores
        ],
        query_type_top_label=routing_decision.query_type_top_label,
        query_type_runner_up_label=routing_decision.query_type_runner_up_label,
        query_type_embedding_margin=routing_decision.query_type_embedding_margin,
        query_type_fallback_used=routing_decision.query_type_fallback_used,
        query_type_fallback_reason=routing_decision.query_type_fallback_reason,
        summary_scope=routing_decision.summary_scope,
        summary_strategy=routing_decision.summary_strategy,
        summary_strategy_source=routing_decision.summary_strategy_source,
        summary_strategy_confidence=routing_decision.summary_strategy_confidence,
        summary_strategy_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.summary_strategy_rule_hits
        ],
        summary_strategy_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.summary_strategy_embedding_scores
        ],
        summary_strategy_top_label=routing_decision.summary_strategy_top_label,
        summary_strategy_runner_up_label=routing_decision.summary_strategy_runner_up_label,
        summary_strategy_embedding_margin=routing_decision.summary_strategy_embedding_margin,
        summary_strategy_fallback_used=routing_decision.summary_strategy_fallback_used,
        summary_strategy_fallback_reason=routing_decision.summary_strategy_fallback_reason,
        resolved_document_ids=list(routing_decision.resolved_document_ids),
        document_mention_source=routing_decision.document_mention_source,
        document_mention_confidence=routing_decision.document_mention_confidence,
        document_mention_candidates=[dict(candidate) for candidate in routing_decision.document_mention_candidates],
        selected_profile=routing_decision.selected_profile,
        resolved_settings=routing_decision.resolved_settings,
    )


def _build_selection_detail(*, selection_result: RetrievalSelectionResult) -> EvaluationSelectionDetail:
    """將 selection 結果轉為 evaluation API detail。

    參數：
    - `selection_result`：本次 diversified selection 結果。

    回傳：
    - `EvaluationSelectionDetail`：preview 與 benchmark 共用的 selection detail。
    """

    return EvaluationSelectionDetail(
        applied=selection_result.applied,
        strategy=selection_result.strategy,
        selected_document_count=len(selection_result.selected_document_ids),
        selected_parent_count=len(selection_result.selected_parent_ids),
        selected_document_ids=list(selection_result.selected_document_ids),
        selected_parent_ids=list(selection_result.selected_parent_ids),
        dropped_by_diversity=[
            {
                "document_id": entry.document_id,
                "parent_chunk_id": entry.parent_chunk_id,
                "chunk_id": entry.chunk_id,
                "drop_reason": entry.drop_reason,
            }
            for entry in selection_result.dropped_by_diversity
        ],
    )


def _load_document_names(*, session: Session, area_id: str) -> dict[str, str]:
    """載入 area 內文件名稱映射。

    參數：
    - `session`：目前資料庫 session。
    - `area_id`：目標 area。

    回傳：
    - `dict[str, str]`：文件名稱映射。
    """

    rows = session.execute(select(Document.id, Document.file_name).where(Document.area_id == area_id)).all()
    return {row.id: row.file_name for row in rows}


def _build_recall_stage(
    *,
    matches,
    gold_spans: list[GoldSpan],
    document_names: dict[str, str],
    top_k: int,
) -> EvaluationCandidateStageResponse:
    """建立 recall stage response。"""

    items: list[EvaluationStageCandidate] = []
    relevances: list[int | None] = []
    full_relevances = [
        match_gold_relevance(
            gold_spans,
            CandidateWindow(
                document_id=match.chunk.document_id,
                start_offset=match.chunk.start_offset,
                end_offset=match.chunk.end_offset,
            ),
        )
        for match in matches
    ]
    for rank, match in enumerate(matches[:top_k], start=1):
        relevance = match_gold_relevance(
            gold_spans,
            CandidateWindow(
                document_id=match.chunk.document_id,
                start_offset=match.chunk.start_offset,
                end_offset=match.chunk.end_offset,
            ),
        )
        relevances.append(relevance)
        items.append(
            EvaluationStageCandidate(
                document_id=match.chunk.document_id,
                document_name=document_names.get(match.chunk.document_id, "Unknown"),
                parent_chunk_id=match.chunk.parent_chunk_id,
                child_chunk_ids=[match.chunk.id],
                heading=match.chunk.heading,
                start_offset=match.chunk.start_offset,
                end_offset=match.chunk.end_offset,
                excerpt=match.chunk.content[:240],
                source="hybrid",
                rank=rank,
                vector_rank=match.vector_rank,
                fts_rank=match.fts_rank,
                rrf_rank=match.rrf_rank,
                rerank_rank=None,
                matched_relevance=relevance,
            )
        )
    return EvaluationCandidateStageResponse(
        stage="recall",
        first_hit_rank=first_hit_rank(relevances),
        full_hit_rank=first_hit_rank(full_relevances),
        rerank_applied=None,
        fallback_reason=None,
        items=items,
    )


def _build_rerank_stage(
    *,
    candidates,
    gold_spans: list[GoldSpan],
    document_names: dict[str, str],
    top_k: int,
    apply_rerank: bool,
) -> EvaluationCandidateStageResponse:
    """建立 rerank stage response。"""

    items: list[EvaluationStageCandidate] = []
    relevances: list[int | None] = []
    rerank_applied = any(candidate.rerank_applied for candidate in candidates) if apply_rerank else None
    fallback_reason = next(
        (candidate.rerank_fallback_reason for candidate in candidates if candidate.rerank_fallback_reason),
        None,
    )
    grouped_candidates: dict[tuple[str, str | None], list[object]] = defaultdict(list)
    order: list[tuple[str, str | None]] = []
    for candidate in candidates:
        group_key = (str(candidate.document_id), str(candidate.parent_chunk_id) if candidate.parent_chunk_id is not None else None)
        if group_key not in grouped_candidates:
            order.append(group_key)
        grouped_candidates[group_key].append(candidate)

    full_relevances: list[int | None] = []
    for group_key in order:
        group = grouped_candidates[group_key]
        full_relevances.append(
            match_gold_relevance_for_windows(
                gold_spans,
                [
                    CandidateWindow(
                        document_id=str(candidate.document_id),
                        start_offset=candidate.start_offset,
                        end_offset=candidate.end_offset,
                    )
                    for candidate in group
                ],
            )
        )

    for rank, group_key in enumerate(order[:top_k], start=1):
        group = grouped_candidates[group_key]
        relevance = match_gold_relevance_for_windows(
            gold_spans,
            [
                CandidateWindow(
                    document_id=str(candidate.document_id),
                    start_offset=candidate.start_offset,
                    end_offset=candidate.end_offset,
                )
                for candidate in group
            ],
        )
        relevances.append(relevance)
        items.append(
            EvaluationStageCandidate(
                document_id=group[0].document_id,
                document_name=document_names.get(group[0].document_id, "Unknown"),
                parent_chunk_id=group[0].parent_chunk_id,
                child_chunk_ids=[candidate.chunk_id for candidate in group],
                heading=group[0].heading,
                start_offset=min(candidate.start_offset for candidate in group),
                end_offset=max(candidate.end_offset for candidate in group),
                excerpt="\n\n".join(candidate.content for candidate in group)[:240],
                source=group[0].source,
                rank=rank,
                vector_rank=min((candidate.vector_rank for candidate in group if candidate.vector_rank is not None), default=None),
                fts_rank=min((candidate.fts_rank for candidate in group if candidate.fts_rank is not None), default=None),
                rrf_rank=min((candidate.rrf_rank for candidate in group if candidate.rrf_rank is not None), default=None),
                rerank_rank=min(
                    (candidate.rerank_rank for candidate in group if candidate.rerank_rank is not None),
                    default=(rank if apply_rerank else None),
                ),
                matched_relevance=relevance,
            )
        )
    return EvaluationCandidateStageResponse(
        stage="rerank",
        first_hit_rank=first_hit_rank(relevances) if apply_rerank else None,
        full_hit_rank=first_hit_rank(full_relevances) if apply_rerank else None,
        rerank_applied=rerank_applied,
        fallback_reason=fallback_reason if apply_rerank else None,
        items=items if apply_rerank else [],
    )


def _build_assembled_stage(
    *,
    session: Session,
    contexts,
    gold_spans: list[GoldSpan],
    document_names: dict[str, str],
    top_k: int,
) -> EvaluationCandidateStageResponse:
    """建立 assembled stage response。"""

    items: list[EvaluationStageCandidate] = []
    relevances: list[int | None] = []
    chunk_ids = [str(chunk_id) for context in contexts for chunk_id in context.chunk_ids]
    chunks = session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))).all() if chunk_ids else []
    chunk_by_id = {str(chunk.id): chunk for chunk in chunks}
    full_relevances: list[int | None] = []
    for context in contexts:
        windows = [
            CandidateWindow(
                document_id=str(chunk.document_id),
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
            )
            for chunk_id in context.chunk_ids
            if (chunk := chunk_by_id.get(str(chunk_id))) is not None
        ]
        if not windows:
            windows = [
                CandidateWindow(
                    document_id=str(context.document_id),
                    start_offset=context.start_offset,
                    end_offset=context.end_offset,
                )
            ]
        full_relevances.append(match_gold_relevance_for_windows(gold_spans, windows))

    for rank, context in enumerate(contexts[:top_k], start=1):
        windows = [
            CandidateWindow(
                document_id=str(chunk.document_id),
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
            )
            for chunk_id in context.chunk_ids
            if (chunk := chunk_by_id.get(str(chunk_id))) is not None
        ]
        if not windows:
            windows = [
                CandidateWindow(
                    document_id=str(context.document_id),
                    start_offset=context.start_offset,
                    end_offset=context.end_offset,
                )
            ]
        relevance = match_gold_relevance_for_windows(gold_spans, windows)
        relevances.append(relevance)
        items.append(
            EvaluationStageCandidate(
                document_id=context.document_id,
                document_name=document_names.get(context.document_id, "Unknown"),
                parent_chunk_id=context.parent_chunk_id,
                child_chunk_ids=context.chunk_ids,
                heading=context.heading,
                start_offset=context.start_offset,
                end_offset=context.end_offset,
                excerpt=context.assembled_text[:240],
                source=context.source,
                rank=rank,
                vector_rank=None,
                fts_rank=None,
                rrf_rank=None,
                rerank_rank=rank,
                matched_relevance=relevance,
            )
        )
    return EvaluationCandidateStageResponse(
        stage="assembled",
        first_hit_rank=first_hit_rank(relevances),
        full_hit_rank=first_hit_rank(full_relevances),
        rerank_applied=None,
        fallback_reason=None,
        items=items,
    )

