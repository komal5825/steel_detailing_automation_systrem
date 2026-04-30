from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import load_project_field_map, write_json_output
from app.db.crud.stages import update_stage_result
from app.db.models import StageStatus
from app.db.session import SessionLocal


GA_FIELD_CODES = [
    "F-039",
    "F-040",
    "F-041",
    "F-042",
    "F-045",
    "F-046",
    "F-054",
    "F-056",
    "F-063",
    "F-064",
]


def generate_ga_drawings(project_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        result = _generate_ga(UUID(str(project_id)), session)
        session.commit()
        return result
    finally:
        if owns_session:
            session.close()


def _generate_ga(project_id: UUID, db: Session) -> dict:
    fields = load_project_field_map(db, project_id)
    payload = {
        "project_id": str(project_id),
        "output_type": "GA",
        "general_arrangement_fields": {code: fields.get(code) for code in GA_FIELD_CODES if fields.get(code) is not None},
        "source_field_count": len(fields),
        "status": "draft_generated",
    }
    output_path = write_json_output(project_id, "ga", "general_arrangement.json", payload)
    result = {**payload, "output_path": str(output_path)}
    update_stage_result(db, project_id=project_id, stage_code="P2-04", status=StageStatus.PASSED, result=result)
    return result
