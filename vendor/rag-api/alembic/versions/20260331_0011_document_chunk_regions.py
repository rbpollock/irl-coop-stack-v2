"""為 PDF citation locator 新增 document_chunk_regions。"""

from alembic import op
import sqlalchemy as sa


revision = "20260331_0011"
down_revision = "20260331_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 document_chunk_regions。

    參數：
    - 無

    回傳：
    - `None`：僅更新 schema。
    """

    op.create_table(
        "document_chunk_regions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("region_order", sa.Integer(), nullable=False),
        sa.Column("bbox_left", sa.Float(), nullable=False),
        sa.Column("bbox_bottom", sa.Float(), nullable=False),
        sa.Column("bbox_right", sa.Float(), nullable=False),
        sa.Column("bbox_top", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", "region_order", name="uq_document_chunk_regions_chunk_order"),
    )


def downgrade() -> None:
    """移除 document_chunk_regions。

    參數：
    - 無

    回傳：
    - `None`：僅回退 schema。
    """

    op.drop_table("document_chunk_regions")
