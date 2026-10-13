"""加入 retrieval foundation 所需的 vector 與 PGroonga schema。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError


revision = "20260313_0005"
down_revision = "20260313_0004"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    """讀取指定資料表目前欄位名稱集合。"""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _ensure_extension(extension_name: str) -> None:
    """確認 PostgreSQL extension 已安裝，必要時嘗試建立。

    參數：
    - `extension_name`：目標 extension 名稱。

    回傳：
    - `None`：僅驗證或建立 extension。

    風險：
    - 在 Supabase 映像中，正式 migration 使用的 `postgres` 角色不是 superuser。
      若 extension 尚未於初始化階段預先安裝，這裡會因權限不足而失敗。
    """

    bind = op.get_bind()
    installed = bind.execute(
        sa.text("select 1 from pg_extension where extname = :extension_name"),
        {"extension_name": extension_name},
    ).scalar_one_or_none()
    if installed is not None:
        return
    try:
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension_name}")
    except DBAPIError as exc:  # pragma: no cover - 依實際 PostgreSQL 權限決定。
        raise RuntimeError(
            f"extension `{extension_name}` 尚未安裝，且目前資料庫角色無法建立它。"
            "請先在資料庫初始化階段或由 superuser 預先安裝所需 extension。"
        ) from exc


def upgrade() -> None:
    """加入 retrieval foundation 所需 schema。"""

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    chunk_columns = _get_column_names("document_chunks")

    if dialect_name == "postgresql":
        _ensure_extension("vector")
        _ensure_extension("pgroonga")
        if "embedding" not in chunk_columns:
            op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_ivfflat
            ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL;
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_content_pgroonga
            ON document_chunks
            USING pgroonga (content)
            WHERE chunk_type = 'child';
            """
        )
        return

    if "embedding" not in chunk_columns:
        op.add_column("document_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
    op.create_index("ix_document_chunks_embedding_ivfflat", "document_chunks", ["embedding"], unique=False)
    op.create_index("ix_document_chunks_content_idx", "document_chunks", ["content"], unique=False)


def downgrade() -> None:
    """回滾 retrieval foundation schema。"""

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    chunk_columns = _get_column_names("document_chunks")

    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_pgroonga")
        if "embedding" in chunk_columns:
            op.execute("ALTER TABLE document_chunks DROP COLUMN embedding")
        return

    op.drop_index("ix_document_chunks_embedding_ivfflat", table_name="document_chunks")
    op.drop_index("ix_document_chunks_content_idx", table_name="document_chunks")
    if "embedding" in chunk_columns:
        op.drop_column("document_chunks", "embedding")
