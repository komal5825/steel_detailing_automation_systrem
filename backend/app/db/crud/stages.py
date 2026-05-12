import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Stage, StageStatus


def update_stage_result(
    db: Session,
    *,
    project_id: UUID,
    stage_code: str,
    status: StageStatus,
    result: dict | None = None,
    error_message: str | None = None,
) -> Stage:
    stage = (
        db.query(Stage)
        .filter(Stage.project_id == project_id)
        .filter(Stage.stage_code == stage_code)
        .first()
    )
    if stage is None:
        stage = Stage(project_id=project_id, stage_code=stage_code)
        db.add(stage)
        db.flush()

    stage.status = status
    stage.result_json = json.dumps(result or {}, default=str)
    stage.error_message = error_message
    if status == StageStatus.RUNNING and stage.started_at is None:
        stage.started_at = datetime.utcnow()
    if status in {StageStatus.PASSED, StageStatus.PASS_WITH_WARNINGS, StageStatus.FAILED, StageStatus.BLOCKED}:
        stage.completed_at = datetime.utcnow()
    db.flush()
    return stage


def list_project_stages(db: Session, project_id: UUID) -> list[Stage]:
    return (
        db.query(Stage)
        .filter(Stage.project_id == project_id)
        .order_by(Stage.stage_code)
        .all()
    )


def reset_all_stages(db: Session, project_id: UUID):
    """Reset all stages and clear all derived/parsed data for a project."""
    from app.db.models import (
        ExtractedFieldValue, ParserRun, StageCheckpoint, ValidationResult,
        ProjectFile, Handoff, Escalation, CorrectionEvent, ReportRecord
    )
    import shutil
    from pathlib import Path
    from app.config.settings import settings

    # 1. Clear all derived pipeline data so no stale history remains
    db.query(ExtractedFieldValue).filter(ExtractedFieldValue.project_id == project_id).delete()
    db.query(ParserRun).filter(ParserRun.project_id == project_id).delete()
    db.query(ValidationResult).filter(ValidationResult.project_id == project_id).delete()
    db.query(StageCheckpoint).filter(StageCheckpoint.project_id == project_id).delete()
    db.query(Handoff).filter(Handoff.project_id == project_id).delete()
    db.query(Escalation).filter(Escalation.project_id == project_id).delete()
    db.query(CorrectionEvent).filter(CorrectionEvent.project_id == project_id).delete()
    db.query(ReportRecord).filter(ReportRecord.project_id == project_id).delete()

    # 2. Clear physical files and ProjectFile records
    # We delete ProjectFile records *after* attempting to clean up disk
    project_files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
    for pf in project_files:
        p = Path(pf.stored_path)
        if p.exists():
            if p.is_file():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
    
    # Also clear the project's input and output directories on disk to ensure 100% isolation
    root = Path(settings.project_data_root)
    proj_dir = root / str(project_id)
    if proj_dir.exists():
        shutil.rmtree(proj_dir / "input", ignore_errors=True)
        shutil.rmtree(proj_dir / "outputs", ignore_errors=True)
        shutil.rmtree(proj_dir / "Processed", ignore_errors=True)

    db.query(ProjectFile).filter(ProjectFile.project_id == project_id).delete()

    # 3. Reset stage statuses
    stages = db.query(Stage).filter(Stage.project_id == project_id).all()
    for stage in stages:
        stage.status = StageStatus.PENDING
        stage.result_json = "{}"
        stage.error_message = None
        stage.started_at = None
        stage.completed_at = None
    db.flush()
