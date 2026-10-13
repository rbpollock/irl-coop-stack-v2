"""Worker indexing 並發 section synopsis 測試。"""

from __future__ import annotations

from threading import Lock
import time
from types import SimpleNamespace

from worker.core.settings import WorkerSettings
from worker.tasks import indexing


def _build_parent_chunk(*, heading_path: str, content: str) -> SimpleNamespace:
    """建立 indexing 測試使用的最小 parent chunk 替身。

    參數：
    - `heading_path`：section 階層路徑。
    - `content`：section 內容。

    回傳：
    - `SimpleNamespace`：具備 section synopsis helper 所需欄位的測試替身。
    """

    return SimpleNamespace(
        heading_path=heading_path,
        section_path_text=heading_path,
        content=content,
        structure_kind=SimpleNamespace(value="text"),
    )


def test_generate_section_synopsis_texts_uses_configured_parallelism(monkeypatch) -> None:
    """section synopsis 生成應遵守設定的並發上限並保留原始順序。"""

    active_calls = 0
    max_active_calls = 0
    call_lock = Lock()

    class FakeProvider:
        """模擬可觀測並發數的 synopsis provider。"""

        def generate_section_synopsis(
            self,
            *,
            file_name: str,
            heading_path: str | None,
            source_text: str,
            output_language: str,
            max_output_chars: int,
        ) -> str:
            """模擬單一 section synopsis 呼叫。

            參數：
            - `file_name`：目前文件檔名。
            - `heading_path`：目前 section 的階層路徑。
            - `source_text`：已做 path-aware 壓縮的輸入文字。
            - `output_language`：期望輸出語言。
            - `max_output_chars`：允許的 synopsis 最大字元數。

            回傳：
            - `str`：用於驗證順序的假 synopsis。
            """

            del file_name, source_text, output_language, max_output_chars

            nonlocal active_calls, max_active_calls
            with call_lock:
                active_calls += 1
                max_active_calls = max(max_active_calls, active_calls)
            time.sleep(0.03)
            with call_lock:
                active_calls -= 1
            return f"synopsis::{heading_path}"

    monkeypatch.setattr(indexing, "build_document_synopsis_provider", lambda settings: FakeProvider())

    settings = WorkerSettings(
        _env_file=None,
        DOCUMENT_SYNOPSIS_PROVIDER="deterministic",
        DOCUMENT_SYNOPSIS_PARALLELISM=3,
    )
    parent_chunks = [
        _build_parent_chunk(heading_path=f"Section {index}", content=f"Body {index}")
        for index in range(1, 7)
    ]

    synopsis_texts = indexing._generate_section_synopsis_texts(
        settings=settings,
        file_name="policy.md",
        parent_chunks=parent_chunks,
    )

    assert synopsis_texts == [f"synopsis::Section {index}" for index in range(1, 7)]
    assert 1 < max_active_calls <= 3
