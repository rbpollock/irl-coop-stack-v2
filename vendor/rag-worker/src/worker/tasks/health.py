"""Celery 骨架 worker 的最小健康檢查與 smoke test task。"""

from worker.celery_app import celery_app


@celery_app.task(name="worker.tasks.health.ping")
def ping() -> str:
    """回傳簡單字串，證明 worker 可以執行 task。"""

    return "pong"
