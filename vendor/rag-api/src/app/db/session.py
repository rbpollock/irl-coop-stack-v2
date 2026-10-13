"""資料庫 engine 與 session dependency。"""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import AppSettings


def create_database_engine(settings: AppSettings) -> Engine:
    """建立資料庫 engine。

    參數：
    - `settings`：包含資料庫連線 URL 與 echo 選項的應用程式設定。

    回傳：
    - `Engine`：可供 session factory 與 migration 使用的 SQLAlchemy engine。

    前置條件：
    - `settings.database_url` 必須指向可連線的資料庫。

    風險：
    - SQLite 僅供測試；正式授權與 SQL gate 行為仍以 PostgreSQL 為目標環境。
    """

    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, echo=settings.database_echo, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """建立供 request-scoped session 使用的 factory。

    參數：
    - `engine`：已初始化完成的 SQLAlchemy engine。

    回傳：
    - `sessionmaker[Session]`：建立 request-scoped session 的 factory。
    """

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_database_session(request: Request) -> Generator[Session, None, None]:
    """提供 request-scoped SQLAlchemy session。

    參數：
    - `request`：目前 HTTP request；用來讀取 `app.state.session_factory`。

    回傳：
    - `Generator[Session, None, None]`：可供 dependency 注入使用的資料庫 session。

    前置條件：
    - `app.state.session_factory` 必須在 app 啟動時初始化。

    風險：
    - 若 route 繞過此 dependency 自行管理 session，可能破壞授權查詢的一致性。
    """

    session_factory: sessionmaker[Session] = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
