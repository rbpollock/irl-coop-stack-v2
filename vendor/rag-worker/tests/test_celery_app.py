"""Celery 應用程式設定測試。"""

from worker.celery_app import create_celery_app


def test_create_celery_app_enforces_single_in_flight_task(monkeypatch) -> None:
    """worker 應限制同時間只有一個已接收但未完成的 ingest 案件。"""

    monkeypatch.setenv("CELERY_WORKER_POOL", "solo")
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "1")
    monkeypatch.setenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")
    monkeypatch.setenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "1")
    monkeypatch.setenv("CELERY_TASK_ACKS_LATE", "true")
    monkeypatch.setenv("CELERY_TASK_REJECT_ON_WORKER_LOST", "true")

    celery_app = create_celery_app()

    assert celery_app.conf.worker_pool == "solo"
    assert celery_app.conf.worker_concurrency == 1
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
