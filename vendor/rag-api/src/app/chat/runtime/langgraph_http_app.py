"""LangGraph Server 掛載的 FastAPI HTTP app 入口。"""

from __future__ import annotations

from app.core.settings import AppSettings
from app.main import create_app


def create_langgraph_http_app(settings: AppSettings | None = None):
    """建立 LangGraph Server 使用的 FastAPI app。"""

    return create_app(settings)


# 對外匯出的 LangGraph HTTP app。
app = create_langgraph_http_app()
