"""Auth dependency 與 Bearer token 解析。"""

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.verifier import AuthServiceUnavailableError, CurrentPrincipal, InvalidTokenError, TokenVerifier


# Bearer token 方案，所有受保護路由都使用同一套安全依賴。
BEARER_SCHEME = HTTPBearer(auto_error=False)


def get_token_verifier(request: Request) -> TokenVerifier:
    """從應用程式狀態取得 token verifier。

    參數：
    - `request`：目前 HTTP request；用來讀取 `app.state.token_verifier`。

    回傳：
    - `TokenVerifier`：目前應用程式使用的 token 驗證器。
    """

    return request.app.state.token_verifier


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Security(BEARER_SCHEME),
) -> str:
    """解析 Bearer token；缺漏時回傳 401。

    參數：
    - `credentials`：FastAPI security dependency 解析出的授權資訊。

    回傳：
    - `str`：去除 `Bearer` 前綴後的 token 字串。
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少有效的 Bearer token。")
    return credentials.credentials


def get_current_principal(
    token: str = Depends(get_bearer_token),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> CurrentPrincipal:
    """驗證 token 並回傳目前使用者 principal。

    參數：
    - `token`：已由 Bearer dependency 解析出的 access token。
    - `verifier`：目前應用程式使用的 token 驗證器。

    回傳：
    - `CurrentPrincipal`：已驗證使用者的最小 auth context。

    前置條件：
    - token verifier 必須能驗證來源 token，並解析出 `sub` 與 `groups`。

    風險：
    - 若 verifier 放寬驗證條件，所有受保護 route 都會受影響，因此必須集中在此處管理。
    """

    try:
        return verifier.verify(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無法驗證存取 token。") from exc
    except AuthServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def get_optional_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(BEARER_SCHEME),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> CurrentPrincipal:
    """解析 principal；缺漏 token 時回傳匿名 principal，僅能存取公開 area。

    參數：
    - `credentials`：Bearer token 憑證，可為 None 表示匿名訪客。
    - `verifier`：目前應用程式使用的 token 驗證器。

    回傳：
    - `CurrentPrincipal`：已驗證使用者的 principal，或匿名訪客的 principal。

    風險：
    - 匿名 principal 的 `sub` 固定為 "anonymous"、`groups` 為空，因此 deny-by-default
      仍成立：匿名只能透過 visibility=public 的 fallback 取得 reader 角色。
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        return CurrentPrincipal(sub="anonymous", groups=(), authenticated=False)
    try:
        return verifier.verify(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無法驗證存取 token。") from exc
    except AuthServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
