"""將外部 benchmark 資料集轉成現有 retrieval benchmark snapshot 的 CLI。"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import urllib.parse
import urllib.request
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.core.settings import get_settings
from app.db.models import Document, DocumentStatus
from app.db.session import create_database_engine, create_session_factory


# workspace 內統一使用的中間檔名。
PREPARED_DOCUMENTS_FILE = "prepared_documents.jsonl"
PREPARED_ITEMS_FILE = "prepared_items.jsonl"
FILTERED_ITEMS_FILE = "filtered_items.jsonl"
FILTER_REPORT_FILE = "filter_report.json"
ALIGNMENT_CANDIDATES_FILE = "alignment_candidates.jsonl"
ALIGNMENT_REVIEW_QUEUE_FILE = "alignment_review_queue.jsonl"
ALIGNMENT_REPORT_FILE = "alignment_report.json"
REVIEW_OVERRIDES_FILE = "review_overrides.jsonl"
SOURCE_DOCUMENTS_DIRNAME = "source_documents"

# snapshot 內固定輸出的檔名。
SNAPSHOT_REQUIRED_FILES = (
    "manifest.json",
    "documents.jsonl",
    "questions.jsonl",
    "gold_spans.jsonl",
)

# 若 workspace 存在 reviewer / LLM 覆核產物，snapshot 應一併保留，形成可驗證證據鏈。
OPTIONAL_SNAPSHOT_AUXILIARY_FILES = (
    REVIEW_OVERRIDES_FILE,
    "openai_review_log.jsonl",
)

# curated v1 允許的最大短答案長度，避免把摘要型答案誤收進 fact lookup。
MAX_SHORT_ANSWER_CHARS = 240

# evidence 太長通常代表需要跨段 synthesis，第一版直接排除。
MAX_EVIDENCE_CHARS = 800

# fuzzy 對齊最低接受分數。
FUZZY_ACCEPT_SCORE = 0.92

# fuzzy 第一名與第二名至少要拉開的分數差距。
FUZZY_ACCEPT_MARGIN = 0.05

# Hugging Face dataset server 的 rows API。
HF_DATASET_ROWS_API = "https://datasets-server.huggingface.co/rows"

# `prepare-source --input-path` 可接受的 Hugging Face pseudo path scheme。
HF_DATASET_REF_SCHEME = "hf://"

# MS MARCO 建檔時最多保留多少非 selected passages 作為噪音上下文。
MSMARCO_MAX_CONTEXT_PASSAGES = 3

# MS MARCO 官方 QA dataset 用來表示無答案的字串。
MSMARCO_NO_ANSWER = "No Answer Present."

# 向 dataset server 取 rows 時每批拉取的大小。
MSMARCO_ROWS_BATCH_SIZE = 100

# NQ evidence context 會保留答案前後多少 token，避免 gold span 過短且不易 disambiguate。
NQ_EVIDENCE_CONTEXT_WINDOW_TOKENS = 48

# DuReader evidence context 會保留答案前後多少字元，降低短答案在 bundle 內多重命中的風險。
DUREADER_EVIDENCE_CONTEXT_WINDOW_CHARS = 120

# DRCD evidence context 會保留答案前後多少字元，降低過短中文答案的多重命中。
DRCD_EVIDENCE_CONTEXT_WINDOW_CHARS = 80


@dataclass(slots=True)
class NormalizedText:
    """保存正規化文字與回推原始 offset 的索引。"""

    normalized_text: str
    normalized_to_original: list[int]


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析外部 benchmark curation 指令的 parser。
    """

    parser = argparse.ArgumentParser(description="將 QASPER / UDA / MS MARCO / NQ / DuReader / DRCD 類外部資料集轉成現有 retrieval benchmark snapshot。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare-source")
    prepare_parser.add_argument("--dataset", choices=["qasper", "uda", "msmarco", "nq", "dureader", "drcd"], required=True)
    prepare_parser.add_argument(
        "--input-path",
        required=True,
        help="外部資料集檔案、目錄，或 `hf://microsoft/ms_marco/v1.1/validation` 這類 Hugging Face dataset 參照。",
    )
    prepare_parser.add_argument("--workspace-dir", required=True, help="中間產物輸出目錄。")
    prepare_parser.add_argument("--limit-documents", type=int, default=None)
    prepare_parser.add_argument("--limit-items", type=int, default=None)

    filter_parser = subparsers.add_parser("filter-items")
    filter_parser.add_argument("--workspace-dir", required=True)

    align_parser = subparsers.add_parser("align-spans")
    align_parser.add_argument("--workspace-dir", required=True)
    align_parser.add_argument("--area-id", required=True)

    build_parser_cmd = subparsers.add_parser("build-snapshot")
    build_parser_cmd.add_argument("--workspace-dir", required=True)
    build_parser_cmd.add_argument("--output-dir", required=True)
    build_parser_cmd.add_argument("--benchmark-name", required=True)
    build_parser_cmd.add_argument("--include-review-items", action="store_true")
    build_parser_cmd.add_argument(
        "--target-question-count",
        type=int,
        default=None,
        help="若提供，僅保留前 N 題已核准題目，且若不足 N 題則直接失敗。",
    )
    build_parser_cmd.add_argument(
        "--reference-evaluation-profile",
        default=None,
        help="snapshot manifest 內要標記的正式 benchmark profile。",
    )

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--workspace-dir", required=True)
    return parser


