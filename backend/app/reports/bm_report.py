"""Generate a BM-001 Build Milestone Report (Phase 2 complete gate)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import StageStatus
from app.reports.collector import (
    BUILD_VERSION,
    collect_project_snapshot,
    gate_snapshot,
    lane_summary,
    manual_review_summary,
    severity_summary,
    source_fallback_summary,
    top_blockers,
)


def generate_bm_report(
    db: Session,
    project_id: UUID,
    generated_by: str = "system",
) -> dict:
    snap = collect_project_snapshot(db, project_id)
    if not snap:
        return {"error": "Project not found", "project_id": str(project_id)}

    project     = snap["project"]
    stages      = snap["stages"]
    validations = snap["validations"]
    checkpoints = snap["checkpoints"]
    escalations = snap["escalations"]
    corrections = snap["corrections"]
    parser_runs = snap["parser_runs"]
    field_values = snap["field_values"]
    files       = snap["files"]
    handoffs    = snap["handoffs"]

    required_stages = ["P2-01", "P2-02", "P2-03", "P2-04", "P2-05"]
    stage_map = {s.stage_code: s for s in stages}
    _passed = {StageStatus.PASSED, StageStatus.PASS_WITH_WARNINGS}

    stages_passed  = [sc for sc in required_stages if sc in stage_map and stage_map[sc].status in _passed]
    stages_blocked = [sc for sc in required_stages if sc in stage_map and stage_map[sc].status not in _passed]
    not_passed     = [sc for sc in required_stages if stage_map.get(sc) is None or stage_map[sc].status not in _passed]

    gate_results   = gate_snapshot(checkpoints)
    all_gates_pass = all(v["gate_status"] == "PASS" for v in gate_results.values()) if gate_results else False

    present_fields  = [v for v in validations if v.status == "PRESENT"]
    missing_fields  = [v for v in validations if v.status == "MISSING"]
    critical_missing = [v for v in missing_fields if v.severity == "CRITICAL"]

    gate5_eligible  = len(not_passed) == 0
    bm001_authorized = gate5_eligible and not critical_missing and all_gates_pass

    hold_reasons: list[str] = []
    if not gate5_eligible:
        hold_reasons.append(f"Stages not passed: {', '.join(not_passed)}")
    if critical_missing:
        hold_reasons.append(f"{len(critical_missing)} critical field(s) still missing: "
                            f"{', '.join(v.field_code for v in critical_missing)}")
    if not all_gates_pass:
        failed_gates = [k for k, v in gate_results.items() if v["gate_status"] != "PASS"]
        hold_reasons.append(f"Gate(s) did not PASS: {', '.join(failed_gates)}")

    return {
        "header": {
            "report_type":      "BM",
            "milestone":        "BM-001",
            "milestone_title":  "First Build Milestone — Phase 2 Complete",
            "project_uuid":     str(project.id),
            "proposal_id":      project.proposal_id,
            "project_name":     project.name,
            "project_status":   project.status.value,
            "build_version":    BUILD_VERSION,
            "generated_at":     datetime.utcnow().isoformat(),
            "generated_by":     generated_by,
        },

        "authorization_gate": {
            "bm001_authorized":           bm001_authorized,
            "gate5_eligible":             gate5_eligible,
            "all_pipeline_gates_pass":    all_gates_pass,
            "critical_missing_count":     len(critical_missing),
            "hold_reasons":               hold_reasons,
            "verdict":                    "AUTHORIZED" if bm001_authorized else "HOLD",
        },

        "pipeline_summary": {
            "required_stages":    required_stages,
            "stages_passed":      stages_passed,
            "stages_blocked":     stages_blocked,
            "all_stages_complete": len(not_passed) == 0,
        },

        "stage_detail": [
            {
                "stage_code":    s.stage_code,
                "status":        s.status.value,
                "revision":      s.revision or 1,
                "started_at":    s.started_at.isoformat() if s.started_at else None,
                "completed_at":  s.completed_at.isoformat() if s.completed_at else None,
                "error_message": s.error_message,
            }
            for s in stages
        ],

        "gate_results":  gate_results,
        "lane_summary":  lane_summary(stages),

        "field_completeness": {
            "total_validated":        len(validations),
            "present_count":          len(present_fields),
            "missing_count":          len(missing_fields),
            "critical_missing_count": len(critical_missing),
            "critical_missing_codes": [v.field_code for v in critical_missing],
            "completeness_pct":       round(
                len(present_fields) / len(validations) * 100, 1
            ) if validations else 0.0,
        },

        "severity_summary":  severity_summary(validations),
        "top_blockers":      top_blockers(validations),
        "source_extraction": source_fallback_summary(parser_runs, field_values),

        "file_intake": {
            "total_files": len(files),
            "parsed":  sum(1 for f in files if f.processing_status.value in ("PARSED", "EXTRACTED")),
            "failed":  sum(1 for f in files if f.processing_status.value == "FAILED"),
            "files": [
                {
                    "original_filename":        f.original_filename,
                    "file_type":                f.file_type,
                    "processing_status":        f.processing_status.value,
                    "classification_confidence": f.classification_confidence,
                }
                for f in files
            ],
        },

        "defect_register": {
            "total_escalations": len(escalations),
            "open":         sum(1 for e in escalations if e.status == "OPEN"),
            "resolved":     sum(1 for e in escalations if e.status == "RESOLVED"),
            "critical_open": sum(1 for e in escalations if e.status == "OPEN" and e.severity == "CRITICAL"),
            "total_corrections": len(corrections),
            "escalations": [
                {
                    "id":          str(e.id),
                    "stage_code":  e.stage_code,
                    "severity":    e.severity,
                    "reason":      e.reason,
                    "status":      e.status,
                    "created_at":  e.created_at.isoformat() if e.created_at else None,
                    "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
                }
                for e in escalations
            ],
            "corrections": [
                {
                    "field_code":       c.field_code,
                    "stage_code":       c.stage_code,
                    "original_value":   c.original_value,
                    "corrected_value":  c.corrected_value,
                    "source":           c.source,
                    "created_at":       c.created_at.isoformat() if c.created_at else None,
                }
                for c in corrections
            ],
        },

        "handoff_status": {
            "handoffs_created": len(handoffs),
            "approved": sum(1 for h in handoffs if h.approved == 1),
            "pending":  sum(1 for h in handoffs if h.approved == 0),
            "rejected": sum(1 for h in handoffs if h.approved == -1),
        },

        "manual_review": manual_review_summary(escalations),
    }
