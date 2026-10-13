"""新增 Phase 7 retrieval evaluation dataset、run 與 artifact schema。"""

from alembic import op
import sqlalchemy as sa


revision = "20260401_0012"
down_revision = "20260331_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 retrieval evaluation 相關資料表。

    參數：
    - 無

    回傳：
    - `None`：僅更新 schema。
    """

    op.create_table(
        "retrieval_eval_datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("area_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("query_type", sa.Enum("fact_lookup", name="evaluationquerytype", native_enum=False), nullable=False),
        sa.Column("created_by_sub", sa.String(length=255), nullable=False),
        sa.Column("baseline_run_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "retrieval_eval_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("query_type", sa.Enum("fact_lookup", name="evaluationquerytype", native_enum=False), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("language", sa.Enum("zh-TW", "en", "mixed", name="evaluationlanguage", native_enum=False), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["retrieval_eval_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "retrieval_eval_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.Enum("running", "completed", "failed", name="evaluationrunstatus", native_enum=False), nullable=False),
        sa.Column("baseline_run_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_sub", sa.String(length=255), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("evaluation_profile", sa.String(length=64), nullable=False, server_default="production_like_v1"),
        sa.Column("config_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["retrieval_eval_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "retrieval_eval_item_spans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("relevance_grade", sa.Integer(), nullable=True),
        sa.Column("is_retrieval_miss", sa.Boolean(), nullable=False),
        sa.Column("created_by_sub", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["retrieval_eval_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "item_id",
            "document_id",
            "start_offset",
            "end_offset",
            "is_retrieval_miss",
            name="uq_retrieval_eval_item_spans_span",
        ),
    )
    op.create_table(
        "retrieval_eval_run_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("baseline_compare_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["retrieval_eval_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "fk_retrieval_eval_datasets_baseline_run",
        "retrieval_eval_datasets",
        "retrieval_eval_runs",
        ["baseline_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_retrieval_eval_runs_baseline_run",
        "retrieval_eval_runs",
        "retrieval_eval_runs",
        ["baseline_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """移除 retrieval evaluation 相關資料表。

    參數：
    - 無

    回傳：
    - `None`：僅回退 schema。
    """

    op.drop_constraint("fk_retrieval_eval_runs_baseline_run", "retrieval_eval_runs", type_="foreignkey")
    op.drop_constraint("fk_retrieval_eval_datasets_baseline_run", "retrieval_eval_datasets", type_="foreignkey")
    op.drop_table("retrieval_eval_run_artifacts")
    op.drop_table("retrieval_eval_item_spans")
    op.drop_table("retrieval_eval_runs")
    op.drop_table("retrieval_eval_items")
    op.drop_table("retrieval_eval_datasets")
