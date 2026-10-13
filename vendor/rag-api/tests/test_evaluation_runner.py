"""Retrieval evaluation dataset、preview 與 run API 測試。"""

import json
from uuid import uuid4

from sqlalchemy import select

from app.db.models import (
    Area,
    AreaUserRole,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    RetrievalEvalRunArtifact,
    Role,
)


ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def test_evaluation_preview_and_run_return_multistage_report(client, db_session, app_settings) -> None:
    """candidate preview 與 benchmark run 應回傳 recall/rerank/assembled 三階段資訊。"""

    area = Area(id=_uuid(), name="Evaluation Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="facts.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="evaluation/facts.md",
        display_text="Alpha policy keeps zh-TW facts.\n\nBeta policy keeps English facts.",
        normalized_text="Alpha policy keeps zh-TW facts.\n\nBeta policy keeps English facts.",
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
        heading="Policy",
        content=document.display_text or "",
        content_preview="Alpha policy keeps zh-TW facts.",
        char_count=len(document.display_text or ""),
        start_offset=0,
        end_offset=len(document.display_text or ""),
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Policy",
        content="Alpha policy keeps zh-TW facts.",
        content_preview="Alpha policy keeps zh-TW facts.",
        char_count=len("Alpha policy keeps zh-TW facts."),
        start_offset=0,
        end_offset=len("Alpha policy keeps zh-TW facts."),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, parent, child])
    db_session.commit()

    dataset_response = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Phase 7 Dataset", "query_type": "fact_lookup"},
    )
    assert dataset_response.status_code == 201
    dataset_id = dataset_response.json()["id"]

    item_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "zh-TW facts", "language": "zh-TW", "query_type": "fact_lookup"},
    )
    assert item_response.status_code == 201
    item_id = item_response.json()["id"]

    span_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": document.id,
            "start_offset": 0,
            "end_offset": len("Alpha policy keeps zh-TW facts."),
            "relevance_grade": 3,
        },
    )
    assert span_response.status_code == 200
    assert span_response.json()["spans"][0]["relevance_grade"] == 3

    preview_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/candidate-preview",
        headers={"Authorization": ADMIN_TOKEN},
        json={},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["query_routing"]["query_type"] == "fact_lookup"
    assert preview_payload["query_routing"]["selected_profile"] == "fact_lookup_precision_v1"
    assert preview_payload["query_routing"]["summary_scope"] is None
    assert preview_payload["query_routing"]["resolved_document_ids"] == []
    assert preview_payload["selection"]["applied"] is False
    assert preview_payload["selection"]["strategy"] == "disabled"
    assert preview_payload["recall"]["items"]
    assert preview_payload["rerank"]["items"]
    assert preview_payload["assembled"]["items"]

    run_response = client.post(
        f"/evaluation/datasets/{dataset_id}/runs",
        headers={"Authorization": ADMIN_TOKEN},
        json={"top_k": 5},
    )
    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["run"]["status"] == "completed"
    assert run_payload["run"]["evaluation_profile"] == "production_like_v1"
    assert run_payload["run"]["config_snapshot"]["top_k"] == 5
    assert run_payload["run"]["config_snapshot"]["query_routing"]["query_type"] == "fact_lookup"
    assert run_payload["run"]["config_snapshot"]["query_routing"]["selected_profile"] == "fact_lookup_precision_v1"
    assert run_payload["run"]["config_snapshot"]["query_routing"]["summary_scope"] is None
    assert run_payload["run"]["config_snapshot"]["rerank"]["top_n"] == app_settings.rerank_top_n
    assert "recall" in run_payload["summary_metrics"]
    assert run_payload["per_query"][0]["query_routing"]["query_type"] == "fact_lookup"
    assert run_payload["per_query"][0]["selection"]["applied"] is False
    assert run_payload["per_query"][0]["recall"]["first_hit_rank"] == 1
    assert run_payload["per_query"][0]["recall"]["first_hit_rank"] == preview_payload["recall"]["first_hit_rank"]
    assert run_payload["per_query"][0]["rerank"]["first_hit_rank"] == preview_payload["rerank"]["first_hit_rank"]
    assert run_payload["per_query"][0]["assembled"]["first_hit_rank"] == preview_payload["assembled"]["first_hit_rank"]
    assert run_payload["dataset"]["baseline_run_id"] == run_payload["run"]["id"]
    artifact = db_session.scalar(
        select(RetrievalEvalRunArtifact).where(RetrievalEvalRunArtifact.run_id == run_payload["run"]["id"])
    )
    assert artifact is not None
    persisted_report = json.loads(artifact.report_json)
    assert persisted_report["per_query"][0]["item_id"] == item_id


