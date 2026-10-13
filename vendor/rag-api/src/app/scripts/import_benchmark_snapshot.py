"""將 benchmark snapshot JSONL 匯入 retrieval evaluation 資料表的 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from app.core.settings import get_settings
from app.db.models import (
    Document,
    DocumentStatus,
    EvaluationLanguage,
    EvaluationQueryType,
    RetrievalEvalDataset,
    RetrievalEvalItem,
    RetrievalEvalItemSpan,
    RetrievalEvalRun,
    RetrievalEvalRunArtifact,
    utc_now,
)
from app.db.session import create_database_engine, create_session_factory


# benchmark package 內的固定檔名，用於驗證 snapshot 結構完整。
REQUIRED_SNAPSHOT_FILES = (
    "manifest.json",
    "documents.jsonl",
    "questions.jsonl",
    "gold_spans.jsonl",
)


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI argument parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 benchmark 匯入參數的 parser。
    """

    parser = argparse.ArgumentParser(description="匯入 benchmark snapshot 到 retrieval evaluation 資料表。")
    parser.add_argument("--snapshot-dir", required=True, help="benchmark package 目錄。")
    parser.add_argument("--area-id", required=True, help="要匯入到哪一個 area。")
    parser.add_argument("--dataset-name", help="覆寫 snapshot 內的 dataset 名稱。")
    parser.add_argument("--actor-sub", default="benchmark-importer", help="寫入資料時使用的 created_by_sub。")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="若資料庫內已存在相同 dataset id，先刪除再重建。",
    )
    return parser


