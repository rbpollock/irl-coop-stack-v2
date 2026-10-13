"""將官方 UDA benchmark 與 source docs 正規化為現有 external benchmark pipeline 可用的 JSONL。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.scripts.prepare_external_benchmark import flatten_text, now_iso, write_jsonl


# 官方 UDA benchmark subset 與對應 bench 檔名映射。
BENCHMARK_SUBSET_FILES: dict[str, str] = {
    "feta": "bench_feta_qa.json",
    "fin": "bench_fin_qa.json",
    "nq": "bench_nq_qa.json",
    "paper_tab": "bench_paper_tab_qa.json",
    "paper_text": "bench_paper_text_qa.json",
    "tat": "bench_tat_qa.json",
}

# 各 subset 偏好的 source file 副檔名順序。
SUBSET_EXTENSION_PRIORITY: dict[str, tuple[str, ...]] = {
    "feta": (".pdf", ".html", ".htm"),
    "fin": (".pdf",),
    "nq": (".pdf", ".html", ".htm"),
    "paper_tab": (".pdf",),
    "paper_text": (".pdf",),
    "tat": (".pdf",),
}


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 UDA full-source normalization 參數的 parser。
    """

    parser = argparse.ArgumentParser(description="將官方 UDA benchmark 與 source docs 轉成現有 benchmark pipeline 可吃的 JSONL rows。")
    parser.add_argument(
        "--bench-root",
        required=True,
        help="官方 UDA repo 內 `dataset/extended_qa_info_bench` 目錄，或其上層 `dataset` 目錄。",
    )
    parser.add_argument(
        "--source-doc-root",
        required=True,
        help="已下載或解壓的官方 source docs 根目錄；會遞迴搜尋對應檔案。",
    )
    parser.add_argument("--output-path", required=True, help="輸出的 JSONL 檔案。")
    parser.add_argument(
        "--subsets",
        default="feta,fin,nq,paper_tab,paper_text,tat",
        help="要納入的官方 subset，逗號分隔。",
    )
    parser.add_argument("--max-rows", type=int, default=None, help="最多輸出幾列；預設全部。")
    return parser


def resolve_bench_root(path: Path) -> Path:
    """將輸入路徑解析成 bench JSON 所在目錄。

    參數：
    - `path`：`dataset` 或 `extended_qa_info_bench` 路徑。

    回傳：
    - `Path`：實際 bench JSON 目錄。
    """

    if (path / "bench_fin_qa.json").exists():
        return path
    candidate = path / "extended_qa_info_bench"
    if candidate.exists():
        return candidate
    raise ValueError(f"找不到 extended_qa_info_bench 目錄：{path}")


def parse_subset_names(raw_value: str) -> list[str]:
    """解析並驗證 subset 名稱清單。

    參數：
    - `raw_value`：CLI 傳入的 subset 字串。

    回傳：
    - `list[str]`：已驗證的 subset 名稱。
    """

    subset_names = [item.strip() for item in raw_value.split(",") if item.strip()]
    invalid_names = sorted(name for name in subset_names if name not in BENCHMARK_SUBSET_FILES)
    if invalid_names:
        raise ValueError(f"不支援的 UDA subset：{', '.join(invalid_names)}")
    if not subset_names:
        raise ValueError("至少需要一個 subset。")
    return subset_names


def build_source_index(source_doc_root: Path) -> dict[str, list[Path]]:
    """建立 source docs 的檔名索引。

    參數：
    - `source_doc_root`：官方 source docs 根目錄。

    回傳：
    - `dict[str, list[Path]]`：以完整檔名與 stem 為 key 的路徑索引。
    """

    index: dict[str, list[Path]] = {}
    for file_path in sorted(path for path in source_doc_root.rglob("*") if path.is_file()):
        for key in {file_path.name.lower(), file_path.stem.lower()}:
            index.setdefault(key, []).append(file_path)
    return index


