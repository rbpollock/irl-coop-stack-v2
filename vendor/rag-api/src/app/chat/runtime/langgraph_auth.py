"""LangGraph Server 的 custom authentication handler。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph_sdk import Auth
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.verifier import (
    AuthServiceUnavailableError,
    InvalidTokenError,
    TokenVerifier,
    build_token_verifier,
)
from app.core.settings import get_settings


# 模組層級 logger，用來保留 LangGraph auth 驗證失敗原因。
logger = logging.getLogger(__name__)

# LangGraph custom auth 實例。
auth = Auth()

# LangGraph auth 共用的設定物件。
AUTH_SETTINGS = get_settings()

# LangGraph auth 共用的 token verifier，避免每個 request 都重建 JWKS client。
AUTH_TOKEN_VERIFIER: TokenVerifier = build_token_verifier(AUTH_SETTINGS)

@auth.authenticate
async def authenticate(authorization: str | None = None) -> Auth.types.MinimalUserDict:
    """驗證 Bearer token 並回傳 LangGraph user payload。"""

    if authorization is None or not authorization.startswith("Bearer "):
        raise auth.exceptions.HTTPException(status_code=401, detail="缺少有效的 Bearer token。")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise auth.exceptions.HTTPException(status_code=401, detail="缺少有效的 Bearer token。")

    try:
        # PyJWT 的 JWKS client 仍使用同步網路呼叫；在 LangGraph ASGI runtime 需移到 thread，
        # 否則會被 blocking-call guard 擋下，導致 built-in thread/run routes 回 500。
        principal = await asyncio.to_thread(AUTH_TOKEN_VERIFIER.verify, token)
    except InvalidTokenError as exc:
        logger.warning("LangGraph Bearer token verification failed: %s", exc)
        raise auth.exceptions.HTTPException(status_code=401, detail="無法驗證存取 token。") from exc
    except AuthServiceUnavailableError as exc:
        logger.exception("LangGraph token verification service unavailable.")
        raise StarletteHTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "identity": principal.sub,
        "sub": principal.sub,
        "groups": list(principal.groups),
    }


@auth.on.threads.create
async def authorize_thread_create(ctx: Auth.types.AuthContext, value: Auth.on.threads.create.value) -> None:
    """在 thread 建立時寫入 owner 與 area metadata。"""

    metadata = dict(value.get("metadata") or {})
    metadata["owner"] = ctx.user.identity
    value["metadata"] = metadata


@auth.on.threads.create_run
async def authorize_thread_create_run(ctx: Auth.types.AuthContext, value: Auth.on.threads.create_run.value) -> None:
    """在 create_run 時把已驗證 principal 注入 graph input。"""

    kwargs_payload = value.get("kwargs")
    if not isinstance(kwargs_payload, dict):
        raise auth.exceptions.HTTPException(status_code=400, detail="LangGraph run input 必須為 JSON object。")
    input_payload = kwargs_payload.get("input")
    if not isinstance(input_payload, dict):
        raise auth.exceptions.HTTPException(status_code=400, detail="LangGraph run input 必須為 JSON object。")

    principal_payload: dict[str, Any] = {
        "sub": ctx.user.identity,
        "groups": list(ctx.user.get("groups", [])),
        "authenticated": True,
    }
    input_payload["principal"] = principal_payload
    kwargs_payload["input"] = input_payload
    value["kwargs"] = kwargs_payload
