"""FastAPI 應用程式進入點。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.verifier import build_token_verifier
from app.core.settings import AppSettings, get_settings
from app.db.session import create_database_engine, create_session_factory
from app.db.schema_guard import ensure_schema_compatibility
from app.routes.areas import router as areas_router
from app.routes.auth import router as auth_router
from app.routes.directory import router as directory_router
from app.routes.documents import router as documents_router
from app.routes.evaluation import router as evaluation_router
from app.routes.jobs import router as jobs_router
from app.routes.mcp import router as mcp_router
from app.routes.root import router as root_router
from app.services.tasks import build_celery_client


@asynccontextmanager
async def _application_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """在 API 啟動時驗證資料庫 schema 相容性。"""

    ensure_schema_compatibility(application.state.engine)
    yield


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """建立並設定 FastAPI 應用程式實例。

    參數：
    - `settings`：可選的應用程式設定；未提供時會讀取預設環境設定。

    回傳：
    - `FastAPI`：已完成路由、資料庫與驗證器接線的應用程式實例。
    """

    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.service_name,
        version=resolved_settings.version,
        summary="MVP skeleton API for the Deep Agent RAG Stack.",
        lifespan=_application_lifespan,
    )
    application.state.settings = resolved_settings
    application.state.engine = create_database_engine(resolved_settings)
    application.state.session_factory = create_session_factory(application.state.engine)
    application.state.token_verifier = build_token_verifier(resolved_settings)
    application.state.celery_client = build_celery_client(resolved_settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in resolved_settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(root_router)
    application.include_router(auth_router)
    application.include_router(directory_router)
    application.include_router(areas_router)
    application.include_router(documents_router)
    application.include_router(evaluation_router)
    application.include_router(jobs_router)
    application.include_router(mcp_router)
    return application


app = create_app()
