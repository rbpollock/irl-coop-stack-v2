"""Auth 相關路由。"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.schemas.auth import AuthContextResponse


# Auth 基礎能力路由集合。
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/context", response_model=AuthContextResponse)
def read_auth_context(principal: CurrentPrincipal = Depends(get_current_principal)) -> AuthContextResponse:
    """回傳已驗證使用者的最小 auth context。"""

    return AuthContextResponse(
        sub=principal.sub,
        groups=list(principal.groups),
        authenticated=principal.authenticated,
        name=principal.name,
        preferred_username=principal.preferred_username,
    )
