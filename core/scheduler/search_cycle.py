"""Self-driven intelligence search cycle.

Replaces external Agent cron (OpenClaw etc.) with in-system orchestration.
LLM is used only for:
  ① Constructing 3-5 search keywords from project context
  ② Judging relevance + extracting summary (≤400 chars)

Everything else (search, read, dedup, create, status) is deterministic Python.

Runs inside each domain container (research/sales), processes only that
container's own domain DB (identified by ANALYZER_DB_SLUG env var).
"""

import logging
import os
import json
import re
import time
import requests
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_REQUEST_TIMEOUT = 20

# 采集频率 → 到期间隔（小时）。oneshot 无自动调度（tick 到期判定只认 >=1h 的频率）。
_FREQ_HOURS = {
    'hourly': 1,
    'daily': 24,
    'weekly': 7 * 24,
    'monthly': 30 * 24,
}


# ── Config ──────────────────────────────────────────────────

def _get_config() -> dict:
    from config import get_search_config
    return get_search_config()


# ── LLM calls ───────────────────────────────────────────────

def _build_keywords(context: dict) -> list:
    """LLM call ①: construct 3-5 search keywords from project context."""
    from core.scheduler.llm_client import call_llm, parse_json_from_response

    system_prompt = (
        "你是一个情报采集关键词构造器。根据给定的项目信息，构造 3-5 个精准的搜索关键词。\n"
        "要求：\n"
        "- 关键词应该能搜到与项目目标相关的最新情报\n"
        "- 结合 target_name + scope + indicators 的语义\n"
        "- 关键词应该是搜索友好的短语（不要长句子）\n"
        '- 输出纯 JSON 数组，如 ["关键词1", "关键词2", ...]\n'
        "- 不要输出其他文字"
    )

    user_prompt = (
        f"项目信息：\n"
        f"- 目标名称: {context.get('target_name', '')}\n"
        f"- 采集范围: {context.get('scope', '')}\n"
        f"- 采集指令: {context.get('instruction', '')}\n"
        f"- 数据源指标: {', '.join(context.get('indicators', []))}\n"
        f"- 目标类型: {context.get('target_type', '')}\n\n"
        f"请构造 3-5 个搜索关键词。"
    )

    result = call_llm(system_prompt, user_prompt, temperature=0.3, max_tokens=500, timeout=30)
    if not result.get("ok"):
        logger.warning(f"[search_cycle] LLM keyword build failed: {result.get('error', '')}")
        return []

    parsed, ok = parse_json_from_response(result["raw"])
    if ok and isinstance(parsed, list):
        return [str(k).strip() for k in parsed if str(k).strip()][:5]

    # Fallback: extract JSON array from raw
    m = re.search(r"\[([^\]]+)\]", result["raw"], re.DOTALL)
    if m:
        try:
            items = json.loads("[" + m.group(1) + "]")
            return [str(k).strip() for k in items if str(k).strip()][:5]
        except Exception:
            pass
    return []


def _judge_and_extract(content: str, context: dict, max_chars: int = 400) -> dict:
    """LLM call ②: judge relevance + extract summary.

    Returns: {relevant: bool, title: str, category: str, summary: str}
    """
    from core.scheduler.llm_client import call_llm, parse_json_from_response

    system_prompt = (
        "你是一个情报价值判断器。根据给定的项目信息和文章内容，判断该文章是否与项目相关，"
        "若相关则提炼摘要。\n"
        "输出纯 JSON 对象：\n"
        '{"relevant": true/false, "title": "文章标题(简短)", "category": "分类", '
        '"summary": "摘要正文"}\n'
        "若文章与项目无关，relevant=false，其余字段为空字符串。\n"
        "不要输出 JSON 以外的任何文字。\n\n"
        "summary 格式要求（严格遵守）：\n"
        f"- 总长度不超过 {max_chars} 字\n"
        "- 段落分明：按信息层次分段，段与段之间用换行分隔\n"
        "- 每段首行缩进两格（用两个全角空格　　开头）\n"
        "- 关键数据/名称可用 **加粗** 标注\n"
        "- 纯 markdown，不要 HTML 标签\n"
        "- 示例：\n"
        "　　**工信部**发布《工业互联网创新发展实施意见》，核心产业规模超**1.6万亿元**。\n"
        "\n　　意见重点部署三方面：一是增强标识纽带作用，推动国家顶级节点扩容升级；"
        "二是深化平台中枢功能，梯度培育综合型平台；三是健全安全保障制度体系。\n"
    )

    content_truncated = content[:3000]

    user_prompt = (
        f"项目目标: {context.get('target_name', '')}\n"
        f"采集范围: {context.get('scope', '')}\n"
        f"目标类型: {context.get('target_type', '')}\n\n"
        f"文章内容（截断）:\n{content_truncated}"
    )

    result = call_llm(system_prompt, user_prompt, temperature=0.1, max_tokens=600, timeout=30)
    if not result.get("ok"):
        return {"relevant": False, "title": "", "category": "", "summary": ""}

    parsed, ok = parse_json_from_response(result["raw"])
    if ok and isinstance(parsed, dict):
        summary = str(parsed.get("summary", ""))[:max_chars * 2]
        # 防御性清理：模型可能输出字面 "\n" 文本（反斜杠+n）或多余空行
        summary = summary.replace("\\n", "\n")
        summary = re.sub(r"\n{3,}", "\n\n", summary).strip()
        return {
            "relevant": bool(parsed.get("relevant", False)),
            "title": str(parsed.get("title", ""))[:200],
            "category": str(parsed.get("category", ""))[:50],
            "summary": summary,
        }
    return {"relevant": False, "title": "", "category": "", "summary": ""}


