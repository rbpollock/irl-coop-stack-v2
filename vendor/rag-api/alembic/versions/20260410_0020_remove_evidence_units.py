"""移除 Phase 8B evidence units schema。"""

from alembic import op


revision = "20260410_0020"
down_revision = "20260409_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """移除 evidence units 資料表與文件 enrichment 觀測欄位。

    參數：
    - 無

    回傳：
    - `None`：僅更新資料庫 schema。
    """

    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_document_chunk_evidence_units_text_pgroonga")
        op.execute("DROP INDEX IF EXISTS ix_document_chunk_evidence_units_embedding_hnsw")

    op.drop_table("document_chunk_evidence_unit_parent_sources")
    op.drop_table("document_chunk_evidence_unit_child_sources")
    op.drop_table("document_chunk_evidence_units")

    op.drop_column("documents", "evidence_enrichment_updated_at")
    op.drop_column("documents", "evidence_enrichment_error")
    op.drop_column("documents", "evidence_enrichment_strategy")
    op.drop_column("documents", "evidence_enrichment_status")


def downgrade() -> None:
    """不支援還原已移除的 evidence units schema。

    參數：
    - 無

    回傳：
    - `None`：此 migration 不提供 downgrade 邏輯。
    """

    raise NotImplementedError("evidence units schema 已移除，不支援 downgrade 還原。")