def test_external_single_document_benchmark_uses_gold_document_scope(client, db_session, app_settings) -> None:
    """QASPER/UDA/DRCD 類 benchmark run 應以 gold 文件作為指定文件 scope。

    參數：
    - `client`：測試用 HTTP client。
    - `db_session`：測試資料庫 session。
    - `app_settings`：測試用 API 設定。

    回傳：
    - `None`：此測試只驗證 benchmark-only 文件範圍。
    """

    area = Area(id=_uuid(), name="QASPER Oracle Scope Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    gold_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="gold-paper.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="evaluation/gold-paper.md",
        display_text="Gold paper contains the alpha answer.",
        normalized_text="Gold paper contains the alpha answer.",
        status=DocumentStatus.ready,
    )
    other_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="other-paper.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="evaluation/other-paper.md",
        display_text="Other paper also mentions alpha answer.",
        normalized_text="Other paper also mentions alpha answer.",
        status=DocumentStatus.ready,
    )
    gold_parent = DocumentChunk(
        id=_uuid(),
        document_id=gold_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=10,
        section_index=0,
        child_index=None,
        heading="Gold",
        content=gold_document.display_text or "",
        content_preview=gold_document.display_text or "",
        char_count=len(gold_document.display_text or ""),
        start_offset=0,
        end_offset=len(gold_document.display_text or ""),
    )
    gold_child = DocumentChunk(
        id=_uuid(),
        document_id=gold_document.id,
        parent_chunk_id=gold_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=11,
        section_index=0,
        child_index=0,
        heading="Gold",
        content=gold_document.display_text or "",
        content_preview=gold_document.display_text or "",
        char_count=len(gold_document.display_text or ""),
        start_offset=0,
        end_offset=len(gold_document.display_text or ""),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    other_parent = DocumentChunk(
        id=_uuid(),
        document_id=other_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Other",
        content=other_document.display_text or "",
        content_preview=other_document.display_text or "",
        char_count=len(other_document.display_text or ""),
        start_offset=0,
        end_offset=len(other_document.display_text or ""),
    )
    other_child = DocumentChunk(
        id=_uuid(),
        document_id=other_document.id,
        parent_chunk_id=other_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Other",
        content=other_document.display_text or "",
        content_preview=other_document.display_text or "",
        char_count=len(other_document.display_text or ""),
        start_offset=0,
        end_offset=len(other_document.display_text or ""),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([gold_document, other_document, gold_parent, gold_child, other_parent, other_child])
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "qasper-curated-v1-100", "query_type": "fact_lookup"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "alpha answer", "language": "en", "query_type": "fact_lookup"},
    ).json()["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": gold_document.id,
            "start_offset": 0,
            "end_offset": len(gold_document.display_text or ""),
            "relevance_grade": 3,
        },
    )

    run_response = client.post(
        f"/evaluation/datasets/{dataset_id}/runs",
        headers={"Authorization": ADMIN_TOKEN},
        json={"top_k": 5},
    )

    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["run"]["config_snapshot"]["benchmark_document_scope"]["mode"] == "gold_document_ids"
    assert run_payload["per_query"][0]["benchmark_document_scope"] == {
        "mode": "gold_document_ids",
        "document_ids": [gold_document.id],
    }
    assert run_payload["per_query"][0]["recall"]["first_hit_rank"] == 1


