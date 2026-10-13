"""將既有 PostgreSQL `match_chunks` RPC 收斂為目前 retrieval contract。"""

from alembic import op


revision = "20260317_0007"
down_revision = "20260313_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """更新 PostgreSQL `match_chunks` RPC 為最新 contract。

    參數：
    - 無

    回傳：
    - `None`：僅在 PostgreSQL 上重建 RPC。

    風險：
    - 此 migration 會覆寫同名 function，既有 retrieval 路徑將改以 Python 層執行最終 RRF。
    """

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_chunks(
            query_embedding vector(1536),
            query_text TEXT,
            match_area_id VARCHAR(36),
            vector_top_k INT DEFAULT 12,
            fts_top_k INT DEFAULT 12
        )
        RETURNS TABLE (
            id VARCHAR(36),
            document_id VARCHAR(36),
            content TEXT,
            content_preview VARCHAR(255),
            structure_kind TEXT,
            heading VARCHAR(255),
            vector_rank INT,
            fts_rank INT,
            fts_score FLOAT
        )
        LANGUAGE sql
        AS $$
        WITH vector_matches AS (
            SELECT
                dc.id,
                ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding, dc.id) :: INT AS rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.area_id = match_area_id
              AND d.status = 'ready'
              AND dc.chunk_type = 'child'
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> query_embedding, dc.id
            LIMIT vector_top_k
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
            WHERE d.area_id = match_area_id
              AND d.status = 'ready'
              AND dc.chunk_type = 'child'
              AND dc.content &@~ query_text
            ORDER BY pgroonga_score(dc.tableoid, dc.ctid) DESC, dc.id
            LIMIT fts_top_k
        ),
        candidate_ids AS (
            SELECT id FROM vector_matches
            UNION
            SELECT id FROM fts_matches
        )
        SELECT
            dc.id,
            dc.document_id,
            dc.content,
            dc.content_preview,
            dc.structure_kind,
            dc.heading,
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
            dc.id;
        $$;
        """
    )


def downgrade() -> None:
    """回退 PostgreSQL `match_chunks` RPC 至舊 contract。

    參數：
    - 無

    回傳：
    - `None`：僅在 PostgreSQL 上重建舊版 RPC。
    """

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_chunks(
            query_embedding vector(1536),
            query_text TEXT,
            match_area_id VARCHAR(36),
            match_count INT DEFAULT 12,
            rrf_k INT DEFAULT 60
        )
        RETURNS TABLE (
            id VARCHAR(36),
            document_id VARCHAR(36),
            content TEXT,
            content_preview VARCHAR(255),
            structure_kind TEXT,
            heading VARCHAR(255),
            vector_rank INT,
            fts_rank INT,
            combined_score FLOAT
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            WITH vector_matches AS (
                SELECT
                    dc.id,
                    ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding) AS rank
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE d.area_id = match_area_id
                  AND d.status = 'ready'
                  AND dc.chunk_type = 'child'
                  AND dc.embedding IS NOT NULL
                LIMIT match_count * 2
            ),
            fts_matches AS (
                SELECT
                    dc.id,
                    ROW_NUMBER() OVER (ORDER BY dc.content &@~ query_text) AS rank
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE d.area_id = match_area_id
                  AND d.status = 'ready'
                  AND dc.chunk_type = 'child'
                  AND dc.content &@~ query_text
                LIMIT match_count * 2
            )
            SELECT
                dc.id,
                dc.document_id,
                dc.content,
                dc.content_preview,
                dc.structure_kind,
                dc.heading,
                vm.rank::INT AS vector_rank,
                fm.rank::INT AS fts_rank,
                (
                    COALESCE(1.0 / (rrf_k + vm.rank), 0.0) +
                    COALESCE(1.0 / (rrf_k + fm.rank), 0.0)
                )::FLOAT AS combined_score
            FROM document_chunks dc
            LEFT JOIN vector_matches vm ON dc.id = vm.id
            LEFT JOIN fts_matches fm ON dc.id = fm.id
            WHERE (vm.id IS NOT NULL OR fm.id IS NOT NULL)
            ORDER BY combined_score DESC
            LIMIT match_count;
        END;
        $$;
        """
    )
