"""Retrieval runtime orchestration，串接 routing、recall、rerank 與 selection。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import EvaluationQueryType
from app.services.access import require_area_access
from app.services.retrieval_recall import apply_python_rrf, recall_ranked_candidates
from app.services.retrieval_rerank import apply_ranking_policy, apply_rerank, build_retrieval_candidate
from app.services.retrieval_routing import DocumentScope, SummaryStrategy, build_query_routing_decision
from app.services.retrieval_selection import apply_scope_aware_selection
from app.services.retrieval_types import RetrievalResult, RetrievalTrace, RetrievalTraceEntry


def retrieve_area_candidates(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    query: str,
    document_scope: DocumentScope | str | None = None,
    summary_strategy: SummaryStrategy | str | None = None,
    query_type: EvaluationQueryType | None = None,
    allowed_document_ids_override: tuple[str, ...] | None = None,
    rerank: bool = True,
) -> RetrievalResult:
    """在指定 area 內取得 hybrid recall、Python RRF 與 rerank candidates。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。
    - `document_scope`：若由外部提供文件範圍提示，只影響 scope 判斷，不允許直接指定 document ids。
    - `summary_strategy`：若由外部提供摘要策略提示，只在 `document_summary` 下使用。
    - `query_type`：若已由上層明確指定的 query type；否則由 classifier 自動判定。
    - `allowed_document_ids_override`：benchmark/test 專用文件白名單；正式 public chat 不應使用。

    回傳：
    - `RetrievalResult`：已完成 recall、RRF、ranking hook 與 rerank 的候選集合。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)

    routing_decision = build_query_routing_decision(
        settings=settings,
        query=query,
        explicit_document_scope=document_scope,
        explicit_summary_strategy=summary_strategy,
        explicit_query_type=query_type,
        session=session,
        principal=principal,
        area_id=area_id,
    )
    resolved_document_ids = allowed_document_ids_override or routing_decision.resolved_document_ids or None
    effective_settings = routing_decision.effective_settings
    recalled_matches = recall_ranked_candidates(
        session=session,
        settings=effective_settings,
        area_id=area_id,
        query=query,
        allowed_document_ids=resolved_document_ids,
        allowed_parent_ids=None,
    )
    rrf_matches = apply_python_rrf(matches=recalled_matches, settings=effective_settings)
    ranked_matches = apply_ranking_policy(
        matches=rrf_matches,
        query=query,
        settings=effective_settings,
    )
    if rerank:
        reranked_matches = apply_rerank(
            matches=ranked_matches,
            query=query,
            settings=effective_settings,
        )
    else:
        # Hybrid recall + RRF only — skip the (slow, CPU) cross-encoder rerank.
        reranked_matches = ranked_matches
    reranked_candidates = [build_retrieval_candidate(match) for match in reranked_matches]
    selection_result = apply_scope_aware_selection(
        candidates=reranked_candidates,
        selected_profile=routing_decision.selected_profile,
        resolved_document_ids=resolved_document_ids or (),
        max_contexts=effective_settings.assembler_max_contexts,
    )
    candidates = selection_result.candidates

    return RetrievalResult(
        candidates=candidates,
        trace=RetrievalTrace(
            query=query,
            vector_top_k=effective_settings.retrieval_vector_top_k,
            fts_top_k=effective_settings.retrieval_fts_top_k,
            max_candidates=effective_settings.retrieval_max_candidates,
            rerank_top_n=min(effective_settings.rerank_top_n, len(reranked_matches)),
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
            document_scope="explicit_document_ids" if allowed_document_ids_override else routing_decision.document_scope,
            resolved_document_ids=list(resolved_document_ids or ()),
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
            fallback_reason=None,
            candidates=[
                RetrievalTraceEntry(
                    chunk_id=candidate.chunk_id,
                    source=candidate.source,
                    vector_rank=candidate.vector_rank,
                    fts_rank=candidate.fts_rank,
                    rrf_rank=candidate.rrf_rank,
                    rrf_score=candidate.rrf_score,
                    rerank_rank=candidate.rerank_rank,
                    rerank_score=candidate.rerank_score,
                    rerank_applied=candidate.rerank_applied,
                    rerank_fallback_reason=candidate.rerank_fallback_reason,
                )
                for candidate in candidates
            ],
        ),
    )
