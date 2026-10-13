"""Retrieval evaluation metrics 計算工具。"""

from __future__ import annotations

import math


def discounted_cumulative_gain(relevances: list[int], *, k: int) -> float:
    """計算 DCG@k。

    參數：
    - `relevances`：依排名排序的 graded relevance 列表。
    - `k`：截斷排名。

    回傳：
    - `float`：DCG@k 分數。
    """

    score = 0.0
    for index, relevance in enumerate(relevances[:k], start=1):
        score += (2**relevance - 1) / math.log2(index + 1)
    return score


def normalized_discounted_cumulative_gain(relevances: list[int], *, k: int) -> float:
    """計算 nDCG@k。

    參數：
    - `relevances`：依排名排序的 graded relevance 列表。
    - `k`：截斷排名。

    回傳：
    - `float`：nDCG@k 分數。
    """

    actual = discounted_cumulative_gain(relevances, k=k)
    ideal = discounted_cumulative_gain(sorted(relevances, reverse=True), k=k)
    if ideal == 0:
        return 0.0
    return actual / ideal


def recall_at_k(relevances: list[int], *, k: int) -> float:
    """計算 Recall@k。

    參數：
    - `relevances`：依排名排序的 graded relevance 列表。
    - `k`：截斷排名。

    回傳：
    - `float`：Recall@k 分數。
    """

    positives = sum(1 for relevance in relevances if relevance > 0)
    if positives == 0:
        return 0.0
    hits = sum(1 for relevance in relevances[:k] if relevance > 0)
    return hits / positives


def mean_reciprocal_rank_at_k(relevances: list[int], *, k: int) -> float:
    """計算 MRR@k。

    參數：
    - `relevances`：依排名排序的 graded relevance 列表。
    - `k`：截斷排名。

    回傳：
    - `float`：MRR@k 分數。
    """

    for index, relevance in enumerate(relevances[:k], start=1):
        if relevance > 0:
            return 1.0 / index
    return 0.0


def precision_at_k(relevances: list[int], *, k: int) -> float:
    """計算 Precision@k。

    參數：
    - `relevances`：依排名排序的 graded relevance 列表。
    - `k`：截斷排名。

    回傳：
    - `float`：Precision@k 分數。
    """

    if k <= 0:
        return 0.0
    hits = sum(1 for relevance in relevances[:k] if relevance > 0)
    return hits / k


def document_coverage_at_k(document_ids: list[str], *, gold_document_ids: set[str], k: int) -> float:
    """計算 Document Coverage@k。

    參數：
    - `document_ids`：依排名排序的文件識別碼。
    - `gold_document_ids`：gold truth 相關文件集合。
    - `k`：截斷排名。

    回傳：
    - `float`：Document Coverage@k 分數。
    """

    normalized_gold_document_ids = {str(document_id) for document_id in gold_document_ids if document_id is not None}
    if not normalized_gold_document_ids:
        return 0.0
    normalized_document_ids = [str(document_id) for document_id in document_ids[:k]]
    covered = normalized_gold_document_ids.intersection(normalized_document_ids)
    return len(covered) / len(normalized_gold_document_ids)
