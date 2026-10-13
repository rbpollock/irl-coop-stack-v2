"""Area access-check API schema。"""

from uuid import UUID
from pydantic import BaseModel

from app.db.models import Role


class AreaAccessResponse(BaseModel):
    """Area access-check 的成功回應。"""

    model_config = {"from_attributes": True}

    area_id: UUID
    effective_role: Role
