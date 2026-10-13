"""將 embedding schema 調整為 1536 維，以對齊 OpenAI embeddings 主線。"""

from alembic import op


revision = "20260405_0015"
down_revision = "20260405_0014"
branch_labels = None
depends_on = None

OLD_EMBEDDING_DIMENSIONS = 1024
NEW_EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    """將 PostgreSQL embedding 欄位與 RPC 調整為 1536 維。

    參數：
    - 無

    回傳：
    - `None`：僅在 PostgreSQL 上執行 schema、index 與 RPC 更新。
    """

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    zero_padding_vector_sql = "'[" + ",".join(["0"] * (NEW_EMBEDDING_DIMENSIONS - OLD_EMBEDDING_DIMENSIONS)) + "]'::vector(512)"

    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute(f"DROP FUNCTION IF EXISTS match_chunks(vector({OLD_EMBEDDING_DIMENSIONS}), TEXT, VARCHAR(36), INT, INT)")
    op.execute(
        f"""
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector({NEW_EMBEDDING_DIMENSIONS})
        USING CASE
            WHEN embedding IS NULL THEN NULL
            ELSE (embedding || {zero_padding_vector_sql})::vector({NEW_EMBEDDING_DIMENSIONS})
        END
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL;
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION match_chunks(
            query_embedding vector({NEW_EMBEDDING_DIMENSIONS}),
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
    """將 PostgreSQL embedding 欄位與 RPC 回退為 1024 維。

    參數：
    - 無

    回傳：
    - `None`：僅在 PostgreSQL 上執行 schema、index 與 RPC 回退。
    """

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute(f"DROP FUNCTION IF EXISTS match_chunks(vector({NEW_EMBEDDING_DIMENSIONS}), TEXT, VARCHAR(36), INT, INT)")
    op.execute(
        f"""
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector({OLD_EMBEDDING_DIMENSIONS})
        USING CASE
            WHEN embedding IS NULL THEN NULL
            ELSE subvector(embedding, 1, {OLD_EMBEDDING_DIMENSIONS})::vector({OLD_EMBEDDING_DIMENSIONS})
        END
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL;
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION match_chunks(
            query_embedding vector({OLD_EMBEDDING_DIMENSIONS}),
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