# ── Search & Read ───────────────────────────────────────────

def _tavily_search(query: str, max_results: int = 5) -> list:
    """Search via Tavily API. Returns [{title, url, content}]."""
    from config import get_tavily_config
    cfg = get_tavily_config()
    api_key = cfg.get("api_key", "")
    if not api_key:
        logger.warning("[search_cycle] Tavily key not configured, skipping search")
        return []

    try:
        resp = requests.post(
            cfg.get("base_url", "https://api.tavily.com").rstrip("/") + "/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.warning(f"[search_cycle] Tavily search failed for '{query[:40]}': {e}")
        return []


def _read_content(url: str) -> str:
    """Read article content. Handles mp.weixin.qq.com and general web."""
    if "mp.weixin.qq.com" in url:
        return _read_wechat_article(url)
    return _read_web(url)


def _read_wechat_article(url: str) -> str:
    """Read WeChat article body (same logic as mcp_server/wechat.py, inlined
    for use inside domain containers that don't have mcp_server/)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return ""
        text = resp.text
        if "请输入验证码" in text or "环境异常" in text:
            return ""
        soup = BeautifulSoup(text, "lxml")
        content_el = soup.select_one("#js_content")
        if content_el:
            return content_el.get_text(strip=True)
        return ""
    except Exception as e:
        logger.warning(f"[search_cycle] wechat read failed: {e}")
        return ""


def _read_web(url: str) -> str:
    """Read general web article content."""
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": _UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove nav/script/style
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        article = (
            soup.select_one("article")
            or soup.select_one("main")
            or soup.select_one("[role='main']")
            or soup.body
        )
        if article:
            return article.get_text(strip=True)[:3000]
        return ""
    except Exception as e:
        logger.warning(f"[search_cycle] web read failed for {url[:80]}: {e}")
        return ""


# ── Main cycle ──────────────────────────────────────────────

def run_search_cycle(trigger_type='scheduled', project_ids=None) -> dict:
    """Execute one search cycle for the current domain.

    Called by the hourly tick (only for projects whose frequency is due,
    passed via ``project_ids``), the legacy cron trigger, or manually via API.
    Records a search_run history row (start/end, result, produced intel) and
    returns a summary dict (includes ``run_id``).

    Projects that enter the run get ``last_search_at`` updated (even when they
    produce zero new items) so the next tick judges "due" from this run.
    """
    from core.db import (
        get_db_path, create_intelligence,
        get_intelligence_by_project, update_intelligence_status,
        record_search_run_start, record_search_run_end,
        finalize_stale_search_runs,
    )
    from core.project import get_projects, touch_project_last_search

    cfg = _get_config()
    if not cfg.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}

    # Determine DB path for this container's domain
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_slug = os.environ.get("ANALYZER_DB_SLUG", "intelligence")
    db_path = get_db_path(project_root, db_slug)

    max_per_domain = int(cfg.get("max_per_domain", 20))
    max_keywords = int(cfg.get("max_keywords_per_project", 5))
    max_llm_calls = int(cfg.get("max_llm_calls_per_cycle", 50))
    results_per_kw = int(cfg.get("results_per_keyword", 5))
    content_max = int(cfg.get("content_max_chars", 400))

    # 本轮使用的 LLM 模型名（config/llm.json），写入调度履历便于追溯
    from config import get_llm_config
    try:
        model_name = get_llm_config().get("model_name", "") or ""
    except Exception:
        model_name = ""

    t0 = time.time()

    # 清理历史遗留的"卡死在 running"记录（上轮进程被杀/容器重启导致）
    # 阈值 10 分钟：正常一轮 ≤ ~170s，超过即视为中断
    try:
        finalize_stale_search_runs(db_path, max_age_sec=600)
    except Exception as e:
        logger.warning(f"[search_cycle] stale-run cleanup failed: {e}")

    run_id = None
    try:
        run_id = record_search_run_start(db_path, db_slug, trigger_type)
    except Exception as e:
        logger.warning(f"[search_cycle] failed to record run start: {e}")

    # 结果累加器（try/finally 保证运行记录一定被 finalize，不会卡在 running）
    acc = {
        "status": "success",
        "projects_processed": 0,
        "new_intel": 0,
        "llm_calls": 0,
        "intel_items": [],
        "error_msg": "",
    }
    try:
        projects = get_projects(db_path, {"status": "active"})
        if project_ids is not None:
            idset = set(project_ids)
            projects = [p for p in projects if p["id"] in idset]
        if not projects:
            return {
                "domain": db_slug, "projects_processed": 0, "new_intel": 0,
                "llm_calls": 0, "run_id": run_id,
                "project_summaries": [], "intel": [],
            }

        llm_calls = 0
        total_new = 0
        project_summaries = []
        intel_items = []  # 本轮产出的情报（用于调度履历）：{title, url, intel_id, project}

        for project in projects:
            if total_new >= max_per_domain:
                break

            pid = project["id"]
            target_name = project.get("target_name", "")
            scope = project.get("scope", "")
            instruction = project.get("instruction", "")
            target_type = project.get("target_type", "")

            # 进入即记时：本次 run 对该项目的采集"已发生"，下轮到期判定以此为基准
            # （即使本轮没采到新情报，也不该在下一个 tick 重复触发）
            try:
                touch_project_last_search(db_path, pid)
            except Exception as e:
                logger.warning(f"[search_cycle] touch last_search_at failed for project {pid}: {e}")

            # Collect indicators from datasources
            datasources = project.get("datasources", [])
            indicators = []
            for ds in datasources:
                ind_raw = ds.get("indicators", "") or ""
                indicators.extend([i.strip() for i in ind_raw.split(",") if i.strip()])

            if not target_name:
                continue

            # Recent intel for dedup
            recent = get_intelligence_by_project(db_path, pid, limit=20)
            recent_titles = {r.get("title", "").lower() for r in recent}

            # ── LLM ①: build keywords ──
            if llm_calls >= max_llm_calls:
                break
            llm_calls += 1
            context = {
                "target_name": target_name,
                "scope": scope,
                "instruction": instruction,
                "indicators": indicators,
                "target_type": target_type,
            }
            keywords = _build_keywords(context)
            keywords = keywords[:max_keywords]
            if not keywords:
                continue

            project_new = 0
            seen_urls = set()

            for kw in keywords:
                if total_new + project_new >= max_per_domain or llm_calls >= max_llm_calls:
                    break

                results = _tavily_search(kw, max_results=results_per_kw)

                for r in results:
                    if total_new + project_new >= max_per_domain or llm_calls >= max_llm_calls:
                        break
                    url = (r.get("url") or "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # 内容获取：优先用 Tavily snippet（快），公众号才做全文抓取
                    content = (r.get("content") or "").strip()
                    if "mp.weixin.qq.com" in url:
                        # 公众号需要完整正文
                        full = _read_content(url)
                        if full:
                            content = full
                    if not content or len(content) < 50:
                        continue

                    # ── LLM ②: judge + extract ──
                    llm_calls += 1
                    judged = _judge_and_extract(content, context, max_chars=content_max)
                    if not judged.get("relevant"):
                        continue

                    title = judged.get("title", "").strip()
                    if not title:
                        continue
                    if title.lower() in recent_titles:
                        continue

                    # Create intelligence
                    category = judged.get("category") or target_type or "market"
                    summary = (judged.get("summary") or "").strip()
                    # 附来源（markdown 引用行），来源清晰；链接文本优先用搜索结果原标题
                    if summary and url:
                        link_text = (r.get("title") or "").strip() or url
                        content_final = summary + f"\n\n> 来源：[{link_text}]({url})"
                    else:
                        content_final = summary
                    intel_id = create_intelligence(
                        db_path,
                        title=title,
                        content=content_final,
                        category=category,
                        contact_name="",
                        metadata={"source_url": url},
                        project_id=pid,
                    )
                    if intel_id:
                        recent_titles.add(title.lower())
                        update_intelligence_status(db_path, intel_id, "done")
                        project_new += 1
                        total_new += 1
                        intel_items.append({
                            "title": title,
                            "url": url,
                            "intel_id": intel_id,
                            "project": project.get("name", ""),
                        })

            project_summaries.append({
                "project_id": pid,
                "project_name": project.get("name", ""),
                "target_name": target_name,
                "new_intel": project_new,
            })

        logger.info(
            f"[search_cycle] domain={db_slug} projects={len(project_summaries)} "
            f"new_intel={total_new} llm_calls={llm_calls}"
        )
        acc.update({
            "status": "success",
            "projects_processed": len(project_summaries),
            "new_intel": total_new,
            "llm_calls": llm_calls,
            "intel_items": intel_items,
        })
        return {
            "domain": db_slug,
            "projects_processed": len(project_summaries),
            "new_intel": total_new,
            "llm_calls": llm_calls,
            "run_id": run_id,
            "intel": intel_items,
            "project_summaries": project_summaries,
        }
    except Exception as e:
        logger.exception(f"[search_cycle] cycle failed: {e}")
        acc["status"] = "failed"
        acc["error_msg"] = f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        if run_id:
            try:
                record_search_run_end(
                    db_path, run_id, acc["status"],
                    projects_processed=acc["projects_processed"],
                    new_intel=acc["new_intel"],
                    llm_calls=acc["llm_calls"],
                    intel_items=acc["intel_items"],
                    duration_sec=int(time.time() - t0),
                    error_msg=acc["error_msg"],
                    model_name=model_name,
                )
            except Exception as e:
                logger.warning(f"[search_cycle] failed to record run end: {e}")


# ── Manual trigger ──────────────────────────────────────────

def trigger_search_once() -> dict:
    """Synchronously run one search cycle (used by the scheduler / tests)."""
    return run_search_cycle(trigger_type='manual')


def trigger_search_async() -> dict:
    """Start one manual search cycle in a background thread, return immediately.

    A full cycle can exceed gunicorn's worker timeout (~120s), so the manual
    API trigger must not block the request. The cycle runs in a daemon thread;
    its result is recorded in the search_run history (visible via
    /api/system/search/runs).
    """
    import threading

    def _worker():
        try:
            result = run_search_cycle(trigger_type='manual')
            logger.info(f"[search_cycle] manual run done: {result}")
        except Exception as e:
            logger.exception(f"[search_cycle] manual run failed: {e}")

    threading.Thread(target=_worker, daemon=True).start()
    return {"ok": True, "started": True}


# ── 频率感知调度（方案B：单一 tick + 每项目到期判定） ──────────

def _due_project_ids(db_path) -> list:
    """查询本域 active 项目中已到期的项目 id。

    到期 = last_search_at 为空（存量项目首次调度）或距上次采集
    >= 该频率的间隔（hourly=1h / daily=24h / weekly=168h / monthly=720h）。
    oneshot 无自动调度（_FREQ_HOURS 里查不到 → 永不到期）。
    """
    now = datetime.now()
    ids = []
    from core.db import get_db
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, frequency, last_search_at FROM projects WHERE status = 'active'"
        ).fetchall()
    for r in rows:
        freq = r["frequency"]
        hours = _FREQ_HOURS.get(freq)
        if hours is None:
            continue  # oneshot / 未知频率：不参与自动调度
        last = r["last_search_at"]
        if not last:
            ids.append(r["id"])  # 存量项目：首次到期，立即采集
            continue
        try:
            last_dt = datetime.fromisoformat(last)
        except ValueError:
            ids.append(r["id"])  # 时间戳损坏：视为到期，下一轮会修复
            continue
        if (now - last_dt) >= timedelta(hours=hours):
            ids.append(r["id"])
    return ids


def run_search_tick(trigger_type='tick') -> dict:
    """每小时心跳：检查本域项目的采集频率，只跑"到期"的项目。

    无到期项目时零成本直接返回（不调 LLM、不写 search_run）。
    有到期项目时复用 run_search_cycle（project_ids 子集），
    调度履历里能看到每轮实际采集了哪些项目。
    """
    from core.db import get_db_path
    from core.project import get_projects

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_slug = os.environ.get("ANALYZER_DB_SLUG", "intelligence")
    db_path = get_db_path(project_root, db_slug)

    cfg = _get_config()
    if not cfg.get("enabled", True):
        return {"domain": db_slug, "due": [], "skipped": True, "reason": "disabled"}

    due = _due_project_ids(db_path)
    if not due:
        # 轻量计数（仅用于日志，不写库）
        n_active = len(get_projects(db_path, {"status": "active"}))
        logger.info(f"[search_tick] domain={db_slug} due=0/{n_active} active, nothing to do")
        return {"domain": db_slug, "due": [], "skipped": True, "reason": "none_due"}

    result = run_search_cycle(trigger_type=trigger_type, project_ids=due)
    result["due"] = due
    return result