def test_evaluation_dataset_query_type_controls_item_query_type(client, db_session) -> None:
    """dataset query_type 應成為 item 的正式 query_type，且拒絕不一致 payload。"""

    area = Area(id=_uuid(), name="Evaluation Query Type Dataset")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    dataset_response = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Summary Dataset", "query_type": "document_summary"},
    )
    assert dataset_response.status_code == 201
    dataset_payload = dataset_response.json()
    assert dataset_payload["query_type"] == "document_summary"

    item_response = client.post(
        f"/evaluation/datasets/{dataset_payload['id']}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "請摘要這份文件", "language": "zh-TW"},
    )
    assert item_response.status_code == 201
    assert item_response.json()["query_type"] == "document_summary"

    mismatch_response = client.post(
        f"/evaluation/datasets/{dataset_payload['id']}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "compare this", "language": "en", "query_type": "cross_document_compare"},
    )
    assert mismatch_response.status_code == 400
    assert "dataset query_type" in mismatch_response.json()["detail"]


def test_evaluation_run_supports_deterministic_profile_snapshot(client, db_session, app_settings) -> None:
    """benchmark run 應可指定 deterministic profile，並回傳對應 snapshot。"""

    area = Area(id=_uuid(), name="Evaluation Profile Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="profile.md",
        content_type="text/markdown",
        file_size=64,
        storage_key="evaluation/profile.md",
        display_text="Alpha benchmark profile fact.",
        normalized_text="Alpha benchmark profile fact.",
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
        heading="Profile",
        content="Alpha benchmark profile fact.",
        content_preview="Alpha benchmark profile fact.",
        char_count=len("Alpha benchmark profile fact."),
        start_offset=0,
        end_offset=len("Alpha benchmark profile fact."),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, child])
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Profile Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "benchmark profile", "language": "en", "query_type": "fact_lookup"},
    ).json()["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": document.id,
            "start_offset": 0,
            "end_offset": len("Alpha benchmark profile fact."),
            "relevance_grade": 3,
        },
    )

    run_response = client.post(
        f"/evaluation/datasets/{dataset_id}/runs",
        headers={"Authorization": ADMIN_TOKEN},
        json={"top_k": 5, "evaluation_profile": "deterministic_gate_v1"},
    )

    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["run"]["evaluation_profile"] == "deterministic_gate_v1"
    assert run_payload["run"]["config_snapshot"]["top_k"] == 5
    assert run_payload["run"]["config_snapshot"]["rerank"]["provider"] == "deterministic"
    assert run_payload["run"]["config_snapshot"]["rerank"]["top_n"] <= app_settings.rerank_top_n
    assert run_payload["run"]["config_snapshot"]["assembler"]["max_children_per_parent"] <= app_settings.assembler_max_children_per_parent


