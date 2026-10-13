"""Directory (User/Group) 搜尋路由。"""

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.schemas.directory import GroupSearchResult, UserSearchResult
from app.services.directory import search_groups, search_users

router = APIRouter(prefix="/directory", tags=["directory"])


@router.get("/users", response_model=list[UserSearchResult])
def search_users_route(
    q: str = Query("", description="要搜尋的使用者名稱或信箱關鍵字"),
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> list[UserSearchResult]:
    """依據關鍵字搜尋系統使用者。

    參數：
    - `q`：要搜尋的關鍵字。
    - `principal`：目前已驗證使用者 (所有已登入使用者皆可查詢)。

    回傳：
    - `list[UserSearchResult]`：符合條件的使用者清單。
    """
    users = search_users(query=q)
    results = []
    for u in users:
        # keycloak get_users returns dicts, some fields may be missing
        if "username" in u:
            results.append(
                UserSearchResult(
                    username=u.get("username", ""),
                    email=u.get("email"),
                    firstName=u.get("firstName"),
                    lastName=u.get("lastName"),
                )
            )
    return results


@router.get("/groups", response_model=list[GroupSearchResult])
def search_groups_route(
    q: str = Query("", description="要搜尋的群組名稱關鍵字"),
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> list[GroupSearchResult]:
    """依據關鍵字搜尋系統群組。

    參數：
    - `q`：要搜尋的關鍵字。
    - `principal`：目前已驗證使用者 (所有已登入使用者皆可查詢)。

    回傳：
    - `list[GroupSearchResult]`：符合條件的群組清單。
    """
    groups = search_groups(query=q)
    results = []
    for g in groups:
        if "path" in g and "name" in g:
            results.append(
                GroupSearchResult(
                    path=g.get("path", ""),
                    name=g.get("name", ""),
                )
            )
    return results
