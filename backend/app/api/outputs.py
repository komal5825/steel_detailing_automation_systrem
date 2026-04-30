from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/{project_id}/files")
async def list_output_files(project_id: str):
    return {"project_id": project_id, "files": []}

@router.get("/{project_id}/download/{file_name}")
async def download_output_file(project_id: str, file_name: str):
    return {"message": "Download logic goes here"}
