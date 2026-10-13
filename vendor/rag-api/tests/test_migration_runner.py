"""migration runner 設定測試。"""

from pathlib import Path

from app.db.migration_runner import build_alembic_config


def test_build_alembic_config_points_to_project_alembic_ini() -> None:
    """migration runner 應指向 `apps/api/alembic.ini`。

    Args:
        無。

    Returns:
        None: 驗證 Alembic 設定檔路徑。
    """

    config = build_alembic_config()

    assert config.config_file_name is not None
    assert Path(config.config_file_name).name == "alembic.ini"
    assert Path(config.config_file_name).resolve() == (Path(__file__).resolve().parents[1] / "alembic.ini").resolve()
