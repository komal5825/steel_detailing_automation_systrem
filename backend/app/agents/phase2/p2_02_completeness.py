"""
P2-02 Completeness Checker — Phase 2 Step 13.

Workflow:
  1. Build conflict-resolved field map from all extracted values (Step 14).
  2. Compare resolved codes against AB-required and GA-required field codes.
  3. Run fallback policy for missing codes (Step 15).
  4. Persist per-field ValidationResult records (Step 13 CRUD).
  5. Write completeness_matrix.json to Processed/ (Step 16 file output).
  6. Write a Hard-Gate checkpoint via CheckpointManager (Step 16).
  7. Emit audit events and update the Stage record.

Returns a dict summary that downstream agents and API endpoints can consume.
Gate blocks if any AB-required OR GA-required mandatory field is still missing.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import write_json_output, write_processed_json
from app.agents.support.checkpoint import CheckpointManager
from app.agents.support.fallback import FallbackManager
from app.db.crud.stages import update_stage_result
from app.db.crud.validation import log_audit_event, save_validation_items
from app.db.models import StageStatus
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger
from app.utils.field_completion_engine import (
    FieldCompletionEngine,
    build_extraction_readiness_report,
    build_fallback_invocation_log,
    build_missing_field_report,
)
from app.utils.master_db import (
    fetch_ab_required_field_codes,
    fetch_ga_required_field_codes,
    fetch_mandatory_field_codes,
)
from app.utils.source_priority import build_resolved_field_map

logger = get_logger(__name__)

_CHECKPOINT_MGR = CheckpointManager()
_FALLBACK_MGR = FallbackManager()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------

def _check_completeness(project_id: UUID, db: Session) -> dict:
    log_audit_event(db, "STAGE_STARTED", project_id=project_id, stage_code="P2-02")
    update_stage_result(db, project_id=project_id, stage_code="P2-02",
                        status=StageStatus.RUNNING)

    # ---- 1. Build conflict-resolved field map ----
    resolved_map = build_resolved_field_map(db, project_id)
    resolved_codes = set(resolved_map.keys())

    # ---- 2. Load AB, GA, and overall mandatory code sets ----
    all_mandatory_codes = set(fetch_mandatory_field_codes())
    ab_required_codes = set(fetch_ab_required_field_codes())
    ga_required_codes = set(fetch_ga_required_field_codes())

    # Fields missing from resolved extraction
    ab_missing_raw = sorted(ab_required_codes - resolved_codes)
    ga_missing_raw = sorted(ga_required_codes - resolved_codes)
    all_missing_raw = sorted(all_mandatory_codes - resolved_codes)

    # ---- 3. Fallback for ALL missing mandatory codes (deduped union) ----
    union_missing = sorted(set(all_missing_raw) | set(ab_missing_raw) | set(ga_missing_raw))
    fallback_report = _FALLBACK_MGR.apply_fallbacks(
        project_id=project_id,
        missing_codes=union_missing,
        db=db,
    )

    unresolved_set = set(
        fallback_report.unresolved_human_fields + fallback_report.unresolved_skip_fields
    )
    fallback_resolved_set = set(union_missing) - unresolved_set

    # ---- 4. Per-output-class still-missing sets ----
    ab_still_missing = sorted(c for c in ab_missing_raw if c in unresolved_set)
    ga_still_missing = sorted(c for c in ga_missing_raw if c in unresolved_set)

    # ---- 5. Persist ValidationResult rows ----
    validation_items: list[dict] = []

    # Present mandatory fields
    for fc in sorted(all_mandatory_codes & resolved_codes):
        cr = resolved_map[fc]
        item = {
            "field_code": fc,
            "status": "PRESENT",
            "severity": "MINOR",
            "source": cr.winning_source,
            "value": cr.winning_value,
            "note": f"strategy={cr.resolution_strategy}",
        }
        if cr.conflict_detected and not cr.requires_human:
            item["status"] = "SUSPICIOUS"
            item["note"] = (
                f"Conflict auto-resolved via {cr.resolution_strategy}. "
                f"Candidates: {cr.candidates}"
            )
        validation_items.append(item)

    # Fallback-resolved fields
    for fc in sorted(fallback_resolved_set):
        outcome = next((o for o in fallback_report.applied if o.field_code == fc), None)
        validation_items.append({
            "field_code": fc,
            "status": "PRESENT",
            "severity": "MINOR",
            "source": outcome.resolved_source if outcome else "FALLBACK",
            "value": outcome.resolved_value if outcome else "",
            "note": outcome.note if outcome else "Resolved via fallback",
        })

    # Still-missing mandatory fields
    for fc in sorted(unresolved_set & all_mandatory_codes):
        outcome = next((o for o in fallback_report.applied if o.field_code == fc), None)
        validation_items.append({
            "field_code": fc,
            "status": "MISSING",
            "severity": "CRITICAL",
            "source": None,
            "value": None,
            "note": outcome.note if outcome else "Not found in any source",
        })

    # Non-blocking warnings: fields in resolved_map that have conflict but aren't mandatory
    non_blocking_warnings = []
    for fc, cr in resolved_map.items():
        if fc not in all_mandatory_codes and cr.conflict_detected:
            non_blocking_warnings.append({
                "field_code": fc,
                "note": (
                    f"Non-mandatory conflict auto-resolved via {cr.resolution_strategy}. "
                    f"Candidates: {cr.candidates}"
                ),
            })

    save_validation_items(db, project_id, "P2-02", validation_items)

    # ---- 6. Build AB/GA readiness matrices ----
    ab_readiness = _build_readiness_matrix(
        label="AB",
        required_codes=ab_required_codes,
        resolved_codes=resolved_codes,
        fallback_resolved_set=fallback_resolved_set,
        still_missing=ab_still_missing,
        resolved_map=resolved_map,
        fallback_report=fallback_report,
    )
    ga_readiness = _build_readiness_matrix(
        label="GA",
        required_codes=ga_required_codes,
        resolved_codes=resolved_codes,
        fallback_resolved_set=fallback_resolved_set,
        still_missing=ga_still_missing,
        resolved_map=resolved_map,
        fallback_report=fallback_report,
    )

    # ---- 7. Gate decision ----
    # Deduplicate: a field missing for both AB and GA counts once for the gate
    unique_blockers = sorted(set(ab_still_missing) | set(ga_still_missing))
    is_complete = len(unique_blockers) == 0
    gate_status = "PASS" if is_complete else "FAIL"

    # ---- 8. Full 196-field completion engine (hard-stop gate) ----
    completion_report = FieldCompletionEngine(resolved_map, db, project_id).run()

    missing_field_report = build_missing_field_report(completion_report)
    fallback_log = build_fallback_invocation_log(completion_report)
    readiness_report = build_extraction_readiness_report(completion_report)

    field_completion_dict = completion_report.to_dict()
    write_processed_json(project_id, "field_completion_matrix.json", field_completion_dict)
    write_processed_json(project_id, "missing_field_report.json", missing_field_report)
    write_processed_json(project_id, "fallback_invocation_log.json", fallback_log)
    write_processed_json(project_id, "extraction_readiness_report.json", readiness_report)
    write_json_output(project_id, "p2_02", "field_completion_matrix.json", field_completion_dict)
    write_json_output(project_id, "p2_02", "missing_field_report.json", missing_field_report)
    write_json_output(project_id, "p2_02", "fallback_invocation_log.json", fallback_log)
    write_json_output(project_id, "p2_02", "extraction_readiness_report.json", readiness_report)

    logger.info(
        "Field completion (all 196): extracted=%d calculated=%d fallback=%d failed=%d | "
        "invariant=%s",
        completion_report.extracted_count,
        completion_report.calculated_count,
        completion_report.fallback_count,
        completion_report.failed_count,
        completion_report.invariant_holds,
    )

    # ---- 9. Write completeness_matrix.json to Processed/ ----
    matrix_payload: dict = {
        "project_id": str(project_id),
        "ab_readiness": ab_readiness,
        "ga_readiness": ga_readiness,
        "blocking_issues": [
            {
                "field_code": fc,
                "affects": _which_outputs(fc, ab_still_missing, ga_still_missing),
                "severity": "CRITICAL",
                "note": next(
                    (i["note"] for i in validation_items if i["field_code"] == fc), ""
                ),
            }
            for fc in unique_blockers
        ],
        "non_blocking_warnings": non_blocking_warnings,
        "human_review_required": fallback_report.unresolved_human_fields,
        "gate_status": gate_status,
        "overall": "PASS" if is_complete else "BLOCKED",
        "field_completion_summary": completion_report.summary_table(),
    }
    write_processed_json(project_id, "completeness_matrix.json", matrix_payload)
    # Agent-dir copy written later (after result is built) to include full result context

    # ---- 10. Hard-gate checkpoint ----
    _CHECKPOINT_MGR.record(
        db,
        project_id=project_id,
        stage_code="P2-02",
        label="Completeness Hard Gate",
        gate_status=gate_status,
        gate_data={
            "ab_missing": ab_still_missing,
            "ga_missing": ga_still_missing,
            "fallback_resolved_count": len(fallback_resolved_set),
            "non_blocking_warnings_count": len(non_blocking_warnings),
            "total_fields_processed": completion_report.total_fields,
            "extracted": completion_report.extracted_count,
            "calculated": completion_report.calculated_count,
            "fallback": completion_report.fallback_count,
            "failed": completion_report.failed_count,
            "invariant_holds": completion_report.invariant_holds,
        },
    )

    # ---- 11. Stage result + audit ----
    failed_ids = completion_report.failed_field_ids()
    p2_02_warnings = []
    if failed_ids:
        p2_02_warnings.append({
            "status": "Warning",
            "agent": "P2-02",
            "title": "Unresolved Fields Detected",
            "issue": (
                f"{len(failed_ids)} field(s) could not be resolved from source files, "
                f"derivation, or fallback defaults"
            ),
            "affected_fields": failed_ids,
            "root_cause": (
                "Fields not extracted from source files and no system default or fallback rule "
                "available. These may be optional/conditional or require manual entry."
            ),
            "recommended_fix": (
                "Provide missing values via the Field Review panel, or upload a more complete "
                "source file. Download missing_field_report.json for per-field remediation guidance."
            ),
            "can_continue": is_complete,
            "severity": "MINOR" if is_complete else "CRITICAL",
        })

    result = {
        "project_id": str(project_id),
        "ab_readiness": ab_readiness,
        "ga_readiness": ga_readiness,
        "blocking_issues_count": len(unique_blockers),
        "blocking_issues": unique_blockers,
        "non_blocking_warnings_count": len(non_blocking_warnings),
        "human_review_required": fallback_report.unresolved_human_fields,
        "is_complete": is_complete,
        "overall": "PASS" if is_complete else "BLOCKED",
        "field_completion": {
            "Extracted":  completion_report.extracted_count,
            "Calculated": completion_report.calculated_count,
            "Fallback":   completion_report.fallback_count,
            "Failed":     completion_report.failed_count,
            "Total":      completion_report.total_fields,
        },
        "hard_stop_satisfied": completion_report.invariant_holds,
        "failed_field_ids": failed_ids,
        "warnings": p2_02_warnings,
        "warnings_count": len(p2_02_warnings),
        "main_output": "reports/p2-02_summary.json",
        "outputs": {
            "field_completion_matrix":    "reports/field_completion_matrix.json",
            "missing_field_report":       "reports/missing_field_report.json",
            "fallback_invocation_log":    "reports/fallback_invocation_log.json",
            "extraction_readiness_report":"reports/extraction_readiness_report.json",
        },
    }
    write_processed_json(project_id, "p2-02_summary.json", result)
    write_json_output(project_id, "p2_02", "p2-02_summary.json", result)
    write_json_output(project_id, "p2_02", "completeness_matrix.json", matrix_payload)

    # PASS_WITH_WARNINGS when gate passes but some fields remain unresolved
    if not is_complete:
        stage_status = StageStatus.BLOCKED
    elif failed_ids:
        stage_status = StageStatus.PASS_WITH_WARNINGS
    else:
        stage_status = StageStatus.PASSED
    update_stage_result(
        db,
        project_id=project_id,
        stage_code="P2-02",
        status=stage_status,
        result=result,
    )
    log_audit_event(
        db,
        "STAGE_PASSED" if is_complete else "STAGE_BLOCKED",
        project_id=project_id,
        stage_code="P2-02",
        detail={
            "ab_missing_count": len(ab_still_missing),
            "ga_missing_count": len(ga_still_missing),
            "gate_status": gate_status,
        },
    )
    logger.info(
        "P2-02 completeness: AB missing=%d, GA missing=%d, "
        "fallback_resolved=%d, warnings=%d — gate=%s",
        len(ab_still_missing), len(ga_still_missing),
        len(fallback_resolved_set), len(non_blocking_warnings), gate_status,
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_readiness_matrix(
    label: str,
    required_codes: set[str],
    resolved_codes: set[str],
    fallback_resolved_set: set[str],
    still_missing: list[str],
    resolved_map: dict,
    fallback_report,
) -> dict:
    present = sorted(
        (required_codes & resolved_codes)
        | (required_codes & fallback_resolved_set)
    )
    fields_detail: dict[str, dict] = {}
    for fc in present:
        if fc in resolved_map:
            cr = resolved_map[fc]
            fields_detail[fc] = {
                "status": "SUSPICIOUS" if cr.conflict_detected else "PRESENT",
                "source": cr.winning_source,
                "value": cr.winning_value,
            }
        else:
            outcome = next((o for o in fallback_report.applied if o.field_code == fc), None)
            fields_detail[fc] = {
                "status": "PRESENT",
                "source": outcome.resolved_source if outcome else "FALLBACK",
                "value": outcome.resolved_value if outcome else "",
            }
    for fc in still_missing:
        fields_detail[fc] = {"status": "MISSING", "source": None, "value": None}

    return {
        "output": label,
        "required_count": len(required_codes),
        "present_count": len(present),
        "missing_count": len(still_missing),
        "missing_codes": still_missing,
        "status": "READY" if not still_missing else "BLOCKED",
        "fields": fields_detail,
    }


def _which_outputs(fc: str, ab_missing: list[str], ga_missing: list[str]) -> list[str]:
    outputs = []
    if fc in ab_missing:
        outputs.append("AB")
    if fc in ga_missing:
        outputs.append("GA")
    return outputs
