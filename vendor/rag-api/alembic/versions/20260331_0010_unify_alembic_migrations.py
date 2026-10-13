"""收斂 migration 來源並清理舊的 retrieval schema 遺留。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError


revision = "20260331_0010"
down_revision = "20260320_0009"
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
    """清理舊雙軌 migration 遺留，並補齊目前 PostgreSQL retrieval schema。

    參數：
    - 無

    回傳：
    - `None`：僅更新 schema。
    """

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    chunk_columns = _get_column_names("document_chunks")

    _ensure_extension("vector")
    _ensure_extension("pgroonga")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts_document_gin")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_idx")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_content_pgroonga
        ON document_chunks
        USING pgroonga (content)
        WHERE chunk_type = 'child';
        """
    )

    if "fts_document" in chunk_columns:
        op.execute("ALTER TABLE document_chunks DROP COLUMN fts_document")


def downgrade() -> None:
    """回退 migration 收斂後的 retrieval schema 清理。

    參數：
    - 無

    回傳：
    - `None`：僅回退本次 cleanup 所做的改動。
    """

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    chunk_columns = _get_column_names("document_chunks")

    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_pgroonga")
    if "fts_document" not in chunk_columns:
        op.execute("ALTER TABLE document_chunks ADD COLUMN fts_document tsvector")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_fts_document_gin
        ON document_chunks
        USING gin (fts_document)
        WHERE fts_document IS NOT NULL;
        """
    )
