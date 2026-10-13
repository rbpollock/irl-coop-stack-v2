"""API 端 Celery dispatch 輔助。"""
from typing import Any

from fastapi import Request

from app.core.settings import AppSettings


# Documents ingest task 的固定名稱。
INGEST_DOCUMENT_TASK_NAME = "worker.tasks.ingest.process_document_ingest"

# API 與 worker 共用的 Celery queue 名稱。
DEFAULT_TASK_QUEUE_NAME = "default"


class NoopCeleryClient:
    """在缺少 celery 套件時提供一致失敗語意的最小 client。"""

    # 標記目前 client 僅供缺少 celery 套件時佔位使用。
    missing_dependency = True

    def send_task(self, name: str, kwargs: dict[str, object], queue: str) -> None:
        """保留 Celery 介面形狀，實際 dispatch 會由呼叫端拒絕。

        參數：
        - `name`：原本要送出的 task 名稱。
        - `kwargs`：原本要送出的 task kwargs。
        - `queue`：原本要使用的 queue 名稱。

        回傳：
        - `None`：此方法只保留相容介面。
        """

        del name, kwargs, queue


def build_celery_client(settings: AppSettings) -> Any:
    """建立 API 用 Celery client。

    參數：
    - `settings`：包含 Celery broker 與 result backend 設定的應用程式設定。

    回傳：
    - `Celery`：供 API 派送背景任務使用的 Celery client。
    """

    try:
        from celery import Celery
    except ModuleNotFoundError:
        return NoopCeleryClient()

    client = Celery(
        f"{settings.service_name}-producer",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    client.conf.update(task_default_queue=DEFAULT_TASK_QUEUE_NAME)
    if settings.celery_broker_url.startswith("filesystem://"):
        broker_path = settings.celery_broker_path.resolve()
        inbound_path = (broker_path / "in").resolve()
        outbound_path = (broker_path / "out").resolve()
        processed_path = (broker_path / "processed").resolve()
        control_path = (broker_path / "control").resolve()
        inbound_path.mkdir(parents=True, exist_ok=True)
        outbound_path.mkdir(parents=True, exist_ok=True)
        processed_path.mkdir(parents=True, exist_ok=True)
        control_path.mkdir(parents=True, exist_ok=True)
        client.conf.broker_transport_options = {
            "data_folder_in": str(inbound_path),
            "data_folder_out": str(outbound_path),
            "processed_folder": str(processed_path),
            "control_folder": str(control_path),
            "store_processed": True,
        }
    return client


def get_celery_client(request: Request) -> Any:
    """從應用程式狀態讀取 Celery client。

    參數：
    - `request`：目前 HTTP request；用來讀取 `app.state.celery_client`。

    回傳：
    - `Celery`：目前應用程式使用的 Celery client。
    """

    return request.app.state.celery_client


def dispatch_document_ingest(celery_client: Any, *, job_id: str, force_reparse: bool = False) -> None:
    """派送文件 ingest task。

    參數：
    - `celery_client`：用來送出背景任務的 Celery client。
    - `job_id`：要處理的 ingest job 識別碼。
    - `force_reparse`：若為真，worker 需忽略既有 parse artifacts 並重跑 parser。

    回傳：
    - `None`：此函式只負責送出任務，不回傳業務資料。
    """

    if getattr(celery_client, "missing_dependency", False):
        raise RuntimeError("目前環境缺少 celery 套件，無法派送背景 ingest task。")

    celery_client.send_task(
        INGEST_DOCUMENT_TASK_NAME,
        kwargs={"job_id": str(job_id), "force_reparse": force_reparse},
        queue=DEFAULT_TASK_QUEUE_NAME,
    )
