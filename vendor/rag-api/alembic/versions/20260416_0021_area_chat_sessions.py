"""新增 area chat session metadata schema。"""

from alembic import op
import sqlalchemy as sa


# 本次 migration 的唯一識別碼。
revision = "20260416_0021"
# 本次 migration 的前一版。
down_revision = "20260410_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """建立正式的 area chat session metadata 資料表與索引。"""

    op.create_table(
        "area_chat_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("area_id", sa.String(length=36), nullable=False),
        sa.Column("owner_sub", sa.String(length=255), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="新對話"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", name="uq_area_chat_sessions_thread_id"),
    )
    op.create_index(
        "ix_area_chat_sessions_area_owner_updated_at",
        "area_chat_sessions",
        ["area_id", "owner_sub", "updated_at"],
        unique=False,
    )
    op.alter_column("area_chat_sessions", "title", server_default=None)


def downgrade() -> None:
    """移除 area chat session metadata 資料表與索引。"""

    op.drop_index("ix_area_chat_sessions_area_owner_updated_at", table_name="area_chat_sessions")
    op.drop_table("area_chat_sessions")
