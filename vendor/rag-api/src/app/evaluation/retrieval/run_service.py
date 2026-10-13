"""Retrieval evaluation benchmark runner。"""

from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import (
    EvaluationRunStatus,
    RetrievalEvalDataset,
    RetrievalEvalItem,
    RetrievalEvalItemSpan,
    RetrievalEvalRun,
    RetrievalEvalRunArtifact,
)
from app.schemas.evaluation import (
    EvaluationPerQueryDetail,
    EvaluationPerQueryStageDetail,
    EvaluationRunReportResponse,
    EvaluationRunSummary,
    EvaluationStageMetricSummary,
    EvaluationSummaryByDimension,
)
from app.services.access import require_minimum_area_role
from app.evaluation.retrieval.mapping import first_hit_rank
from app.evaluation.retrieval.metrics import (
    document_coverage_at_k,
    mean_reciprocal_rank_at_k,
    normalized_discounted_cumulative_gain,
    precision_at_k,
    recall_at_k,
)
from app.evaluation.retrieval.datasets import build_dataset_summary
from app.evaluation.retrieval.profiles import resolve_evaluation_settings
from app.evaluation.retrieval.stage_runner import evaluate_item_stage_outputs
from app.services.retrieval_routing import build_query_routing_decision

# 這些外部資料集的原始任務皆帶有指定文件上下文；benchmark run 應用 gold 文件作為 oracle scope。
GOLD_DOCUMENT_SCOPE_DATASET_PREFIXES = ("qasper-", "uda-", "drcd-")
# benchmark 文件白名單未套用時的 trace 模式名稱。
BENCHMARK_DOCUMENT_SCOPE_MODE_ROUTING = "routing"
# benchmark 以 gold span 文件作為指定文件時的 trace 模式名稱。
BENCHMARK_DOCUMENT_SCOPE_MODE_GOLD = "gold_document_ids"


