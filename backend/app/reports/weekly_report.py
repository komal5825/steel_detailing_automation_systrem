"""Generate a Weekly Roll-up Report from Daily source tables."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    AuditEventLog,
    Escalation,
    ParserRun,
    Stage,
    StageCheckpoint,
    ValidationResult,
    Project,
)
from app.reports.collector import (
    BUILD_VERSION,
    collect_audit_events,
    collect_project_snapshot,
    severity_summary,
)


def _week_bounds(week_date: date) -> tuple[datetime, datetime]:
    monday = week_date - timedelta(days=week_date.weekday())
    sunday = monday + timedelta(days=7)
    return datetime.combine(monday, datetime.min.time()), datetime.combine(sunday, datetime.min.time())


def generate_weekly_report(
    db: Session,
    project_id: Optional[UUID],
    week_date: date | None = None,
    generated_by: str = "system",
) -> dict:
    if week_date is None:
        week_date = date.today()

    week_start, week_end = _week_bounds(week_date)
    week_label = f"{week_date.isocalendar()[0]}-W{week_date.isocalendar()[1]:02d}"

    # Collect base project snapshot (if project_id given)
    project_name = "All Projects"
    proposal_id  = "—"
    if project_id:
        snap = collect_project_snapshot(db, project_id)
        if snap and snap.get("project"):
            project_name = snap["project"].name
            proposal_id  = snap["project"].proposal_id

    # ── Validation results for the week ─────────────────────────────────────
    val_q = db.query(ValidationResult).filter(
        ValidationResult.created_at >= week_start,
        ValidationResult.created_at < week_end,
    )
    if project_id:
        val_q = val_q.filter(ValidationResult.project_id == project_id)
    week_validations = val_q.all()

    sev_counts = severity_summary(week_validations)

    # Recurring blockers (field_codes appearing > 1 time)
    field_counter = Counter(v.field_code for v in week_validations if v.status in ("MISSING", "SUSPICIOUS"))
    recurring_blockers = [
        {"field_code": fc, "occurrences": cnt}
        for fc, cnt in field_counter.most_common(10)
        if cnt > 1
    ]

    # ── Audit events for the week ────────────────────────────────────────────
    audit_events = collect_audit_events(db, project_id, week_start, week_end)
    event_type_counts = Counter(e.event_type for e in audit_events)

    # ── Gate checkpoints for the week (Gap 4 fix) ────────────────────────────
    cp_q = db.query(StageCheckpoint).filter(
        StageCheckpoint.created_at >= week_start,
        StageCheckpoint.created_at < week_end,
    )
    if project_id:
        cp_q = cp_q.filter(StageCheckpoint.project_id == project_id)
    week_checkpoints = cp_q.all()

    cp_pass  = sum(1 for cp in week_checkpoints if cp.gate_status == "PASS")
    cp_fail  = sum(1 for cp in week_checkpoints if cp.gate_status == "FAIL")
    cp_pend  = sum(1 for cp in week_checkpoints if cp.gate_status == "PENDING")
    # Per-stage pass rate from checkpoint records
    cp_by_stage: dict[str, dict] = {}
    for cp in week_checkpoints:
        entry = cp_by_stage.setdefault(cp.stage_code, {"pass": 0, "fail": 0, "pending": 0})
        entry[cp.gate_status.lower() if cp.gate_status.lower() in ("pass", "fail", "pending") else "pending"] += 1

    # ── Stage throughput ─────────────────────────────────────────────────────
    stage_q = db.query(Stage).filter(
        Stage.completed_at >= week_start,
        Stage.completed_at < week_end,
    )
    if project_id:
        stage_q = stage_q.filter(Stage.project_id == project_id)
    completed_stages = stage_q.all()

    stage_pass  = sum(1 for s in completed_stages if s.status.value in ("PASSED", "PASS_WITH_WARNINGS"))
    stage_fail  = sum(1 for s in completed_stages if s.status.value in ("FAILED", "BLOCKED"))
    reruns      = sum(1 for s in completed_stages if (s.revision or 1) > 1)

    # ── Parser stability ─────────────────────────────────────────────────────
    parser_q = db.query(ParserRun).filter(
        ParserRun.created_at >= week_start,
        ParserRun.created_at < week_end,
    )
    if project_id:
        parser_q = parser_q.filter(ParserRun.project_id == project_id)
    parser_runs = parser_q.all()
    parser_total   = len(parser_runs)
    parser_success = sum(1 for p in parser_runs if p.status.value == "SUCCESS")
    parser_failed  = parser_total - parser_success
    parser_stability_pct = round(parser_success / parser_total * 100, 1) if parser_total else 0

    parser_names = Counter(p.parser_name for p in parser_runs if p.status.value == "FAILED")
    unstable_parsers = [{"parser": k, "failures": v} for k, v in parser_names.most_common(5)]

    # ── Escalations (defects) ─────────────────────────────────────────────────
    esc_q = db.query(Escalation).filter(
        Escalation.created_at >= week_start,
        Escalation.created_at < week_end,
    )
    if project_id:
        esc_q = esc_q.filter(Escalation.project_id == project_id)
    week_esc = esc_q.all()

    defects_opened   = len(week_esc)
    defects_resolved = sum(1 for e in week_esc if e.status == "RESOLVED")
    sla_breaches     = sum(
        1 for e in week_esc
        if e.status == "OPEN" and e.severity == "CRITICAL"
    )

    # ── Fallback usage ────────────────────────────────────────────────────────
    fallback_events = [e for e in audit_events if "FALLBACK" in e.event_type.upper()]

    # ── Top 10 improvement areas ──────────────────────────────────────────────
    improvement_areas = []
    if recurring_blockers:
        for rb in recurring_blockers[:5]:
            improvement_areas.append(f"Recurring missing field: {rb['field_code']} ({rb['occurrences']}x)")
    if unstable_parsers:
        for up in unstable_parsers[:3]:
            improvement_areas.append(f"Parser instability: {up['parser']} ({up['failures']} failures)")
    if reruns:
        improvement_areas.append(f"Stage re-runs this week: {reruns} — investigate root causes")
    if sla_breaches:
        improvement_areas.append(f"{sla_breaches} critical escalation(s) unresolved — SLA breach risk")

    report = {
        "header": {
            "report_type":   "WEEKLY",
            "week":          week_label,
            "week_start":    week_start.date().isoformat(),
            "week_end":      (week_end - timedelta(days=1)).date().isoformat(),
            "project_uuid":  str(project_id) if project_id else None,
            "project_name":  project_name,
            "proposal_id":   proposal_id,
            "build_version": BUILD_VERSION,
            "generated_at":  datetime.utcnow().isoformat(),
            "generated_by":  generated_by,
        },

        "throughput": {
            "stages_completed":        len(completed_stages),
            "stages_passed":           stage_pass,
            "stages_failed_or_blocked": stage_fail,
            "reruns_triggered":        reruns,
            "close_discipline_pct":    round(stage_pass / len(completed_stages) * 100, 1) if completed_stages else 0,
        },

        "gate_trend": {
            "total_checkpoints": len(week_checkpoints),
            "gate_pass":         cp_pass,
            "gate_fail":         cp_fail,
            "gate_pending":      cp_pend,
            "pass_rate_pct":     round(cp_pass / len(week_checkpoints) * 100, 1) if week_checkpoints else 0,
            "reruns_triggered":  reruns,
            "by_stage":          cp_by_stage,
        },

        "validation_summary": {
            **sev_counts,
            "total_rules_evaluated": len(week_validations),
        },

        "recurring_blockers": recurring_blockers,

        "parser_stability": {
            "total_runs":      parser_total,
            "success":         parser_success,
            "failed":          parser_failed,
            "stability_pct":   parser_stability_pct,
            "unstable_parsers": unstable_parsers,
        },

        "fallback_usage": {
            "fallback_events": len(fallback_events),
            "details": [
                {"event_type": e.event_type, "stage_code": e.stage_code, "created_at": e.created_at.isoformat()}
                for e in fallback_events[:20]
            ],
        },

        "defect_summary": {
            "opened":       defects_opened,
            "resolved":     defects_resolved,
            "sla_breaches": sla_breaches,
            "net_open":     defects_opened - defects_resolved,
        },

        "audit_event_counts": dict(event_type_counts.most_common(20)),

        "top_10_improvement_areas": improvement_areas[:10],
    }

    return report
