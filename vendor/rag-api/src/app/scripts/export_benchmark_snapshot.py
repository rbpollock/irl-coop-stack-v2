"""將 retrieval evaluation dataset 匯出為 benchmark snapshot package 的 CLI。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth.verifier import CurrentPrincipal
from app.core.settings import get_settings
from app.db.models import Document, RetrievalEvalDataset, RetrievalEvalItem, RetrievalEvalItemSpan, RetrievalEvalRun, RetrievalEvalRunArtifact, utc_now
from app.db.session import create_database_engine, create_session_factory
from app.evaluation.retrieval.datasets import get_evaluation_run_report


# 匯出 package 時固定產生的檔名清單，用於 manifest 與目錄檢查。
PACKAGE_FILES = [
    "documents.jsonl",
    "questions.jsonl",
    "gold_spans.jsonl",
    "per_query.jsonl",
    "runs.jsonl",
    "reference_run_report.json",
    "manifest.json",
]


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI argument parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 benchmark 匯出參數的 parser。
    """

    parser = argparse.ArgumentParser(description="匯出 retrieval evaluation dataset 成 benchmark snapshot。")
    parser.add_argument("--dataset-id", required=True, help="要匯出的 evaluation dataset id。")
    parser.add_argument("--output-dir", required=True, help="輸出目錄。")
    parser.add_argument("--benchmark-name", help="覆寫 benchmark 名稱，預設使用 dataset name。")
    parser.add_argument("--reference-run-id", help="指定 reference run；未提供時使用最新 completed run。")
    parser.add_argument("--actor-sub", default="benchmark-exporter", help="讀取 run report 時使用的 principal sub。")
    parser.add_argument(
        "--source-doc-root",
        help="原始文件根目錄。若提供，manifest 會嘗試補上檔案大小、SHA-256 與實際路徑。",
    )
    return parser


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """將單一 JSON 物件寫入檔案。

    參數：
    - `path`：輸出檔案路徑。
    - `payload`：要寫入的 JSON 物件。

    回傳：
    - `None`：寫入完成時不回傳內容。
    """

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """將 JSON 物件列表寫成 JSONL。

    參數：
    - `path`：輸出檔案路徑。
    - `rows`：逐行輸出的 JSON 物件。

    回傳：
    - `None`：寫入完成時不回傳內容。
    """

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def git_commit_sha() -> str | None:
    """讀取目前工作樹的 git commit SHA。

    參數：
    - 無。

    回傳：
    - `str | None`：目前 commit SHA；若無法取得則回傳 `None`。
    """

    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip() or None
        )
    except Exception:
        return None


def sha256_of_file(path: Path) -> str:
    """計算檔案的 SHA-256。

    參數：
    - `path`：目標檔案路徑。

    回傳：
    - `str`：十六進位 SHA-256 字串。
    """

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def serialize_document(document: Document) -> dict[str, Any]:
    """將 ORM 文件轉成 snapshot `documents.jsonl` 格式。

    參數：
    - `document`：ORM 文件。

    回傳：
    - `dict[str, Any]`：可序列化的文件資料。
    """

    return {
        "document_id": document.id,
        "file_name": document.file_name,
        "content_type": document.content_type,
        "file_size": document.file_size,
        "status": document.status.value if hasattr(document.status, "value") else str(document.status),
        "created_at": document.created_at.isoformat(),
        "area_id": document.area_id,
    }


