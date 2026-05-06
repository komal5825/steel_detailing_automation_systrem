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
    if status in {StageStatus.PASSED, StageStatus.FAILED, StageStatus.AWAITING_INPUT}:
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
    """Reset all stages for a project to PENDING status."""
    stages = db.query(Stage).filter(Stage.project_id == project_id).all()
    for stage in stages:
        stage.status = StageStatus.PENDING
        stage.result_json = "{}"
        stage.error_message = None
        stage.started_at = None
        stage.completed_at = None
    db.flush()
