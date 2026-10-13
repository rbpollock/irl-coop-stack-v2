"""Worker indexing 使用的 embedding 文字組裝 helper。"""

from __future__ import annotations


def build_embedding_input_text(*, heading: str | None, content: str) -> str:
    """建立送進 embedding provider 的自然語言文字。

    參數：
    - `heading`：chunk 標題；允許為空值。
    - `content`：chunk 正文內容。

    回傳：
    - `str`：優先保留主題語意的 embedding 文字。
    """

    normalized_heading = (heading or "").strip()
    normalized_content = content.strip()
    if normalized_heading and normalized_content:
        return f"{normalized_heading}\n\n{normalized_content}"
    return normalized_heading or normalized_content
