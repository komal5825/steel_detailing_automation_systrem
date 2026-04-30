from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import load_project_field_map, write_json_output
from app.db.crud.stages import update_stage_result
from app.db.models import StageStatus
from app.db.session import SessionLocal


AB_FIELD_CODES = ["F-081", "F-082", "F-083", "F-084", "F-085", "F-086", "F-087", "F-088", "F-089"]


def generate_ab_drawings(project_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        result = _generate_ab(UUID(str(project_id)), session)
        session.commit()
        return result
    finally:
        if owns_session:
            session.close()


def _generate_ab(project_id: UUID, db: Session) -> dict:
    fields = load_project_field_map(db, project_id)
    payload = {
        "project_id": str(project_id),
        "output_type": "AB",
        "anchor_bolt_fields": {code: fields.get(code) for code in AB_FIELD_CODES if fields.get(code) is not None},
        "source_field_count": len(fields),
        "status": "draft_generated",
    }
    output_path = write_json_output(project_id, "ab", "anchor_bolt_layout.json", payload)
    result = {**payload, "output_path": str(output_path)}
    update_stage_result(db, project_id=project_id, stage_code="P2-03", status=StageStatus.PASSED, result=result)
    return result
