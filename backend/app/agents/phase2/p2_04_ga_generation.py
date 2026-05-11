from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import (
    write_json_output,
    write_processed_json,
)
from app.agents.support.checkpoint import CheckpointManager
from app.agents.support.fallback import FallbackManager
from app.db.crud.stages import update_stage_result
from app.db.crud.validation import log_audit_event
from app.db.models import StageStatus
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger
from app.utils.master_db import fetch_ga_required_field_codes
from app.utils.source_priority import build_resolved_field_map
from app.utils.traceability import trace_action

logger = get_logger(__name__)
_CHECKPOINT_MGR = CheckpointManager()
_FALLBACK_MGR = FallbackManager()

# All GA output field codes (superset of mandatory; non-mandatory included for
# completeness of the output document).
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
    log_audit_event(db, "STAGE_STARTED", project_id=project_id, stage_code="P2-04")
    update_stage_result(
        db, project_id=project_id, stage_code="P2-04", status=StageStatus.RUNNING
    )

    # 1. Conflict-resolved field map (consistent with P2-03)
    resolved_map = build_resolved_field_map(db, project_id)
    field_map: dict[str, str] = {
        fc: str(cr.winning_value)
        for fc, cr in resolved_map.items()
        if cr.winning_value is not None
    }

    ga_codes = set(fetch_ga_required_field_codes())

    # 2. Supplement with FallbackManager for missing mandatory GA codes.
    missing_before_fallback = sorted(fc for fc in ga_codes if fc not in field_map)
    if missing_before_fallback:
        fallback_report = _FALLBACK_MGR.apply_fallbacks(
            project_id=project_id,
            missing_codes=missing_before_fallback,
            db=db,
        )
        for outcome in fallback_report.applied:
            if (
                outcome.resolved
                and outcome.resolved_value is not None
                and outcome.resolved_value != ""
            ):
                field_map[outcome.field_code] = outcome.resolved_value
                log_audit_event(
                    db, "FALLBACK_APPLIED", project_id=project_id,
                    field_code=outcome.field_code,
                    detail={
                        "strategy": outcome.strategy,
                        "value": outcome.resolved_value,
                        "source": outcome.resolved_source,
                        "stage": "P2-04",
                    },
                )

    missing_ga = sorted(fc for fc in ga_codes if fc not in field_map)

    # 3. Hard gate — FAIL if any mandatory GA field is still missing.
    if missing_ga:
        gate_status = "FAIL"
        gate_data = {
            "total_ga_required": len(ga_codes),
            "resolved_count": len(ga_codes) - len(missing_ga),
            "missing_count": len(missing_ga),
            "missing_codes": missing_ga,
        }
        _CHECKPOINT_MGR.record(
            db, project_id=project_id, stage_code="P2-04",
            label="GA Generation Gate", gate_status=gate_status,
            gate_data=gate_data,
        )
        result = {
            "project_id": str(project_id),
            "status": "BLOCKED",
            "gate_status": "FAIL",
            "field_summary": gate_data,
            "overall": "BLOCKED",
            "main_output": "reports/p2-04_summary.json",
        }
        write_processed_json(project_id, "p2-04_summary.json", result)
        update_stage_result(
            db, project_id=project_id, stage_code="P2-04",
            status=StageStatus.BLOCKED, result=result,
        )
        log_audit_event(
            db, "STAGE_BLOCKED", project_id=project_id, stage_code="P2-04",
            detail={"missing_codes": missing_ga, "gate_status": "FAIL"},
        )
        logger.warning("P2-04 BLOCKED: missing mandatory GA fields: %s", missing_ga)
        return result

    # 4. Gate PASS — all mandatory GA fields present.
    _CHECKPOINT_MGR.record(
        db, project_id=project_id, stage_code="P2-04",
        label="GA Generation Gate", gate_status="PASS",
        gate_data={"total_ga_required": len(ga_codes), "resolved_count": len(ga_codes)},
    )

    payload = {
        "project_id": str(project_id),
        "output_type": "GA",
        "general_arrangement_fields": {
            code: field_map[code] for code in GA_FIELD_CODES if code in field_map
        },
        "source_field_count": len(field_map),
        "status": "draft_generated",
        "gate_status": "PASS",
        "main_output": "reports/p2-04_summary.json",
    }
    write_processed_json(project_id, "p2-04_summary.json", payload)
    output_path = write_json_output(project_id, "ga", "general_arrangement.json", payload)
    result = {**payload, "output_path": str(output_path)}

    update_stage_result(
        db, project_id=project_id, stage_code="P2-04",
        status=StageStatus.PASSED, result=result,
    )
    log_audit_event(
        db, "STAGE_PASSED", project_id=project_id, stage_code="P2-04",
        detail={
            "ga_fields_populated": len(payload["general_arrangement_fields"]),
            "total_ga_required": len(ga_codes),
        },
    )
    trace_action(
        db, project_id, "p2_04_ga_generated",
        {
            "field_count": len(payload["general_arrangement_fields"]),
            "output_path": str(output_path),
        },
    )
    logger.info(
        "P2-04 GA generation PASS: %d of %d GA fields present",
        len(payload["general_arrangement_fields"]), len(ga_codes),
    )
    return result
