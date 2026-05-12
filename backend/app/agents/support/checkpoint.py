"""
Stage Checkpoint Manager — Phase 2 Step 16.

Writes hard-gate checkpoint records to stage_checkpoints in the runtime DB
and logs the corresponding audit event.  The manager is the single authority
for "has this gate passed?" queries in the pipeline.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.crud.validation import log_audit_event, save_checkpoint
from app.db.models import StageCheckpoint
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)


class CheckpointManager:
    """
    Create, query, and summarise hard-gate checkpoints for a project.

    All writes go through the session supplied to each method.
    A convenience ``create_checkpoint`` classmethod is provided for
    call-sites that do not manage their own session.
    """

    # ------------------------------------------------------------------
    # Write side
    # ------------------------------------------------------------------

    def record(
        self,
        db: Session,
        *,
        project_id: UUID,
        stage_code: str,
        label: str,
        gate_status: str,
        gate_data: dict | None = None,
    ) -> StageCheckpoint:
        """
        Persist a checkpoint and emit an audit event.

        gate_status: PASS | FAIL | PENDING
        """
        checkpoint = save_checkpoint(
            db,
            project_id=project_id,
            stage_code=stage_code,
            label=label,
            gate_status=gate_status,
            gate_data=gate_data,
        )
        log_audit_event(
            db,
            "CHECKPOINT_CREATED",
            project_id=project_id,
            stage_code=stage_code,
            detail={
                "label": label,
                "gate_status": gate_status,
                "gate_data": gate_data or {},
            },
        )
        logger.info(
            "Checkpoint [%s] %s → %s", stage_code, label, gate_status
        )
        return checkpoint

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------

    def gate_passed(self, db: Session, project_id: UUID, stage_code: str) -> bool:
        """
        Return True only if the latest checkpoint for this stage has status PASS.
        Returns False when no checkpoint exists (gate not yet evaluated).
        """
        latest = (
            db.query(StageCheckpoint)
            .filter(
                StageCheckpoint.project_id == project_id,
                StageCheckpoint.stage_code == stage_code,
            )
            .order_by(StageCheckpoint.created_at.desc())
            .first()
        )
        return latest is not None and latest.gate_status == "PASS"

    def all_gates_passed(
        self, db: Session, project_id: UUID, stage_codes: list[str]
    ) -> bool:
        """Return True only if every listed stage has a PASS checkpoint."""
        return all(self.gate_passed(db, project_id, s) for s in stage_codes)

    def get_summary(
        self, db: Session, project_id: UUID
    ) -> list[dict]:
        """Return all checkpoints for a project as plain dicts."""
        rows = (
            db.query(StageCheckpoint)
            .filter(StageCheckpoint.project_id == project_id)
            .order_by(StageCheckpoint.created_at)
            .all()
        )
        import json as _json
        results = []
        for r in rows:
            gate_data_parsed = {}
            if r.gate_data:
                try:
                    gate_data_parsed = _json.loads(r.gate_data)
                except Exception:
                    gate_data_parsed = {}
            results.append({
                "stage_code": r.stage_code,
                "label": r.checkpoint_label,
                "gate_status": r.gate_status,
                "created_at": str(r.created_at),
                "gate_data": gate_data_parsed,
            })
        return results

    # ------------------------------------------------------------------
    # Convenience classmethod (no external session needed)
    # ------------------------------------------------------------------

    @classmethod
    def create_checkpoint(
        cls,
        project_id: str,
        stage: str,
        label: str = "auto",
        gate_status: str = "PASS",
        gate_data: dict | None = None,
    ) -> None:
        """Backwards-compatible helper — opens its own session."""
        mgr = cls()
        session = SessionLocal()
        try:
            mgr.record(
                session,
                project_id=UUID(str(project_id)),
                stage_code=stage,
                label=label,
                gate_status=gate_status,
                gate_data=gate_data,
            )
            session.commit()
        finally:
            session.close()
