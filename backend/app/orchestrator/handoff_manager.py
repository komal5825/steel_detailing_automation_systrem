"""
Handoff Manager — Phase 2 Step 22.

Builds the Phase 2 → Phase 3 handoff package JSON, writes it to disk, and
persists a Handoff record in the runtime DB.  Only eligible when all five
P2 stages have PASSED.
"""
from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import project_output_dir, write_json_output
from app.db.crud.handoffs import create_handoff, get_latest_handoff
from app.db.crud.stages import list_project_stages
from app.db.crud.validation import log_audit_event
from app.db.models import StageStatus
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)

_REQUIRED_STAGES = ["P2-01", "P2-02", "P2-03", "P2-04", "P2-05"]


class HandoffManager:
    def prepare_handoff(
        self,
        project_id: str,
        source_stage: str = "P2-05",
        target_stage: str = "P3-01",
        db: Session | None = None,
    ) -> dict:
        owns_session = db is None
        session = db or SessionLocal()
        try:
            result = self._prepare(UUID(str(project_id)), source_stage, target_stage, session)
            session.commit()
            return result
        finally:
            if owns_session:
                session.close()

    # ------------------------------------------------------------------

    def _prepare(
        self,
        project_id: UUID,
        source_stage: str,
        target_stage: str,
        db: Session,
    ) -> dict:
        stages = list_project_stages(db, project_id)
        stage_map = {s.stage_code: s for s in stages}

        phase2_complete = all(
            stage_map.get(code) is not None
            and stage_map[code].status == StageStatus.PASSED
            for code in _REQUIRED_STAGES
        )

        stage_summary = [
            {
                "stage_code": s.stage_code,
                "status": s.status.value,
                "result": json.loads(s.result_json or "{}"),
            }
            for s in stages
        ]

        package = {
            "project_id": str(project_id),
            "from_stage": source_stage,
            "to_stage": target_stage,
            "phase3_eligible": phase2_complete,
            "required_phase2_stages": _REQUIRED_STAGES,
            "stages": stage_summary,
            "ab_output_dir": str(project_output_dir(project_id, "ab")),
            "ga_output_dir": str(project_output_dir(project_id, "ga")),
            "validation_output_dir": str(project_output_dir(project_id, "validation")),
            "cad_output_dir": str(project_output_dir(project_id, "cad")),
        }

        package_path = write_json_output(
            project_id, "handoff", "phase2_to_phase3_handoff.json", package
        )
        package["package_path"] = str(package_path)

        # Persist handoff record (create only if none exists for this from_stage)
        existing = get_latest_handoff(db, project_id, from_stage=source_stage)
        if existing is None:
            handoff_row = create_handoff(
                db,
                project_id=project_id,
                from_stage=source_stage,
                to_stage=target_stage,
                package_path=str(package_path),
            )
            package["handoff_id"] = str(handoff_row.id)
        else:
            existing.package_path = str(package_path)
            db.flush()
            package["handoff_id"] = str(existing.id)

        log_audit_event(
            db,
            "HANDOFF_PREPARED",
            project_id=project_id,
            stage_code=source_stage,
            detail={
                "phase3_eligible": phase2_complete,
                "package_path": str(package_path),
            },
        )
        logger.info("Handoff prepared for %s — phase3_eligible=%s",
                    project_id, phase2_complete)
        return package
