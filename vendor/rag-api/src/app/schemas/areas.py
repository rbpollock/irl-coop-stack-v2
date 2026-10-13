"""Knowledge Area CRUD 與 access management API schema。"""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models import Role


class CreateAreaRequest(BaseModel):
    """建立 Knowledge Area 的請求 payload。"""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """拒絕只有空白的 area 名稱。"""

        stripped = value.strip()
        if not stripped:
            raise ValueError("area 名稱不可為空白。")
        return stripped


class UpdateAreaRequest(BaseModel):
    """更新 Knowledge Area 的請求 payload。"""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """拒絕只有空白的 area 名稱。"""

        stripped = value.strip()
        if not stripped:
            raise ValueError("area 名稱不可為空白。")
        return stripped


class AreaSummaryResponse(BaseModel):
    """Area list 與 detail 共用的最小 area 表示。"""

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str | None
    effective_role: Role
    created_at: datetime
    updated_at: datetime


class AreaListResponse(BaseModel):
    """目前使用者可存取的 area 清單。"""

    items: list[AreaSummaryResponse]


class AccessUserEntry(BaseModel):
    """Area direct user role 映射。"""

    username: str = Field(min_length=1, max_length=255)
    role: Role

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """拒絕只有空白的 username。"""

        stripped = value.strip()
        if not stripped:
            raise ValueError("username 不可為空白。")
        return stripped


class AccessGroupEntry(BaseModel):
    """Area group role 映射。"""

    group_path: str = Field(min_length=1, max_length=255)
    role: Role

    @field_validator("group_path")
    @classmethod
    def validate_group_path(cls, value: str) -> str:
        """拒絕只有空白的 group_path。"""

        stripped = value.strip()
        if not stripped:
            raise ValueError("group_path 不可為空白。")
        return stripped


class AreaAccessManagementResponse(BaseModel):
    """Area access 管理內容。"""

    model_config = {"from_attributes": True}

    area_id: UUID
    users: list[AccessUserEntry]
    groups: list[AccessGroupEntry]


class ReplaceAreaAccessRequest(BaseModel):
    """整體替換 area access 規則的請求 payload。"""

    users: list[AccessUserEntry] = Field(default_factory=list)
    groups: list[AccessGroupEntry] = Field(default_factory=list)
