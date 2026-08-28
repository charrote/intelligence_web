"""Extraction engine: extracts structured facts from intelligence records.

P1（合并规则）：同一篇情报只打 1 次 LLM，一次抽完所有启用规则的字段，
把 N×M 次调用降为 N 次。落库仍按规则拆分（每条规则写各自 rule_id），
下游报告聚合 / 事实查询完全不受影响。

安全设计：
  - LLM 侧字段 key 加规则前缀（{rule_id}__{field_key}），跨规则同 key 不冲突。
  - regex 快路径仍按规则分别跑（field_extractor 的 label windowing 依赖单规则
    字段顺序，合并会改变窗口切分导致串值），只合并 LLM 部分，regex 语义不变。
  - 数据库写入统一在主线程串行完成（单连接），避免多线程共享 SQLite 连接竞争。
  - content 超长截断，防止长文拖慢单次 LLM 调用。
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from core.db import get_db, get_setting, get_engine_domain_key
from core.scheduler.llm_client import call_llm, parse_json_from_response
from core.scheduler.prompt_renderer import render_extraction_prompt_multi
from core.scheduler.field_extractor import extract_fields_regex

logger = logging.getLogger(__name__)

# 默认配置（可被 settings 表 llm.extract_concurrency / llm.extract_content_max_chars 覆盖）
# 注意：本地 LLM 并发上限实测为 2 —— C=3 起输出退化（JSON 串词/格式错乱，失败率飙升）。
# 不要盲目调高；P1 合并规则后调用数已减半，C=2 即已足够。
DEFAULT_CONCURRENCY = 2
DEFAULT_CONTENT_MAX_CHARS = 8000
# 合并多规则后单篇输出可达 30+ 字段，1500 tokens 会截断导致 JSON 解析失败（线上实锤）。
# 4000 覆盖 30 字段 × ~100 token/字段的典型输出，留有余量。
DEFAULT_EXTRACT_MAX_TOKENS = 4000
# LLM 失败（extracted=2）的情报，距标记超过 24h 后自动重新抽取，避免永久丢数。
RETRY_AFTER_HOURS = 24


def extract_all_pending(db_path: str) -> dict:
    """
    Extract structured facts from all pending intelligence records.

    每篇情报 1 次 LLM 调用（合并全部启用规则），并发度由
    llm.extract_concurrency 控制。

    Returns:
        {"processed": int, "success": int, "failed": int}
    """
    concurrency = max(1, int(get_setting(db_path, "llm.extract_concurrency") or DEFAULT_CONCURRENCY))
    content_max_chars = max(0, int(get_setting(db_path, "llm.extract_content_max_chars") or DEFAULT_CONTENT_MAX_CHARS))
    max_tokens = max(1000, int(get_setting(db_path, "llm.extract_max_tokens") or DEFAULT_EXTRACT_MAX_TOKENS))

    with get_db(db_path) as conn:
        # extracted=0 新情报 + extracted=2 且距标记超过 RETRY_AFTER_HOURS 小时的失败情报（自动重试，避免永久丢数）
        retry_cutoff = (datetime.now(timezone.utc) - timedelta(hours=RETRY_AFTER_HOURS)).isoformat()
        pending = conn.execute(
            """SELECT id, title, content, extracted FROM intelligence
               WHERE extracted = 0
                  OR (extracted = 2 AND updated_at < ?)""",
            (retry_cutoff,),
        ).fetchall()

        if not pending:
            return {"processed": 0, "success": 0, "failed": 0}

        rules = conn.execute(
            "SELECT id, name, domain FROM intel_extraction_rule WHERE enabled = 1"
        ).fetchall()
        # Cross-domain guard: apply only rules belonging to THIS domain's own key.
        # A stray cross-domain row can never be used on this domain's intelligence.
        _own = get_engine_domain_key(conn)
        if _own is not None:
            rules = [r for r in rules if r["domain"] == _own]

        if not rules:
            # 无启用规则：整批直接标记完成
            for row in pending:
                conn.execute("UPDATE intelligence SET extracted = 1 WHERE id = ?", (row["id"],))
            conn.commit()
            logger.info(f"[extract] no enabled rules; marked {len(pending)} records done")
            return {"processed": len(pending), "success": len(pending), "failed": 0}

        # 预取规则字段（主线程，单连接）
        rule_fields = {r["id"]: _get_rule_fields(conn, r["id"]) for r in rules}

        # 为每条情报构建一个合并任务
        tasks = []
        for intel_row in pending:
            iid, title, content = intel_row["id"], intel_row["title"], intel_row["content"]

            # regex 快路径按规则分别跑（保留 windowing 语义）
            per_rule = []  # [(rule_id, rule_name, fields, regex_values, remaining)]
            for r in rules:
                rid, rname = r["id"], r["name"]
                fields = rule_fields[rid]
                regex_values, remaining = extract_fields_regex(fields, title, content)
                per_rule.append((rid, rname, fields, regex_values, remaining))

            # 收集所有规则的 remaining 字段，作为这一次 LLM 调用的字段集
            llm_rule_fields = [(rid, rname, remaining) for rid, rname, fields, _, remaining in per_rule if remaining]

            tasks.append({
                "id": iid,
                "title": title,
                "content": content,
                "per_rule": per_rule,
                "llm_rule_fields": llm_rule_fields,
                "_content_max_chars": content_max_chars,
                "_max_tokens": max_tokens,
            })

        total = len(tasks)
        logger.info(
            f"[extract] {total} intel × {len(rules)} rules → {total} merged LLM calls "
            f"(concurrency={concurrency}, content_max_chars={content_max_chars})"
        )

        # 并发执行每篇情报的合并 LLM 调用（worker 只做 LLM，结果存回 task）
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            for task in ex.map(_extract_intel_merged, tasks):
                _persist_intel(conn, task, rule_fields)

        processed = sum(1 for t in tasks if t.get("_row_success"))
        success = sum(1 for t in tasks if t.get("_row_success"))
        failed = total - success
        logger.info(f"[extract] done: processed={processed} success={success} failed={failed}")
        return {"processed": processed, "success": success, "failed": failed}


def _extract_intel_merged(task: dict) -> dict:
    """Run the single merged LLM call for one intel (worker). No DB access.

    结果（含规则前缀的原始 dict）写入 task["_llm_values"]；失败写入 task["_llm_error"]。
    返回 task 本身（供 ex.map 迭代）。
    """
    llm_rule_fields = task["llm_rule_fields"]
    if not llm_rule_fields:
        # 全部字段都被 regex 命中，无需 LLM
        task["_llm_values"] = {}
        return task

    db_path = _get_db_path()
    timeout = int(get_setting(db_path, "llm.extract_timeout") or 60)
    max_tokens = task.get("_max_tokens", DEFAULT_EXTRACT_MAX_TOKENS)

    content = task["content"] or ""
    max_chars = task.get("_content_max_chars", 0)
    if max_chars and len(content) > max_chars:
        content = content[:max_chars]

    # 最多重试一次：截断/偶发 JSON 解析失败时再给模型一次机会（失败即退避，不循环）
    for _attempt in range(2):
        try:
            system_prompt, user_prompt = render_extraction_prompt_multi(
                llm_rule_fields, task["title"], content
            )

            result = call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=max_tokens,
                timeout=timeout
            )

            if not result.get("ok"):
                task["_llm_values"] = None
                task["_llm_error"] = result.get("error", "LLM call failed")
                continue

            parsed, json_ok = parse_json_from_response(result["raw"])
            if not json_ok:
                task["_llm_values"] = None
                task["_llm_error"] = f"JSON parse failed. Raw: {result['raw'][:200]}"
                continue

            task["_llm_values"] = parsed if isinstance(parsed, dict) else {}
            return task
        except Exception as e:
            task["_llm_values"] = None
            task["_llm_error"] = str(e)

    return task


def _persist_intel(conn, task: dict, rule_fields: dict) -> None:
    """Merge regex + LLM values per rule and save to intel_fact (main thread, single connection)."""
    llm_values = task.get("_llm_values")
    if llm_values is None and task.get("_llm_error"):
        logger.warning(f"[extract] LLM failed intel={task['id']}: {task['_llm_error']}")

    intel_id = task["id"]
    llm_ok = llm_values is not None
    for rid, rname, fields, regex_values, remaining in task["per_rule"]:
        # regex 结果不依赖 LLM：LLM 失败时 regex 命中的字段照常落库（信息不丢）
        merged = {}
        for f in fields:
            fk = f["field_key"]
            if fk in regex_values:
                merged[fk] = regex_values[fk]
            elif llm_ok:
                prefixed = f"{rid}__{fk}"
                if prefixed in llm_values and llm_values[prefixed] is not None:
                    merged[fk] = llm_values[prefixed]

        _save_facts(conn, intel_id, rid, fields, merged)

    # 行级成功 = LLM 成功（纯 regex 行 _llm_values={} 视为成功）；
    # 更新 updated_at 作为 24h 自动重试计时器（_persist 的标记时间戳）
    new_status = 1 if llm_ok else 2
    conn.execute(
        "UPDATE intelligence SET extracted = ?, updated_at = ? WHERE id = ?",
        (new_status, datetime.now(timezone.utc).isoformat(), intel_id),
    )
    conn.commit()
    task["_row_success"] = llm_ok


def _get_rule_fields(conn, rule_id: int) -> list:
    """Get field list for an extraction rule."""
    rows = conn.execute(
        "SELECT * FROM intel_extraction_field WHERE rule_id = ? ORDER BY sort_order",
        (rule_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _get_db_path() -> str:
    """Get the database path for the scheduler (configurable per domain)."""
    import os
    from core.db import get_db_path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_slug = os.environ.get("ANALYZER_DB_SLUG", "intelligence")
    return get_db_path(project_root, db_slug)



def _save_facts(conn, intel_id: int, rule_id: int, fields: list,
                data: dict) -> int:
    """Save extracted facts to intel_fact table (Plan A: consolidated columns).

    幂等：先删 (intel_id, rule_id) 的旧事实再插入 —— 重抽（手动 retrigger /
    24h 自动重试）不会重复落库。
    """
    now = datetime.now(timezone.utc).isoformat()
    count = 0

    conn.execute(
        "DELETE FROM intel_fact WHERE intel_id = ? AND rule_id = ?",
        (intel_id, rule_id),
    )

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