"""修復 documents 資料表與現行模型不一致的欄位。"""

from alembic import op
import sqlalchemy as sa


# Alembic revision 唯一識別碼。
revision = "20260312_0002"

# 本次 migration 的前一版。
down_revision = "20260312_0001"

# Alembic branch labels 預留欄位。
branch_labels = None

# Alembic dependency 預留欄位。
depends_on = None


def _get_column_names() -> set[str]:
    """讀取目前 documents 資料表欄位名稱集合。"""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("documents")}


def upgrade() -> None:
    """補上舊資料庫缺失的 documents 欄位，避免現行 API 查詢失敗。"""

    column_names = _get_column_names()

    if "content_type" not in column_names:
        op.add_column(
            "documents",
            sa.Column(
                "content_type",
                sa.String(length=255),
                nullable=False,
                server_default="application/octet-stream",
            ),
        )
        op.alter_column("documents", "content_type", server_default=None)

    if "file_size" not in column_names:
        op.add_column(
            "documents",
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("documents", "file_size", server_default=None)


def downgrade() -> None:
    """回滾 schema 修復欄位。"""

    column_names = _get_column_names()

    if "file_size" in column_names:
        op.drop_column("documents", "file_size")

    if "content_type" in column_names:
        op.drop_column("documents", "content_type")
