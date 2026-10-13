"""Gold source span 與 retrieval 候選的映射工具。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GoldSpan:
    """單一 gold source span。"""

    document_id: str | None
    start_offset: int
    end_offset: int
    relevance_grade: int | None
    is_retrieval_miss: bool


@dataclass(slots=True)
class CandidateWindow:
    """可與 gold span 比對的候選視窗。"""

    document_id: str
    start_offset: int
    end_offset: int


def spans_overlap(*, left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    """判斷兩個 offset 區間是否重疊。

    參數：
    - `left_start`：左側區間起點。
    - `left_end`：左側區間終點。
    - `right_start`：右側區間起點。
    - `right_end`：右側區間終點。

    回傳：
    - `bool`：若兩區間有重疊則回傳真。
    """

    return left_start < right_end and right_start < left_end


def match_gold_relevance(spans: list[GoldSpan], candidate: CandidateWindow) -> int | None:
    """找出候選命中的最高 gold relevance。

    參數：
    - `spans`：目前題目的 gold spans。
    - `candidate`：待比對的候選範圍。

    回傳：
    - `int | None`：命中的最高 relevance；未命中則回傳 `None`。
    """

    matched_relevance: int | None = None
    for span in spans:
        span_document_id = str(span.document_id) if span.document_id is not None else None
        candidate_document_id = str(candidate.document_id)
        if span.is_retrieval_miss or span_document_id != candidate_document_id:
            continue
        if not spans_overlap(
            left_start=span.start_offset,
            left_end=span.end_offset,
            right_start=candidate.start_offset,
            right_end=candidate.end_offset,
        ):
            continue
        if span.relevance_grade is None:
            continue
        matched_relevance = max(matched_relevance or 0, span.relevance_grade)
    return matched_relevance


def match_gold_relevance_for_windows(spans: list[GoldSpan], candidates: list[CandidateWindow]) -> int | None:
    """找出多個候選視窗對 gold spans 的最高命中 relevance。

    參數：
    - `spans`：目前題目的 gold spans。
    - `candidates`：同一 stage item 代表的多個候選視窗。

    回傳：
    - `int | None`：任一視窗命中的最高 relevance；未命中則回傳 `None`。
    """

    matched_relevance: int | None = None
    for candidate in candidates:
        candidate_relevance = match_gold_relevance(spans, candidate)
        if candidate_relevance is None:
            continue
        matched_relevance = max(matched_relevance or 0, candidate_relevance)
    return matched_relevance


def first_hit_rank(relevances: list[int | None]) -> int | None:
    """找出第一個命中的排名。

    參數：
    - `relevances`：依排名排序的命中 relevance。

    回傳：
    - `int | None`：第一個命中的 1-based 排名；若未命中則回傳 `None`。
    """

    for index, relevance in enumerate(relevances, start=1):
        if relevance and relevance > 0:
            return index
    return None