def choose_source_file(*, subset: str, document_id: str, source_index: dict[str, list[Path]]) -> Path | None:
    """依 subset 與 document id 選出最適合的 source file。

    參數：
    - `subset`：UDA subset 名稱。
    - `document_id`：官方文件識別碼。
    - `source_index`：source docs 索引。

    回傳：
    - `Path | None`：找到的 source file；若缺少則回傳空值。
    """

    candidates = source_index.get(document_id.lower(), [])
    if not candidates:
        candidates = source_index.get(f"{document_id}.pdf".lower(), []) + source_index.get(f"{document_id}.html".lower(), [])
    if not candidates:
        return None

    extension_priority = SUBSET_EXTENSION_PRIORITY.get(subset, (".pdf", ".html", ".htm", ".md", ".txt"))
    ranked_candidates = sorted(
        candidates,
        key=lambda path: (
            extension_priority.index(path.suffix.lower()) if path.suffix.lower() in extension_priority else len(extension_priority),
            str(path),
        ),
    )
    return ranked_candidates[0]


def extract_answer_text(entry: dict[str, Any]) -> str:
    """從官方 UDA bench entry 擷取短答案文字。

    參數：
    - `entry`：單題 bench payload。

    回傳：
    - `str`：可交給現有 UDA prepare 流程的答案文字。
    """

    answers = entry.get("answers")
    if isinstance(answers, list):
        for answer_row in answers:
            if not isinstance(answer_row, dict):
                continue
            answer_text = flatten_text(answer_row.get("answer"))
            if answer_text:
                return answer_text
    if isinstance(answers, dict):
        for key in ("answer", "str_answer", "short_answer", "long_answer", "exe_answer"):
            answer_text = flatten_text(answers.get(key))
            if answer_text:
                return answer_text
    for key in ("answer", "short_answer", "long_answer"):
        answer_text = flatten_text(entry.get(key))
        if answer_text:
            return answer_text
    return ""


def _flatten_evidence_node(node: Any) -> list[str]:
    """將單一 evidence node 展平成文字片段。

    參數：
    - `node`：巢狀 evidence payload。

    回傳：
    - `list[str]`：攤平後的 evidence 文字列表。
    """

    if node is None:
        return []
    if isinstance(node, str):
        normalized = node.strip()
        return [normalized] if normalized else []
    if isinstance(node, list):
        rows: list[str] = []
        for item in node:
            rows.extend(_flatten_evidence_node(item))
        return rows
    if isinstance(node, dict):
        ordered_keys = (
            "highlighted_evidence",
            "raw_evidence",
            "facts",
            "table_1",
            "table_2",
            "table_3",
            "table_4",
            "table",
            "table_array",
            "pre_text",
            "post_text",
            "context",
            "value",
        )
        rows: list[str] = []
        for key in ordered_keys:
            if key in node:
                rows.extend(_flatten_evidence_node(node[key]))
        if rows:
            return rows
        flattened = flatten_text(node)
        return [flattened] if flattened else []
    flattened = flatten_text(node)
    return [flattened] if flattened else []


def extract_evidence_text(entry: dict[str, Any]) -> str:
    """從官方 UDA bench entry 擷取可供對齊的 evidence 文字。

    參數：
    - `entry`：單題 bench payload。

    回傳：
    - `str`：依優先順序合併後的 evidence 文字。
    """

    evidence_rows = _flatten_evidence_node(entry.get("evidence"))
    if not evidence_rows and "facts" in entry:
        evidence_rows = _flatten_evidence_node(entry.get("facts"))
    if not evidence_rows and "context" in entry:
        evidence_rows = _flatten_evidence_node(entry.get("context"))
    deduped_rows: list[str] = []
    seen_rows: set[str] = set()
    for row in evidence_rows:
        normalized = " ".join(row.split())
        if not normalized or normalized in seen_rows:
            continue
        seen_rows.add(normalized)
        deduped_rows.append(normalized)
    return "\n".join(deduped_rows)


