from fastapi import APIRouter
from app.orchestrator.handoff_manager import HandoffManager

router = APIRouter()

@router.get("/{project_id}")
async def get_handoff_package(project_id: str):
    return HandoffManager().prepare_handoff(project_id)
