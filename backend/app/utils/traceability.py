from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from uuid import UUID

from app.db.crud.validation import log_audit_event

def trace_action(db: Session, project_id: UUID | str, action: str, details: dict = None):
    """
    Trace an agent action both to the console and the persistent audit log.
    """
    print(f"Tracing action for {project_id}: {action} - {details}")
    from uuid import UUID as _UUID
    pid = _UUID(str(project_id)) if not isinstance(project_id, _UUID) else project_id
    
    log_audit_event(
        db,
        event_type=action.upper(),
        project_id=pid,
        detail=details
    )
    return True
