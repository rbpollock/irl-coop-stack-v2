"""Retrieval evaluation dataset、review 與 run 路由。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings, get_app_settings
from app.db.session import get_database_session
from app.schemas.evaluation import (
    CreateEvaluationDatasetRequest,
    CreateEvaluationItemRequest,
    EvaluationCandidatePreviewResponse,
    EvaluationDatasetDetailResponse,
    EvaluationDatasetListResponse,
    EvaluationDatasetSummary,
    EvaluationItemSummary,
    EvaluationPreviewDebugRequest,
    EvaluationRunReportResponse,
    MarkEvaluationSpanRequest,
    RunEvaluationDatasetRequest,
)
from app.evaluation.retrieval.datasets import (
    add_item_span,
    create_area_evaluation_dataset,
    create_evaluation_item,
    create_evaluation_run,
    delete_evaluation_dataset,
    delete_evaluation_item,
    get_evaluation_dataset_detail,
    get_evaluation_run_report,
    list_area_evaluation_datasets,
    mark_item_retrieval_miss,
    preview_evaluation_candidates,
)


router = APIRouter(tags=["evaluation"])


@router.get("/areas/{area_id}/evaluation/datasets", response_model=EvaluationDatasetListResponse)
def list_evaluation_datasets_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EvaluationDatasetListResponse:
    """列出指定 area 的 evaluation datasets。

    參數：
    - `area_id`：目標 area。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationDatasetListResponse`：dataset 清單。
    """

    return list_area_evaluation_datasets(session=session, principal=principal, area_id=area_id)


@router.post("/areas/{area_id}/evaluation/datasets", response_model=EvaluationDatasetSummary, status_code=status.HTTP_201_CREATED)
def create_evaluation_dataset_route(
    area_id: str,
    payload: CreateEvaluationDatasetRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EvaluationDatasetSummary:
    """建立新的 evaluation dataset。

    參數：
    - `area_id`：目標 area。
    - `payload`：建立 payload。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationDatasetSummary`：新 dataset。
    """

    return create_area_evaluation_dataset(
        session=session,
        principal=principal,
        area_id=area_id,
        name=payload.name,
        query_type=payload.query_type,
    )


@router.get("/evaluation/datasets/{dataset_id}", response_model=EvaluationDatasetDetailResponse)
def read_evaluation_dataset_route(
    dataset_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EvaluationDatasetDetailResponse:
    """讀取單一 evaluation dataset 詳細資料。

    參數：
    - `dataset_id`：目標 dataset。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationDatasetDetailResponse`：dataset 詳細資料。
    """

    return get_evaluation_dataset_detail(session=session, principal=principal, dataset_id=dataset_id)


@router.delete("/evaluation/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evaluation_dataset_route(
    dataset_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> None:
    """刪除單一 evaluation dataset。

    參數：
    - `dataset_id`：目標 dataset。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `None`：刪除成功時不回傳內容。
    """

    delete_evaluation_dataset(session=session, principal=principal, dataset_id=dataset_id)


@router.post("/evaluation/datasets/{dataset_id}/items", response_model=EvaluationItemSummary, status_code=status.HTTP_201_CREATED)
def create_evaluation_item_route(
    dataset_id: str,
    payload: CreateEvaluationItemRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EvaluationItemSummary:
    """建立 evaluation item。

    參數：
    - `dataset_id`：目標 dataset。
    - `payload`：建立 payload。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationItemSummary`：新題目。
    """

    return create_evaluation_item(session=session, principal=principal, dataset_id=dataset_id, payload=payload)


@router.delete("/evaluation/datasets/{dataset_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evaluation_item_route(
    dataset_id: str,
    item_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> None:
    """刪除 evaluation item。

    參數：
    - `dataset_id`：目標 dataset；僅作為路徑穩定性用途。
    - `item_id`：目標題目。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `None`：刪除成功時不回傳內容。
    """

    _ = dataset_id
    delete_evaluation_item(session=session, principal=principal, item_id=item_id)


@router.post("/evaluation/datasets/{dataset_id}/items/{item_id}/candidate-preview", response_model=EvaluationCandidatePreviewResponse)
def preview_evaluation_candidates_route(
    dataset_id: str,
    item_id: str,
    payload: EvaluationPreviewDebugRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    settings: AppSettings = Depends(get_app_settings),
    session: Session = Depends(get_database_session),
) -> EvaluationCandidatePreviewResponse:
    """讀取單題 candidate preview。

    參數：
    - `dataset_id`：目標 dataset；僅作為路徑穩定性用途。
    - `item_id`：目標題目。
    - `payload`：preview 臨時調參 payload。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationCandidatePreviewResponse`：三階段預覽。
    """

    _ = dataset_id
    return preview_evaluation_candidates(
        session=session,
        principal=principal,
        settings=settings,
        item_id=item_id,
        payload=payload,
    )


@router.post("/evaluation/datasets/{dataset_id}/items/{item_id}/spans", response_model=EvaluationItemSummary)
def add_evaluation_span_route(
    dataset_id: str,
    item_id: str,
    payload: MarkEvaluationSpanRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EvaluationItemSummary:
    """新增 gold source span。

    參數：
    - `dataset_id`：目標 dataset；僅作為路徑穩定性用途。
    - `item_id`：目標題目。
    - `payload`：span payload。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationItemSummary`：更新後題目。
    """

    _ = dataset_id
    return add_item_span(
        session=session,
        principal=principal,
        item_id=item_id,
        document_id=str(payload.document_id),
        start_offset=payload.start_offset,
        end_offset=payload.end_offset,
        relevance_grade=payload.relevance_grade,
    )


@router.post("/evaluation/datasets/{dataset_id}/items/{item_id}/mark-miss", response_model=EvaluationItemSummary)
def mark_evaluation_miss_route(
    dataset_id: str,
    item_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EvaluationItemSummary:
    """將題目標記為 retrieval miss。

    參數：
    - `dataset_id`：目標 dataset；僅作為路徑穩定性用途。
    - `item_id`：目標題目。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationItemSummary`：更新後題目。
    """

    _ = dataset_id
    return mark_item_retrieval_miss(session=session, principal=principal, item_id=item_id)


@router.post("/evaluation/datasets/{dataset_id}/runs", response_model=EvaluationRunReportResponse, status_code=status.HTTP_201_CREATED)
def run_evaluation_dataset_route(
    dataset_id: str,
    payload: RunEvaluationDatasetRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    settings: AppSettings = Depends(get_app_settings),
    session: Session = Depends(get_database_session),
) -> EvaluationRunReportResponse:
    """執行 dataset benchmark run。

    參數：
    - `dataset_id`：目標 dataset。
    - `payload`：run payload。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationRunReportResponse`：完整 run 報表。
    """

    return create_evaluation_run(
        session=session,
        principal=principal,
        settings=settings,
        dataset_id=dataset_id,
        top_k=payload.top_k,
        evaluation_profile=payload.evaluation_profile,
    )


@router.get("/evaluation/runs/{run_id}", response_model=EvaluationRunReportResponse)
def read_evaluation_run_route(
    run_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> EvaluationRunReportResponse:
    """讀取既有 benchmark run。

    參數：
    - `run_id`：目標 run。
    - `principal`：目前已驗證使用者。
    - `session`：目前資料庫 session。

    回傳：
    - `EvaluationRunReportResponse`：run 報表。
    """

    return get_evaluation_run_report(session=session, principal=principal, run_id=run_id)
