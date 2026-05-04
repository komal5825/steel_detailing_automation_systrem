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


@router.post("/{project_id}/pipeline/run")
async def run_pipeline(
    project_id: str,
    body: PipelineRunRequest = PipelineRunRequest(),
    db: Session = Depends(get_db),
):
    """Trigger the full Phase 2 pipeline and return the summary."""
    try:
        UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc
    try:
        return _CTRL.run(project_id=project_id, from_stage=body.from_stage, db=db)
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
    except Exception as exc:
        try:
            update_stage_result(
                db,
                project_id=UUID(project_id),
                stage_code=normalized_stage_code,
                status=StageStatus.FAILED,
                error_message=str(exc),
            )
            db.commit()
            broadcast_stage_update(project_id, normalized_stage_code, "FAILED")
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
# Legacy approval stub
# ---------------------------------------------------------------------------

@router.post("/{project_id}/approve")
async def approve_stage(project_id: str, stage: str):
    return {"message": f"Stage {stage} approved for project {project_id}"}
