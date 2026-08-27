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
    """Get the database path for the scheduler (configurable per domain)."""
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_slug = os.environ.get("ANALYZER_DB_SLUG", "intelligence")
    return get_db_path(project_root, db_slug)


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

    # 搜刮调度（从 config/search.json 读取时间）
    try:
        from config import get_search_config
        scfg = get_search_config()
        if scfg.get("enabled", True):
            h1 = int(scfg.get("cron_hour", 8))
            h2 = int(scfg.get("cron_hour2", 14))
            scheduler.add_job(
                func=_run_search_cycle,
                trigger=CronTrigger(hour=h1, minute=0),
                id="search_cycle",
                replace_existing=True,
                misfire_grace_time=120,
            )
            if h2 != h1:
                scheduler.add_job(
                    func=_run_search_cycle,
                    trigger=CronTrigger(hour=h2, minute=0),
                    id="search_cycle_2",
                    replace_existing=True,
                    misfire_grace_time=120,
                )
            logger.info(f"[scheduler] search_cycle registered: {h1}:00, {h2}:00")
    except Exception as e:
        logger.warning(f"[scheduler] Failed to register search_cycle: {e}")

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


def _run_search_cycle():
    """Search cycle — run self-driven intelligence search for this domain."""
    from core.scheduler.search_cycle import run_search_cycle

    logger.info("[search_cycle] Running self-driven search cycle")
    try:
        result = run_search_cycle()
        logger.info(
            f"[search_cycle] Done: domain={result.get('domain')}, "
            f"projects={result.get('projects_processed')}, "
            f"new_intel={result.get('new_intel')}, "
            f"llm_calls={result.get('llm_calls')}"
        )
        _update_scheduler("last_search_time", _now_iso())
    except Exception as e:
        logger.error(f"[search_cycle] Error: {e}")


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


def trigger_extract_async():
    """Manually trigger one extraction cycle in the background (called from API).

    Returns immediately with {"ok": True, "started": True}; the extraction
    runs in a daemon thread. Progress is observable via /api/extract/stats
    (pending_extract count) and report_scheduler.last_extract_time.
    """
    import threading
    from core.scheduler.extraction_engine import extract_all_pending
    db_path = _get_db_path()

    def _worker():
        try:
            result = extract_all_pending(db_path)
            logger.info(f"[manual_extract] Done: {result}")
            _update_scheduler("last_extract_time", _now_iso())
        except Exception as e:
            logger.error(f"[manual_extract] Error: {e}")

    threading.Thread(target=_worker, daemon=True).start()
    return {"ok": True, "started": True}


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
