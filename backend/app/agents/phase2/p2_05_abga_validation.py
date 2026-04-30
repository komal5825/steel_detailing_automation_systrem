from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import project_output_dir, write_json_output
from app.db.crud.stages import update_stage_result
from app.db.models import StageStatus
from app.db.session import SessionLocal


def validate_abga(project_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        result = _validate(UUID(str(project_id)), session)
        session.commit()
        return result
    finally:
        if owns_session:
            session.close()


def _validate(project_id: UUID, db: Session) -> dict:
    ab_path = project_output_dir(project_id, "ab") / "anchor_bolt_layout.json"
    ga_path = project_output_dir(project_id, "ga") / "general_arrangement.json"
    items = []

    ab_payload = _read_json(ab_path)
    ga_payload = _read_json(ga_path)
    items.append(_item("AB_OUTPUT_EXISTS", ab_payload is not None, str(ab_path)))
    items.append(_item("GA_OUTPUT_EXISTS", ga_payload is not None, str(ga_path)))

    if ab_payload is not None:
        items.append(_item("AB_HAS_SOURCE_FIELDS", ab_payload.get("source_field_count", 0) > 0, str(ab_path)))
    if ga_payload is not None:
        items.append(_item("GA_HAS_SOURCE_FIELDS", ga_payload.get("source_field_count", 0) > 0, str(ga_path)))

    overall = "PASS" if all(item["passed"] for item in items) else "FAIL"
    result = {
        "project_id": str(project_id),
        "overall": overall,
        "items": items,
    }
    report_path = write_json_output(project_id, "validation", "abga_validation.json", result)
    result["report_path"] = str(report_path)
    update_stage_result(
        db,
        project_id=project_id,
        stage_code="P2-05",
        status=StageStatus.PASSED if overall == "PASS" else StageStatus.FAILED,
        result=result,
    )
    return result


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _item(rule_id: str, passed: bool, evidence: str) -> dict:
    return {
        "rule_id": rule_id,
        "passed": passed,
        "severity": "CRITICAL" if not passed else "INFO",
        "evidence": evidence,
    }
