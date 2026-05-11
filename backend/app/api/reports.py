"""API endpoints for the Automated Reporting Layer (Daily / Weekly / Monthly)."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.models import (
    ReportRecord, ReportType,
    StageCheckpoint, ValidationResult, StageStatus,
)
from app.db.session import get_db
from app.db.crud.stages import list_project_stages
from app.reports.bm_report import generate_bm_report
from app.reports.daily_report import generate_daily_report
from app.reports.weekly_report import generate_weekly_report
from app.reports.monthly_report import generate_monthly_report
from app.reports.exporter import export_json, export_xlsx, export_docx
from app.utils.project_paths import get_writable_project_data_root

router = APIRouter()

BUILD_VERSION = "2.0"

# ---------------------------------------------------------------------------
# Storage path helpers — spec: /reports/{project_uuid}/{type}/{date_folder}/
# ---------------------------------------------------------------------------

def _report_folder(project_id: UUID, report_type: str, date_label: str) -> Path:
    """
    Returns (and creates) the date-specific folder for a report.
    Structure: <data_root>/reports/<project_uuid>/<daily|weekly|monthly>/<date_label>/
    """
    base = (
        get_writable_project_data_root()
        / "reports"
        / str(project_id)
        / report_type.lower()
        / date_label
    )
    base.mkdir(parents=True, exist_ok=True)
    return base


def _build_report_id_str(
    report_type: str,
    project_id: UUID,
    build_version: str,
    date_label: str,
    sequence: int,
) -> str:
    """
    Spec naming: {type}_{project_uuid}_{build_version}_{date}_{sequence:03d}
    e.g. daily_proj-abc123_v2.0_2026-05-06_001
    """
    short_pid = str(project_id)[:8]  # first 8 chars of UUID for readability
    return f"{report_type.lower()}_proj-{short_pid}_v{build_version}_{date_label}_{sequence:03d}"


def _next_sequence(db: Session, project_id: UUID, report_type: ReportType, date_label: str) -> int:
    """Return next run sequence for the same project+type+date (1-based)."""
    count = db.query(ReportRecord).filter(
        ReportRecord.project_id  == project_id,
        ReportRecord.report_type == report_type,
        ReportRecord.report_date == date_label,
    ).count()
    return count + 1


# ---------------------------------------------------------------------------
# Internal save helper
# ---------------------------------------------------------------------------

def _save_record(
    db: Session,
    report_type: ReportType,
    date_label: str,
    report: dict,
    project_id: UUID,
    export_path: Optional[str] = None,
    generated_by: str = "automated_reporting_layer",
    force_new: bool = False,
) -> ReportRecord:
    """
    If a record already exists for (project, type, date) and force_new=False,
    regenerate it in-place (increment sequence). Otherwise always create new.
    Re-generate path: bump sequence and overwrite payload.
    """
    existing = db.query(ReportRecord).filter(
        ReportRecord.project_id  == project_id,
        ReportRecord.report_type == report_type,
        ReportRecord.report_date == date_label,
    ).order_by(ReportRecord.sequence.desc()).first()

    if existing and not force_new:
        new_seq = existing.sequence + 1
        report_id_str = _build_report_id_str(
            report_type.value, project_id, BUILD_VERSION, date_label, new_seq
        )
        existing.sequence      = new_seq
        existing.report_id_str = report_id_str
        existing.report_data   = json.dumps(report, default=str)
        existing.generated_at  = datetime.utcnow()
        existing.export_path   = export_path
        existing.qc_status     = "pending"
        existing.signed_off_by = None
        existing.signed_off_at = None
        db.commit()
        db.refresh(existing)
        return existing

    seq = _next_sequence(db, project_id, report_type, date_label)
    report_id_str = _build_report_id_str(
        report_type.value, project_id, BUILD_VERSION, date_label, seq
    )
    record = ReportRecord(
        project_id    = project_id,
        report_type   = report_type,
        report_date   = date_label,
        sequence      = seq,
        report_id_str = report_id_str,
        report_data   = json.dumps(report, default=str),
        generated_by  = generated_by,
        build_version = BUILD_VERSION,
        export_path   = export_path,
        qc_status     = "pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _enrich_header(report: dict, record: ReportRecord) -> dict:
    """Inject the spec-compliant report_id and sequence into the report header."""
    report.setdefault("header", {}).update({
        "report_id":    record.report_id_str,
        "sequence":     record.sequence,
        "qc_status":    record.qc_status,
        "signed_off_by": record.signed_off_by,
        "signed_off_at": record.signed_off_at,
    })
    return report


# ---------------------------------------------------------------------------
# Generate endpoints
# ---------------------------------------------------------------------------

@router.post("/{project_id}/daily")
async def generate_daily(
    project_id: str,
    report_date: Optional[str] = Query(None, description="YYYY-MM-DD (defaults to today)"),
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) the daily report for a project. Saves JSON to disk."""
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    parsed_date: date | None = None
    if report_date:
        try:
            parsed_date = date.fromisoformat(report_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="report_date must be YYYY-MM-DD") from exc

    report = generate_daily_report(db, pid, report_date=parsed_date)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])

    date_label = (parsed_date or date.today()).isoformat()

    # Determine sequence before saving so we can name the file
    seq = _next_sequence(db, pid, ReportType.DAILY, date_label)
    short_pid = str(pid)[:8]
    fname_stem = f"daily_proj-{short_pid}_v{BUILD_VERSION}_{date_label}_{seq:03d}"
    folder = _report_folder(pid, "daily", date_label)
    json_path = folder / f"{fname_stem}.json"

    # Persist record
    record = _save_record(db, ReportType.DAILY, date_label, report, pid, export_path=str(json_path))
    report  = _enrich_header(report, record)

    # Write JSON to disk (spec: primary output)
    export_json(report, json_path)

    return {
        "report_id":     str(record.id),
        "report_id_str": record.report_id_str,
        "report_type":   "DAILY",
        "report_date":   date_label,
        "sequence":      record.sequence,
        "project_id":    project_id,
        "generated_at":  record.generated_at.isoformat(),
        "qc_status":     record.qc_status,
        "export_path":   str(json_path),
        "report":        report,
    }


