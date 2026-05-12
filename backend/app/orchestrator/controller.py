"""
Phase 2 Pipeline Orchestrator — P2-01 → P2-02 → P2-03 → P2-04 → P2-05 → Handoff.

Each stage is called sequentially.  A stage that returns overall=BLOCKED/FAIL
pauses the pipeline and records the failure.  Re-runs are supported via
from_stage parameter.  Hard Gate 5 is checked after P2-05.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.p2_01_ingestion import run_ingestion
from app.agents.phase2.p2_02_completeness import check_completeness
from app.agents.phase2.p2_03_ab_generation import generate_ab_drawings
from app.agents.phase2.p2_04_ga_generation import generate_ga_drawings
from app.agents.phase2.p2_05_abga_validation import validate_abga
from app.agents.support.checkpoint import CheckpointManager
from app.db.crud.stages import list_project_stages, update_stage_result
from app.db.crud.agent_execution_logs import create_execution_log, finalize_execution_log
from app.db.crud.validation import log_audit_event
from app.db.models import StageStatus
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)

_CHECKPOINT_MGR = CheckpointManager()

_STAGE_PIPELINE: list[tuple[str, callable]] = [
    ("P2-01", run_ingestion),
    ("P2-02", check_completeness),
    ("P2-03", generate_ab_drawings),
    ("P2-04", generate_ga_drawings),
    ("P2-05", validate_abga),
]

# WebSocket registry: project_id (str) → set of connected WebSocket objects
_ws_connections: dict[str, set] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class OrchestrationController:
    """Run the full Phase 2 pipeline for a project."""

    def run(
        self,
        project_id: str,
        from_stage: str | None = None,
        to_stage: str | None = None,
        db: Session | None = None,
    ) -> dict:
        """Execute the P2 pipeline.  Stops on first failure.

        from_stage: skip stages before this code (for targeted re-runs).
        to_stage: stop after this stage completes (for partial runs, e.g. P2-01→P2-02 only).
        """
        owns_session = db is None
        session = db or SessionLocal()
        try:
            result = self._run(UUID(str(project_id)), from_stage, to_stage, session)
            session.commit()
            return result
        except Exception as exc:
            logger.error("Orchestrator crashed for %s: %s", project_id, exc)
            try:
                session.rollback()
            except Exception:
                pass
            raise
        finally:
            if owns_session:
                session.close()

    def start_process(self, project_id: str) -> dict:
        """Backwards-compatible alias."""
        return self.run(project_id, to_stage=None)

    def get_pipeline_status(self, project_id: str, db: Session | None = None) -> dict:
        owns_session = db is None
        session = db or SessionLocal()
        try:
            return _build_pipeline_status(UUID(str(project_id)), session)
        finally:
            if owns_session:
                session.close()

    # ------------------------------------------------------------------
    def _run(
        self,
        project_id: UUID,
        from_stage: str | None,
        to_stage: str | None,
        db: Session,
    ) -> dict:
        log_audit_event(db, "PIPELINE_STARTED", project_id=project_id,
                        detail={"from_stage": from_stage, "to_stage": to_stage})
        snapshot_path = _take_db_snapshot(project_id)
        if snapshot_path:
            log_audit_event(db, "DB_SNAPSHOT_TAKEN", project_id=project_id,
                            detail={"snapshot_path": snapshot_path})

        skipping = from_stage is not None
        if from_stage is None:
            # Auto-resume: find the first stage that is not PASSED or PASS_WITH_WARNINGS
            existing_stages = {s.stage_code: s.status for s in list_project_stages(db, project_id)}
            for sc, _ in _STAGE_PIPELINE:
                if existing_stages.get(sc) not in {StageStatus.PASSED, StageStatus.PASS_WITH_WARNINGS}:
                    from_stage = sc
                    skipping = True
                    logger.info("Auto-resuming pipeline from %s", from_stage)
                    break

        failed_stage: str | None = None
        pipeline_blocked = False     # BLOCKED = missing input, recoverable
        pipeline_failed = False      # FAIL = hard failure, pipeline must stop
        last_stage_run: str | None = None

        for stage_code, agent_fn in _STAGE_PIPELINE:
            if skipping:
                if stage_code == from_stage:
                    skipping = False
                else:
                    continue

            logger.info("Starting stage %s", stage_code)
            update_stage_result(db, project_id=project_id, stage_code=stage_code,
                                status=StageStatus.RUNNING)
            db.flush()
            _broadcast(project_id, stage_code, "RUNNING")

            exec_log = None
            try:
                exec_log = create_execution_log(
                    db,
                    project_id=project_id,
                    stage_code=stage_code,
                    trigger_type="pipeline",
                    status="RUNNING",
                    input_payload={
                        "project_id": str(project_id),
                        "stage_code": stage_code,
                        "from_stage": from_stage,
                        "to_stage": to_stage,
                    },
                )
                stage_result = agent_fn(project_id=str(project_id), db=db)
                overall = stage_result.get("overall", "PASS")
                last_stage_run = stage_code

                if overall == "BLOCKED":
                    failed_stage = stage_code
                    pipeline_blocked = True
                    update_stage_result(db, project_id=project_id, stage_code=stage_code,
                                        status=StageStatus.BLOCKED, result=stage_result)
                    _broadcast(project_id, stage_code, "BLOCKED")
                    finalize_execution_log(
                        db,
                        log_id=exec_log.id,
                        status="BLOCKED",
                        output_payload=stage_result,
                        error_message="Stage blocked by validator gate",
                        root_cause=stage_result.get("reason") or stage_result.get("error"),
                    )
                    logger.warning("Stage %s BLOCKED — pipeline paused awaiting input", stage_code)
                    break

                if overall == "FAIL":
                    failed_stage = stage_code
                    pipeline_failed = True
                    # Capture the failure reason from the stage result for visibility
                    failure_reason = stage_result.get("error") or stage_result.get("reason") or "Agent returned FAIL"
                    update_stage_result(
                        db, project_id=project_id, stage_code=stage_code,
                        status=StageStatus.FAILED,
                        result=stage_result,
                        error_message=failure_reason,
                    )
                    _broadcast(project_id, stage_code, "FAILED")
                    finalize_execution_log(
                        db,
                        log_id=exec_log.id,
                        status="FAILED",
                        output_payload=stage_result,
                        error_message=failure_reason,
                        root_cause=failure_reason,
                    )
                    logger.warning("Stage %s FAILED: %s", stage_code, failure_reason)
                    break

                status_to_set = StageStatus.PASSED
                if overall == "PASS_WITH_WARNINGS":
                    status_to_set = StageStatus.PASS_WITH_WARNINGS

                update_stage_result(db, project_id=project_id, stage_code=stage_code,
                                    status=status_to_set, result=stage_result)
                _broadcast(project_id, stage_code, status_to_set.value)
                finalize_execution_log(
                    db,
                    log_id=exec_log.id,
                    status=status_to_set.value,
                    output_payload=stage_result,
                )
                logger.info("Stage %s %s", stage_code, status_to_set.value)

            except Exception as exc:
                tb = traceback.format_exc()
                logger.error("Stage %s raised: %s\n%s", stage_code, exc, tb)
                update_stage_result(db, project_id=project_id, stage_code=stage_code,
                                    status=StageStatus.FAILED, error_message=str(exc))
                log_audit_event(db, "STAGE_FAILED", project_id=project_id,
                                stage_code=stage_code, detail={"error": str(exc), "traceback": tb})
                _broadcast(project_id, stage_code, "FAILED")
                try:
                    if exec_log is not None:
                        finalize_execution_log(
                            db,
                            log_id=exec_log.id,
                            status="FAILED",
                            output_payload={},
                            error_message=str(exc),
                            root_cause=str(exc),
                        )
                except Exception:
                    pass
                failed_stage = stage_code
                pipeline_failed = True
                last_stage_run = stage_code
                break

            # Stop after to_stage if specified (partial run)
            if to_stage and stage_code == to_stage:
                logger.info("Reached to_stage=%s — pausing pipeline", to_stage)
                break

        # Hard Gate 5 (only relevant when all 5 stages have been run)
        gate5_status, gate5_detail = _check_hard_gate_5(project_id, db)
        _CHECKPOINT_MGR.record(db, project_id=project_id, stage_code="P2-05",
                               label="Hard Gate 5 — Phase 2 Release Gate",
                               gate_status=gate5_status, gate_data=gate5_detail)

        # Handoff
        handoff_result: dict = {}
        if gate5_status == "PASS":
            try:
                from app.orchestrator.handoff_manager import HandoffManager  # noqa
                handoff_result = HandoffManager().prepare_handoff(str(project_id), db=db)
            except Exception as exc:
                logger.error("Handoff preparation failed: %s", exc)
                handoff_result = {"error": str(exc)}

        pipeline_status = _build_pipeline_status(project_id, db)
        summary = {
            "project_id": str(project_id),
            "pipeline_complete": failed_stage is None and to_stage is None,
            "pipeline_blocked": pipeline_blocked,
            "pipeline_failed": pipeline_failed,
            "failed_stage": failed_stage,
            "last_stage_run": last_stage_run,
            "hard_gate_5": gate5_status,
            "hard_gate_5_detail": gate5_detail,
            "phase3_eligible": gate5_status == "PASS",
            "handoff": handoff_result,
            "stages": pipeline_status["stages"],
            "run_at": datetime.now(timezone.utc).isoformat(),
        }
        log_audit_event(db, "PIPELINE_COMPLETED", project_id=project_id,
                        detail={"pipeline_complete": summary["pipeline_complete"],
                                "pipeline_failed": pipeline_failed,
                                "gate5": gate5_status})
        return summary


# ---------------------------------------------------------------------------
# Hard Gate 5
# ---------------------------------------------------------------------------

def _check_hard_gate_5(project_id: UUID, db: Session) -> tuple[str, dict]:
    stages = list_project_stages(db, project_id)
    stage_map = {s.stage_code: s.status for s in stages}
    required = ["P2-01", "P2-02", "P2-03", "P2-04", "P2-05"]
    not_passed = [s for s in required if stage_map.get(s) not in {StageStatus.PASSED, StageStatus.PASS_WITH_WARNINGS}]

    from app.agents.phase2.output_utils import project_output_dir  # noqa
    ab_exists = (project_output_dir(project_id, "ab") / "anchor_bolt_layout.json").exists()
    ga_exists = (project_output_dir(project_id, "ga") / "general_arrangement.json").exists()

    detail = {
        "required_stages": required,
        "not_passed_stages": not_passed,
        "ab_output_exists": ab_exists,
        "ga_output_exists": ga_exists,
    }
    passed = not not_passed and ab_exists and ga_exists
    return ("PASS" if passed else "FAIL"), detail


# ---------------------------------------------------------------------------
# Pipeline status helper
# ---------------------------------------------------------------------------

def _build_pipeline_status(project_id: UUID, db: Session) -> dict:
    stages = list_project_stages(db, project_id)
    checkpoints = _CHECKPOINT_MGR.get_summary(db, project_id)
    
    # Map checkpoints by stage_code for easy lookup
    cp_map = {}
    for cp in checkpoints:
        cp_map.setdefault(cp["stage_code"], []).append(cp)

    return {
        "project_id": str(project_id),
        "stages": [
            {
                "stage_code": s.stage_code,
                "status": s.status.value,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "error_message": s.error_message,
                "result": json.loads(s.result_json or "{}"),
                "checkpoints": cp_map.get(s.stage_code, []),
            }
            for s in stages
        ],
        "checkpoints": checkpoints,  # Also include full list at top level
    }


# ---------------------------------------------------------------------------
# Pre-run DB snapshot
# ---------------------------------------------------------------------------

def _take_db_snapshot(project_id: UUID) -> str | None:
    """
    Hot-backup the SQLite DB to processed_exports before the pipeline mutates it.
    Uses sqlite3.Connection.backup() which is WAL-safe and consistent.
    Returns the snapshot path, or None on failure (non-fatal).
    """
    try:
        from app.config.settings import settings
        from app.utils.project_paths import get_writable_project_data_root
        db_url = settings.database_url
        if not db_url.startswith("sqlite:///"):
            return None
        db_rel = db_url[len("sqlite:///"):]
        backend_dir = Path(__file__).resolve().parents[2]
        db_path = (backend_dir / db_rel).resolve()
        if not db_path.exists():
            return None

        export_dir = (
            get_writable_project_data_root()
            / str(project_id)
            / "outputs"
            / "processed_exports"
        )
        export_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = export_dir / f"db_snapshot_pre_run_{ts}.sqlite"

        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(dest))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        logger.info("Pre-run DB snapshot saved: %s", dest.name)
        return str(dest)
    except Exception as exc:
        logger.warning("Pre-run DB snapshot failed (non-fatal): %s", exc)
        return None


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------

def register_ws(project_id: str, ws) -> None:
    _ws_connections.setdefault(project_id, set()).add(ws)


def unregister_ws(project_id: str, ws) -> None:
    _ws_connections.get(project_id, set()).discard(ws)


def broadcast_stage_update(project_id: UUID | str, stage_code: str, status: str) -> None:
    _broadcast(UUID(str(project_id)), stage_code, status)


def _broadcast(project_id: UUID, stage_code: str, status: str) -> None:
    import asyncio  # noqa
    pid = str(project_id)
    message = json.dumps({
        "type": "stage_update",
        "project_id": pid,
        "stage_code": stage_code,
        "status": status,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    for ws in list(_ws_connections.get(pid, [])):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(ws.send_text(message))
        except Exception:
            pass
