from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.config.constants import StageCode
from app.db.models import FileProcessingStatus, Project, ProjectFile, Stage, StageStatus
from app.schemas.project import ProjectCreate


PHASE2_STAGE_CODES = [
    StageCode.P2_01.value,
    StageCode.P2_02.value,
    StageCode.P2_03.value,
    StageCode.P2_04.value,
    StageCode.P2_05.value,
]


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).order_by(Project.created_at.desc()).all()


def get_project(db: Session, project_id: UUID) -> Project | None:
    return db.query(Project).filter(Project.id == project_id).first()


def get_project_by_proposal_id(db: Session, proposal_id: str) -> Project | None:
    return db.query(Project).filter(Project.proposal_id == proposal_id).first()


def list_project_files(db: Session, project_id: UUID) -> list[ProjectFile]:
    return (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project_id)
        .order_by(ProjectFile.created_at.asc(), ProjectFile.original_filename.asc())
        .all()
    )


def create_project(db: Session, payload: ProjectCreate) -> Project:
    project = Project(
        proposal_id=payload.proposal_id,
        name=payload.name,
        location=payload.location,
        project_type=payload.project_type,
    )
    db.add(project)
    db.flush()

    for stage_code in PHASE2_STAGE_CODES:
        db.add(
            Stage(
                project_id=project.id,
                stage_code=stage_code,
                status=StageStatus.PENDING,
            )
        )

    db.commit()
    db.refresh(project)
    return project


def create_project_file(
    db: Session,
    *,
    project_id: UUID,
    original_filename: str,
    stored_path: str,
    file_type: str,
    file_category: str,
    source_application: str,
    likely_role: str,
    classification_confidence: int,
    processing_status: FileProcessingStatus = FileProcessingStatus.PENDING,
    parent_file_id: UUID | None = None,
) -> ProjectFile:
    project_file = ProjectFile(
        project_id=project_id,
        original_filename=original_filename,
        stored_path=stored_path,
        file_extension=Path(original_filename).suffix.lower(),
        file_type=file_type,
        file_category=file_category,
        source_application=source_application,
        likely_role=likely_role,
        classification_confidence=classification_confidence,
        processing_status=processing_status,
        parent_file_id=parent_file_id,
    )
    db.add(project_file)
    db.commit()
    db.refresh(project_file)
    return project_file


def delete_project_file(db: Session, file_id: UUID):
    db.query(ProjectFile).filter(ProjectFile.id == file_id).delete()
    db.flush()
