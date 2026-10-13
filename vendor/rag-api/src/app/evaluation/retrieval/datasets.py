"""Retrieval evaluation dataset、review 與報表讀取 service。"""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import (
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    EvaluationQueryType,
    RetrievalEvalDataset,
    RetrievalEvalItem,
    RetrievalEvalItemSpan,
    RetrievalEvalRun,
    RetrievalEvalRunArtifact,
    Role,
    utc_now,
)
from app.schemas.evaluation import (
    CreateEvaluationItemRequest,
    EvaluationCandidatePreviewResponse,
    EvaluationDatasetDetailResponse,
    EvaluationDatasetListResponse,
    EvaluationDatasetSummary,
    EvaluationDocumentSearchHit,
    EvaluationItemSpanResponse,
    EvaluationItemSummary,
    EvaluationPreviewDebugRequest,
    EvaluationRunReportResponse,
    EvaluationRunSummary,
)
from app.evaluation.retrieval.stage_runner import evaluate_item_stage_outputs
from app.services.access import require_area_access, require_minimum_area_role


def list_area_evaluation_datasets(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
) -> EvaluationDatasetListResponse:
    """列出指定 area 的 evaluation datasets。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。

    回傳：
    - `EvaluationDatasetListResponse`：可存取 datasets 清單。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    datasets = session.scalars(
        select(RetrievalEvalDataset)
        .where(RetrievalEvalDataset.area_id == area_id)
        .order_by(RetrievalEvalDataset.created_at.desc())
    ).all()
    return EvaluationDatasetListResponse(items=[build_dataset_summary(session=session, dataset=dataset) for dataset in datasets])


def create_area_evaluation_dataset(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    name: str,
    query_type: EvaluationQueryType,
) -> EvaluationDatasetSummary:
    """建立新的 evaluation dataset。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。
    - `name`：dataset 名稱。
    - `query_type`：dataset 題型。

    回傳：
    - `EvaluationDatasetSummary`：新建立的 dataset。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    dataset = RetrievalEvalDataset(area_id=area_id, name=name, query_type=query_type, created_by_sub=principal.sub)
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    return build_dataset_summary(session=session, dataset=dataset)


def get_evaluation_dataset_detail(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
) -> EvaluationDatasetDetailResponse:
    """讀取 dataset 詳細資料。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。

    回傳：
    - `EvaluationDatasetDetailResponse`：dataset 詳細資料。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    items = session.scalars(
        select(RetrievalEvalItem).where(RetrievalEvalItem.dataset_id == dataset.id).order_by(RetrievalEvalItem.created_at.asc())
    ).all()
    runs = session.scalars(
        select(RetrievalEvalRun).where(RetrievalEvalRun.dataset_id == dataset.id).order_by(RetrievalEvalRun.created_at.desc())
    ).all()
    spans_by_item_id = _load_spans_by_item_id(session=session, item_ids=[item.id for item in items])
    return EvaluationDatasetDetailResponse(
        dataset=build_dataset_summary(session=session, dataset=dataset),
        items=[build_item_summary(item=item, spans=spans_by_item_id.get(item.id, [])) for item in items],
        runs=[build_run_summary(run) for run in runs],
    )


def delete_evaluation_dataset(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
) -> None:
    """刪除單一 evaluation dataset。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。

    回傳：
    - `None`：刪除成功時不回傳內容。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    session.delete(dataset)
    session.commit()