@router.post("/{project_id}/weekly")
async def generate_weekly(
    project_id: str,
    week_date: Optional[str] = Query(None, description="Any date in the target week YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) the weekly roll-up."""
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    parsed_week: date | None = None
    if week_date:
        try:
            parsed_week = date.fromisoformat(week_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="week_date must be YYYY-MM-DD") from exc

    ref = parsed_week or date.today()
    iso = ref.isocalendar()
    week_label = f"{iso[0]}-W{iso[1]:02d}"

    report = generate_weekly_report(db, pid, week_date=ref)

    seq = _next_sequence(db, pid, ReportType.WEEKLY, week_label)
    short_pid = str(pid)[:8]
    fname_stem = f"weekly_proj-{short_pid}_v{BUILD_VERSION}_{week_label}_{seq:03d}"
    folder = _report_folder(pid, "weekly", week_label)
    json_path = folder / f"{fname_stem}.json"

    record = _save_record(db, ReportType.WEEKLY, week_label, report, pid, export_path=str(json_path))
    report  = _enrich_header(report, record)
    export_json(report, json_path)

    return {
        "report_id":     str(record.id),
        "report_id_str": record.report_id_str,
        "report_type":   "WEEKLY",
        "week":          week_label,
        "sequence":      record.sequence,
        "project_id":    project_id,
        "generated_at":  record.generated_at.isoformat(),
        "qc_status":     record.qc_status,
        "export_path":   str(json_path),
        "report":        report,
    }


@router.post("/{project_id}/monthly")
async def generate_monthly(
    project_id: str,
    year:  Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) the monthly management report."""
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    today = date.today()
    y = year  or today.year
    m = month or today.month

    if not (1 <= m <= 12):
        raise HTTPException(status_code=400, detail="month must be 1–12")

    month_label = f"{y}-{m:02d}"
    report = generate_monthly_report(db, pid, year=y, month=m)

    seq = _next_sequence(db, pid, ReportType.MONTHLY, month_label)
    short_pid = str(pid)[:8]
    fname_stem = f"monthly_proj-{short_pid}_v{BUILD_VERSION}_{month_label}_{seq:03d}"
    folder = _report_folder(pid, "monthly", month_label)
    json_path = folder / f"{fname_stem}.json"

    record = _save_record(db, ReportType.MONTHLY, month_label, report, pid, export_path=str(json_path))
    report  = _enrich_header(report, record)
    export_json(report, json_path)

    return {
        "report_id":     str(record.id),
        "report_id_str": record.report_id_str,
        "report_type":   "MONTHLY",
        "month":         month_label,
        "sequence":      record.sequence,
        "project_id":    project_id,
        "generated_at":  record.generated_at.isoformat(),
        "qc_status":     record.qc_status,
        "export_path":   str(json_path),
        "report":        report,
    }


# ---------------------------------------------------------------------------
# BM-001 Preflight helper
# ---------------------------------------------------------------------------

def _run_bm_preflight(db: Session, pid: UUID) -> dict:
    """Check all technical conditions required before BM-001 can be authorized."""
    from app.agents.phase2.output_utils import project_output_dir

    required_stages = ["P2-01", "P2-02", "P2-03", "P2-04", "P2-05"]
    _passed = {StageStatus.PASSED, StageStatus.PASS_WITH_WARNINGS}

    stages   = list_project_stages(db, pid)
    stage_map = {s.stage_code: s for s in stages}

    # 1 — All stages passed
    not_passed = [sc for sc in required_stages
                  if sc not in stage_map or stage_map[sc].status not in _passed]
    check_stages = {
        "item":   "All pipeline stages passed (P2-01 → P2-05)",
        "status": "PASS" if not not_passed else "FAIL",
        "detail": "All 5 stages passed" if not not_passed
                  else f"Not passed: {', '.join(not_passed)}",
    }

    # 2 — No critical missing fields
    critical_missing = db.query(ValidationResult).filter(
        ValidationResult.project_id == pid,
        ValidationResult.status     == "MISSING",
        ValidationResult.severity   == "CRITICAL",
    ).all()
    check_fields = {
        "item":   "No critical missing fields",
        "status": "PASS" if not critical_missing else "FAIL",
        "detail": "No critical missing fields" if not critical_missing
                  else f"{len(critical_missing)} critical field(s) missing: "
                       f"{', '.join(v.field_code for v in critical_missing)}",
    }

    # 3 — AB output exists
    ab_path = project_output_dir(pid, "ab") / "anchor_bolt_layout.json"
    check_ab = {
        "item":   "AB drawing output (anchor_bolt_layout.json) exists",
        "status": "PASS" if ab_path.exists() else "FAIL",
        "detail": str(ab_path) if ab_path.exists() else f"File not found: {ab_path}",
    }

    # 4 — GA output exists
    ga_path = project_output_dir(pid, "ga") / "general_arrangement.json"
    check_ga = {
        "item":   "GA drawing output (general_arrangement.json) exists",
        "status": "PASS" if ga_path.exists() else "FAIL",
        "detail": str(ga_path) if ga_path.exists() else f"File not found: {ga_path}",
    }

    # 5 — Evidence pack exported (integrity_manifest present)
    manifest_path = (
        get_writable_project_data_root()
        / str(pid) / "outputs" / "processed_exports" / "integrity_manifest.json"
    )
    check_evidence = {
        "item":   "Evidence pack exported (integrity_manifest.json present)",
        "status": "PASS" if manifest_path.exists() else "FAIL",
        "detail": str(manifest_path) if manifest_path.exists()
                  else "Run GET /export/evidence-files first",
    }

    # 6 — All gate checkpoints PASS
    checkpoints  = db.query(StageCheckpoint).filter(StageCheckpoint.project_id == pid).all()
    failed_gates = [cp.checkpoint_label for cp in checkpoints if cp.gate_status != "PASS"]
    if not checkpoints:
        gate_status  = "FAIL"
        gate_detail  = "No gate checkpoints recorded — pipeline has not completed"
    elif failed_gates:
        gate_status  = "FAIL"
        gate_detail  = f"Failed gates: {', '.join(failed_gates)}"
    else:
        gate_status  = "PASS"
        gate_detail  = "All gates PASS"
    check_gates = {
        "item":   "All gate checkpoints PASS",
        "status": gate_status,
        "detail": gate_detail,
    }

    checks   = [check_stages, check_fields, check_ab, check_ga, check_evidence, check_gates]
    all_pass = all(c["status"] == "PASS" for c in checks)

    return {
        "preflight_passed":  all_pass,
        "testing_permitted": all_pass,
        "checks":            checks,
        "pass_count":        sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count":        sum(1 for c in checks if c["status"] == "FAIL"),
        "checked_at":        datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# BM-001 Milestone Report
# ---------------------------------------------------------------------------

@router.post("/{project_id}/bm")
async def generate_bm(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) the BM-001 Build Milestone report for a project."""
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    report = generate_bm_report(db, pid)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])

    date_label = date.today().isoformat()
    seq        = _next_sequence(db, pid, ReportType.BM, date_label)
    short_pid  = str(pid)[:8]
    fname_stem = f"bm_proj-{short_pid}_v{BUILD_VERSION}_{date_label}_{seq:03d}"
    folder     = _report_folder(pid, "bm", date_label)
    json_path  = folder / f"{fname_stem}.json"

    record = _save_record(db, ReportType.BM, date_label, report, pid,
                          export_path=str(json_path))
    report = _enrich_header(report, record)
    export_json(report, json_path)

    return {
        "report_id":      str(record.id),
        "report_id_str":  record.report_id_str,
        "report_type":    "BM",
        "milestone":      "BM-001",
        "report_date":    date_label,
        "sequence":       record.sequence,
        "project_id":     project_id,
        "generated_at":   record.generated_at.isoformat(),
        "qc_status":      record.qc_status,
        "export_path":    str(json_path),
        "verdict":        report.get("authorization_gate", {}).get("verdict", "UNKNOWN"),
        "report":         report,
    }


