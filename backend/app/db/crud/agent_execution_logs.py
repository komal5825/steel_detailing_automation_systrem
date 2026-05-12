import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AgentExecutionLog


def create_execution_log(
    db: Session,
    *,
    project_id: UUID,
    stage_code: str,
    trigger_type: str,
    status: str,
    input_payload: dict | None = None,
) -> AgentExecutionLog:
    row = AgentExecutionLog(
        project_id=project_id,
        stage_code=stage_code,
        trigger_type=trigger_type,
        status=status,
        input_payload=json.dumps(input_payload or {}, default=str),
        started_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def finalize_execution_log(
    db: Session,
    *,
    log_id: UUID,
    status: str,
    output_payload: dict | None = None,
    error_message: str | None = None,
    root_cause: str | None = None,
) -> AgentExecutionLog | None:
    row = db.query(AgentExecutionLog).filter(AgentExecutionLog.id == log_id).first()
    if row is None:
        return None
    row.status = status
    row.output_payload = json.dumps(output_payload or {}, default=str)
    row.error_message = error_message
    row.root_cause = root_cause
    row.completed_at = datetime.utcnow()
    db.flush()
    return row


def list_execution_logs(db: Session, project_id: UUID, limit: int = 200) -> list[AgentExecutionLog]:
    return (
        db.query(AgentExecutionLog)
        .filter(AgentExecutionLog.project_id == project_id)
        .order_by(AgentExecutionLog.started_at.desc())
        .limit(limit)
        .all()
    )
