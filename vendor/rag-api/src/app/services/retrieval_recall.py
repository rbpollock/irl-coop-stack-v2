"""Retrieval recall、RRF fusion 與資料庫 fallback 查詢。"""

from __future__ import annotations

import math

from sqlalchemy import Integer, String, bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.db.models import ChunkType, Document, DocumentChunk, DocumentStatus, EvaluationQueryType
from app.db.sql_types import DEFAULT_EMBEDDING_DIMENSIONS, Vector
from app.services.embeddings import build_embedding_provider
from app.services.retrieval_types import (
    DocumentRecallMatch,
    DocumentRecallResult,
    DocumentRecallTrace,
    DocumentRecallTraceEntry,
    RankedChunkMatch,
    SectionRecallMatch,
    SectionRecallResult,
    SectionRecallTrace,
    SectionRecallTraceEntry,
)


def build_match_chunks_rpc_statement():
    """建立具備 PostgreSQL 明確 bind type 的 `match_chunks` RPC statement。

    參數：
    - 無

    回傳：
    - `TextClause`：已綁定 vector/text/varchar/int 型別的 SQL statement。
    """

    if Vector is None:  # pragma: no cover - PostgreSQL 正式路徑應固定安裝 pgvector。
        raise RuntimeError("PostgreSQL retrieval 路徑需要 `pgvector` SQLAlchemy 型別支援。")

    return text(
        "SELECT * FROM match_chunks(:query_embedding, :query_text, :area_id, :vector_top_k, :fts_top_k, :allowed_document_ids, :allowed_parent_chunk_ids)"
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
        bindparam("allowed_document_ids", type_=PG_ARRAY(String(36))),
        bindparam("allowed_parent_chunk_ids", type_=PG_ARRAY(String(36))),
    )


def build_document_recall_statement():
    """建立 PostgreSQL document synopsis recall 的 SQL statement。

    參數：
    - 無

    回傳：
    - `TextClause`：已綁定 vector/text/varchar/int 型別的 SQL statement。
    """

    if Vector is None:  # pragma: no cover - PostgreSQL 正式路徑應固定安裝 pgvector。
        raise RuntimeError("PostgreSQL document recall 路徑需要 `pgvector` SQLAlchemy 型別支援。")

    return text(
        """
        WITH vector_matches AS (
            SELECT
                d.id,
                ROW_NUMBER() OVER (ORDER BY d.synopsis_embedding <=> :query_embedding, d.id) :: INT AS rank
            FROM documents d
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND d.synopsis_embedding IS NOT NULL
            ORDER BY d.synopsis_embedding <=> :query_embedding, d.id
            LIMIT :vector_top_k
        ),
        fts_matches AS (
            SELECT
                d.id,
                ROW_NUMBER() OVER (
                    ORDER BY pgroonga_score(d.tableoid, d.ctid) DESC, d.id
                ) :: INT AS rank,
                pgroonga_score(d.tableoid, d.ctid) :: FLOAT AS score
            FROM documents d
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND d.synopsis_text IS NOT NULL
              AND d.synopsis_text &@~ :query_text
            ORDER BY pgroonga_score(d.tableoid, d.ctid) DESC, d.id
            LIMIT :fts_top_k
        ),
        candidate_ids AS (
            SELECT id FROM vector_matches
            UNION
            SELECT id FROM fts_matches
        )
        SELECT
            d.id,
            d.file_name,
            vm.rank AS vector_rank,
            fm.rank AS fts_rank,
            fm.score AS fts_score
        FROM candidate_ids c
        JOIN documents d ON d.id = c.id
        LEFT JOIN vector_matches vm ON vm.id = d.id
        LEFT JOIN fts_matches fm ON fm.id = d.id
        ORDER BY
            COALESCE(vm.rank, 2147483647),
            COALESCE(fm.rank, 2147483647),
            d.id
        """
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
    )