def create_evaluation_item(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
    payload: CreateEvaluationItemRequest,
) -> EvaluationItemSummary:
    """在 dataset 內新增題目。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。
    - `payload`：建立題目 payload。

    回傳：
    - `EvaluationItemSummary`：新題目摘要。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    if payload.query_type is not None and payload.query_type != dataset.query_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item query_type 必須與 dataset query_type 一致。",
        )
    item = RetrievalEvalItem(
        dataset_id=dataset.id,
        query_type=dataset.query_type,
        query_text=payload.query_text,
        language=payload.language,
        notes=payload.notes,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return build_item_summary(item=item, spans=[])


def delete_evaluation_item(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
) -> None:
    """刪除單一 evaluation 題目。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。

    回傳：
    - `None`：刪除成功時不回傳內容。
    """

    item, _dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    session.delete(item)
    session.commit()


def add_item_span(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
    document_id: str,
    start_offset: int,
    end_offset: int,
    relevance_grade: int,
) -> EvaluationItemSummary:
    """為題目新增 gold source span。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。
    - `document_id`：來源文件。
    - `start_offset`：起始 offset。
    - `end_offset`：結束 offset。
    - `relevance_grade`：relevance 分級。

    回傳：
    - `EvaluationItemSummary`：更新後題目摘要。
    """

    item, dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    document = _get_authorized_ready_document(
        session=session,
        principal=principal,
        area_id=dataset.area_id,
        document_id=document_id,
    )
    if not document.display_text or end_offset > len(document.display_text):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="span 超出 display_text 範圍。")
    session.execute(
        delete(RetrievalEvalItemSpan).where(
            RetrievalEvalItemSpan.item_id == item.id,
            RetrievalEvalItemSpan.is_retrieval_miss.is_(True),
        )
    )
    existing_span = session.scalars(
        select(RetrievalEvalItemSpan).where(
            RetrievalEvalItemSpan.item_id == item.id,
            RetrievalEvalItemSpan.document_id == document.id,
            RetrievalEvalItemSpan.start_offset == start_offset,
            RetrievalEvalItemSpan.end_offset == end_offset,
            RetrievalEvalItemSpan.is_retrieval_miss.is_(False),
        )
    ).one_or_none()
    if existing_span is None:
        session.add(
            RetrievalEvalItemSpan(
                item_id=item.id,
                document_id=document.id,
                start_offset=start_offset,
                end_offset=end_offset,
                relevance_grade=relevance_grade,
                is_retrieval_miss=False,
                created_by_sub=principal.sub,
            )
        )
    else:
        existing_span.relevance_grade = relevance_grade
        existing_span.updated_at = utc_now()
    session.commit()
    session.refresh(item)
    spans = _load_spans_by_item_id(session=session, item_ids=[item.id]).get(item.id, [])
    return build_item_summary(item=item, spans=spans)


def mark_item_retrieval_miss(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
) -> EvaluationItemSummary:
    """將題目標記為 retrieval miss。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。

    回傳：
    - `EvaluationItemSummary`：更新後題目摘要。
    """

    item, _dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    session.execute(delete(RetrievalEvalItemSpan).where(RetrievalEvalItemSpan.item_id == item.id))
    session.add(
        RetrievalEvalItemSpan(
            item_id=item.id,
            document_id=None,
            start_offset=0,
            end_offset=0,
            relevance_grade=None,
            is_retrieval_miss=True,
            created_by_sub=principal.sub,
        )
    )
    session.commit()
    session.refresh(item)
    spans = _load_spans_by_item_id(session=session, item_ids=[item.id]).get(item.id, [])
    return build_item_summary(item=item, spans=spans)


def preview_evaluation_candidates(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    item_id: str,
    payload: EvaluationPreviewDebugRequest,
) -> EvaluationCandidatePreviewResponse:
    """讀取單題的 recall/rerank/assembled candidate preview。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `item_id`：目標題目。
    - `payload`：preview 臨時調參 payload。

    回傳：
    - `EvaluationCandidatePreviewResponse`：三階段 candidate preview。
    """

    item, dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    spans = _load_spans_by_item_id(session=session, item_ids=[item.id]).get(item.id, [])
    stage_result = evaluate_item_stage_outputs(
        session=session,
        principal=principal,
        settings=_apply_preview_debug_overrides(settings=settings, payload=payload),
        area_id=dataset.area_id,
        item=item,
        spans=spans,
        top_k=payload.top_k,
        apply_rerank=payload.apply_rerank,
    )
    return EvaluationCandidatePreviewResponse(
        dataset=build_dataset_summary(session=session, dataset=dataset),
        item=build_item_summary(item=item, spans=spans),
        query_routing=stage_result.query_routing,
        selection=stage_result.selection,
        recall=stage_result.recall_stage,
        rerank=stage_result.rerank_stage,
        assembled=stage_result.assembled_stage,
        document_search_hits=_search_document_hits(
            session=session,
            principal=principal,
            area_id=dataset.area_id,
            query=item.query_text,
        ),
    )


def _apply_preview_debug_overrides(*, settings: AppSettings, payload: EvaluationPreviewDebugRequest) -> AppSettings:
    """將 preview 臨時調參套用到單題 evaluation。"""

    updates: dict[str, int] = {}
    if payload.retrieval_vector_top_k is not None:
        updates["retrieval_vector_top_k"] = payload.retrieval_vector_top_k
    if payload.retrieval_fts_top_k is not None:
        updates["retrieval_fts_top_k"] = payload.retrieval_fts_top_k
    if payload.retrieval_max_candidates is not None:
        updates["retrieval_max_candidates"] = payload.retrieval_max_candidates
    if payload.rerank_top_n is not None:
        updates["rerank_top_n"] = payload.rerank_top_n
    return settings.model_copy(update=updates) if updates else settings


def create_evaluation_run(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    dataset_id: str,
    top_k: int,
    evaluation_profile: str = "production_like_v1",
) -> EvaluationRunReportResponse:
    """執行 dataset benchmark。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `dataset_id`：目標 dataset。
    - `top_k`：指標截斷排名。

    回傳：
    - `EvaluationRunReportResponse`：完整 run 報表。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    items = session.scalars(select(RetrievalEvalItem).where(RetrievalEvalItem.dataset_id == dataset.id)).all()
    spans_by_item_id = _load_spans_by_item_id(session=session, item_ids=[item.id for item in items])
    from app.evaluation.retrieval.run_service import run_evaluation_dataset

    return run_evaluation_dataset(
        session=session,
        principal=principal,
        settings=settings,
        dataset=dataset,
        items=items,
        spans_by_item_id=spans_by_item_id,
        top_k=top_k,
        evaluation_profile=evaluation_profile,
    )


