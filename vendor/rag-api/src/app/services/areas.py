"""Knowledge Area CRUD 與 access management service。"""

from collections.abc import Iterable
from pathlib import PurePosixPath

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.db.models import (
    Area,
    AreaChatSession,
    AreaGroupRole,
    AreaUserRole,
    AreaVisibility,
    Document,
    DocumentChunk,
    IngestJob,
    Role,
)
from app.schemas.areas import (
    AccessGroupEntry,
    AccessUserEntry,
    AreaAccessManagementResponse,
    AreaSummaryResponse,
    ReplaceAreaAccessRequest,
)
from app.services.access import ROLE_PRIORITY, require_area_access, require_area_admin
from app.services.directory import get_sub_by_username, get_usernames_by_subs
from app.services.storage import ObjectStorage


# parse artifact 儲存目錄名稱。
PARSE_ARTIFACTS_DIRECTORY = "artifacts"


def create_area(
    session: Session,
    principal: CurrentPrincipal,
    *,
    name: str,
    description: str | None,
) -> AreaSummaryResponse:
    """建立 area，並讓建立者自動成為 admin。

    參數：
    - `session`：用來建立 area 與角色映射的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `name`：新 area 的名稱。
    - `description`：新 area 的補充說明。

    回傳：
    - `AreaSummaryResponse`：剛建立 area 的摘要資料。
    """

    area = Area(name=name.strip(), description=_normalize_optional_text(description))
    session.add(area)
    session.flush()
    session.add(AreaUserRole(area_id=area.id, user_sub=principal.sub, role=Role.admin))
    session.commit()
    session.refresh(area)
    return _build_area_summary(area=area, effective_role=Role.admin)


def list_accessible_areas(session: Session, principal: CurrentPrincipal) -> list[AreaSummaryResponse]:
    """列出目前使用者可存取的 areas。

    參數：
    - `session`：用來查詢 area 與角色映射的資料庫 session。
    - `principal`：目前已驗證使用者。

    回傳：
    - `list[AreaSummaryResponse]`：目前使用者可存取的 area 清單。
    """

    direct_rows = session.execute(
        select(Area, AreaUserRole.role).join(AreaUserRole, AreaUserRole.area_id == Area.id).where(
            AreaUserRole.user_sub == principal.sub
        )
    ).all()
    group_rows = []
    if principal.groups:
        group_rows = session.execute(
            select(Area, AreaGroupRole.role).join(AreaGroupRole, AreaGroupRole.area_id == Area.id).where(
                AreaGroupRole.group_path.in_(principal.groups)
            )
        ).all()
    public_areas = session.scalars(select(Area).where(Area.visibility == AreaVisibility.public)).all()
    public_rows = [(area, Role.reader) for area in public_areas]

    return _merge_area_rows([*direct_rows, *group_rows, *public_rows])


def get_area_detail(session: Session, principal: CurrentPrincipal, area_id: str) -> AreaSummaryResponse:
    """取得單一 area 詳細資料。

    參數：
    - `session`：用來查詢 area 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要讀取的 area 識別碼。

    回傳：
    - `AreaSummaryResponse`：指定 area 的摘要資料。
    """

    effective_role = require_area_access(session=session, principal=principal, area_id=area_id)
    area = session.get(Area, area_id)
    if area is None:
        raise _build_area_not_found_error()
    return _build_area_summary(area=area, effective_role=effective_role)


def get_area_access_management(
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
) -> AreaAccessManagementResponse:
    """讀取指定 area 的 access 規則。

    參數：
    - `session`：用來查詢 access 規則的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要讀取 access 規則的 area 識別碼。

    回傳：
    - `AreaAccessManagementResponse`：指定 area 的 access 管理資料。
    """

    require_area_admin(session=session, principal=principal, area_id=area_id)
    return _load_area_access_management(session=session, area_id=area_id)