def build_section_recall_statement():
    """建立 PostgreSQL section synopsis recall 的 SQL statement。

    參數：
    - 無

    回傳：
    - `TextClause`：已綁定 vector/text/varchar/int 型別的 SQL statement。
    """

    if Vector is None:  # pragma: no cover - PostgreSQL 正式路徑應固定安裝 pgvector。
        raise RuntimeError("PostgreSQL section recall 路徑需要 `pgvector` SQLAlchemy 型別支援。")

    return text(
        """
        WITH vector_matches AS (
            SELECT
                dc.id,
                ROW_NUMBER() OVER (ORDER BY dc.section_synopsis_embedding <=> :query_embedding, dc.id) :: INT AS rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND dc.chunk_type = 'parent'
              AND dc.section_synopsis_embedding IS NOT NULL
              AND (
                :allowed_document_ids IS NULL
                OR d.id = ANY(:allowed_document_ids)
              )
            ORDER BY dc.section_synopsis_embedding <=> :query_embedding, dc.id
            LIMIT :vector_top_k
        ),
        fts_matches AS (
            SELECT
                dc.id,
                ROW_NUMBER() OVER (
                    ORDER BY pgroonga_score(dc.tableoid, dc.ctid) DESC, dc.id
                ) :: INT AS rank,
                pgroonga_score(dc.tableoid, dc.ctid) :: FLOAT AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND dc.chunk_type = 'parent'
              AND dc.section_synopsis_text IS NOT NULL
              AND dc.section_synopsis_text &@~ :query_text
              AND (
                :allowed_document_ids IS NULL
                OR d.id = ANY(:allowed_document_ids)
              )
            ORDER BY pgroonga_score(dc.tableoid, dc.ctid) DESC, dc.id
            LIMIT :fts_top_k
        ),
        candidate_ids AS (
            SELECT id FROM vector_matches
            UNION
            SELECT id FROM fts_matches
        )
        SELECT
            dc.id,
            dc.document_id,
            dc.heading,
            dc.heading_path,
            dc.section_path_text,
            vm.rank AS vector_rank,
            fm.rank AS fts_rank,
            fm.score AS fts_score
        FROM candidate_ids c
        JOIN document_chunks dc ON dc.id = c.id
        LEFT JOIN vector_matches vm ON vm.id = dc.id
        LEFT JOIN fts_matches fm ON fm.id = dc.id
        ORDER BY
            COALESCE(vm.rank, 2147483647),
            COALESCE(fm.rank, 2147483647),
            dc.id
        """
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
        bindparam("allowed_document_ids", type_=PG_ARRAY(String(36))),
    )


def recall_ranked_candidates(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None = None,
    allowed_parent_ids: tuple[str, ...] | None = None,
) -> list[RankedChunkMatch]:
    """依資料庫方言取得已套用 area/ready 邊界的 ranked candidates。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `area_id`：已通過 access gate 的 area。
    - `query`：使用者查詢。
    - `allowed_document_ids`：可選文件白名單。
    - `allowed_parent_ids`：可選 parent chunk 白名單。

    回傳：
    - `list[RankedChunkMatch]`：已帶回 recall rank 的候選。
    """

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        return _run_postgres_candidate_generation(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
            allowed_parent_ids=allowed_parent_ids,
        )
    return _run_sqlite_candidate_generation(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query,
        allowed_document_ids=allowed_document_ids,
        allowed_parent_ids=allowed_parent_ids,
    )


def apply_python_rrf(*, matches: list[RankedChunkMatch], settings: AppSettings) -> list[RankedChunkMatch]:
    """在 Python 層對 recall 候選套用 RRF。

    參數：
    - `matches`：已完成 recall 的候選。
    - `settings`：API 執行期設定。

    回傳：
    - `list[RankedChunkMatch]`：已套用 RRF 並裁切候選數的結果。
    """

    for match in matches:
        match.rrf_score = compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)

    merged_matches = sorted(
        matches,
        key=lambda item: (
            -item.rrf_score,
            best_rank(item),
            item.chunk.position,
            item.chunk.id,
        ),
    )[: settings.retrieval_max_candidates]

    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return merged_matches


