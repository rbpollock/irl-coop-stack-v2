"""Area chat session metadata API 測試。"""

from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from app.db.models import Area, AreaChatSession, AreaGroupRole, AreaUserRole, Role
from app.services.chat_sessions import LangGraphThreadNotVerifiableError


# 管理者測試 token。
ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"
# reader 測試 token。
READER_TOKEN = "Bearer test::user-reader::/group/reader"
# 另一位 reader 測試 token。
SECOND_READER_TOKEN = "Bearer test::user-reader-2::/group/reader-two"
# 無授權測試 token。
OUTSIDER_TOKEN = "Bearer test::user-outsider::/group/outsider"


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def _build_thread_payload(*, thread_id: str, area_id: str, owner_sub: str) -> dict[str, object]:
    """建立 fake LangGraph thread payload。"""

    return {
        "thread_id": thread_id,
        "metadata": {
            "area_id": area_id,
            "owner": owner_sub,
        },
    }


def test_list_area_chat_sessions_returns_only_current_user_rows(client, db_session) -> None:
    """list route 只應回傳目前使用者自己的 sessions。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add_all(
        [
            AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader),
            AreaGroupRole(area_id=area.id, group_path="/group/reader-two", role=Role.reader),
            AreaChatSession(area_id=area.id, owner_sub="user-reader", thread_id="thread-reader", title="Reader A"),
            AreaChatSession(area_id=area.id, owner_sub="user-reader-2", thread_id="thread-other", title="Other B"),
        ]
    )
    db_session.commit()

    response = client.get(f"/areas/{area.id}/chat-sessions", headers={"Authorization": READER_TOKEN})

    assert response.status_code == 200
    assert [item["thread_id"] for item in response.json()["items"]] == ["thread-reader"]


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_register_area_chat_session_creates_metadata_row_for_valid_thread(mock_fetch_thread, client, db_session) -> None:
    """註冊合法 thread 後應建立正式 metadata row。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    async def fake_fetch_thread(**_kwargs):
        return _build_thread_payload(thread_id="thread-1", area_id=area.id, owner_sub="user-reader")

    mock_fetch_thread.side_effect = fake_fetch_thread

    response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": READER_TOKEN},
        json={"thread_id": "thread-1", "title": "Reader Session"},
    )

    assert response.status_code == 201
    assert response.json()["thread_id"] == "thread-1"
    row = db_session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == "thread-1"))
    assert row is not None
    assert row.owner_sub == "user-reader"
    assert row.area_id == area.id


