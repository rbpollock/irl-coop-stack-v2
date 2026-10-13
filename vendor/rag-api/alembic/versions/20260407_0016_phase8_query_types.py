"""擴充 Phase 8.1 evaluation query_type enum 至三種題型。"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_0016"
down_revision = "20260405_0015"
branch_labels = None
depends_on = None


OLD_QUERY_TYPE_ENUM = sa.Enum(
    "fact_lookup",
    name="evaluationquerytype",
    native_enum=False,
)
NEW_QUERY_TYPE_ENUM = sa.Enum(
    "fact_lookup",
    "document_summary",
    "cross_document_compare",
    name="evaluationquerytype",
    native_enum=False,
)


def upgrade() -> None:
    """將 evaluation query type 擴充為三種正式題型。

    參數：
    - 無

    回傳：
    - `None`：僅更新 schema。
    """

    op.alter_column(
        "retrieval_eval_datasets",
        "query_type",
        existing_type=OLD_QUERY_TYPE_ENUM,
        type_=NEW_QUERY_TYPE_ENUM,
        existing_nullable=False,
        postgresql_using="query_type::varchar(22)",
    )

    op.alter_column(
        "retrieval_eval_items",
        "query_type",
        existing_type=OLD_QUERY_TYPE_ENUM,
        type_=NEW_QUERY_TYPE_ENUM,
        existing_nullable=False,
        postgresql_using="query_type::varchar(22)",
    )


def downgrade() -> None:
    """將 evaluation query type 回退為僅支援 fact_lookup。

    參數：
    - 無

    回傳：
    - `None`：僅回退 schema。
    """

    op.alter_column(
        "retrieval_eval_items",
        "query_type",
        existing_type=NEW_QUERY_TYPE_ENUM,
        type_=OLD_QUERY_TYPE_ENUM,
        existing_nullable=False,
        postgresql_using="query_type::varchar(11)",
    )

    op.alter_column(
        "retrieval_eval_datasets",
        "query_type",
        existing_type=NEW_QUERY_TYPE_ENUM,
        type_=OLD_QUERY_TYPE_ENUM,
        existing_nullable=False,
        postgresql_using="query_type::varchar(11)",
    )
