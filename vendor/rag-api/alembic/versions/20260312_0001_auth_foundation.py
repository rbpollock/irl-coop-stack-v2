"""建立授權與資料基礎骨架表。"""

from alembic import op
import sqlalchemy as sa


# Alembic revision 唯一識別碼。
revision = "20260312_0001"

# 本次 migration 的前一版；初始版為空值。
down_revision = None

# Alembic branch labels 預留欄位。
branch_labels = None

# Alembic dependency 預留欄位。
depends_on = None


def upgrade() -> None:
    """建立最小授權與文件骨架資料表。"""

    role_enum = sa.Enum("reader", "maintainer", "admin", name="role_enum", native_enum=False)
    document_status_enum = sa.Enum(
        "uploaded",
        "processing",
        "ready",
        "failed",
        name="document_status_enum",
        native_enum=False,
    )
    ingest_job_status_enum = sa.Enum(
        "queued",
        "processing",
        "succeeded",
        "failed",
        name="ingest_job_status_enum",
        native_enum=False,
    )

    op.create_table(
        "areas",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "area_user_roles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("area_id", sa.String(length=36), sa.ForeignKey("areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_sub", sa.String(length=255), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("area_id", "user_sub", name="uq_area_user_roles_area_subject"),
    )
    op.create_table(
        "area_group_roles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("area_id", sa.String(length=36), sa.ForeignKey("areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_path", sa.String(length=255), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("area_id", "group_path", name="uq_area_group_roles_area_group_path"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("area_id", sa.String(length=36), sa.ForeignKey("areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("status", document_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", ingest_job_status_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """回滾最小授權與文件骨架資料表。"""

    op.drop_table("ingest_jobs")
    op.drop_table("documents")
    op.drop_table("area_group_roles")
    op.drop_table("area_user_roles")
    op.drop_table("areas")
