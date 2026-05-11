"""Scheduled report job functions — run for every active project."""
from __future__ import annotations

import logging
from datetime import date, datetime
from uuid import UUID

from app.db.models import Project, ProjectStatus, ReportType, ReportRecord
from app.db.session import SessionLocal
from app.reports.daily_report import generate_daily_report
from app.reports.weekly_report import generate_weekly_report
from app.reports.monthly_report import generate_monthly_report
from app.reports.exporter import export_json
from app.utils.project_paths import get_writable_project_data_root

log = logging.getLogger("scheduler.jobs")

BUILD_VERSION = "2.0"


def _get_active_projects(db) -> list:
    return db.query(Project).filter(
        Project.status.in_([ProjectStatus.IN_PROGRESS, ProjectStatus.CREATED])
    ).all()


def _report_folder(project_id: UUID, report_type: str, date_label: str):
    from pathlib import Path
    base = (
        get_writable_project_data_root()
        / "reports"
        / str(project_id)
        / report_type.lower()
        / date_label
    )
    base.mkdir(parents=True, exist_ok=True)
    return base


def _next_seq(db, project_id: UUID, report_type: ReportType, date_label: str) -> int:
    count = db.query(ReportRecord).filter(
        ReportRecord.project_id  == project_id,
        ReportRecord.report_type == report_type,
        ReportRecord.report_date == date_label,
    ).count()
    return count + 1


def _persist(db, report: dict, project_id: UUID, report_type: ReportType,
             date_label: str, json_path) -> ReportRecord:
    import json as _json
    short_pid = str(project_id)[:8]
    seq = _next_seq(db, project_id, report_type, date_label)
    report_id_str = (
        f"{report_type.value.lower()}_proj-{short_pid}"
        f"_v{BUILD_VERSION}_{date_label}_{seq:03d}"
    )

    record = ReportRecord(
        project_id    = project_id,
        report_type   = report_type,
        report_date   = date_label,
        sequence      = seq,
        report_id_str = report_id_str,
        report_data   = _json.dumps(report, default=str),
        generated_by  = "automated_reporting_layer",
        build_version = BUILD_VERSION,
        export_path   = str(json_path),
        qc_status     = "pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    report.setdefault("header", {}).update({
        "report_id":    report_id_str,
        "sequence":     seq,
        "qc_status":    "pending",
    })
    export_json(report, json_path)
    log.info("Report saved: %s", report_id_str)
    return record


# ---------------------------------------------------------------------------
# Job functions — called by APScheduler
# ---------------------------------------------------------------------------

def run_daily_reports():
    """Daily job: 5:00 PM every day."""
    log.info("=== Scheduled Daily Report Job started ===")
    today = date.today()
    date_label = today.isoformat()
    db = SessionLocal()
    try:
        projects = _get_active_projects(db)
        if not projects:
            log.info("No active projects — daily report skipped.")
            return

        for project in projects:
            try:
                report = generate_daily_report(db, project.id, report_date=today)
                if "error" in report:
                    log.warning("Daily report skipped for %s: %s", project.id, report["error"])
                    continue
                short_pid = str(project.id)[:8]
                seq = _next_seq(db, project.id, ReportType.DAILY, date_label)
                fname = f"daily_proj-{short_pid}_v{BUILD_VERSION}_{date_label}_{seq:03d}.json"
                folder = _report_folder(project.id, "daily", date_label)
                _persist(db, report, project.id, ReportType.DAILY, date_label, folder / fname)
                log.info("Daily report done: project=%s", project.proposal_id)
            except Exception as exc:
                log.error("Daily report FAILED for project %s: %s", project.id, exc, exc_info=True)
    finally:
        db.close()
    log.info("=== Daily Report Job complete ===")


def run_weekly_reports():
    """Weekly job: every Friday at 5:15 PM."""
    log.info("=== Scheduled Weekly Report Job started ===")
    today = date.today()
    iso = today.isocalendar()
    week_label = f"{iso[0]}-W{iso[1]:02d}"
    db = SessionLocal()
    try:
        projects = _get_active_projects(db)
        if not projects:
            log.info("No active projects — weekly report skipped.")
            return

        for project in projects:
            try:
                report = generate_weekly_report(db, project.id, week_date=today)
                short_pid = str(project.id)[:8]
                seq = _next_seq(db, project.id, ReportType.WEEKLY, week_label)
                fname = f"weekly_proj-{short_pid}_v{BUILD_VERSION}_{week_label}_{seq:03d}.json"
                folder = _report_folder(project.id, "weekly", week_label)
                _persist(db, report, project.id, ReportType.WEEKLY, week_label, folder / fname)
                log.info("Weekly report done: project=%s", project.proposal_id)
            except Exception as exc:
                log.error("Weekly report FAILED for project %s: %s", project.id, exc, exc_info=True)
    finally:
        db.close()
    log.info("=== Weekly Report Job complete ===")


def run_monthly_reports():
    """Monthly job: 30th of each month at 5:30 PM."""
    log.info("=== Scheduled Monthly Report Job started ===")
    today = date.today()
    month_label = f"{today.year}-{today.month:02d}"
    db = SessionLocal()
    try:
        projects = _get_active_projects(db)
        if not projects:
            log.info("No active projects — monthly report skipped.")
            return

        for project in projects:
            try:
                report = generate_monthly_report(db, project.id, year=today.year, month=today.month)
                short_pid = str(project.id)[:8]
                seq = _next_seq(db, project.id, ReportType.MONTHLY, month_label)
                fname = f"monthly_proj-{short_pid}_v{BUILD_VERSION}_{month_label}_{seq:03d}.json"
                folder = _report_folder(project.id, "monthly", month_label)
                _persist(db, report, project.id, ReportType.MONTHLY, month_label, folder / fname)
                log.info("Monthly report done: project=%s", project.proposal_id)
            except Exception as exc:
                log.error("Monthly report FAILED for project %s: %s", project.id, exc, exc_info=True)
    finally:
        db.close()
    log.info("=== Monthly Report Job complete ===")
