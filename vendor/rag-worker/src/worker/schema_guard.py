"""Worker 啟動前的資料庫 schema 相容性檢查。"""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


# preview contract 升級後 documents 必須存在的欄位。
REQUIRED_DOCUMENT_COLUMNS = frozenset({"display_text"})


def ensure_schema_compatibility(engine: Engine) -> None:
    """確認目前資料庫 schema 與 worker 程式碼相容。

    參數：
    - `engine`：目前 worker 使用的資料庫 engine。

    回傳：
    - `None`：若 schema 相容則不回傳任何值。

    風險：
    - 若資料庫尚未升級到目前程式碼需要的 schema，應在 worker 啟動時明確失敗，
      避免 task 執行到一半才以 SQL `UndefinedColumn` 中斷。
    """

    if engine.dialect.name == "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "documents" not in table_names:
        raise RuntimeError(
            "資料庫尚未初始化或 schema 不完整：缺少 `documents` 資料表。"
            "請先執行 migration runner；compose 環境可重新 `docker compose up`，"
            "非 compose 環境請在 `apps/api` 執行 `python -m app.db.migration_runner`。"
        )

    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    missing_columns = sorted(REQUIRED_DOCUMENT_COLUMNS - document_columns)
    if not missing_columns:
        return

    missing_label = ", ".join(f"`documents.{name}`" for name in missing_columns)
    raise RuntimeError(
        "資料庫 schema 與目前 worker 程式碼不相容，缺少欄位："
        f"{missing_label}。請先執行 migration runner；compose 環境可重新 "
        "`docker compose up` 讓 migration runner 自動補齊，非 compose 環境請在 "
        "`apps/api` 執行 `python -m app.db.migration_runner`。"
    )
