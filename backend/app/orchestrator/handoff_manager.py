from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import project_output_dir, write_json_output
from app.db.crud.stages import list_project_stages
from app.db.models import StageStatus
from app.db.session import SessionLocal


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

    def _prepare(self, project_id: UUID, source_stage: str, target_stage: str, db: Session) -> dict:
        stages = list_project_stages(db, project_id)
        stage_summary = [
            {
                "stage_code": stage.stage_code,
                "status": stage.status.value,
                "result": json.loads(stage.result_json or "{}"),
            }
            for stage in stages
        ]
        phase2_complete = any(stage.stage_code == "P2-05" and stage.status == StageStatus.PASSED for stage in stages)
        package = {
            "project_id": str(project_id),
            "from_stage": source_stage,
            "to_stage": target_stage,
            "phase3_eligible": phase2_complete,
            "stages": stage_summary,
            "ab_output_dir": str(project_output_dir(project_id, "ab")),
            "ga_output_dir": str(project_output_dir(project_id, "ga")),
            "validation_output_dir": str(project_output_dir(project_id, "validation")),
        }
        package_path = write_json_output(project_id, "handoff", "phase2_to_phase3_handoff.json", package)
        package["package_path"] = str(package_path)
        return package
