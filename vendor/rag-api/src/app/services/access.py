"""Area access 與 effective role 計算 service。"""

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.db.models import Area, AreaGroupRole, AreaUserRole, AreaVisibility, Role


# 角色強度排序，數值越大代表權限越高。
ROLE_PRIORITY = {
    Role.reader: 1,
    Role.maintainer: 2,
    Role.admin: 3,
}


def resolve_highest_role(roles: Iterable[Role]) -> Role | None:
    """從多個角色中取出權限最大的角色。

    參數：
    - `roles`：待比較的角色集合。

    回傳：
    - `Role | None`：權限最大的角色；若集合為空則回傳 `None`。
    """

    resolved_roles = list(roles)
    if not resolved_roles:
        return None
    return max(resolved_roles, key=lambda role: ROLE_PRIORITY[role])


def resolve_effective_role_for_area(
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
) -> Role | None:
    """計算使用者在指定 area 的 effective role。

    參數：
    - `session`：用來查詢 area 角色映射的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要計算 effective role 的 area 識別碼。

    回傳：
    - `Role | None`：使用者在指定 area 的最大權限；若沒有任何角色則回傳 `None`。

    前置條件：
    - `principal` 必須已完成 JWT 驗證。
    - 所有 access 資料都必須透過 SQL 查詢取得，不可先取全量再在記憶體過濾。

    風險：
    - 若將授權查詢移到 route handler 或前端，會破壞 deny-by-default 與資訊洩漏保護。
    """

    user_roles = session.scalars(
        select(AreaUserRole.role).where(AreaUserRole.area_id == area_id, AreaUserRole.user_sub == principal.sub)
    ).all()
    group_roles = session.scalars(
        select(AreaGroupRole.role).where(
            AreaGroupRole.area_id == area_id,
            AreaGroupRole.group_path.in_(principal.groups or ("__no_groups__",)),
        )
    ).all()
    effective = resolve_highest_role([*user_roles, *group_roles])
    if effective is not None:
        return effective
    # 公開 area：任何已驗證成員都取得最低的 reader 角色。
    visibility = session.scalar(select(Area.visibility).where(Area.id == area_id))
    if visibility == AreaVisibility.public:
        return Role.reader
    return None


def require_area_access(session: Session, principal: CurrentPrincipal, area_id: str) -> Role:
    """要求使用者必須對 area 具有有效角色，否則回傳不暴露存在性的 404。

    參數：
    - `session`：用來查詢 area 角色映射的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要驗證存取權的 area 識別碼。

    回傳：
    - `Role`：使用者在指定 area 的 effective role。
    """

    effective_role = resolve_effective_role_for_area(session=session, principal=principal, area_id=area_id)
    if effective_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 area。")
    return effective_role


def require_minimum_area_role(
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    minimum_role: Role,
) -> Role:
    """要求使用者在指定 area 至少具有某一層級的角色。

    參數：
    - `session`：用來查詢 area 角色映射的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要驗證存取權的 area 識別碼。
    - `minimum_role`：允許執行操作所需的最小角色。

    回傳：
    - `Role`：使用者在指定 area 的 effective role。
    """

    effective_role = require_area_access(session=session, principal=principal, area_id=area_id)
    if ROLE_PRIORITY[effective_role] < ROLE_PRIORITY[minimum_role]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="目前角色無法執行此操作。")
    return effective_role


def require_area_admin(session: Session, principal: CurrentPrincipal, area_id: str) -> Role:
    """要求使用者必須是指定 area 的 admin。

    參數：
    - `session`：用來查詢 area 角色映射的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要驗證管理權限的 area 識別碼。

    回傳：
    - `Role`：驗證成功後的 `admin` effective role。
    """

    return require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.admin)