def ensure_workspace_dir(workspace_dir: Path) -> None:
    """建立 benchmark curation workspace。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `None`：若目錄不存在則建立。
    """

    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / SOURCE_DOCUMENTS_DIRNAME).mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    """讀取 JSON 檔案。

    參數：
    - `path`：JSON 路徑。

    回傳：
    - `Any`：解析後的 JSON payload。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def read_json_from_url(url: str) -> dict[str, Any]:
    """從 URL 讀取 JSON payload。

    參數：
    - `url`：可直接 GET 的 JSON URL。

    回傳：
    - `dict[str, Any]`：解析後的 JSON 物件。
    """

    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """讀取 JSONL 檔案。

    參數：
    - `path`：JSONL 路徑。

    回傳：
    - `list[dict[str, Any]]`：逐行 JSON 物件。
    """

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """將 JSON payload 寫入檔案。

    參數：
    - `path`：目標檔案。
    - `payload`：可序列化物件。

    回傳：
    - `None`：寫入完成。
    """

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """將 JSONL rows 寫入檔案。

    參數：
    - `path`：目標檔案。
    - `rows`：逐行物件。

    回傳：
    - `None`：寫入完成。
    """

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_hf_dataset_reference(input_reference: str) -> tuple[str, str, str] | None:
    """解析 `hf://dataset/config/split` 形式的 Hugging Face dataset 參照。

    參數：
    - `input_reference`：CLI 傳入的 input 參照。

    回傳：
    - `tuple[str, str, str] | None`：回傳 `(dataset_name, config_name, split_name)`；若不是 `hf://` 參照則回傳空值。
    """

    if not input_reference.startswith(HF_DATASET_REF_SCHEME):
        return None

    raw_path = input_reference[len(HF_DATASET_REF_SCHEME) :].strip("/")
    parts = [part for part in raw_path.split("/") if part]
    if len(parts) < 4:
        raise ValueError("Hugging Face dataset 參照必須是 `hf://<namespace>/<dataset>/<config>/<split>`。")

    dataset_name = "/".join(parts[:-2])
    config_name = parts[-2]
    split_name = parts[-1]
    if not dataset_name or not config_name or not split_name:
        raise ValueError("Hugging Face dataset 參照缺少 dataset/config/split。")
    return dataset_name, config_name, split_name


def slugify_filename(value: str, *, suffix: str) -> str:
    """將字串轉成安全檔名。

    參數：
    - `value`：原始名稱。
    - `suffix`：檔名副檔名。

    回傳：
    - `str`：安全檔名。
    """

    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-") or "document"
    return f"{stem}{suffix}"


def now_iso() -> str:
    """回傳目前 UTC ISO 時間字串。

    參數：
    - 無。

    回傳：
    - `str`：ISO 8601 時間字串。
    """

    return datetime.now(UTC).isoformat()


def stable_uuid(value: str) -> str:
    """依固定字串產生穩定 UUID。

    參數：
    - `value`：穩定輸入字串。

    回傳：
    - `str`：UUID5 字串。
    """

    return str(uuid5(NAMESPACE_URL, value))


def flatten_text(value: Any) -> str:
    """將巢狀文字 payload 攤平成單一字串。

    參數：
    - `value`：可能為字串、list、dict 的資料。

    回傳：
    - `str`：展平成單一字串後的內容。
    """

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [flatten_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for candidate_key in ("text", "paragraph", "content", "value", "sentence"):
            if candidate_key in value:
                return flatten_text(value[candidate_key])
        return ""
    return str(value).strip()


def normalize_nested_sequence(value: Any) -> list[Any]:
    """將 list-like / numpy-like 結構轉成 Python list。

    參數：
    - `value`：原始欄位值。

    回傳：
    - `list[Any]`：正規化後的 list。
    """

    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    to_list = getattr(value, "tolist", None)
    if callable(to_list):
        converted = to_list()
        if isinstance(converted, list):
            return converted
        if isinstance(converted, tuple):
            return list(converted)
    return [value]


def normalize_newlines(text: str) -> str:
    """統一換行並清掉多餘空白。

    參數：
    - `text`：原始字串。

    回傳：
    - `str`：清理後文字。
    """

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def build_qasper_markdown(record: dict[str, Any]) -> str:
    """將 QASPER paper record 轉成 Markdown 文件。

    參數：
    - `record`：單篇 paper 原始資料。

    回傳：
    - `str`：可寫入 repo 的 Markdown 內容。
    """

    title = flatten_text(record.get("title")) or flatten_text(record.get("paper_title")) or "Untitled Paper"
    abstract = flatten_text(record.get("abstract"))
    sections = record.get("full_text") or record.get("sections") or []

    blocks = [f"# {title}"]
    if abstract:
        blocks.extend(["", "## Abstract", "", abstract])

    for section in sections:
        heading = flatten_text(section.get("section_name") or section.get("heading") or section.get("title")) or "Section"
        paragraphs = section.get("paragraphs") or section.get("text") or section.get("contents") or []
        paragraph_text = flatten_text(paragraphs)
        if not paragraph_text:
            continue
        blocks.extend(["", f"## {heading}", "", paragraph_text])
    return normalize_newlines("\n".join(blocks)) + "\n"


def extract_qasper_answer_bundle(raw_answers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """從多個 annotator answer 中挑出最適合 benchmark 的一筆。

    參數：
    - `raw_answers`：QASPER answers 陣列。

    回傳：
    - `dict[str, Any] | None`：整理後的 answer bundle；若無可用答案則回傳空值。
    """

    for raw_answer in raw_answers:
        answer_payload = raw_answer.get("answer") if isinstance(raw_answer, dict) else None
        if not isinstance(answer_payload, dict):
            continue
        if answer_payload.get("unanswerable"):
            continue
        yes_no = answer_payload.get("yes_no") or answer_payload.get("yes_no_answer")
        if isinstance(yes_no, bool):
            continue
        if isinstance(yes_no, str) and yes_no.lower() in {"yes", "no"}:
            continue

        extractive_spans = [span.strip() for span in answer_payload.get("extractive_spans", []) if isinstance(span, str) and span.strip()]
        evidence_nodes = answer_payload.get("evidence") or raw_answer.get("evidence") or []
        evidence_texts = [flatten_text(node) for node in evidence_nodes]
        evidence_texts = [text for text in evidence_texts if text]
        answer_text = flatten_text(
            answer_payload.get("free_form_answer")
            or answer_payload.get("extractive_answer")
            or raw_answer.get("free_form_answer")
        )
        if not extractive_spans and not evidence_texts:
            continue
        if answer_text and len(answer_text) > MAX_SHORT_ANSWER_CHARS:
            continue
        return {
            "answer_text": answer_text,
            "evidence_texts": extractive_spans or evidence_texts,
            "answer_type": "extractive" if extractive_spans else "evidence_only",
            "raw_answer": raw_answer,
        }
    return None


def prepare_qasper_source(*, input_path: Path, workspace_dir: Path, limit_documents: int | None, limit_items: int | None) -> dict[str, Any]:
    """將 QASPER 原始資料轉成中間格式與 source documents。

    參數：
    - `input_path`：QASPER JSON 檔。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    raw_payload = read_json(input_path)
    if isinstance(raw_payload, dict):
        raw_records = list(raw_payload.values())
    elif isinstance(raw_payload, list):
        raw_records = raw_payload
    else:
        raise ValueError("QASPER input 必須是 JSON object 或 JSON array。")

    documents: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME

    for record_index, record in enumerate(raw_records):
        if limit_documents is not None and len(documents) >= limit_documents:
            break
        paper_id = str(record.get("paper_id") or record.get("id") or record.get("title") or f"qasper-paper-{record_index}")
        file_name = slugify_filename(paper_id, suffix=".md")
        markdown = build_qasper_markdown(record)
        output_path = source_dir / file_name
        output_path.write_text(markdown, encoding="utf-8")

        document_row = {
            "dataset": "qasper",
            "source_document_id": paper_id,
            "file_name": file_name,
            "title": flatten_text(record.get("title") or record.get("paper_title")) or paper_id,
            "source_path": str(output_path.resolve()),
            "content_type": "text/markdown",
            "created_at": now_iso(),
        }
        documents.append(document_row)

        question_groups = record.get("qas") or record.get("questions") or []
        for question_index, question_entry in enumerate(question_groups):
            if limit_items is not None and len(items) >= limit_items:
                break
            question_text = flatten_text(question_entry.get("question") or question_entry.get("query"))
            raw_answers = question_entry.get("answers") or question_entry.get("answer") or []
            if isinstance(raw_answers, dict):
                raw_answers = [raw_answers]
            answer_bundle = extract_qasper_answer_bundle(raw_answers)
            item_id = stable_uuid(f"qasper::{paper_id}::{question_index}::{question_text}")
            items.append(
                {
                    "item_id": item_id,
                    "dataset": "qasper",
                    "source_document_id": paper_id,
                    "file_name": file_name,
                    "query_text": question_text,
                    "language": "en",
                    "query_type": "fact_lookup",
                    "answer_text": answer_bundle["answer_text"] if answer_bundle else "",
                    "evidence_texts": answer_bundle["evidence_texts"] if answer_bundle else [],
                    "answer_type": answer_bundle["answer_type"] if answer_bundle else "missing",
                    "source_question_index": question_index,
                    "source_metadata": {
                        "question_id": question_entry.get("question_id"),
                        "paper_id": paper_id,
                    },
                    "created_at": now_iso(),
                }
            )
        if limit_items is not None and len(items) >= limit_items:
            break

    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "qasper",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def read_table_like_rows(input_path: Path) -> list[dict[str, Any]]:
    """讀取 CSV / JSON / JSONL 的列資料。

    參數：
    - `input_path`：輸入檔案。

    回傳：
    - `list[dict[str, Any]]`：列資料。
    """

    if input_path.is_dir():
        raise ValueError("UDA input 目前需提供單一檔案。")
    suffix = input_path.suffix.lower()
    if suffix == ".jsonl":
        return read_jsonl(input_path)
    if suffix == ".json":
        try:
            payload = read_json(input_path)
        except json.JSONDecodeError:
            return read_jsonl(input_path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            rows = payload.get("data") or payload.get("rows")
            if isinstance(rows, list):
                return rows
            return [payload]
        raise ValueError("JSON input 必須是 rows list，或逐行 JSON 的 JSONL-like `.json`。")
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with input_path.open("r", encoding="utf-8") as file:
            return list(csv.DictReader(file, delimiter=delimiter))
    raise ValueError("UDA input 只支援 .json / .jsonl / .csv / .tsv。")


def iter_hf_dataset_rows(*, dataset_name: str, config_name: str, split_name: str) -> Any:
    """逐批讀取 Hugging Face dataset server rows。

    參數：
    - `dataset_name`：資料集名稱。
    - `config_name`：config 名稱。
    - `split_name`：split 名稱。

    回傳：
    - `Any`：可迭代的 row dict 產生器。
    """

    offset = 0
    while True:
        query_string = urllib.parse.urlencode(
            {
                "dataset": dataset_name,
                "config": config_name,
                "split": split_name,
                "offset": offset,
                "length": MSMARCO_ROWS_BATCH_SIZE,
            }
        )
        payload = read_json_from_url(f"{HF_DATASET_ROWS_API}?{query_string}")
        rows = payload.get("rows", [])
        if not rows:
            break
        for row_wrapper in rows:
            if isinstance(row_wrapper, dict) and isinstance(row_wrapper.get("row"), dict):
                yield row_wrapper["row"]
            elif isinstance(row_wrapper, dict):
                yield row_wrapper
        offset += len(rows)


def resolve_prepare_source_rows(input_reference: Path | str) -> Any:
    """依輸入參照回傳可供 `prepare-source` 使用的列資料。

    參數：
    - `input_reference`：本機檔案路徑或 `hf://` 參照。

    回傳：
    - `Any`：可迭代的 row dict 序列。
    """

    if isinstance(input_reference, str):
        hf_reference = parse_hf_dataset_reference(input_reference)
        if hf_reference is not None:
            dataset_name, config_name, split_name = hf_reference
            return iter_hf_dataset_rows(
                dataset_name=dataset_name,
                config_name=config_name,
                split_name=split_name,
            )
        input_path = Path(input_reference).resolve()
    else:
        input_path = input_reference
    return read_table_like_rows(input_path)


def first_present(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    """依序取出第一個存在且非空的欄位。

    參數：
    - `row`：列資料。
    - `keys`：候選欄位名。

    回傳：
    - `str`：找到的值；若全部不存在則為空字串。
    """

    for key in keys:
        value = flatten_text(row.get(key))
        if value:
            return value
    return ""


def build_uda_document_content(row: dict[str, Any]) -> str:
    """從 UDA row 中取出可線性化的文件內容。

    參數：
    - `row`：原始列資料。

    回傳：
    - `str`：文件文字內容。
    """

    return first_present(
        row,
        (
            "document_text",
            "doc_text",
            "context",
            "content",
            "passage",
            "source_text",
            "document_content",
        ),
    )


def extract_msmarco_answer(row: dict[str, Any]) -> tuple[str, str]:
    """從 MS MARCO row 挑出最適合 benchmark 的答案文字。

    參數：
    - `row`：MS MARCO 單列資料。

    回傳：
    - `tuple[str, str]`：`(answer_text, answer_type)`；若沒有可用答案則 `answer_text` 會是空字串。
    """

    well_formed_answers = [
        answer.strip()
        for answer in normalize_nested_sequence(row.get("wellFormedAnswers"))
        if isinstance(answer, str) and answer.strip() and answer.strip() != "[]"
    ]
    if well_formed_answers:
        return well_formed_answers[0], "well_formed_answer"

    answers = [
        answer.strip()
        for answer in normalize_nested_sequence(row.get("answers"))
        if isinstance(answer, str) and answer.strip() and answer.strip() != MSMARCO_NO_ANSWER
    ]
    if answers:
        return answers[0], "short_answer"
    return "", "missing"


def extract_msmarco_passages(row: dict[str, Any], *, selected_only: bool) -> list[dict[str, str]]:
    """從 MS MARCO row 抽出 selected 或 context passages。

    參數：
    - `row`：MS MARCO 單列資料。
    - `selected_only`：是否只保留官方 `is_selected=1` 的 passages。

    回傳：
    - `list[dict[str, str]]`：包含 `text` 與 `url` 的 passages 列表。
    """

    passages = row.get("passages") if isinstance(row.get("passages"), dict) else {}
    selected_flags = normalize_nested_sequence(passages.get("is_selected"))
    passage_texts = normalize_nested_sequence(passages.get("passage_text"))
    passage_urls = normalize_nested_sequence(passages.get("url"))

    results: list[dict[str, str]] = []
    for index, passage_text in enumerate(passage_texts):
        if not isinstance(passage_text, str) or not passage_text.strip():
            continue
        is_selected = int(selected_flags[index]) == 1 if index < len(selected_flags) else False
        if selected_only != is_selected:
            continue
        url = passage_urls[index].strip() if index < len(passage_urls) and isinstance(passage_urls[index], str) else ""
        results.append(
            {
                "text": passage_text.strip(),
                "url": url,
            }
        )
    return results


def build_msmarco_document_content(*, query_id: str, selected_passages: list[dict[str, str]], context_passages: list[dict[str, str]]) -> str:
    """將 MS MARCO row 轉成可上傳的 Markdown 文件。

    參數：
    - `query_id`：原始 query id。
    - `selected_passages`：官方標記為 selected 的 passages。
    - `context_passages`：額外保留的非 selected passages。

    回傳：
    - `str`：可寫入 repo 的 Markdown 內容。
    """

    blocks = [f"# MS MARCO Snippet Bundle {query_id}"]

    for index, passage in enumerate(selected_passages, start=1):
        blocks.extend(["", f"## Selected Passage {index}"])
        if passage["url"]:
            blocks.extend(["", f"Source URL: {passage['url']}"])
        blocks.extend(["", passage["text"]])

    for index, passage in enumerate(context_passages[:MSMARCO_MAX_CONTEXT_PASSAGES], start=1):
        blocks.extend(["", f"## Context Passage {index}"])
        if passage["url"]:
            blocks.extend(["", f"Source URL: {passage['url']}"])
        blocks.extend(["", passage["text"]])

    return normalize_newlines("\n".join(blocks)) + "\n"


def prepare_msmarco_source(
    *,
    input_reference: Path | str,
    workspace_dir: Path,
    limit_documents: int | None,
    limit_items: int | None,
) -> dict[str, Any]:
    """將 MS MARCO QA rows 轉成中間格式與 source documents。

    參數：
    - `input_reference`：本機檔案路徑或 `hf://` dataset 參照。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME
    documents: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    for row_index, raw_row in enumerate(resolve_prepare_source_rows(input_reference)):
        row = raw_row if isinstance(raw_row, dict) else {}
        query_text = first_present(row, ("query", "question"))
        if not query_text:
            continue

        answer_text, answer_type = extract_msmarco_answer(row)
        selected_passages = extract_msmarco_passages(row, selected_only=True)
        if not answer_text or not selected_passages:
            continue

        if limit_documents is not None and len(documents) >= limit_documents:
            break
        if limit_items is not None and len(items) >= limit_items:
            break

        query_id = first_present(row, ("query_id", "id")) or f"msmarco-query-{row_index}"
        file_name = slugify_filename(f"msmarco-{query_id}", suffix=".md")
        source_document_path = source_dir / file_name
        context_passages = extract_msmarco_passages(row, selected_only=False)
        source_document_path.write_text(
            build_msmarco_document_content(
                query_id=query_id,
                selected_passages=selected_passages,
                context_passages=context_passages,
            ),
            encoding="utf-8",
        )

        documents.append(
            {
                "dataset": "msmarco",
                "source_document_id": query_id,
                "file_name": file_name,
                "title": f"MS MARCO Snippet Bundle {query_id}",
                "source_path": str(source_document_path.resolve()),
                "content_type": "text/markdown",
                "created_at": now_iso(),
            }
        )
        items.append(
            {
                "item_id": stable_uuid(f"msmarco::{query_id}::{query_text}"),
                "dataset": "msmarco",
                "source_document_id": query_id,
                "file_name": file_name,
                "query_text": query_text,
                "language": "en",
                "query_type": "fact_lookup",
                "answer_text": answer_text,
                "evidence_texts": [answer_text],
                "answer_type": answer_type,
                "source_question_index": row_index,
                "source_metadata": {
                    "query_id": query_id,
                    "original_query_type": first_present(row, ("query_type",)),
                    "selected_passage_count": len(selected_passages),
                    "context_passage_count": len(context_passages[:MSMARCO_MAX_CONTEXT_PASSAGES]),
                    "selected_urls": [passage["url"] for passage in selected_passages if passage["url"]],
                },
                "created_at": now_iso(),
            }
        )

    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "msmarco",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def normalize_nq_tag_name(token: str) -> str:
    """從 HTML token 中抽出標籤名稱。

    參數：
    - `token`：NQ `document.tokens.token` 內的 HTML token。

    回傳：
    - `str`：去除 `< > /` 與屬性後的大寫標籤名；若不是可辨識 HTML token 則回傳空字串。
    """

    matched = re.match(r"<\s*/?\s*([A-Za-z0-9]+)", token.strip())
    if not matched:
        return ""
    return matched.group(1).upper()


def should_insert_nq_block_break(token: str) -> bool:
    """判斷某個 HTML token 是否應在純文字輸出中形成段落分隔。

    參數：
    - `token`：HTML token。

    回傳：
    - `bool`：若此標籤應轉成段落/區塊換行則回傳真值。
    """

    return normalize_nq_tag_name(token) in {
        "P",
        "DIV",
        "TR",
        "LI",
        "UL",
        "OL",
        "TABLE",
        "TBODY",
        "THEAD",
        "TD",
        "TH",
        "DD",
        "DT",
        "SECTION",
        "ARTICLE",
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
        "BR",
        "HR",
    }


def normalize_nq_rendered_text(text: str) -> str:
    """清理 NQ token 線性化後的標點與空白。

    參數：
    - `text`：原始渲染字串。

    回傳：
    - `str`：清理後的文字。
    """

    normalized = normalize_newlines(text)
    normalized = re.sub(r"[ \t]+([,.;:!?%)\]\}])", r"\1", normalized)
    normalized = re.sub(r"([(\[\{])\s+", r"\1", normalized)
    normalized = re.sub(r"\s+([’'])\s*", r"\1", normalized)
    normalized = re.sub(r"([A-Za-z])\s+([’']s\b)", r"\1\2", normalized)
    normalized = re.sub(r"\s{2,}", " ", normalized)
    normalized = re.sub(r"\n +", "\n", normalized)
    return normalized.strip()


def render_nq_tokens_to_text(
    tokens: dict[str, list[Any]],
    *,
    start_token: int = 0,
    end_token: int | None = None,
) -> str:
    """將 NQ `document.tokens` 轉成較乾淨的純文字。

    參數：
    - `tokens`：NQ 文件 token 欄位。
    - `start_token`：要渲染的起始 token index（含）。
    - `end_token`：要渲染的結束 token index（不含）；未提供時代表直到結尾。

    回傳：
    - `str`：線性化後的純文字。
    """

    token_values = normalize_nested_sequence(tokens.get("token"))
    html_flags = normalize_nested_sequence(tokens.get("is_html"))
    if end_token is None:
        end_token = len(token_values)

    rendered_parts: list[str] = []
    previous_was_break = True
    for token_index in range(max(0, start_token), min(end_token, len(token_values))):
        token_value = token_values[token_index]
        is_html = bool(html_flags[token_index]) if token_index < len(html_flags) else False
        if not isinstance(token_value, str):
            continue
        if is_html:
            if should_insert_nq_block_break(token_value) and rendered_parts and not previous_was_break:
                rendered_parts.append("\n\n")
                previous_was_break = True
            continue
        cleaned_token = html.unescape(token_value).strip()
        if not cleaned_token:
            continue
        if rendered_parts and not previous_was_break:
            rendered_parts.append(" ")
        rendered_parts.append(cleaned_token)
        previous_was_break = False

    return normalize_nq_rendered_text("".join(rendered_parts))


def find_nq_body_start_token(tokens: dict[str, list[Any]]) -> int:
    """尋找 NQ 文件正文起始 token，盡量略過頁首重複 title。

    參數：
    - `tokens`：NQ 文件 token 欄位。

    回傳：
    - `int`：建議的正文起始 token index。
    """

    token_values = normalize_nested_sequence(tokens.get("token"))
    html_flags = normalize_nested_sequence(tokens.get("is_html"))
    for index, token_value in enumerate(token_values):
        is_html = bool(html_flags[index]) if index < len(html_flags) else False
        if is_html and isinstance(token_value, str) and token_value.upper() == "</H1>":
            return index + 1
    return 0


def build_nq_short_answer_text(short_answer_row: dict[str, Any]) -> str:
    """將單一 annotator 的 short answers 合併成答案字串。

    參數：
    - `short_answer_row`：NQ annotation 內單一 `short_answers` row。

    回傳：
    - `str`：合併後答案；若沒有有效 short answers 則為空字串。
    """

    parts = [part.strip() for part in normalize_nested_sequence(short_answer_row.get("text")) if isinstance(part, str) and part.strip()]
    if not parts:
        return ""
    return "; ".join(parts)


def normalize_nq_answer_key(answer_text: str) -> str:
    """將 NQ short answer 正規化為可做 majority vote 的 key。

    參數：
    - `answer_text`：原始答案文字。

    回傳：
    - `str`：正規化 key。
    """

    return re.sub(r"\s+", " ", answer_text.strip()).lower()


def select_nq_annotation(row: dict[str, Any]) -> dict[str, Any] | None:
    """從 NQ 多位 annotator 中挑出最適合 benchmark 的一筆。

    參數：
    - `row`：單筆 NQ row。

    回傳：
    - `dict[str, Any] | None`：被選中的 annotation bundle；若無可用 short answer 則回傳空值。
    """

    annotations = row.get("annotations") if isinstance(row.get("annotations"), dict) else {}
    short_answers = normalize_nested_sequence(annotations.get("short_answers"))
    long_answers = normalize_nested_sequence(annotations.get("long_answer"))
    annotation_ids = normalize_nested_sequence(annotations.get("id"))

    candidates: list[dict[str, Any]] = []
    answer_counter: Counter[str] = Counter()

    for index, short_answer_row in enumerate(short_answers):
        if not isinstance(short_answer_row, dict):
            continue
        answer_text = build_nq_short_answer_text(short_answer_row)
        if not answer_text:
            continue
        long_answer_row = long_answers[index] if index < len(long_answers) and isinstance(long_answers[index], dict) else {}
        candidate = {
            "annotation_index": index,
            "annotation_id": annotation_ids[index] if index < len(annotation_ids) else "",
            "answer_text": answer_text,
            "answer_key": normalize_nq_answer_key(answer_text),
            "short_answer_row": short_answer_row,
            "long_answer_row": long_answer_row,
            "has_long_answer": int(long_answer_row.get("candidate_index", -1) >= 0),
        }
        candidates.append(candidate)
        answer_counter[candidate["answer_key"]] += 1

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: (
            -answer_counter[candidate["answer_key"]],
            -candidate["has_long_answer"],
            len(candidate["answer_text"]),
            candidate["annotation_index"],
        )
    )
    return candidates[0]


def clamp_nq_token_range(*, start_token: int, end_token: int, token_count: int) -> tuple[int, int]:
    """將 NQ token range 壓回合法範圍。

    參數：
    - `start_token`：起始 token index。
    - `end_token`：結束 token index（不含）。
    - `token_count`：文件總 token 數。

    回傳：
    - `tuple[int, int]`：合法的 `(start_token, end_token)`。
    """

    normalized_start = max(0, min(start_token, token_count))
    normalized_end = max(normalized_start, min(end_token, token_count))
    return normalized_start, normalized_end


def build_nq_evidence_text(tokens: dict[str, list[Any]], *, short_answer_row: dict[str, Any], long_answer_row: dict[str, Any]) -> str:
    """從 short/long answer token 範圍抽出可對齊的 evidence context。

    參數：
    - `tokens`：NQ 文件 token 欄位。
    - `short_answer_row`：挑選後的 short answer row。
    - `long_answer_row`：同一 annotator 對應的 long answer row。

    回傳：
    - `str`：包含答案附近上下文的 evidence 文字。
    """

    token_values = normalize_nested_sequence(tokens.get("token"))
    token_count = len(token_values)
    start_tokens = [int(value) for value in normalize_nested_sequence(short_answer_row.get("start_token")) if isinstance(value, int)]
    end_tokens = [int(value) for value in normalize_nested_sequence(short_answer_row.get("end_token")) if isinstance(value, int)]
    if not start_tokens or not end_tokens:
        return ""

    answer_start = min(start_tokens)
    answer_end = max(end_tokens)
    long_start = int(long_answer_row.get("start_token", answer_start)) if isinstance(long_answer_row, dict) else answer_start
    long_end = int(long_answer_row.get("end_token", answer_end)) if isinstance(long_answer_row, dict) else answer_end
    if long_end <= long_start:
        long_start, long_end = answer_start, answer_end

    context_start = max(long_start, answer_start - NQ_EVIDENCE_CONTEXT_WINDOW_TOKENS)
    context_end = min(long_end, answer_end + NQ_EVIDENCE_CONTEXT_WINDOW_TOKENS)
    context_start, context_end = clamp_nq_token_range(
        start_token=context_start,
        end_token=context_end,
        token_count=token_count,
    )
    return render_nq_tokens_to_text(tokens, start_token=context_start, end_token=context_end)


def build_nq_document_content(*, title: str, url: str, tokens: dict[str, list[Any]]) -> str:
    """將 NQ 文件 tokens 轉成可上傳的 Markdown 文件。

    參數：
    - `title`：文件標題。
    - `url`：來源 URL。
    - `tokens`：NQ 文件 token 欄位。

    回傳：
    - `str`：可寫入 repo 的 Markdown 內容。
    """

    body_start_token = find_nq_body_start_token(tokens)
    body_text = render_nq_tokens_to_text(tokens, start_token=body_start_token)
    blocks = [f"# {title}"]
    if url:
        blocks.extend(["", f"Source URL: {url}"])
    if body_text:
        blocks.extend(["", body_text])
    return normalize_newlines("\n".join(blocks)) + "\n"


def prepare_nq_source(
    *,
    input_reference: Path | str,
    workspace_dir: Path,
    limit_documents: int | None,
    limit_items: int | None,
) -> dict[str, Any]:
    """將 Natural Questions rows 轉成中間格式與 source documents。

    參數：
    - `input_reference`：本機檔案路徑或 `hf://` dataset 參照。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME
    documents_by_id: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []

    for row_index, raw_row in enumerate(resolve_prepare_source_rows(input_reference)):
        row = raw_row if isinstance(raw_row, dict) else {}
        document = row.get("document") if isinstance(row.get("document"), dict) else {}
        question = row.get("question") if isinstance(row.get("question"), dict) else {}
        tokens = document.get("tokens") if isinstance(document.get("tokens"), dict) else {}
        selection = select_nq_annotation(row)
        question_text = flatten_text(question.get("text"))
        if not question_text or selection is None:
            continue

        source_document_id = flatten_text(document.get("title")) or str(row.get("id") or f"nq-document-{row_index}")
        if limit_documents is not None and source_document_id not in documents_by_id and len(documents_by_id) >= limit_documents:
            continue
        if limit_items is not None and len(items) >= limit_items:
            break

        file_name = slugify_filename(source_document_id, suffix=".md")
        source_document_path = source_dir / file_name
        source_url = html.unescape(flatten_text(document.get("url")))
        if source_document_id not in documents_by_id:
            source_document_path.write_text(
                build_nq_document_content(
                    title=flatten_text(document.get("title")) or source_document_id,
                    url=source_url,
                    tokens=tokens,
                ),
                encoding="utf-8",
            )
            documents_by_id[source_document_id] = {
                "dataset": "nq",
                "source_document_id": source_document_id,
                "file_name": file_name,
                "title": flatten_text(document.get("title")) or source_document_id,
                "source_path": str(source_document_path.resolve()),
                "content_type": "text/markdown",
                "created_at": now_iso(),
            }

        evidence_text = build_nq_evidence_text(
            tokens,
            short_answer_row=selection["short_answer_row"],
            long_answer_row=selection["long_answer_row"],
        )
        items.append(
            {
                "item_id": stable_uuid(f"nq::{row.get('id')}::{question_text}"),
                "dataset": "nq",
                "source_document_id": source_document_id,
                "file_name": file_name,
                "query_text": question_text,
                "language": "en",
                "query_type": "fact_lookup",
                "answer_text": selection["answer_text"],
                "evidence_texts": [evidence_text] if evidence_text else [selection["answer_text"]],
                "answer_type": "short_answer",
                "source_question_index": row_index,
                "source_metadata": {
                    "nq_id": str(row.get("id") or ""),
                    "document_title": flatten_text(document.get("title")) or source_document_id,
                    "document_url": source_url,
                    "annotation_id": selection["annotation_id"],
                    "annotation_index": selection["annotation_index"],
                },
                "created_at": now_iso(),
            }
        )

    documents = list(documents_by_id.values())
    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "nq",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def looks_like_ascii_token(token: str) -> bool:
    """判斷 token 是否主要由 ASCII 英數與常見 URL 符號構成。

    參數：
    - `token`：待判斷 token。

    回傳：
    - `bool`：若屬於 ASCII-ish token 則回傳真值。
    """

    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+%-]*", token))


def render_dureader_token_sequence(tokens: list[Any]) -> str:
    """將 DuReader segmented tokens 渲染回較自然的文字。

    參數：
    - `tokens`：DuReader segmented tokens。

    回傳：
    - `str`：重組後的文字。
    """

    normalized_tokens = [flatten_text(token) for token in normalize_nested_sequence(tokens)]
    normalized_tokens = [token for token in normalized_tokens if token]
    if not normalized_tokens:
        return ""

    parts: list[str] = []
    previous_token = ""
    no_space_before = {",", ".", "!", "?", ";", ":", "%", ")", "]", "}", "，", "。", "！", "？", "；", "：", "、", "）", "】", "》", "”", "’"}
    no_space_after = {"(", "[", "{", "（", "【", "《", "“", "‘"}

    for token in normalized_tokens:
        if not parts:
            parts.append(token)
            previous_token = token
            continue

        need_space = looks_like_ascii_token(previous_token) and looks_like_ascii_token(token)
        if token in no_space_before or previous_token in no_space_after:
            need_space = False
        if any("\u4e00" <= char <= "\u9fff" for char in previous_token + token):
            need_space = False

        parts.append((" " if need_space else "") + token)
        previous_token = token
    return "".join(parts).strip()


def build_dureader_document_title(document: dict[str, Any], *, fallback_index: int) -> str:
    """為 DuReader bundle 內單一文件建立標題。

    參數：
    - `document`：DuReader 單一文件 payload。
    - `fallback_index`：若缺少標題時使用的順序號。

    回傳：
    - `str`：可寫入 Markdown heading 的標題。
    """

    title = flatten_text(document.get("title"))
    if title:
        return title
    segmented_title = render_dureader_token_sequence(
        document.get("segmented_title") if isinstance(document.get("segmented_title"), list) else []
    )
    if segmented_title:
        return segmented_title
    return f"Document {fallback_index}"


def build_dureader_document_paragraphs(document: dict[str, Any]) -> list[str]:
    """抽出 DuReader 單一文件可寫入 bundle 的段落文字。

    參數：
    - `document`：DuReader 單一文件 payload。

    回傳：
    - `list[str]`：依原始順序保留的段落文字。
    """

    raw_paragraphs = document.get("paragraphs") if isinstance(document.get("paragraphs"), list) else []
    paragraphs = [flatten_text(paragraph) for paragraph in raw_paragraphs if flatten_text(paragraph)]
    if paragraphs:
        return paragraphs

    segmented_paragraphs = document.get("segmented_paragraphs") if isinstance(document.get("segmented_paragraphs"), list) else []
    rendered = [
        render_dureader_token_sequence(paragraph_tokens)
        for paragraph_tokens in segmented_paragraphs
        if isinstance(paragraph_tokens, list)
    ]
    return [paragraph for paragraph in rendered if paragraph]


def select_dureader_documents(*, documents: list[dict[str, Any]], answer_doc_indexes: list[int]) -> list[dict[str, Any]]:
    """選出要 materialize 成 benchmark bundle 的 DuReader 文件。

    參數：
    - `documents`：題目下的文件列表。
    - `answer_doc_indexes`：官方 answer docs index 列表；若存在會強制保留。

    回傳：
    - `list[dict[str, Any]]`：依原始順序挑選後的文件列表。
    """

    selected_indexes = {
        index
        for index, document in enumerate(documents)
        if isinstance(document, dict) and document.get("is_selected")
    }
    selected_indexes.update(
        index for index in answer_doc_indexes if 0 <= index < len(documents)
    )
    if not selected_indexes:
        selected_indexes = set(range(min(len(documents), 3)))
    return [
        documents[index]
        for index in sorted(selected_indexes)
        if isinstance(documents[index], dict)
    ]


def build_dureader_evidence_window(*, paragraph_text: str, answer_text: str) -> str:
    """從 DuReader 段落中擷取答案附近的 evidence 視窗。

    參數：
    - `paragraph_text`：段落全文。
    - `answer_text`：候選答案文字。

    回傳：
    - `str`：答案附近的 evidence 視窗；若找不到答案則回傳原段落前段。
    """

    if not paragraph_text:
        return ""
    if not answer_text:
        return paragraph_text[:MAX_EVIDENCE_CHARS].strip()

    start_offset = paragraph_text.find(answer_text)
    if start_offset < 0:
        return paragraph_text[:MAX_EVIDENCE_CHARS].strip()

    end_offset = start_offset + len(answer_text)
    context_start = max(0, start_offset - DUREADER_EVIDENCE_CONTEXT_WINDOW_CHARS)
    context_end = min(len(paragraph_text), end_offset + DUREADER_EVIDENCE_CONTEXT_WINDOW_CHARS)
    return paragraph_text[context_start:context_end].strip()


def dedupe_texts(texts: list[str]) -> list[str]:
    """依原始順序去除重複文字。

    參數：
    - `texts`：原始文字列表。

    回傳：
    - `list[str]`：去重後列表。
    """

    deduped: list[str] = []
    seen: set[str] = set()
    for text in texts:
        normalized = text.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def build_dureader_answer_bundle(*, row: dict[str, Any], selected_documents: list[dict[str, Any]]) -> dict[str, Any]:
    """為 DuReader 單題建立 answer/evidence bundle。

    參數：
    - `row`：DuReader 單題 row。
    - `selected_documents`：本題最終要 materialize 的文件。

    回傳：
    - `dict[str, Any]`：包含 `answer_text`、`evidence_texts` 與 `answer_type` 的 bundle。
    """

    fake_answers = dedupe_texts(
        [flatten_text(answer) for answer in normalize_nested_sequence(row.get("fake_answers"))]
    )
    raw_answers = dedupe_texts(
        [flatten_text(answer) for answer in normalize_nested_sequence(row.get("answers"))]
    )
    short_answer_candidates = [
        answer
        for answer in fake_answers + raw_answers
        if answer and len(answer) <= MAX_SHORT_ANSWER_CHARS
    ]
    answer_text = min(short_answer_candidates, key=len) if short_answer_candidates else ""

    evidence_texts: list[str] = []
    evidence_texts.extend(text for text in fake_answers if len(text) <= MAX_EVIDENCE_CHARS)
    if not evidence_texts:
        evidence_texts.extend(text for text in raw_answers if len(text) <= MAX_EVIDENCE_CHARS)

    paragraph_hints: list[str] = []
    for document in selected_documents:
        paragraphs = build_dureader_document_paragraphs(document)
        most_related_para = document.get("most_related_para")
        if not isinstance(most_related_para, int) or not (0 <= most_related_para < len(paragraphs)):
            continue
        paragraph_hints.append(
            build_dureader_evidence_window(
                paragraph_text=paragraphs[most_related_para],
                answer_text=answer_text,
            )
        )

    evidence_texts.extend(text for text in paragraph_hints if text and len(text) <= MAX_EVIDENCE_CHARS)
    evidence_texts = dedupe_texts(evidence_texts)[:3]
    if not answer_text and evidence_texts:
        short_evidences = [text for text in evidence_texts if len(text) <= MAX_SHORT_ANSWER_CHARS]
        if short_evidences:
            answer_text = min(short_evidences, key=len)

    answer_type = "fake_answer" if fake_answers else "short_answer" if answer_text else "evidence_only"
    return {
        "answer_text": answer_text,
        "evidence_texts": evidence_texts,
        "answer_type": answer_type,
    }


def resolve_dureader_answer_start(*, context: str, answer_text: str, answer_start: int | None) -> int:
    """解析 DuReader 類資料集答案在 context 內的起始 offset。

    參數：
    - `context`：原始 context。
    - `answer_text`：答案文字。
    - `answer_start`：資料集提供的 offset；可能是 `-1`。

    回傳：
    - `int`：若可定位則回傳有效 offset，否則回傳 `-1`。
    """

    if isinstance(answer_start, int) and answer_start >= 0:
        return answer_start
    if not context or not answer_text:
        return -1
    return context.find(answer_text)


def build_dureader_robust_answer_text(answer_payload: dict[str, Any], *, context: str) -> tuple[str, int] | None:
    """從 DuReader-robust `answers` 物件挑出最適合 benchmark 的答案與 offset。

    參數：
    - `answer_payload`：DuReader-robust `answers` 物件。
    - `context`：原始 context，用於回找 `answer_start=-1` 的答案。

    回傳：
    - `tuple[str, int] | None`：`(answer_text, answer_start)`；若沒有有效答案則回傳空值。
    """

    texts = normalize_nested_sequence(answer_payload.get("text"))
    answer_starts = normalize_nested_sequence(answer_payload.get("answer_start"))
    candidates: list[tuple[str, int]] = []
    counter: Counter[tuple[str, int]] = Counter()

    for index, text in enumerate(texts):
        answer_text = flatten_text(text)
        raw_answer_start = answer_starts[index] if index < len(answer_starts) else None
        answer_start = resolve_dureader_answer_start(
            context=context,
            answer_text=answer_text,
            answer_start=raw_answer_start,
        )
        if not answer_text:
            continue
        candidate = (answer_text, answer_start)
        candidates.append(candidate)
        counter[candidate] += 1

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: (-counter[candidate], candidate[1], len(candidate[0])))
    return candidates[0]


