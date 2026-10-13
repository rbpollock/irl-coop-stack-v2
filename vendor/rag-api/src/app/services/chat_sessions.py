"""Area chat session metadata service 與 LangGraph thread 驗證。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from fastapi import HTTPException, status
from langgraph_sdk import get_client
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import AreaChatSession
from app.schemas.chat_sessions import ChatSessionSummaryResponse
from app.services.access import require_area_access


# 新建 session 的預設標題。
DEFAULT_CHAT_SESSION_TITLE = "新對話"
# 模組 logger，保留 thread 驗證降級原因。
logger = logging.getLogger(__name__)


class LangGraphThreadNotVerifiableError(RuntimeError):
    """代表目前無法可靠驗證 LangGraph thread metadata。"""


@dataclass(frozen=True, slots=True)
class LangGraphThreadMetadata:
    """驗證後可安全使用的 LangGraph thread metadata。"""

    thread_id: str
    owner_sub: str
    area_id: str


def list_area_chat_sessions(
    session: Session,
    principal: CurrentPrincipal,
    *,
    area_id: str,
) -> list[ChatSessionSummaryResponse]:
    """列出指定 area 且屬於目前使用者的 chat sessions。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area 識別碼。

    回傳：
    - `list[ChatSessionSummaryResponse]`：依最近使用時間排序的 chat sessions。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    rows = session.scalars(
        select(AreaChatSession)
        .where(AreaChatSession.area_id == area_id, AreaChatSession.owner_sub == principal.sub)
        .order_by(AreaChatSession.updated_at.desc(), AreaChatSession.created_at.desc())
    ).all()
    return [build_chat_session_summary(row) for row in rows]


def register_area_chat_session(
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    *,
    area_id: str,
    bearer_token: str,
    thread_id: str | None,
    title: str | None,
) -> ChatSessionSummaryResponse:
    """註冊既有 LangGraph thread 為正式 chat session metadata。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：目前 API 設定。
    - `area_id`：目標 area 識別碼。
    - `bearer_token`：目前 request 的 Bearer token。
    - `thread_id`：要註冊的 LangGraph thread id。
    - `title`：可選的 session 標題。

    回傳：
    - `ChatSessionSummaryResponse`：建立或既有的 session 摘要。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    resolved_thread_id = thread_id
    if resolved_thread_id is None:
        resolved_thread_id = create_langgraph_thread(
            settings=settings,
            bearer_token=bearer_token,
            area_id=area_id,
        )
        thread_metadata = LangGraphThreadMetadata(
            thread_id=resolved_thread_id,
            owner_sub=principal.sub,
            area_id=area_id,
        )
    else:
        thread_metadata = validate_langgraph_thread_access(
            settings=settings,
            bearer_token=bearer_token,
            principal=principal,
            area_id=area_id,
            thread_id=resolved_thread_id,
        )

    existing = session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == resolved_thread_id))
    if existing is not None:
        if existing.owner_sub != principal.sub or existing.area_id != area_id:
            raise _build_chat_session_not_found_error()
        return build_chat_session_summary(existing)

    chat_session = AreaChatSession(
        area_id=area_id,
        owner_sub=principal.sub,
        thread_id=resolved_thread_id,
        title=_resolve_chat_session_title(title),
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return build_chat_session_summary(chat_session)


def update_area_chat_session(
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    *,
    area_id: str,
    bearer_token: str,
    thread_id: str,
    title: str | None,
) -> ChatSessionSummaryResponse:
    """更新既有 chat session metadata。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：目前 API 設定。
    - `area_id`：目標 area 識別碼。
    - `bearer_token`：目前 request 的 Bearer token。
    - `thread_id`：要更新的 LangGraph thread id。
    - `title`：可選的新標題；若為空則只 touch `updated_at`。

    回傳：
    - `ChatSessionSummaryResponse`：更新後的 session 摘要。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    chat_session = session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == thread_id))
    if chat_session is not None and (chat_session.owner_sub != principal.sub or chat_session.area_id != area_id):
        raise _build_chat_session_not_found_error()

    if chat_session is None:
        thread_metadata = validate_langgraph_thread_access(
            settings=settings,
            bearer_token=bearer_token,
            principal=principal,
            area_id=area_id,
            thread_id=thread_id,
        )
        resolved_thread_id = thread_metadata.thread_id if thread_metadata is not None else thread_id
        chat_session = AreaChatSession(
            area_id=area_id,
            owner_sub=principal.sub,
            thread_id=resolved_thread_id,
            title=_resolve_chat_session_title(title),
        )
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return build_chat_session_summary(chat_session)

    if title is not None:
        chat_session.title = _resolve_chat_session_title(title)
    session.commit()
    session.refresh(chat_session)
    return build_chat_session_summary(chat_session)