def test_evaluation_run_supports_guarded_assembler_profile_snapshot(client, db_session, app_settings) -> None:
    """guarded assembler profile 應反映在 config snapshot。"""

    area = Area(id=_uuid(), name="QASPER Recall Depth Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="qasper-depth.md",
        content_type="text/markdown",
        file_size=64,
        storage_key="evaluation/qasper-depth.md",
        display_text="Alpha qasper depth fact.",
        normalized_text="Alpha qasper depth fact.",
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
        heading="QASPER",
        content="Alpha qasper depth fact.",
        content_preview="Alpha qasper depth fact.",
        char_count=len("Alpha qasper depth fact."),
        start_offset=0,
        end_offset=len("Alpha qasper depth fact."),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, child])
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "QASPER Guarded Assembler Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "qasper synopsis", "language": "en", "query_type": "fact_lookup"},
    ).json()["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": document.id,
            "start_offset": 0,
            "end_offset": len("Alpha qasper depth fact."),
            "relevance_grade": 3,
        },
    )

    run_response = client.post(
        f"/evaluation/datasets/{dataset_id}/runs",
        headers={"Authorization": ADMIN_TOKEN},
        json={"top_k": 5, "evaluation_profile": "generic_guarded_assembler_v1"},
    )

    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["run"]["evaluation_profile"] == "generic_guarded_assembler_v1"
    assert run_payload["run"]["config_snapshot"]["retrieval"]["vector_top_k"] == app_settings.retrieval_vector_top_k
    assert run_payload["run"]["config_snapshot"]["retrieval"]["fts_top_k"] == app_settings.retrieval_fts_top_k
    assert run_payload["run"]["config_snapshot"]["retrieval"]["max_candidates"] == app_settings.retrieval_max_candidates
    assert run_payload["run"]["config_snapshot"]["rerank"]["top_n"] >= app_settings.rerank_top_n
    assert run_payload["run"]["config_snapshot"]["assembler"]["max_contexts"] >= app_settings.assembler_max_contexts
    assert run_payload["run"]["config_snapshot"]["assembler"]["max_children_per_parent"] >= app_settings.assembler_max_children_per_parent


def test_evaluation_preview_debug_exposes_recall_ranks_and_runs_rerank_on_demand(client, db_session, app_settings) -> None:
    """preview debug 應先暴露 vector/fts/rrf rank，並可再手動執行 rerank。"""

    area = Area(id=_uuid(), name="Evaluation Debug Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="debug.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="evaluation/debug.md",
        display_text="Alpha debug fact.",
        normalized_text="Alpha debug fact.",
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
        heading="Debug",
        content="Alpha debug fact.",
        content_preview="Alpha debug fact.",
        char_count=len("Alpha debug fact."),
        start_offset=0,
        end_offset=len("Alpha debug fact."),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, child])
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Debug Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "Alpha debug", "language": "en", "query_type": "fact_lookup"},
    ).json()["id"]

    recall_preview = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/candidate-preview",
        headers={"Authorization": ADMIN_TOKEN},
        json={"apply_rerank": False, "retrieval_vector_top_k": 10, "retrieval_fts_top_k": 10, "retrieval_max_candidates": 10},
    )
    assert recall_preview.status_code == 200
    recall_payload = recall_preview.json()
    assert recall_payload["recall"]["items"][0]["vector_rank"] == 1
    assert recall_payload["recall"]["items"][0]["rrf_rank"] == 1
    assert recall_payload["rerank"]["items"] == []
    assert recall_payload["rerank"]["first_hit_rank"] is None

    rerank_preview = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/candidate-preview",
        headers={"Authorization": ADMIN_TOKEN},
        json={"apply_rerank": True, "retrieval_vector_top_k": 10, "retrieval_fts_top_k": 10, "retrieval_max_candidates": 10, "rerank_top_n": 10},
    )
    assert rerank_preview.status_code == 200
    rerank_payload = rerank_preview.json()
    assert rerank_payload["rerank"]["items"]
    assert rerank_payload["rerank"]["items"][0]["rerank_rank"] == 1


def test_evaluation_mark_miss_replaces_existing_spans(client, db_session) -> None:
    """標記 retrieval miss 後應以 miss span 取代既有 spans。"""

    area = Area(id=_uuid(), name="Evaluation Miss Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Miss Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "missing fact", "language": "en", "query_type": "fact_lookup"},
    ).json()["id"]

    miss_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/mark-miss",
        headers={"Authorization": ADMIN_TOKEN},
    )

    assert miss_response.status_code == 200
    assert miss_response.json()["spans"] == [
        {
            "id": miss_response.json()["spans"][0]["id"],
            "document_id": None,
            "start_offset": 0,
            "end_offset": 0,
            "relevance_grade": None,
            "is_retrieval_miss": True,
            "created_by_sub": "user-admin",
            "created_at": miss_response.json()["spans"][0]["created_at"],
        }
    ]


