from fastapi import APIRouter

router = APIRouter()

@router.get("/{project_id}")
async def get_handoff_package(project_id: str):
    return {"project_id": project_id, "handoff_data": {}}
