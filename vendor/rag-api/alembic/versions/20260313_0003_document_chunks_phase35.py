"""加入 document_chunks 與 Phase 3.5 ingest observability 欄位。"""

from alembic import op
import sqlalchemy as sa


revision = "20260313_0003"
down_revision = "20260312_0002"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    """讀取指定資料表目前欄位名稱集合。"""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _get_table_names() -> set[str]:
    """讀取目前資料庫中的資料表名稱集合。"""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def upgrade() -> None:
    """加入 chunking 與 ingest observability 所需 schema。"""

    document_columns = _get_column_names("documents")
    if "indexed_at" not in document_columns:
        op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))

    ingest_job_columns = _get_column_names("ingest_jobs")
    if "stage" not in ingest_job_columns:
        op.add_column("ingest_jobs", sa.Column("stage", sa.String(length=32), nullable=False, server_default="queued"))
        op.alter_column("ingest_jobs", "stage", server_default=None)
    if "parent_chunk_count" not in ingest_job_columns:
        op.add_column(
            "ingest_jobs",
            sa.Column("parent_chunk_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("ingest_jobs", "parent_chunk_count", server_default=None)
    if "child_chunk_count" not in ingest_job_columns:
        op.add_column(
            "ingest_jobs",
            sa.Column("child_chunk_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("ingest_jobs", "child_chunk_count", server_default=None)

    if "document_chunks" not in _get_table_names():
        chunk_type_enum = sa.Enum("parent", "child", name="chunk_type_enum", native_enum=False)
        op.create_table(
            "document_chunks",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("parent_chunk_id", sa.String(length=36), sa.ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=True),
            sa.Column("chunk_type", chunk_type_enum, nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("section_index", sa.Integer(), nullable=False),
            sa.Column("child_index", sa.Integer(), nullable=True),
            sa.Column("heading", sa.String(length=255), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("content_preview", sa.String(length=255), nullable=False),
            sa.Column("char_count", sa.Integer(), nullable=False),
            sa.Column("start_offset", sa.Integer(), nullable=False),
            sa.Column("end_offset", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("document_id", "position", name="uq_document_chunks_document_position"),
            sa.UniqueConstraint("document_id", "section_index", "child_index", name="uq_document_chunks_document_section_child"),
        )


def downgrade() -> None:
    """回滾 Phase 3.5 chunking 與 observability schema。"""

    if "document_chunks" in _get_table_names():
        op.drop_table("document_chunks")

    ingest_job_columns = _get_column_names("ingest_jobs")
    if "child_chunk_count" in ingest_job_columns:
        op.drop_column("ingest_jobs", "child_chunk_count")
    if "parent_chunk_count" in ingest_job_columns:
        op.drop_column("ingest_jobs", "parent_chunk_count")
    if "stage" in ingest_job_columns:
        op.drop_column("ingest_jobs", "stage")

    document_columns = _get_column_names("documents")
    if "indexed_at" in document_columns:
        op.drop_column("documents", "indexed_at")
