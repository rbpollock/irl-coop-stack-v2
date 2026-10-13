"""Retrieval evaluation metrics 與 mapping 純函式測試。"""

from uuid import uuid4

from app.evaluation.retrieval.metrics import (
    document_coverage_at_k,
    mean_reciprocal_rank_at_k,
    normalized_discounted_cumulative_gain,
    precision_at_k,
    recall_at_k,
)
from app.evaluation.retrieval.mapping import CandidateWindow, GoldSpan, match_gold_relevance


def test_normalized_discounted_cumulative_gain_returns_one_for_ideal_ranking() -> None:
    """理想排序時 nDCG@k 應為 1。"""

    assert normalized_discounted_cumulative_gain([3, 2, 0], k=3) == 1.0


def test_recall_precision_and_mrr_at_k_follow_expected_values() -> None:
    """Recall@k、Precision@k 與 MRR@k 應符合基本定義。"""

    relevances = [0, 3, 2, 0]

    assert recall_at_k(relevances, k=3) == 1.0
    assert precision_at_k(relevances, k=2) == 0.5
    assert mean_reciprocal_rank_at_k(relevances, k=4) == 0.5


def test_document_coverage_at_k_counts_distinct_gold_documents() -> None:
    """Document Coverage@k 應以 distinct gold 文件覆蓋率計算。"""

    assert document_coverage_at_k(
        ["doc-a", "doc-a", "doc-b"],
        gold_document_ids={"doc-a", "doc-b", "doc-c"},
        k=3,
    ) == 2 / 3


def test_document_coverage_at_k_accepts_uuid_and_string_document_ids() -> None:
    """Document Coverage@k 應接受 UUID 與字串混用的文件識別碼。"""

    document_id = uuid4()

    assert document_coverage_at_k(
        [str(document_id), "doc-b"],
        gold_document_ids={document_id},
        k=2,
    ) == 1.0


def test_match_gold_relevance_accepts_uuid_and_string_document_ids() -> None:
    """gold span 與 candidate 的 document_id 型別不同時仍應正確命中。"""

    document_id = uuid4()

    assert match_gold_relevance(
        [
            GoldSpan(
                document_id=document_id,
                start_offset=5027,
                end_offset=6545,
                relevance_grade=3,
                is_retrieval_miss=False,
            )
        ],
        CandidateWindow(
            document_id=str(document_id),
            start_offset=5027,
            end_offset=9730,
        ),
    ) == 3
