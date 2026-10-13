"""Directory (User/Group) 搜尋相關的 API schema。"""

from pydantic import BaseModel


class UserSearchResult(BaseModel):
    """使用者搜尋結果。"""

    username: str
    email: str | None = None
    firstName: str | None = None
    lastName: str | None = None


class GroupSearchResult(BaseModel):
    """群組搜尋結果。"""

    path: str
    name: str
