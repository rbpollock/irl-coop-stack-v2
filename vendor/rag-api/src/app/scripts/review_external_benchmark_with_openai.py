"""使用 OpenAI API 對外部 benchmark 題目做 LLM review 與 span 覆核。"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.core.settings import get_settings
from app.scripts.prepare_external_benchmark import (
    ALIGNMENT_REVIEW_QUEUE_FILE,
    ALIGNMENT_CANDIDATES_FILE,
    FILTERED_ITEMS_FILE,
    PREPARED_ITEMS_FILE,
    REVIEW_OVERRIDES_FILE,
    load_ready_documents_for_area,
    now_iso,
    read_jsonl,
    write_jsonl,
)

# review log 檔名，保存每題送給 LLM 的候選視窗與決策結果。
LLM_REVIEW_LOG_FILE = "openai_review_log.jsonl"

# 單一視窗的最大字元數，避免 prompt 成本失控。
WINDOW_MAX_CHARS = 1400

# 每題最多送給 LLM 的候選視窗數。
MAX_WINDOWS_PER_ITEM = 12

# 答案太短時容易造成大量誤命中；短答案主要靠 query lexical signal 補強。
MIN_DIRECT_ANSWER_CHARS = 3


@dataclass(slots=True)
class CandidateWindow:
    """保存單一 review 候選視窗。"""

    window_id: str
    start_offset: int
    end_offset: int
    text: str
    score: float


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 OpenAI review 指令的 parser。
    """

    parser = argparse.ArgumentParser(description="使用 OpenAI API 對外部 benchmark 題目做 LLM review。")
    parser.add_argument("--workspace-dir", required=True, help="benchmark curation workspace。")
    parser.add_argument("--area-id", required=True, help="目標 area id。")
    parser.add_argument("--model", default="gpt-5.4-mini", help="OpenAI model 名稱。")
    parser.add_argument("--max-items", type=int, default=None, help="最多 review 幾題。")
    parser.add_argument("--replace", action="store_true", help="覆蓋既有 review_overrides，而不是 merge。")
    parser.add_argument(
        "--review-source",
        choices=("prepared_items", "filtered_items", "alignment_review_queue"),
        default="prepared_items",
        help="本輪 review 題目來源；預設維持相容，仍從 prepared_items 取題。",
    )
    return parser


def tokenize(text: str) -> set[str]:
    """將字串切成粗粒度 token 集合。

    參數：
    - `text`：輸入字串。

    回傳：
    - `set[str]`：可用於 lexical overlap 的 token 集合。
    """

    return {token for token in re.findall(r"[A-Za-z0-9%$.,/\u4e00-\u9fff-]+", text.lower()) if token}