def update_area(
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    *,
    name: str,
    description: str | None,
) -> AreaSummaryResponse:
    """更新指定 area 的名稱與說明。

    參數：
    - `session`：用來更新 area 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要更新的 area 識別碼。
    - `name`：更新後的 area 名稱。
    - `description`：更新後的 area 說明。

    回傳：
    - `AreaSummaryResponse`：更新後的 area 摘要資料。
    """

    require_area_admin(session=session, principal=principal, area_id=area_id)
    area = session.get(Area, area_id)
    if area is None:
        raise _build_area_not_found_error()

    area.name = name.strip()
    area.description = _normalize_optional_text(description)
    session.commit()
    session.refresh(area)
    return _build_area_summary(area=area, effective_role=Role.admin)


def delete_area(
    session: Session,
    principal: CurrentPrincipal,
    storage: ObjectStorage,
    *,
    area_id: str,
) -> None:
    """刪除指定 area 與其關聯資料，並先清理 storage 內容。

    參數：
    - `session`：用來刪除 area 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `storage`：原始檔物件儲存介面。
    - `area_id`：要刪除的 area 識別碼。

    回傳：
    - `None`：此函式只負責完成刪除流程。

    前置條件：
    - 僅 area `admin` 可刪除 area。
    - 若 storage 清理失敗，必須中止刪除，避免資料庫與物件儲存狀態分裂。
    """

    require_area_admin(session=session, principal=principal, area_id=area_id)
    area = session.get(Area, area_id)
    if area is None:
        raise _build_area_not_found_error()

    documents = session.scalars(select(Document).where(Document.area_id == area_id)).all()
    for document in documents:
        storage.delete_prefix(prefix=_build_parse_artifact_prefix(storage_key=document.storage_key))
        storage.delete_object(object_key=document.storage_key)

    document_ids = [document.id for document in documents]
    if document_ids:
        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids)))
        session.execute(delete(IngestJob).where(IngestJob.document_id.in_(document_ids)))
        session.execute(delete(Document).where(Document.id.in_(document_ids)))
    session.execute(delete(AreaChatSession).where(AreaChatSession.area_id == area_id))
    session.execute(delete(AreaUserRole).where(AreaUserRole.area_id == area_id))
    session.execute(delete(AreaGroupRole).where(AreaGroupRole.area_id == area_id))
    session.delete(area)
    session.commit()


def replace_area_access_management(
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    payload: ReplaceAreaAccessRequest,
) -> AreaAccessManagementResponse:
    """整體替換指定 area 的 access 規則。

    參數：
    - `session`：用來更新 access 規則的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要更新 access 規則的 area 識別碼。
    - `payload`：新的 access 規則內容。

    回傳：
    - `AreaAccessManagementResponse`：更新後的 access 管理資料。
    """

    require_area_admin(session=session, principal=principal, area_id=area_id)

    session.execute(delete(AreaUserRole).where(AreaUserRole.area_id == area_id))
    session.execute(delete(AreaGroupRole).where(AreaGroupRole.area_id == area_id))

    user_roles = []
    for entry in _deduplicate_user_entries(payload.users):
        username = entry.username.strip()
        sub = get_sub_by_username(username)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"找不到使用者: {username}",
            )
        user_roles.append(AreaUserRole(area_id=area_id, user_sub=sub, role=entry.role))

    group_roles = [
        AreaGroupRole(area_id=area_id, group_path=entry.group_path.strip(), role=entry.role)
        for entry in _deduplicate_group_entries(payload.groups)
    ]
    session.add_all([*user_roles, *group_roles])
    session.commit()
    return _load_area_access_management(session=session, area_id=area_id)


def _merge_area_rows(rows: Iterable[tuple[Area, Role]]) -> list[AreaSummaryResponse]:
    """將 direct role 與 group role 查詢結果合併成唯一 area 清單。

    參數：
    - `rows`：包含 area 與角色的查詢結果集合。

    回傳：
    - `list[AreaSummaryResponse]`：去重、取最大角色後的 area 清單。
    """

    area_map: dict[str, tuple[Area, Role]] = {}
    for area, role in rows:
        current = area_map.get(area.id)
        if current is None or ROLE_PRIORITY[role] > ROLE_PRIORITY[current[1]]:
            area_map[area.id] = (area, role)

    merged = [_build_area_summary(area=area, effective_role=role) for area, role in area_map.values()]
    return sorted(merged, key=lambda item: item.created_at, reverse=True)


