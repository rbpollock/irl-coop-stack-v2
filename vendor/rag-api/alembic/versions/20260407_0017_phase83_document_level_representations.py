"""新增 Phase 8.3 document synopsis 欄位與 child recall SQL filter contract。"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_0017"
down_revision = "20260407_0016"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    """加入 document synopsis 欄位、索引與新版 `match_chunks` contract。

    參數：
    - 無

    回傳：
    - `None`：僅更新 schema、索引與 PostgreSQL function。
    """

    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.add_column("documents", sa.Column("synopsis_text", sa.Text(), nullable=True))
    if is_postgres:
        op.execute(f"ALTER TABLE documents ADD COLUMN synopsis_embedding vector({EMBEDDING_DIMENSIONS})")
    else:
        op.add_column("documents", sa.Column("synopsis_embedding", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("synopsis_updated_at", sa.DateTime(timezone=True), nullable=True))

    if not is_postgres:
        return

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_synopsis_embedding_hnsw
        ON documents
        USING hnsw (synopsis_embedding vector_cosine_ops)
        WHERE synopsis_embedding IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_synopsis_text_pgroonga
        ON documents
        USING pgroonga (synopsis_text)
        WHERE synopsis_text IS NOT NULL;
        """
    )
    op.execute(f"DROP FUNCTION IF EXISTS match_chunks(vector({EMBEDDING_DIMENSIONS}), TEXT, VARCHAR(36), INT, INT)")
    op.execute(
        f"""
        CREATE FUNCTION match_chunks(
            query_embedding vector({EMBEDDING_DIMENSIONS}),
            query_text TEXT,
            match_area_id VARCHAR(36),
            vector_top_k INT DEFAULT 12,
            fts_top_k INT DEFAULT 12,
            allowed_document_ids VARCHAR(36)[] DEFAULT NULL
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
              AND (
                allowed_document_ids IS NULL
                OR d.id = ANY(allowed_document_ids)
              )
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
              AND (
                allowed_document_ids IS NULL
                OR d.id = ANY(allowed_document_ids)
              )
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
    """回退 document synopsis 欄位與新版 `match_chunks` contract。

    參數：
    - 無

    回傳：
    - `None`：僅回退 schema、索引與 PostgreSQL function。
    """

    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_documents_synopsis_embedding_hnsw")
        op.execute("DROP INDEX IF EXISTS ix_documents_synopsis_text_pgroonga")
        op.execute(
            f"DROP FUNCTION IF EXISTS match_chunks(vector({EMBEDDING_DIMENSIONS}), TEXT, VARCHAR(36), INT, INT, VARCHAR(36)[])"
        )
        op.execute(
            f"""
            CREATE FUNCTION match_chunks(
                query_embedding vector({EMBEDDING_DIMENSIONS}),
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

    op.drop_column("documents", "synopsis_updated_at")
    op.drop_column("documents", "synopsis_embedding")
    op.drop_column("documents", "synopsis_text")
