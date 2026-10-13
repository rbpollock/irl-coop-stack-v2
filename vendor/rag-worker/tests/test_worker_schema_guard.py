"""Worker schema 相容性檢查測試。"""

from sqlalchemy import create_engine

from worker.schema_guard import ensure_schema_compatibility


def test_ensure_schema_compatibility_skips_sqlite() -> None:
    """SQLite 測試資料庫不應觸發正式 schema guard。"""

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    ensure_schema_compatibility(engine)