def _build_area_summary(area: Area, effective_role: Role) -> AreaSummaryResponse:
    """將 ORM area model 轉成 API schema。

    參數：
    - `area`：ORM area model。
    - `effective_role`：目前使用者在此 area 的 effective role。

    回傳：
    - `AreaSummaryResponse`：可供 API 回傳的 area 摘要資料。
    """

    return AreaSummaryResponse(
        id=area.id,
        name=area.name,
        description=area.description,
        effective_role=effective_role,
        created_at=area.created_at,
        updated_at=area.updated_at,
    )


def _normalize_optional_text(value: str | None) -> str | None:
    """將可選文字欄位去除前後空白，空值則轉為 None。

    參數：
    - `value`：待標準化的可選文字值。

    回傳：
    - `str | None`：去除空白後的文字；若為空值則回傳 `None`。
    """

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _build_parse_artifact_prefix(*, storage_key: str) -> str:
    """依文件 storage key 建立 parse artifact 的固定前綴路徑。

    參數：
    - `storage_key`：文件原始檔在物件儲存中的鍵值。

    回傳：
    - `str`：對應 parse artifact 的固定前綴路徑。
    """

    return str(PurePosixPath(storage_key).parent / PARSE_ARTIFACTS_DIRECTORY)


def _deduplicate_user_entries(entries: list[AccessUserEntry]) -> Iterable[AccessUserEntry]:
    """以最後一次輸入為準去除重複的 username。

    參數：
    - `entries`：原始 direct user role 輸入列表。

    回傳：
    - `Iterable[AccessUserEntry]`：已去除重複 username 的條目集合。
    """

    deduplicated: dict[str, AccessUserEntry] = {}
    for entry in entries:
        deduplicated[entry.username.strip()] = entry
    return deduplicated.values()


def _deduplicate_group_entries(entries: list[AccessGroupEntry]) -> Iterable[AccessGroupEntry]:
    """以最後一次輸入為準去除重複的 group_path。

    參數：
    - `entries`：原始 group role 輸入列表。

    回傳：
    - `Iterable[AccessGroupEntry]`：已去除重複 group_path 的條目集合。
    """

    deduplicated: dict[str, AccessGroupEntry] = {}
    for entry in entries:
        deduplicated[entry.group_path.strip()] = entry
    return deduplicated.values()


def _build_area_not_found_error() -> HTTPException:
    """建立與授權層一致的 area not found 例外。

    參數：
    - 無

    回傳：
    - `HTTPException`：用來隱藏 area 存在性的 404 例外。
    """

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 area。")


def _load_area_access_management(session: Session, area_id: str) -> AreaAccessManagementResponse:
    """直接依 area_id 讀取 access 規則內容。

    參數：
    - `session`：用來查詢 access 規則的資料庫 session。
    - `area_id`：要讀取 access 規則的 area 識別碼。

    回傳：
    - `AreaAccessManagementResponse`：指定 area 的 access 管理資料。
    """

    user_rows = session.scalars(
        select(AreaUserRole).where(AreaUserRole.area_id == area_id).order_by(AreaUserRole.user_sub.asc())
    ).all()
    group_rows = session.scalars(
        select(AreaGroupRole).where(AreaGroupRole.area_id == area_id).order_by(AreaGroupRole.group_path.asc())
    ).all()
    
    subs = [row.user_sub for row in user_rows]
    username_map = get_usernames_by_subs(subs)

    return AreaAccessManagementResponse(
        area_id=area_id,
        users=[
            AccessUserEntry(
                username=username_map.get(row.user_sub, row.user_sub),
                role=row.role
            )
            for row in user_rows
        ],
        groups=[AccessGroupEntry(group_path=row.group_path, role=row.role) for row in group_rows],
    )
