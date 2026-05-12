"""Generate a Daily Automated Report from system-of-record tables.

Section sources (all scoped to today's date window unless noted):
  header                  — projects
  execution_summary       — stages (today), validation_results (all), correction_events (today)
  lane_summary            — stages (current state snapshot)
  stage_detail            — stages (current state snapshot)
  gate_snapshot           — stage_checkpoints (current state snapshot)
  severity_summary        — validation_results (all, current)
  top_blockers            — validation_results (MISSING/SUSPICIOUS or CRITICAL)
  manual_review_summary   — escalations (all open/resolved)
  source_fallback_summary — parser_runs + extracted_field_values (all)
  defect_summary          — escalations (all)
  audit_events_today      — audit_event_log (today only)
  next_day_critical_path  — stages (FAILED/BLOCKED) + validation_results (CRITICAL MISSING)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import CorrectionEvent
from app.reports.collector import (
    BUILD_VERSION,
    _field_description,
    collect_audit_events,
    collect_project_snapshot,
    gate_snapshot,
    lane_summary,
    manual_review_summary,
    next_day_critical_path,
    severity_summary,
    source_fallback_summary,
    top_blockers,
)


def generate_daily_report(
    db: Session,
    project_id: UUID,
    report_date: date | None = None,
    generated_by: str = "system",
) -> dict:
    if report_date is None:
        report_date = date.today()

    day_start = datetime.combine(report_date, datetime.min.time())
    day_end   = day_start + timedelta(days=1)

    snap = collect_project_snapshot(db, project_id)
    if not snap:
        return {"error": "Project not found", "project_id": str(project_id)}

    project      = snap["project"]
    stages       = snap["stages"]
    validations  = snap["validations"]
    checkpoints  = snap["checkpoints"]
    escalations  = snap["escalations"]
    parser_runs  = snap["parser_runs"]
    field_values = snap["field_values"]
    files        = snap["files"]

    audit_today = collect_audit_events(db, project_id, day_start, day_end)

    # ── Gap 8 fix: today-only stage activity counts ──────────────────────────
    stages_run_today   = [s for s in stages if s.started_at and day_start <= s.started_at < day_end]
    reruns_today       = [s for s in stages_run_today if (s.revision or 1) > 1]
    gates_touched      = len(set(cp.stage_code for cp in checkpoints))

    # ── Gap 5 fix: corrections applied today ────────────────────────────────
    corrections_today = (
        db.query(CorrectionEvent)
        .filter(
            CorrectionEvent.project_id == project_id,
            CorrectionEvent.created_at >= day_start,
            CorrectionEvent.created_at < day_end,
        )
        .all()
    )

    # File counts
    file_total  = len(files)
    file_parsed = sum(1 for f in files if f.processing_status.value in ("PARSED", "EXTRACTED"))
    file_failed = sum(1 for f in files if f.processing_status.value == "FAILED")

    report = {
        # ── Header ─────────────────────────────────────────────────────────────
        "header": {
            "report_type":    "DAILY",
            "date":           report_date.isoformat(),
            "project_uuid":   str(project.id),
            "proposal_id":    project.proposal_id,
            "project_name":   project.name,
            "project_status": project.status.value,
            "build_version":  BUILD_VERSION,
            "generated_at":   datetime.utcnow().isoformat(),
            "generated_by":   generated_by,
        },

        # ── Execution Summary (today-scoped where possible) ─────────────────
        "execution_summary": {
            "tasks_run_today":         len(stages_run_today),
            "reruns_today":            len(reruns_today),
            "rules_evaluated_total":   len(validations),
            "gates_touched_total":     gates_touched,
            "corrections_today":       len(corrections_today),
            "audit_events_today":      len(audit_today),
            "files_total":             file_total,
            "files_parsed":            file_parsed,
            "files_failed":            file_failed,
        },

        # ── Lane Summary ────────────────────────────────────────────────────
        "lane_summary": lane_summary(stages),

        # ── Stage Detail ────────────────────────────────────────────────────
        "stage_detail": [
            {
                "stage_code":    s.stage_code,
                "status":        s.status.value,
                "revision":      s.revision or 1,
                "started_at":    s.started_at.isoformat() if s.started_at else None,
                "completed_at":  s.completed_at.isoformat() if s.completed_at else None,
                "error_message": s.error_message,
                "ran_today":     bool(s.started_at and day_start <= s.started_at < day_end),
            }
            for s in stages
        ],

        # ── Gate Snapshot ───────────────────────────────────────────────────
        "gate_snapshot": gate_snapshot(checkpoints),

        # ── Severity Summary ────────────────────────────────────────────────
        "severity_summary": severity_summary(validations),

        # ── Top Blockers ────────────────────────────────────────────────────
        "top_blockers": top_blockers(validations),

        # ── Manual Review Summary ───────────────────────────────────────────
        "manual_review_summary": manual_review_summary(escalations),

        # ── Source / Fallback Summary ───────────────────────────────────────
        "source_fallback_summary": source_fallback_summary(parser_runs, field_values),

        # ── Defect Summary ──────────────────────────────────────────────────
        "defect_summary": {
            "total_escalations": len(escalations),
            "open":              sum(1 for e in escalations if e.status == "OPEN"),
            "resolved":          sum(1 for e in escalations if e.status == "RESOLVED"),
            "critical_open":     sum(1 for e in escalations if e.status == "OPEN" and e.severity == "CRITICAL"),
            "by_severity": {
                "CRITICAL": sum(1 for e in escalations if e.severity == "CRITICAL"),
                "MAJOR":    sum(1 for e in escalations if e.severity == "MAJOR"),
                "MINOR":    sum(1 for e in escalations if e.severity == "MINOR"),
            },
        },

        # ── Corrections Applied Today (Gap 5) ───────────────────────────────
        "corrections_today": [
            {
                "field_code":      c.field_code,
                "stage_code":      c.stage_code,
                "original_value":  c.original_value,
                "corrected_value": c.corrected_value,
                "source":          c.source,
            }
            for c in corrections_today
        ],

        # ── Audit Events Today ──────────────────────────────────────────────
        "audit_events_today": [
            {
                "event_type": e.event_type,
                "actor":      e.actor,
                "stage_code": e.stage_code,
                "field_code": e.field_code,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in audit_today
        ],

        # ── Next-Day Critical Path ──────────────────────────────────────────
        "next_day_critical_path": next_day_critical_path(stages, validations),

        # ── P2-02 Parse Failures — fields not extracted from source files ───
        # Lists every field P2-02 recorded as MISSING/FAILED, with field_id
        # and description so the reader knows exactly what was not resolved.
        "p2_02_parse_failures": [
            {
                "field_id":    v.field_code,
                "description": _field_description(v.field_code),
                "status":      v.status,
                "severity":    v.severity,
                "source":      v.source,
                "note":        v.note,
            }
            for v in validations
            if v.stage_code == "P2-02" and v.status in ("MISSING", "FAILED", "SUSPICIOUS")
        ],
    }

    return report
