"""Retrieval query helper 測試。"""

from app.services.retrieval_query import detect_query_language, extract_query_tokens, normalize_query_text


def test_normalize_query_text_collapses_whitespace() -> None:
    """query 正規化應壓縮空白並移除前後空白。"""

    assert normalize_query_text(query="  alpha\n\nbeta\tgamma  ") == "alpha beta gamma"


def test_detect_query_language_distinguishes_cjk_latin_and_mixed() -> None:
    """語言偵測應區分繁中、英文與混合 query。"""

    assert detect_query_language(query="身分限制") == "zh-TW"
    assert detect_query_language(query="single domain") == "en"
    assert detect_query_language(query="身分 single-domain") == "mixed"


def test_extract_query_tokens_emits_cjk_bigrams_and_latin_tokens() -> None:
    """token helper 應保留 CJK 原片段、bigram 與英文 token。"""

    tokens = extract_query_tokens(query="身分限制 single-domain")

    assert "身分限制" in tokens
    assert "身分" in tokens
    assert "分限" in tokens
    assert "限制" in tokens
    assert "single-domain" in tokens
