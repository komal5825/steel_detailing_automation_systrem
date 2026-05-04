"""
Handoff API endpoints.

  GET  /api/handoffs/{project_id}              — latest handoff package
  GET  /api/handoffs/{project_id}/list         — all handoff records
  POST /api/handoffs/{project_id}/approve      — approve / reject handoff
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.crud.handoffs import approve_handoff, list_handoffs
from app.db.session import get_db
from app.orchestrator.handoff_manager import HandoffManager

router = APIRouter()


@router.get("/{project_id}")
async def get_handoff_package(project_id: str, db: Session = Depends(get_db)):
    """Build (or re-build) the handoff package for a project."""
    return HandoffManager().prepare_handoff(project_id, db=db)


@router.get("/{project_id}/list")
async def list_project_handoffs(project_id: str, db: Session = Depends(get_db)):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    rows = list_handoffs(db, pid)
    return [
        {
            "id": str(r.id),
            "from_stage": r.from_stage,
            "to_stage": r.to_stage,
            "package_path": r.package_path,
            "approved": r.approved,
            "approved_by": r.approved_by,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


class ApprovalRequest(BaseModel):
    handoff_id: str
    approved_by: str
    decision: int   # 1 = approve, -1 = reject


@router.post("/{project_id}/approve")
async def approve_project_handoff(
    project_id: str,
    body: ApprovalRequest,
    db: Session = Depends(get_db),
):
    try:
        hid = UUID(body.handoff_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid handoff_id") from exc

    row = approve_handoff(db, hid, approved_by=body.approved_by, decision=body.decision)
    if row is None:
        raise HTTPException(status_code=404, detail="Handoff not found")

    db.commit()
    return {
        "handoff_id": str(row.id),
        "approved": row.approved,
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
    }
