from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.crud.stages import update_stage_result
from app.db.models import ExtractedFieldValue, StageStatus
from app.db.session import SessionLocal
from app.utils.master_db import fetch_mandatory_field_codes


def check_completeness(project_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        result = _check_completeness(UUID(str(project_id)), session)
        session.commit()
        return result
    finally:
        if owns_session:
            session.close()


def _check_completeness(project_id: UUID, db: Session) -> dict:
    mandatory_codes = set(fetch_mandatory_field_codes())
    present_codes = {
        row[0]
        for row in db.query(ExtractedFieldValue.field_code)
        .filter(ExtractedFieldValue.project_id == project_id)
        .distinct()
        .all()
    }
    missing_codes = sorted(mandatory_codes - present_codes)
    present_mandatory = sorted(mandatory_codes & present_codes)
    blocker_count = len(missing_codes)

    result = {
        "project_id": str(project_id),
        "mandatory_count": len(mandatory_codes),
        "present_mandatory_count": len(present_mandatory),
        "missing_mandatory_count": blocker_count,
        "missing_mandatory_codes": missing_codes,
        "is_complete": blocker_count == 0,
        "overall": "PASS" if blocker_count == 0 else "BLOCKED",
    }
    update_stage_result(
        db,
        project_id=project_id,
        stage_code="P2-02",
        status=StageStatus.PASSED if blocker_count == 0 else StageStatus.AWAITING_INPUT,
        result=result,
    )
    return result
