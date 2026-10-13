"""新增 area 可見性層級（public / group / private）。"""

from alembic import op
import sqlalchemy as sa


# 本次 migration 的唯一識別碼。
revision = "20260906_0022"
# 本次 migration 的前一版。
down_revision = "20260416_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 areas.visibility 欄位（預設 group）。"""

    op.add_column(
        "areas",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="group"),
    )


def downgrade() -> None:
    """移除 areas.visibility 欄位。"""

    op.drop_column("areas", "visibility")
