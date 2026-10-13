"""JWT 驗證與 principal 解析元件。"""

from dataclasses import dataclass
from threading import Lock
from typing import NotRequired, TypedDict

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from app.core.settings import AppSettings


# 測試模式 token 的固定前綴，用來避免誤把一般字串當成 token。
TEST_TOKEN_PREFIX = "test::"


class InvalidTokenError(ValueError):
    """代表 token 無法通過驗證或缺少必要 claims。"""


class AuthServiceUnavailableError(RuntimeError):
    """代表外部驗證服務暫時不可用，無法完成 token 驗證。"""


@dataclass(frozen=True, slots=True)
class CurrentPrincipal:
    """已驗證使用者的最小 auth context。"""

    sub: str
    groups: tuple[str, ...]
    authenticated: bool = True
    name: str | None = None
    preferred_username: str | None = None


class JwtClaimsPayload(TypedDict, total=False):
    """JWT 驗證完成後使用的最小 claims payload。"""

    # 使用者 sub。
    sub: str
    # 群組列表；實際 claim key 由設定決定。
    groups: list[str]
    # 顯示名稱。
    name: str | None
    # 偏好使用者名稱。
    preferred_username: str | None
    # 允許保留其他 Keycloak claims，而不要求全部顯式列出。
    aud: NotRequired[object]


class TokenVerifier:
    """Token verifier 介面。"""

    def verify(self, token: str) -> CurrentPrincipal:
        """驗證 token 並回傳 principal。

        參數：
        - `token`：待驗證的 access token。

        回傳：
        - `CurrentPrincipal`：從 token 解析出的已驗證使用者資訊。
        """

        raise NotImplementedError


class KeycloakJwtVerifier(TokenVerifier):
    """使用 Keycloak JWKS 驗證 access token 的 verifier。"""

    def __init__(self, settings: AppSettings) -> None:
        """初始化 Keycloak JWT verifier。

        參數：
        - `settings`：包含 JWKS URL、issuer 與 groups claim 名稱的應用程式設定。

        回傳：
        - `None`：此建構子只負責初始化 verifier 狀態。
        """

        self._groups_claim = settings.keycloak_groups_claim
        self._sources: list[dict[str, str]] = [
            {"issuer": settings.keycloak_issuer, "jwks_url": settings.keycloak_jwks_url},
        ]
        if settings.coop_jwt_issuer:
            self._sources.append(
                {"issuer": settings.coop_jwt_issuer, "jwks_url": settings.coop_jwt_jwks_url},
            )
        self._jwks_client_lock = Lock()
        self._clients = {s["jwks_url"]: self._build_jwks_client(s["jwks_url"]) for s in self._sources}

    def _build_jwks_client(self, jwks_url: str) -> PyJWKClient:
        """建立新的 JWKS client。

        參數：
        - 無

        回傳：
        - `PyJWKClient`：用來抓取與快取 Keycloak 簽章金鑰的 client。
        """

        return PyJWKClient(jwks_url)

    def _refresh_jwks_client(self, jwks_url: str) -> PyJWKClient:
        """在 JWKS 連線異常時重建 client。

        參數：
        - 無

        回傳：
        - `PyJWKClient`：重建後的 JWKS client。
        """

        with self._jwks_client_lock:
            self._clients[jwks_url] = self._build_jwks_client(jwks_url)
            return self._clients[jwks_url]

    def _get_signing_key(self, token: str, jwks_url: str):
        """取得 token 對應的簽章金鑰，必要時重建 JWKS client 後重試一次。

        參數：
        - `token`：待驗證的 Keycloak access token。

        回傳：
        - `PyJWK`：可供 JWT 驗證使用的簽章金鑰。

        風險：
        - 若 Keycloak JWKS endpoint 暫時不可用，這裡只會重試一次，避免在驗證路徑無限阻塞。
        """

        client = self._clients[jwks_url]
        last_error: PyJWKClientConnectionError | None = None
        for attempt in range(2):
            try:
                return client.get_signing_key_from_jwt(token)
            except PyJWKClientConnectionError as exc:
                last_error = exc
                if attempt == 0:
                    client = self._refresh_jwks_client(jwks_url)
                    continue
                raise AuthServiceUnavailableError("目前無法連線到 Keycloak 驗證服務，請稍後再試。") from exc

        raise AuthServiceUnavailableError("目前無法連線到 Keycloak 驗證服務，請稍後再試。") from last_error

    def verify(self, token: str) -> CurrentPrincipal:
        """驗證 Keycloak JWT 並解析 principal。

        參數：
        - `token`：待驗證的 Keycloak access token。

        回傳：
        - `CurrentPrincipal`：由合法 JWT 解析出的 principal。

        前置條件：
        - token 必須由設定中的 Keycloak issuer 簽發。

        風險：
        - 目前未驗證 audience，因為 API client 尚未在本專案固定；後續若引入專用 client，需同步收緊。
        """

        for source in self._sources:
            try:
                signing_key = self._get_signing_key(token, source["jwks_url"])
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "RS384", "RS512"],
                    issuer=source["issuer"],
                    options={"verify_aud": False},
                )
                return _build_principal_from_payload(payload=payload, groups_claim=self._groups_claim)
            except AuthServiceUnavailableError:
                raise
            except Exception:
                # wrong issuer / kid / claims — try the next trusted source
                continue
        raise InvalidTokenError("Token 驗證失敗。")