def run_evaluation_dataset(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    dataset: RetrievalEvalDataset,
    items: list[RetrievalEvalItem],
    spans_by_item_id: dict[str, list[RetrievalEvalItemSpan]],
    top_k: int,
    evaluation_profile: str = "production_like_v1",
) -> EvaluationRunReportResponse:
    """執行單一 dataset 的 benchmark run。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `dataset`：要執行的 dataset。
    - `items`：dataset 內題目列表。
    - `spans_by_item_id`：各題對應的 gold spans。
    - `top_k`：指標截斷排名。

    回傳：
    - `EvaluationRunReportResponse`：完整 benchmark run 結果。
    """

    require_minimum_area_role(
        session=session,
        principal=principal,
        area_id=dataset.area_id,
        minimum_role=build_required_role(),
    )

    routing_decision = build_query_routing_decision(
        settings=settings,
        query=dataset.query_type.value,
        explicit_query_type=dataset.query_type,
    )
    effective_settings = resolve_evaluation_settings(
        settings=routing_decision.effective_settings,
        evaluation_profile=evaluation_profile,
    )
    config_snapshot = _build_evaluation_config_snapshot(
        settings=effective_settings,
        top_k=top_k,
        query_type=dataset.query_type.value,
        selected_profile=routing_decision.selected_profile,
        summary_strategy=routing_decision.summary_strategy,
        benchmark_document_scope_mode=_resolve_benchmark_document_scope_mode(dataset=dataset),
    )

    run = RetrievalEvalRun(
        dataset_id=dataset.id,
        status=EvaluationRunStatus.running,
        baseline_run_id=dataset.baseline_run_id,
        created_by_sub=principal.sub,
        total_items=len(items),
        evaluation_profile=evaluation_profile,
        config_snapshot=json.dumps(config_snapshot, ensure_ascii=False, sort_keys=True),
        error_message=None,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        report_payload = _build_run_report_payload(
            session=session,
            principal=principal,
            settings=effective_settings,
            dataset=dataset,
            items=items,
            spans_by_item_id=spans_by_item_id,
            top_k=top_k,
        )
        baseline_compare = _build_baseline_compare(
            session=session,
            baseline_run_id=dataset.baseline_run_id,
            current_summary=report_payload["summary_metrics"],
            current_config_snapshot=config_snapshot,
        )
        artifact = RetrievalEvalRunArtifact(
            run_id=run.id,
            report_json=json.dumps(report_payload, ensure_ascii=False, default=str),
            baseline_compare_json=json.dumps(baseline_compare, ensure_ascii=False, default=str) if baseline_compare is not None else None,
        )
        run.status = EvaluationRunStatus.completed
        run.completed_at = datetime.now(UTC)
        session.add(artifact)
        if dataset.baseline_run_id is None:
            dataset.baseline_run_id = run.id
        session.commit()
        session.refresh(run)
        return EvaluationRunReportResponse(
            run=build_run_summary(run),
            dataset=build_dataset_summary(session=session, dataset=dataset),
            summary_metrics={stage: EvaluationStageMetricSummary(**metrics) for stage, metrics in report_payload["summary_metrics"].items()},
            breakdowns=[EvaluationSummaryByDimension(**item) for item in report_payload["breakdowns"]],
            per_query=[EvaluationPerQueryDetail(**item) for item in report_payload["per_query"]],
            baseline_compare=baseline_compare,
        )
    except Exception as exc:
        run.status = EvaluationRunStatus.failed
        run.error_message = str(exc)
        session.commit()
        raise


def build_run_summary(run: RetrievalEvalRun) -> EvaluationRunSummary:
    """將 ORM run 轉為 API summary。

    參數：
    - `run`：ORM run。

    回傳：
    - `EvaluationRunSummary`：API summary。
    """

    payload = {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "baseline_run_id": run.baseline_run_id,
        "created_by_sub": run.created_by_sub,
        "total_items": run.total_items,
        "evaluation_profile": run.evaluation_profile,
        "config_snapshot": json.loads(run.config_snapshot) if run.config_snapshot else {},
        "error_message": run.error_message,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }
    return EvaluationRunSummary.model_validate(payload)


def _build_evaluation_config_snapshot(
    *,
    settings: AppSettings,
    top_k: int,
    query_type: str,
    selected_profile: str,
    summary_strategy: str | None,
    benchmark_document_scope_mode: str,
) -> dict[str, object]:
    """建立 benchmark run 的設定快照。"""

    return deepcopy(
        {
            "top_k": top_k,
            "query_routing": {
                "query_type": query_type,
                "selected_profile": selected_profile,
                "summary_scope": None,
                "summary_strategy": summary_strategy,
                "resolved_document_ids": [],
            },
            "benchmark_document_scope": {
                "mode": benchmark_document_scope_mode,
                "dataset_prefixes": list(GOLD_DOCUMENT_SCOPE_DATASET_PREFIXES),
            },
            "retrieval": {
                "vector_top_k": settings.retrieval_vector_top_k,
                "fts_top_k": settings.retrieval_fts_top_k,
                "max_candidates": settings.retrieval_max_candidates,
                "document_recall_enabled": settings.retrieval_document_recall_enabled,
                "document_recall_top_k": settings.retrieval_document_recall_top_k,
                "rrf_k": settings.retrieval_rrf_k,
                "hnsw_ef_search": settings.retrieval_hnsw_ef_search,
            },
            "rerank": {
                "provider": settings.rerank_provider,
                "model": settings.rerank_model,
                "top_n": settings.rerank_top_n,
                "max_chars_per_doc": settings.rerank_max_chars_per_doc,
            },
            "assembler": {
                "max_contexts": settings.assembler_max_contexts,
                "max_chars_per_context": settings.assembler_max_chars_per_context,
                "max_children_per_parent": settings.assembler_max_children_per_parent,
            },
        }
    )


def build_required_role():
    """回傳 evaluation 功能要求的最小角色。

    參數：
    - 無。

    回傳：
    - `Role`：evaluation 最小角色。
    """

    from app.db.models import Role

    return Role.maintainer


def _build_run_report_payload(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    dataset: RetrievalEvalDataset,
    items: list[RetrievalEvalItem],
    spans_by_item_id: dict[str, list[RetrievalEvalItemSpan]],
    top_k: int,
) -> dict[str, object]:
    """建立完整 benchmark 報表 payload。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `dataset`：要執行的 dataset。
    - `items`：dataset 內題目列表。
    - `spans_by_item_id`：各題 gold spans。
    - `top_k`：指標截斷排名。

    回傳：
    - `dict[str, object]`：可序列化的完整報表。
    """

    per_query: list[dict[str, object]] = []
    summary_bucket: dict[str, list[dict[str, float]]] = defaultdict(list)
    breakdown_bucket: dict[tuple[str, str], dict[str, list[dict[str, float]]]] = defaultdict(lambda: defaultdict(list))
    benchmark_document_scope_mode = _resolve_benchmark_document_scope_mode(dataset=dataset)

    for item in items:
        spans = spans_by_item_id.get(item.id, [])
        benchmark_document_scope_ids = (
            _resolve_gold_document_scope_ids(spans=spans)
            if benchmark_document_scope_mode == BENCHMARK_DOCUMENT_SCOPE_MODE_GOLD
            else None
        )
        detail = _evaluate_single_item(
            session=session,
            principal=principal,
            settings=settings,
            area_id=dataset.area_id,
            item=item,
            spans=spans,
            top_k=top_k,
            benchmark_document_scope_mode=benchmark_document_scope_mode,
            benchmark_document_scope_ids=benchmark_document_scope_ids,
        )
        per_query.append(detail)
        for stage_name in ("recall", "rerank", "assembled"):
            metrics = detail["_metrics"][stage_name]
            summary_bucket[stage_name].append(metrics)
            breakdown_bucket[("language", item.language.value)][stage_name].append(metrics)
            breakdown_bucket[("query_type", item.query_type.value)][stage_name].append(metrics)

    return {
        "summary_metrics": {
            stage_name: _average_metric_bucket(metric_list)
            for stage_name, metric_list in summary_bucket.items()
        },
        "breakdowns": [
            {
                "dimension": dimension,
                "value": value,
                "metrics": {
                    stage_name: _average_metric_bucket(metric_list)
                    for stage_name, metric_list in stage_bucket.items()
                },
            }
            for (dimension, value), stage_bucket in sorted(breakdown_bucket.items())
        ],
        "per_query": [
            {key: value for key, value in detail.items() if key != "_metrics"}
            for detail in per_query
        ],
    }


def _evaluate_single_item(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    item: RetrievalEvalItem,
    spans: list[RetrievalEvalItemSpan],
    top_k: int,
    benchmark_document_scope_mode: str = BENCHMARK_DOCUMENT_SCOPE_MODE_ROUTING,
    benchmark_document_scope_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """執行單題評估並產出 per-query detail。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `area_id`：dataset 所屬 area。
    - `item`：評估題目。
    - `spans`：該題的 gold spans。
    - `top_k`：指標截斷排名。
    - `benchmark_document_scope_mode`：benchmark 指定文件模式。
    - `benchmark_document_scope_ids`：若為 gold 文件模式，本題使用的文件白名單。

    回傳：
    - `dict[str, object]`：可序列化的 per-query 明細。
    """

    stage_result = evaluate_item_stage_outputs(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        item=item,
        spans=spans,
        top_k=top_k,
        allowed_document_ids_override=benchmark_document_scope_ids,
    )
    gold_spans = stage_result.gold_spans
    recall_relevances = [candidate.matched_relevance for candidate in stage_result.recall_stage.items[:top_k]]
    rerank_relevances = [candidate.matched_relevance for candidate in stage_result.rerank_stage.items[:top_k]]
    assembled_relevances = [candidate.matched_relevance for candidate in stage_result.assembled_stage.items[:top_k]]
    gold_document_ids = {str(span.document_id) for span in gold_spans if span.document_id is not None}
    metrics = {
        "recall": _build_stage_metrics(
            relevances=recall_relevances,
            document_ids=[str(candidate.document_id) for candidate in stage_result.recall_stage.items[:top_k]],
            gold_document_ids=gold_document_ids,
            top_k=top_k,
        ),
        "rerank": _build_stage_metrics(
            relevances=rerank_relevances,
            document_ids=[str(candidate.document_id) for candidate in stage_result.rerank_stage.items[:top_k]],
            gold_document_ids=gold_document_ids,
            top_k=top_k,
        ),
        "assembled": _build_stage_metrics(
            relevances=assembled_relevances,
            document_ids=[str(candidate.document_id) for candidate in stage_result.assembled_stage.items[:top_k]],
            gold_document_ids=gold_document_ids,
            top_k=top_k,
        ),
    }
    return {
        "item_id": item.id,
        "query_text": item.query_text,
        "language": item.language.value,
        "retrieval_miss": any(span.is_retrieval_miss for span in gold_spans),
        "gold_spans": [build_item_summary_span(span) for span in spans],
        "query_routing": stage_result.query_routing.model_dump(mode="json"),
        "benchmark_document_scope": {
            "mode": benchmark_document_scope_mode,
            "document_ids": list(benchmark_document_scope_ids or ()),
        },
        "selection": stage_result.selection.model_dump(mode="json"),
        "recall": _build_stage_detail(recall_relevances).model_dump(mode="json"),
        "rerank": _build_stage_detail(
            rerank_relevances,
            rerank_applied=stage_result.rerank_stage.rerank_applied,
            fallback_reason=stage_result.rerank_stage.fallback_reason,
        ).model_dump(mode="json"),
        "assembled": _build_stage_detail(assembled_relevances).model_dump(mode="json"),
        "baseline_delta": {
            "recall_first_hit_rank_delta": None,
            "rerank_first_hit_rank_delta": None,
            "assembled_first_hit_rank_delta": None,
        },
        "_metrics": metrics,
    }


def _resolve_benchmark_document_scope_mode(*, dataset: RetrievalEvalDataset) -> str:
    """依 dataset 名稱決定 benchmark 是否使用 gold 文件作為指定文件 scope。

    參數：
    - `dataset`：目前 benchmark dataset。

    回傳：
    - `str`：benchmark document scope 模式。
    """

    dataset_name = dataset.name.strip().lower()
    if dataset_name.startswith(GOLD_DOCUMENT_SCOPE_DATASET_PREFIXES):
        return BENCHMARK_DOCUMENT_SCOPE_MODE_GOLD
    return BENCHMARK_DOCUMENT_SCOPE_MODE_ROUTING


def _resolve_gold_document_scope_ids(*, spans: list[RetrievalEvalItemSpan]) -> tuple[str, ...] | None:
    """從 gold spans 取出本題指定文件 ids。

    參數：
    - `spans`：該題 gold spans。

    回傳：
    - `tuple[str, ...] | None`：本題可用文件白名單；沒有可用文件時回傳空值。
    """

    document_ids = sorted(
        {
            str(span.document_id)
            for span in spans
            if span.document_id is not None and not span.is_retrieval_miss
        }
    )
    return tuple(document_ids) if document_ids else None


def build_item_summary_span(span: RetrievalEvalItemSpan) -> dict[str, object]:
    """將 ORM span 轉為可序列化輸出。

    參數：
    - `span`：ORM span。

    回傳：
    - `dict[str, object]`：可序列化 span。
    """

    return {
        "id": span.id,
        "document_id": span.document_id,
        "start_offset": span.start_offset,
        "end_offset": span.end_offset,
        "relevance_grade": span.relevance_grade,
        "is_retrieval_miss": span.is_retrieval_miss,
        "created_by_sub": span.created_by_sub,
        "created_at": span.created_at.isoformat(),
    }


def _build_stage_detail(
    relevances: list[int | None],
    *,
    rerank_applied: bool | None = None,
    fallback_reason: str | None = None,
) -> EvaluationPerQueryStageDetail:
    """建立單題單階段 detail。

    參數：
    - `relevances`：依排名排序的 relevance。
    - `rerank_applied`：是否已成功套用 rerank provider。
    - `fallback_reason`：若 rerank fallback，記錄原因。

    回傳：
    - `EvaluationPerQueryStageDetail`：單階段 detail。
    """

    first_rank = first_hit_rank(relevances)
    matched_relevance = max((value or 0 for value in relevances), default=0) or None
    return EvaluationPerQueryStageDetail(
        first_hit_rank=first_rank,
        matched_core_evidence=matched_relevance == 3,
        matched_relevance=matched_relevance,
        rerank_applied=rerank_applied,
        fallback_reason=fallback_reason,
    )


def _build_stage_metrics(
    *,
    relevances: list[int | None],
    document_ids: list[str],
    gold_document_ids: set[str],
    top_k: int,
) -> dict[str, float]:
    """建立單階段 metrics。

    參數：
    - `relevances`：依排名排序的 relevance。
    - `document_ids`：依排名排序的文件 id。
    - `gold_document_ids`：gold files。
    - `top_k`：指標截斷排名。

    回傳：
    - `dict[str, float]`：單階段 metrics。
    """

    normalized = [value or 0 for value in relevances]
    return {
        "nDCG_at_k": normalized_discounted_cumulative_gain(normalized, k=top_k),
        "recall_at_k": recall_at_k(normalized, k=top_k),
        "mrr_at_k": mean_reciprocal_rank_at_k(normalized, k=top_k),
        "precision_at_k": precision_at_k(normalized, k=top_k),
        "document_coverage_at_k": document_coverage_at_k(document_ids, gold_document_ids=gold_document_ids, k=top_k),
    }


def _average_metric_bucket(metric_list: list[dict[str, float]]) -> dict[str, float]:
    """計算一組 metrics 的平均值。

    參數：
    - `metric_list`：多筆單題 metrics。

    回傳：
    - `dict[str, float]`：平均 metrics。
    """

    if not metric_list:
        return {
            "nDCG_at_k": 0.0,
            "recall_at_k": 0.0,
            "mrr_at_k": 0.0,
            "precision_at_k": 0.0,
            "document_coverage_at_k": 0.0,
        }
    keys = metric_list[0].keys()
    return {key: sum(item[key] for item in metric_list) / len(metric_list) for key in keys}


def _build_baseline_compare(
    *,
    session: Session,
    baseline_run_id: str | None,
    current_summary: dict[str, object],
    current_config_snapshot: dict[str, object],
) -> dict[str, object] | None:
    """建立與 baseline 的 summary compare。

    參數：
    - `session`：目前資料庫 session。
    - `baseline_run_id`：baseline run id。
    - `current_summary`：目前 run 的 summary metrics。
    - `current_config_snapshot`：目前 run 的設定快照。

    回傳：
    - `dict[str, object] | None`：baseline compare；無 baseline 時回傳空值。
    """

    if baseline_run_id is None:
        return None
    baseline_run = session.get(RetrievalEvalRun, baseline_run_id)
    if baseline_run is None:
        return None
    baseline_config_snapshot = json.loads(baseline_run.config_snapshot) if baseline_run.config_snapshot else {}
    current_scope_mode = _extract_benchmark_document_scope_mode(config_snapshot=current_config_snapshot)
    baseline_scope_mode = _extract_benchmark_document_scope_mode(config_snapshot=baseline_config_snapshot)
    if current_scope_mode != baseline_scope_mode:
        return {
            "baseline_run_id": baseline_run_id,
            "skipped": True,
            "reason": "benchmark_document_scope_mismatch",
            "baseline_document_scope_mode": baseline_scope_mode,
            "candidate_document_scope_mode": current_scope_mode,
        }
    artifact = session.scalars(
        select(RetrievalEvalRunArtifact).where(RetrievalEvalRunArtifact.run_id == baseline_run_id)
    ).one_or_none()
    if artifact is None:
        return None
    baseline_payload = json.loads(artifact.report_json)
    baseline_summary = baseline_payload.get("summary_metrics", {})
    compare: dict[str, object] = {"baseline_run_id": baseline_run_id, "delta": {}}
    for stage_name, metrics in current_summary.items():
        baseline_stage = baseline_summary.get(stage_name, {})
        compare["delta"][stage_name] = {
            key: metrics[key] - baseline_stage.get(key, 0.0)
            for key in metrics.keys()
        }
    return compare


def _extract_benchmark_document_scope_mode(*, config_snapshot: dict[str, object]) -> str:
    """從 benchmark config snapshot 取出文件 scope 模式。

    參數：
    - `config_snapshot`：benchmark run 的設定快照。

    回傳：
    - `str`：benchmark 文件 scope 模式；舊 run 缺欄位時視為 routing。
    """

    scope_payload = config_snapshot.get("benchmark_document_scope")
    if not isinstance(scope_payload, dict):
        return BENCHMARK_DOCUMENT_SCOPE_MODE_ROUTING
    mode = scope_payload.get("mode")
    return str(mode) if mode else BENCHMARK_DOCUMENT_SCOPE_MODE_ROUTING
