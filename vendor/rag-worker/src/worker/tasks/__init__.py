"""Celery 骨架 worker 的 task 模組。"""

from worker.tasks.health import ping
from worker.tasks.ingest import process_document_ingest

__all__ = ["ping", "process_document_ingest"]
