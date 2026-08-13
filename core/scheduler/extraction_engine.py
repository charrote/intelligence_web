"""Extraction engine: extracts structured facts from intelligence records."""
import json
import logging
from datetime import datetime, timezone

from core.db import get_db, get_setting
from core.scheduler.llm_client import call_llm, parse_json_from_response
from core.scheduler.prompt_renderer import render_extraction_prompt

logger = logging.getLogger(__name__)


def extract_all_pending(db_path: str) -> dict:
    """
    Extract structured facts from all pending intelligence records.

    Args:
        db_path: path to the SQLite database

    Returns:
        {"processed": int, "success": int, "failed": int}
    """
    processed = 0
    success = 0
    failed = 0

    with get_db(db_path) as conn:
        pending = conn.execute(
            "SELECT id, title, content FROM intelligence WHERE extracted = 0"
        ).fetchall()

        if not pending:
            return {"processed": 0, "success": 0, "failed": 0}

        rules = conn.execute(
            "SELECT id, name FROM intel_extraction_rule WHERE enabled = 1"
        ).fetchall()

        for intel_row in pending:
            intel_id = intel_row["id"]
            intel_title = intel_row["title"]
            intel_content = intel_row["content"]
            row_success = True

            for rule_row in rules:
                rule_id = rule_row["id"]
                rule_name = rule_row["name"]
                fields = _get_rule_fields(conn, rule_id)
                result = _extract_single(intel_id, rule_id, rule_name,
                                          fields, intel_title, intel_content, conn)
                if not result["ok"]:
                    row_success = False
                    logger.warning(f"Extract failed intel={intel_id} rule={rule_id}: {result.get('error')}")

            new_status = 1 if row_success else 2
            conn.execute(
                "UPDATE intelligence SET extracted = ? WHERE id = ?",
                (new_status, intel_id)
            )
            conn.commit()

            if row_success:
                success += 1
            else:
                failed += 1
            processed += 1

    return {"processed": processed, "success": success, "failed": failed}


def _get_rule_fields(conn, rule_id: int) -> list:
    """Get field list for an extraction rule."""
    rows = conn.execute(
        "SELECT * FROM intel_extraction_field WHERE rule_id = ? ORDER BY sort_order",
        (rule_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _extract_single(intel_id: int, rule_id: int, rule_name: str,
                     fields: list, intel_title: str, intel_content: str,
                     conn) -> dict:
    """Extract facts for a single intel x single rule."""
    db_path = _get_db_path()
    timeout = int(get_setting(db_path, "llm.extract_timeout")) if get_setting(db_path, "llm.extract_timeout") else 60

    system_prompt, user_prompt = render_extraction_prompt(
        rule_name, fields, intel_title, intel_content
    )

    result = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=500,
        timeout=timeout
    )

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "LLM call failed")}

    parsed, json_ok = parse_json_from_response(result["raw"])
    if not json_ok:
        return {"ok": False, "error": f"JSON parse failed. Raw: {result['raw'][:200]}"}

    fact_count = _save_facts(conn, intel_id, rule_id, fields, parsed)
    return {"ok": True, "fact_count": fact_count}


def _get_db_path() -> str:
    """Get the default database path for the scheduler."""
    import os
    from core.db import get_db_path
    # Use current directory as project root, 'intelligence' as slug
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return get_db_path(project_root, "intelligence")


def _save_facts(conn, intel_id: int, rule_id: int, fields: list,
                data: dict) -> int:
    """Save extracted facts to intel_fact table."""
    now = datetime.now(timezone.utc).isoformat()
    count = 0

    for field in fields:
        fk = field["field_key"]
        value = data.get(fk)
        if value is None:
            continue

        entity_name = ""
        metric_name = ""
        metric_value = None
        metric_unit = ""
        time_period = ""
        context = ""

        ft = field["field_type"]
        if ft == "company":
            entity_name = str(value)
        elif ft in ("pct", "number"):
            metric_name = field["field_label"]
            metric_value = _safe_float(value)
            if ft == "pct":
                metric_unit = "%"
        elif ft == "currency":
            metric_name = field["field_label"]
            metric_value = _safe_float(value)
        elif ft == "currency_code":
            metric_unit = str(value)
        elif ft == "location":
            entity_name = str(value)
        elif ft == "year":
            metric_name = "年份"
            metric_value = _safe_float(value)
            metric_unit = "年"
        elif ft == "date":
            time_period = str(value)
        elif ft == "text":
            context = str(value)

        conn.execute(
            """INSERT INTO intel_fact
               (intel_id, rule_id, field_key, entity_name, metric_name,
                metric_value, metric_unit, time_period, context, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (intel_id, rule_id, fk, entity_name, metric_name,
             metric_value, metric_unit, time_period, context, "high", now)
        )
        count += 1

    return count


def _safe_float(val) -> float:
    """Safely convert to float."""
    try:
        return float(str(val).replace(",", "").replace("，", ""))
    except (ValueError, TypeError):
        return 0.0
