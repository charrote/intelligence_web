"""SQL aggregator: builds and executes aggregation queries from intel_fact."""
import json
import logging
from datetime import datetime, timedelta, timezone

from core.db import get_db

logger = logging.getLogger(__name__)


def aggregate(db_path: str, template: dict) -> dict:
    """
    Aggregate data from intel_fact based on report template configuration.

    Args:
        db_path: path to the SQLite database
        template: report template dict with group_by, metrics, filters, rule_id, lookback_days

    Returns:
        {"rows": [...], "fact_count": int, "error": str|None}
    """
    try:
        with get_db(db_path) as conn:
            # 1. Build WHERE clause
            where_clause = f"WHERE main.rule_id = ?"
            params = [template['rule_id']]

            # Time filter
            lookback = template.get("lookback_days", 30)
            cutoff = datetime.now(timezone.utc) - timedelta(days=lookback)
            where_clause += f" AND main.created_at >= '{cutoff.isoformat()}'"

            # Custom filter conditions
            filters = json.loads(template.get("filters", "[]"))
            filter_clauses, filter_params = _build_filter_clauses(filters)
            if filter_clauses:
                where_clause += " AND " + " AND ".join(filter_clauses)
                params.extend(filter_params)

            # 2. Build GROUP BY
            group_field = _map_group_field(template.get("group_by", "entity_name"))
            group_clause = f"GROUP BY main.{group_field}"

            # 3. Build SELECT with metrics
            metrics = json.loads(template.get("metrics", "[]"))

            # 4. Build main query - count facts per entity
            base_sql = f"""
                SELECT main.{group_field} AS entity_name,
                       COUNT(DISTINCT main.intel_id) AS fact_count
                FROM intel_fact main
                {where_clause}
                {group_clause}
                ORDER BY entity_name
            """

            rows = conn.execute(base_sql, params).fetchall()
            result_rows = [dict(r) for r in rows]

            # 5. Enrich with metric values via sub-queries
            #    Value is stored in value_text (all types use one column)
            enriched_rows = []
            for row in result_rows:
                enriched = dict(row)
                for i, m in enumerate(metrics):
                    field_key = m.get("field_key", "")
                    agg_fn = m.get("agg", "avg")
                    unit = m.get("unit", "")

                    sub_sql = f"""
                        SELECT value_text
                        FROM intel_fact
                        WHERE rule_id = ? AND {group_field} = ?
                          AND field_key = ?
                          AND created_at >= ?
                    """
                    sub_params = [template['rule_id'], enriched['entity_name'],
                                  field_key, cutoff.isoformat()]
                    sub_rows = conn.execute(sub_sql, sub_params).fetchall()

                    # Convert string values to numbers for aggregation
                    values = []
                    for r in sub_rows:
                        raw = r["value_text"]
                        if raw is not None and raw != "":
                            try:
                                values.append(float(str(raw).replace(",", "").replace("，", "")))
                            except (ValueError, TypeError):
                                pass

                    enriched[f"metric_{i}"] = _apply_agg(values, agg_fn) if values else 0
                    enriched[f"metric_{i}_unit"] = unit
                enriched_rows.append(enriched)

            return {
                "rows": enriched_rows,
                "fact_count": sum(r["fact_count"] for r in result_rows),
                "error": None
            }

    except Exception as e:
        logger.error(f"Aggregation failed: {e}")
        return {"rows": [], "fact_count": 0, "error": str(e)}


def _map_group_field(group_by: str) -> str:
    """Map group_by config to intel_fact column."""
    mapping = {
        "entity_name": "entity_name",
        "time_period": "time_period",
        "value_text": "value_text",
        "value_type": "value_type",
        "country": "entity_name",
    }
    return mapping.get(group_by, "entity_name")


def _apply_agg(values: list, agg: str) -> float:
    """Apply aggregation function to values."""
    if not values:
        return 0.0
    mapping = {
        "avg": lambda vs: round(sum(vs) / len(vs), 2),
        "sum": lambda vs: round(sum(vs), 2),
        "max": lambda vs: round(max(vs), 2),
        "min": lambda vs: round(min(vs), 2),
        "count": lambda vs: len(vs),
    }
    fn = mapping.get(agg, mapping["avg"])
    return fn(values)


def _build_filter_clauses(filters: list) -> tuple:
    """Build SQL filter clauses from filter config."""
    clauses = []
    params = []
    for f in filters:
        fk = f.get("field_key", "")
        op = f.get("op", "eq")
        val = f.get("value", "")

        # Map field_key to column: company/location → entity_name, others → value_text
        if fk in ("country", "location"):
            col = "entity_name"
        else:
            col = "value_text"
        clause = f"({col} = ?)"
        clauses.append(clause)
        params.append(val)

    return clauses, params
