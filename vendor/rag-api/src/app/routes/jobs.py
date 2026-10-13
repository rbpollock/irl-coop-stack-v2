"""Ingest jobs 查詢路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.db.session import get_database_session
from app.schemas.documents import IngestJobSummary
from app.services.documents import get_ingest_job_detail


# Ingest jobs 相關最小授權路由集合。
router = APIRouter(prefix="/ingest-jobs", tags=["ingest-jobs"])


@router.get("/{job_id}", response_model=IngestJobSummary)
def read_ingest_job_route(
    job_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> IngestJobSummary:
    """讀取單一 ingest job 詳情。

    參數：
    - `job_id`：要查詢的 ingest job 識別碼。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `IngestJobSummary`：指定 ingest job 的摘要資料。
    """

    return get_ingest_job_detail(session=session, principal=principal, job_id=job_id)
