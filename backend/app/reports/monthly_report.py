"""Generate a Monthly Management Report aggregated from weekly source tables."""
from __future__ import annotations

from calendar import monthrange
from collections import Counter
from datetime import date, datetime, timedelta
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
    Stage,
    ValidationResult,
    ProjectFile,
)
from app.reports.collector import BUILD_VERSION, severity_summary

COMPONENT_STAGE_MAP = {
    "Ingestion (P2-01)":      "P2-01",
    "Completeness (P2-02)":   "P2-02",
    "AB Generation (P2-03)":  "P2-03",
    "GA Generation (P2-04)":  "P2-04",
    "Validation (P2-05)":     "P2-05",
}


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    _, last_day = monthrange(year, month)
    start = datetime(year, month, 1)
    end   = datetime(year, month, last_day, 23, 59, 59, 999999) + timedelta(seconds=1)
    return start, end


def _stage_health(stages: list, stage_code: str) -> str:
    matching = [s for s in stages if s.stage_code == stage_code]
    if not matching:
        return "NO_DATA"
    statuses = [s.status.value for s in matching]
    if all(s in ("PASSED", "PASS_WITH_WARNINGS") for s in statuses):
        return "HEALTHY"
    if any(s in ("FAILED", "BLOCKED") for s in statuses):
        return "DEGRADED"
    return "PARTIAL"


def _effectiveness_score(
    stage_pass_rate: float,
    parser_stability_pct: float,
    sev: dict,
    total_validations: int,
) -> float:
    """Simple 0–100 score: weighted average of key health signals."""
    blocker_penalty = min(sev.get("release_blockers", 0) * 5, 30)
    critical_penalty = min(sev.get("CRITICAL", 0) * 2, 20)
    base = (stage_pass_rate * 0.4 + parser_stability_pct * 0.4 + 20) - blocker_penalty - critical_penalty
    return round(max(0.0, min(100.0, base)), 1)


