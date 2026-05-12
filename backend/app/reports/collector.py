"""Collect raw state from all source-of-record SQLite tables for report generation."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    AuditEventLog,
    CorrectionEvent,
    Escalation,
    ExtractedFieldValue,
    Handoff,
    ParserRun,
    Project,
    ProjectFile,
    Stage,
    StageCheckpoint,
    ValidationResult,
)


def _field_description(field_code: str) -> str:
    """Return the human-readable field name for a field code, or the code itself."""
    try:
        from app.utils.field_dictionary import get_field_dictionary
        dictionary = get_field_dictionary()
        by_code = getattr(dictionary, "_fields_by_code", {}) or {}
        defn = by_code.get(field_code) or by_code.get(str(field_code).upper()) or by_code.get(str(field_code).lower())
        return defn.standard_field_name if defn else field_code
    except Exception:
        return field_code

BUILD_VERSION = "2.0"

# ---------------------------------------------------------------------------
# Lane definitions (Lane 1–4)
# ---------------------------------------------------------------------------
LANE_MAP = {
    "Lane 1 - Ingestion":     ["P2-01"],
    "Lane 2 - Completeness":  ["P2-02"],
    "Lane 3 - Generation":    ["P2-03", "P2-04"],
    "Lane 4 - Validation":    ["P2-05"],
}


def _ser(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    return str(obj)


def collect_project_snapshot(db: Session, project_id: UUID) -> dict:
    """Full current-state snapshot for one project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {}

    stages       = db.query(Stage).filter(Stage.project_id == project_id).order_by(Stage.stage_code).all()
    validations  = db.query(ValidationResult).filter(ValidationResult.project_id == project_id).all()
    checkpoints  = db.query(StageCheckpoint).filter(StageCheckpoint.project_id == project_id).all()
    escalations  = db.query(Escalation).filter(Escalation.project_id == project_id).all()
    corrections  = db.query(CorrectionEvent).filter(CorrectionEvent.project_id == project_id).all()
    handoffs     = db.query(Handoff).filter(Handoff.project_id == project_id).all()
    files        = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
    parser_runs  = db.query(ParserRun).filter(ParserRun.project_id == project_id).all()
    field_values = db.query(ExtractedFieldValue).filter(ExtractedFieldValue.project_id == project_id).all()

    return {
        "project":      project,
        "stages":       stages,
        "validations":  validations,
        "checkpoints":  checkpoints,
        "escalations":  escalations,
        "corrections":  corrections,
        "handoffs":     handoffs,
        "files":        files,
        "parser_runs":  parser_runs,
        "field_values": field_values,
    }


def collect_audit_events(
    db: Session,
    project_id: Optional[UUID],
    from_dt: datetime,
    to_dt: datetime,
) -> list:
    q = db.query(AuditEventLog).filter(
        AuditEventLog.created_at >= from_dt,
        AuditEventLog.created_at < to_dt,
    )
    if project_id:
        q = q.filter(AuditEventLog.project_id == project_id)
    return q.order_by(AuditEventLog.created_at).all()


def collect_date_range_validations(
    db: Session,
    project_id: Optional[UUID],
    from_dt: datetime,
    to_dt: datetime,
) -> list:
    q = db.query(ValidationResult).filter(
        ValidationResult.created_at >= from_dt,
        ValidationResult.created_at < to_dt,
    )
    if project_id:
        q = q.filter(ValidationResult.project_id == project_id)
    return q.all()


def collect_date_range_escalations(
    db: Session,
    project_id: Optional[UUID],
    from_dt: datetime,
    to_dt: datetime,
) -> list:
    q = db.query(Escalation).filter(
        Escalation.created_at >= from_dt,
        Escalation.created_at < to_dt,
    )
    if project_id:
        q = q.filter(Escalation.project_id == project_id)
    return q.all()


# ---------------------------------------------------------------------------
# Helpers used by report generators
# ---------------------------------------------------------------------------

