"""Celery dispatch 輔助測試。"""

from app.services.tasks import (
    DEFAULT_TASK_QUEUE_NAME,
    INGEST_DOCUMENT_TASK_NAME,
    NoopCeleryClient,
    dispatch_document_ingest,
)


class CapturingCeleryClient:
    """記錄 `send_task` 呼叫內容的測試替身。"""

    def __init__(self) -> None:
        """初始化空的呼叫紀錄。"""

        self.calls: list[tuple[str, dict[str, object], str]] = []

    def send_task(self, name: str, kwargs: dict[str, object], queue: str) -> None:
        """保存 dispatch 呼叫參數供測試斷言。"""

        self.calls.append((name, dict(kwargs), queue))


def test_dispatch_document_ingest_sends_expected_task() -> None:
    """dispatch helper 應以固定 task name 與 queue 派送工作。"""

    celery_client = CapturingCeleryClient()

    dispatch_document_ingest(celery_client=celery_client, job_id="job-123")

    assert celery_client.calls == [
        (
            INGEST_DOCUMENT_TASK_NAME,
            {"job_id": "job-123", "force_reparse": False},
            DEFAULT_TASK_QUEUE_NAME,
        )
    ]


def test_dispatch_document_ingest_can_force_reparse() -> None:
    """dispatch helper 應可將 force_reparse 旗標傳給 worker。"""

    celery_client = CapturingCeleryClient()

    dispatch_document_ingest(celery_client=celery_client, job_id="job-123", force_reparse=True)

    assert celery_client.calls == [
        (
            INGEST_DOCUMENT_TASK_NAME,
            {"job_id": "job-123", "force_reparse": True},
            DEFAULT_TASK_QUEUE_NAME,
        )
    ]


def test_dispatch_document_ingest_raises_for_missing_celery_dependency() -> None:
    """缺少 celery 套件時應明確拒絕 dispatch。"""

    try:
        dispatch_document_ingest(celery_client=NoopCeleryClient(), job_id="job-123")
    except RuntimeError as exc:
        assert str(exc) == "目前環境缺少 celery 套件，無法派送背景 ingest task。"
    else:
        raise AssertionError("預期 dispatch_document_ingest() 會在缺少 celery 套件時拋出 RuntimeError。")
