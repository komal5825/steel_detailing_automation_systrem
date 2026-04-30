import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.crud.stages import list_project_stages
from app.db.session import get_db
from app.orchestrator.dependency_checker import DependencyChecker

router = APIRouter()

@router.get("/dependencies/readiness")
async def get_dependency_readiness():
    return DependencyChecker().check_dependencies()

@router.get("/{project_id}/status")
async def get_stage_status(project_id: str, db: Session = Depends(get_db)):
    try:
        project_uuid = UUID(str(project_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    stages = list_project_stages(db, project_uuid)
    return {
        "project_id": project_id,
        "stages": [
            {
                "stage_code": stage.stage_code,
                "status": stage.status.value,
                "started_at": stage.started_at,
                "completed_at": stage.completed_at,
                "error_message": stage.error_message,
                "result": json.loads(stage.result_json or "{}"),
            }
            for stage in stages
        ],
    }

@router.post("/{project_id}/approve")
async def approve_stage(project_id: str, stage: str):
    return {"message": f"Stage {stage} approved for project {project_id}"}
