"""retrieval 與 assembler 共用的文字組裝 helper。"""

from __future__ import annotations

import re

from app.db.models import ChunkStructureKind


# 兩個命中 child 時，rerank 文字可放寬到基礎 budget 的 2 倍。
MULTI_HIT_RERANK_BUDGET_MULTIPLIER_DOUBLE = 2.0
# 三個以上命中 child 時，rerank 文字可放寬到基礎 budget 的 2.5 倍。
MULTI_HIT_RERANK_BUDGET_MULTIPLIER_TRIPLE_OR_MORE = 2.5
# 多 hit child rerank 的硬上限，避免 provider latency / cost 無上限膨脹。
MULTI_HIT_RERANK_BUDGET_HARD_CAP = 5000


def merge_chunk_contents(*, structure_kind: ChunkStructureKind, contents: list[str]) -> str:
    """依 chunk 結構型別合併多筆 child content。

    參數：
    - `structure_kind`：chunk 內容結構型別。
    - `contents`：同一 parent 下、已依既定順序排列的 child content。

    回傳：
    - `str`：合併後的文字；table 只保留一次表頭。
    """

    normalized_contents = [content.strip() for content in contents if content and content.strip()]
    if not normalized_contents:
        return ""
    if structure_kind == ChunkStructureKind.table:
        return _merge_table_contents(contents=normalized_contents)
    return "\n\n".join(normalized_contents).strip()


def build_rerank_document_text(
    *,
    heading: str | None,
    content: str,
    max_chars: int,
    matched_child_contents: list[str] | None = None,
) -> str:
    """建立送進 rerank provider 的文件文字。

    參數：
    - `heading`：此文件片段的標題；允許為空值。
    - `content`：已組裝完成的正文內容。
    - `max_chars`：允許送入 rerank 的最大字元數。
    - `matched_child_contents`：同一 parent 內實際命中的 child 內容；允許為空值。

    回傳：
    - `str`：帶有 `Header:` / `Content:` 前綴且受成本 guardrail 限制的文字。
    """

    normalized_heading = (heading or "").strip()
    normalized_content = content.strip()
    normalized_children = [item.strip() for item in (matched_child_contents or []) if item and item.strip()]
    effective_max_chars = _resolve_rerank_effective_max_chars(
        base_max_chars=max_chars,
        matched_child_count=len(normalized_children),
    )
    sections = [f"Header: {normalized_heading}".strip()]
    prefix = "\n".join(section for section in sections if section).strip()
    content_body = _build_rerank_content_body(
        content=normalized_content,
        matched_child_contents=normalized_children,
        max_chars=(
            effective_max_chars - len(prefix) - len("\nContent:\n")
            if prefix
            else effective_max_chars - len("Content:\n")
        ),
    )
    structured_sections = [prefix] if prefix else []
    structured_sections.append(f"Content:\n{content_body}")
    structured_text = "\n".join(section for section in structured_sections if section).strip()
    if len(structured_text) <= effective_max_chars:
        return structured_text
    return structured_text[:effective_max_chars]


def _resolve_rerank_effective_max_chars(*, base_max_chars: int, matched_child_count: int) -> int:
    """依命中 child 數量決定 rerank soft budget。

    參數：
    - `base_max_chars`：原始 rerank budget。
    - `matched_child_count`：同一 parent 內命中的 child 數量。

    回傳：
    - `int`：實際可使用的 rerank budget。
    """

    if matched_child_count <= 1:
        return base_max_chars

    multiplier = (
        MULTI_HIT_RERANK_BUDGET_MULTIPLIER_TRIPLE_OR_MORE
        if matched_child_count >= 3
        else MULTI_HIT_RERANK_BUDGET_MULTIPLIER_DOUBLE
    )
    expanded_budget = int(base_max_chars * multiplier)
    return min(MULTI_HIT_RERANK_BUDGET_HARD_CAP, max(base_max_chars, expanded_budget))


def _build_rerank_content_body(*, content: str, matched_child_contents: list[str], max_chars: int) -> str:
    """依 rerank 預算建立正文區塊。

    參數：
    - `content`：原本供 rerank 使用的正文內容。
    - `matched_child_contents`：同一 parent 內命中的 child 內容。
    - `max_chars`：正文區塊可用的最大字元數。

    回傳：
    - `str`：符合預算的 rerank 正文內容。
    """

    if max_chars <= 0:
        return ""
    if len(content) <= max_chars:
        return content

    if len(matched_child_contents) <= 1:
        return content[:max_chars]

    full_bundle = _format_matched_child_bundle(contents=matched_child_contents)
    if len(full_bundle) <= max_chars:
        return full_bundle

    return _build_truncated_matched_child_bundle(contents=matched_child_contents, max_chars=max_chars)


def _format_matched_child_bundle(*, contents: list[str]) -> str:
    """將多個命中 child 組成可讀的 rerank evidence bundle。

    參數：
    - `contents`：依 child 順序排列的命中內容。

    回傳：
    - `str`：標記每個 hit child 的組裝文字。
    """

    return "\n\n".join(f"[Hit child {index}]\n{content}" for index, content in enumerate(contents, start=1)).strip()


def _build_truncated_matched_child_bundle(*, contents: list[str], max_chars: int) -> str:
    """在超出 budget 時仍強制保留所有 hit child 的最小片段。

    參數：
    - `contents`：依 child 順序排列的命中內容。
    - `max_chars`：bundle 可用的最大字元數。

    回傳：
    - `str`：每個 hit child 至少保留部分文字的壓縮 bundle。
    """

    if max_chars <= 0:
        return ""

    labels = [f"[Hit child {index}]\n" for index in range(1, len(contents) + 1)]
    separator_overhead = max(0, len(contents) - 1) * len("\n\n")
    label_overhead = sum(len(label) for label in labels)
    available_excerpt_chars = max(0, max_chars - label_overhead - separator_overhead)
    if available_excerpt_chars <= 0:
        return _truncate_with_suffix(value=_format_matched_child_bundle(contents=contents), max_chars=max_chars)

    sections: list[str] = []
    remaining_excerpt_chars = available_excerpt_chars
    remaining_count = len(contents)
    for label, content in zip(labels, contents, strict=False):
        excerpt_budget = max(1, remaining_excerpt_chars // remaining_count)
        excerpt = _truncate_with_suffix(value=content, max_chars=excerpt_budget)
        sections.append(f"{label}{excerpt}")
        remaining_excerpt_chars -= len(excerpt)
        remaining_count -= 1

    bundle = "\n\n".join(sections).strip()
    if len(bundle) <= max_chars:
        return bundle
    return _truncate_with_suffix(value=bundle, max_chars=max_chars)


def _truncate_with_suffix(*, value: str, max_chars: int) -> str:
    """以 ASCII 省略標記裁切文字。

    參數：
    - `value`：待裁切文字。
    - `max_chars`：最大字元數。

    回傳：
    - `str`：若超出長度則以 `...` 結尾的文字。
    """

    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return f"{value[: max_chars - 3]}..."

def _merge_table_contents(*, contents: list[str]) -> str:
    """將多個 table row-group child 合併為單一 table 文字。

    參數：
    - `contents`：同一 parent 下、已依 child 順序排列的 table child content。

    回傳：
    - `str`：只保留一次表頭的 Markdown table。
    """

    merged_lines: list[str] = []
    for index, content in enumerate(contents):
        lines = [line.rstrip() for line in content.splitlines() if line.strip()]
        if not lines:
            continue
        if index == 0 or len(lines) < 3:
            merged_lines.extend(lines)
            continue
        merged_lines.extend(lines[2:])
    return "\n".join(merged_lines).strip()
