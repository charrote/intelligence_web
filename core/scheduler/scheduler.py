"""Report scheduler: APScheduler-based background task runner."""
import json
import logging
import signal
import sys
import time
import os
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.db import get_db, get_setting, get_db_path

logger = logging.getLogger(__name__)

scheduler = None  # Global scheduler instance


def _get_db_path():
    """Get the default database path for the scheduler."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return get_db_path(project_root, "intelligence")


def start_scheduler():
    """Start the scheduler as a background daemon."""
    global scheduler

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=_run_extract_cycle,
        trigger=IntervalTrigger(minutes=10),
        id="extract_cycle",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        func=_run_report_cycle,
        trigger=IntervalTrigger(minutes=5),
        id="report_cycle",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        func=_run_cleanup,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_cleanup",
        replace_existing=True,
    )

    logger.info("Scheduler starting...")
    scheduler.start()
    logger.info("Scheduler started (extract=10min, report=5min, cleanup=08:00)")

    def _signal_handler(signum, frame):
        logger.info("Scheduler shutting down...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


def _run_extract_cycle():
    """Extraction cycle — runs every extract_interval_min."""
    from core.scheduler.extraction_engine import extract_all_pending

    db_path = _get_db_path()
    enabled = get_setting(db_path, "scheduler.extract_enabled") or "1"
    if enabled == "0":
        return

    logger.info("[extract_cycle] Running extraction cycle")

    try:
        result = extract_all_pending(db_path)
        logger.info(f"[extract_cycle] Processed {result['processed']}: success={result['success']}, failed={result['failed']}")
        _update_scheduler("last_extract_time", _now_iso())
    except Exception as e:
        logger.error(f"[extract_cycle] Error: {e}")


def _run_report_cycle():
    """Report cycle — runs every report_interval_min."""
    from core.scheduler.report_engine import run_scheduled_reports

    db_path = _get_db_path()
    enabled = get_setting(db_path, "scheduler.report_enabled") or "1"
    if enabled == "0":
        return

    logger.info("[report_cycle] Running report cycle")

    try:
        result = run_scheduled_reports(db_path)
        logger.info(f"[report_cycle] Executed {result['executed']}: success={result['success']}, failed={result['failed']}")
        _update_scheduler("last_report_time", _now_iso())
    except Exception as e:
        logger.error(f"[report_cycle] Error: {e}")


def _run_cleanup():
    """Daily cleanup — delete report_run records older than retention_days."""
    db_path = _get_db_path()
    keep_days = int(get_setting(db_path, "report.retention_days") or "30")

    with get_db(db_path) as conn:
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        deleted = conn.execute(
            "DELETE FROM report_run WHERE completed_at < ?",
            (cutoff.isoformat(),)
        ).rowcount
        conn.commit()

    if deleted > 0:
        logger.info(f"[cleanup] Deleted {deleted} expired report_run records")

    _update_scheduler("last_cleanup_time", _now_iso())


def _update_scheduler(field: str, value):
    """Update report_scheduler status field."""
    db_path = _get_db_path()
    now = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE report_scheduler SET {field} = ?, updated_at = ? WHERE id = 1",
            (value, now)
        )
        conn.commit()


# ─── Manual trigger functions ─────────────────────────────────

def trigger_extract_once():
    """Manually trigger one extraction cycle (called from API)."""
    from core.scheduler.extraction_engine import extract_all_pending
    db_path = _get_db_path()
    return extract_all_pending(db_path)


def trigger_report_once(template_id: int):
    """Manually trigger one report execution (called from API)."""
    from core.scheduler.report_engine import run_single_report
    db_path = _get_db_path()
    return run_single_report(db_path, template_id)


def trigger_report_all():
    """Manually trigger all due reports (called from API)."""
    from core.scheduler.report_engine import run_scheduled_reports
    db_path = _get_db_path()
    return run_scheduled_reports(db_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
