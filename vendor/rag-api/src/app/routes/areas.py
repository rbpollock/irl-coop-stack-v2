"""Knowledge Area 與 access management 路由。"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_bearer_token, get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.core.settings import get_app_settings
from app.db.session import get_database_session
from app.schemas.chat_sessions import ChatSessionListResponse, ChatSessionSummaryResponse, RegisterChatSessionRequest, UpdateChatSessionRequest
from app.schemas.access import AreaAccessResponse
from app.schemas.areas import (
    AreaAccessManagementResponse,
    AreaListResponse,
    AreaSummaryResponse,
    CreateAreaRequest,
    ReplaceAreaAccessRequest,
    UpdateAreaRequest,
)
from app.services.chat_sessions import delete_area_chat_session, list_area_chat_sessions, register_area_chat_session, update_area_chat_session
from app.services.access import require_area_access
from app.services.areas import (
    create_area,
    delete_area,
    get_area_access_management,
    get_area_detail,
    list_accessible_areas,
    replace_area_access_management,
    update_area,
)
from app.services.storage import ObjectStorage, StorageError, build_object_storage


# Area 相關最小授權路由集合。
router = APIRouter(prefix="/areas", tags=["areas"])


def get_object_storage(settings=Depends(get_app_settings)) -> ObjectStorage:
    """建立目前 request 使用的 object storage。

    參數：
    - `settings`：目前應用程式的儲存相關設定。

    回傳：
    - `ObjectStorage`：符合目前執行模式的物件儲存實作。
    """

    return build_object_storage(settings=settings)


@router.post("", response_model=AreaSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_area_route(
    payload: CreateAreaRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaSummaryResponse:
    """建立新的 Knowledge Area。

    參數：
    - `payload`：建立 area 所需的名稱與說明。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `AreaSummaryResponse`：剛建立 area 的摘要資料。
    """

    return create_area(
        session=session,
        principal=principal,
        name=payload.name,
        description=payload.description,
    )


@router.get("", response_model=AreaListResponse)
def list_areas_route(
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaListResponse:
    """列出目前使用者可存取的 areas。

    參數：
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `AreaListResponse`：目前使用者可存取的 area 清單。
    """

    return AreaListResponse(items=list_accessible_areas(session=session, principal=principal))


@router.get("/{area_id}", response_model=AreaSummaryResponse)
def read_area_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaSummaryResponse:
    """讀取單一 area 詳細資料。

    參數：
    - `area_id`：要查詢的 area 識別碼。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `AreaSummaryResponse`：指定 area 的摘要資料。
    """

    return get_area_detail(session=session, principal=principal, area_id=area_id)


@router.put("/{area_id}", response_model=AreaSummaryResponse)
def update_area_route(
    area_id: str,
    payload: UpdateAreaRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaSummaryResponse:
    """更新單一 area 的名稱與說明。

    參數：
    - `area_id`：要更新的 area 識別碼。
    - `payload`：新的 area 名稱與說明。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `AreaSummaryResponse`：更新後的 area 摘要資料。
    """

    return update_area(
        session=session,
        principal=principal,
        area_id=area_id,
        name=payload.name,
        description=payload.description,
    )


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_area_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    storage: ObjectStorage = Depends(get_object_storage),
    session: Session = Depends(get_database_session),
) -> Response:
    """刪除單一 area 與其所有關聯資料。

    參數：
    - `area_id`：要刪除的 area 識別碼。
    - `principal`：目前已驗證使用者。
    - `storage`：原始檔物件儲存介面。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `Response`：成功時回傳無內容回應。
    """

    try:
        delete_area(session=session, principal=principal, storage=storage, area_id=area_id)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刪除 area 時無法清理物件儲存內容。",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{area_id}/access-check", response_model=AreaAccessResponse)
def read_area_access_check(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaAccessResponse:
    """檢查目前使用者是否對指定 area 擁有有效角色。

    參數：
    - `area_id`：要檢查權限的 area 識別碼。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `AreaAccessResponse`：指定 area 的 effective role 檢查結果。
    """

    effective_role = require_area_access(session=session, principal=principal, area_id=area_id)
    return AreaAccessResponse(area_id=area_id, effective_role=effective_role)


@router.get("/{area_id}/access", response_model=AreaAccessManagementResponse)
def read_area_access_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaAccessManagementResponse:
    """讀取指定 area 的 access 管理資料。

    參數：
    - `area_id`：要查詢 access 管理資料的 area 識別碼。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `AreaAccessManagementResponse`：指定 area 的 access 管理資料。
    """

    return get_area_access_management(session=session, principal=principal, area_id=area_id)


@router.put("/{area_id}/access", response_model=AreaAccessManagementResponse)
def replace_area_access_route(
    area_id: str,
    payload: ReplaceAreaAccessRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaAccessManagementResponse:
    """整體替換指定 area 的 access 規則。

    參數：
    - `area_id`：要更新 access 規則的 area 識別碼。
    - `payload`：新的 access 規則內容。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `AreaAccessManagementResponse`：更新後的 access 管理資料。
    """

    return replace_area_access_management(
        session=session,
        principal=principal,
        area_id=area_id,
        payload=payload,
    )


@router.get("/{area_id}/chat-sessions", response_model=ChatSessionListResponse)
def list_area_chat_sessions_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> ChatSessionListResponse:
    """列出指定 area 且屬於目前使用者的 chat sessions。

    參數：
    - `area_id`：目標 area 識別碼。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `ChatSessionListResponse`：依最近使用時間排序的 chat sessions。
    """

    return ChatSessionListResponse(items=list_area_chat_sessions(session=session, principal=principal, area_id=area_id))


@router.post("/{area_id}/chat-sessions", response_model=ChatSessionSummaryResponse, status_code=status.HTTP_201_CREATED)
def register_area_chat_session_route(
    area_id: str,
    payload: RegisterChatSessionRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    bearer_token: str = Depends(get_bearer_token),
    settings=Depends(get_app_settings),
    session: Session = Depends(get_database_session),
) -> ChatSessionSummaryResponse:
    """註冊既有 LangGraph thread 為正式 chat session metadata。

    參數：
    - `area_id`：目標 area 識別碼。
    - `payload`：要註冊的 thread 與可選 title。
    - `principal`：目前已驗證使用者。
    - `bearer_token`：目前 request 的 Bearer token。
    - `settings`：目前 API 設定。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `ChatSessionSummaryResponse`：建立或既有的 chat session 摘要。
    """

    return register_area_chat_session(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        bearer_token=bearer_token,
        thread_id=payload.thread_id,
        title=payload.title,
    )


@router.patch("/{area_id}/chat-sessions/{thread_id}", response_model=ChatSessionSummaryResponse)
def update_area_chat_session_route(
    area_id: str,
    thread_id: str,
    payload: UpdateChatSessionRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    bearer_token: str = Depends(get_bearer_token),
    settings=Depends(get_app_settings),
    session: Session = Depends(get_database_session),
) -> ChatSessionSummaryResponse:
    """更新既有 chat session metadata。

    參數：
    - `area_id`：目標 area 識別碼。
    - `thread_id`：要更新的 LangGraph thread id。
    - `payload`：可選的新 title。
    - `principal`：目前已驗證使用者。
    - `bearer_token`：目前 request 的 Bearer token。
    - `settings`：目前 API 設定。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `ChatSessionSummaryResponse`：更新後的 chat session 摘要。
    """

    return update_area_chat_session(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        bearer_token=bearer_token,
        thread_id=thread_id,
        title=payload.title,
    )


@router.delete("/{area_id}/chat-sessions/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_area_chat_session_route(
    area_id: str,
    thread_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> Response:
    """刪除既有 chat session metadata。"""

    delete_area_chat_session(
        session=session,
        principal=principal,
        area_id=area_id,
        thread_id=thread_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