def resolve_document_recall_result(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    query_type: EvaluationQueryType,
    summary_scope: str | None,
    resolved_document_ids: tuple[str, ...],
) -> DocumentRecallResult:
    """依 query type 與 synopsis recall 決定第二階段允許的文件集合。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：routing 後的有效設定。
    - `area_id`：目標 area。
    - `query`：使用者原始查詢。
    - `query_type`：本次 query type。
    - `summary_scope`：若為摘要問題，表示 single/multi document scope。
    - `resolved_document_ids`：document mention resolver 高信心命中的文件集合。

    回傳：
    - `DocumentRecallResult`：第一階段選文件結果與 trace。
    """

    if query_type == EvaluationQueryType.fact_lookup or not settings.retrieval_document_recall_enabled:
        return DocumentRecallResult(
            selected_document_ids=(),
            trace=DocumentRecallTrace(
                applied=False,
                strategy="disabled",
                top_k=settings.retrieval_document_recall_top_k,
                selected_document_ids=[],
                dropped_document_ids=[],
                candidates=[],
            ),
        )

    if summary_scope == "single_document" and len(resolved_document_ids) == 1:
        return DocumentRecallResult(
            selected_document_ids=resolved_document_ids,
            trace=DocumentRecallTrace(
                applied=True,
                strategy="mention_resolved_single_document_v1",
                top_k=1,
                selected_document_ids=list(resolved_document_ids),
                dropped_document_ids=[],
                candidates=[],
            ),
        )

    recall_matches = recall_documents_by_synopsis(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query,
    )
    selected_document_ids: list[str] = []
    for document_id in resolved_document_ids:
        if document_id not in selected_document_ids:
            selected_document_ids.append(document_id)
    for match in recall_matches:
        if match.document.id in selected_document_ids:
            continue
        selected_document_ids.append(match.document.id)
        if len(selected_document_ids) >= settings.retrieval_document_recall_top_k:
            break

    selected_document_set = set(selected_document_ids)
    return DocumentRecallResult(
        selected_document_ids=tuple(selected_document_ids),
        trace=DocumentRecallTrace(
            applied=True,
            strategy="synopsis_rrf_v1",
            top_k=settings.retrieval_document_recall_top_k,
            selected_document_ids=selected_document_ids,
            dropped_document_ids=[match.document.id for match in recall_matches if match.document.id not in selected_document_set],
            candidates=[
                DocumentRecallTraceEntry(
                    document_id=match.document.id,
                    file_name=match.document.file_name,
                    vector_rank=match.vector_rank,
                    fts_rank=match.fts_rank,
                    rrf_rank=match.rrf_rank or 0,
                    rrf_score=match.rrf_score,
                )
                for match in recall_matches
            ],
        ),
    )


def recall_documents_by_synopsis(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[DocumentRecallMatch]:
    """以 document synopsis 執行第一階段 document-level recall。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：routing 後的有效設定。
    - `area_id`：目標 area。
    - `query`：使用者原始查詢。

    回傳：
    - `list[DocumentRecallMatch]`：依 RRF 排序後的文件候選。
    """

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        matches = _run_postgres_document_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
        )
    else:
        matches = _run_sqlite_document_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
        )

    for match in matches:
        match.rrf_score = compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)

    merged_matches = sorted(
        matches,
        key=lambda item: (
            -item.rrf_score,
            best_rank(item),
            item.document.file_name.casefold(),
            item.document.id,
        ),
    )[: settings.retrieval_document_recall_top_k]
    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return merged_matches


