"""
CRUD for the Handoff table — records Phase 2 → Phase 3 handoff packages
and tracks approval status.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Handoff


def create_handoff(
    db: Session,
    *,
    project_id: UUID,
    from_stage: str,
    to_stage: str,
    package_path: str | None = None,
) -> Handoff:
    handoff = Handoff(
        project_id=project_id,
        from_stage=from_stage,
        to_stage=to_stage,
        package_path=package_path,
        approved=0,
    )
    db.add(handoff)
    db.flush()
    return handoff


def get_latest_handoff(
    db: Session,
    project_id: UUID,
    from_stage: str | None = None,
) -> Handoff | None:
    q = db.query(Handoff).filter(Handoff.project_id == project_id)
    if from_stage:
        q = q.filter(Handoff.from_stage == from_stage)
    return q.order_by(Handoff.created_at.desc()).first()


def list_handoffs(db: Session, project_id: UUID) -> list[Handoff]:
    return (
        db.query(Handoff)
        .filter(Handoff.project_id == project_id)
        .order_by(Handoff.created_at.desc())
        .all()
    )


def approve_handoff(
    db: Session,
    handoff_id: UUID,
    *,
    approved_by: str,
    decision: int,          # 1 = approve, -1 = reject
) -> Handoff | None:
    from datetime import datetime  # noqa: PLC0415
    handoff = db.query(Handoff).filter(Handoff.id == handoff_id).first()
    if handoff is None:
        return None
    handoff.approved = decision
    handoff.approved_by = approved_by
    handoff.approved_at = datetime.utcnow()
    db.flush()
    return handoff
