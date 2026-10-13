"""Alembic migration runner，負責將資料庫升級到目前 head。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from app.core.settings import get_settings


def build_alembic_config() -> Config:
    """建立 Alembic 設定物件。

    Args:
        無。

    Returns:
        Config: 指向專案 `alembic.ini` 的設定物件。
    """

    project_root = Path(__file__).resolve().parents[3]
    return Config(str(project_root / "alembic.ini"))


def run_migrations() -> None:
    """執行 migration，並將資料庫升級到目前 Alembic head。

    Args:
        無。

    Returns:
        None: 函式完成後會讓資料庫升級到目前 Alembic head。
    """

    settings = get_settings()
    alembic_config = build_alembic_config()
    engine = create_engine(settings.database_url, future=True)

    try:
        command.upgrade(alembic_config, "head")
    finally:
        engine.dispose()


def main() -> None:
    """提供 `python -m app.db.migration_runner` 的 CLI 入口。

    Args:
        無。

    Returns:
        None: 直接呼叫 migration 執行流程。
    """

    run_migrations()


if __name__ == "__main__":
    main()
