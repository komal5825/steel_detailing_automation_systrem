from fastapi import APIRouter

router = APIRouter()

@router.get("/{project_id}/status")
async def get_stage_status(project_id: str):
    return {"project_id": project_id, "stages": []}

@router.post("/{project_id}/approve")
async def approve_stage(project_id: str, stage: str):
    return {"message": f"Stage {stage} approved for project {project_id}"}
