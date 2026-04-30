import shutil
from pathlib import Path
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.crud import projects as project_crud
from app.db.models import FileProcessingStatus
from app.db.session import get_db
from app.parsers.archive_handler import ArchiveHandler
from app.parsers.source_classifier import SourceClassifier
from app.schemas.project import ProjectCreate, ProjectFileRead, ProjectRead

router = APIRouter()


def _project_input_dir(project_id: UUID) -> Path:
    root = Path(settings.project_data_root)
    path = root / str(project_id) / "input"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_stored_name(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    return f"{uuid4()}{suffix}"


def _register_file(db: Session, project_id: UUID, file_path: Path, original_filename: str, parent_file_id: UUID | None = None):
    classification = SourceClassifier.classify_details(str(file_path))
    status_value = (
        FileProcessingStatus.UNSUPPORTED
        if classification.file_type.value == "UNKNOWN"
        else FileProcessingStatus.PENDING
    )
    return project_crud.create_project_file(
        db,
        project_id=project_id,
        original_filename=original_filename,
        stored_path=str(file_path),
        file_type=classification.file_type.value,
        file_category=classification.file_category,
        source_application=classification.source_application,
        likely_role=classification.likely_role,
        classification_confidence=classification.confidence,
        processing_status=status_value,
        parent_file_id=parent_file_id,
    )


@router.get("/", response_model=List[ProjectRead], summary="List all projects")
async def list_projects(db: Session = Depends(get_db)) -> List[ProjectRead]:
    return project_crud.list_projects(db)


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Create a new project")
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    return project_crud.create_project(db, project)


@router.post(
    "/{project_id}/files",
    response_model=List[ProjectFileRead],
    status_code=status.HTTP_201_CREATED,
    summary="Upload and register project files",
)
async def upload_project_files(
    project_id: UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> List[ProjectFileRead]:
    project = project_crud.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    input_dir = _project_input_dir(project_id)
    registered_files = []

    for upload in files:
        stored_path = input_dir / _safe_stored_name(upload.filename)
        with stored_path.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)

        parent_file = _register_file(db, project_id, stored_path, upload.filename)
        registered_files.append(parent_file)

        if parent_file.file_category == "archive":
            extract_dir = input_dir / f"{stored_path.stem}_extracted"
            extracted_paths = ArchiveHandler.extract(str(stored_path), str(extract_dir))
            for extracted_path in extracted_paths:
                extracted_file = Path(extracted_path)
                if extracted_file.is_file():
                    registered_files.append(
                        _register_file(
                            db,
                            project_id,
                            extracted_file,
                            extracted_file.name,
                            parent_file_id=parent_file.id,
                        )
                    )

    return registered_files
