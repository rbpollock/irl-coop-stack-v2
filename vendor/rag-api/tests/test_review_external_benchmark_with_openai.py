"""外部 benchmark OpenAI review 腳本測試。"""

from __future__ import annotations

import json
from pathlib import Path

from app.scripts.prepare_external_benchmark import ALIGNMENT_REVIEW_QUEUE_FILE, FILTERED_ITEMS_FILE, PREPARED_ITEMS_FILE
from app.scripts.review_external_benchmark_with_openai import load_review_candidates


def test_load_review_candidates_can_scope_to_alignment_review_queue(tmp_path: Path) -> None:
    """review 腳本應可只載入 alignment review queue 題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證 review_source 生效。
    """

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    prepared_rows = [
        {
            "item_id": "prepared-only",
            "file_name": "paper-1.md",
            "query_text": "Prepared question",
            "answer_text": "Prepared answer",
        }
    ]
    filtered_rows = [
        {
            "item_id": "filtered-only",
            "file_name": "paper-2.md",
            "query_text": "Filtered question",
            "answer_text": "Filtered answer",
        }
    ]
    review_queue_rows = [
        {
            "item_id": "review-only",
            "file_name": "paper-3.md",
            "query_text": "Review question",
            "answer_text": "Review answer",
        }
    ]
    for file_name, rows in (
        (PREPARED_ITEMS_FILE, prepared_rows),
        (FILTERED_ITEMS_FILE, filtered_rows),
        (ALIGNMENT_REVIEW_QUEUE_FILE, review_queue_rows),
    ):
        (workspace_dir / file_name).write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )

    review_rows = load_review_candidates(workspace_dir=workspace_dir, review_source="alignment_review_queue")

    assert len(review_rows) == 1
    assert review_rows[0]["item_id"] == "review-only"