def read_json(path: Path) -> dict[str, Any]:
    """讀取單一 JSON 檔案。

    參數：
    - `path`：JSON 檔案路徑。

    回傳：
    - `dict[str, Any]`：解析後的 JSON 物件。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """讀取 JSONL 檔案。

    參數：
    - `path`：JSONL 檔案路徑。

    回傳：
    - `list[dict[str, Any]]`：逐行解析後的 JSON 物件列表。
    """

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def validate_snapshot_dir(snapshot_dir: Path) -> None:
    """檢查 snapshot 目錄是否包含必要檔案。

    參數：
    - `snapshot_dir`：benchmark package 目錄。

    回傳：
    - `None`：驗證成功時不回傳內容。

    風險：
    - 若匯入缺檔的 snapshot，可能造成 dataset 與 span 不一致。
    """

    missing_files = [name for name in REQUIRED_SNAPSHOT_FILES if not (snapshot_dir / name).exists()]
    if missing_files:
        raise ValueError(f"snapshot 缺少必要檔案：{', '.join(missing_files)}")


def parse_language(value: str) -> EvaluationLanguage:
    """將 snapshot 中的語言字串轉成 ORM enum。

    參數：
    - `value`：snapshot 內的語言字串。

    回傳：
    - `EvaluationLanguage`：標準化後的語言 enum。
    """

    normalized = {
        "zh_tw": EvaluationLanguage.zh_tw,
        "zh-TW": EvaluationLanguage.zh_tw,
        "en": EvaluationLanguage.en,
        "mixed": EvaluationLanguage.mixed,
    }.get(value)
    if normalized is None:
        raise ValueError(f"不支援的 language：{value}")
    return normalized


def parse_query_type(value: str) -> EvaluationQueryType:
    """將 snapshot 中的題型字串轉成 ORM enum。

    參數：
    - `value`：snapshot 內的題型字串。

    回傳：
    - `EvaluationQueryType`：標準化後的題型 enum。
    """

    normalized = {
        "fact_lookup": EvaluationQueryType.fact_lookup,
        "document_summary": EvaluationQueryType.document_summary,
        "cross_document_compare": EvaluationQueryType.cross_document_compare,
    }.get(value)
    if normalized is None:
        raise ValueError(f"不支援的 query_type：{value}")
    return normalized


def load_ready_documents_by_name(*, session_factory: Any, area_id: str) -> dict[str, Document]:
    """載入指定 area 內可供 span 對應的 ready 文件。

    參數：
    - `session_factory`：資料庫 session factory。
    - `area_id`：目標 area 識別碼。

    回傳：
    - `dict[str, Document]`：以檔名為 key 的 ready 文件映射。
    """

    with session_factory() as session:
        documents = session.scalars(
            select(Document).where(
                Document.area_id == area_id,
                Document.status == DocumentStatus.ready,
            )
        ).all()
    return {document.file_name: document for document in documents}


def import_snapshot(
    *,
    snapshot_dir: Path,
    area_id: str,
    dataset_name_override: str | None,
    actor_sub: str,
    replace: bool,
) -> dict[str, Any]:
    """執行 benchmark snapshot 匯入。

    參數：
    - `snapshot_dir`：benchmark package 目錄。
    - `area_id`：要匯入到的 area 識別碼。
    - `dataset_name_override`：覆寫 dataset 名稱；若為空則使用 manifest 中名稱。
    - `actor_sub`：寫入資料時使用的 actor sub。
    - `replace`：是否允許覆蓋既有 dataset。

    回傳：
    - `dict[str, Any]`：匯入摘要。

    前置條件：
    - 指定 area 中必須已有與 snapshot 同名、且狀態為 `ready` 的文件。

    風險：
    - 此匯入流程依 `file_name` 對回當前 area 中的文件。若外部環境上傳的是不同內容但同名檔案，span offset 可能不再正確。
    """

    validate_snapshot_dir(snapshot_dir)
    manifest = read_json(snapshot_dir / "manifest.json")
    questions = read_jsonl(snapshot_dir / "questions.jsonl")
    spans = read_jsonl(snapshot_dir / "gold_spans.jsonl")

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    ready_documents_by_name = load_ready_documents_by_name(session_factory=session_factory, area_id=area_id)
    missing_documents = sorted(
        {
            span["file_name"]
            for span in spans
            if not span.get("is_retrieval_miss", False) and span.get("file_name") not in ready_documents_by_name
        }
    )
    if missing_documents:
        raise ValueError(
            "指定 area 缺少對應的 ready 文件，無法對回 gold spans："
            + ", ".join(missing_documents)
        )

    dataset_id = manifest["dataset"]["dataset_id"]
    dataset_name = dataset_name_override or manifest["benchmark_name"]
    imported_at = utc_now()

    with session_factory() as session:
        existing_dataset = session.get(RetrievalEvalDataset, dataset_id)
        if existing_dataset is not None:
            if not replace:
                raise ValueError(f"dataset id 已存在：{dataset_id}。若要覆蓋請加上 --replace。")
            existing_item_ids = session.scalars(
                select(RetrievalEvalItem.id).where(RetrievalEvalItem.dataset_id == dataset_id)
            ).all()
            existing_run_ids = session.scalars(
                select(RetrievalEvalRun.id).where(RetrievalEvalRun.dataset_id == dataset_id)
            ).all()
            if existing_run_ids:
                session.execute(
                    delete(RetrievalEvalRunArtifact).where(RetrievalEvalRunArtifact.run_id.in_(existing_run_ids))
                )
                session.execute(delete(RetrievalEvalRun).where(RetrievalEvalRun.id.in_(existing_run_ids)))
            if existing_item_ids:
                session.execute(delete(RetrievalEvalItemSpan).where(RetrievalEvalItemSpan.item_id.in_(existing_item_ids)))
                session.execute(delete(RetrievalEvalItem).where(RetrievalEvalItem.id.in_(existing_item_ids)))
            session.delete(existing_dataset)
            session.flush()

        dataset = RetrievalEvalDataset(
            id=dataset_id,
            area_id=area_id,
            name=dataset_name,
            query_type=parse_query_type(manifest["dataset"]["query_type"]),
            created_by_sub=actor_sub,
            created_at=imported_at,
            updated_at=imported_at,
        )
        session.add(dataset)

        items_by_id: dict[str, RetrievalEvalItem] = {}
        for question in questions:
            item = RetrievalEvalItem(
                id=question["question_id"],
                dataset_id=dataset.id,
                query_type=parse_query_type(question["query_type"]),
                query_text=question["question"],
                language=parse_language(question["language"]),
                notes=question.get("notes"),
                created_at=imported_at,
                updated_at=imported_at,
            )
            session.add(item)
            items_by_id[item.id] = item

        for span_row in spans:
            item_id = span_row["question_id"]
            if item_id not in items_by_id:
                raise ValueError(f"gold span 指向不存在的 question_id：{item_id}")
            document_id: str | None = None
            if not span_row.get("is_retrieval_miss", False):
                document = ready_documents_by_name[span_row["file_name"]]
                document_id = document.id
                display_text = document.display_text or ""
                end_offset = int(span_row["end_offset"])
                if end_offset > len(display_text):
                    raise ValueError(
                        f"文件 `{document.file_name}` 的 span 超出 display_text 範圍："
                        f"{span_row['start_offset']}..{end_offset} > {len(display_text)}"
                    )
            session.add(
                RetrievalEvalItemSpan(
                    id=span_row["span_id"],
                    item_id=item_id,
                    document_id=document_id,
                    start_offset=int(span_row["start_offset"]),
                    end_offset=int(span_row["end_offset"]),
                    relevance_grade=span_row.get("relevance_grade"),
                    is_retrieval_miss=bool(span_row.get("is_retrieval_miss", False)),
                    created_by_sub=actor_sub,
                    created_at=imported_at,
                    updated_at=imported_at,
                )
            )

        session.commit()

    return {
        "benchmark_name": manifest["benchmark_name"],
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "area_id": area_id,
        "question_count": len(questions),
        "span_count": len(spans),
        "mapped_document_count": len({row["file_name"] for row in spans if not row.get("is_retrieval_miss", False)}),
        "replace": replace,
    }


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：將匯入摘要輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    summary = import_snapshot(
        snapshot_dir=Path(args.snapshot_dir).resolve(),
        area_id=args.area_id,
        dataset_name_override=args.dataset_name,
        actor_sub=args.actor_sub,
        replace=args.replace,
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
