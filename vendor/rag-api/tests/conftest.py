"""API 測試共用 fixtures。"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.db.base import Base
from app.chat.runtime.langgraph_http_app import create_langgraph_http_app


@dataclass
class FakeCeleryClient:
    """供 API 測試觀察 dispatch 呼叫的 Celery client 替身。"""

    # 記錄每次 `send_task` 呼叫內容。
    calls: list[tuple[str, dict[str, object], str]] = field(default_factory=list)

    def send_task(self, name: str, kwargs: dict[str, object], queue: str) -> None:
        """保存 dispatch 呼叫參數供測試斷言。"""

        self.calls.append((name, dict(kwargs), queue))


@pytest.fixture()
def app_settings(tmp_path: Path) -> AppSettings:
    """建立測試專用設定。

    參數：
    - `tmp_path`：pytest 提供的暫存目錄。

    回傳：
    - `AppSettings`：供 API 測試使用的設定物件。
    """

    database_path = tmp_path / "test.db"
    return AppSettings(
        API_SERVICE_NAME="deep-agent-api-test",
        API_VERSION="0.1.0-test",
        API_HOST="127.0.0.1",
        API_PORT=18000,
        API_CORS_ORIGINS="http://localhost:13000",
        DATABASE_URL=f"sqlite+pysqlite:///{database_path}",
        DATABASE_ECHO=False,
        REDIS_URL="redis://redis:6379/0",
        STORAGE_BACKEND="filesystem",
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_ACCESS_KEY="minio",
        MINIO_SECRET_KEY="minio123",
        MINIO_BUCKET="documents",
        LOCAL_STORAGE_PATH=tmp_path / "storage",
        MAX_UPLOAD_SIZE_BYTES=1024,
        CHUNK_MIN_PARENT_SECTION_LENGTH=800,
        CHUNK_TARGET_CHILD_SIZE=800,
        CHUNK_CHILD_OVERLAP=120,
        CHUNK_CONTENT_PREVIEW_LENGTH=120,
        CHUNK_TXT_PARENT_GROUP_SIZE=4,
        CHUNK_TABLE_PRESERVE_MAX_CHARS=4000,
        CHUNK_TABLE_MAX_ROWS_PER_CHILD=20,
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/1",
        EMBEDDING_PROVIDER="deterministic",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS=1536,
        RETRIEVAL_VECTOR_TOP_K=8,
        RETRIEVAL_FTS_TOP_K=8,
        RETRIEVAL_MAX_CANDIDATES=12,
        RETRIEVAL_RRF_K=60,
        RETRIEVAL_HNSW_EF_SEARCH=100,
        RERANK_PROVIDER="deterministic",
        RERANK_MODEL="rerank-v3.5",
        COHERE_API_KEY=None,
        RERANK_TOP_N=6,
        RERANK_MAX_CHARS_PER_DOC=2000,
        ASSEMBLER_MAX_CONTEXTS=6,
        ASSEMBLER_MAX_CHARS_PER_CONTEXT=2500,
        ASSEMBLER_MAX_CHILDREN_PER_PARENT=3,
        CHAT_PROVIDER="deterministic",
        CHAT_MODEL="deterministic-chat",
        CHAT_MAX_OUTPUT_TOKENS=700,
        CHAT_TIMEOUT_SECONDS=30,
        CHAT_INCLUDE_TRACE=True,
        CHAT_STREAM_CHUNK_SIZE=24,
        LANGGRAPH_SERVICE_PORT=18000,
        LANGGRAPH_API_URL="http://127.0.0.1:18000",
        KEYCLOAK_URL="http://keycloak:8080",
        KEYCLOAK_ISSUER="http://localhost:18080/realms/deep-agent-dev",
        KEYCLOAK_JWKS_URL="http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs",
        KEYCLOAK_GROUPS_CLAIM="groups",
        AUTH_TEST_MODE=True,
    )


@pytest.fixture()
def celery_client() -> FakeCeleryClient:
    """建立可觀察 dispatch 呼叫的 Celery client 替身。"""

    return FakeCeleryClient()


@pytest.fixture()
def app(app_settings: AppSettings, celery_client: FakeCeleryClient):
    """建立測試用 FastAPI 應用程式並初始化資料表。

    參數：
    - `app_settings`：測試專用應用程式設定。

    回傳：
    - 測試用 `FastAPI` 應用程式 fixture。
    """

    application = create_langgraph_http_app(app_settings)
    Base.metadata.create_all(bind=application.state.engine)
    application.state.celery_client = celery_client
    try:
        yield application
    finally:
        Base.metadata.drop_all(bind=application.state.engine)
        application.state.engine.dispose()


@pytest.fixture()
def client(app) -> Iterator[TestClient]:
    """建立測試用 TestClient。

    參數：
    - `app`：測試用 FastAPI 應用程式。

    回傳：
    - `Iterator[TestClient]`：供測試發送 HTTP 請求的 client fixture。
    """

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(app) -> Iterator[Session]:
    """提供測試用資料庫 session。

    參數：
    - `app`：測試用 FastAPI 應用程式。

    回傳：
    - `Iterator[Session]`：供測試直接操作資料庫的 session fixture。
    """

    session_factory = app.state.session_factory
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()
