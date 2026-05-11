"""Retention enforcement job — deletes report files and DB rows past policy age.

Policy:
  DAILY   — 90 days
  WEEKLY  — 365 days
  MONTHLY — 7 years (2 557 days)

Runs nightly at 02:00 IST via the same APScheduler instance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("scheduler.retention")

RETENTION_DAYS = {
    "DAILY":   90,
    "WEEKLY":  365,
    "MONTHLY": 2557,   # 7 years
}


def run_retention_cleanup() -> None:
    """Delete report_records rows and their on-disk JSON files past retention age."""
    from app.db.models import ReportRecord, ReportType
    from app.db.session import SessionLocal

    log.info("=== Retention cleanup started ===")
    db = SessionLocal()
    deleted_rows = 0
    deleted_files = 0

    try:
        for rtype, days in RETENTION_DAYS.items():
            cutoff = datetime.utcnow() - timedelta(days=days)
            old_records = (
                db.query(ReportRecord)
                .filter(
                    ReportRecord.report_type == ReportType(rtype),
                    ReportRecord.generated_at < cutoff,
                )
                .all()
            )

            for rec in old_records:
                # Remove the primary JSON file and any sibling exports
                if rec.export_path:
                    base = Path(rec.export_path)
                    for sibling in base.parent.glob(f"{base.stem}.*"):
                        try:
                            sibling.unlink(missing_ok=True)
                            deleted_files += 1
                            log.debug("Deleted file: %s", sibling)
                        except OSError as exc:
                            log.warning("Could not delete %s: %s", sibling, exc)
                db.delete(rec)
                deleted_rows += 1

            db.commit()
            log.info(
                "Retention [%s]: deleted %d record(s) older than %d days (cutoff %s)",
                rtype, len(old_records), days, cutoff.date().isoformat(),
            )

    except Exception as exc:
        db.rollback()
        log.error("Retention cleanup failed: %s", exc, exc_info=True)
    finally:
        db.close()

    log.info(
        "=== Retention cleanup complete — %d rows, %d files removed ===",
        deleted_rows, deleted_files,
    )
