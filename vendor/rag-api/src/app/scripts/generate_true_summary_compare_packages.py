"""從真實外部資料集提取 summary/compare benchmark packages。"""

from __future__ import annotations

from collections import OrderedDict
import json
import re
from pathlib import Path
import shutil
from typing import Any

from datasets import load_dataset
from huggingface_hub import hf_hub_download
import pandas as pd
import requests


# 套件題數上限。
PACKAGE_ITEM_COUNT = 10
# 真實資料集 suite 名稱。
SUITE_NAME = "summary-compare-real-curated-v1"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """將字典寫成 JSON 檔。

    參數：
    - `path`：輸出路徑。
    - `payload`：要序列化的字典。

    回傳：
    - `None`：僅寫入檔案。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """將多筆 row 寫成 JSONL。

    參數：
    - `path`：輸出路徑。
    - `rows`：JSON 可序列化 row 清單。

    回傳：
    - `None`：僅寫入檔案。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_readme(
    *,
    package_dir: Path,
    title: str,
    purpose_en: str,
    purpose_zh: str,
    provenance_en: list[str],
    provenance_zh: list[str],
    reproduction_en: list[str],
    reproduction_zh: list[str],
) -> None:
    """建立簡易 README 中英雙語檔案。

    參數：
    - `package_dir`：package 目錄。
    - `title`：README 標題。
    - `purpose_en`：英文用途說明。
    - `purpose_zh`：中文用途說明。

    回傳：
    - `None`：僅寫入檔案。
    """

    (package_dir / "README.md").write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                "## Purpose",
                "",
                purpose_en,
                "",
                "## Provenance",
                "",
                *[f"- {line}" for line in provenance_en],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package_dir / "README.zh-TW.md").write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                "## 用途",
                "",
                purpose_zh,
                "",
                "## 資料來源與還原依據",
                "",
                *[f"- {line}" for line in provenance_zh],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package_dir / "reproduce.md").write_text(
        "\n".join(
            [
                "# Reproduce",
                "",
                "## English",
                "",
                *[f"{index}. {line}" for index, line in enumerate(reproduction_en, start=1)],
                "",
                "## 繁體中文",
                "",
                *[f"{index}. {line}" for index, line in enumerate(reproduction_zh, start=1)],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package_dir / "reference_run_summary.json").write_text(
        json.dumps({"main_score": 0.0}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _reset_dir(path: Path) -> None:
    """清空既有目錄並重新建立。

    參數：
    - `path`：要重建的目錄。

    回傳：
    - `None`：僅重建目錄。
    """

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _sentence_split(text: str, *, lang: str) -> list[str]:
    """以簡單規則切句。

    參數：
    - `text`：輸入文字。
    - `lang`：`en` 或 `zh`。

    回傳：
    - `list[str]`：切句後的片段。
    """

    if lang == "zh":
        parts = re.split(r"[。！？]", text)
    else:
        parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _claims_from_summary(summary: str, *, lang: str) -> list[str]:
    """從 summary 擷取 1 到 2 個 claims。

    參數：
    - `summary`：參考摘要。
    - `lang`：語系。

    回傳：
    - `list[str]`：截短後的 claims。
    """

    claims = _sentence_split(summary, lang=lang)[:2]
    if not claims:
        claims = [summary.strip()[:120]]
    return [claim[:120] for claim in claims]


def _safe_filename(prefix: str, index: int, *, suffix: str = ".md") -> str:
    """建立穩定檔名。

    參數：
    - `prefix`：前綴。
    - `index`：索引。
    - `suffix`：副檔名。

    回傳：
    - `str`：穩定檔名。
    """

    return f"{prefix}-{index:02d}{suffix}"


def _normalize_lcsts_input(text: str) -> str:
    """移除 LCSTS row 前綴說明文字。

    參數：
    - `text`：原始 article。

    回傳：
    - `str`：去除 instruction 後的 article。
    """

    prefix = "在本任务中，您将获得一段文本，您的任务是生成该文本的摘要。"
    return text[len(prefix):].strip() if text.startswith(prefix) else text.strip()


def _build_dataset_provenance(
    *,
    source_name: str,
    upstream_url: str,
    source_split: str,
    extraction_rule: str,
    note: str | None = None,
) -> dict[str, object]:
    """建立標準化 dataset provenance payload。

    參數：
    - `source_name`：資料集名稱。
    - `upstream_url`：上游來源 URL。
    - `source_split`：使用的 split。
    - `extraction_rule`：抽取規則。
    - `note`：可選補充說明。

    回傳：
    - `dict[str, object]`：標準化 provenance payload。
    """

    payload: dict[str, object] = {
        "source_name": source_name,
        "upstream_url": upstream_url,
        "source_split": source_split,
        "extraction_rule": extraction_rule,
    }
    if note:
        payload["note"] = note
    return payload


def build_qmsum_package(*, root: Path) -> None:
    """建立 QMSum query summary package。

    參數：
    - `root`：benchmarks 根目錄。

    回傳：
    - `None`：直接寫入 package。
    """

    package_dir = root / "qmsum-query-summary-curated-pilot-v1"
    source_dir = package_dir / "source_documents"
    _reset_dir(package_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    text = requests.get(
        "https://raw.githubusercontent.com/Yale-LILY/QMSum/master/data/ALL/jsonl/test.jsonl",
        timeout=60,
    ).text
    meetings = [json.loads(line) for line in text.splitlines() if line.strip()]

    rows: list[dict[str, Any]] = []
    document_written: set[str] = set()
    item_index = 0
    meeting_index = 0
    while item_index < PACKAGE_ITEM_COUNT and meeting_index < len(meetings):
        meeting = meetings[meeting_index]
        file_name = _safe_filename("qmsum-meeting", meeting_index + 1)
        if file_name not in document_written:
            transcript_lines = []
            for turn in meeting["meeting_transcripts"]:
                transcript_lines.append(f"### {turn['speaker']}\n{turn['content']}")
            (source_dir / file_name).write_text("\n\n".join(transcript_lines), encoding="utf-8")
            document_written.add(file_name)

        topics = meeting.get("topic_list", [])
        for local_query_index, query_payload in enumerate(meeting.get("specific_query_list", [])):
            if item_index >= PACKAGE_ITEM_COUNT:
                break
            span = query_payload.get("relevant_text_span", [])
            expected_headings = []
            if span:
                start = int(span[0][0]) - 1
                end = int(span[0][1]) - 1
                gold_refs = [
                    {"file_name": file_name, "quote": meeting["meeting_transcripts"][start]["content"][:240]},
                    {"file_name": file_name, "quote": meeting["meeting_transcripts"][min(end, start + 1)]["content"][:240]},
                ]
                for topic in topics:
                    if topic.get("relevant_text_span") == span:
                        expected_headings.append(topic.get("topic", "meeting topic"))
            else:
                gold_refs = [{"file_name": file_name, "quote": meeting["meeting_transcripts"][0]["content"][:240]}]
            item_index += 1
            rows.append(
                {
                    "id": f"qmsum-summary-{item_index}",
                    "language": "en",
                    "task_type": "document_summary",
                    "question": query_payload["query"],
                    "summary_strategy": "section_focused",
                    "expected_document_names": [file_name],
                    "expected_section_headings": expected_headings,
                    "required_claims_or_axes": _claims_from_summary(query_payload["answer"], lang="en"),
                    "gold_span_refs": gold_refs,
                    "reference_answer": query_payload["answer"],
                    "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": [file_name]},
                    "allows_insufficient_evidence": False,
                    "source_dataset": "QMSum",
                    "source_split": "test",
                    "source_record_index": meeting_index,
                    "source_example_id": f"qmsum-test-meeting-{meeting_index}-query-{local_query_index}",
                    "source_mapping": {
                        "query_group": "specific_query_list",
                        "query_index": local_query_index,
                        "meeting_file_name": file_name,
                    },
                }
            )
        meeting_index += 1

    _write_json(
        package_dir / "manifest.json",
        {
            "benchmark_name": package_dir.name,
            "version": "2.0.0",
            "description": "Officially extracted QMSum query-conditioned summary package.",
            "language": "en",
            "task_family": "summary",
            "item_count": len(rows),
            "dataset_provenance": _build_dataset_provenance(
                source_name="QMSum",
                upstream_url="https://github.com/Yale-LILY/QMSum/blob/master/data/ALL/jsonl/test.jsonl",
                source_split="test",
                extraction_rule="Take the first 10 items from `specific_query_list` in test meetings, preserving original order.",
                note="Each benchmark item records the source meeting index and the local query index used for extraction.",
            ),
        },
    )
    _write_jsonl(package_dir / "questions.jsonl", rows)
    _write_readme(
        package_dir=package_dir,
        title=package_dir.name,
        purpose_en="10 real QMSum query-conditioned summary items extracted from the official test split.",
        purpose_zh="從 QMSum 官方 test split 提取的 `10` 題 query-conditioned summary 真實資料 package。",
        provenance_en=[
            "Upstream dataset: QMSum official test split.",
            "Upstream file: `data/ALL/jsonl/test.jsonl` in the official Yale-LILY repository.",
            "Extraction rule: preserve original meeting order and take the first 10 `specific_query_list` items.",
            "Each item stores `source_record_index`, `source_example_id`, and `source_mapping.query_index` for exact trace-back.",
        ],
        provenance_zh=[
            "上游資料集：QMSum 官方 test split。",
            "上游檔案：Yale-LILY 官方 repo 的 `data/ALL/jsonl/test.jsonl`。",
            "抽取規則：依原始會議順序，從 `specific_query_list` 取前 `10` 題。",
            "每題都保存 `source_record_index`、`source_example_id` 與 `source_mapping.query_index`，可直接回對原始 row。",
        ],
        reproduction_en=[
            "Download the official `test.jsonl` from the Yale-LILY QMSum repository.",
            "Parse each meeting row and keep the first 10 `specific_query_list` entries in original order.",
            "Render the corresponding `meeting_transcripts` into `source_documents/qmsum-meeting-XX.md`.",
            "Use the stored `source_record_index` and `source_mapping.query_index` to verify each question against the raw JSONL.",
        ],
        reproduction_zh=[
            "從 Yale-LILY 官方 QMSum repo 下載 `test.jsonl`。",
            "逐筆解析 meeting row，依原始順序保留前 `10` 個 `specific_query_list` 題目。",
            "把對應的 `meeting_transcripts` 轉成 `source_documents/qmsum-meeting-XX.md`。",
            "透過每題保存的 `source_record_index` 與 `source_mapping.query_index` 回查原始 JSONL。",        
        ],
    )


def build_multinews_package(*, root: Path) -> None:
    """建立 Multi-News multi-doc summary package。

    參數：
    - `root`：benchmarks 根目錄。

    回傳：
    - `None`：直接寫入 package。
    """

    package_dir = root / "multinews-multi-doc-summary-curated-pilot-v1"
    source_dir = package_dir / "source_documents"
    _reset_dir(package_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    src_path = hf_hub_download(repo_id="alexfabbri/multi_news", repo_type="dataset", filename="data/test.src.cleaned")
    tgt_path = hf_hub_download(repo_id="alexfabbri/multi_news", repo_type="dataset", filename="data/test.tgt")
    rows: list[dict[str, Any]] = []
    with open(src_path, encoding="utf-8") as src_file, open(tgt_path, encoding="utf-8") as tgt_file:
        for index, (src_line, tgt_line) in enumerate(zip(src_file, tgt_file), start=1):
            if index > PACKAGE_ITEM_COUNT:
                break
            document = src_line.strip().replace("NEWLINE_CHAR", "\n")
            docs = [part.strip() for part in document.split("|||||") if part.strip()][:3]
            file_names = []
            gold_refs = []
            for doc_index, doc_text in enumerate(docs, start=1):
                file_name = f"multinews-{index:02d}-doc-{doc_index}.md"
                (source_dir / file_name).write_text(doc_text, encoding="utf-8")
                file_names.append(file_name)
                sentence = _sentence_split(doc_text, lang="en")[0]
                gold_refs.append({"file_name": file_name, "quote": sentence[:240]})
            summary = tgt_line.strip()
            rows.append(
                {
                    "id": f"multinews-summary-{index}",
                    "language": "en",
                    "task_type": "document_summary",
                    "question": "Summarize the common themes and key developments across these news reports.",
                    "summary_strategy": "multi_document_theme",
                    "expected_document_names": file_names,
                    "expected_section_headings": [],
                    "required_claims_or_axes": _claims_from_summary(summary, lang="en"),
                    "gold_span_refs": gold_refs,
                    "reference_answer": summary,
                    "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": file_names},
                    "allows_insufficient_evidence": False,
                    "source_dataset": "Multi-News",
                    "source_split": "test",
                    "source_record_index": index - 1,
                    "source_example_id": f"multinews-test-{index - 1}",
                    "source_mapping": {
                        "source_file": "data/test.src.cleaned",
                        "summary_file": "data/test.tgt",
                        "document_count": len(file_names),
                    },
                }
            )

    _write_json(
        package_dir / "manifest.json",
        {
            "benchmark_name": package_dir.name,
            "version": "2.0.0",
            "description": "Officially extracted Multi-News multi-document summary package.",
            "language": "en",
            "task_family": "summary",
            "item_count": len(rows),
            "dataset_provenance": _build_dataset_provenance(
                source_name="Multi-News",
                upstream_url="https://huggingface.co/datasets/alexfabbri/multi_news",
                source_split="test",
                extraction_rule="Take the first 10 rows from the official test set, preserving article order and splitting documents by the `|||||` separator.",
                note="Each row stores the original line index from `test.src.cleaned` / `test.tgt`.",
            ),
        },
    )
    _write_jsonl(package_dir / "questions.jsonl", rows)
    _write_readme(
        package_dir=package_dir,
        title=package_dir.name,
        purpose_en="10 real Multi-News items extracted from the official test set.",
        purpose_zh="從 Multi-News 官方 test set 提取的 `10` 題多文件摘要真實資料 package。",
        provenance_en=[
            "Upstream dataset: Multi-News official test split.",
            "Upstream files: `data/test.src.cleaned` and `data/test.tgt` from the dataset repo.",
            "Extraction rule: preserve original line order and take the first 10 rows.",
            "Each item stores the original line index in `source_record_index`.",
        ],
        provenance_zh=[
            "上游資料集：Multi-News 官方 test split。",
            "上游檔案：資料集 repo 的 `data/test.src.cleaned` 與 `data/test.tgt`。",
            "抽取規則：保留原始行順序，取前 `10` 筆。",
            "每題都在 `source_record_index` 保存原始行號。",        
        ],
        reproduction_en=[
            "Download `data/test.src.cleaned` and `data/test.tgt` from the official Multi-News dataset repository.",
            "Read the first 10 aligned rows in original order.",
            "Split each source row on `|||||` to reconstruct the individual source documents.",
            "Use `source_record_index` to verify the exact original source-summary pair.",
        ],
        reproduction_zh=[
            "從官方 Multi-News 資料集 repo 下載 `data/test.src.cleaned` 與 `data/test.tgt`。",
            "按原始順序讀取前 `10` 筆對齊資料。",
            "用 `|||||` 分隔符把每筆 source row 還原成多份來源文件。",
            "透過 `source_record_index` 回查原始 source-summary 配對。",        
        ],
    )


def build_cocotrip_package(*, root: Path) -> None:
    """建立 CoCoTrip compare package。

    參數：
    - `root`：benchmarks 根目錄。

    回傳：
    - `None`：直接寫入 package。
    """

    package_dir = root / "cocotrip-compare-curated-pilot-v1"
    source_dir = package_dir / "source_documents"
    _reset_dir(package_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    anno = requests.get(
        "https://raw.githubusercontent.com/megagonlabs/cocosum/master/data/anno.json",
        timeout=60,
    ).json()
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(anno["test"][:PACKAGE_ITEM_COUNT], start=1):
        file_name_a = f"cocotrip-{index:02d}-entity-a.md"
        file_name_b = f"cocotrip-{index:02d}-entity-b.md"
        entity_a_doc = "# Entity A\n\n" + "\n\n".join(item["entity_a_summary"])
        entity_b_doc = "# Entity B\n\n" + "\n\n".join(item["entity_b_summary"])
        (source_dir / file_name_a).write_text(entity_a_doc, encoding="utf-8")
        (source_dir / file_name_b).write_text(entity_b_doc, encoding="utf-8")
        reference_answer = (
            f"Entity A: {item['entity_a_summary'][0]} "
            f"Entity B: {item['entity_b_summary'][0]} "
            f"Shared points: {item['common_summary'][0]}"
        )
        rows.append(
            {
                "id": f"cocotrip-compare-{index}",
                "language": "en",
                "task_type": "cross_document_compare",
                "question": "Compare the two travel entities based on the provided review summaries. Include the main strengths of each entity and any shared points.",
                "comparison_axes": ["entity A strengths", "entity B strengths", "shared points"],
                "expected_document_names": [file_name_a, file_name_b],
                "required_claims_or_axes": _claims_from_summary(reference_answer, lang="en"),
                "gold_span_refs": [
                    {"file_name": file_name_a, "quote": item["entity_a_summary"][0][:240]},
                    {"file_name": file_name_b, "quote": item["entity_b_summary"][0][:240]},
                ],
                "reference_answer": reference_answer,
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": [file_name_a, file_name_b]},
                "allows_insufficient_evidence": False,
                "source_dataset": "CoCoTrip / CoCoSum",
                "source_split": "test",
                "source_record_index": index - 1,
                "source_example_id": f"cocotrip-test-{index - 1}",
                "source_mapping": {
                    "annotation_file": "data/anno.json",
                    "entity_a_id": item["entity_a"],
                    "entity_b_id": item["entity_b"],
                },
            }
        )

    _write_json(
        package_dir / "manifest.json",
        {
            "benchmark_name": package_dir.name,
            "version": "2.0.0",
            "description": "Officially extracted CoCoTrip-derived compare package using annotated entity summaries.",
            "language": "en",
            "task_family": "compare",
            "item_count": len(rows),
            "dataset_provenance": _build_dataset_provenance(
                source_name="CoCoTrip / CoCoSum",
                upstream_url="https://github.com/megagonlabs/cocosum/blob/master/data/anno.json",
                source_split="test",
                extraction_rule="Take the first 10 entries from the official `anno.json` test split and preserve both entity summary lists plus common summary.",
                note="Each item stores the original test index and both original entity ids.",
            ),
        },
    )
    _write_jsonl(package_dir / "questions.jsonl", rows)
    _write_readme(
        package_dir=package_dir,
        title=package_dir.name,
        purpose_en="10 real CoCoTrip-derived compare items extracted from the official annotation file.",
        purpose_zh="從 CoCoTrip 官方標註檔提取的 `10` 題 compare 真實資料 package。",
        provenance_en=[
            "Upstream dataset: CoCoTrip annotations from the official CoCoSum repository.",
            "Upstream file: `data/anno.json`.",
            "Extraction rule: preserve original `test` order and take the first 10 entries.",
            "Each item stores the original test index plus `entity_a_id` and `entity_b_id`.",
        ],
        provenance_zh=[
            "上游資料集：CoCoSum 官方 repo 中的 CoCoTrip 標註資料。",
            "上游檔案：`data/anno.json`。",
            "抽取規則：保留 `test` split 原始順序，取前 `10` 筆。",
            "每題都保存原始 test index，以及 `entity_a_id` / `entity_b_id`。",        
        ],
        reproduction_en=[
            "Download `data/anno.json` from the official CoCoSum repository.",
            "Read the `test` split and take the first 10 entries in order.",
            "Render `entity_a_summary` and `entity_b_summary` into the two source documents for each item.",
            "Use `source_record_index`, `entity_a_id`, and `entity_b_id` to verify the original annotation entry.",
        ],
        reproduction_zh=[
            "從官方 CoCoSum repo 下載 `data/anno.json`。",
            "讀取 `test` split，依順序取前 `10` 筆。",
            "把每筆的 `entity_a_summary` 與 `entity_b_summary` 分別寫成兩份 source documents。",
            "透過 `source_record_index`、`entity_a_id`、`entity_b_id` 回查原始標註。",        
        ],
    )


def build_lcsts_package(*, root: Path) -> None:
    """建立 LCSTS 中文摘要 package。

    參數：
    - `root`：benchmarks 根目錄。

    回傳：
    - `None`：直接寫入 package。
    """

    package_dir = root / "lcsts-news-summary-curated-pilot-v1"
    source_dir = package_dir / "source_documents"
    _reset_dir(package_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset("suolyer/lcsts", split=f"test[:{PACKAGE_ITEM_COUNT}]")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(dataset, start=1):
        article = _normalize_lcsts_input(item["input"])
        file_name = _safe_filename("lcsts-article", index)
        (source_dir / file_name).write_text(article, encoding="utf-8")
        rows.append(
            {
                "id": f"lcsts-summary-{index}",
                "language": "zh-TW",
                "task_type": "document_summary",
                "question": "請摘要這篇新聞的重點。",
                "summary_strategy": "document_overview",
                "expected_document_names": [file_name],
                "expected_section_headings": [],
                "required_claims_or_axes": _claims_from_summary(item["output"], lang="zh"),
                "gold_span_refs": [{"file_name": file_name, "quote": _sentence_split(article, lang="zh")[0][:240]}],
                "reference_answer": item["output"],
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": [file_name]},
                "allows_insufficient_evidence": False,
                "source_dataset": "LCSTS",
                "source_split": "test",
                "source_record_index": index - 1,
                    "source_example_id": f"lcsts-test-{index - 1}",
                    "source_mapping": {
                        "input_field": "input",
                        "summary_field": "output",
                        "original_id": item["id"],
                    },
                }
            )

    _write_json(
        package_dir / "manifest.json",
        {
            "benchmark_name": package_dir.name,
            "version": "1.0.0",
            "description": "Officially extracted LCSTS Chinese news summary package.",
            "language": "zh-TW",
            "task_family": "summary",
            "item_count": len(rows),
            "dataset_provenance": _build_dataset_provenance(
                source_name="LCSTS",
                upstream_url="https://huggingface.co/datasets/suolyer/lcsts",
                source_split="test",
                extraction_rule="Take the first 10 rows from the official test split after removing the instruction prefix from `input`.",
                note="Each item stores the zero-based row index as the stable key, and keeps the raw LCSTS `id` in `source_mapping.original_id`.",
            ),
        },
    )
    _write_jsonl(package_dir / "questions.jsonl", rows)
    _write_readme(
        package_dir=package_dir,
        title=package_dir.name,
        purpose_en="10 real LCSTS Chinese news summarization items extracted from the official test split.",
        purpose_zh="從 LCSTS 官方 test split 提取的 `10` 題中文新聞摘要真實資料 package。",
        provenance_en=[
            "Upstream dataset: LCSTS official test split.",
            "Upstream source: Hugging Face dataset `suolyer/lcsts`.",
            "Extraction rule: take the first 10 test rows and strip the shared instruction prefix from `input`.",
            "Each item stores the zero-based row index as the stable key and keeps the raw LCSTS `id` in `source_mapping.original_id`.",
        ],
        provenance_zh=[
            "上游資料集：LCSTS 官方 test split。",
            "上游來源：Hugging Face `suolyer/lcsts`。",
            "抽取規則：取 test split 前 `10` 筆，並移除 `input` 欄位共用的 instruction 前綴。",
            "每題都保存 test split 的零起算 row index 作為穩定鍵，原始 LCSTS `id` 則保留在 `source_mapping.original_id`。",        
        ],
        reproduction_en=[
            "Load `suolyer/lcsts` from Hugging Face.",
            "Read the official `test` split and keep the first 10 rows.",
            "Remove the instruction prefix from `input` before writing the source document.",
            "Use `source_example_id` and `source_record_index` as the stable lookup key, then verify the raw LCSTS id via `source_mapping.original_id`.",
        ],
        reproduction_zh=[
            "從 Hugging Face 載入 `suolyer/lcsts`。",
            "讀取官方 `test` split，保留前 `10` 筆。",
            "寫 source document 前先移除 `input` 的 instruction 前綴。",
            "透過 `source_example_id` 與 `source_record_index` 回查每筆提取結果，原始 LCSTS `id` 則用 `source_mapping.original_id` 驗證。",        
        ],
    )


def build_cnewsum_package(*, root: Path) -> None:
    """建立 CNewSum 中文摘要 package。

    參數：
    - `root`：benchmarks 根目錄。

    回傳：
    - `None`：直接寫入 package。
    """

    package_dir = root / "cnewsum-news-summary-curated-pilot-v1"
    source_dir = package_dir / "source_documents"
    _reset_dir(package_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = hf_hub_download(
        repo_id="ethanhao2077/cnewsum-processed",
        repo_type="dataset",
        filename="data/test-00000-of-00001.parquet",
    )
    dataframe = pd.read_parquet(parquet_path).head(PACKAGE_ITEM_COUNT)
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(dataframe.to_dict(orient="records"), start=1):
        article = str(row["article"]).replace("。", "。\n")
        file_name = _safe_filename("cnewsum-article", index)
        (source_dir / file_name).write_text(article, encoding="utf-8")
        rows.append(
            {
                "id": f"cnewsum-summary-{index}",
                "language": "zh-TW",
                "task_type": "document_summary",
                "question": "請摘要這篇新聞的核心事件與主要結論。",
                "summary_strategy": "document_overview",
                "expected_document_names": [file_name],
                "expected_section_headings": [],
                "required_claims_or_axes": _claims_from_summary(str(row["summary"]), lang="zh"),
                "gold_span_refs": [{"file_name": file_name, "quote": _sentence_split(str(row['article']), lang='zh')[0][:240]}],
                "reference_answer": str(row["summary"]),
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": [file_name]},
                "allows_insufficient_evidence": False,
                "source_dataset": "CNewSum processed",
                "source_split": "test",
                "source_record_index": index - 1,
                "source_example_id": str(row["id"]),
                "source_mapping": {
                    "parquet_file": "data/test-00000-of-00001.parquet",
                    "label": row.get("label"),
                },
            }
        )

    _write_json(
        package_dir / "manifest.json",
        {
            "benchmark_name": package_dir.name,
            "version": "1.0.0",
            "description": "Officially extracted CNewSum Chinese news summary package.",
            "language": "zh-TW",
            "task_family": "summary",
            "item_count": len(rows),
            "dataset_provenance": _build_dataset_provenance(
                source_name="CNewSum processed",
                upstream_url="https://huggingface.co/datasets/ethanhao2077/cnewsum-processed",
                source_split="test",
                extraction_rule="Take the first 10 rows from the processed test parquet, preserving original article and summary.",
                note="Each item stores the original `id`, zero-based row index, and `label` value from the processed dataset.",
            ),
        },
    )
    _write_jsonl(package_dir / "questions.jsonl", rows)
    _write_readme(
        package_dir=package_dir,
        title=package_dir.name,
        purpose_en="10 real CNewSum news summarization items extracted from the processed test split.",
        purpose_zh="從 CNewSum processed test split 提取的 `10` 題中文新聞摘要真實資料 package。",
        provenance_en=[
            "Upstream dataset: CNewSum processed test split.",
            "Upstream source: Hugging Face dataset `ethanhao2077/cnewsum-processed`.",
            "Extraction rule: take the first 10 rows from `data/test-00000-of-00001.parquet`.",
            "Each item stores the original dataset `id`, zero-based row index, and processed `label`.",
        ],
        provenance_zh=[
            "上游資料集：CNewSum processed test split。",
            "上游來源：Hugging Face `ethanhao2077/cnewsum-processed`。",
            "抽取規則：從 `data/test-00000-of-00001.parquet` 取前 `10` 筆。",
            "每題都保存原始資料集 `id`、零起算 row index 與 processed `label`。",        
        ],
        reproduction_en=[
            "Download `data/test-00000-of-00001.parquet` from `ethanhao2077/cnewsum-processed`.",
            "Read the parquet in original order and keep the first 10 rows.",
            "Write each `article` into a source document and keep the paired `summary` as `reference_answer`.",
            "Use `source_example_id` and `source_record_index` to verify the original row.",
        ],
        reproduction_zh=[
            "從 `ethanhao2077/cnewsum-processed` 下載 `data/test-00000-of-00001.parquet`。",
            "依原始順序讀取 parquet，保留前 `10` 筆。",
            "把每筆 `article` 寫成 source document，並把配對的 `summary` 保留成 `reference_answer`。",
            "透過 `source_example_id` 與 `source_record_index` 回查原始 row。",        
        ],
    )


def build_suite(*, root: Path) -> None:
    """建立 summary/compare 真資料 suite manifest。

    參數：
    - `root`：benchmarks 根目錄。

    回傳：
    - `None`：直接寫入 suite manifest 與 README。
    """

    suite_dir = root / SUITE_NAME
    _reset_dir(suite_dir)
    _write_json(
        suite_dir / "manifest.json",
        {
            "benchmark_name": SUITE_NAME,
            "version": "1.0.0",
            "description": "Summary/compare suite generated from real external datasets.",
            "dataset_packages": [
                "../qmsum-query-summary-curated-pilot-v1",
                "../multinews-multi-doc-summary-curated-pilot-v1",
                "../cocotrip-compare-curated-pilot-v1",
                "../lcsts-news-summary-curated-pilot-v1",
                "../cnewsum-news-summary-curated-pilot-v1",
            ],
            "suite_provenance": {
                "policy": "Every package must be reconstructable from public upstream files using recorded source split, row index, and original example id.",
                "generated_by": "app.scripts.generate_true_summary_compare_packages",
            },
        },
    )
    (suite_dir / "README.md").write_text(
        "# summary-compare-real-curated-v1\n\nThis suite contains only packages extracted from real external datasets.\n\nEach package records upstream source, split, row index, and original example id so the benchmark can be independently reconstructed.\n",
        encoding="utf-8",
    )
    (suite_dir / "README.zh-TW.md").write_text(
        "# summary-compare-real-curated-v1\n\n此 suite 只包含從真實外部資料集提取的 packages。\n\n每個 package 都會記錄上游來源、split、row index 與原始 example id，方便外部獨立重建。\n",
        encoding="utf-8",
    )


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：直接在 `benchmarks/` 生成真資料 packages。
    """

    root = Path(__file__).resolve().parents[5] / "benchmarks"
    build_qmsum_package(root=root)
    build_multinews_package(root=root)
    build_cocotrip_package(root=root)
    build_lcsts_package(root=root)
    build_cnewsum_package(root=root)
    build_suite(root=root)


if __name__ == "__main__":
    main()
