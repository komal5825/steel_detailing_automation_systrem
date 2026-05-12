import logging
import shutil
import traceback
from pathlib import Path
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.crud import projects as project_crud
from app.db.crud.stages import list_project_stages, reset_all_stages
from app.db.models import FileProcessingStatus
from app.db.session import get_db
from app.orchestrator.controller import broadcast_stage_update
from app.parsers.archive_handler import ArchiveHandler
from app.parsers.source_classifier import SourceClassifier
from app.schemas.project import ProjectCreate, ProjectFileRead, ProjectRead

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.get("/{project_id}", response_model=ProjectRead, summary="Get a project")
async def get_project(project_id: UUID, db: Session = Depends(get_db)) -> ProjectRead:
    project = project_crud.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Create a new project")
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    existing = project_crud.get_project_by_proposal_id(db, project.proposal_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project with proposal ID '{project.proposal_id}' already exists.",
        )
    return project_crud.create_project(db, project)


@router.get("/{project_id}/files", response_model=List[ProjectFileRead], summary="List project files")
async def list_project_files(project_id: UUID, db: Session = Depends(get_db)) -> List[ProjectFileRead]:
    project = project_crud.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_crud.list_project_files(db, project_id)


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
    if not files:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No files received",
                "root_cause": "Multipart payload did not include any 'files'.",
                "stage": "upload_intake",
                "suggested_fix": "Attach one or more supported files and retry.",
            },
        )

    registered_files = []
    try:
        # Full reset guarantees fresh execution even for same-file re-upload.
        reset_all_stages(db, project_id)
        db.flush()
        for stage in list_project_stages(db, project_id):
            broadcast_stage_update(project_id, stage.stage_code, "PENDING")

        input_dir = _project_input_dir(project_id)

        for upload in files:
            if not upload.filename:
                raise ValueError("Encountered uploaded item without filename")

            stored_path = input_dir / _safe_stored_name(upload.filename)
            with stored_path.open("wb") as buffer:
                shutil.copyfileobj(upload.file, buffer)

            parent_file = _register_file(db, project_id, stored_path, upload.filename)
            registered_files.append(parent_file)

            if parent_file.file_category == "archive":
                extract_dir = input_dir / f"{stored_path.stem}_extracted"
                extracted_paths = ArchiveHandler.extract(str(stored_path), str(extract_dir))
                parent_file.processing_status = FileProcessingStatus.EXTRACTED
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

        db.commit()
        return registered_files
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            "Upload failed project=%s files=%s: %s\n%s",
            project_id,
            [getattr(f, "filename", None) for f in files],
            exc,
            traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Upload pipeline failed",
                "root_cause": str(exc),
                "stage": "project_upload",
                "suggested_fix": "Verify file integrity and retry upload.",
                "input_payload": {
                    "project_id": str(project_id),
                    "file_count": len(files),
                    "filenames": [getattr(f, "filename", None) for f in files],
                },
            },
        ) from exc


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a project file")
async def delete_file(project_id: UUID, file_id: UUID, db: Session = Depends(get_db)):
    file_record = db.query(project_crud.ProjectFile).filter(
        project_crud.ProjectFile.id == file_id,
        project_crud.ProjectFile.project_id == project_id
    ).first()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    stored_path = Path(file_record.stored_path)
    if stored_path.exists():
        stored_path.unlink()

    project_crud.delete_project_file(db, file_id)

    reset_all_stages(db, project_id)
    db.flush()
    for stage in list_project_stages(db, project_id):
        broadcast_stage_update(project_id, stage.stage_code, "PENDING")

    db.commit()
    return None
