"""準備 summary/compare benchmark package 的通用 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


def build_parser() -> argparse.ArgumentParser:
    """建立 benchmark package builder CLI parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 builder 指令的 parser。
    """

    parser = argparse.ArgumentParser(description="準備 summary/compare benchmark package。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_source = subparsers.add_parser("prepare-source", help="複製原始文件與 item JSONL 到 workspace。")
    prepare_source.add_argument("--source-documents-dir", required=True, help="原始 source documents 目錄。")
    prepare_source.add_argument("--items-jsonl", required=True, help="原始 items JSONL 路徑。")
    prepare_source.add_argument("--workspace-dir", required=True, help="workspace 輸出目錄。")

    curate_items = subparsers.add_parser("curate-items", help="從 prepared items deterministic 選出 pilot subset。")
    curate_items.add_argument("--workspace-dir", required=True, help="workspace 目錄。")
    curate_items.add_argument("--max-items", type=int, required=True, help="要保留的題數。")

    build_package = subparsers.add_parser("build-package", help="將 curated items 與 source documents materialize 成 benchmark package。")
    build_package.add_argument("--workspace-dir", required=True, help="workspace 目錄。")
    build_package.add_argument("--package-dir", required=True, help="package 輸出目錄。")
    build_package.add_argument("--manifest-json", required=True, help="package manifest JSON 路徑。")

    return parser


def prepare_source(*, source_documents_dir: Path, items_jsonl: Path, workspace_dir: Path) -> dict[str, object]:
    """將原始文件與 items 複製到 workspace。

    參數：
    - `source_documents_dir`：原始 source documents 目錄。
    - `items_jsonl`：原始 item JSONL 路徑。
    - `workspace_dir`：workspace 目錄。

    回傳：
    - `dict[str, object]`：動作摘要。
    """

    prepared_documents_dir = workspace_dir / "source_documents"
    prepared_items_path = workspace_dir / "prepared_items.jsonl"
    prepared_documents_dir.mkdir(parents=True, exist_ok=True)
    for source_file in sorted(source_documents_dir.iterdir()):
        if source_file.is_file():
            shutil.copy2(source_file, prepared_documents_dir / source_file.name)
    shutil.copy2(items_jsonl, prepared_items_path)
    return {
        "workspace_dir": str(workspace_dir),
        "prepared_items_path": str(prepared_items_path),
        "source_document_count": len(list(prepared_documents_dir.glob("*"))),
    }


def curate_items(*, workspace_dir: Path, max_items: int) -> dict[str, object]:
    """從 prepared items deterministic 取前 N 題。

    參數：
    - `workspace_dir`：workspace 目錄。
    - `max_items`：最多保留題數。

    回傳：
    - `dict[str, object]`：curation 摘要。
    """

    prepared_items_path = workspace_dir / "prepared_items.jsonl"
    curated_items_path = workspace_dir / "curated_items.jsonl"
    rows = [line for line in prepared_items_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected_rows = rows[:max_items]
    curated_items_path.write_text("\n".join(selected_rows) + ("\n" if selected_rows else ""), encoding="utf-8")
    return {
        "workspace_dir": str(workspace_dir),
        "prepared_item_count": len(rows),
        "curated_item_count": len(selected_rows),
        "curated_items_path": str(curated_items_path),
    }


def build_package(*, workspace_dir: Path, package_dir: Path, manifest_json: Path) -> dict[str, object]:
    """將 curated workspace materialize 成 benchmark package。

    參數：
    - `workspace_dir`：workspace 目錄。
    - `package_dir`：package 輸出目錄。
    - `manifest_json`：package manifest JSON 檔案。

    回傳：
    - `dict[str, object]`：build 摘要。
    """

    package_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_json, package_dir / "manifest.json")
    shutil.copy2(workspace_dir / "curated_items.jsonl", package_dir / "questions.jsonl")
    source_documents_dir = package_dir / "source_documents"
    source_documents_dir.mkdir(parents=True, exist_ok=True)
    for source_file in sorted((workspace_dir / "source_documents").iterdir()):
        if source_file.is_file():
            shutil.copy2(source_file, source_documents_dir / source_file.name)
    return {
        "package_dir": str(package_dir),
        "question_count": len([line for line in (package_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]),
        "source_document_count": len(list(source_documents_dir.glob("*"))),
    }


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：直接將結果輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare-source":
        summary = prepare_source(
            source_documents_dir=Path(args.source_documents_dir).resolve(),
            items_jsonl=Path(args.items_jsonl).resolve(),
            workspace_dir=Path(args.workspace_dir).resolve(),
        )
    elif args.command == "curate-items":
        summary = curate_items(
            workspace_dir=Path(args.workspace_dir).resolve(),
            max_items=args.max_items,
        )
    else:
        summary = build_package(
            workspace_dir=Path(args.workspace_dir).resolve(),
            package_dir=Path(args.package_dir).resolve(),
            manifest_json=Path(args.manifest_json).resolve(),
        )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