def build_row(*, subset: str, document_id: str, source_file: Path, entry: dict[str, Any], item_index: int) -> dict[str, Any]:
    """建立單一 UDA row contract。

    參數：
    - `subset`：UDA subset 名稱。
    - `document_id`：官方文件識別碼。
    - `source_file`：對應 source file。
    - `entry`：單題 bench payload。
    - `item_index`：subset 內排序索引。

    回傳：
    - `dict[str, Any]`：可供現有 UDA prepare-source 直接使用的 JSON 物件。
    """

    return {
        "subset": subset,
        "document_id": document_id,
        "source_file": str(source_file.resolve()),
        "question": flatten_text(entry.get("question")),
        "answer": extract_answer_text(entry),
        "evidence": extract_evidence_text(entry),
        "source_metadata": {
            "subset": subset,
            "q_uid": entry.get("q_uid"),
            "doc_url": entry.get("doc_url"),
            "answer_type": flatten_text(entry.get("answer_type") or (entry.get("answers") or {}).get("answer_type")),
            "derivation": flatten_text(entry.get("derivation")),
            "program": flatten_text(entry.get("program")),
            "doc_page_uid": flatten_text(entry.get("doc_page_uid")),
            "row_index": item_index,
        },
        "created_at": now_iso(),
    }


def normalize_uda_full_source(
    *,
    bench_root: Path,
    source_doc_root: Path,
    subset_names: list[str],
    output_path: Path,
    max_rows: int | None,
) -> dict[str, Any]:
    """將官方 UDA bench + source docs 正規化為現有 JSONL row contract。

    參數：
    - `bench_root`：官方 UDA bench JSON 目錄。
    - `source_doc_root`：官方 source docs 根目錄。
    - `subset_names`：要納入的 subset。
    - `output_path`：輸出的 JSONL 路徑。
    - `max_rows`：最多輸出幾列；`None` 代表全部。

    回傳：
    - `dict[str, Any]`：normalize 摘要。
    """

    source_index = build_source_index(source_doc_root)
    output_rows: list[dict[str, Any]] = []
    missing_documents: dict[str, set[str]] = {subset: set() for subset in subset_names}
    kept_counts: dict[str, int] = {subset: 0 for subset in subset_names}

    for subset in subset_names:
        subset_path = bench_root / BENCHMARK_SUBSET_FILES[subset]
        payload = json.loads(subset_path.read_text(encoding="utf-8"))
        sorted_document_ids = sorted(payload.keys())
        item_index = 0
        for document_id in sorted_document_ids:
            source_file = choose_source_file(subset=subset, document_id=document_id, source_index=source_index)
            if source_file is None:
                missing_documents[subset].add(document_id)
                continue
            for entry in payload[document_id]:
                output_rows.append(
                    build_row(
                        subset=subset,
                        document_id=document_id,
                        source_file=source_file,
                        entry=entry,
                        item_index=item_index,
                    )
                )
                kept_counts[subset] += 1
                item_index += 1
                if max_rows is not None and len(output_rows) >= max_rows:
                    break
            if max_rows is not None and len(output_rows) >= max_rows:
                break
        if max_rows is not None and len(output_rows) >= max_rows:
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_path, output_rows)
    return {
        "output_path": str(output_path.resolve()),
        "row_count": len(output_rows),
        "subset_counts": kept_counts,
        "missing_document_counts": {subset: len(document_ids) for subset, document_ids in missing_documents.items()},
    }


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：將 normalize 摘要輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    summary = normalize_uda_full_source(
        bench_root=resolve_bench_root(Path(args.bench_root).resolve()),
        source_doc_root=Path(args.source_doc_root).resolve(),
        subset_names=parse_subset_names(args.subsets),
        output_path=Path(args.output_path).resolve(),
        max_rows=args.max_rows,
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
