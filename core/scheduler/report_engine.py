"""Report engine: executes scheduled report generation."""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

from core.db import get_db, get_setting, get_db_path
from core.scheduler.llm_client import call_llm, parse_json_from_response
from core.scheduler.prompt_renderer import render_report_prompt
from core.scheduler.sql_aggregator import aggregate

logger = logging.getLogger(__name__)


def _get_db_path():
    """Get the database path for the scheduler (configurable per domain)."""
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_slug = os.environ.get("ANALYZER_DB_SLUG", "intelligence")
    return get_db_path(project_root, db_slug)


def run_scheduled_reports(db_path: str) -> dict:
    """Execute all due scheduled reports."""
    executed = 0
    success = 0
    failed = 0

    with get_db(db_path) as conn:
        templates = conn.execute(
            """SELECT * FROM intel_aggregate
               WHERE enabled = 1 AND next_run <= ? AND status != 'fused'
               ORDER BY next_run""",
            (datetime.now(timezone.utc).isoformat(),)
        ).fetchall()

        for tmpl in templates:
            template_dict = dict(tmpl)
            executed += 1

            result = run_single_report_internal(db_path, template_dict, conn)
            if result.get("ok"):
                success += 1
                _update_template_success(conn, template_dict["id"])
            elif result.get("no_data"):
                # 空数据不是失败：不清零也不累计 fail_count，仅刷新 next_run
                _update_template_success(conn, template_dict["id"])
            else:
                failed += 1
                _handle_failure(conn, template_dict["id"], result.get("error"))

    return {"executed": executed, "success": success, "failed": failed}


