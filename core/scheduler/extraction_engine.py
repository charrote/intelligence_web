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
    """Extract facts for a single intel x single rule.

    Hybrid strategy:
      1. Regex fast path handles numeric-ish fields (number/pct/currency/
         currency_code/date/year) — deterministic, zero LLM cost.
      2. LLM only processes the remaining fields (company/location/text,
         plus regex-missed numerics as fallback).
      3. If there is nothing left for the LLM, skip the call entirely.
    """
    from core.scheduler.field_extractor import extract_fields_regex

    db_path = _get_db_path()

    # Step 1: regex fast path
    regex_values, remaining_fields = extract_fields_regex(
        fields, intel_title, intel_content
    )

    # Step 2: LLM for the rest (entity/text fields + regex misses)
    llm_values: dict = {}
    if remaining_fields:
        timeout = int(get_setting(db_path, "llm.extract_timeout") or 60)

        system_prompt, user_prompt = render_extraction_prompt(
            rule_name, remaining_fields, intel_title, intel_content
        )

        result = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=500,
            timeout=timeout
        )

        if not result.get("ok"):
            # Preserve pre-hybrid semantics: LLM failure → row marked failed
            return {"ok": False, "error": result.get("error", "LLM call failed")}

        parsed, json_ok = parse_json_from_response(result["raw"])
        if not json_ok:
            return {"ok": False,
                    "error": f"JSON parse failed. Raw: {result['raw'][:200]}"}
        llm_values = parsed if isinstance(parsed, dict) else {}

    # Step 3: merge (regex wins; LLM fills the gaps) and save
    merged: dict = {}
    for f in fields:
        fk = f.get("field_key", "")
        if fk in regex_values:
            merged[fk] = regex_values[fk]
        elif fk in llm_values and llm_values[fk] is not None:
            merged[fk] = llm_values[fk]

    fact_count = _save_facts(conn, intel_id, rule_id, fields, merged)
    return {
        "ok": True,
        "fact_count": fact_count,
        "regex_count": len(regex_values),
        "llm_count": len(remaining_fields),
    }


def _get_db_path() -> str:
    """Get the database path for the scheduler (configurable per domain)."""
    import os
    from core.db import get_db_path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_slug = os.environ.get("ANALYZER_DB_SLUG", "intelligence")
    return get_db_path(project_root, db_slug)


def _save_facts(conn, intel_id: int, rule_id: int, fields: list,
                data: dict) -> int:
    """Save extracted facts to intel_fact table (Plan A: consolidated columns)."""
    now = datetime.now(timezone.utc).isoformat()
    count = 0

    for field in fields:
        fk = field["field_key"]
        value = data.get(fk)
        if value is None:
            continue

        ft = field["field_type"]
        field_label = field["field_label"]
        value_text = ""
        value_num = None
        value_type = ft
        entity_name = ""
        time_period = ""

        if ft in ("company", "location"):
            # 实体类字段：值存 value_text，实体名存 entity_name
            value_text = str(value)
            entity_name = value_text
        elif ft in ("pct", "number", "year"):
            # 数值类字段：标签存 field_label，数值存 value_num
            field_label = field_label if ft != "year" else "年份"
            value_text = str(value)
            value_num = _safe_float(value)
        elif ft == "currency":
            # 金额：标签存 field_label，数值存 value_num
            value_text = str(value)
            value_num = _safe_float(value)
        elif ft == "currency_code":
            # 货币代码：纯文本
            value_text = str(value)
        elif ft == "date":
            # 日期：存 time_period
            time_period = str(value)
            value_text = str(value)
        elif ft == "text":
            # 任意文本
            value_text = str(value)

        conn.execute(
            """INSERT INTO intel_fact
               (intel_id, rule_id, field_key, field_label, value_text,
                value_num, value_type, entity_name, time_period, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (intel_id, rule_id, fk, field_label, value_text,
             value_num, value_type, entity_name, time_period, "high", now)
        )
        count += 1

    return count


def _safe_float(val) -> float:
    """Safely convert to float."""
    try:
        return float(str(val).replace(",", "").replace("，", ""))
    except (ValueError, TypeError):
        return 0.0
