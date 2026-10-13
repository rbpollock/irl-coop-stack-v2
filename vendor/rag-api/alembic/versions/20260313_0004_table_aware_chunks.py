"""加入表格感知 chunking 所需 schema。"""

from alembic import op
import sqlalchemy as sa


revision = "20260313_0004"
down_revision = "20260313_0003"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    """讀取指定資料表目前欄位名稱集合。"""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """加入 table-aware chunking 所需 schema。"""

    chunk_columns = _get_column_names("document_chunks")
    if "structure_kind" not in chunk_columns:
        op.add_column(
            "document_chunks",
            sa.Column(
                "structure_kind",
                sa.Enum("text", "table", name="chunk_structure_kind_enum", native_enum=False),
                nullable=False,
                server_default="text",
            ),
        )
        op.alter_column("document_chunks", "structure_kind", server_default=None)


def downgrade() -> None:
    """回滾 table-aware chunking schema。"""

    chunk_columns = _get_column_names("document_chunks")
    if "structure_kind" in chunk_columns:
        op.drop_column("document_chunks", "structure_kind")
