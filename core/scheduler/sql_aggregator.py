"""SQL aggregator: builds and executes aggregation queries from intel_fact."""
import json
import logging
from datetime import datetime, timedelta, timezone

from core.db import get_db

logger = logging.getLogger(__name__)


def aggregate(db_path: str, template: dict) -> dict:
    """
    Aggregate data from intel_fact based on report template configuration.

    单查询完成 fact_count + 全部指标聚合（基于 value_num 列的条件聚合），
    filters 对实体与指标一致生效（旧版 N+1 子查询漏掉 filters 导致
    实体被过滤而数值未过滤，报表数字对不上）。

    Args:
        db_path: path to the SQLite database
        template: report template dict with group_by, metrics, filters, rule_id, lookback_days

    Returns:
        {"rows": [...], "fact_count": int, "error": str|None}
    """
    try:
        with get_db(db_path) as conn:
            # 1. Build WHERE clause（与旧版相同，但统一走参数化）
            where_clause = "WHERE rule_id = ?"
            params = [template['rule_id']]

            # Time filter
            lookback = template.get("lookback_days", 30)
            cutoff = datetime.now(timezone.utc) - timedelta(days=lookback)
            where_clause += " AND created_at >= ?"
            params.append(cutoff.isoformat())

            # Custom filter conditions
            filters = json.loads(template.get("filters", "[]"))
            filter_clauses, filter_params = _build_filter_clauses(filters)
            if filter_clauses:
                where_clause += " AND " + " AND ".join(filter_clauses)
                params.extend(filter_params)

            # 2. Group field
            group_field = _map_group_field(template.get("group_by", "entity_name"))

            # 3. Metrics → 条件聚合列（value_num 只有数值类字段有值；
            #    AVG/SUM/MAX/MIN 自动忽略 NULL，COUNT 统计非空值）。
            #    注意参数顺序：SELECT 里的 metric 占位符在 WHERE 之前，
            #    所以 metric_params 必须放在 where_params 之前执行。
            metrics = json.loads(template.get("metrics", "[]"))
            metric_cols = []
            metric_params = []
            for i, m in enumerate(metrics):
                field_key = m.get("field_key", "")
                agg_fn = (m.get("agg") or "avg").lower()
                fn = {"avg": "AVG", "sum": "SUM", "max": "MAX", "min": "MIN", "count": "COUNT"}.get(agg_fn, "AVG")
                metric_cols.append(
                    f"{fn}(CASE WHEN field_key = ? THEN value_num END) AS metric_{i}"
                )
                metric_params.append(field_key)

            # 4. 单条查询：实体 + 事实数 + 全部指标
            select_items = [
                f"{group_field} AS entity_name",
                "COUNT(DISTINCT intel_id) AS fact_count",
            ] + metric_cols
            base_sql = f"""
                SELECT {", ".join(select_items)}
                FROM intel_fact
                {where_clause}
                GROUP BY {group_field}
                ORDER BY entity_name
            """
            # 参数顺序 = SQL 中 ? 出现顺序：SELECT(metric_params) 在前，WHERE(params) 在后
            rows = conn.execute(base_sql, metric_params + params).fetchall()

            enriched_rows = []
            for r in rows:
                d = dict(r)
                for i, m in enumerate(metrics):
                    v = d.get(f"metric_{i}")
                    is_count = (m.get("agg") or "avg").lower() == "count"
                    if v is None:
                        d[f"metric_{i}"] = 0
                    elif is_count:
                        d[f"metric_{i}"] = int(v)
                    else:
                        d[f"metric_{i}"] = round(v, 2)
                    d[f"metric_{i}_unit"] = m.get("unit", "")
                enriched_rows.append(d)

            return {
                "rows": enriched_rows,
                "fact_count": sum(r["fact_count"] for r in enriched_rows),
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
