"""Area chat session metadata API schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatSessionSummaryResponse(BaseModel):
    """單一 area chat session 摘要。"""

    model_config = {"from_attributes": True}

    id: UUID
    area_id: UUID
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    """指定 area 目前使用者可見的 chat session 清單。"""

    items: list[ChatSessionSummaryResponse]


class RegisterChatSessionRequest(BaseModel):
    """建立或註冊正式 chat session metadata 的 payload。"""

    thread_id: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)

    @field_validator("thread_id")
    @classmethod
    def validate_thread_id(cls, value: str | None) -> str | None:
        """若有提供 thread id，拒絕只有空白的值。"""

        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("thread_id 不可為空白。")
        return stripped

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        """將空白 title 正規化為空值。"""

        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class UpdateChatSessionRequest(BaseModel):
    """更新 chat session metadata 的 payload。"""

    title: str | None = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        """將空白 title 正規化為空值。"""

        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