def test_evaluation_preview_and_run_map_rerank_and_assembled_by_runtime_windows(client, db_session, app_settings) -> None:
    """rerank 與 assembled 應以 runtime child windows 判定命中，而非只看粗略 parent 視窗。"""

    area = Area(id=_uuid(), name="Runtime Mapping Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    display_text = "# Policy\n\nAlpha policy keeps zh-TW facts.\n\nBeta policy keeps English facts."
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="runtime-mapping.md",
        content_type="text/markdown",
        file_size=256,
        storage_key="evaluation/runtime-mapping.md",
        display_text=display_text,
        normalized_text=display_text,
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
        heading="Policy",
        content=display_text,
        content_preview="Alpha policy keeps zh-TW facts.",
        char_count=len(display_text),
        start_offset=0,
        end_offset=len(display_text),
    )
    alpha_text = "Alpha policy keeps zh-TW facts."
    alpha_start = display_text.index(alpha_text)
    alpha_end = alpha_start + len(alpha_text)
    alpha_child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Policy",
        content=alpha_text,
        content_preview=alpha_text,
        char_count=len(alpha_text),
        start_offset=alpha_start,
        end_offset=alpha_end,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    beta_text = "Beta policy keeps English facts."
    beta_start = display_text.index(beta_text)
    beta_end = beta_start + len(beta_text)
    beta_child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Policy",
        content=beta_text,
        content_preview=beta_text,
        char_count=len(beta_text),
        start_offset=beta_start,
        end_offset=beta_end,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, parent, alpha_child, beta_child])
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Runtime Mapping Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "zh-TW facts", "language": "zh-TW", "query_type": "fact_lookup"},
    ).json()["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": document.id,
            "start_offset": alpha_start,
            "end_offset": alpha_end,
            "relevance_grade": 3,
        },
    )

    preview_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/candidate-preview",
        headers={"Authorization": ADMIN_TOKEN},
        json={},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["rerank"]["first_hit_rank"] == 1
    assert preview_payload["assembled"]["first_hit_rank"] == 1

    run_response = client.post(
        f"/evaluation/datasets/{dataset_id}/runs",
        headers={"Authorization": ADMIN_TOKEN},
        json={"top_k": 5},
    )
    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["per_query"][0]["recall"]["first_hit_rank"] == preview_payload["recall"]["first_hit_rank"]
    assert run_payload["per_query"][0]["rerank"]["first_hit_rank"] == 1
    assert run_payload["per_query"][0]["assembled"]["first_hit_rank"] == 1
    assert run_payload["per_query"][0]["rerank"]["first_hit_rank"] == preview_payload["rerank"]["first_hit_rank"]
    assert run_payload["per_query"][0]["assembled"]["first_hit_rank"] == preview_payload["assembled"]["first_hit_rank"]