def serialize_question(item: RetrievalEvalItem) -> dict[str, Any]:
    """將 ORM 題目轉成 snapshot `questions.jsonl` 格式。

    參數：
    - `item`：ORM 題目。

    回傳：
    - `dict[str, Any]`：可序列化的題目資料。
    """

    return {
        "question_id": item.id,
        "dataset_id": item.dataset_id,
        "query_type": item.query_type.value if hasattr(item.query_type, "value") else str(item.query_type),
        "language": item.language.value if hasattr(item.language, "value") else str(item.language),
        "question": item.query_text,
        "notes": item.notes,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def build_source_document_manifest(*, documents: list[Document], source_doc_root: Path | None) -> list[dict[str, Any]]:
    """建立 manifest 內的 source document 清單。

    參數：
    - `documents`：benchmark 涉及的文件。
    - `source_doc_root`：原始文件根目錄；可為空值。

    回傳：
    - `list[dict[str, Any]]`：可寫入 manifest 的文件資訊。
    """

    rows: list[dict[str, Any]] = []
    for document in sorted(documents, key=lambda row: row.file_name):
        row: dict[str, Any] = {
            "file_name": document.file_name,
            "file_size": document.file_size,
        }
        if source_doc_root is not None:
            candidate_path = source_doc_root / document.file_name
            if candidate_path.exists():
                row["local_source_path"] = str(candidate_path.resolve())
                row["file_size"] = candidate_path.stat().st_size
                row["sha256"] = sha256_of_file(candidate_path)
        rows.append(row)
    return rows


def export_snapshot(
    *,
    dataset_id: str,
    output_dir: Path,
    benchmark_name: str | None,
    reference_run_id: str | None,
    actor_sub: str,
    source_doc_root: Path | None,
) -> dict[str, Any]:
    """執行 benchmark snapshot 匯出。

    參數：
    - `dataset_id`：要匯出的 dataset id。
    - `output_dir`：輸出目錄。
    - `benchmark_name`：覆寫 benchmark 名稱；若為空則使用 dataset name。
    - `reference_run_id`：reference run id；若為空則挑最新 completed run。
    - `actor_sub`：讀取 run report 時使用的 principal sub。
    - `source_doc_root`：原始文件根目錄；可為空值。

    回傳：
    - `dict[str, Any]`：匯出摘要。
    """

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    output_dir.mkdir(parents=True, exist_ok=True)

    with session_factory() as session:
        dataset = session.get(RetrievalEvalDataset, dataset_id)
        if dataset is None:
            raise ValueError(f"找不到 dataset：{dataset_id}")

        items = session.scalars(
            select(RetrievalEvalItem).where(RetrievalEvalItem.dataset_id == dataset.id).order_by(RetrievalEvalItem.created_at.asc(), RetrievalEvalItem.id.asc())
        ).all()
        item_ids = [item.id for item in items]
        spans = session.scalars(
            select(RetrievalEvalItemSpan)
            .where(RetrievalEvalItemSpan.item_id.in_(item_ids))
            .order_by(RetrievalEvalItemSpan.created_at.asc(), RetrievalEvalItemSpan.id.asc())
        ).all()
        document_ids = sorted({span.document_id for span in spans if span.document_id})
        documents = session.scalars(
            select(Document).where(Document.id.in_(document_ids)).order_by(Document.file_name.asc())
        ).all()
        documents_by_id = {document.id: document for document in documents}

        runs = session.scalars(
            select(RetrievalEvalRun).where(RetrievalEvalRun.dataset_id == dataset.id).order_by(RetrievalEvalRun.created_at.desc())
        ).all()
        if not runs:
            raise ValueError(f"dataset `{dataset_id}` 尚無任何 run，無法建立 snapshot。")

        selected_run = None
        if reference_run_id:
            for run in runs:
                if str(run.id) == reference_run_id:
                    selected_run = run
                    break
            if selected_run is None:
                raise ValueError(f"找不到指定的 reference run：{reference_run_id}")
        else:
            selected_run = next((run for run in runs if str(run.status) == "EvaluationRunStatus.completed" or getattr(run.status, "value", None) == "completed"), None)
            if selected_run is None:
                selected_run = runs[0]

        principal = CurrentPrincipal(sub=actor_sub, groups=())
        run_report = get_evaluation_run_report(session=session, principal=principal, run_id=selected_run.id)

        artifacts_by_run_id = {
            artifact.run_id: artifact
            for artifact in session.scalars(
                select(RetrievalEvalRunArtifact).where(RetrievalEvalRunArtifact.run_id.in_([run.id for run in runs]))
            ).all()
        }
        try:
            version_row = session.connection().exec_driver_sql("select version_num from alembic_version").first()
        except SQLAlchemyError:
            version_row = None
        alembic_version_num = version_row[0] if version_row else None

        document_rows = [serialize_document(document) for document in documents]
        question_rows = [serialize_question(item) for item in items]
        span_rows: list[dict[str, Any]] = []
        for span in spans:
            document = documents_by_id.get(span.document_id) if span.document_id else None
            span_text = None
            if document is not None and document.display_text is not None:
                span_text = document.display_text[span.start_offset:span.end_offset]
            span_rows.append(
                {
                    "span_id": span.id,
                    "question_id": span.item_id,
                    "document_id": span.document_id,
                    "file_name": document.file_name if document is not None else None,
                    "start_offset": span.start_offset,
                    "end_offset": span.end_offset,
                    "relevance_grade": span.relevance_grade,
                    "is_retrieval_miss": span.is_retrieval_miss,
                    "span_text": span_text,
                    "created_at": span.created_at.isoformat(),
                    "updated_at": span.updated_at.isoformat(),
                }
            )

        run_rows: list[dict[str, Any]] = []
        for run in runs:
            artifact = artifacts_by_run_id.get(run.id)
            report_json = json.loads(artifact.report_json) if artifact is not None else {}
            run_rows.append(
                {
                    "run_id": run.id,
                    "dataset_id": run.dataset_id,
                    "dataset_name": dataset.name,
                    "area_id": dataset.area_id,
                    "evaluation_profile": run.evaluation_profile,
                    "status": run.status.value if hasattr(run.status, "value") else str(run.status),
                    "total_items": run.total_items,
                    "config_snapshot": json.loads(run.config_snapshot),
                    "summary_metrics": report_json.get("summary_metrics"),
                    "created_at": run.created_at.isoformat(),
                    "completed_at": run.completed_at.isoformat() if run.completed_at is not None else None,
                }
            )

        benchmark_name_value = benchmark_name or dataset.name
        matched_core_evidence_counts = {
            stage: sum(1 for row in run_report.per_query if getattr(row, stage).matched_core_evidence)
            for stage in ("recall", "rerank", "assembled")
        }
        manifest_payload = {
            "benchmark_name": benchmark_name_value,
            "snapshot_exported_at": utc_now().isoformat(),
            "repository": {
                "git_commit": git_commit_sha(),
                "alembic_version": alembic_version_num,
            },
            "dataset": {
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "area_id": dataset.area_id,
                "area_name": None,
                "query_type": dataset.query_type.value if hasattr(dataset.query_type, "value") else str(dataset.query_type),
                "language_distribution": {
                    language: sum(1 for item in items if (item.language.value if hasattr(item.language, "value") else str(item.language)) == language)
                    for language in sorted({item.language.value if hasattr(item.language, "value") else str(item.language) for item in items})
                },
                "counts": {
                    "documents": len(documents),
                    "questions": len(items),
                    "gold_spans": len(spans),
                    "retrieval_miss_spans": sum(1 for span in spans if span.is_retrieval_miss),
                },
            },
            "source_documents": build_source_document_manifest(documents=documents, source_doc_root=source_doc_root),
            "reference_run": {
                "run_id": run_report.run.id,
                "evaluation_profile": run_report.run.evaluation_profile,
                "status": run_report.run.status,
                "created_at": run_report.run.created_at.isoformat(),
                "completed_at": run_report.run.completed_at.isoformat() if run_report.run.completed_at else None,
                "total_items": run_report.run.total_items,
                "config_snapshot": run_report.run.config_snapshot,
                "summary_metrics": {stage: metric.model_dump(mode="json") for stage, metric in run_report.summary_metrics.items()},
                "matched_core_evidence_counts": matched_core_evidence_counts,
            },
            "package_files": PACKAGE_FILES,
            "notes": [
                "若要讓第三方重建 ingest，正式公開時應一併提供 source documents。",
                "若要追求更高精度重現，建議加上 document_chunks 與 parser artifacts snapshot。",
            ],
        }

        write_jsonl(output_dir / "documents.jsonl", document_rows)
        write_jsonl(output_dir / "questions.jsonl", question_rows)
        write_jsonl(output_dir / "gold_spans.jsonl", span_rows)
        write_jsonl(output_dir / "per_query.jsonl", [row.model_dump(mode="json") for row in run_report.per_query])
        write_jsonl(output_dir / "runs.jsonl", run_rows)
        write_json(
            output_dir / "reference_run_report.json",
            {
                "run": run_report.run.model_dump(mode="json"),
                "dataset": run_report.dataset.model_dump(mode="json"),
                "summary_metrics": {stage: metric.model_dump(mode="json") for stage, metric in run_report.summary_metrics.items()},
                "breakdowns": [item.model_dump(mode="json") for item in run_report.breakdowns],
                "per_query": [item.model_dump(mode="json") for item in run_report.per_query],
                "baseline_compare": run_report.baseline_compare,
            },
        )
        write_json(output_dir / "manifest.json", manifest_payload)

    return {
        "dataset_id": dataset_id,
        "benchmark_name": benchmark_name_value,
        "output_dir": str(output_dir.resolve()),
        "reference_run_id": run_report.run.id,
        "document_count": len(document_rows),
        "question_count": len(question_rows),
        "span_count": len(span_rows),
        "run_count": len(run_rows),
    }


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：將匯出摘要輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    summary = export_snapshot(
        dataset_id=args.dataset_id,
        output_dir=Path(args.output_dir).resolve(),
        benchmark_name=args.benchmark_name,
        reference_run_id=args.reference_run_id,
        actor_sub=args.actor_sub,
        source_doc_root=Path(args.source_doc_root).resolve() if args.source_doc_root else None,
    )
    print(json.dumps(summary, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
