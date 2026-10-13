"""Benchmark snapshot import/export/compare 腳本測試。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.auth.verifier import CurrentPrincipal
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role
from app.scripts.compare_benchmark_runs import compare_reports
from app.scripts.export_benchmark_snapshot import export_snapshot
from app.scripts.import_benchmark_snapshot import import_snapshot
from app.evaluation.retrieval.datasets import create_evaluation_run, get_evaluation_run_report

def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def test_benchmark_snapshot_round_trip_and_compare(app, client, db_session, app_settings, tmp_path, monkeypatch) -> None:
    """export/import/compare 應可完成 benchmark snapshot round-trip。

    參數：
    - `app`：測試用 FastAPI app。
    - `client`：測試用 HTTP client。
    - `db_session`：測試用資料庫 session。
    - `app_settings`：測試用 app settings。
    - `tmp_path`：pytest 暫存目錄。
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 round-trip 成功。
    """

    area = Area(id=_uuid(), name="Snapshot Source Area")
    import_area = Area(id=_uuid(), name="Snapshot Import Area")
    db_session.add_all([area, import_area])
    db_session.add_all(
        [
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            AreaUserRole(area_id=import_area.id, user_sub="user-admin", role=Role.admin),
        ]
    )

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
    import_document = Document(
        id=_uuid(),
        area_id=import_area.id,
        file_name=document.file_name,
        content_type=document.content_type,
        file_size=document.file_size,
        storage_key="evaluation/import-facts.md",
        display_text=document.display_text,
        normalized_text=document.normalized_text,
        status=DocumentStatus.ready,
    )
    import_parent = DocumentChunk(
        id=_uuid(),
        document_id=import_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Policy",
        content=import_document.display_text or "",
        content_preview="Alpha policy keeps zh-TW facts.",
        char_count=len(import_document.display_text or ""),
        start_offset=0,
        end_offset=len(import_document.display_text or ""),
    )
    import_child = DocumentChunk(
        id=_uuid(),
        document_id=import_document.id,
        parent_chunk_id=import_parent.id,
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
    db_session.add_all([document, parent, child, import_document, import_parent, import_child])
    db_session.commit()

    dataset_payload = client.post(
        f"/areas/{area.id}/evaluation/datasets",
        headers={"Authorization": "Bearer test::user-admin::/group/admin"},
        json={"name": "Snapshot Dataset"},
    ).json()
    dataset_id = dataset_payload["id"]
    item_payload = client.post(
        f"/evaluation/datasets/{dataset_id}/items",
        headers={"Authorization": "Bearer test::user-admin::/group/admin"},
        json={"query_text": "zh-TW facts", "language": "zh-TW", "query_type": "fact_lookup"},
    ).json()
    item_id = item_payload["id"]
    client.post(
        f"/evaluation/datasets/{dataset_id}/items/{item_id}/spans",
        headers={"Authorization": "Bearer test::user-admin::/group/admin"},
        json={
            "document_id": document.id,
            "start_offset": 0,
            "end_offset": len("Alpha policy keeps zh-TW facts."),
            "relevance_grade": 3,
        },
    )

    principal = CurrentPrincipal(sub="user-admin", groups=("/group/admin",))
    report = create_evaluation_run(
        session=db_session,
        principal=principal,
        settings=app_settings,
        dataset_id=dataset_id,
        top_k=5,
        evaluation_profile="deterministic_gate_v1",
    )

    snapshot_dir = tmp_path / "snapshot"
    monkeypatch.setattr("app.scripts.export_benchmark_snapshot.get_settings", lambda: app_settings)
    monkeypatch.setattr("app.scripts.import_benchmark_snapshot.get_settings", lambda: app_settings)

    export_summary = export_snapshot(
        dataset_id=dataset_id,
        output_dir=snapshot_dir,
        benchmark_name="snapshot-test",
        reference_run_id=str(report.run.id),
        actor_sub="user-admin",
        source_doc_root=None,
    )
    assert export_summary["question_count"] == 1
    assert (snapshot_dir / "reference_run_report.json").exists()

    import_summary = import_snapshot(
        snapshot_dir=snapshot_dir,
        area_id=import_area.id,
        dataset_name_override="snapshot-test-imported",
        actor_sub="user-admin",
        replace=True,
    )
    assert import_summary["question_count"] == 1
    assert import_summary["span_count"] == 1
    assert import_summary["replace"] is True

    exported_report = json.loads((snapshot_dir / "reference_run_report.json").read_text(encoding="utf-8"))
    rerun_report = create_evaluation_run(
        session=db_session,
        principal=principal,
        settings=app_settings,
        dataset_id=dataset_id,
        top_k=5,
        evaluation_profile="deterministic_gate_v1",
    )
    live_report = get_evaluation_run_report(
        session=db_session,
        principal=principal,
        run_id=str(rerun_report.run.id),
    ).model_dump(mode="json")
    compare_payload = compare_reports(reference_report=exported_report, candidate_report=live_report)
    assert compare_payload["per_query_diff"]["missing_in_candidate"] == []
    assert compare_payload["per_query_diff"]["extra_in_candidate"] == []
    assert compare_payload["per_query_diff"]["matched_core_evidence_mismatch_count"]["recall"] == 0
    assert compare_payload["summary_metric_deltas"]["recall"]["Recall@k"]["delta"] == 0.0
    assert compare_payload["candidate"]["run_id"] == str(rerun_report.run.id)
    assert import_summary["replace"] is True
