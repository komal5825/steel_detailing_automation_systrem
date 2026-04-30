from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class ValidationItem(BaseModel):
    field_code: str
    status: str        # PRESENT / MISSING / SUSPICIOUS
    severity: str      # CRITICAL / MAJOR / MINOR
    source: Optional[str]
    value: Optional[str]
    note: Optional[str]

class ValidationReport(BaseModel):
    project_id: UUID
    stage_code: str
    generated_at: datetime
    items: List[ValidationItem]
    overall: str       # PASS / FAIL

    class Config:
        from_attributes = True
