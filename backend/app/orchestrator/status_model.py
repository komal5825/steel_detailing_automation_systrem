from pydantic import BaseModel
from typing import List, Optional

class StageStatus(BaseModel):
    stage_name: str
    status: str
    progress: float
    message: Optional[str] = None

class ProjectStatus(BaseModel):
    project_id: str
    current_stage: str
    stages: List[StageStatus]
