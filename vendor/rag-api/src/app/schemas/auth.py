"""Auth 相關 API schema。"""

from pydantic import BaseModel


class AuthContextResponse(BaseModel):
    """目前使用者的最小 auth context。"""

    sub: str
    groups: list[str]
    authenticated: bool
    name: str | None = None
    preferred_username: str | None = None