def build_dureader_answer_list_text(*, answers: list[dict[str, Any]], context: str) -> tuple[str, int] | None:
    """從 DuReader-robust article wrapper 的答案列表挑出最適合 benchmark 的答案與 offset。

    參數：
    - `answers`：答案列表。
    - `context`：原始 context，用於回找 `answer_start=-1`。

    回傳：
    - `tuple[str, int] | None`：`(answer_text, answer_start)`；若沒有有效答案則回傳空值。
    """

    candidates: list[tuple[str, int]] = []
    counter: Counter[tuple[str, int]] = Counter()

    for answer in answers:
        if not isinstance(answer, dict):
            continue
        answer_text = flatten_text(answer.get("text"))
        answer_start = resolve_dureader_answer_start(
            context=context,
            answer_text=answer_text,
            answer_start=answer.get("answer_start"),
        )
        if not answer_text:
            continue
        candidate = (answer_text, answer_start)
        candidates.append(candidate)
        counter[candidate] += 1

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: (-counter[candidate], candidate[1], len(candidate[0])))
    return candidates[0]


def build_dureader_robust_document_content(*, title: str, context: str) -> str:
    """將 DuReader-robust 單題 context 轉成可上傳的 Markdown 文件。

    參數：
    - `title`：原始文章標題。
    - `context`：題目對應全文。

    回傳：
    - `str`：可寫入 repo 的 Markdown 內容。
    """

    blocks = [f"# {title}", "", "## Context", "", context]
    return normalize_newlines("\n".join(blocks)) + "\n"


