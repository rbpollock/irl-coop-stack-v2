"""將 retrieval vector index 切換為 HNSW，並補齊 documents filter index。"""

from alembic import op


revision = "20260313_0006"
down_revision = "20260313_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """將 ANN index 由 IVFFlat 切換為 HNSW，並補 documents filter index。"""

    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL;
            """
        )
    else:
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat")
        op.create_index("ix_document_chunks_embedding_hnsw", "document_chunks", ["embedding"], unique=False)

    op.create_index("ix_documents_area_status", "documents", ["area_id", "status"], unique=False)


def downgrade() -> None:
    """回滾 HNSW index 與 documents filter index。"""

    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.drop_index("ix_documents_area_status", table_name="documents")

    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_ivfflat
            ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL;
            """
        )
    else:
        op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
        op.create_index("ix_document_chunks_embedding_ivfflat", "document_chunks", ["embedding"], unique=False)