class TestModeTokenVerifier(TokenVerifier):
    """本機測試模式使用的 verifier。

    token 格式：
    - `test::<sub>::<group1,group2>`
    - groups 可省略，表示空集合
    """

    def __init__(self, groups_claim: str) -> None:
        """初始化測試模式 verifier。

        參數：
        - `groups_claim`：測試 token 中用來對應群組列表的 claim 名稱。

        回傳：
        - `None`：此建構子只負責初始化 verifier 狀態。
        """

        self._groups_claim = groups_claim

    def verify(self, token: str) -> CurrentPrincipal:
        """解析測試模式 token。

        參數：
        - `token`：符合 `test::<sub>::<groups>` 格式的測試 token。

        回傳：
        - `CurrentPrincipal`：由測試 token 解析出的 principal。
        """

        if not token.startswith(TEST_TOKEN_PREFIX):
            raise InvalidTokenError("測試模式 token 前綴不正確。")
        try:
            _, sub, raw_groups = token.split("::", maxsplit=2)
        except ValueError as exc:
            raise InvalidTokenError("測試模式 token 格式不正確。") from exc
        payload: JwtClaimsPayload = {
            "sub": sub,
            self._groups_claim: [group for group in raw_groups.split(",") if group],
        }
        return _build_principal_from_payload(payload=payload, groups_claim=self._groups_claim)


def _build_principal_from_payload(payload: JwtClaimsPayload, groups_claim: str) -> CurrentPrincipal:
    """從已驗證 payload 建立 principal。

    參數：
    - `payload`：已完成驗證的 JWT payload。
    - `groups_claim`：應從 payload 讀取群組列表的 claim 名稱。

    回傳：
    - `CurrentPrincipal`：由 payload 建立出的 principal。
    """

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError("Token 缺少合法的 sub claim。")

    raw_groups = payload.get(groups_claim, [])
    if raw_groups is None:
        raw_groups = []
    if not isinstance(raw_groups, list) or any(not isinstance(item, str) for item in raw_groups):
        raise InvalidTokenError("Token 的 groups claim 格式不正確。")

    name = payload.get("name")
    preferred_username = payload.get("preferred_username")

    return CurrentPrincipal(
        sub=subject,
        groups=tuple(raw_groups),
        name=name if isinstance(name, str) else None,
        preferred_username=preferred_username if isinstance(preferred_username, str) else None,
    )


def build_token_verifier(settings: AppSettings) -> TokenVerifier:
    """根據設定建立 token verifier。

    參數：
    - `settings`：包含 auth mode、issuer 與 groups claim 設定的應用程式設定。

    回傳：
    - `TokenVerifier`：符合目前執行模式的 token 驗證器。
    """

    if settings.auth_test_mode:
        return TestModeTokenVerifier(groups_claim=settings.keycloak_groups_claim)
    return KeycloakJwtVerifier(settings=settings)