# ---------------------------------------------------------------------------
# BM-001 Preflight check
# ---------------------------------------------------------------------------

@router.get("/{project_id}/bm/preflight")
async def bm_preflight(project_id: str, db: Session = Depends(get_db)):
    """
    Run all BM-001 technical preflight checks.
    Returns testing_permitted: true only when every check is PASS.
    Use this before calling /bm/authorize.
    """
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    result = _run_bm_preflight(db, pid)
    result["project_id"] = str(pid)
    return result


# ---------------------------------------------------------------------------
# BM-001 Auto-Authorization
# ---------------------------------------------------------------------------

@router.post("/{project_id}/bm/authorize")
async def bm_authorize(
    project_id:    str,
    authorized_by: str = Query(default="system", description="Name / ID of authorizing party"),
    db: Session = Depends(get_db),
):
    """
    Authorize BM-001 for controlled testing in one call:
      1. Runs all preflight checks — stops with HOLD if any fail.
      2. Generates the BM-001 milestone report.
      3. Auto-signs the report record when verdict = AUTHORIZED.
      4. Exports the full evidence pack (evidence-files endpoint).
      5. Writes a consolidated authorization_package JSON to disk.

    Returns testing_permitted: true when fully authorized.
    """
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    # Step 1 — Preflight
    preflight = _run_bm_preflight(db, pid)
    if not preflight["preflight_passed"]:
        return {
            "project_id":        str(pid),
            "testing_permitted": False,
            "verdict":           "HOLD",
            "reason":            "One or more preflight checks failed — resolve before authorizing.",
            "preflight":         preflight,
        }

    # Step 2 — Generate BM report
    report = generate_bm_report(db, pid, generated_by=authorized_by)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])

    date_label = date.today().isoformat()
    seq        = _next_sequence(db, pid, ReportType.BM, date_label)
    short_pid  = str(pid)[:8]
    fname_stem = f"bm_proj-{short_pid}_v{BUILD_VERSION}_{date_label}_{seq:03d}"
    folder     = _report_folder(pid, "bm", date_label)
    json_path  = folder / f"{fname_stem}.json"

    record = _save_record(db, ReportType.BM, date_label, report, pid,
                          export_path=str(json_path), generated_by=authorized_by)
    report = _enrich_header(report, record)
    export_json(report, json_path)

    verdict = report.get("authorization_gate", {}).get("verdict", "HOLD")

    # Step 3 — Auto-sign when AUTHORIZED
    if verdict == "AUTHORIZED":
        record.qc_status     = "approved"
        record.signed_off_by = authorized_by
        record.signed_off_at = datetime.utcnow()
        db.commit()
        db.refresh(record)

    # Step 4 — Export full evidence pack
    evidence_dir = (
        get_writable_project_data_root()
        / str(pid) / "outputs" / "processed_exports"
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Step 5 — Write consolidated authorization package
    auth_package = {
        "authorization_package": "BM-001",
        "project_id":            str(pid),
        "verdict":               verdict,
        "testing_permitted":     verdict == "AUTHORIZED",
        "authorized_by":         authorized_by,
        "authorized_at":         datetime.utcnow().isoformat(),
        "report_id":             str(record.id),
        "report_id_str":         record.report_id_str,
        "qc_status":             record.qc_status,
        "preflight_checks":      preflight["checks"],
        "authorization_gate":    report.get("authorization_gate", {}),
        "pipeline_summary":      report.get("pipeline_summary", {}),
        "evidence_pack_path":    str(evidence_dir),
        "bm_report_path":        str(json_path),
        "generated_at":          datetime.utcnow().isoformat(),
    }
    auth_path = folder / f"authorization_package_{date_label}.json"
    export_json(auth_package, auth_path)

    return {
        "project_id":                  str(pid),
        "testing_permitted":           verdict == "AUTHORIZED",
        "verdict":                     verdict,
        "report_id":                   str(record.id),
        "report_id_str":               record.report_id_str,
        "qc_status":                   record.qc_status,
        "signed_off_by":               record.signed_off_by,
        "authorization_package_path":  str(auth_path),
        "bm_report_path":              str(json_path),
        "preflight":                   preflight,
        "authorization_gate":          report.get("authorization_gate", {}),
    }


# ---------------------------------------------------------------------------
# List / get saved reports
# ---------------------------------------------------------------------------

@router.get("/{project_id}/list")
async def list_reports(
    project_id: str,
    report_type: Optional[str] = Query(None, description="DAILY | WEEKLY | MONTHLY"),
    db: Session = Depends(get_db),
):
    """List all saved reports for a project, newest first."""
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    q = db.query(ReportRecord).filter(ReportRecord.project_id == pid)
    if report_type:
        try:
            rtype = ReportType(report_type.upper())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="report_type must be DAILY, WEEKLY, or MONTHLY") from exc
        q = q.filter(ReportRecord.report_type == rtype)

    records = q.order_by(ReportRecord.generated_at.desc()).all()
    return [
        {
            "report_id":     str(r.id),
            "report_id_str": r.report_id_str,
            "report_type":   r.report_type.value,
            "report_date":   r.report_date,
            "sequence":      r.sequence,
            "generated_at":  r.generated_at.isoformat(),
            "generated_by":  r.generated_by,
            "build_version": r.build_version,
            "qc_status":     r.qc_status,
            "signed_off_by": r.signed_off_by,
        }
        for r in records
    ]


