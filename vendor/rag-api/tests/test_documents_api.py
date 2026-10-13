"""Documents、ingest jobs 與全文 preview API 測試。"""

from pathlib import Path
from uuid import uuid4

from app.db.models import (
    Area,
    AreaUserRole,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentChunkRegion,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    Role,
)
from app.services.tasks import DEFAULT_TASK_QUEUE_NAME, INGEST_DOCUMENT_TASK_NAME


# 管理者測試 token。
ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"

# 維護者測試 token。
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"

# 讀者測試 token。
READER_TOKEN = "Bearer test::user-reader::/group/reader"

# 無授權測試 token。
OUTSIDER_TOKEN = "Bearer test::user-outsider::/group/outsider"


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def _assert_single_dispatch(celery_client, *, job_id: str, force_reparse: bool = False) -> None:
    """驗證測試 Celery client 只收到一次正確的 ingest dispatch。"""

    assert celery_client.calls == [
        (
            INGEST_DOCUMENT_TASK_NAME,
            {"job_id": job_id, "force_reparse": force_reparse},
            DEFAULT_TASK_QUEUE_NAME,
        )
    ]


def test_upload_document_creates_uploaded_document_and_dispatches_job(client, db_session, app_settings, celery_client) -> None:
    """maintainer 上傳文件後應只建立 queued job 並 dispatch worker。"""

    area = Area(id=_uuid(), name="Maintainer Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    file_payload = f"# Intro\n{'A' * 320}\n\n## Detail\n{'B' * 340}\n".encode()
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("notes.md", file_payload, "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["file_name"] == "notes.md"
    assert payload["document"]["status"] == "uploaded"
    assert payload["document"]["chunk_summary"]["total_chunks"] == 0
    assert payload["job"]["status"] == "queued"
    assert payload["job"]["stage"] == "queued"
    assert payload["job"]["chunk_summary"]["total_chunks"] == 0

    stored_document = db_session.get(Document, payload["document"]["id"])
    stored_job = db_session.get(IngestJob, payload["job"]["id"])
    assert stored_document is not None
    assert stored_document.status == DocumentStatus.uploaded
    assert stored_document.file_size == len(file_payload)
    assert stored_document.indexed_at is None
    assert stored_document.display_text is None
    assert stored_document.normalized_text is None
    assert stored_job is not None
    assert stored_job.status == IngestJobStatus.queued
    assert stored_job.stage == "queued"
    assert stored_job.parent_chunk_count == 0
    assert stored_job.child_chunk_count == 0
    assert db_session.query(DocumentChunk).filter(DocumentChunk.document_id == stored_document.id).count() == 0
    assert (Path(app_settings.local_storage_path) / stored_document.storage_key).exists()
    _assert_single_dispatch(celery_client, job_id=stored_job.id)


def test_upload_document_rejects_reader(client, db_session, celery_client) -> None:
    """reader 不可上傳文件。"""

    area = Area(id=_uuid(), name="Reader Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": READER_TOKEN},
        files={"file": ("notes.md", b"# denied", "text/markdown")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "目前角色無法執行此操作。"
    assert celery_client.calls == []


def test_upload_document_returns_same_404_for_unauthorized_and_missing_area(client, db_session, celery_client) -> None:
    """未授權與不存在 area 的上傳都應回相同 404。"""

    area = Area(id=_uuid(), name="Hidden Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": OUTSIDER_TOKEN},
        files={"file": ("notes.md", b"# hidden", "text/markdown")},
    )
    missing_response = client.post(
        "/areas/missing-area/documents",
        headers={"Authorization": OUTSIDER_TOKEN},
        files={"file": ("notes.md", b"# hidden", "text/markdown")},
    )

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()
    assert celery_client.calls == []


def test_upload_document_rejects_empty_file(client, db_session, celery_client) -> None:
    """空檔案應被 upload validator 擋下。"""

    area = Area(id=_uuid(), name="Empty File Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("empty.md", b"", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "上傳檔案不可為空。"
    assert celery_client.calls == []


def test_upload_document_rejects_oversized_file(client, db_session, app_settings, celery_client) -> None:
    """超過上限的檔案應被 upload validator 擋下。"""

    area = Area(id=_uuid(), name="Oversized Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    oversized_payload = b"A" * (app_settings.max_upload_size_bytes + 1)
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("oversized.md", oversized_payload, "text/markdown")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "檔案超過上傳大小限制。"
    assert celery_client.calls == []


def test_upload_document_rejects_unknown_extension(client, db_session, celery_client) -> None:
    """未知副檔名應被 upload validator 擋下。"""

    area = Area(id=_uuid(), name="Unknown Extension Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("notes.csv", b"alpha,beta", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "目前不支援此檔案類型。"
    assert celery_client.calls == []


def test_list_documents_returns_only_area_documents_with_chunk_summary(client, db_session) -> None:
    """area 文件列表只應回傳指定 area 內的文件與其 chunk 摘要。"""

    visible_area = Area(id=_uuid(), name="Visible")
    hidden_area = Area(id=_uuid(), name="Hidden")
    visible_document_id = _uuid()
    hidden_document_id = _uuid()
    db_session.add_all([visible_area, hidden_area])
    db_session.add_all(
        [
            AreaUserRole(area_id=visible_area.id, user_sub="user-reader", role=Role.reader),
            AreaUserRole(area_id=hidden_area.id, user_sub="user-admin", role=Role.admin),
            Document(
                id=visible_document_id,
                area_id=visible_area.id,
                file_name="visible.md",
                content_type="text/markdown",
                file_size=10,
                storage_key="visible",
                status=DocumentStatus.ready,
            ),
            Document(
                id=hidden_document_id,
                area_id=hidden_area.id,
                file_name="hidden.md",
                content_type="text/markdown",
                file_size=12,
                storage_key="hidden",
                status=DocumentStatus.ready,
            ),
            DocumentChunk(
                document_id=visible_document_id,
                parent_chunk_id=None,
                chunk_type=ChunkType.parent,
                structure_kind=ChunkStructureKind.text,
                position=0,
                section_index=0,
                child_index=None,
                heading="Visible",
                content="Visible section",
                content_preview="Visible section",
                char_count=15,
                start_offset=0,
                end_offset=15,
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/areas/{visible_area.id}/documents", headers={"Authorization": READER_TOKEN})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [visible_document_id]
    assert response.json()["items"][0]["chunk_summary"]["parent_chunks"] == 1
    assert response.json()["items"][0]["chunk_summary"]["mixed_structure_parents"] == 0
    assert response.json()["items"][0]["chunk_summary"]["text_table_text_clusters"] == 0


def test_document_detail_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 document 都應回相同 404。"""

    area = Area(id=_uuid(), name="Secret")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    db_session.add(area)
    db_session.add(document)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/documents/{document.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/documents/missing-document", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_document_preview_returns_display_text_and_child_chunk_map(client, db_session) -> None:
    """已授權且 ready 的文件應可回傳全文 display_text 與 child chunk map。"""

    area = Area(id=_uuid(), name="Preview Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="preview.md",
        content_type="text/markdown",
        file_size=18,
        storage_key="preview",
        display_text="# Intro\nAlpha body\n\n## Next\nBeta body",
        normalized_text="# Intro\nAlpha body\n\n## Next\nBeta body",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Intro",
        content="Alpha body\n\nBeta body",
        content_preview="Alpha body",
        char_count=21,
        start_offset=8,
        end_offset=29,
    )
    child_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Intro",
        content="Alpha body",
        content_preview="Alpha body",
        char_count=10,
        start_offset=8,
        end_offset=18,
    )
    child_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Next",
        content="Beta body",
        content_preview="Beta body",
        char_count=9,
        start_offset=29,
        end_offset=38,
    )
    db_session.add_all([area, document, parent, child_one, child_two])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.commit()

    response = client.get(f"/documents/{document.id}/preview", headers={"Authorization": READER_TOKEN})

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document.id
    assert payload["display_text"] == "# Intro\nAlpha body\n\n## Next\nBeta body"
    assert [item["child_index"] for item in payload["chunks"]] == [0, 1]
    assert payload["chunks"][0]["parent_chunk_id"] == parent.id
    assert payload["chunks"][0]["start_offset"] == 8
    assert payload["chunks"][1]["heading"] == "Next"


def test_document_preview_returns_chunk_regions_without_uuid_cast_errors(client, db_session) -> None:
    """全文 preview 在存在 chunk regions 時不應因字串/UUID 型別不一致而失敗。"""

    area = Area(id=_uuid(), name="Preview Region Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="preview-regions.pdf",
        content_type="application/pdf",
        file_size=18,
        storage_key="preview-regions",
        display_text="Alpha body\nBeta body",
        normalized_text="Alpha body\nBeta body",
        status=DocumentStatus.ready,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Intro",
        content="Alpha body",
        content_preview="Alpha body",
        char_count=10,
        start_offset=0,
        end_offset=10,
    )
    region = DocumentChunkRegion(
        id=_uuid(),
        chunk_id=child.id,
        page_number=1,
        region_order=0,
        bbox_left=10.0,
        bbox_bottom=20.0,
        bbox_right=30.0,
        bbox_top=40.0,
    )
    db_session.add_all([area, document, child, region])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.commit()

    response = client.get(f"/documents/{document.id}/preview", headers={"Authorization": READER_TOKEN})

    assert response.status_code == 200
    payload = response.json()
    assert payload["chunks"][0]["chunk_id"] == child.id
    assert payload["chunks"][0]["page_start"] == 1
    assert payload["chunks"][0]["page_end"] == 1
    assert payload["chunks"][0]["regions"] == [
        {
            "page_number": 1,
            "region_order": 0,
            "bbox_left": 10.0,
            "bbox_bottom": 20.0,
            "bbox_right": 30.0,
            "bbox_top": 40.0,
        }
    ]


def test_document_preview_returns_same_404_for_unauthorized_missing_and_not_ready(client, db_session) -> None:
    """未授權、不存在與非 ready 文件的 preview 都應回相同 404。"""

    area = Area(id=_uuid(), name="Preview Secret")
    ready_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="ready.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="ready",
        display_text="Ready body",
        normalized_text="Ready body",
        status=DocumentStatus.ready,
    )
    uploaded_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="uploaded.md",
        content_type="text/markdown",
        file_size=11,
        storage_key="uploaded",
        normalized_text=None,
        status=DocumentStatus.uploaded,
    )
    db_session.add_all([area, ready_document, uploaded_document])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/documents/{ready_document.id}/preview", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/documents/missing-document/preview", headers={"Authorization": OUTSIDER_TOKEN})
    not_ready_response = client.get(f"/documents/{uploaded_document.id}/preview", headers={"Authorization": ADMIN_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert not_ready_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json() == not_ready_response.json()


def test_document_preview_returns_same_404_when_display_text_is_missing(client, db_session) -> None:
    """ready 文件若尚未建立 display_text，也應與 missing 文件回相同 404。"""

    area = Area(id=_uuid(), name="Preview Missing Display Text")
    ready_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="ready.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="ready",
        normalized_text="Ready body",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, ready_document])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    missing_display_text_response = client.get(
        f"/documents/{ready_document.id}/preview",
        headers={"Authorization": ADMIN_TOKEN},
    )
    missing_response = client.get("/documents/missing-document/preview", headers={"Authorization": ADMIN_TOKEN})

    assert missing_display_text_response.status_code == 404
    assert missing_response.status_code == 404
    assert missing_display_text_response.json() == missing_response.json()


def test_ingest_job_detail_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 ingest job 都應回相同 404。"""

    area = Area(id=_uuid(), name="Secret Job")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    job = IngestJob(id=_uuid(), document_id=document.id, status=IngestJobStatus.succeeded)
    db_session.add_all([area, document, job])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/ingest-jobs/{job.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/ingest-jobs/missing-job", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_reindex_document_resets_document_and_dispatches_new_job(client, db_session, app_settings, celery_client) -> None:
    """reindex 應清掉舊 chunks、保留 parse artifacts，並建立新的 queued job。"""

    area = Area(id=_uuid(), name="Reindex Docs")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="notes.md",
        content_type="text/markdown",
        file_size=20,
        storage_key=f"{area.id}/document/notes.md",
        display_text="old text",
        normalized_text="old text",
        status=DocumentStatus.ready,
    )
    old_job = IngestJob(id=_uuid(), document_id=document.id, status=IngestJobStatus.succeeded, stage="succeeded")
    old_parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Intro",
        content="old text",
        content_preview="old text",
        char_count=8,
        start_offset=0,
        end_offset=8,
    )
    old_child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=old_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Intro",
        content="old text",
        content_preview="old text",
        char_count=8,
        start_offset=0,
        end_offset=8,
    )
    db_session.add_all([area, document, old_job, old_parent, old_child])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    storage_path = Path(app_settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"# Intro\ncontent\n")
    artifact_path = Path(app_settings.local_storage_path) / area.id / "document" / "artifacts" / "stale.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("stale artifact", encoding="utf-8")

    response = client.post(f"/documents/{document.id}/reindex", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["status"] == "uploaded"
    assert payload["document"]["chunk_summary"]["total_chunks"] == 0
    assert payload["job"]["status"] == "queued"
    assert payload["job"]["stage"] == "queued"

    db_session.expire_all()
    refreshed_document = db_session.get(Document, document.id)
    assert refreshed_document is not None
    assert refreshed_document.status == DocumentStatus.uploaded
    assert refreshed_document.display_text is None
    assert refreshed_document.normalized_text is None
    assert refreshed_document.indexed_at is None
    assert db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count() == 0
    assert artifact_path.exists()
    assert db_session.query(IngestJob).filter(IngestJob.document_id == document.id).count() == 2
    _assert_single_dispatch(celery_client, job_id=payload["job"]["id"])


def test_reindex_document_can_force_reparse(client, db_session, celery_client) -> None:
    """reindex 應可透過 query 參數要求 worker 強制重跑 parser。"""

    area = Area(id=_uuid(), name="Force Reparse Docs")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="notes.md",
        content_type="text/markdown",
        file_size=20,
        storage_key=f"{area.id}/document/notes.md",
        display_text="old text",
        normalized_text="old text",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, document])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/documents/{document.id}/reindex?force_reparse=true",
        headers={"Authorization": ADMIN_TOKEN},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_single_dispatch(celery_client, job_id=payload["job"]["id"], force_reparse=True)


def test_reindex_document_returns_same_404_for_unauthorized_and_missing(client, db_session, celery_client) -> None:
    """未授權與不存在的 reindex 操作都應回相同 404。"""

    area = Area(id=_uuid(), name="Reindex Secret")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, document])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.post(f"/documents/{document.id}/reindex", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.post("/documents/missing-document/reindex", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()
    assert celery_client.calls == []


def test_delete_document_removes_storage_chunks_jobs_and_record(client, db_session, app_settings) -> None:
    """刪除文件時應一併移除 storage、artifacts、jobs、chunks 與 document record。"""

    area = Area(id=_uuid(), name="Delete Docs")
    document_id = _uuid()
    document = Document(
        id=document_id,
        area_id=area.id,
        file_name="notes.md",
        content_type="text/markdown",
        file_size=20,
        storage_key=f"{area.id}/document/notes.md",
        status=DocumentStatus.ready,
    )
    job = IngestJob(id=_uuid(), document_id=document.id, status=IngestJobStatus.succeeded, stage="succeeded")
    chunk = DocumentChunk(
        id=_uuid(),
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
    )
    db_session.add_all([area, document, job, chunk])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    storage_path = Path(app_settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"# Intro\ncontent\n")
    artifact_path = Path(app_settings.local_storage_path) / area.id / "document" / "artifacts" / "stale.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("stale artifact", encoding="utf-8")

    response = client.delete(f"/documents/{document.id}", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(Document, document_id) is None
    assert db_session.query(IngestJob).filter(IngestJob.document_id == document_id).count() == 0
    assert db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count() == 0
    assert not artifact_path.exists()
    assert not storage_path.exists()


def test_delete_document_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 delete 操作都應回相同 404。"""

    area = Area(id=_uuid(), name="Delete Secret")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, document])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.delete(f"/documents/{document.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.delete("/documents/missing-document", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()
