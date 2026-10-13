"""Knowledge Area CRUD 與 access management API 測試。"""

from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from sqlalchemy import select

from app.db.models import Area, AreaGroupRole, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, IngestJob, IngestJobStatus, Role
from app.routes.areas import get_object_storage
from app.services.storage import StorageError


# 管理者測試 token。
ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"

# 維護者測試 token。
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"

# 無授權測試 token。
OUTSIDER_TOKEN = "Bearer test::user-outsider::/group/outsider"


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def test_create_area_assigns_creator_as_admin(client, db_session) -> None:
    """建立 area 後，建立者應自動成為 admin。"""

    response = client.post(
        "/areas",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "  平台文件區  ", "description": "  MVP area  "},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "平台文件區"
    assert payload["description"] == "MVP area"
    assert payload["effective_role"] == "admin"

    area_role = db_session.scalars(select(AreaUserRole).where(AreaUserRole.area_id == payload["id"])).one()
    assert area_role.user_sub == "user-admin"
    assert area_role.role == Role.admin


def test_list_areas_returns_only_accessible_areas_with_highest_role(client, db_session) -> None:
    """area list 只應回傳有權限的 area，且 role 應取最大值。"""

    accessible_area = Area(id=_uuid(), name="Visible Area")
    stronger_area = Area(id=_uuid(), name="Strong Area")
    hidden_area = Area(id=_uuid(), name="Hidden Area")
    db_session.add_all([accessible_area, stronger_area, hidden_area])
    db_session.add_all(
        [
            AreaGroupRole(area_id=accessible_area.id, group_path="/group/admin", role=Role.reader),
            AreaUserRole(area_id=stronger_area.id, user_sub="user-admin", role=Role.reader),
            AreaGroupRole(area_id=stronger_area.id, group_path="/group/admin", role=Role.admin),
            AreaGroupRole(area_id=hidden_area.id, group_path="/group/other", role=Role.reader),
        ]
    )
    db_session.commit()

    response = client.get("/areas", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [stronger_area.id, accessible_area.id]
    assert payload["items"][0]["effective_role"] == "admin"
    assert payload["items"][1]["effective_role"] == "reader"


def test_read_area_returns_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """未授權與不存在的 area 都應回相同 404。"""

    area = Area(id=_uuid(), name="Secret Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/areas/{area.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/areas/missing-area", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_read_area_returns_detail_for_authorized_user(client, db_session) -> None:
    """有權限的使用者應可讀取 area 詳細資料。"""

    area = Area(id=_uuid(), name="Detail Area", description="Area Description")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/admin", role=Role.maintainer))
    db_session.commit()

    response = client.get(f"/areas/{area.id}", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 200
    assert response.json()["effective_role"] == "maintainer"
    assert response.json()["description"] == "Area Description"


def test_update_area_updates_name_and_description_for_admin(client, db_session) -> None:
    """admin 應可更新 area 名稱與說明。"""

    area = Area(id=_uuid(), name="Old Name", description="Old Description")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.put(
        f"/areas/{area.id}",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "  New Name  ", "description": "  New Description  "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["description"] == "New Description"

    db_session.refresh(area)
    assert area.name == "New Name"
    assert area.description == "New Description"


def test_update_area_allows_blank_description_to_clear_value(client, db_session) -> None:
    """空白 description 應被正規化為空值。"""

    area = Area(id=_uuid(), name="Old Name", description="Legacy Description")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.put(
        f"/areas/{area.id}",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Updated", "description": "   "},
    )

    assert response.status_code == 200
    assert response.json()["description"] is None

    db_session.refresh(area)
    assert area.description is None


def test_update_area_requires_admin_role(client, db_session) -> None:
    """maintainer 不可更新 area。"""

    area = Area(id=_uuid(), name="Protected Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.put(
        f"/areas/{area.id}",
        headers={"Authorization": MAINTAINER_TOKEN},
        json={"name": "Updated", "description": "Updated"},
    )

    assert response.status_code == 403


def test_update_area_returns_same_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """未授權與不存在的 area update 都應回相同 404。"""

    area = Area(id=_uuid(), name="Secret Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.put(
        f"/areas/{area.id}",
        headers={"Authorization": OUTSIDER_TOKEN},
        json={"name": "Updated", "description": "Updated"},
    )
    missing_response = client.put(
        "/areas/missing-area",
        headers={"Authorization": OUTSIDER_TOKEN},
        json={"name": "Updated", "description": "Updated"},
    )

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_get_area_access_requires_admin_role(client, db_session) -> None:
    """maintainer 不可讀取 area access 管理內容。"""

    area = Area(id=_uuid(), name="Access Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.get(f"/areas/{area.id}/access", headers={"Authorization": MAINTAINER_TOKEN})

    assert response.status_code == 403


def test_get_area_access_returns_same_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """未授權與不存在的 access API 都應回相同 404。"""

    area = Area(id=_uuid(), name="Hidden Access Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/areas/{area.id}/access", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/areas/missing-area/access", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


@patch("app.services.areas.get_usernames_by_subs")
def test_get_area_access_returns_users_and_groups_for_admin(mock_get_usernames, client, db_session) -> None:
    """admin 應可讀取完整 access 規則。"""

    area = Area(id=_uuid(), name="Admin Access Area")
    db_session.add(area)
    db_session.add_all(
        [
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            AreaGroupRole(area_id=area.id, group_path="/group/editor", role=Role.maintainer),
        ]
    )
    db_session.commit()

    mock_get_usernames.return_value = {
        "user-admin": "user-admin",
        "user-reader": "user-reader",
    }

    response = client.get(f"/areas/{area.id}/access", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 200
    assert response.json() == {
        "area_id": area.id,
        "users": [
            {"username": "user-admin", "role": "admin"},
            {"username": "user-reader", "role": "reader"},
        ],
        "groups": [{"group_path": "/group/editor", "role": "maintainer"}],
    }


def test_replace_area_access_requires_admin_role(client, db_session) -> None:
    """maintainer 不可更新 area access。"""

    area = Area(id=_uuid(), name="Maintainer Update Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.put(
        f"/areas/{area.id}/access",
        headers={"Authorization": MAINTAINER_TOKEN},
        json={"users": [{"username": "user-maintainer", "role": "admin"}], "groups": []},
    )

    assert response.status_code == 403


def test_delete_area_requires_admin_role(client, db_session) -> None:
    """maintainer 不可刪除 area。"""

    area = Area(id=_uuid(), name="Protected Delete Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.delete(f"/areas/{area.id}", headers={"Authorization": MAINTAINER_TOKEN})

    assert response.status_code == 403


def test_delete_area_returns_same_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """未授權與不存在的 area delete 都應回相同 404。"""

    area = Area(id=_uuid(), name="Hidden Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.delete(f"/areas/{area.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.delete("/areas/missing-area", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_delete_area_cascades_related_data_and_cleans_storage(client, db_session, app_settings) -> None:
    """admin 刪除 area 時應同步清理 DB 與 storage 內容。"""

    area = Area(id=_uuid(), name="Delete Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="notes.md",
        content_type="text/markdown",
        file_size=12,
        storage_key=f"{area.id}/doc-1/notes.md",
        status=DocumentStatus.ready,
    )
    job = IngestJob(document_id=document.id, status=IngestJobStatus.succeeded, stage="succeeded")
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader),
            document,
            job,
            DocumentChunk(
                document_id=document.id,
                parent_chunk_id=None,
                chunk_type=ChunkType.parent,
                structure_kind=ChunkStructureKind.text,
                position=0,
                section_index=0,
                child_index=None,
                heading="Intro",
                content="content",
                content_preview="content",
                char_count=7,
                start_offset=0,
                end_offset=7,
            ),
        ]
    )
    db_session.commit()

    storage_root = Path(app_settings.local_storage_path)
    source_path = storage_root / document.storage_key
    artifact_path = storage_root / area.id / "doc-1" / "artifacts" / "opendataloader.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("source", encoding="utf-8")
    artifact_path.write_text("artifact", encoding="utf-8")
    area_id = area.id
    document_id = document.id
    job_id = job.id

    response = client.delete(f"/areas/{area_id}", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(Area, area_id) is None
    assert db_session.get(Document, document_id) is None
    assert db_session.get(IngestJob, job_id) is None
    assert db_session.scalars(select(AreaUserRole).where(AreaUserRole.area_id == area_id)).all() == []
    assert db_session.scalars(select(AreaGroupRole).where(AreaGroupRole.area_id == area_id)).all() == []
    assert db_session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).all() == []
    assert not source_path.exists()
    assert not artifact_path.exists()


def test_delete_area_keeps_database_rows_when_storage_cleanup_fails(client, db_session) -> None:
    """storage 清理失敗時，不得刪除 area 與其關聯資料。"""

    area = Area(id=_uuid(), name="Delete Failure Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="notes.md",
        content_type="text/markdown",
        file_size=12,
        storage_key=f"{area.id}/doc-1/notes.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            document,
        ]
    )
    db_session.commit()

    failing_storage = Mock()
    failing_storage.delete_prefix.side_effect = StorageError("boom")
    client.app.dependency_overrides[get_object_storage] = lambda: failing_storage
    try:
        response = client.delete(f"/areas/{area.id}", headers={"Authorization": ADMIN_TOKEN})
    finally:
        client.app.dependency_overrides.pop(get_object_storage, None)

    assert response.status_code == 500
    assert response.json()["detail"] == "刪除 area 時無法清理物件儲存內容。"
    db_session.expire_all()
    assert db_session.get(Area, area.id) is not None
    assert db_session.get(Document, document.id) is not None
    failing_storage.delete_prefix.assert_called_once()
    failing_storage.delete_object.assert_not_called()


@patch("app.services.areas.get_sub_by_username")
@patch("app.services.areas.get_usernames_by_subs")
def test_replace_area_access_replaces_existing_rules_for_admin(mock_get_usernames, mock_get_sub, client, db_session) -> None:
    """admin 應可整體替換 area access 規則。"""

    area = Area(id=_uuid(), name="Replace Area")
    db_session.add(area)
    db_session.add_all(
        [
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            AreaUserRole(area_id=area.id, user_sub="user-legacy", role=Role.reader),
            AreaGroupRole(area_id=area.id, group_path="/group/legacy", role=Role.reader),
        ]
    )
    db_session.commit()

    def mock_get_sub_fn(username):
        return username
    mock_get_sub.side_effect = mock_get_sub_fn

    mock_get_usernames.return_value = {
        "user-admin": "user-admin",
        "user-next": "user-next",
    }

    response = client.put(
        f"/areas/{area.id}/access",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "users": [
                {"username": "user-admin", "role": "admin"},
                {"username": "user-next", "role": "maintainer"},
            ],
            "groups": [{"group_path": "/group/new", "role": "reader"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "area_id": area.id,
        "users": [
            {"username": "user-admin", "role": "admin"},
            {"username": "user-next", "role": "maintainer"},
        ],
        "groups": [{"group_path": "/group/new", "role": "reader"}],
    }

    stored_user_roles = db_session.scalars(select(AreaUserRole).where(AreaUserRole.area_id == area.id)).all()
    stored_group_roles = db_session.scalars(select(AreaGroupRole).where(AreaGroupRole.area_id == area.id)).all()
    assert {(item.user_sub, item.role.value) for item in stored_user_roles} == {
        ("user-admin", "admin"),
        ("user-next", "maintainer"),
    }
    assert {(item.group_path, item.role.value) for item in stored_group_roles} == {("/group/new", "reader")}