def get_evaluation_run_report(
    *,
    session: Session,
    principal: CurrentPrincipal,
    run_id: str,
) -> EvaluationRunReportResponse:
    """讀取既有 benchmark run 報表。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `run_id`：目標 run。

    回傳：
    - `EvaluationRunReportResponse`：完整 run 報表。
    """

    run, dataset = _get_authorized_run(session=session, principal=principal, run_id=run_id)
    artifact = session.scalars(
        select(RetrievalEvalRunArtifact).where(RetrievalEvalRunArtifact.run_id == run.id)
    ).one_or_none()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation run。")
    payload = json.loads(artifact.report_json)
    baseline_compare = json.loads(artifact.baseline_compare_json) if artifact.baseline_compare_json else None
    return EvaluationRunReportResponse(
        run=build_run_summary(run),
        dataset=build_dataset_summary(session=session, dataset=dataset),
        summary_metrics=payload["summary_metrics"],
        breakdowns=payload["breakdowns"],
        per_query=payload["per_query"],
        baseline_compare=baseline_compare,
    )


def build_dataset_summary(*, session: Session, dataset: RetrievalEvalDataset) -> EvaluationDatasetSummary:
    """建立 dataset summary。

    參數：
    - `session`：目前資料庫 session。
    - `dataset`：ORM dataset。

    回傳：
    - `EvaluationDatasetSummary`：API summary。
    """

    item_count = session.scalar(
        select(func.count(RetrievalEvalItem.id)).where(RetrievalEvalItem.dataset_id == dataset.id)
    ) or 0
    return EvaluationDatasetSummary(
        id=dataset.id,
        area_id=dataset.area_id,
        name=dataset.name,
        query_type=dataset.query_type,
        baseline_run_id=dataset.baseline_run_id,
        created_by_sub=dataset.created_by_sub,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        item_count=int(item_count),
    )


def build_item_summary(*, item: RetrievalEvalItem, spans: list[RetrievalEvalItemSpan]) -> EvaluationItemSummary:
    """建立 item summary。

    參數：
    - `item`：ORM item。
    - `spans`：該題的 spans。

    回傳：
    - `EvaluationItemSummary`：API summary。
    """

    return EvaluationItemSummary(
        id=item.id,
        dataset_id=item.dataset_id,
        query_type=item.query_type,
        query_text=item.query_text,
        language=item.language,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        spans=[build_span_response(span) for span in spans],
    )