def test_evaluation_preview_and_run_expose_rerank_fallback_reason(client, db_session, app_settings, monkeypatch) -> None:
    """rerank fail-open 時，preview 與 run report 都應暴露 fallback 原因。"""

    area = Area(id=_uuid(), name="Evaluation Fallback Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="fallback.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="evaluation/fallback.md",
        display_text="Alpha fallback fact.",
        normalized_text="Alpha fallback fact.",
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
        heading="Fallback",
        content="Alpha fallback fact.",
        content_preview="Alpha fallback fact.",
        char_count=len("Alpha fallback fact."),
        start_offset=0,
        end_offset=len("Alpha fallback fact."),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, child])
    db_session.commit()

    class FailingRerankProvider:
        """固定拋錯的 rerank provider 測試替身。"""

        def rerank(self, *, query: str, documents: list, top_n: int):
            """模擬 provider runtime failure。"""

            raise RuntimeError("boom")

    monkeypatch.setattr("app.services.retrieval_rerank.build_rerank_provider", lambda settings: FailingRerankProvider())

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Fallback Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "Alpha fallback", "language": "en", "query_type": "fact_lookup"},
    ).json()["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": document.id,
            "start_offset": 0,
            "end_offset": len("Alpha fallback fact."),
            "relevance_grade": 3,
        },
    )

    preview_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/candidate-preview",
        headers={"Authorization": ADMIN_TOKEN},
        json={},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["rerank"]["rerank_applied"] is False
    assert preview_payload["rerank"]["fallback_reason"] == "provider_error"

    run_response = client.post(
        f"/evaluation/datasets/{dataset_id}/runs",
        headers={"Authorization": ADMIN_TOKEN},
        json={"top_k": 5},
    )
    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert run_payload["per_query"][0]["rerank"]["rerank_applied"] is False
    assert run_payload["per_query"][0]["rerank"]["fallback_reason"] == "provider_error"


def test_evaluation_preview_and_run_hide_document_recall_details(client, db_session, app_settings) -> None:
    """document_summary preview 與 run report 不再暴露 document/section recall 明細。"""

    area = Area(id=_uuid(), name="Evaluation Document Recall Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))

    alpha_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤加盟辦法.pdf",
        content_type="application/pdf",
        file_size=128,
        storage_key="evaluation/dantei-policy.pdf",
        display_text="## Alpha\n\nAlpha summary facts.",
        normalized_text="## Alpha\n\nAlpha summary facts.",
        synopsis_text="Alpha summary facts.",
        synopsis_embedding=[0.1] * app_settings.embedding_dimensions,
        status=DocumentStatus.ready,
    )
    beta_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤門市手冊.pdf",
        content_type="application/pdf",
        file_size=128,
        storage_key="evaluation/dantei-manual.pdf",
        display_text="## Beta\n\nBeta summary facts.",
        normalized_text="## Beta\n\nBeta summary facts.",
        synopsis_text="Beta summary facts.",
        synopsis_embedding=[0.2] * app_settings.embedding_dimensions,
        status=DocumentStatus.ready,
    )
    alpha_parent = DocumentChunk(
        id=_uuid(),
        document_id=alpha_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Alpha",
        content="Alpha summary facts.",
        content_preview="Alpha summary facts.",
        char_count=len("Alpha summary facts."),
        start_offset=10,
        end_offset=30,
    )
    beta_parent = DocumentChunk(
        id=_uuid(),
        document_id=beta_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=1,
        child_index=None,
        heading="Beta",
        content="Beta summary facts.",
        content_preview="Beta summary facts.",
        char_count=len("Beta summary facts."),
        start_offset=9,
        end_offset=28,
    )
    alpha_child = DocumentChunk(
        id=_uuid(),
        document_id=alpha_document.id,
        parent_chunk_id=alpha_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Alpha",
        content="Alpha summary facts.",
        content_preview="Alpha summary facts.",
        char_count=len("Alpha summary facts."),
        start_offset=10,
        end_offset=30,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    beta_child = DocumentChunk(
        id=_uuid(),
        document_id=beta_document.id,
        parent_chunk_id=beta_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=3,
        section_index=1,
        child_index=0,
        heading="Beta",
        content="Beta summary facts.",
        content_preview="Beta summary facts.",
        char_count=len("Beta summary facts."),
        start_offset=9,
        end_offset=28,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([alpha_document, beta_document, alpha_parent, beta_parent, alpha_child, beta_child])
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Summary Dataset", "query_type": "document_summary"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "請摘要丹堤加盟辦法", "language": "zh-TW", "query_type": "document_summary"},
    ).json()["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": alpha_document.id,
            "start_offset": 10,
            "end_offset": 30,
            "relevance_grade": 3,
        },
    )

    preview_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/candidate-preview",
        headers={"Authorization": ADMIN_TOKEN},
        json={},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["query_routing"]["summary_scope"] == "single_document"
    assert "document_recall" not in preview_payload
    assert "section_recall" not in preview_payload
    assert "selected_synopsis_level" not in preview_payload

    run_response = client.post(
        f"/evaluation/datasets/{dataset_id}/runs",
        headers={"Authorization": ADMIN_TOKEN},
        json={"top_k": 5},
    )
    assert run_response.status_code == 201
    run_payload = run_response.json()
    assert "document_recall" not in run_payload["per_query"][0]
    assert "section_recall" not in run_payload["per_query"][0]
    assert "selected_synopsis_level" not in run_payload["per_query"][0]