def lane_summary(stages: list) -> dict:
    stage_map = {s.stage_code: s for s in stages}
    result = {}
    for lane_name, codes in LANE_MAP.items():
        statuses = [stage_map[c].status.value if c in stage_map else "PENDING" for c in codes]
        if "FAILED" in statuses or "BLOCKED" in statuses:
            overall = "BLOCKED" if "BLOCKED" in statuses else "FAILED"
        elif all(s in ("PASSED", "PASS_WITH_WARNINGS") for s in statuses):
            overall = "PASSED"
        elif any(s == "RUNNING" for s in statuses):
            overall = "IN_PROGRESS"
        elif all(s == "PENDING" for s in statuses):
            overall = "PENDING"
        else:
            overall = "IN_PROGRESS"
        result[lane_name] = {"stages": codes, "statuses": statuses, "overall": overall}
    return result


def gate_snapshot(checkpoints: list) -> dict:
    gates: dict = {}
    for cp in checkpoints:
        key = f"{cp.stage_code} – {cp.checkpoint_label}"
        gates[key] = {
            "stage_code":       cp.stage_code,
            "checkpoint_label": cp.checkpoint_label,
            "gate_status":      cp.gate_status,
            "created_at":       cp.created_at.isoformat() if cp.created_at else None,
        }
    return gates


def severity_summary(validations: list) -> dict:
    counts = {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0, "release_blockers": 0}
    for v in validations:
        sev = v.severity.upper() if v.severity else "MINOR"
        if sev in counts:
            counts[sev] += 1
        if v.status == "MISSING" and sev == "CRITICAL":
            counts["release_blockers"] += 1
    return counts


def top_blockers(validations: list, limit: int = 10) -> list:
    blockers = [
        v for v in validations
        if v.status in ("MISSING", "SUSPICIOUS") or v.severity == "CRITICAL"
    ]
    blockers.sort(key=lambda v: (0 if v.severity == "CRITICAL" else 1, v.field_code))
    return [
        {
            "field_id":    v.field_code,
            "field_code":  v.field_code,
            "description": _field_description(v.field_code),
            "stage_code":  v.stage_code,
            "status":      v.status,
            "severity":    v.severity,
            "note":        v.note,
            "source":      v.source,
        }
        for v in blockers[:limit]
    ]


def manual_review_summary(escalations: list) -> dict:
    open_esc   = [e for e in escalations if e.status == "OPEN"]
    closed_esc = [e for e in escalations if e.status == "RESOLVED"]
    return {
        "total":    len(escalations),
        "open":     len(open_esc),
        "resolved": len(closed_esc),
        "open_items": [
            {"id": str(e.id), "stage_code": e.stage_code, "severity": e.severity, "reason": e.reason}
            for e in open_esc
        ],
    }


def source_fallback_summary(parser_runs: list, field_values: list) -> dict:
    total_runs = len(parser_runs)
    success    = sum(1 for p in parser_runs if p.status.value == "SUCCESS")
    failed     = total_runs - success
    avg_conf   = round(sum(p.confidence for p in parser_runs) / total_runs, 1) if total_runs else 0

    source_counts: dict = {}
    for fv in field_values:
        src = fv.source_path.split("/")[0] if fv.source_path else "unknown"
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "parser_runs_total":   total_runs,
        "parser_runs_success": success,
        "parser_runs_failed":  failed,
        "avg_confidence":      avg_conf,
        "source_distribution": source_counts,
    }


def next_day_critical_path(stages: list, validations: list) -> dict:
    blocked_stages = [
        {"stage_code": s.stage_code, "status": s.status.value, "error": s.error_message}
        for s in stages
        if s.status.value in ("FAILED", "BLOCKED")
    ]
    critical_missing = [
        {
            "field_id":    v.field_code,
            "field_code":  v.field_code,
            "description": _field_description(v.field_code),
            "stage_code":  v.stage_code,
            "note":        v.note,
        }
        for v in validations
        if v.status == "MISSING" and v.severity == "CRITICAL"
    ]
    return {
        "blocked_stages":    blocked_stages,
        "critical_missing":  critical_missing,
        "action_required":   bool(blocked_stages or critical_missing),
    }