@patch("app.services.chat_sessions.create_langgraph_thread")
def test_register_area_chat_session_creates_thread_server_side_when_thread_id_is_missing(
    mock_create_thread,
    client,
    db_session,
) -> None:
    """若 request 未提供 thread_id，後端應自行建立 LangGraph thread 並保存 metadata。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()
    mock_create_thread.return_value = "thread-created-by-api"

    response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": READER_TOKEN},
        json={"title": "Server Created"},
    )

    assert response.status_code == 201
    assert response.json()["thread_id"] == "thread-created-by-api"
    row = db_session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == "thread-created-by-api"))
    assert row is not None
    assert row.owner_sub == "user-reader"


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_register_area_chat_session_is_idempotent_for_same_thread(mock_fetch_thread, client, db_session) -> None:
    """重複註冊同一 thread 應回既有 row，而不是新增重複資料。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    async def fake_fetch_thread(**_kwargs):
        return _build_thread_payload(thread_id="thread-1", area_id=area.id, owner_sub="user-reader")

    mock_fetch_thread.side_effect = fake_fetch_thread

    first_response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": READER_TOKEN},
        json={"thread_id": "thread-1", "title": "Reader Session"},
    )
    second_response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": READER_TOKEN},
        json={"thread_id": "thread-1", "title": "Reader Session"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    rows = db_session.scalars(select(AreaChatSession).where(AreaChatSession.thread_id == "thread-1")).all()
    assert len(rows) == 1


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_update_area_chat_session_updates_title_and_touch_timestamp(mock_fetch_thread, client, db_session) -> None:
    """patch route 應可更新 title，且只允許自己的 session。"""

    area = Area(id=_uuid(), name="Session Area")
    chat_session = AreaChatSession(area_id=area.id, owner_sub="user-reader", thread_id="thread-1", title="Old Title")
    db_session.add_all(
        [
            area,
            AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader),
            chat_session,
        ]
    )
    db_session.commit()
    original_updated_at = chat_session.updated_at

    async def fake_fetch_thread(**_kwargs):
        return _build_thread_payload(thread_id="thread-1", area_id=area.id, owner_sub="user-reader")

    mock_fetch_thread.side_effect = fake_fetch_thread

    response = client.patch(
        f"/areas/{area.id}/chat-sessions/thread-1",
        headers={"Authorization": READER_TOKEN},
        json={"title": "New Title"},
    )

    assert response.status_code == 200
    db_session.refresh(chat_session)
    assert chat_session.title == "New Title"
    assert chat_session.updated_at != original_updated_at
    mock_fetch_thread.assert_not_called()


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_update_area_chat_session_creates_row_when_metadata_was_missing(mock_fetch_thread, client, db_session) -> None:
    """若 session metadata 尚未建立，patch route 應可在驗證 thread 後自動補建。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    async def fake_fetch_thread(**_kwargs):
        return _build_thread_payload(thread_id="thread-upsert", area_id=area.id, owner_sub="user-reader")

    mock_fetch_thread.side_effect = fake_fetch_thread

    response = client.patch(
        f"/areas/{area.id}/chat-sessions/thread-upsert",
        headers={"Authorization": READER_TOKEN},
        json={"title": "Upserted Title"},
    )

    assert response.status_code == 200
    row = db_session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == "thread-upsert"))
    assert row is not None
    assert row.title == "Upserted Title"
    assert row.owner_sub == "user-reader"


def test_delete_area_chat_session_deletes_owned_row(client, db_session) -> None:
    """delete route 應可刪除目前使用者自己的 chat session。"""

    area = Area(id=_uuid(), name="Session Area")
    chat_session = AreaChatSession(area_id=area.id, owner_sub="user-reader", thread_id="thread-delete", title="Delete Me")
    db_session.add_all(
        [
            area,
            AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader),
            chat_session,
        ]
    )
    db_session.commit()

    response = client.delete(
        f"/areas/{area.id}/chat-sessions/thread-delete",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 204
    assert db_session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == "thread-delete")) is None


def test_delete_area_chat_session_preserves_same_404_for_missing_and_unauthorized(client, db_session) -> None:
    """delete route 對 missing/unauthorized 應維持 same-404。"""

    area = Area(id=_uuid(), name="Session Area")
    chat_session = AreaChatSession(area_id=area.id, owner_sub="user-admin", thread_id="thread-admin", title="Admin Only")
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            chat_session,
        ]
    )
    db_session.commit()

    unauthorized_response = client.delete(
        f"/areas/{area.id}/chat-sessions/thread-admin",
        headers={"Authorization": OUTSIDER_TOKEN},
    )
    missing_response = client.delete(
        "/areas/missing-area/chat-sessions/thread-admin",
        headers={"Authorization": OUTSIDER_TOKEN},
    )

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_delete_area_chat_session_preserves_same_404_for_other_users_row(client, db_session) -> None:
    """若 session 屬於其他使用者，delete route 應回 same-404。"""

    area = Area(id=_uuid(), name="Session Area")
    chat_session = AreaChatSession(area_id=area.id, owner_sub="user-admin", thread_id="thread-admin", title="Admin Only")
    db_session.add_all(
        [
            area,
            AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader),
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            chat_session,
        ]
    )
    db_session.commit()

    response = client.delete(
        f"/areas/{area.id}/chat-sessions/thread-admin",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 404


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_chat_session_routes_preserve_same_404_for_outsider_and_missing_area(mock_fetch_thread, client, db_session) -> None:
    """outsider 與 missing area 對 chat session route 應維持 same-404。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    async def fake_fetch_thread(**_kwargs):
        return _build_thread_payload(thread_id="thread-1", area_id=area.id, owner_sub="user-outsider")

    mock_fetch_thread.side_effect = fake_fetch_thread

    list_response = client.get(f"/areas/{area.id}/chat-sessions", headers={"Authorization": OUTSIDER_TOKEN})
    missing_list_response = client.get("/areas/missing-area/chat-sessions", headers={"Authorization": OUTSIDER_TOKEN})
    create_response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": OUTSIDER_TOKEN},
        json={"thread_id": "thread-1"},
    )
    missing_create_response = client.post(
        "/areas/missing-area/chat-sessions",
        headers={"Authorization": OUTSIDER_TOKEN},
        json={"thread_id": "thread-1"},
    )

    assert list_response.status_code == 404
    assert missing_list_response.status_code == 404
    assert list_response.json() == missing_list_response.json()
    assert create_response.status_code == 404
    assert missing_create_response.status_code == 404
    assert create_response.json() == missing_create_response.json()


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_register_area_chat_session_rejects_thread_owned_by_other_user_with_same_404(mock_fetch_thread, client, db_session) -> None:
    """若 thread owner 與 caller 不符，應回 same-404。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    async def fake_fetch_thread(**_kwargs):
        return _build_thread_payload(thread_id="thread-1", area_id=area.id, owner_sub="user-reader-2")

    mock_fetch_thread.side_effect = fake_fetch_thread

    response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": READER_TOKEN},
        json={"thread_id": "thread-1"},
    )

    assert response.status_code == 404


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_register_area_chat_session_rejects_thread_from_other_area_with_same_404(mock_fetch_thread, client, db_session) -> None:
    """若 thread metadata area 與 route area 不符，應回 same-404。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    async def fake_fetch_thread(**_kwargs):
        return _build_thread_payload(thread_id="thread-1", area_id="other-area", owner_sub="user-reader")

    mock_fetch_thread.side_effect = fake_fetch_thread

    response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": READER_TOKEN},
        json={"thread_id": "thread-1"},
    )

    assert response.status_code == 404


@patch("app.services.chat_sessions._fetch_langgraph_thread")
def test_register_area_chat_session_allows_fallback_when_thread_is_temporarily_unverifiable(
    mock_fetch_thread,
    client,
    db_session,
) -> None:
    """若 LangGraph thread 暫時不可驗證，仍應允許建立 metadata 以避免阻斷首次對話。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    async def fake_fetch_thread(**_kwargs):
        raise LangGraphThreadNotVerifiableError("404 not found")

    mock_fetch_thread.side_effect = fake_fetch_thread

    response = client.post(
        f"/areas/{area.id}/chat-sessions",
        headers={"Authorization": READER_TOKEN},
        json={"thread_id": "thread-fallback", "title": "Fallback Session"},
    )

    assert response.status_code == 201
    row = db_session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == "thread-fallback"))
    assert row is not None
    assert row.owner_sub == "user-reader"


def test_delete_area_cascades_chat_session_rows(client, db_session) -> None:
    """刪除 area 時應一併清除 chat session metadata。"""

    area = Area(id=_uuid(), name="Session Area")
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            AreaChatSession(area_id=area.id, owner_sub="user-admin", thread_id="thread-1", title="Delete Me"),
        ]
    )
    db_session.commit()

    response = client.delete(f"/areas/{area.id}", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 204
    assert db_session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == "thread-1")) is None
