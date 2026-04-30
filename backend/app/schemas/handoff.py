from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class HandoffRead(BaseModel):
    id: UUID
    project_id: UUID
    from_stage: str
    to_stage: str
    package_path: Optional[str]
    approved: int
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class HandoffApprove(BaseModel):
    approved_by: str
    approved: int  # 1=approve, -1=reject
