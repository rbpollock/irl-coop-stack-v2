"""Keycloak 目錄服務，負責查詢使用者與群組。"""

import logging
from typing import Any

from keycloak import KeycloakAdmin  # type: ignore

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_admin_client: KeycloakAdmin | None = None


def _is_auth_test_mode() -> bool:
    """判斷目前是否為 auth test mode。"""

    return get_settings().auth_test_mode


def _get_admin_client() -> KeycloakAdmin:
    """取得初始化的 KeycloakAdmin 客戶端 (Lazy initialization)。"""
    global _admin_client
    if _admin_client is None:
        settings = get_settings()
        _admin_client = KeycloakAdmin(
            server_url=settings.keycloak_url.rstrip("/") + "/",
            username=settings.keycloak_admin_user,
            password=settings.keycloak_admin_password,
            realm_name=settings.keycloak_realm,
            user_realm_name="master",
            client_id="admin-cli",
            verify=True,
        )
    return _admin_client


def search_users(query: str) -> list[dict[str, Any]]:
    """依據關鍵字搜尋使用者。若 query 為空則回傳所有使用者。

    參數：
    - `query`：要搜尋的使用者名稱或信箱關鍵字。

    回傳：
    - `list[dict]`：符合條件的使用者清單。
    """
    admin = _get_admin_client()
    try:
        search_params = {}
        if query and query.strip():
            search_params["search"] = query.strip()
        
        # KeycloakAdmin.get_users accepts search params in a 'query' dict or as direct kwargs
        users = admin.get_users(query=search_params)
        return users
    except Exception as e:
        logger.error(f"Failed to search users from Keycloak: {e}")
        return []


def search_groups(query: str) -> list[dict[str, Any]]:
    """依據關鍵字搜尋群組。若 query 為空則回傳所有群組。

    參數：
    - `query`：要搜尋的群組名稱關鍵字。

    回傳：
    - `list[dict]`：符合條件的群組清單。
    """
    admin = _get_admin_client()
    try:
        search_params = {}
        if query and query.strip():
            search_params["search"] = query.strip()
            
        # KeycloakAdmin.get_groups expects search params in a 'query' dict
        groups = admin.get_groups(query=search_params)
        return groups
    except Exception as e:
        logger.error(f"Failed to search groups from Keycloak: {e}")
        return []


def get_sub_by_username(username: str) -> str | None:
    """根據 username 取得對應的 sub (Keycloak user ID)。

    參數：
    - `username`：精確的使用者名稱。

    回傳：
    - `str | None`：若存在回傳 `sub`，否則回傳 `None`。
    """
    if not username:
        return None
    if _is_auth_test_mode():
        return username

    admin = _get_admin_client()
    try:
        # exact=True ensures exact match
        users = admin.get_users(query={"username": username, "exact": True})
        if users and len(users) > 0:
            return users[0].get("id")
    except Exception as e:
        logger.error(f"Failed to get sub for username {username}: {e}")
    return None


def get_usernames_by_subs(subs: list[str]) -> dict[str, str]:
    """批次查詢 sub 列表對應的 username。

    參數：
    - `subs`：一組 `sub` (Keycloak user ID) 的清單。

    回傳：
    - `dict[str, str]`：`sub` 到 `username` 的映射字典。若找不到對應的使用者，不會出現在字典中。
    """
    if not subs:
        return {}
    if _is_auth_test_mode():
        return {sub: sub for sub in subs}

    admin = _get_admin_client()
    mapping: dict[str, str] = {}
    
    # Keycloak doesn't have a bulk get_users_by_ids endpoint,
    # so we have to fetch them one by one if we don't fetch all users.
    # Alternatively, we could fetch users dynamically, but to avoid N+1,
    # let's just fetch them individually since the number of roles per area is usually small.
    # To optimize slightly, we skip duplicates.
    unique_subs = set(subs)
    
    for sub in unique_subs:
        try:
            user = admin.get_user(sub)
            if user and "username" in user:
                mapping[sub] = user["username"]
        except Exception as e:
            # keycloak admin raises an exception (usually 404) if user not found
            logger.warning(f"Failed to get user for sub {sub}: {e}")
            
    return mapping