def resolve_section_recall_result(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    query_type: EvaluationQueryType,
    summary_strategy: str | None,
    allowed_document_ids: tuple[str, ...] | None,
) -> SectionRecallResult:
    """依 query type 與 summary strategy 決定第二階段 section 集合。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：routing 後的有效設定。
    - `area_id`：目標 area。
    - `query`：使用者原始查詢。
    - `query_type`：本次 query type。
    - `summary_strategy`：本次 summary strategy。
    - `allowed_document_ids`：可選文件白名單。

    回傳：
    - `SectionRecallResult`：section recall 結果。
    """

    if query_type == EvaluationQueryType.fact_lookup:
        return SectionRecallResult(
            selected_parent_ids=(),
            trace=SectionRecallTrace(
                applied=False,
                strategy="disabled",
                top_k=0,
                selected_parent_ids=[],
                dropped_parent_ids=[],
                candidates=[],
            ),
        )

    section_top_k = resolve_section_recall_top_k(
        settings=settings,
        query_type=query_type,
        summary_strategy=summary_strategy,
    )
    recall_matches = recall_sections_by_synopsis(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query,
        allowed_document_ids=allowed_document_ids,
        top_k=section_top_k,
    )
    selected_parent_ids = [match.parent_chunk.id for match in recall_matches[:section_top_k]]
    selected_parent_set = set(selected_parent_ids)
    return SectionRecallResult(
        selected_parent_ids=tuple(selected_parent_ids),
        trace=SectionRecallTrace(
            applied=bool(selected_parent_ids),
            strategy="section_synopsis_rrf_v1",
            top_k=section_top_k,
            selected_parent_ids=selected_parent_ids,
            dropped_parent_ids=[match.parent_chunk.id for match in recall_matches if match.parent_chunk.id not in selected_parent_set],
            candidates=[
                SectionRecallTraceEntry(
                    parent_chunk_id=match.parent_chunk.id,
                    document_id=match.parent_chunk.document_id,
                    heading=match.parent_chunk.heading,
                    heading_path=match.parent_chunk.heading_path,
                    section_path_text=match.parent_chunk.section_path_text,
                    vector_rank=match.vector_rank,
                    fts_rank=match.fts_rank,
                    rrf_rank=match.rrf_rank or 0,
                    rrf_score=match.rrf_score,
                )
                for match in recall_matches
            ],
        ),
    )


def resolve_section_recall_top_k(
    *,
    settings: AppSettings,
    query_type: EvaluationQueryType,
    summary_strategy: str | None,
) -> int:
    """依題型與策略決定 section recall top-k。

    參數：
    - `settings`：routing 後的有效設定。
    - `query_type`：本次 query type。
    - `summary_strategy`：本次 summary strategy。

    回傳：
    - `int`：section recall top-k。
    """

    if query_type == EvaluationQueryType.cross_document_compare:
        return max(settings.assembler_max_contexts * 2, 10)
    if summary_strategy == "section_focused":
        return max(settings.assembler_max_contexts, 6)
    return max(settings.assembler_max_contexts * 2, 8)


def recall_sections_by_synopsis(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    top_k: int,
) -> list[SectionRecallMatch]:
    """以 section synopsis 執行 parent-level recall。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：routing 後的有效設定。
    - `area_id`：目標 area。
    - `query`：使用者原始查詢。
    - `allowed_document_ids`：可選文件白名單。
    - `top_k`：section recall top-k。

    回傳：
    - `list[SectionRecallMatch]`：依 RRF 排序後的 parent 候選。
    """

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        matches = _run_postgres_section_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
        )
    else:
        matches = _run_sqlite_section_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
        )

    for match in matches:
        match.rrf_score = compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)

    merged_matches = sorted(
        matches,
        key=lambda item: (
            -item.rrf_score,
            best_rank(item),
            item.parent_chunk.position,
            item.parent_chunk.id,
        ),
    )[:top_k]
    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return merged_matches


def resolve_retrieval_fallback_reason(
    *,
    document_recall_result: DocumentRecallResult,
    section_recall_result: SectionRecallResult,
) -> str | None:
    """依 document/section recall 結果決定是否有摘要層級 fallback。

    參數：
    - `document_recall_result`：document recall 結果。
    - `section_recall_result`：section recall 結果。

    回傳：
    - `str | None`：fallback reason；若無 fallback 則回傳空值。
    """

    if document_recall_result.trace.strategy != "disabled" and not document_recall_result.selected_document_ids:
        return "document_recall_empty_fallback_to_child"
    if section_recall_result.trace.strategy != "disabled" and not section_recall_result.selected_parent_ids:
        return "section_recall_empty_fallback_to_document_scope"
    return None


def compute_rrf_score(*, match, rrf_k: int) -> float:  # noqa: ANN001
    """依 vector/FTS rank 計算單一候選的 RRF 分數。

    參數：
    - `match`：具有 `vector_rank` 與 `fts_rank` 欄位的候選。
    - `rrf_k`：RRF K 值。

    回傳：
    - `float`：RRF 分數。
    """

    score = 0.0
    if match.vector_rank is not None:
        score += 1.0 / (rrf_k + match.vector_rank)
    if match.fts_rank is not None:
        score += 1.0 / (rrf_k + match.fts_rank)
    return score


