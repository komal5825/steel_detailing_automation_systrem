"""
Stage and pipeline API endpoints.

  GET  /api/stages/dependencies/readiness
  GET  /api/stages/{project_id}/status
  POST /api/stages/{project_id}/pipeline/run
  POST /api/stages/{project_id}/pipeline/run/{stage_code}
  GET  /api/stages/{project_id}/pipeline/status
  POST /api/stages/{project_id}/approve
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.crud.stages import list_project_stages, update_stage_result
from app.db.models import StageStatus
from app.db.session import get_db
from app.orchestrator.controller import OrchestrationController, broadcast_stage_update
from app.orchestrator.dependency_checker import DependencyChecker

router = APIRouter()
_CTRL = OrchestrationController()

# ---------------------------------------------------------------------------
# Tool readiness
# ---------------------------------------------------------------------------

@router.get("/dependencies/readiness")
async def get_dependency_readiness():
    return DependencyChecker().check_dependencies()


# ---------------------------------------------------------------------------
# Stage status (per-row)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/status")
async def get_stage_status(project_id: str, db: Session = Depends(get_db)):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    stages = list_project_stages(db, pid)
    return {
        "project_id": project_id,
        "stages": [
            {
                "stage_code": s.stage_code,
                "status": s.status.value,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "error_message": s.error_message,
                "result": json.loads(s.result_json or "{}"),
            }
            for s in stages
        ],
    }


# ---------------------------------------------------------------------------
# Full pipeline run
# ---------------------------------------------------------------------------

class PipelineRunRequest(BaseModel):
    from_stage: str | None = None
    to_stage: str | None = None


@router.post("/{project_id}/pipeline/run")
async def run_pipeline(
    project_id: str,
    body: PipelineRunRequest = PipelineRunRequest(),
    db: Session = Depends(get_db),
):
    """Trigger the Phase 2 pipeline and return the summary."""
    try:
        UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    try:
        result = _CTRL.run(project_id=project_id, from_stage=body.from_stage, to_stage=body.to_stage, db=db)
        if result.get("pipeline_failed"):
            # If the pipeline failed (hard failure), we return the summary but with 422
            # to let the frontend know it stopped due to an error.
            raise HTTPException(status_code=422, detail={
                "message": "Pipeline failed",
                "summary": result
            })
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Single-stage run
# ---------------------------------------------------------------------------

_STAGE_AGENTS: dict[str, callable] = {}


def _agents() -> dict[str, callable]:
    if not _STAGE_AGENTS:
        from app.agents.phase2.p2_01_ingestion import run_ingestion           # noqa
        from app.agents.phase2.p2_02_completeness import check_completeness   # noqa
        from app.agents.phase2.p2_03_ab_generation import generate_ab_drawings  # noqa
        from app.agents.phase2.p2_04_ga_generation import generate_ga_drawings   # noqa
        from app.agents.phase2.p2_05_abga_validation import validate_abga     # noqa
        _STAGE_AGENTS.update({
            "P2-01": run_ingestion,
            "P2-02": check_completeness,
            "P2-03": generate_ab_drawings,
            "P2-04": generate_ga_drawings,
            "P2-05": validate_abga,
        })
    return _STAGE_AGENTS


@router.post("/{project_id}/pipeline/run/{stage_code}")
async def run_single_stage(
    project_id: str,
    stage_code: str,
    db: Session = Depends(get_db),
):
    """Re-run a single stage in isolation."""
    normalized_stage_code = stage_code.upper()
    fn = _agents().get(normalized_stage_code)
    if fn is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown stage '{stage_code}'. Valid: {list(_agents())}",
        )
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    try:
        update_stage_result(
            db,
            project_id=pid,
            stage_code=normalized_stage_code,
            status=StageStatus.RUNNING,
        )
        db.commit()
        broadcast_stage_update(pid, normalized_stage_code, "RUNNING")
        result = fn(project_id=project_id, db=db)
        
        # Check if the single stage run resulted in a failure
        overall = result.get("overall", "PASS")
        if overall == "FAIL":
             raise HTTPException(status_code=422, detail={
                "message": f"Stage {normalized_stage_code} failed",
                "result": result
            })

        stage = next(
            (row for row in list_project_stages(db, pid) if row.stage_code == normalized_stage_code),
            None,
        )
        broadcast_stage_update(
            pid,
            normalized_stage_code,
            stage.status.value if stage else "PASSED",
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        try:
            update_stage_result(
                db,
                project_id=pid,
                stage_code=normalized_stage_code,
                status=StageStatus.FAILED,
                error_message=str(exc),
            )
            db.commit()
            broadcast_stage_update(pid, normalized_stage_code, "FAILED")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Pipeline status summary
# ---------------------------------------------------------------------------

@router.get("/{project_id}/pipeline/status")
async def get_pipeline_status(project_id: str, db: Session = Depends(get_db)):
    try:
        UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    return _CTRL.get_pipeline_status(project_id, db=db)


# ---------------------------------------------------------------------------
# Extra Endpoints: Reset, Fields, Approve, Checkpoints
# ---------------------------------------------------------------------------

@router.post("/{project_id}/reset-intake")
async def reset_intake(project_id: str, db: Session = Depends(get_db)):
    """Clear all ingested files and reset P2-01 status."""
    from app.db.models import ProjectFile, Stage, StageCheckpoint, ValidationResult
    from app.db.crud.validation import log_audit_event
    try:
        pid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    # Delete related data
    db.query(ValidationResult).filter(ValidationResult.project_id == pid).delete()
    db.query(StageCheckpoint).filter(StageCheckpoint.project_id == pid).delete()
    db.query(ProjectFile).filter(ProjectFile.project_id == pid).delete()
    
    # Reset P2-01 stage
    update_stage_result(db, project_id=pid, stage_code="P2-01", status=StageStatus.PENDING, result={})
    
    log_audit_event(db, "INTAKE_RESET", project_id=pid)
    db.commit()
    broadcast_stage_update(pid, "P2-01", "PENDING")
    return {"message": "Intake reset successfully"}


@router.get("/{project_id}/fields")
async def get_fields(project_id: str, stage_code: str | None = None, db: Session = Depends(get_db)):
    """Get validation items (missing fields) for a project/stage."""
    from app.db.crud.validation import get_validation_items
    try:
        pid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")
    
    items = get_validation_items(db, pid, stage_code=stage_code)
    return [
        {
            "id": str(i.id),
            "field_code": i.field_code,
            "status": i.status,
            "severity": i.severity,
            "value": i.value,
            "note": i.note,
            "created_at": i.created_at.isoformat()
        }
        for i in items
    ]


class FieldOverride(BaseModel):
    field_code: str
    value: str
    note: str | None = None


@router.post("/{project_id}/fields/override")
async def override_fields(project_id: str, overrides: list[FieldOverride], db: Session = Depends(get_db)):
    """Manually override missing fields to resolve blockers."""
    from app.db.models import ValidationResult
    from app.db.crud.validation import log_audit_event
    try:
        pid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")
    
    for ovr in overrides:
        # Find existing missing field or create new record
        record = db.query(ValidationResult).filter(
            ValidationResult.project_id == pid,
            ValidationResult.field_code == ovr.field_code
        ).first()
        
        if record:
            record.status = "PRESENT"
            record.value = ovr.value
            record.note = ovr.note or "Manual override"
        else:
            record = ValidationResult(
                project_id=pid,
                stage_code="MANUAL",
                field_code=ovr.field_code,
                status="PRESENT",
                severity="MINOR",
                value=ovr.value,
                note=ovr.note or "Manual entry"
            )
            db.add(record)
        
        log_audit_event(db, "FIELD_OVERRIDDEN", project_id=pid, field_code=ovr.field_code, detail={"value": ovr.value})
    
    db.commit()
    return {"message": f"Overrode {len(overrides)} fields"}


@router.post("/{project_id}/approve")
async def approve_stage(project_id: str, stage_code: str, db: Session = Depends(get_db)):
    """Mark a stage as PASSED manually (approval gate)."""
    from app.db.crud.validation import log_audit_event
    try:
        pid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")
    
    update_stage_result(db, project_id=pid, stage_code=stage_code, status=StageStatus.PASSED)
    log_audit_event(db, "STAGE_APPROVED", project_id=pid, stage_code=stage_code)
    db.commit()
    broadcast_stage_update(pid, stage_code, "PASSED")
    return {"message": f"Stage {stage_code} approved"}


@router.get("/{project_id}/checkpoints")
async def get_checkpoints(project_id: str, db: Session = Depends(get_db)):
    """Get all hard-gate checkpoints for a project."""
    from app.agents.support.checkpoint import CheckpointManager
    try:
        pid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")
    
    return CheckpointManager().get_summary(db, pid)