def delete_area_chat_session(
    session: Session,
    principal: CurrentPrincipal,
    *,
    area_id: str,
    thread_id: str,
) -> None:
    """刪除指定 area 中屬於目前使用者的 chat session metadata。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area 識別碼。
    - `thread_id`：要刪除的 LangGraph thread id。

    回傳：
    - `None`：成功時僅完成刪除。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    chat_session = session.scalar(select(AreaChatSession).where(AreaChatSession.thread_id == thread_id))
    if chat_session is None or chat_session.owner_sub != principal.sub or chat_session.area_id != area_id:
        raise _build_chat_session_not_found_error()

    session.delete(chat_session)
    session.commit()


def build_chat_session_summary(chat_session: AreaChatSession) -> ChatSessionSummaryResponse:
    """將 ORM model 轉為 API summary。

    參數：
    - `chat_session`：已持久化的 chat session model。

    回傳：
    - `ChatSessionSummaryResponse`：可直接回傳給 API 的摘要。
    """

    return ChatSessionSummaryResponse.model_validate(chat_session)


def validate_langgraph_thread_access(
    *,
    settings: AppSettings,
    bearer_token: str,
    principal: CurrentPrincipal,
    area_id: str,
    thread_id: str,
) -> LangGraphThreadMetadata | None:
    """驗證指定 LangGraph thread 是否屬於目前使用者與 area。

    參數：
    - `settings`：目前 API 設定。
    - `bearer_token`：目前 request 的 Bearer token。
    - `principal`：目前已驗證使用者。
    - `area_id`：預期 thread 所屬 area。
    - `thread_id`：要驗證的 thread 識別碼。

    回傳：
    - `LangGraphThreadMetadata`：驗證後可安全使用的 thread metadata。
    """

    try:
        thread_payload = asyncio.run(
            _fetch_langgraph_thread(
                settings=settings,
                bearer_token=bearer_token,
                thread_id=thread_id,
            )
        )
    except LangGraphThreadNotVerifiableError:
        logger.warning(
            "LangGraph thread metadata is temporarily unverifiable; allowing chat session metadata fallback. area_id=%s thread_id=%s principal_sub=%s",
            area_id,
            thread_id,
            principal.sub,
        )
        return None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="目前無法驗證 chat session 狀態，請稍後再試。",
        ) from exc

    metadata = thread_payload.get("metadata") if isinstance(thread_payload.get("metadata"), dict) else {}
    owner_sub = metadata.get("owner")
    metadata_area_id = metadata.get("area_id")
    if owner_sub != principal.sub or metadata_area_id != area_id:
        raise _build_chat_session_not_found_error()

    return LangGraphThreadMetadata(thread_id=thread_id, owner_sub=owner_sub, area_id=metadata_area_id)


def create_langgraph_thread(
    *,
    settings: AppSettings,
    bearer_token: str,
    area_id: str,
) -> str:
    """在後端直接建立 LangGraph thread，避免前端先建 thread 再回寫 metadata 的競態。

    參數：
    - `settings`：目前 API 設定。
    - `bearer_token`：目前 request 的 Bearer token。
    - `area_id`：thread 所屬 area。

    回傳：
    - `str`：新建立的 LangGraph thread id。
    """

    try:
        return asyncio.run(
            _create_langgraph_thread(
                settings=settings,
                bearer_token=bearer_token,
                area_id=area_id,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="目前無法建立 chat session，請稍後再試。",
        ) from exc


async def _fetch_langgraph_thread(
    *,
    settings: AppSettings,
    bearer_token: str,
    thread_id: str,
) -> dict[str, object]:
    """透過 LangGraph SDK 讀取 thread metadata。

    參數：
    - `settings`：目前 API 設定。
    - `bearer_token`：目前 request 的 Bearer token。
    - `thread_id`：目標 thread 識別碼。

    回傳：
    - `dict[str, object]`：LangGraph SDK 回傳的 thread payload。
    """

    client = get_client(url=settings.langgraph_api_url)
    try:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                thread = await client.threads.get(
                    thread_id,
                    headers={
                        "Authorization": f"Bearer {bearer_token}",
                    },
                )
                return dict(thread)
            except Exception as exc:
                last_error = exc
                error_message = str(exc)
                if "404" in error_message or "not found" in error_message.lower():
                    if attempt < 2:
                        await asyncio.sleep(0.15 * (attempt + 1))
                        continue
                    raise LangGraphThreadNotVerifiableError("thread not found during validation") from exc
                raise
        raise LangGraphThreadNotVerifiableError("thread metadata could not be verified") from last_error
    finally:
        await client.aclose()


async def _create_langgraph_thread(
    *,
    settings: AppSettings,
    bearer_token: str,
    area_id: str,
) -> str:
    """透過 LangGraph SDK 建立 thread。"""

    client = get_client(url=settings.langgraph_api_url)
    try:
        thread = await client.threads.create(
            metadata={
                "area_id": area_id,
            },
            headers={
                "Authorization": f"Bearer {bearer_token}",
            },
        )
    finally:
        await client.aclose()

    thread_id = thread.get("thread_id") if isinstance(thread, dict) else getattr(thread, "thread_id", None)
    if not isinstance(thread_id, str) or not thread_id:
        raise RuntimeError("LangGraph thread 建立成功，但缺少 thread_id。")
    return thread_id


def _resolve_chat_session_title(title: str | None) -> str:
    """正規化 chat session 標題。

    參數：
    - `title`：原始標題。

    回傳：
    - `str`：可持久化的標題。
    """

    if title is None:
        return DEFAULT_CHAT_SESSION_TITLE
    stripped = title.strip()
    return stripped or DEFAULT_CHAT_SESSION_TITLE


def _build_chat_session_not_found_error() -> HTTPException:
    """建立統一的 same-404 錯誤。"""

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 area chat session。")