def _execute_report_steps(db_path: str, conn, run_id: int, template_dict: dict) -> dict:
    """Execute aggregation → charts → LLM → write results for an existing run_id."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        # Step 1: SQL aggregation
        agg_result = aggregate(db_path, template_dict)
        if agg_result.get("error"):
            _update_run_status(conn, run_id, "failed", error_msg=agg_result["error"])
            return {"ok": False, "error": f"Aggregation failed: {agg_result['error']}"}

        # Step 1.5: 空数据兜底 — 聚合无事实时跳过 LLM，明确标记 no_data
        if not agg_result.get("rows") and not agg_result.get("fact_count"):
            msg = (
                "所选时间范围内没有已抽取的事实数据（intel_fact 为空）。"
                "请先执行抽取，再运行报告。"
            )
            _update_run_status(conn, run_id, "no_data", error_msg=msg)
            return {"ok": False, "error": msg, "no_data": True}

        # Step 2: Build chart data
        chart_data = _build_charts(template_dict, agg_result["rows"])

        # Step 3: Render prompt
        system_prompt, user_prompt = render_report_prompt(
            report_name=template_dict["name"],
            start_date=_calc_start_date(template_dict["lookback_days"]),
            end_date=now,
            fact_count=agg_result["fact_count"],
            aggregated_data=json.dumps(agg_result["rows"], ensure_ascii=False),
            chart_data=json.dumps(chart_data, ensure_ascii=False),
            prompt_template=template_dict["prompt_template"],
        )

        # Step 4: LLM analysis
        db_path = _get_db_path()
        timeout = int(get_setting(db_path, "llm.report_timeout") or "120")
        llm_result = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=1500,
            timeout=timeout,
        )
        if not llm_result.get("ok"):
            _update_run_status(conn, run_id, "failed", error_msg=llm_result.get("error") or "LLM call failed")
            return {"ok": False, "error": llm_result.get("error")}

        parsed, json_ok = parse_json_from_response(llm_result["raw"])
        if not json_ok:
            _update_run_status(conn, run_id, "failed", error_msg="Report LLM JSON parse failed")
            return {"ok": False, "error": "Report LLM JSON parse failed"}

        # Step 5: Write report_run
        _update_run_result(conn, run_id, {
            "aggregated_data": json.dumps(agg_result["rows"], ensure_ascii=False),
            "output_analysis": parsed.get("analysis", ""),
            "output_charts": json.dumps(chart_data, ensure_ascii=False),
            "output_summary": parsed.get("summary", ""),
            "fact_count": agg_result["fact_count"],
        })
        return {"ok": True}

    except Exception as e:
        logger.error(f"Report execution error template={template_dict['id']}: {e}")
        try:
            _update_run_status(conn, run_id, "failed", error_msg=str(e))
        except Exception:
            pass
        return {"ok": False, "error": str(e)}


def run_single_report_internal(db_path: str, template_dict: dict, conn) -> dict:
    """Execute a single report (no retry) — used by the scheduler (blocking is fine there)."""
    now = datetime.now(timezone.utc).isoformat()
    run_id = _create_run_record(conn, template_dict["id"], now, template_dict.get("domain") or "research")
    return _execute_report_steps(db_path, conn, run_id, template_dict)


def run_single_report(db_path: str, template_id: int) -> dict:
    """Manually trigger single report (async).

    Creates the run record, returns run_id immediately, then executes the
    report in a background thread so the frontend can poll status via
    /api/reports/runs/<template_id>.
    """
    import threading
    now = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        template = conn.execute(
            "SELECT * FROM intel_aggregate WHERE id = ?", (template_id,)
        ).fetchone()
        if not template:
            return {"ok": False, "error": "Template not found"}
        template_dict = dict(template)
        run_id = _create_run_record(
            conn, template_dict["id"], now, template_dict.get("domain") or "research"
        )

    def _worker():
        try:
            with get_db(db_path) as wconn:
                _execute_report_steps(db_path, wconn, run_id, template_dict)
        except Exception as e:
            # Defensive: any unhandled error in the worker thread must mark
            # the run as failed, otherwise it stays 'running' forever.
            logger.error(f"report worker crashed template={template_id}: {e}")
            try:
                with get_db(db_path) as wconn:
                    _update_run_status(wconn, run_id, "failed", error_msg=f"Worker error: {e}")
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()
    return {"ok": True, "run_id": run_id}


# ─── Helpers ──────────────────────────────────────────────────

def _create_run_record(conn, template_id: int, scheduled_time: str, domain: str = 'research') -> int:
    """Create a report_run record, return run_id."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """INSERT INTO report_run
           (template_id, domain, scheduled_time, status, started_at, created_at)
           VALUES (?, ?, ?, 'running', ?, ?)""",
        (template_id, domain, scheduled_time, now, now)
    )
    conn.commit()
    return cursor.lastrowid


def _update_run_status(conn, run_id: int, status: str, error_msg: str = None):
    """Update run status."""
    now = datetime.now(timezone.utc).isoformat()
    if error_msg:
        conn.execute(
            "UPDATE report_run SET status = ?, completed_at = ?, error_msg = ? WHERE id = ?",
            (status, now, error_msg, run_id)
        )
    else:
        conn.execute(
            "UPDATE report_run SET status = ?, completed_at = ? WHERE id = ?",
            (status, now, run_id)
        )
    conn.commit()


def _update_run_result(conn, run_id: int, data: dict) -> None:
    """Update run to completed with results."""
    now = datetime.now(timezone.utc).isoformat()
    # Calculate duration from started_at
    row = conn.execute("SELECT started_at FROM report_run WHERE id = ?", (run_id,)).fetchone()
    duration = 0
    if row and row["started_at"]:
        try:
            start = datetime.fromisoformat(row["started_at"])
            end = datetime.fromisoformat(now)
            duration = max(0, int((end - start).total_seconds()))
        except (ValueError, TypeError):
            duration = 0
    conn.execute(
        """UPDATE report_run SET
           status = 'completed',
           completed_at = ?,
           duration_sec = ?,
           aggregated_data = ?,
           output_analysis = ?,
           output_charts = ?,
           output_summary = ?,
           fact_count = ?
           WHERE id = ?""",
        (now, duration, data.get("aggregated_data"), data.get("output_analysis"),
         data.get("output_charts"), data.get("output_summary"),
         data.get("fact_count"), run_id)
    )
    conn.commit()


def _update_template_success(conn, template_id: int):
    """Update template after successful execution."""
    now = datetime.now(timezone.utc).isoformat()
    schedule_min = 1440
    try:
        schedule_min = int(conn.execute(
            "SELECT schedule_minutes FROM intel_aggregate WHERE id = ?", (template_id,)
        ).fetchone()[0])
    except Exception:
        pass

    conn.execute(
        """UPDATE intel_aggregate SET
           fail_count = 0,
           last_success_time = ?,
           next_run = datetime(?, '+' || ? || ' minutes')
           WHERE id = ?""",
        (now, now, schedule_min, template_id)
    )
    conn.commit()


def _handle_failure(conn, template_id: int, error_msg: str):
    """Handle failure: increment fail_count, check fuse threshold."""
    now = datetime.now(timezone.utc).isoformat()
    db_path = _get_db_path()
    fuse_threshold = int(get_setting(db_path, "report.fuse_threshold") or "3")

    conn.execute(
        """UPDATE intel_aggregate SET
           fail_count = fail_count + 1,
           last_fail_time = ?
           WHERE id = ?""",
        (now, template_id)
    )
    conn.commit()

    row = conn.execute(
        "SELECT fail_count FROM intel_aggregate WHERE id = ?", (template_id,)
    ).fetchone()

    if row["fail_count"] >= fuse_threshold:
        conn.execute(
            "UPDATE intel_aggregate SET status = 'fused' WHERE id = ?",
            (template_id,)
        )
        conn.commit()
        logger.warning(f"Template {template_id} fused after {row['fail_count']} consecutive failures")


def _build_charts(template_dict: dict, rows: list) -> list:
    """Convert aggregated data to ECharts format based on chart_config."""
    configs = json.loads(template_dict.get("chart_config", "[]"))
    charts = []

    for config in configs:
        chart_type = config.get("type", "bar")
        title = config.get("title", "图表")
        name_field = config.get("name_field", "entity_name")
        value_field = config.get("value_field", "metric_0")

        data = []
        for row in rows:
            item = {}
            if name_field in row:
                item["name"] = row[name_field]
            else:
                item["name"] = str(row.get("entity_name", ""))
            if value_field in row:
                item["value"] = row[value_field]
            else:
                item["value"] = 0
            data.append(item)

        charts.append({
            "type": chart_type,
            "title": title,
            "data": data
        })

    return charts


def _calc_start_date(lookback_days: int) -> str:
    """Calculate start date for lookback period."""
    start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return start.strftime("%Y-%m-%d")