def best_rank(match) -> int:  # noqa: ANN001
    """回傳候選可用 rank 中最好的那個，用於 tie-break。

    參數：
    - `match`：具有 rank 欄位的候選。

    回傳：
    - `int`：最小 rank；沒有 rank 時回傳大數。
    """

    available_ranks = [
        rank
        for rank in (
            getattr(match, "vector_rank", None),
            getattr(match, "fts_rank", None),
            getattr(match, "rrf_rank", None),
        )
        if rank is not None
    ]
    return min(available_ranks) if available_ranks else 1_000_000


def cosine_distance(left: list[float], right: list[float] | None) -> float:
    """計算兩個向量的 cosine distance。

    參數：
    - `left`：左側向量。
    - `right`：右側向量；若為空值視為最大距離。

    回傳：
    - `float`：cosine distance。
    """

    if right is None:
        return 1.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    cosine_similarity = dot_product / (left_norm * right_norm)
    return 1.0 - cosine_similarity


def sqlite_fts_score(*, query: str, content: str) -> int:
    """SQLite 測試 fallback 的簡化 FTS 分數。

    參數：
    - `query`：使用者查詢。
    - `content`：候選內容。

    回傳：
    - `int`：簡化後的詞頻分數。
    """

    tokens = [token.strip().lower() for token in query.split() if token.strip()]
    if not tokens:
        tokens = [query.strip().lower()]
    lowered_content = content.lower()
    return sum(lowered_content.count(token) for token in tokens if token)


def _run_postgres_candidate_generation(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    allowed_parent_ids: tuple[str, ...] | None,
) -> list[RankedChunkMatch]:
    """透過 PostgreSQL RPC 取得 recall 候選與其排序輸入。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    rpc_stmt = build_match_chunks_rpc_statement()
    rows = session.execute(
        rpc_stmt,
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": settings.retrieval_vector_top_k,
            "fts_top_k": settings.retrieval_fts_top_k,
            "allowed_document_ids": list(allowed_document_ids) if allowed_document_ids else None,
            "allowed_parent_chunk_ids": list(allowed_parent_ids) if allowed_parent_ids else None,
        },
    ).all()

    matches: list[RankedChunkMatch] = []
    for row in rows:
        chunk = session.get(DocumentChunk, str(row.id))
        if chunk is None:
            continue
        matches.append(
            RankedChunkMatch(
                chunk=chunk,
                vector_rank=row.vector_rank,
                fts_rank=row.fts_rank,
            )
        )
    return matches


def _run_sqlite_candidate_generation(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    allowed_parent_ids: tuple[str, ...] | None,
) -> list[RankedChunkMatch]:
    """SQLite 本機測試專用的 candidate generation 路徑。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    chunks = session.scalars(
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.child,
            Document.id.in_(allowed_document_ids) if allowed_document_ids else True,
            DocumentChunk.parent_chunk_id.in_(allowed_parent_ids) if allowed_parent_ids else True,
        )
        .order_by(DocumentChunk.position.asc())
    ).all()

    merged_by_chunk_id: dict[str, RankedChunkMatch] = {}

    vector_scored = sorted(
        (
            (cosine_distance(query_embedding, chunk.embedding), chunk)
            for chunk in chunks
            if chunk.embedding is not None
        ),
        key=lambda item: (item[0], item[1].position),
    )[: settings.retrieval_vector_top_k]
    for index, (_, chunk) in enumerate(vector_scored, start=1):
        current = merged_by_chunk_id.setdefault(chunk.id, RankedChunkMatch(chunk=chunk))
        current.vector_rank = index

    fts_scored = sorted(
        (
            (sqlite_fts_score(query=query, content=chunk.content), chunk)
            for chunk in chunks
            if chunk.content
        ),
        key=lambda item: (-item[0], item[1].position),
    )
    for index, (_, chunk) in enumerate((item for item in fts_scored if item[0] > 0), start=1):
        if index > settings.retrieval_fts_top_k:
            break
        current = merged_by_chunk_id.setdefault(chunk.id, RankedChunkMatch(chunk=chunk))
        current.fts_rank = index

    return list(merged_by_chunk_id.values())


