"""為文件全文 preview 新增 display_text 欄位。"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_0009"
down_revision = "20260319_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 documents.display_text。

    參數：
    - 無

    回傳：
    - `None`：僅更新 schema。
    """

    op.add_column("documents", sa.Column("display_text", sa.Text(), nullable=True))


def downgrade() -> None:
    """移除 documents.display_text。

    參數：
    - 無

    回傳：
    - `None`：僅回退 schema。
    """

    op.drop_column("documents", "display_text")