def test_evaluation_adding_same_span_twice_updates_existing_record(client, db_session, app_settings) -> None:
    """重複新增同一個 span 不應 500，且應更新既有 relevance。"""

    area = Area(id=_uuid(), name="Duplicate Span Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="facts.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="evaluation/facts.md",
        display_text="Alpha policy keeps zh-TW facts.",
        normalized_text="Alpha policy keeps zh-TW facts.",
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
        heading="Policy",
        content=document.display_text or "",
        content_preview="Alpha policy keeps zh-TW facts.",
        char_count=len(document.display_text or ""),
        start_offset=0,
        end_offset=len(document.display_text or ""),
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Policy",
        content="Alpha policy keeps zh-TW facts.",
        content_preview="Alpha policy keeps zh-TW facts.",
        char_count=len("Alpha policy keeps zh-TW facts."),
        start_offset=0,
        end_offset=len("Alpha policy keeps zh-TW facts."),
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, parent, child])
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Duplicate Span Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "zh-TW facts", "language": "zh-TW", "query_type": "fact_lookup"},
    ).json()["id"]

    first_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": document.id,
            "start_offset": 0,
            "end_offset": len("Alpha policy keeps zh-TW facts."),
            "relevance_grade": 3,
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "document_id": document.id,
            "start_offset": 0,
            "end_offset": len("Alpha policy keeps zh-TW facts."),
            "relevance_grade": 2,
        },
    )
    assert second_response.status_code == 200
    assert len(second_response.json()["spans"]) == 1
    assert second_response.json()["spans"][0]["relevance_grade"] == 2


def test_evaluation_item_can_be_deleted(client, db_session) -> None:
    """evaluation 題目應可被刪除，且 dataset detail 不再包含該題。"""

    area = Area(id=_uuid(), name="Delete Item Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Delete Item Dataset"},
    ).json()["id"]
    item_id = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "delete me", "language": "en", "query_type": "fact_lookup"},
    ).json()["id"]

    delete_response = client.delete(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}",
        headers={"Authorization": ADMIN_TOKEN},
    )
    assert delete_response.status_code == 204

    detail_response = client.get(
        f"/evaluation/datasets/{dataset_id}",
        headers={"Authorization": ADMIN_TOKEN},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["items"] == []


def test_evaluation_dataset_can_be_deleted(client, db_session) -> None:
    """evaluation dataset 應可被刪除，且 detail route 需回 same-404。"""

    area = Area(id=_uuid(), name="Delete Dataset Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    dataset_id = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "Delete Dataset"},
    ).json()["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": ADMIN_TOKEN},
        json={"query_text": "delete dataset", "language": "en", "query_type": "fact_lookup"},
    )

    delete_response = client.delete(
        f"/evaluation/datasets/{dataset_id}",
        headers={"Authorization": ADMIN_TOKEN},
    )
    assert delete_response.status_code == 204

    list_response = client.get(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": ADMIN_TOKEN},
    )
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []

    detail_response = client.get(
        f"/evaluation/datasets/{dataset_id}",
        headers={"Authorization": ADMIN_TOKEN},
    )
    assert detail_response.status_code == 404