def _run_postgres_document_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[DocumentRecallMatch]:
    """透過 PostgreSQL 對 document synopsis 執行 recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    rows = session.execute(
        build_document_recall_statement(),
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": settings.retrieval_document_recall_top_k,
            "fts_top_k": settings.retrieval_document_recall_top_k,
        },
    ).all()

    matches: list[DocumentRecallMatch] = []
    for row in rows:
        document = session.get(Document, str(row.id))
        if document is None:
            continue
        matches.append(
            DocumentRecallMatch(
                document=document,
                vector_rank=row.vector_rank,
                fts_rank=row.fts_rank,
            )
        )
    return matches


def _run_sqlite_document_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[DocumentRecallMatch]:
    """SQLite 測試路徑使用的 document synopsis recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    documents = session.scalars(
        select(Document)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
        )
        .order_by(Document.file_name.asc())
    ).all()

    merged_by_document_id: dict[str, DocumentRecallMatch] = {}
    vector_scored = sorted(
        (
            (cosine_distance(query_embedding, document.synopsis_embedding), document)
            for document in documents
            if document.synopsis_embedding is not None
        ),
        key=lambda item: (item[0], item[1].file_name.casefold(), item[1].id),
    )[: settings.retrieval_document_recall_top_k]
    for index, (_, document) in enumerate(vector_scored, start=1):
        current = merged_by_document_id.setdefault(document.id, DocumentRecallMatch(document=document))
        current.vector_rank = index

    fts_scored = sorted(
        (
            (sqlite_fts_score(query=query, content=document.synopsis_text or ""), document)
            for document in documents
            if document.synopsis_text
        ),
        key=lambda item: (-item[0], item[1].file_name.casefold(), item[1].id),
    )
    for index, (_, document) in enumerate((item for item in fts_scored if item[0] > 0), start=1):
        if index > settings.retrieval_document_recall_top_k:
            break
        current = merged_by_document_id.setdefault(document.id, DocumentRecallMatch(document=document))
        current.fts_rank = index

    return list(merged_by_document_id.values())


def _run_postgres_section_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    top_k: int,
) -> list[SectionRecallMatch]:
    """透過 PostgreSQL 對 section synopsis 執行 recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    rows = session.execute(
        build_section_recall_statement(),
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": top_k,
            "fts_top_k": top_k,
            "allowed_document_ids": list(allowed_document_ids) if allowed_document_ids else None,
        },
    ).all()

    matches: list[SectionRecallMatch] = []
    for row in rows:
        parent_chunk = session.get(DocumentChunk, str(row.id))
        if parent_chunk is None:
            continue
        matches.append(
            SectionRecallMatch(
                parent_chunk=parent_chunk,
                vector_rank=row.vector_rank,
                fts_rank=row.fts_rank,
            )
        )
    return matches


def _run_sqlite_section_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    top_k: int,
) -> list[SectionRecallMatch]:
    """SQLite 測試路徑使用的 section synopsis recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    parents = session.scalars(
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.parent,
            Document.id.in_(allowed_document_ids) if allowed_document_ids else True,
        )
        .order_by(DocumentChunk.position.asc())
    ).all()

    merged_by_parent_id: dict[str, SectionRecallMatch] = {}
    vector_scored = sorted(
        (
            (cosine_distance(query_embedding, parent.section_synopsis_embedding), parent)
            for parent in parents
            if parent.section_synopsis_embedding is not None
        ),
        key=lambda item: (item[0], item[1].position, item[1].id),
    )[:top_k]
    for index, (_, parent) in enumerate(vector_scored, start=1):
        current = merged_by_parent_id.setdefault(parent.id, SectionRecallMatch(parent_chunk=parent))
        current.vector_rank = index

    fts_scored = sorted(
        (
            (sqlite_fts_score(query=query, content=parent.section_synopsis_text or ""), parent)
            for parent in parents
            if parent.section_synopsis_text
        ),
        key=lambda item: (-item[0], item[1].position, item[1].id),
    )
    for index, (_, parent) in enumerate((item for item in fts_scored if item[0] > 0), start=1):
        if index > top_k:
            break
        current = merged_by_parent_id.setdefault(parent.id, SectionRecallMatch(parent_chunk=parent))
        current.fts_rank = index

    return list(merged_by_parent_id.values())
