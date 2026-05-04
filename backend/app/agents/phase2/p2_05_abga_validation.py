"""
P2-05 AB/GA Validation Agent — Phase 2 Step 20.

Validates:
  1. AB and GA output JSON files exist and contain field data.
  2. Active validation_rule_master rules pass against the resolved field map.

Persists ValidationResult rows, writes a Hard-Gate checkpoint, and emits
audit events.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import (
    load_project_field_map,
    project_output_dir,
    write_json_output,
)
from app.agents.support.checkpoint import CheckpointManager
from app.agents.support.validator import Validator
from app.db.crud.stages import update_stage_result
from app.db.crud.validation import log_audit_event, save_validation_items
from app.db.models import StageStatus
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)

_CHECKPOINT_MGR = CheckpointManager()
_VALIDATOR = Validator()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------

def _validate(project_id: UUID, db: Session) -> dict:
    log_audit_event(db, "STAGE_STARTED", project_id=project_id, stage_code="P2-05")
    update_stage_result(db, project_id=project_id, stage_code="P2-05",
                        status=StageStatus.RUNNING)

    # ---- 1. File existence checks ----
    ab_path = project_output_dir(project_id, "ab") / "anchor_bolt_layout.json"
    ga_path = project_output_dir(project_id, "ga") / "general_arrangement.json"
    ab_payload = _read_json(ab_path)
    ga_payload = _read_json(ga_path)

    file_items = [
        _item("AB_OUTPUT_EXISTS", ab_payload is not None, str(ab_path)),
        _item("GA_OUTPUT_EXISTS", ga_payload is not None, str(ga_path)),
    ]
    if ab_payload is not None:
        file_items.append(_item("AB_HAS_FIELDS",
                                ab_payload.get("source_field_count", 0) > 0,
                                str(ab_path)))
    if ga_payload is not None:
        file_items.append(_item("GA_HAS_FIELDS",
                                ga_payload.get("source_field_count", 0) > 0,
                                str(ga_path)))

    # ---- 2. Rule-based field validation ----
    field_map = load_project_field_map(db, project_id)
    rule_report = _VALIDATOR.validate_project(field_map, stage="P2-05")
    rule_items = rule_report.to_items()

    # ---- 3. Persist ValidationResult rows ----
    file_vr_items = [
        {
            "field_code": itm["rule_id"],
            "status": "PRESENT" if itm["passed"] else "MISSING",
            "severity": "CRITICAL" if not itm["passed"] else "MINOR",
            "source": "output_check",
            "value": itm["evidence"],
            "note": itm["rule_id"],
        }
        for itm in file_items
    ]
    save_validation_items(db, project_id, "P2-05", rule_items + file_vr_items)

    # ---- 4. Overall verdict ----
    file_ok = all(itm["passed"] for itm in file_items)
    rules_ok = rule_report.overall == "PASS"
    overall = "PASS" if (file_ok and rules_ok) else "FAIL"

    result = {
        "project_id": str(project_id),
        "overall": overall,
        "file_checks": file_items,
        "rule_validation": {
            "overall": rule_report.overall,
            "blocking_failures": rule_report.blocking_failures,
            "rules_evaluated": len(rule_report.results),
        },
    }

    # ---- 5. Checkpoint ----
    _CHECKPOINT_MGR.record(
        db, project_id=project_id, stage_code="P2-05",
        label="AB/GA Validation Gate",
        gate_status=overall,
        gate_data=result,
    )

    # ---- 6. Write report ----
    report_path = write_json_output(project_id, "validation", "abga_validation.json", result)
    result["report_path"] = str(report_path)

    update_stage_result(
        db, project_id=project_id, stage_code="P2-05",
        status=StageStatus.PASSED if overall == "PASS" else StageStatus.FAILED,
        result=result,
    )
    log_audit_event(
        db, "STAGE_PASSED" if overall == "PASS" else "STAGE_FAILED",
        project_id=project_id, stage_code="P2-05",
        detail={"overall": overall,
                "blocking_failures": rule_report.blocking_failures},
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _item(rule_id: str, passed: bool, evidence: str) -> dict:
    return {
        "rule_id": rule_id,
        "passed": passed,
        "severity": "CRITICAL" if not passed else "INFO",
        "evidence": evidence,
    }
