"""新增 Phase 8B evidence units schema 與 documents observability 欄位。"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0019"
down_revision = "20260408_0018"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    """加入 evidence units schema、索引與 documents observability 欄位。

    參數：
    - 無

    回傳：
    - `None`：僅更新資料庫 schema。
    """

    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.add_column(
        "documents",
        sa.Column(
            "evidence_enrichment_status",
            sa.String(length=16),
            nullable=False,
            server_default="skipped",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("evidence_enrichment_strategy", sa.String(length=32), nullable=True),
    )
    op.add_column("documents", sa.Column("evidence_enrichment_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("evidence_enrichment_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "document_chunk_evidence_units",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("primary_parent_chunk_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("build_strategy", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("path_quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("path_quality_reason", sa.String(length=32), nullable=False, server_default="ok"),
        sa.Column("cluster_strategy", sa.String(length=32), nullable=False),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("section_path_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_parent_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "primary_parent_chunk_id",
            "position",
            name="uq_document_chunk_evidence_units_parent_position",
        ),
    )
    if is_postgres:
        op.execute(
            f"ALTER TABLE document_chunk_evidence_units ADD COLUMN evidence_embedding vector({EMBEDDING_DIMENSIONS})"
        )
    else:
        op.add_column("document_chunk_evidence_units", sa.Column("evidence_embedding", sa.JSON(), nullable=True))

    op.create_table(
        "document_chunk_evidence_unit_child_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evidence_unit_id", sa.String(length=36), nullable=False),
        sa.Column("child_chunk_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evidence_unit_id"], ["document_chunk_evidence_units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["child_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_unit_id",
            "child_chunk_id",
            name="uq_document_chunk_evidence_unit_child_sources_unit_child",
        ),
        sa.UniqueConstraint(
            "evidence_unit_id",
            "position",
            name="uq_document_chunk_evidence_unit_child_sources_unit_position",
        ),
    )

    op.create_table(
        "document_chunk_evidence_unit_parent_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evidence_unit_id", sa.String(length=36), nullable=False),
        sa.Column("parent_chunk_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evidence_unit_id"], ["document_chunk_evidence_units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_unit_id",
            "parent_chunk_id",
            name="uq_document_chunk_evidence_unit_parent_sources_unit_parent",
        ),
        sa.UniqueConstraint(
            "evidence_unit_id",
            "position",
            name="uq_document_chunk_evidence_unit_parent_sources_unit_position",
        ),
    )

    op.create_index(
        "ix_document_chunk_evidence_units_document_position",
        "document_chunk_evidence_units",
        ["document_id", "position"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunk_evidence_units_primary_parent",
        "document_chunk_evidence_units",
        ["primary_parent_chunk_id"],
        unique=False,
    )
    if is_postgres:
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunk_evidence_units_embedding_hnsw
            ON document_chunk_evidence_units
            USING hnsw (evidence_embedding vector_cosine_ops)
            WHERE evidence_embedding IS NOT NULL;
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunk_evidence_units_text_pgroonga
            ON document_chunk_evidence_units
            USING pgroonga (evidence_text);
            """
        )

    op.alter_column("documents", "evidence_enrichment_status", server_default=None)


def downgrade() -> None:
    """回退 Phase 8B evidence units schema 與 documents observability 欄位。

    參數：
    - 無

    回傳：
    - `None`：僅回退資料庫 schema。
    """

    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_document_chunk_evidence_units_text_pgroonga")
        op.execute("DROP INDEX IF EXISTS ix_document_chunk_evidence_units_embedding_hnsw")

    op.drop_index("ix_document_chunk_evidence_units_primary_parent", table_name="document_chunk_evidence_units")
    op.drop_index("ix_document_chunk_evidence_units_document_position", table_name="document_chunk_evidence_units")
    op.drop_table("document_chunk_evidence_unit_parent_sources")
    op.drop_table("document_chunk_evidence_unit_child_sources")
    op.drop_table("document_chunk_evidence_units")

    op.drop_column("documents", "evidence_enrichment_updated_at")
    op.drop_column("documents", "evidence_enrichment_error")
    op.drop_column("documents", "evidence_enrichment_strategy")
    op.drop_column("documents", "evidence_enrichment_status")
