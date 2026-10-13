"""Scope-aware diversified selection 測試。"""

from app.db.models import ChunkStructureKind
from app.services.retrieval_selection import apply_scope_aware_selection
from app.services.retrieval_types import RetrievalCandidate


def _candidate(
    *,
    document_id: str,
    chunk_id: str,
    parent_chunk_id: str,
    rerank_rank: int,
    heading: str,
) -> RetrievalCandidate:
    """建立 selection 測試用 retrieval candidate。

    參數：
    - `document_id`：文件識別碼。
    - `chunk_id`：chunk 識別碼。
    - `parent_chunk_id`：parent 識別碼。
    - `rerank_rank`：rerank 排名。
    - `heading`：標題文字。

    回傳：
    - `RetrievalCandidate`：最小可用測試候選。
    """

    return RetrievalCandidate(
        document_id=document_id,
        chunk_id=chunk_id,
        parent_chunk_id=parent_chunk_id,
        structure_kind=ChunkStructureKind.text,
        heading=heading,
        content=heading,
        start_offset=0,
        end_offset=len(heading),
        source="hybrid",
        vector_rank=rerank_rank,
        fts_rank=rerank_rank,
        rrf_rank=rerank_rank,
        rrf_score=1.0 / max(rerank_rank, 1),
        rerank_rank=rerank_rank,
        rerank_score=1.0 - (rerank_rank * 0.01),
        rerank_applied=True,
        rerank_fallback_reason=None,
    )


def test_single_document_selection_keeps_only_resolved_document() -> None:
    """single-document lane 不得混入其他文件。"""

    candidates = [
        _candidate(document_id="doc-1", chunk_id="c-1", parent_chunk_id="p-1", rerank_rank=1, heading="doc1-a"),
        _candidate(document_id="doc-2", chunk_id="c-2", parent_chunk_id="p-2", rerank_rank=2, heading="doc2-a"),
        _candidate(document_id="doc-1", chunk_id="c-3", parent_chunk_id="p-3", rerank_rank=3, heading="doc1-b"),
    ]

    result = apply_scope_aware_selection(
        candidates=candidates,
        selected_profile="document_summary_single_document_diversified_v1",
        resolved_document_ids=("doc-1",),
        max_contexts=6,
    )

    assert result.applied is True
    assert result.strategy == "single_document_parent_diversity_v1"
    assert result.selected_document_ids == ("doc-1",)
    assert all(candidate.document_id == "doc-1" for candidate in result.candidates)


def test_multi_document_summary_selection_keeps_multiple_documents_before_third_parent() -> None:
    """multi-document summary 在其他文件未拿到第二個 parent 前，不得先讓單一文件拿第三個。"""

    candidates = [
        _candidate(document_id="doc-1", chunk_id="c-1", parent_chunk_id="p-1", rerank_rank=1, heading="doc1-a"),
        _candidate(document_id="doc-1", chunk_id="c-2", parent_chunk_id="p-2", rerank_rank=2, heading="doc1-b"),
        _candidate(document_id="doc-1", chunk_id="c-3", parent_chunk_id="p-3", rerank_rank=3, heading="doc1-c"),
        _candidate(document_id="doc-2", chunk_id="c-4", parent_chunk_id="p-4", rerank_rank=4, heading="doc2-a"),
        _candidate(document_id="doc-2", chunk_id="c-5", parent_chunk_id="p-5", rerank_rank=5, heading="doc2-b"),
    ]

    result = apply_scope_aware_selection(
        candidates=candidates,
        selected_profile="document_summary_multi_document_diversified_v1",
        resolved_document_ids=(),
        max_contexts=5,
    )

    selected_parents_by_document: dict[str, list[str]] = {}
    for candidate in result.candidates:
        selected_parents_by_document.setdefault(candidate.document_id, []).append(candidate.parent_chunk_id or candidate.chunk_id)

    assert result.selected_document_ids == ("doc-1", "doc-2")
    assert len(selected_parents_by_document["doc-2"]) >= 2
    assert selected_parents_by_document["doc-1"][:2] == ["p-1", "p-2"]


def test_cross_document_compare_selection_fills_beyond_four_parents_when_budget_allows() -> None:
    """compare lane 在 budget 足夠時可超過四個 selected parents。"""

    candidates = [
        _candidate(document_id="doc-1", chunk_id="c-1", parent_chunk_id="p-1", rerank_rank=1, heading="doc1-a"),
        _candidate(document_id="doc-2", chunk_id="c-2", parent_chunk_id="p-2", rerank_rank=2, heading="doc2-a"),
        _candidate(document_id="doc-1", chunk_id="c-3", parent_chunk_id="p-3", rerank_rank=3, heading="doc1-b"),
        _candidate(document_id="doc-2", chunk_id="c-4", parent_chunk_id="p-4", rerank_rank=4, heading="doc2-b"),
        _candidate(document_id="doc-1", chunk_id="c-5", parent_chunk_id="p-5", rerank_rank=5, heading="doc1-c"),
        _candidate(document_id="doc-2", chunk_id="c-6", parent_chunk_id="p-6", rerank_rank=6, heading="doc2-c"),
    ]

    result = apply_scope_aware_selection(
        candidates=candidates,
        selected_profile="cross_document_compare_diversified_v1",
        resolved_document_ids=("doc-1", "doc-2"),
        max_contexts=6,
    )

    assert result.applied is True
    assert result.strategy == "compare_coverage_then_fill_v1"
    assert len(result.selected_parent_ids) == 6
    assert result.selected_parent_ids[:4] == ("p-1", "p-2", "p-3", "p-4")


def test_fact_lookup_selection_bypasses_diversity() -> None:
    """fact_lookup lane 應完全略過 diversified selection。"""

    candidates = [
        _candidate(document_id="doc-1", chunk_id="c-1", parent_chunk_id="p-1", rerank_rank=1, heading="doc1-a"),
        _candidate(document_id="doc-1", chunk_id="c-2", parent_chunk_id="p-2", rerank_rank=2, heading="doc1-b"),
    ]

    result = apply_scope_aware_selection(
        candidates=candidates,
        selected_profile="fact_lookup_precision_v1",
        resolved_document_ids=(),
        max_contexts=1,
    )

    assert result.applied is False
    assert result.strategy == "disabled"
    assert [candidate.chunk_id for candidate in result.candidates] == ["c-1", "c-2"]