def build_span_response(span: RetrievalEvalItemSpan) -> EvaluationItemSpanResponse:
    """建立 span response。

    參數：
    - `span`：ORM span。

    回傳：
    - `EvaluationItemSpanResponse`：API span response。
    """

    return EvaluationItemSpanResponse.model_validate(span)


def build_run_summary(run: RetrievalEvalRun) -> EvaluationRunSummary:
    """建立 run summary。

    參數：
    - `run`：ORM run。

    回傳：
    - `EvaluationRunSummary`：API run summary。
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


def _get_authorized_dataset(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
) -> RetrievalEvalDataset:
    """讀取並驗證 dataset 存取權。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。

    回傳：
    - `RetrievalEvalDataset`：已授權 dataset。
    """

    dataset = session.get(RetrievalEvalDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation dataset。")
    try:
        require_minimum_area_role(session=session, principal=principal, area_id=dataset.area_id, minimum_role=Role.maintainer)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation dataset。") from exc
        raise
    return dataset


def _get_authorized_item(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
) -> tuple[RetrievalEvalItem, RetrievalEvalDataset]:
    """讀取並驗證題目存取權。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。

    回傳：
    - `tuple[RetrievalEvalItem, RetrievalEvalDataset]`：已授權題目與 dataset。
    """

    item = session.get(RetrievalEvalItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation item。")
    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=item.dataset_id)
    return item, dataset


def _get_authorized_run(
    *,
    session: Session,
    principal: CurrentPrincipal,
    run_id: str,
) -> tuple[RetrievalEvalRun, RetrievalEvalDataset]:
    """讀取並驗證 run 存取權。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `run_id`：目標 run。

    回傳：
    - `tuple[RetrievalEvalRun, RetrievalEvalDataset]`：已授權 run 與 dataset。
    """

    run = session.get(RetrievalEvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation run。")
    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=run.dataset_id)
    return run, dataset


def _load_spans_by_item_id(*, session: Session, item_ids: list[str]) -> dict[str, list[RetrievalEvalItemSpan]]:
    """批次載入題目的 spans。

    參數：
    - `session`：目前資料庫 session。
    - `item_ids`：題目 id 列表。

    回傳：
    - `dict[str, list[RetrievalEvalItemSpan]]`：依 item_id 分組的 spans。
    """

    if not item_ids:
        return {}
    spans = session.scalars(
        select(RetrievalEvalItemSpan)
        .where(RetrievalEvalItemSpan.item_id.in_(item_ids))
        .order_by(RetrievalEvalItemSpan.created_at.asc())
    ).all()
    grouped: dict[str, list[RetrievalEvalItemSpan]] = defaultdict(list)
    for span in spans:
        grouped[span.item_id].append(span)
    return grouped


def _get_authorized_ready_document(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    document_id: str,
) -> Document:
    """讀取已授權且 ready 的文件。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。
    - `document_id`：文件 id。

    回傳：
    - `Document`：已授權且 ready 文件。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    document = session.get(Document, document_id)
    if document is None or document.area_id != area_id or document.status != DocumentStatus.ready:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的文件。")
    return document


def _search_document_hits(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    query: str,
) -> list[EvaluationDocumentSearchHit]:
    """在 ready 文件內做簡化全文搜尋。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。
    - `query`：搜尋關鍵字。

    回傳：
    - `list[EvaluationDocumentSearchHit]`：搜尋命中結果。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    rows = session.execute(
        select(DocumentChunk, Document.file_name)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.child,
            DocumentChunk.content.ilike(f"%{query}%"),
        )
        .order_by(Document.file_name.asc(), DocumentChunk.position.asc())
        .limit(10)
    ).all()
    return [
        EvaluationDocumentSearchHit(
            document_id=row[0].document_id,
            document_name=row[1],
            chunk_id=row[0].id,
            heading=row[0].heading,
            start_offset=row[0].start_offset,
            end_offset=row[0].end_offset,
            excerpt=row[0].content[:240],
        )
        for row in rows
    ]
