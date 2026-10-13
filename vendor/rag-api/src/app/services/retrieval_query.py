"""retrieval query 正規化與 token helper。"""

from __future__ import annotations

import re


# `zh-TW` 表示繁體中文 query language。
QUERY_LANGUAGE_ZH_TW = "zh-TW"
# `en` 表示英文 query language。
QUERY_LANGUAGE_EN = "en"
# `mixed` 表示中英混合 query language。
QUERY_LANGUAGE_MIXED = "mixed"

# CJK script 偵測 pattern。
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# Latin script 偵測 pattern。
_LATIN_PATTERN = re.compile(r"[A-Za-z]")
# 空白正規化 pattern。
_WHITESPACE_PATTERN = re.compile(r"\s+")
# query token 抽取 pattern；會同時保留英文詞與 CJK 片段。
_QUERY_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*|[\u3400-\u4dbf\u4e00-\u9fff]+")


def normalize_query_text(*, query: str) -> str:
    """正規化 query 的空白與前後空白。

    參數：
    - `query`：原始 query。

    回傳：
    - `str`：正規化後的 query。
    """

    return _WHITESPACE_PATTERN.sub(" ", query).strip()


def detect_query_language(*, query: str) -> str:
    """判斷 query 的主要語言類型。

    參數：
    - `query`：待判斷的 query。

    回傳：
    - `str`：`zh-TW`、`en` 或 `mixed`。
    """

    has_cjk = bool(_CJK_PATTERN.search(query))
    has_latin = bool(_LATIN_PATTERN.search(query))
    if has_cjk and has_latin:
        return QUERY_LANGUAGE_MIXED
    if has_cjk:
        return QUERY_LANGUAGE_ZH_TW
    return QUERY_LANGUAGE_EN


def extract_query_tokens(*, query: str) -> list[str]:
    """抽出 ranking 與文件 mention resolution 共用的 query tokens。

    參數：
    - `query`：原始 query。

    回傳：
    - `list[str]`：去重後的 query tokens。
    """

    normalized_query = normalize_query_text(query=query)
    if not normalized_query:
        return []

    tokens: list[str] = []
    seen: set[str] = set()
    for raw_token in _QUERY_TOKEN_PATTERN.findall(normalized_query.casefold()):
        if _CJK_PATTERN.search(raw_token):
            cjk_tokens = [raw_token]
            if len(raw_token) >= 2:
                cjk_tokens.extend(raw_token[index : index + 2] for index in range(len(raw_token) - 1))
            for token in cjk_tokens:
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
            continue
        if raw_token not in seen:
            seen.add(raw_token)
            tokens.append(raw_token)
    return tokens
