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

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.crud.stages import list_project_stages, update_stage_result
from app.db.crud.agent_execution_logs import create_execution_log, finalize_execution_log, list_execution_logs
from app.db.models import StageStatus
from app.db.session import get_db
from app.orchestrator.controller import OrchestrationController, broadcast_stage_update
from app.orchestrator.dependency_checker import DependencyChecker

logger = logging.getLogger(__name__)

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
        UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    return _CTRL.get_pipeline_status(project_id, db=db)


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
        if result.get("pipeline_failed") or result.get("pipeline_blocked"):
            # Return 422 for both hard failures and blocks to signal incomplete run
            raise HTTPException(status_code=422, detail={
                "message": "Pipeline failed" if result.get("pipeline_failed") else "Pipeline blocked",
                "summary": result
            })
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Pipeline run failed for project %s: %s", project_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Pipeline orchestration failed",
                "root_cause": str(exc),
                "stage": body.from_stage or "pipeline",
                "suggested_fix": "Review stage logs/audit trail and retry from the failed stage.",
            },
        ) from exc


# ---------------------------------------------------------------------------
# Single-stage run
# ---------------------------------------------------------------------------

_STAGE_AGENTS: dict[str, callable] = {}

# Pipeline execution order — used for upstream dependency enforcement
_PIPELINE_ORDER = ["P2-01", "P2-02", "P2-03", "P2-04", "P2-05"]

_VALIDATOR_NAMES = {
    "P2-01": "File Ingestion Validator (format, readability, inventory check)",
    "P2-02": "Completeness Validator (field check, data quality, logical check)",
    "P2-03": "AB Generation Validator (data accuracy, unit check, standard check)",
    "P2-04": "GA Generation Validator (geometry, consistency, standard check)",
    "P2-05": "AB/GA Validation (code, clash, tolerance check)",
}


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

    # ── Upstream dependency lock ──────────────────────────────────────────────
    # A stage cannot execute until all upstream stages have cleared their
    # validators (status PASSED or PASS_WITH_WARNINGS).
    if normalized_stage_code in _PIPELINE_ORDER:
        stage_idx = _PIPELINE_ORDER.index(normalized_stage_code)
        if stage_idx > 0:
            prev_code = _PIPELINE_ORDER[stage_idx - 1]
            all_stages = list_project_stages(db, pid)
            prev = next((s for s in all_stages if s.stage_code == prev_code), None)
            prev_status = prev.status if prev else None
            if prev_status not in {StageStatus.PASSED, StageStatus.PASS_WITH_WARNINGS}:
                prev_status_val = prev_status.value if prev_status else "NOT_STARTED"
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": (
                            f"Stage {normalized_stage_code} is blocked — upstream "
                            f"validator has not cleared"
                        ),
                        "validator": _VALIDATOR_NAMES.get(prev_code, f"{prev_code} Validator"),
                        "status": "Pending",
                        "reason": (
                            f"{prev_code} has not completed successfully "
                            f"(current status: {prev_status_val})"
                        ),
                        "blocking_dependency": (
                            f"{prev_code} must reach PASSED or PASS_WITH_WARNINGS "
                            f"before {normalized_stage_code} can execute"
                        ),
                        "expected_source": (
                            f"Successful output from {prev_code} stage execution"
                        ),
                        "recommended_fix": (
                            f"Run {prev_code} first and ensure it completes without "
                            f"blocking failures before attempting {normalized_stage_code}"
                        ),
                    },
                )
    # ─────────────────────────────────────────────────────────────────────────

    exec_log_id = None
    try:
        update_stage_result(
            db,
            project_id=pid,
            stage_code=normalized_stage_code,
            status=StageStatus.RUNNING,
        )
        exec_log = create_execution_log(
            db,
            project_id=pid,
            stage_code=normalized_stage_code,
            trigger_type="manual_stage",
            status="RUNNING",
            input_payload={"project_id": project_id, "stage_code": normalized_stage_code},
        )
        exec_log_id = exec_log.id
        db.commit()
        broadcast_stage_update(pid, normalized_stage_code, "RUNNING")
        result = fn(project_id=project_id, db=db)
        
        # Check if the single stage run resulted in a failure or block
        overall = result.get("overall", "PASS")
        if overall in ("FAIL", "BLOCKED"):
             raise HTTPException(status_code=422, detail={
                "message": f"Stage {normalized_stage_code} {overall}",
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
        if isinstance(result, dict):
            result.setdefault("execution_trace", {})
            result["execution_trace"].update(
                {
                    "stage_code": normalized_stage_code,
                    "status": "PASSED",
                    "input": {"project_id": project_id, "stage_code": normalized_stage_code},
                    "failure_reason": None,
                }
            )
        if exec_log_id:
            finalize_execution_log(
                db,
                log_id=exec_log_id,
                status="PASSED" if overall == "PASS" else overall,
                output_payload=result if isinstance(result, dict) else {"result": str(result)},
            )
            db.commit()
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Stage %s raised an unhandled exception for project %s: %s",
            normalized_stage_code, project_id, exc, exc_info=True,
        )
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
            if exec_log_id:
                finalize_execution_log(
                    db,
                    log_id=exec_log_id,
                    status="FAILED",
                    output_payload={},
                    error_message=str(exc),
                    root_cause=str(exc),
                )
                db.commit()
        except Exception as inner:
            logger.error("Could not persist FAILED status for %s: %s", normalized_stage_code, inner)
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Stage {normalized_stage_code} crashed",
                "root_cause": str(exc),
                "stage": normalized_stage_code,
                "suggested_fix": "Inspect stack trace and stage inputs in backend logs, then rerun the stage.",
                "input_payload": {"project_id": project_id, "stage_code": normalized_stage_code},
            },
        ) from exc


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


@router.get("/{project_id}/execution-logs")
async def get_execution_logs(project_id: str, limit: int = 200, db: Session = Depends(get_db)):
    try:
        pid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")
    rows = list_execution_logs(db, pid, limit=max(1, min(limit, 1000)))
    out = []
    for r in rows:
        out.append(
            {
                "id": str(r.id),
                "project_id": str(r.project_id),
                "stage_code": r.stage_code,
                "trigger_type": r.trigger_type,
                "status": r.status,
                "input_payload": r.input_payload,
                "output_payload": r.output_payload,
                "error_message": r.error_message,
                "root_cause": r.root_cause,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
        )
    return out
