from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.db.models import FileProcessingStatus, ProjectStatus

class ProjectCreate(BaseModel):
    proposal_id: str
    name: str
    location: Optional[str] = None
    project_type: Optional[str] = None

class ProjectRead(BaseModel):
    id: UUID
    proposal_id: str
    name: str
    location: Optional[str]
    project_type: Optional[str]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectFileRead(BaseModel):
    id: UUID
    project_id: UUID
    original_filename: str
    stored_path: str
    file_extension: Optional[str]
    file_type: str
    file_category: str
    source_application: str
    likely_role: str
    classification_confidence: int
    processing_status: FileProcessingStatus
    parent_file_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True