def generate_monthly_report(
    db: Session,
    project_id: Optional[UUID],
    year: int | None = None,
    month: int | None = None,
    generated_by: str = "system",
) -> dict:
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    month_start, month_end = _month_bounds(year, month)
    month_label = f"{year}-{month:02d}"

    # ── Projects covered ─────────────────────────────────────────────────────
    project_name = "All Projects"
    proposal_id  = "—"
    if project_id:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj:
            project_name = proj.name
            proposal_id  = proj.proposal_id

    def _filter(q, model):
        q = q.filter(model.created_at >= month_start, model.created_at < month_end)
        if project_id:
            q = q.filter(model.project_id == project_id)
        return q

    month_validations = _filter(db.query(ValidationResult), ValidationResult).all()
    month_stages      = _filter(db.query(Stage), Stage).all()
    month_parsers     = _filter(db.query(ParserRun), ParserRun).all()
    month_escalations = _filter(db.query(Escalation), Escalation).all()
    month_corrections = _filter(db.query(CorrectionEvent), CorrectionEvent).all()
    month_handoffs    = _filter(db.query(Handoff), Handoff).all()
    month_audit       = _filter(db.query(AuditEventLog), AuditEventLog).order_by(AuditEventLog.created_at).all()
    month_files       = _filter(db.query(ProjectFile), ProjectFile).all()

    # ── System effectiveness ──────────────────────────────────────────────────
    completed_stages = [s for s in month_stages if s.status.value in ("PASSED", "PASS_WITH_WARNINGS", "FAILED", "BLOCKED")]
    passed_stages    = [s for s in completed_stages if s.status.value in ("PASSED", "PASS_WITH_WARNINGS")]
    stage_pass_rate  = round(len(passed_stages) / len(completed_stages) * 100, 1) if completed_stages else 0

    parser_total     = len(month_parsers)
    parser_success   = sum(1 for p in month_parsers if p.status.value == "SUCCESS")
    parser_stability = round(parser_success / parser_total * 100, 1) if parser_total else 0

    sev_counts     = severity_summary(month_validations)
    eff_score      = _effectiveness_score(stage_pass_rate, parser_stability, sev_counts, len(month_validations))

    # ── Component health ─────────────────────────────────────────────────────
    component_health = {}
    for comp_name, stage_code in COMPONENT_STAGE_MAP.items():
        component_health[comp_name] = _stage_health(month_stages, stage_code)
    component_health["Reporting"] = "HEALTHY"  # This module running means it works
    component_health["Handoff"]   = "HEALTHY" if month_handoffs else "NO_DATA"

    # ── Root-cause analysis ───────────────────────────────────────────────────
    field_failures = Counter(
        v.field_code for v in month_validations
        if v.status in ("MISSING", "SUSPICIOUS")
    )
    source_failures = Counter(
        v.source for v in month_validations
        if v.status in ("MISSING", "SUSPICIOUS") and v.source
    )
    correction_fields = Counter(c.field_code for c in month_corrections)

    root_cause = {
        "top_failing_fields":   [{"field_code": k, "count": v} for k, v in field_failures.most_common(10)],
        "top_failing_sources":  [{"source": k, "count": v} for k, v in source_failures.most_common(5)],
        "most_corrected_fields": [{"field_code": k, "count": v} for k, v in correction_fields.most_common(5)],
    }

    # ── Benchmark history / evidence compliance ───────────────────────────────
    handoff_approved  = sum(1 for h in month_handoffs if h.approved == 1)
    handoff_rejected  = sum(1 for h in month_handoffs if h.approved == -1)
    handoff_pending   = sum(1 for h in month_handoffs if h.approved == 0)

    # ── Defects ───────────────────────────────────────────────────────────────
    defects_opened   = len(month_escalations)
    defects_resolved = sum(1 for e in month_escalations if e.status == "RESOLVED")
    sla_breaches     = sum(
        1 for e in month_escalations
        if e.status == "OPEN" and e.severity == "CRITICAL"
    )

    # ── Improvement register ──────────────────────────────────────────────────
    improvement_register = []
    if field_failures:
        for field, cnt in field_failures.most_common(3):
            improvement_register.append({
                "area":        "Field Extraction",
                "item":        f"Field '{field}' failed {cnt} time(s) — review source mapping",
                "priority":    "HIGH" if cnt >= 3 else "MEDIUM",
            })
    if parser_stability < 90:
        improvement_register.append({
            "area":     "Parser Stability",
            "item":     f"Parser success rate {parser_stability}% — below 90% threshold",
            "priority": "HIGH",
        })
    if sla_breaches:
        improvement_register.append({
            "area":     "Escalation SLA",
            "item":     f"{sla_breaches} critical issue(s) unresolved — address before next release",
            "priority": "CRITICAL",
        })
    reruns = sum(1 for s in month_stages if (s.revision or 1) > 1)
    if reruns > 5:
        improvement_register.append({
            "area":     "Pipeline Stability",
            "item":     f"{reruns} stage re-runs in the month — investigate failure patterns",
            "priority": "MEDIUM",
        })

    # ── Release readiness ─────────────────────────────────────────────────────
    release_blockers = sev_counts.get("release_blockers", 0)
    release_ready    = release_blockers == 0 and stage_pass_rate >= 80 and eff_score >= 70

    report = {
        "header": {
            "report_type":   "MONTHLY",
            "month":         month_label,
            "month_start":   month_start.date().isoformat(),
            "month_end":     (month_end - timedelta(seconds=1)).date().isoformat(),
            "project_uuid":  str(project_id) if project_id else None,
            "project_name":  project_name,
            "proposal_id":   proposal_id,
            "build_version": BUILD_VERSION,
            "generated_at":  datetime.utcnow().isoformat(),
            "generated_by":  generated_by,
        },

        "system_effectiveness": {
            "score":              eff_score,
            "stage_pass_rate_pct": stage_pass_rate,
            "parser_stability_pct": parser_stability,
            "total_validations":  len(month_validations),
            **sev_counts,
        },

        "component_health": component_health,

        "pipeline_overview": {
            "stages_completed":    len(completed_stages),
            "stages_passed":       len(passed_stages),
            "stages_failed":       len(completed_stages) - len(passed_stages),
            "reruns":              reruns,
            "files_processed":     len(month_files),
            "corrections_applied": len(month_corrections),
        },

        "root_cause_analysis": root_cause,

        "benchmark_and_evidence": {
            "handoffs_created":  len(month_handoffs),
            "handoffs_approved": handoff_approved,
            "handoffs_rejected": handoff_rejected,
            "handoffs_pending":  handoff_pending,
        },

        "defect_summary": {
            "opened":       defects_opened,
            "resolved":     defects_resolved,
            "sla_breaches": sla_breaches,
            "net_open":     defects_opened - defects_resolved,
        },

        "improvement_register": improvement_register,

        "management_summary": {
            "release_ready":       release_ready,
            "release_blockers":    release_blockers,
            "effectiveness_score": eff_score,
            "key_risks": [
                item["item"] for item in improvement_register if item["priority"] in ("HIGH", "CRITICAL")
            ],
        },
    }

    return report