def build_dureader_document_content(*, question_id: str, documents: list[dict[str, Any]]) -> str:
    """將 DuReader 單題文件集合 materialize 成單一 Markdown bundle。

    參數：
    - `question_id`：原始題目 id。
    - `documents`：本題選中的文件列表。

    回傳：
    - `str`：可上傳到 repo 的 Markdown 內容。
    """

    blocks = [f"# DuReader Bundle {question_id}"]
    for document_index, document in enumerate(documents, start=1):
        title = build_dureader_document_title(document, fallback_index=document_index)
        blocks.extend(["", f"## Document {document_index}: {title}"])
        for paragraph_index, paragraph_text in enumerate(build_dureader_document_paragraphs(document), start=1):
            blocks.extend(["", f"### Paragraph {paragraph_index}", "", paragraph_text])
    return normalize_newlines("\n".join(blocks)) + "\n"


def prepare_dureader_source(
    *,
    input_reference: Path | str,
    workspace_dir: Path,
    limit_documents: int | None,
    limit_items: int | None,
) -> dict[str, Any]:
    """將 DuReader rows 轉成中間格式與 source documents。

    參數：
    - `input_reference`：本機檔案路徑。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件 bundle。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME
    documents: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    input_path = Path(str(input_reference)).resolve()
    source_split = input_path.stem or "dureader"

    for row_index, raw_row in enumerate(resolve_prepare_source_rows(input_reference)):
        row = raw_row if isinstance(raw_row, dict) else {}
        question_text = flatten_text(row.get("question"))

        if not question_text and isinstance(row.get("paragraphs"), list):
            article_title = flatten_text(row.get("title")) or f"DuReader Robust Article {row_index}"
            for paragraph_index, paragraph in enumerate(row.get("paragraphs") or []):
                if not isinstance(paragraph, dict):
                    continue
                context = flatten_text(paragraph.get("context"))
                qas = paragraph.get("qas") if isinstance(paragraph.get("qas"), list) else []
                if not context or not qas:
                    continue

                paragraph_identifier = f"{row_index}-{paragraph_index}"
                if limit_documents is not None and len(documents) >= limit_documents:
                    break

                file_name = slugify_filename(f"dureader-{paragraph_identifier}", suffix=".md")
                source_document_path = source_dir / file_name
                paragraph_title = article_title if article_title else f"DuReader Robust Paragraph {paragraph_identifier}"
                source_document_path.write_text(
                    build_dureader_robust_document_content(title=paragraph_title, context=context),
                    encoding="utf-8",
                )
                documents.append(
                    {
                        "dataset": "dureader",
                        "source_document_id": paragraph_identifier,
                        "file_name": file_name,
                        "title": paragraph_title,
                        "source_path": str(source_document_path.resolve()),
                        "content_type": "text/markdown",
                        "created_at": now_iso(),
                    }
                )

                for qa_index, qa in enumerate(qas):
                    if limit_items is not None and len(items) >= limit_items:
                        break
                    if not isinstance(qa, dict):
                        continue
                    qa_question_text = flatten_text(qa.get("question"))
                    answer_selection = build_dureader_answer_list_text(
                        answers=qa.get("answers") if isinstance(qa.get("answers"), list) else [],
                        context=context,
                    )
                    if not qa_question_text or answer_selection is None:
                        continue
                    answer_text, answer_start = answer_selection
                    evidence_text = build_dureader_evidence_window(
                        paragraph_text=context,
                        answer_text=answer_text,
                    )
                    items.append(
                        {
                            "item_id": stable_uuid(
                                f"dureader::robust::{paragraph_identifier}::{qa.get('id') or qa_index}"
                            ),
                            "dataset": "dureader",
                            "source_document_id": paragraph_identifier,
                            "file_name": file_name,
                            "query_text": qa_question_text,
                            "language": "zh-TW",
                            "query_type": "fact_lookup",
                            "answer_text": answer_text,
                            "evidence_texts": [evidence_text] if evidence_text else [answer_text],
                            "answer_type": "short_answer",
                            "source_question_index": qa_index,
                            "source_metadata": {
                                "question_id": flatten_text(qa.get("id")) or paragraph_identifier,
                                "schema_variant": "robust",
                                "source_split": source_split,
                                "title": paragraph_title,
                                "paragraph_index": paragraph_index,
                                "answer_start": answer_start,
                            },
                            "created_at": now_iso(),
                        }
                    )
                if limit_items is not None and len(items) >= limit_items:
                    break
            if limit_documents is not None and len(documents) >= limit_documents:
                break
            if limit_items is not None and len(items) >= limit_items:
                break
            continue

        if not question_text:
            continue

        if isinstance(row.get("answers"), dict) and flatten_text(row.get("context")):
            answer_selection = build_dureader_robust_answer_text(
                row.get("answers") if isinstance(row.get("answers"), dict) else {},
                context=flatten_text(row.get("context")),
            )
            if answer_selection is None:
                continue
            if limit_documents is not None and len(documents) >= limit_documents:
                break
            if limit_items is not None and len(items) >= limit_items:
                break

            source_document_id = flatten_text(row.get("id")) or f"dureader-robust-{row_index}"
            title = flatten_text(row.get("title")) or f"DuReader Robust {source_document_id}"
            context = flatten_text(row.get("context"))
            answer_text, answer_start = answer_selection
            evidence_text = build_dureader_evidence_window(
                paragraph_text=context,
                answer_text=answer_text,
            )

            file_name = slugify_filename(f"dureader-{source_document_id}", suffix=".md")
            source_document_path = source_dir / file_name
            source_document_path.write_text(
                build_dureader_robust_document_content(title=title, context=context),
                encoding="utf-8",
            )
            documents.append(
                {
                    "dataset": "dureader",
                    "source_document_id": source_document_id,
                    "file_name": file_name,
                    "title": title,
                    "source_path": str(source_document_path.resolve()),
                    "content_type": "text/markdown",
                    "created_at": now_iso(),
                }
            )
            items.append(
                {
                    "item_id": stable_uuid(f"dureader::robust::{source_document_id}::{question_text}"),
                    "dataset": "dureader",
                    "source_document_id": source_document_id,
                    "file_name": file_name,
                    "query_text": question_text,
                    "language": "zh-TW",
                    "query_type": "fact_lookup",
                    "answer_text": answer_text,
                    "evidence_texts": [evidence_text] if evidence_text else [answer_text],
                    "answer_type": "short_answer",
                    "source_question_index": row_index,
                    "source_metadata": {
                        "question_id": source_document_id,
                        "schema_variant": "robust",
                        "source_split": source_split,
                        "title": title,
                        "answer_start": answer_start,
                    },
                    "created_at": now_iso(),
                }
            )
            continue

        fact_or_opinion = flatten_text(row.get("fact_or_opinion")).upper()
        if fact_or_opinion and fact_or_opinion != "FACT":
            continue
        yesno_answers = [
            flatten_text(answer)
            for answer in normalize_nested_sequence(row.get("yesno_answers"))
            if flatten_text(answer)
        ]
        if yesno_answers:
            continue

        raw_documents = row.get("documents") if isinstance(row.get("documents"), list) else []
        documents_payload = [document for document in raw_documents if isinstance(document, dict)]
        if not documents_payload:
            continue

        answer_doc_indexes = [
            answer_doc
            for answer_doc in normalize_nested_sequence(row.get("answer_docs"))
            if isinstance(answer_doc, int)
        ]
        selected_documents = select_dureader_documents(
            documents=documents_payload,
            answer_doc_indexes=answer_doc_indexes,
        )
        if not selected_documents:
            continue

        answer_bundle = build_dureader_answer_bundle(
            row=row,
            selected_documents=selected_documents,
        )
        if not answer_bundle["answer_text"] and not answer_bundle["evidence_texts"]:
            continue

        if limit_documents is not None and len(documents) >= limit_documents:
            break
        if limit_items is not None and len(items) >= limit_items:
            break

        question_id = flatten_text(row.get("question_id")) or f"dureader-question-{row_index}"
        file_name = slugify_filename(f"dureader-{question_id}", suffix=".md")
        source_document_path = source_dir / file_name
        source_document_path.write_text(
            build_dureader_document_content(question_id=question_id, documents=selected_documents),
            encoding="utf-8",
        )

        documents.append(
            {
                "dataset": "dureader",
                "source_document_id": question_id,
                "file_name": file_name,
                "title": f"DuReader Bundle {question_id}",
                "source_path": str(source_document_path.resolve()),
                "content_type": "text/markdown",
                "created_at": now_iso(),
            }
        )
        items.append(
            {
                "item_id": stable_uuid(f"dureader::{question_id}::{question_text}"),
                "dataset": "dureader",
                "source_document_id": question_id,
                "file_name": file_name,
                "query_text": question_text,
                "language": "zh-TW",
                "query_type": "fact_lookup",
                "answer_text": answer_bundle["answer_text"],
                "evidence_texts": answer_bundle["evidence_texts"],
                "answer_type": answer_bundle["answer_type"],
                "source_question_index": row_index,
                "source_metadata": {
                    "question_id": question_id,
                    "question_type": flatten_text(row.get("question_type")),
                    "schema_variant": "search_bundle",
                    "fact_or_opinion": fact_or_opinion or "UNKNOWN",
                    "source_split": source_split,
                    "selected_document_count": len(selected_documents),
                    "answer_doc_count": len(answer_doc_indexes),
                },
                "created_at": now_iso(),
            }
        )

    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "dureader",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def build_drcd_answer_text(answers: list[dict[str, Any]]) -> tuple[str, int] | None:
    """從 DRCD 單題答案列表挑出最適合 benchmark 的答案與 offset。

    參數：
    - `answers`：DRCD `qas.answers` 陣列。

    回傳：
    - `tuple[str, int] | None`：`(answer_text, answer_start)`；若沒有有效答案則回傳空值。
    """

    candidates: list[tuple[str, int]] = []
    counter: Counter[tuple[str, int]] = Counter()

    for answer in answers:
        if not isinstance(answer, dict):
            continue
        answer_text = flatten_text(answer.get("text"))
        answer_start = answer.get("answer_start")
        if not answer_text or not isinstance(answer_start, int) or answer_start < 0:
            continue
        candidate = (answer_text, answer_start)
        candidates.append(candidate)
        counter[candidate] += 1

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: (-counter[candidate], candidate[1], len(candidate[0])))
    return candidates[0]


def build_drcd_evidence_text(*, context: str, answer_text: str, answer_start: int) -> str:
    """從 DRCD paragraph context 擷取可對齊的 evidence 視窗。

    參數：
    - `context`：DRCD paragraph 全文。
    - `answer_text`：核准的答案文字。
    - `answer_start`：答案在 paragraph 內的起始 offset。

    回傳：
    - `str`：包含答案附近上下文的 evidence 文字。
    """

    if not context or not answer_text:
        return ""

    answer_end = min(len(context), answer_start + len(answer_text))
    if answer_start < 0 or answer_start >= len(context) or answer_end <= answer_start:
        return answer_text

    context_start = max(0, answer_start - DRCD_EVIDENCE_CONTEXT_WINDOW_CHARS)
    context_end = min(len(context), answer_end + DRCD_EVIDENCE_CONTEXT_WINDOW_CHARS)
    return context[context_start:context_end].strip()


def build_drcd_document_content(*, title: str, paragraphs: list[dict[str, Any]]) -> str:
    """將 DRCD article row 轉成可上傳的 Markdown 文件。

    參數：
    - `title`：文章標題。
    - `paragraphs`：文章段落列表。

    回傳：
    - `str`：可寫入 repo 的 Markdown 內容。
    """

    blocks = [f"# {title}"]
    for index, paragraph in enumerate(paragraphs, start=1):
        if not isinstance(paragraph, dict):
            continue
        context = flatten_text(paragraph.get("context"))
        if not context:
            continue
        blocks.extend(["", f"## Paragraph {index}", "", context])
    return normalize_newlines("\n".join(blocks)) + "\n"


def prepare_drcd_source(
    *,
    input_reference: Path | str,
    workspace_dir: Path,
    limit_documents: int | None,
    limit_items: int | None,
) -> dict[str, Any]:
    """將 DRCD article rows 轉成中間格式與 source documents。

    參數：
    - `input_reference`：本機檔案路徑或 `hf://` dataset 參照。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME
    documents: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    for row_index, raw_row in enumerate(resolve_prepare_source_rows(input_reference)):
        row = raw_row if isinstance(raw_row, dict) else {}
        title = flatten_text(row.get("title")) or f"DRCD Article {row_index}"
        source_document_id = flatten_text(row.get("id")) or f"drcd-article-{row_index}"
        paragraphs = row.get("paragraphs") if isinstance(row.get("paragraphs"), list) else []

        if limit_documents is not None and len(documents) >= limit_documents:
            break

        file_name = slugify_filename(f"drcd-{source_document_id}", suffix=".md")
        source_document_path = source_dir / file_name
        source_document_path.write_text(
            build_drcd_document_content(title=title, paragraphs=paragraphs),
            encoding="utf-8",
        )
        documents.append(
            {
                "dataset": "drcd",
                "source_document_id": source_document_id,
                "file_name": file_name,
                "title": title,
                "source_path": str(source_document_path.resolve()),
                "content_type": "text/markdown",
                "created_at": now_iso(),
            }
        )

        for paragraph_index, paragraph in enumerate(paragraphs):
            if not isinstance(paragraph, dict):
                continue
            context = flatten_text(paragraph.get("context"))
            paragraph_id = flatten_text(paragraph.get("id")) or f"{source_document_id}-paragraph-{paragraph_index}"
            qas = paragraph.get("qas") if isinstance(paragraph.get("qas"), list) else []
            for question_index, qa in enumerate(qas):
                if limit_items is not None and len(items) >= limit_items:
                    break
                if not isinstance(qa, dict):
                    continue
                question_text = flatten_text(qa.get("question"))
                answer_selection = build_drcd_answer_text(
                    qa.get("answers") if isinstance(qa.get("answers"), list) else []
                )
                if not question_text or answer_selection is None:
                    continue
                answer_text, answer_start = answer_selection
                evidence_text = build_drcd_evidence_text(
                    context=context,
                    answer_text=answer_text,
                    answer_start=answer_start,
                )
                items.append(
                    {
                        "item_id": stable_uuid(f"drcd::{source_document_id}::{paragraph_id}::{qa.get('id') or question_index}"),
                        "dataset": "drcd",
                        "source_document_id": source_document_id,
                        "file_name": file_name,
                        "query_text": question_text,
                        "language": "zh-TW",
                        "query_type": "fact_lookup",
                        "answer_text": answer_text,
                        "evidence_texts": [evidence_text] if evidence_text else [answer_text],
                        "answer_type": "short_answer",
                        "source_question_index": question_index,
                        "source_metadata": {
                            "article_id": source_document_id,
                            "paragraph_id": paragraph_id,
                            "qa_id": flatten_text(qa.get("id")),
                            "answer_start": answer_start,
                            "title": title,
                        },
                        "created_at": now_iso(),
                    }
                )
            if limit_items is not None and len(items) >= limit_items:
                break
        if limit_items is not None and len(items) >= limit_items:
            break

    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "drcd",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def prepare_uda_source(*, input_path: Path, workspace_dir: Path, limit_documents: int | None, limit_items: int | None) -> dict[str, Any]:
    """將 UDA 類表格資料轉成中間格式與 source documents。

    參數：
    - `input_path`：UDA JSON/JSONL/CSV 檔。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    rows = read_table_like_rows(input_path)
    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME
    documents_by_id: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows):
        document_key = first_present(row, ("document_id", "doc_id", "doc_name", "file_name", "source_file"))
        if not document_key:
            document_key = f"uda-document-{row_index}"
        if limit_documents is not None and document_key not in documents_by_id and len(documents_by_id) >= limit_documents:
            continue

        file_name = slugify_filename(document_key, suffix=".md")
        source_document_path = source_dir / file_name
        document_text = build_uda_document_content(row)
        source_file = first_present(row, ("source_file", "file_path", "source_path"))
        if source_file and Path(source_file).exists():
            suffix = Path(source_file).suffix or ".bin"
            file_name = slugify_filename(document_key, suffix=suffix)
            source_document_path = source_dir / file_name
            if not source_document_path.exists():
                shutil.copy2(Path(source_file), source_document_path)
            content_type = "application/octet-stream"
        else:
            if not document_text:
                document_text = first_present(row, ("answer_context",))
            source_document_path.write_text(normalize_newlines(document_text) + "\n", encoding="utf-8")
            content_type = "text/markdown"

        if document_key not in documents_by_id:
            documents_by_id[document_key] = {
                "dataset": "uda",
                "source_document_id": document_key,
                "file_name": file_name,
                "title": first_present(row, ("title", "doc_title", "document_title")) or document_key,
                "source_path": str(source_document_path.resolve()),
                "content_type": content_type,
                "created_at": now_iso(),
            }

        if limit_items is not None and len(items) >= limit_items:
            continue
        question_text = first_present(row, ("question", "query", "prompt"))
        answer_text = first_present(row, ("answer", "gold_answer", "short_answer", "response"))
        evidence_candidates = [
            first_present(row, ("evidence", "gold_evidence", "supporting_text", "supporting_context", "answer_span")),
        ]
        evidence_candidates = [candidate for candidate in evidence_candidates if candidate]
        if not evidence_candidates and answer_text:
            evidence_candidates = [answer_text]
        item_id = stable_uuid(f"uda::{document_key}::{question_text}::{row_index}")
        items.append(
            {
                "item_id": item_id,
                "dataset": "uda",
                "source_document_id": document_key,
                "file_name": file_name,
                "query_text": question_text,
                "language": first_present(row, ("language",)) or "en",
                "query_type": "fact_lookup",
                "answer_text": answer_text,
                "evidence_texts": evidence_candidates,
                "answer_type": "short_answer" if answer_text else "missing",
                "source_question_index": row_index,
                "source_metadata": {
                    "row_index": row_index,
                },
                "created_at": now_iso(),
            }
        )

    documents = list(documents_by_id.values())
    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "uda",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def prepare_source(
    *,
    dataset: str,
    input_path: Path | str,
    workspace_dir: Path,
    limit_documents: int | None,
    limit_items: int | None,
) -> dict[str, Any]:
    """依資料集型別執行 source preparation。

    參數：
    - `dataset`：資料集型別。
    - `input_path`：原始輸入路徑。
    - `workspace_dir`：工作目錄。
    - `limit_documents`：最多文件數。
    - `limit_items`：最多題數。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    ensure_workspace_dir(workspace_dir)
    if dataset == "qasper":
        return prepare_qasper_source(
            input_path=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    if dataset == "uda":
        return prepare_uda_source(
            input_path=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    if dataset == "msmarco":
        return prepare_msmarco_source(
            input_reference=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    if dataset == "nq":
        return prepare_nq_source(
            input_reference=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    if dataset == "dureader":
        return prepare_dureader_source(
            input_reference=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    if dataset == "drcd":
        return prepare_drcd_source(
            input_reference=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    raise ValueError(f"不支援的 dataset：{dataset}")


def contains_layout_dependent_keyword(text: str) -> bool:
    """判斷文字是否高度依賴圖像或版面。

    參數：
    - `text`：待檢查文字。

    回傳：
    - `bool`：若疑似依賴圖像/版面則回傳真值。
    """

    lowered = text.lower()
    return any(keyword in lowered for keyword in ("figure", "image", "diagram", "bbox", "coordinate", "left side", "right side"))


def filter_item(item: dict[str, Any]) -> tuple[bool, str]:
    """套用 curated v1 篩題規則。

    參數：
    - `item`：單題中間格式。

    回傳：
    - `tuple[bool, str]`：是否保留與原因。
    """

    query_text = item.get("query_text", "").strip()
    answer_text = item.get("answer_text", "").strip()
    evidence_texts = [text.strip() for text in item.get("evidence_texts", []) if isinstance(text, str) and text.strip()]
    dataset = item.get("dataset")

    if not query_text:
        return False, "missing_query"
    if item.get("query_type") != "fact_lookup":
        return False, "unsupported_query_type"
    if not evidence_texts and not answer_text:
        return False, "missing_evidence"
    if answer_text and len(answer_text) > MAX_SHORT_ANSWER_CHARS:
        return False, "answer_too_long"
    if any(len(text) > MAX_EVIDENCE_CHARS for text in evidence_texts):
        return False, "evidence_too_long"
    if contains_layout_dependent_keyword(query_text) or any(contains_layout_dependent_keyword(text) for text in evidence_texts):
        return False, "layout_dependent"
    if re.search(r"\b(yes|no)\b", answer_text.lower()) and len(answer_text) <= 3:
        return False, "yes_no_answer"
    if dataset == "qasper" and not evidence_texts:
        return False, "qasper_requires_evidence"
    if dataset == "uda" and not evidence_texts and not answer_text:
        return False, "uda_requires_short_answer"
    if dataset == "nq" and not evidence_texts:
        return False, "nq_requires_evidence"
    if dataset == "dureader" and not evidence_texts:
        return False, "dureader_requires_evidence"
    if dataset == "drcd" and not evidence_texts:
        return False, "drcd_requires_evidence"
    return True, "kept"


def filter_items(*, workspace_dir: Path) -> dict[str, Any]:
    """執行 curated v1 篩題並輸出報表。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `dict[str, Any]`：篩題摘要。
    """

    prepared_items = read_jsonl(workspace_dir / PREPARED_ITEMS_FILE)
    kept_items: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()

    for item in prepared_items:
        keep, reason = filter_item(item)
        item["filter_reason"] = reason
        reason_counter[reason] += 1
        if keep:
            kept_items.append(item)

    write_jsonl(workspace_dir / FILTERED_ITEMS_FILE, kept_items)
    report = {
        "prepared_item_count": len(prepared_items),
        "kept_item_count": len(kept_items),
        "drop_item_count": len(prepared_items) - len(kept_items),
        "reason_counts": dict(sorted(reason_counter.items())),
        "generated_at": now_iso(),
    }
    write_json(workspace_dir / FILTER_REPORT_FILE, report)
    return report


def normalize_with_mapping(text: str) -> NormalizedText:
    """將文字正規化並保留 normalized index 到原始 offset 的映射。

    參數：
    - `text`：原始全文或 evidence。

    回傳：
    - `NormalizedText`：正規化後資料。
    """

    normalized_chars: list[str] = []
    mapping: list[int] = []
    previous_was_space = True
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\u00ad":
            index += 1
            continue
        if char == "-" and index + 1 < len(text) and text[index + 1] in {"\n", "\r"}:
            index += 1
            while index < len(text) and text[index] in {"\n", "\r", " "}:
                index += 1
            previous_was_space = False
            continue
        expanded = unicodedata.normalize("NFKC", char)
        for normalized_char in expanded:
            if normalized_char.isspace():
                if not previous_was_space and normalized_chars:
                    normalized_chars.append(" ")
                    mapping.append(index)
                previous_was_space = True
                continue
            normalized_chars.append(normalized_char.lower())
            mapping.append(index)
            previous_was_space = False
        index += 1
    return NormalizedText(normalized_text="".join(normalized_chars).strip(), normalized_to_original=mapping)


def find_all_exact_matches(document: NormalizedText, evidence: NormalizedText) -> list[tuple[int, int]]:
    """在正規化後全文中尋找 evidence 的所有精確命中。

    參數：
    - `document`：文件全文。
    - `evidence`：待對齊 evidence。

    回傳：
    - `list[tuple[int, int]]`：原始 offset 範圍列表。
    """

    if not evidence.normalized_text:
        return []
    hits: list[tuple[int, int]] = []
    start_at = 0
    while True:
        found_index = document.normalized_text.find(evidence.normalized_text, start_at)
        if found_index < 0:
            break
        end_index = found_index + len(evidence.normalized_text) - 1
        if end_index >= len(document.normalized_to_original):
            break
        original_start = document.normalized_to_original[found_index]
        original_end = document.normalized_to_original[end_index] + 1
        hits.append((original_start, original_end))
        start_at = found_index + 1
    deduped: list[tuple[int, int]] = []
    for hit in hits:
        if hit not in deduped:
            deduped.append(hit)
    return deduped


def tokenize(text: str) -> set[str]:
    """將文字切成粗粒度 token 集合。

    參數：
    - `text`：輸入文字。

    回傳：
    - `set[str]`：token 集合。
    """

    return {token for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text.lower()) if token}


def overlap_score(query_signal: str, candidate_text: str) -> float:
    """計算 query/answer 與候選片段的 token overlap。

    參數：
    - `query_signal`：問題與答案組成的訊號。
    - `candidate_text`：候選片段。

    回傳：
    - `float`：0 到 1 的 overlap 分數。
    """

    left = tokenize(query_signal)
    right = tokenize(candidate_text)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def disambiguate_exact_matches(*, display_text: str, matches: list[tuple[int, int]], query_signal: str) -> tuple[tuple[int, int] | None, list[dict[str, Any]]]:
    """對多重 exact matches 做 context disambiguation。

    參數：
    - `display_text`：原始全文。
    - `matches`：所有 exact match 範圍。
    - `query_signal`：問題與答案訊號。

    回傳：
    - `tuple[tuple[int, int] | None, list[dict[str, Any]]]`：最佳命中與評分細節。
    """

    scored: list[dict[str, Any]] = []
    for start_offset, end_offset in matches:
        context_start = max(0, start_offset - 120)
        context_end = min(len(display_text), end_offset + 120)
        context_text = display_text[context_start:context_end]
        score = overlap_score(query_signal, context_text)
        scored.append(
            {
                "start_offset": start_offset,
                "end_offset": end_offset,
                "score": round(score, 6),
                "excerpt": display_text[start_offset:end_offset],
            }
        )
    scored.sort(key=lambda row: (-row["score"], row["start_offset"]))
    if len(scored) == 1:
        return (scored[0]["start_offset"], scored[0]["end_offset"]), scored
    if scored and len(scored) > 1 and scored[0]["score"] > scored[1]["score"]:
        return (scored[0]["start_offset"], scored[0]["end_offset"]), scored
    return None, scored


def iter_candidate_segments(display_text: str, *, window_size: int) -> list[tuple[int, int, str]]:
    """依段落與句子切出 fuzzy 對齊候選片段。

    參數：
    - `display_text`：全文。
    - `window_size`：預估 evidence 長度。

    回傳：
    - `list[tuple[int, int, str]]`：原始 offset 與候選文字。
    """

    segments: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^\n]+", display_text):
        segment = match.group(0).strip()
        if not segment:
            continue
        start_offset, end_offset = match.start(), match.end()
        segments.append((start_offset, end_offset, segment))
    if segments:
        return segments
    if display_text:
        return [(0, min(len(display_text), window_size), display_text[:window_size])]
    return []


def fuzzy_match_evidence(*, display_text: str, evidence_text: str, query_signal: str) -> dict[str, Any] | None:
    """用句段級 fuzzy 規則搜尋 evidence。

    參數：
    - `display_text`：文件全文。
    - `evidence_text`：待對齊 evidence。
    - `query_signal`：問題與答案訊號。

    回傳：
    - `dict[str, Any] | None`：最佳候選；若信心不足則回傳空值。
    """

    evidence_normalized = normalize_with_mapping(evidence_text).normalized_text
    if not evidence_normalized:
        return None
    candidates: list[dict[str, Any]] = []
    for start_offset, end_offset, segment in iter_candidate_segments(display_text, window_size=max(len(evidence_text) * 2, 80)):
        normalized_segment = normalize_with_mapping(segment).normalized_text
        if not normalized_segment:
            continue
        ratio = SequenceMatcher(None, evidence_normalized, normalized_segment).ratio()
        score = (0.7 * ratio) + (0.3 * overlap_score(query_signal, segment))
        candidates.append(
            {
                "start_offset": start_offset,
                "end_offset": end_offset,
                "score": round(score, 6),
                "excerpt": segment,
            }
        )
    candidates.sort(key=lambda row: (-row["score"], row["start_offset"]))
    if not candidates:
        return None
    top = candidates[0]
    second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    if top["score"] >= FUZZY_ACCEPT_SCORE and (top["score"] - second_score) >= FUZZY_ACCEPT_MARGIN:
        return top
    return None


def load_ready_documents_for_area(*, area_id: str) -> dict[str, Document]:
    """載入指定 area 內所有 ready 文件。

    參數：
    - `area_id`：area id。

    回傳：
    - `dict[str, Document]`：以 file_name 為 key 的 ready 文件。
    """

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        documents = session.scalars(
            select(Document).where(
                Document.area_id == area_id,
                Document.status == DocumentStatus.ready,
            )
        ).all()
    return {document.file_name: document for document in documents}


def align_single_item(*, item: dict[str, Any], display_text: str) -> dict[str, Any]:
    """將單題 evidence 對齊到 display_text offsets。

    參數：
    - `item`：篩題後單題資料。
    - `display_text`：系統正式全文。

    回傳：
    - `dict[str, Any]`：對齊結果。
    """

    document_normalized = normalize_with_mapping(display_text)
    query_signal = " ".join(part for part in (item.get("query_text", ""), item.get("answer_text", "")) if part).strip()
    accepted_spans: list[dict[str, Any]] = []
    review_candidates: list[dict[str, Any]] = []
    rejected_evidences: list[dict[str, Any]] = []

    evidence_texts = [text for text in item.get("evidence_texts", []) if isinstance(text, str) and text.strip()]
    for evidence_text in evidence_texts:
        evidence_normalized = normalize_with_mapping(evidence_text)
        exact_matches = find_all_exact_matches(document_normalized, evidence_normalized)
        if len(exact_matches) == 1:
            accepted_spans.append(
                {
                    "start_offset": exact_matches[0][0],
                    "end_offset": exact_matches[0][1],
                    "match_type": "exact_unique",
                    "evidence_text": evidence_text,
                }
            )
            continue
        if len(exact_matches) > 1:
            chosen, scored_matches = disambiguate_exact_matches(
                display_text=display_text,
                matches=exact_matches,
                query_signal=query_signal,
            )
            if chosen is not None:
                accepted_spans.append(
                    {
                        "start_offset": chosen[0],
                        "end_offset": chosen[1],
                        "match_type": "exact_disambiguated",
                        "evidence_text": evidence_text,
                    }
                )
            else:
                review_candidates.append(
                    {
                        "evidence_text": evidence_text,
                        "reason": "multiple_exact_matches",
                        "candidates": scored_matches,
                    }
                )
            continue
        fuzzy_candidate = fuzzy_match_evidence(
            display_text=display_text,
            evidence_text=evidence_text,
            query_signal=query_signal,
        )
        if fuzzy_candidate is not None:
            accepted_spans.append(
                {
                    "start_offset": fuzzy_candidate["start_offset"],
                    "end_offset": fuzzy_candidate["end_offset"],
                    "match_type": "fuzzy",
                    "score": fuzzy_candidate["score"],
                    "evidence_text": evidence_text,
                }
            )
        else:
            rejected_evidences.append(
                {
                    "evidence_text": evidence_text,
                    "reason": "no_confident_match",
                }
            )

    deduped_spans: list[dict[str, Any]] = []
    seen_offsets: set[tuple[int, int]] = set()
    for span in accepted_spans:
        span_key = (span["start_offset"], span["end_offset"])
        if span_key in seen_offsets:
            continue
        seen_offsets.add(span_key)
        deduped_spans.append(span)

    status = "auto_matched"
    if not deduped_spans and review_candidates:
        status = "needs_review"
    elif not deduped_spans and rejected_evidences:
        status = "rejected"
    elif deduped_spans and review_candidates:
        status = "auto_matched"

    return {
        "item_id": item["item_id"],
        "dataset": item["dataset"],
        "file_name": item["file_name"],
        "query_text": item["query_text"],
        "answer_text": item.get("answer_text"),
        "language": item["language"],
        "query_type": item["query_type"],
        "status": status,
        "accepted_spans": deduped_spans,
        "review_candidates": review_candidates,
        "rejected_evidences": rejected_evidences,
        "source_metadata": item.get("source_metadata", {}),
        "generated_at": now_iso(),
    }


def align_spans(*, workspace_dir: Path, area_id: str) -> dict[str, Any]:
    """對齊所有篩題後 evidence 到指定 area 的 ready 文件。

    參數：
    - `workspace_dir`：工作目錄。
    - `area_id`：目標 area id。

    回傳：
    - `dict[str, Any]`：對齊摘要。
    """

    filtered_items = read_jsonl(workspace_dir / FILTERED_ITEMS_FILE)
    ready_documents = load_ready_documents_for_area(area_id=area_id)
    results: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()

    for item in filtered_items:
        document = ready_documents.get(item["file_name"])
        if document is None:
            result = {
                "item_id": item["item_id"],
                "dataset": item["dataset"],
                "file_name": item["file_name"],
                "query_text": item["query_text"],
                "answer_text": item.get("answer_text"),
                "language": item["language"],
                "query_type": item["query_type"],
                "status": "rejected",
                "accepted_spans": [],
                "review_candidates": [],
                "rejected_evidences": [{"reason": "missing_ready_document", "evidence_text": ""}],
                "source_metadata": item.get("source_metadata", {}),
                "generated_at": now_iso(),
            }
        else:
            result = align_single_item(item=item, display_text=document.display_text or "")
        results.append(result)
        status_counter[result["status"]] += 1
        if result["status"] in {"needs_review", "rejected"}:
            review_queue.append(result)

    write_jsonl(workspace_dir / ALIGNMENT_CANDIDATES_FILE, results)
    write_jsonl(workspace_dir / ALIGNMENT_REVIEW_QUEUE_FILE, review_queue)
    report = {
        "area_id": area_id,
        "item_count": len(filtered_items),
        "status_counts": dict(sorted(status_counter.items())),
        "auto_matched_ratio": round(status_counter.get("auto_matched", 0) / len(filtered_items), 6) if filtered_items else 0.0,
        "generated_at": now_iso(),
    }
    write_json(workspace_dir / ALIGNMENT_REPORT_FILE, report)
    return report


def read_review_overrides(workspace_dir: Path) -> dict[str, dict[str, Any]]:
    """讀取 reviewer 手動覆核結果。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `dict[str, dict[str, Any]]`：以 item id 為 key 的 override 映射。
    """

    path = workspace_dir / REVIEW_OVERRIDES_FILE
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    return {row["item_id"]: row for row in rows if row.get("item_id")}


def build_snapshot(
    *,
    workspace_dir: Path,
    output_dir: Path,
    benchmark_name: str,
    include_review_items: bool,
    target_question_count: int | None = None,
    reference_evaluation_profile: str | None = None,
) -> dict[str, Any]:
    """以 auto-matched 與 reviewed-approved 題目建立 snapshot。

    參數：
    - `workspace_dir`：工作目錄。
    - `output_dir`：snapshot 輸出目錄。
    - `benchmark_name`：snapshot 名稱。
    - `include_review_items`：是否保留尚未有 spans 的 review queue 題目。
    - `target_question_count`：若提供，僅保留前 N 題已核准題目，且不足時直接失敗。
    - `reference_evaluation_profile`：若提供，寫入 manifest 的正式跑分 profile。

    回傳：
    - `dict[str, Any]`：snapshot 摘要。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    prepared_documents = read_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE)
    prepared_items = {row["item_id"]: row for row in read_jsonl(workspace_dir / PREPARED_ITEMS_FILE)}
    filtered_items = {row["item_id"]: row for row in read_jsonl(workspace_dir / FILTERED_ITEMS_FILE)}
    alignment_rows = read_jsonl(workspace_dir / ALIGNMENT_CANDIDATES_FILE)
    overrides = read_review_overrides(workspace_dir)

    accepted_rows: list[dict[str, Any]] = []

    for alignment_row in alignment_rows:
        item = filtered_items.get(alignment_row["item_id"]) or prepared_items.get(alignment_row["item_id"])
        if item is None:
            continue
        accepted_spans = list(alignment_row.get("accepted_spans", []))
        override = overrides.get(item["item_id"])
        if override:
            decision = override.get("decision")
            if decision == "approved":
                accepted_spans = override.get("spans", [])
            elif decision == "rejected":
                accepted_spans = []

        include_item = bool(accepted_spans)
        if not include_item and include_review_items and alignment_row["status"] == "needs_review":
            include_item = True
        if not include_item:
            continue
        accepted_rows.append(
            {
                "item": item,
                "alignment_status": alignment_row["status"],
                "accepted_spans": accepted_spans,
            }
        )

    if target_question_count is not None:
        if target_question_count <= 0:
            raise ValueError("target_question_count 必須大於 0。")
        if len(accepted_rows) < target_question_count:
            raise ValueError(
                f"已核准題目僅有 {len(accepted_rows)} 題，無法建立要求的 {target_question_count} 題 snapshot。"
            )
        accepted_rows = accepted_rows[:target_question_count]

    questions: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    included_document_names: set[str] = set()
    accepted_item_count = 0
    dataset_counter: Counter[str] = Counter()

    for accepted_row in accepted_rows:
        item = accepted_row["item"]
        accepted_spans = accepted_row["accepted_spans"]
        question_id = stable_uuid(f"question::{benchmark_name}::{item['item_id']}")
        questions.append(
            {
                "question_id": question_id,
                "dataset_id": stable_uuid(f"benchmark::{benchmark_name}"),
                "query_type": "fact_lookup",
                "language": item["language"],
                "question": item["query_text"],
                "notes": json.dumps(
                    {
                        "source_item_id": item["item_id"],
                        "dataset": item["dataset"],
                        "source_document_id": item["source_document_id"],
                        "answer_text": item.get("answer_text"),
                        "alignment_status": accepted_row["alignment_status"],
                    },
                    ensure_ascii=False,
                ),
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        )
        dataset_counter[item["dataset"]] += 1
        for span_index, span in enumerate(accepted_spans):
            spans.append(
                {
                    "span_id": stable_uuid(
                        f"span::{benchmark_name}::{question_id}::{span['start_offset']}::{span['end_offset']}::{span_index}"
                    ),
                    "question_id": question_id,
                    "file_name": item["file_name"],
                    "start_offset": int(span["start_offset"]),
                    "end_offset": int(span["end_offset"]),
                    "relevance_grade": 3,
                    "is_retrieval_miss": False,
                }
            )
            included_document_names.add(item["file_name"])
        if accepted_spans:
            accepted_item_count += 1

    documents = [
        {
            "document_id": stable_uuid(f"document::{row['file_name']}"),
            "file_name": row["file_name"],
            "content_type": row.get("content_type", "application/octet-stream"),
            "file_size": Path(row["source_path"]).stat().st_size if Path(row["source_path"]).exists() else 0,
            "status": "ready",
            "created_at": row.get("created_at", now_iso()),
            "area_id": None,
        }
        for row in prepared_documents
        if row["file_name"] in included_document_names or include_review_items
    ]

    snapshot_files = list(SNAPSHOT_REQUIRED_FILES) + [
        ALIGNMENT_CANDIDATES_FILE,
        ALIGNMENT_REVIEW_QUEUE_FILE,
        FILTER_REPORT_FILE,
    ]
    for auxiliary_name in OPTIONAL_SNAPSHOT_AUXILIARY_FILES:
        if (workspace_dir / auxiliary_name).exists():
            snapshot_files.append(auxiliary_name)

    manifest = {
        "benchmark_name": benchmark_name,
        "dataset": {
            "dataset_id": stable_uuid(f"benchmark::{benchmark_name}"),
            "query_type": "fact_lookup",
            "generated_at": now_iso(),
        },
        "reference": {
            "evaluation_profile": reference_evaluation_profile,
        },
        "source_dataset_breakdown": dict(sorted(dataset_counter.items())),
        "snapshot_files": snapshot_files,
        "stats": {
            "question_count": len(questions),
            "question_with_gold_span_count": accepted_item_count,
            "span_count": len(spans),
            "document_count": len(documents),
        },
    }

    write_jsonl(output_dir / "documents.jsonl", documents)
    write_jsonl(output_dir / "questions.jsonl", questions)
    write_jsonl(output_dir / "gold_spans.jsonl", spans)
    write_json(output_dir / "manifest.json", manifest)
    for auxiliary_name in snapshot_files:
        if auxiliary_name in SNAPSHOT_REQUIRED_FILES:
            continue
        source_path = workspace_dir / auxiliary_name
        if source_path.exists():
            shutil.copy2(source_path, output_dir / auxiliary_name)

    return {
        "benchmark_name": benchmark_name,
        "dataset_id": manifest["dataset"]["dataset_id"],
        "question_count": len(questions),
        "question_with_gold_span_count": accepted_item_count,
        "span_count": len(spans),
        "document_count": len(documents),
        "include_review_items": include_review_items,
        "reference_evaluation_profile": reference_evaluation_profile,
    }


def build_report(*, workspace_dir: Path) -> dict[str, Any]:
    """輸出目前 workspace 的整體 curation 狀態。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `dict[str, Any]`：整體摘要。
    """

    prepared_items = read_jsonl(workspace_dir / PREPARED_ITEMS_FILE) if (workspace_dir / PREPARED_ITEMS_FILE).exists() else []
    filtered_items = read_jsonl(workspace_dir / FILTERED_ITEMS_FILE) if (workspace_dir / FILTERED_ITEMS_FILE).exists() else []
    alignment_rows = read_jsonl(workspace_dir / ALIGNMENT_CANDIDATES_FILE) if (workspace_dir / ALIGNMENT_CANDIDATES_FILE).exists() else []
    overrides = read_review_overrides(workspace_dir)

    status_counts = Counter(row.get("status", "unknown") for row in alignment_rows)
    approved_override_count = sum(1 for row in overrides.values() if row.get("decision") == "approved")
    report = {
        "prepared_item_count": len(prepared_items),
        "filtered_item_count": len(filtered_items),
        "alignment_item_count": len(alignment_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "review_override_count": len(overrides),
        "approved_override_count": approved_override_count,
        "auto_match_ratio": round(status_counts.get("auto_matched", 0) / len(filtered_items), 6) if filtered_items else 0.0,
        "generated_at": now_iso(),
    }
    return report


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：將執行結果輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare-source":
        input_path: Path | str
        if args.input_path.startswith(HF_DATASET_REF_SCHEME):
            input_path = args.input_path
        else:
            input_path = Path(args.input_path).resolve()
        summary = prepare_source(
            dataset=args.dataset,
            input_path=input_path,
            workspace_dir=Path(args.workspace_dir).resolve(),
            limit_documents=args.limit_documents,
            limit_items=args.limit_items,
        )
    elif args.command == "filter-items":
        summary = filter_items(workspace_dir=Path(args.workspace_dir).resolve())
    elif args.command == "align-spans":
        summary = align_spans(
            workspace_dir=Path(args.workspace_dir).resolve(),
            area_id=args.area_id,
        )
    elif args.command == "build-snapshot":
        summary = build_snapshot(
            workspace_dir=Path(args.workspace_dir).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            benchmark_name=args.benchmark_name,
            include_review_items=args.include_review_items,
            target_question_count=args.target_question_count,
            reference_evaluation_profile=args.reference_evaluation_profile,
        )
    elif args.command == "report":
        summary = build_report(workspace_dir=Path(args.workspace_dir).resolve())
    else:
        raise ValueError(f"不支援的指令：{args.command}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