@router.get("/{project_id}/{report_id}/detail")
async def get_report(project_id: str, report_id: str, db: Session = Depends(get_db)):
    """Fetch a saved report payload by UUID."""
    try:
        UUID(project_id)
        rid = UUID(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID") from exc

    record = db.query(ReportRecord).filter(ReportRecord.id == rid).first()
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "report_id":     str(record.id),
        "report_id_str": record.report_id_str,
        "report_type":   record.report_type.value,
        "report_date":   record.report_date,
        "sequence":      record.sequence,
        "generated_at":  record.generated_at.isoformat(),
        "generated_by":  record.generated_by,
        "build_version": record.build_version,
        "qc_status":     record.qc_status,
        "signed_off_by": record.signed_off_by,
        "signed_off_at": record.signed_off_at.isoformat() if record.signed_off_at else None,
        "report":        json.loads(record.report_data or "{}"),
    }


# ---------------------------------------------------------------------------
# QC Sign-off
# ---------------------------------------------------------------------------

@router.post("/{project_id}/{report_id}/signoff")
async def sign_off_report(
    project_id: str,
    report_id:  str,
    signed_by:  str = Query(..., description="Name/ID of the person signing off"),
    db: Session = Depends(get_db),
):
    """Approve / sign off a report (sets qc_status=approved)."""
    try:
        UUID(project_id)
        rid = UUID(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID") from exc

    record = db.query(ReportRecord).filter(ReportRecord.id == rid).first()
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")

    record.qc_status     = "approved"
    record.signed_off_by = signed_by
    record.signed_off_at = datetime.utcnow()
    db.commit()
    db.refresh(record)

    return {
        "report_id":     str(record.id),
        "report_id_str": record.report_id_str,
        "qc_status":     record.qc_status,
        "signed_off_by": record.signed_off_by,
        "signed_off_at": record.signed_off_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# QC Reject (Gap 7)
# ---------------------------------------------------------------------------

@router.post("/{project_id}/{report_id}/reject")
async def reject_report(
    project_id: str,
    report_id:  str,
    reason:     str = Query(..., description="Reason for rejection"),
    rejected_by: str = Query(..., description="Name/ID of the person rejecting"),
    db: Session = Depends(get_db),
):
    """Reject a report and record the reason (sets qc_status=rejected)."""
    try:
        UUID(project_id)
        rid = UUID(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID") from exc

    record = db.query(ReportRecord).filter(ReportRecord.id == rid).first()
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")

    record.qc_status     = "rejected"
    record.signed_off_by = rejected_by
    record.signed_off_at = datetime.utcnow()
    # Persist rejection reason inside the report payload header
    try:
        import json as _json
        payload = _json.loads(record.report_data or "{}")
        payload.setdefault("header", {})["rejection_reason"] = reason
        payload["header"]["rejected_by"] = rejected_by
        record.report_data = _json.dumps(payload, default=str)
    except Exception:
        pass  # never let payload mutation block the status update
    db.commit()
    db.refresh(record)

    return {
        "report_id":     str(record.id),
        "report_id_str": record.report_id_str,
        "qc_status":     record.qc_status,
        "rejected_by":   rejected_by,
        "reason":        reason,
        "rejected_at":   record.signed_off_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Export endpoints — spec: json (primary), csv, xlsx
# ---------------------------------------------------------------------------

@router.get("/{project_id}/{report_id}/export/{fmt}")
async def export_report(
    project_id: str,
    report_id:  str,
    fmt:        str,
    db: Session = Depends(get_db),
):
    """Download a saved report as json | xlsx | docx.
    File saved using the spec naming standard."""
    try:
        pid = UUID(project_id)
        rid = UUID(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID") from exc

    fmt = fmt.lower()
    if fmt not in {"json", "xlsx", "docx"}:
        raise HTTPException(status_code=400, detail="Supported formats: json, xlsx, docx")

    record = db.query(ReportRecord).filter(ReportRecord.id == rid).first()
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")

    report   = json.loads(record.report_data or "{}")
    folder   = _report_folder(pid, record.report_type.value, record.report_date)
    # Use the canonical report_id_str as filename
    stem     = record.report_id_str or f"{record.report_type.value.lower()}_{record.report_date}_{record.sequence:03d}"
    out_path = folder / f"{stem}.{fmt}"

    if fmt == "json":
        export_json(report, out_path)
        return FileResponse(out_path, filename=out_path.name, media_type="application/json")

    if fmt == "xlsx":
        export_xlsx(report, out_path)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return FileResponse(out_path, filename=out_path.name, media_type=media)

    export_docx(report, out_path)
    media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(out_path, filename=out_path.name, media_type=media)


# ---------------------------------------------------------------------------
# Scheduler status + manual test triggers
# ---------------------------------------------------------------------------

@router.get("/admin/scheduler/status")
async def scheduler_status():
    """Check whether the automated scheduler is running and show next run times."""
    from app.scheduler.scheduler import scheduler_status as _status
    return _status()


@router.post("/admin/trigger/{job_type}")
async def trigger_now(job_type: str):
    """
    Manually fire a report job RIGHT NOW (for testing).
    job_type: daily | weekly | monthly
    Runs synchronously and returns when complete.
    """
    job_type = job_type.lower()
    if job_type not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="job_type must be: daily, weekly, or monthly")

    from app.scheduler import jobs as _jobs
    import time

    start = time.monotonic()
    try:
        if job_type == "daily":
            _jobs.run_daily_reports()
        elif job_type == "weekly":
            _jobs.run_weekly_reports()
        else:
            _jobs.run_monthly_reports()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Job failed: {exc}") from exc

    elapsed = round(time.monotonic() - start, 2)
    return {
        "job":      job_type,
        "status":   "completed",
        "elapsed_s": elapsed,
        "message":  f"{job_type.capitalize()} reports generated for all active projects.",
    }


# ---------------------------------------------------------------------------
# Latest daily report shortcut
# ---------------------------------------------------------------------------

@router.get("/{project_id}/latest/daily")
async def latest_daily(project_id: str, db: Session = Depends(get_db)):
    """Return the most recently generated daily report (for dashboard widget)."""
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    record = (
        db.query(ReportRecord)
        .filter(ReportRecord.project_id == pid, ReportRecord.report_type == ReportType.DAILY)
        .order_by(ReportRecord.generated_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="No daily report found. Generate one first via POST.")

    return {
        "report_id":     str(record.id),
        "report_id_str": record.report_id_str,
        "report_type":   "DAILY",
        "report_date":   record.report_date,
        "sequence":      record.sequence,
        "generated_at":  record.generated_at.isoformat(),
        "qc_status":     record.qc_status,
        "signed_off_by": record.signed_off_by,
        "report":        json.loads(record.report_data or "{}"),
    }
