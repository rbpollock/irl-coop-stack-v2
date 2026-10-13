"""授權與 access-check API 測試。"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import jwt

from app.auth.dependencies import get_token_verifier
from app.auth.verifier import AuthServiceUnavailableError
from app.auth.verifier import CurrentPrincipal
from app.auth.verifier import InvalidTokenError
from app.auth.verifier import KeycloakJwtVerifier
from app.auth.verifier import _build_principal_from_payload
from app.chat.runtime import langgraph_auth as langgraph_auth_runtime
from app.db.models import Area, AreaGroupRole, AreaUserRole, RetrievalEvalDataset, Role
from app.services.access import resolve_effective_role_for_area, resolve_highest_role


# 測試模式使用的 Bearer token，格式由 TestModeTokenVerifier 定義。
READER_TOKEN = "Bearer test::user-reader::/group/reader"
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"
OUTSIDER_TOKEN = "Bearer test::user-outsider::/group/outsider"


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def test_resolve_highest_role_prefers_stronger_role() -> None:
    """應回傳權限最高的角色。"""

    assert resolve_highest_role([Role.reader, Role.admin, Role.maintainer]) == Role.admin


def test_resolve_highest_role_returns_none_when_empty() -> None:
    """沒有角色時應回傳 None。"""

    assert resolve_highest_role([]) is None


def test_effective_role_uses_direct_role(db_session) -> None:
    """只有 direct role 時應正確回傳。"""

    area = Area(id=_uuid(), name="Direct Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-direct", role=Role.maintainer))
    db_session.commit()

    principal = CurrentPrincipal(sub="user-direct", groups=tuple())
    assert resolve_effective_role_for_area(db_session, principal, area.id) == Role.maintainer


def test_effective_role_uses_group_role(db_session) -> None:
    """只有 group role 時應正確回傳。"""

    area = Area(id=_uuid(), name="Group Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    principal = CurrentPrincipal(sub="user-group", groups=("/group/reader",))
    assert resolve_effective_role_for_area(db_session, principal, area.id) == Role.reader


def test_effective_role_uses_maximum_of_direct_and_group_roles(db_session) -> None:
    """direct 與 group 同時存在時應取最大值。"""

    area = Area(id=_uuid(), name="Max Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-max", role=Role.reader))
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/admin", role=Role.admin))
    db_session.commit()

    principal = CurrentPrincipal(sub="user-max", groups=("/group/admin",))
    assert resolve_effective_role_for_area(db_session, principal, area.id) == Role.admin


def test_claim_parser_treats_missing_groups_as_empty_tuple() -> None:
    """缺少 groups claim 時應視為空集合。"""

    principal = _build_principal_from_payload(payload={"sub": "user-no-groups"}, groups_claim="groups")
    assert principal == CurrentPrincipal(sub="user-no-groups", groups=tuple())


def test_claim_parser_rejects_invalid_groups_shape() -> None:
    """groups claim 不是字串陣列時應拒絕。"""

    try:
        _build_principal_from_payload(payload={"sub": "user-bad-groups", "groups": "not-a-list"}, groups_claim="groups")
    except InvalidTokenError:
        pass
    else:
        raise AssertionError("預期應拒絕非法的 groups claim 格式。")


def test_auth_context_requires_valid_bearer_token(client) -> None:
    """沒有 Bearer token 時應回 401。"""

    response = client.get("/auth/context")
    assert response.status_code == 401


def test_auth_context_returns_principal(client) -> None:
    """測試模式 token 應可回傳 principal。"""

    response = client.get("/auth/context", headers={"Authorization": "Bearer test::user-1::/group/a,/group/b"})

    assert response.status_code == 200
    assert response.json() == {
        "sub": "user-1",
        "groups": ["/group/a", "/group/b"],
        "authenticated": True,
        "name": None,
        "preferred_username": None,
    }


def test_evaluation_dataset_routes_allow_maintainer_but_hide_from_reader_and_outsider(client, db_session) -> None:
    """evaluation dataset routes 應只允許 maintainer/admin，並維持 same-404。"""

    area = Area(id=_uuid(), name="Evaluation Protected")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.add(
        RetrievalEvalDataset(
            id=_uuid(),
            area_id=area.id,
            name="Protected Dataset",
            created_by_sub="user-maintainer",
        )
    )
    db_session.commit()

    maintainer_response = client.get(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": MAINTAINER_TOKEN},
    )
    reader_response = client.get(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": READER_TOKEN},
    )
    outsider_response = client.get(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": OUTSIDER_TOKEN},
    )
    missing_response = client.get(
        "/areas/missing-area/evaluation/datasets",
        headers={"Authorization": OUTSIDER_TOKEN},
    )

    assert maintainer_response.status_code == 200
    assert maintainer_response.json()["items"][0]["name"] == "Protected Dataset"
    assert reader_response.status_code == 403
    assert outsider_response.status_code == 404
    assert missing_response.status_code == 404
    assert outsider_response.json() == missing_response.json()


def test_auth_context_rejects_invalid_groups_claim_shape(client) -> None:
    """格式錯誤的測試 token 應被視為無效。"""

    response = client.get("/auth/context", headers={"Authorization": "Bearer malformed-token"})
    assert response.status_code == 401


def test_auth_context_returns_503_when_auth_service_is_unavailable(client) -> None:
    """當外部驗證服務暫時不可用時，auth context 應回 503 而非 500。"""

    class UnavailableVerifier:
        """固定模擬外部驗證服務失敗的 verifier。"""

        def verify(self, token: str) -> CurrentPrincipal:
            """驗證 token 並固定拋出服務不可用錯誤。

            參數：
            - `token`：待驗證 token；此測試不實際使用其內容。

            回傳：
            - `CurrentPrincipal`：此測試路徑不會成功回傳。
            """

            raise AuthServiceUnavailableError("目前無法連線到 Keycloak 驗證服務，請稍後再試。")

    client.app.dependency_overrides[get_token_verifier] = lambda: UnavailableVerifier()
    try:
        response = client.get("/auth/context", headers={"Authorization": "Bearer test::user-1::/group/a"})
    finally:
        client.app.dependency_overrides.pop(get_token_verifier, None)

    assert response.status_code == 503
    assert response.json() == {"detail": "目前無法連線到 Keycloak 驗證服務，請稍後再試。"}


def test_langgraph_authenticate_reuses_module_level_token_verifier(monkeypatch) -> None:
    """LangGraph custom auth 應重用模組層級 verifier，而非每次 request 重建。"""

    class RecordingVerifier:
        """記錄 verify 呼叫次數的測試 verifier。"""

        def __init__(self) -> None:
            """建立可觀測的測試 verifier。

            參數：
            - 無

            回傳：
            - `None`：僅初始化內部狀態。
            """

            self.calls: list[str] = []

        def verify(self, token: str) -> CurrentPrincipal:
            """記錄 token 並回傳固定 principal。

            參數：
            - `token`：待驗證 token。

            回傳：
            - `CurrentPrincipal`：固定的測試 principal。
            """

            self.calls.append(token)
            return CurrentPrincipal(sub="user-langgraph", groups=("/group/a",), preferred_username="alice")

    verifier = RecordingVerifier()
    monkeypatch.setattr(langgraph_auth_runtime, "AUTH_TOKEN_VERIFIER", verifier)

    payload_one = asyncio.run(langgraph_auth_runtime.authenticate("Bearer token-one"))
    payload_two = asyncio.run(langgraph_auth_runtime.authenticate("Bearer token-two"))

    assert verifier.calls == ["token-one", "token-two"]
    assert payload_one == {
        "identity": "user-langgraph",
        "sub": "user-langgraph",
        "groups": ["/group/a"],
    }
    assert payload_two == payload_one


def test_keycloak_verifier_rebuilds_jwks_client_after_connection_error(monkeypatch) -> None:
    """JWKS client 第一次連線失敗時應重建 client 後再成功驗證。"""

    class FakeSigningKey:
        """模擬 PyJWT signing key 結果。"""

        key = "fake-key"

    class FakeJwksClient:
        """模擬會在第一次失敗、第二次成功的 JWKS client。"""

        def __init__(self, url: str) -> None:
            """建立測試用 client。

            參數：
            - `url`：JWKS endpoint；此測試只保留供斷言用途。

            回傳：
            - `None`：僅建立測試狀態。
            """

            self.url = url
            self.calls = 0

        def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
            """模擬第一次連線失敗、之後成功回傳 signing key。

            參數：
            - `token`：待驗證 token；此測試不解析內容。

            回傳：
            - `FakeSigningKey`：第二次起回傳的簽章金鑰。
            """

            self.calls += 1
            if fail_once_state["pending"]:
                fail_once_state["pending"] = False
                raise jwt.exceptions.PyJWKClientConnectionError("connection refused")
            return FakeSigningKey()

    created_clients: list[FakeJwksClient] = []
    fail_once_state = {"pending": True}

    def fake_jwks_client_factory(url: str) -> FakeJwksClient:
        """建立可觀測的假 JWKS client。"""

        client = FakeJwksClient(url)
        created_clients.append(client)
        return client

    def fake_decode(*args, **kwargs) -> dict[str, object]:
        """回傳固定 payload，避免依賴真實 JWT 驗章。"""

        return {"sub": "user-1", "groups": ["/group/a"], "preferred_username": "alice"}

    monkeypatch.setattr("app.auth.verifier.PyJWKClient", fake_jwks_client_factory)
    monkeypatch.setattr("app.auth.verifier.jwt.decode", fake_decode)

    settings = SimpleNamespace(
        keycloak_jwks_url="http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs",
        keycloak_issuer="http://localhost:18080/realms/deep-agent-dev",
        keycloak_groups_claim="groups",
    )
    verifier = KeycloakJwtVerifier(settings=settings)

    principal = verifier.verify("fake-token")

    assert principal == CurrentPrincipal(sub="user-1", groups=("/group/a",), preferred_username="alice")
    assert len(created_clients) == 2
    assert created_clients[0].calls == 1
    assert created_clients[1].calls == 1


def test_access_check_returns_effective_role_for_authorized_user(client, db_session) -> None:
    """已授權使用者應取得 effective role。"""

    area = Area(id=_uuid(), name="Access Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    response = client.get(
        f"/areas/{area.id}/access-check",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 200
    assert response.json() == {"area_id": area.id, "effective_role": "reader"}


def test_access_check_returns_404_for_unauthorized_area(client, db_session) -> None:
    """沒有有效角色時應以 404 隱藏 area。"""

    area = Area(id=_uuid(), name="Hidden Area")
    db_session.add(area)
    db_session.commit()

    response = client.get(
        f"/areas/{area.id}/access-check",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 404


def test_access_check_returns_same_404_for_missing_area(client) -> None:
    """不存在的 area 也應回相同 404，避免資訊洩漏。"""

    response = client.get(
        "/areas/missing-area/access-check",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 404
