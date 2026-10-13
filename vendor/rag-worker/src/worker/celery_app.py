"""Worker 骨架的 Celery 應用程式進入點。"""

from worker.core.settings import get_settings
from worker.db import create_database_engine
from worker.schema_guard import ensure_schema_compatibility


class _FallbackCeleryApp:
    """在本機缺少 celery 套件時提供最小 task decorator。"""

    def task(self, name: str):
        """回傳不改動原函式的 decorator。

        參數：
        - `name`：原本要註冊的 task 名稱。

        回傳：
        - 可直接包裝函式的 decorator。
        """

        del name

        def decorator(function):
            return function

        return decorator


def create_celery_app():
    """建立並設定 Celery 應用程式實例。

    參數：
    - 無

    回傳：
    - `Celery`：已完成基本 queue 與 serializer 設定的 Celery 應用程式。
    """

    try:
        from celery import Celery
    except ModuleNotFoundError:
        return _FallbackCeleryApp()

    settings = get_settings()
    application = Celery(
        settings.service_name,
        broker=settings.broker_url,
        backend=settings.result_backend,
    )
    application.conf.update(
        task_default_queue="default",
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        task_acks_late=settings.task_acks_late,
        task_reject_on_worker_lost=settings.task_reject_on_worker_lost,
        worker_pool=settings.worker_pool,
        worker_concurrency=settings.worker_concurrency,
        worker_prefetch_multiplier=settings.worker_prefetch_multiplier,
        worker_max_tasks_per_child=settings.worker_max_tasks_per_child,
    )
    if settings.broker_url.startswith("filesystem://"):
        broker_path = settings.broker_path.resolve()
        inbound_path = (broker_path / "out").resolve()
        outbound_path = (broker_path / "in").resolve()
        processed_path = (broker_path / "processed").resolve()
        control_path = (broker_path / "control").resolve()
        inbound_path.mkdir(parents=True, exist_ok=True)
        outbound_path.mkdir(parents=True, exist_ok=True)
        processed_path.mkdir(parents=True, exist_ok=True)
        control_path.mkdir(parents=True, exist_ok=True)
        application.conf.broker_transport_options = {
            "data_folder_in": str(inbound_path),
            "data_folder_out": str(outbound_path),
            "processed_folder": str(processed_path),
            "control_folder": str(control_path),
            "store_processed": True,
        }
    application.autodiscover_tasks(["worker.tasks"])

    from celery.signals import worker_init

    @worker_init.connect
    def verify_database_schema(**_: object) -> None:
        """在 worker 啟動時確認資料庫 schema 與目前程式碼相容。"""

        ensure_schema_compatibility(create_database_engine(settings))

    return application


celery_app = create_celery_app()
