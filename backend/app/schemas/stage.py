from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.db.models import StageStatus

class StageRead(BaseModel):
    id: UUID
    project_id: UUID
    stage_code: str
    status: StageStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    revision: int

    class Config:
        from_attributes = True

class StageApprove(BaseModel):
    approved_by: str
