"""APScheduler setup for automated report generation and retention cleanup.

Schedule (IST — Asia/Kolkata):
  Daily     — every day          at 17:00
  Weekly    — every Friday       at 17:15
  Monthly   — 30th of each month at 17:30
  Monthly*  — last day of month  at 17:35  (Gap 3: covers months shorter than 30 days)
  Retention — every day          at 02:00  (Gap 2: enforces 90d / 365d / 7yr policy)
"""
from __future__ import annotations

import logging

log = logging.getLogger("scheduler")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _APSCHEDULER_AVAILABLE = True
except ImportError:
    _APSCHEDULER_AVAILABLE = False
    log.warning(
        "APScheduler not installed. Automated scheduling is DISABLED.\n"
        "Run:  pip install apscheduler\n"
        "Then restart the server."
    )

_scheduler: "BackgroundScheduler | None" = None


def get_scheduler():
    return _scheduler


def start_scheduler() -> bool:
    """Initialize and start the background scheduler. Returns True on success."""
    global _scheduler

    if not _APSCHEDULER_AVAILABLE:
        log.warning("APScheduler unavailable — scheduler not started.")
        return False

    if _scheduler and _scheduler.running:
        log.info("Scheduler already running.")
        return True

    from app.scheduler.jobs import run_daily_reports, run_weekly_reports, run_monthly_reports
    from app.scheduler.retention import run_retention_cleanup

    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # ── Daily report — every day at 17:00 ────────────────────────────────────
    _scheduler.add_job(
        run_daily_reports,
        CronTrigger(hour=17, minute=0),
        id="daily_reports",
        name="Daily Report — 5:00 PM",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # ── Weekly report — every Friday at 17:15 ────────────────────────────────
    _scheduler.add_job(
        run_weekly_reports,
        CronTrigger(day_of_week="fri", hour=17, minute=15),
        id="weekly_reports",
        name="Weekly Report — Friday 5:15 PM",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # ── Monthly report — 30th of each month at 17:30 ─────────────────────────
    _scheduler.add_job(
        run_monthly_reports,
        CronTrigger(day=30, hour=17, minute=30),
        id="monthly_reports",
        name="Monthly Report — 30th 5:30 PM",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    # ── Gap 3: last-day fallback for months shorter than 30 days ─────────────
    # Fires on the last calendar day of every month at 17:35.
    # _run_monthly_if_short_month guards against double-firing on months with
    # exactly 30+ days (where the primary job already ran on the 30th).
    _scheduler.add_job(
        _run_monthly_if_short_month,
        CronTrigger(day="last", hour=17, minute=35),
        id="monthly_reports_short_month",
        name="Monthly Report — last-day fallback (short months)",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    # ── Gap 2: retention cleanup — every day at 02:00 ────────────────────────
    _scheduler.add_job(
        run_retention_cleanup,
        CronTrigger(hour=2, minute=0),
        id="retention_cleanup",
        name="Retention Cleanup — 2:00 AM",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    _scheduler.start()
    log.info(
        "Scheduler started. Jobs: daily@17:00, weekly(Fri)@17:15, "
        "monthly(30th)@17:30, monthly-fallback(last)@17:35, retention@02:00"
    )
    return True


def _run_monthly_if_short_month() -> None:
    """Only runs monthly reports when the current month has fewer than 30 days.
    Prevents double-firing for months where the 30th-day job already ran."""
    import calendar
    from datetime import date
    today = date.today()
    _, last_day = calendar.monthrange(today.year, today.month)
    if last_day < 30:
        log.info("Short-month fallback triggered for %s-%02d (last day=%d)",
                 today.year, today.month, last_day)
        from app.scheduler.jobs import run_monthly_reports
        run_monthly_reports()
    else:
        log.debug("Short-month fallback skipped — month has %d days, primary job handles it.", last_day)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped.")


def scheduler_status() -> dict:
    """Return current scheduler state for the API status endpoint."""
    if not _APSCHEDULER_AVAILABLE:
        return {
            "running":   False,
            "available": False,
            "message":   "APScheduler not installed — run: pip install apscheduler",
            "jobs":      [],
        }

    if not _scheduler or not _scheduler.running:
        return {"running": False, "available": True, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id":           job.id,
            "name":         job.name,
            "next_run_utc": next_run.isoformat() if next_run else None,
        })

    return {"running": True, "available": True, "jobs": jobs}