def overlap_score(query_signal: str, candidate_text: str) -> float:
    """計算 query/answer 與候選片段之間的 lexical overlap。

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


def compact_text(text: str) -> str:
    """將字串壓平成便於弱比對的形式。

    參數：
    - `text`：原始字串。

    回傳：
    - `str`：移除常見分隔符後的字串。
    """

    return re.sub(r"[\s,.$()%/-]+", "", text.lower())


def is_yes_no_answer(answer_text: str) -> bool:
    """判斷答案是否屬於 yes/no 類型。

    參數：
    - `answer_text`：答案文字。

    回傳：
    - `bool`：若屬於 yes/no 類型則回傳真值。
    """

    lowered = answer_text.strip().lower()
    return lowered in {"yes", "no"}


def build_query_signal(item: dict[str, Any]) -> str:
    """建立用於視窗排序的 query signal。

    參數：
    - `item`：prepared / filtered item。

    回傳：
    - `str`：問題、答案與既有 evidence hints 的拼接文字。
    """

    parts = [item.get("query_text", ""), item.get("answer_text", "")]
    parts.extend(text for text in item.get("evidence_texts", []) if isinstance(text, str))
    return " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def extract_query_phrases(query_text: str) -> list[str]:
    """從 query 中抽取可用於 substring seed 的長片語。

    參數：
    - `query_text`：原始題目。

    回傳：
    - `list[str]`：長度較高、較可能直接出現在文件中的 query phrase。
    """

    raw_tokens = [token for token in re.findall(r"[A-Za-z0-9]+", query_text) if token]
    if len(raw_tokens) < 3:
        return []

    phrases: list[str] = []
    max_ngram = min(6, len(raw_tokens))
    for ngram_size in range(max_ngram, 2, -1):
        for start_index in range(0, len(raw_tokens) - ngram_size + 1):
            phrase = " ".join(raw_tokens[start_index : start_index + ngram_size])
            if phrase.lower() in {"what is the", "what was the", "how much did", "in which year"}:
                continue
            phrases.append(phrase)
    deduped: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        lowered = phrase.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(phrase)
    return deduped[:12]


def iter_display_segments(display_text: str) -> list[tuple[int, int, str]]:
    """將 display_text 切成可供 review 的候選片段。

    參數：
    - `display_text`：文件全文。

    回傳：
    - `list[tuple[int, int, str]]`：片段的 offset 與文字內容。
    """

    if not display_text:
        return []

    segments: list[tuple[int, int, str]] = []
    block_pattern = re.compile(r"\n{2,}")
    cursor = 0
    for match in block_pattern.finditer(display_text):
        block = display_text[cursor : match.start()]
        if block.strip():
            segments.append((cursor, match.start(), block.strip()))
        cursor = match.end()
    tail = display_text[cursor:]
    if tail.strip():
        segments.append((cursor, len(display_text), tail.strip()))

    if segments:
        return segments
    return [(0, len(display_text), display_text)]


def build_candidate_windows(*, display_text: str, item: dict[str, Any]) -> list[CandidateWindow]:
    """依 query/answer 訊號為單題建立候選 review 視窗。

    參數：
    - `display_text`：文件全文。
    - `item`：prepared / filtered item。

    回傳：
    - `list[CandidateWindow]`：排序後的候選視窗。
    """

    query_signal = build_query_signal(item)
    answer_text = item.get("answer_text", "").strip()
    evidence_hints = [text.strip() for text in item.get("evidence_texts", []) if isinstance(text, str) and text.strip()]
    query_phrases = extract_query_phrases(item.get("query_text", ""))
    segments = iter_display_segments(display_text)

    candidates: list[CandidateWindow] = []
    for index, (start_offset, end_offset, segment) in enumerate(segments, start=1):
        trimmed = segment[:WINDOW_MAX_CHARS]
        score = overlap_score(query_signal, trimmed)
        compact_segment = compact_text(trimmed)
        if answer_text and len(answer_text) >= MIN_DIRECT_ANSWER_CHARS and compact_text(answer_text) in compact_segment:
            score += 0.35
        if any(compact_text(hint) in compact_segment for hint in evidence_hints if len(hint) >= MIN_DIRECT_ANSWER_CHARS):
            score += 0.25
        if any(phrase.lower() in trimmed.lower() for phrase in query_phrases):
            score += 0.45
        if score <= 0:
            continue
        candidates.append(
            CandidateWindow(
                window_id=f"W{index}",
                start_offset=start_offset,
                end_offset=min(start_offset + len(trimmed), end_offset),
                text=trimmed,
                score=round(score, 6),
            )
        )

    candidates.sort(key=lambda row: (-row.score, row.start_offset))
    deduped: list[CandidateWindow] = []
    seen_texts: set[str] = set()
    for candidate in candidates:
        normalized = candidate.text[:240].strip()
        if normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        deduped.append(candidate)
        if len(deduped) >= MAX_WINDOWS_PER_ITEM:
            break

    if deduped:
        return deduped

    fallback_text = display_text[:WINDOW_MAX_CHARS]
    return [
        CandidateWindow(
            window_id="W1",
            start_offset=0,
            end_offset=len(fallback_text),
            text=fallback_text,
            score=0.0,
        )
    ]


def build_review_prompt(*, item: dict[str, Any], windows: list[CandidateWindow]) -> tuple[str, str]:
    """建立 OpenAI review prompt。

    參數：
    - `item`：待 review 題目。
    - `windows`：候選視窗。

    回傳：
    - `tuple[str, str]`：system prompt 與 user prompt。
    """

    system_prompt = (
        "你是 retrieval benchmark reviewer。"
        "你只能根據提供的候選視窗判斷題目是否有足夠的 fact_lookup 證據。"
        "若有足夠證據，請挑出 1 到 3 段『直接從視窗複製』的原文 quote。"
        "quote 必須與視窗文字逐字一致，不可改寫，不可補字，不可摘要。"
        "若視窗不足以支持答案，必須回 rejected。"
        "輸出必須是 JSON 物件，欄位為 decision, rationale, snippets。"
    )

    user_payload = {
        "question": item.get("query_text", ""),
        "answer": item.get("answer_text", ""),
        "existing_evidence_hints": item.get("evidence_texts", []),
        "windows": [
            {
                "window_id": window.window_id,
                "start_offset": window.start_offset,
                "end_offset": window.end_offset,
                "score": window.score,
                "text": window.text,
            }
            for window in windows
        ],
        "output_schema": {
            "decision": "approved | rejected",
            "rationale": "簡短說明",
            "snippets": [
                {
                    "window_id": "W1",
                    "quote": "必須與視窗逐字一致的原文",
                }
            ],
        },
    }
    return system_prompt, json.dumps(user_payload, ensure_ascii=False, indent=2)


def call_openai_review(*, client: OpenAI, model: str, item: dict[str, Any], windows: list[CandidateWindow]) -> dict[str, Any]:
    """呼叫 OpenAI API 取得 review 決策。

    參數：
    - `client`：OpenAI client。
    - `model`：OpenAI model 名稱。
    - `item`：待 review 題目。
    - `windows`：候選視窗。

    回傳：
    - `dict[str, Any]`：LLM 回傳的 review JSON。
    """

    system_prompt, user_prompt = build_review_prompt(item=item, windows=windows)
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def map_snippets_to_spans(*, review_payload: dict[str, Any], windows_by_id: dict[str, CandidateWindow]) -> list[dict[str, int]]:
    """將 LLM 選中的 quote 映射回原始 display_text offsets。

    參數：
    - `review_payload`：LLM 回傳的 JSON。
    - `windows_by_id`：候選視窗索引。

    回傳：
    - `list[dict[str, int]]`：可寫入 review override 的 spans。
    """

    spans: list[dict[str, int]] = []
    seen_offsets: set[tuple[int, int]] = set()
    for snippet in review_payload.get("snippets", []):
        if not isinstance(snippet, dict):
            continue
        window_id = str(snippet.get("window_id", ""))
        quote = str(snippet.get("quote", "")).strip()
        if not quote:
            continue
        window = windows_by_id.get(window_id)
        if window is None:
            continue
        local_offset = window.text.find(quote)
        if local_offset < 0:
            continue
        start_offset = window.start_offset + local_offset
        end_offset = start_offset + len(quote)
        offset_key = (start_offset, end_offset)
        if offset_key in seen_offsets:
            continue
        seen_offsets.add(offset_key)
        spans.append({"start_offset": start_offset, "end_offset": end_offset})
    return spans


def _load_review_source_rows(*, workspace_dir: Path, review_source: str) -> list[dict[str, Any]]:
    """依指定來源載入可供 review 的題目列。

    參數：
    - `workspace_dir`：benchmark curation workspace。
    - `review_source`：review 題目來源。

    回傳：
    - `list[dict[str, Any]]`：指定來源的題目列表。
    """

    if review_source == "prepared_items":
        return read_jsonl(workspace_dir / PREPARED_ITEMS_FILE)
    if review_source == "filtered_items":
        return read_jsonl(workspace_dir / FILTERED_ITEMS_FILE)
    if review_source == "alignment_review_queue":
        return read_jsonl(workspace_dir / ALIGNMENT_REVIEW_QUEUE_FILE)
    raise ValueError(f"不支援的 review_source：{review_source}")


def load_review_candidates(*, workspace_dir: Path, review_source: str) -> list[dict[str, Any]]:
    """載入可供 LLM review 的題目。

    參數：
    - `workspace_dir`：benchmark curation workspace。
    - `review_source`：review 題目來源。

    回傳：
    - `list[dict[str, Any]]`：可 review 的題目列表。
    """

    candidate_rows = _load_review_source_rows(workspace_dir=workspace_dir, review_source=review_source)
    candidates: list[dict[str, Any]] = []
    for item in candidate_rows:
        query_text = str(item.get("query_text", "")).strip()
        answer_text = str(item.get("answer_text", "")).strip()
        if not query_text:
            continue
        if not answer_text:
            continue
        if is_yes_no_answer(answer_text):
            continue
        candidates.append(item)
    return candidates


def merge_alignment_rows(*, workspace_dir: Path, review_items: list[dict[str, Any]]) -> None:
    """將缺少 alignment row 的 review 題目補入 alignment_candidates。

    參數：
    - `workspace_dir`：benchmark curation workspace。
    - `review_items`：本輪 review 題目。

    回傳：
    - `None`：必要時會更新 `alignment_candidates.jsonl`。
    """

    alignment_path = workspace_dir / ALIGNMENT_CANDIDATES_FILE
    existing_rows = read_jsonl(alignment_path) if alignment_path.exists() else []
    existing_item_ids = {row["item_id"] for row in existing_rows}

    for item in review_items:
        if item["item_id"] in existing_item_ids:
            continue
        existing_rows.append(
            {
                "item_id": item["item_id"],
                "dataset": item["dataset"],
                "file_name": item["file_name"],
                "query_text": item["query_text"],
                "answer_text": item.get("answer_text"),
                "language": item["language"],
                "query_type": item["query_type"],
                "status": "needs_review",
                "accepted_spans": [],
                "review_candidates": [],
                "rejected_evidences": [],
                "source_metadata": item.get("source_metadata", {}),
                "generated_at": now_iso(),
            }
        )

    write_jsonl(alignment_path, existing_rows)


def review_with_openai(
    *,
    workspace_dir: Path,
    area_id: str,
    model: str,
    max_items: int | None,
    replace: bool,
    review_source: str,
) -> dict[str, Any]:
    """執行 OpenAI review，並輸出 review overrides 與 log。

    參數：
    - `workspace_dir`：benchmark curation workspace。
    - `area_id`：目標 area id。
    - `model`：OpenAI model 名稱。
    - `max_items`：最多處理幾題；`None` 代表全部。
    - `replace`：是否覆蓋既有 overrides。
    - `review_source`：review 題目來源。

    回傳：
    - `dict[str, Any]`：review 摘要。
    """

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("使用 OpenAI review 前必須提供 OPENAI_API_KEY。")

    ready_documents = load_ready_documents_for_area(area_id=area_id)
    review_items = [
        item for item in load_review_candidates(workspace_dir=workspace_dir, review_source=review_source) if item["file_name"] in ready_documents
    ]
    if max_items is not None:
        review_items = review_items[:max_items]

    client = OpenAI(api_key=settings.openai_api_key)
    overrides_path = workspace_dir / REVIEW_OVERRIDES_FILE
    existing_overrides = {} if replace else {row["item_id"]: row for row in read_jsonl(overrides_path)} if overrides_path.exists() else {}
    logs: list[dict[str, Any]] = []

    approved_count = 0
    rejected_count = 0
    for item in review_items:
        document = ready_documents[item["file_name"]]
        display_text = document.display_text or ""
        windows = build_candidate_windows(display_text=display_text, item=item)
        windows_by_id = {window.window_id: window for window in windows}
        review_payload = call_openai_review(client=client, model=model, item=item, windows=windows)
        spans = map_snippets_to_spans(review_payload=review_payload, windows_by_id=windows_by_id)
        decision = "approved" if review_payload.get("decision") == "approved" and spans else "rejected"
        if decision == "approved":
            approved_count += 1
            existing_overrides[item["item_id"]] = {
                "item_id": item["item_id"],
                "decision": "approved",
                "spans": spans,
            }
        else:
            rejected_count += 1
        logs.append(
            {
                "item_id": item["item_id"],
                "file_name": item["file_name"],
                "query_text": item["query_text"],
                "answer_text": item.get("answer_text"),
                "decision": decision,
                "rationale": review_payload.get("rationale", ""),
                "spans": spans,
                "windows": [
                    {
                        "window_id": window.window_id,
                        "start_offset": window.start_offset,
                        "end_offset": window.end_offset,
                        "score": window.score,
                    }
                    for window in windows
                ],
                "generated_at": now_iso(),
            }
        )

    review_rows = sorted(existing_overrides.values(), key=lambda row: row["item_id"])
    write_jsonl(overrides_path, review_rows)
    write_jsonl(workspace_dir / LLM_REVIEW_LOG_FILE, logs)
    merge_alignment_rows(workspace_dir=workspace_dir, review_items=review_items)

    return {
        "workspace_dir": str(workspace_dir),
        "model": model,
        "review_source": review_source,
        "review_item_count": len(review_items),
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "override_count": len(review_rows),
        "log_file": LLM_REVIEW_LOG_FILE,
    }


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：將執行結果輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    summary = review_with_openai(
        workspace_dir=Path(args.workspace_dir).resolve(),
        area_id=args.area_id,
        model=args.model,
        max_items=args.max_items,
        replace=args.replace,
        review_source=args.review_source,
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
