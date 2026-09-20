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
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

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

# 采集频率 → 时效窗口（天）：让"新旧"由搜索 API 硬约束。
# 高频项目看得更近，低频项目允许更宽的窗口；oneshot/未知频率用 config 的 recency_days 兜底。
_FREQ_RECENCY_DAYS = {
    'hourly': 1,     # day
    'daily': 7,      # week
    'weekly': 30,    # month
    'monthly': 365,  # year
}

# 时效窗口（天）→ Tavily time_range（精确档位）；其余天数走 start_date/end_date。
_TAVILY_TIME_RANGE = {1: 'day', 7: 'week', 30: 'month', 365: 'year'}

# 公众号内联 JS 的发布时间戳：var ct = "169..."（与 mcp_server/wechat.py 一致）
_PUBLISH_TS_RE = re.compile(r'var\s+ct\s*=\s*["\'](\d+)["\']')

# 受控分类词表（closed vocabulary）：LLM 只能从这里选，杜绝分类膨胀。
# 单一事实来源在 core/db.py；这里 re-export 供提示词与入库校验使用。
from core.db import CATEGORIES, OTHER_CATEGORY, normalize_category as _normalize_category


# ── Config ──────────────────────────────────────────────────

def _get_config() -> dict:
    from config import get_search_config
    return get_search_config()


def _recency_window_days(frequency: str, cfg: dict) -> int:
    """项目采集频率 → 时效窗口（天）。

    hourly→1 / daily→7 / weekly→30 / monthly→365；oneshot 及未知频率
    回落到 config/search.json 的 recency_days（默认 30）。
    """
    mapped = _FREQ_RECENCY_DAYS.get(frequency)
    if mapped is not None:
        return mapped
    try:
        return max(1, int(cfg.get('recency_days', 30)))
    except (TypeError, ValueError):
        return 30


# ── 日期解析（时效判断用，统一输出 YYYY-MM-DD） ─────────────

def _parse_date_str(s) -> str:
    """把各种形态的日期字符串归一为 YYYY-MM-DD；解析失败返回 ''。

    支持：ISO（2026-09-01 / 2026-09-01T08:00:00Z / 2026-09-01 08:00:00）、
    斜杠日期（2026/9/1）、RFC 822/HTTP 日期（feed 的 pubDate）、unix 秒时间戳。
    """
    if not s:
        return ''
    s = str(s).strip()
    if not s:
        return ''

    # ISO / 斜杠 / 点 / 空格 / 中文年月日：取第一段 YYYY-MM-DD
    m = re.search(r'(\d{4})\s*[年./\-]\s*(\d{1,2})\s*[月./\-]\s*(\d{1,2})\s*日?', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y >= 1990:
            try:
                return datetime(y, mo, d).strftime('%Y-%m-%d')
            except ValueError:
                pass

    # unix 秒时间戳（9~11 位）
    if re.fullmatch(r'\d{9,11}', s):
        try:
            ts = int(s)
            if 946684800 < ts < 4102444800:  # 2000-01-01 .. 2099-...
                return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        except (ValueError, OverflowError, OSError):
            pass

    # RFC 822 / HTTP 日期（RSS pubDate 等）
    try:
        dt = parsedate_to_datetime(s)
        if dt is not None and dt.year >= 1990:
            return dt.strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        pass
    return ''


_DATE_META_SELECTORS = (
    'meta[property="article:published_time"]',
    'meta[property="og:article:published_time"]',
    'meta[itemprop="datePublished"]',
    'meta[name="pubdate"]',
    'meta[name="publishdate"]',
    'meta[name="publish-date"]',
    'meta[name="weibo:article:create_at"]',
    'meta[name="date"]',
)


def _extract_published_date(html: str) -> str:
    """从通用网页 HTML 提取发布时间（YYYY-MM-DD），取不到返回 ''。

    顺序：meta 标签 → <time datetime> → JSON-LD datePublished/dateModified。
    """
    if not html:
        return ''
    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        return ''

    for sel in _DATE_META_SELECTORS:
        el = soup.select_one(sel)
        if el is not None:
            d = _parse_date_str(el.get('content') or el.get('datetime') or '')
            if d:
                return d

    el = soup.select_one('time[datetime]')
    if el is not None:
        d = _parse_date_str(el.get('datetime', ''))
        if d:
            return d

    for s in soup.select('script[type="application/ld+json"]'):
        raw = s.string or s.get_text() or ''
        d = _jsonld_date(raw)
        if d:
            return d
    return ''


def _jsonld_date(raw: str) -> str:
    """从 JSON-LD 文本里找 datePublished（优先）/ dateModified，归一为 YYYY-MM-DD。"""
    if not raw:
        return ''
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ''
    found = []

    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ('datePublished', 'dateModified') and isinstance(v, str):
                    d = _parse_date_str(v)
                    if d:
                        found.append(d)
                else:
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(data)
    if found:
        return sorted(found)[0]  # 多条取最早（发布时间语义）
    return ''


def _is_stale(published_date: str, window_days: int, now: datetime = None) -> bool:
    """已知发布日期且早于时效窗口 → 视为旧情报（True）。日期未知 → False（不拦）。"""
    if not published_date or not window_days:
        return False
    now = now or datetime.now()
    try:
        pub = datetime.strptime(published_date[:10], '%Y-%m-%d')
    except ValueError:
        return False
    if pub > now:
        return False  # 未来时间（时钟漂移/脏数据）不拦
    return (now - pub).days > window_days


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


def _judge_and_extract(content: str, context: dict, max_chars: int = 400,
                       published_date: str = "", recency_days: int = 0) -> dict:
    """LLM call ②: judge relevance + extract summary.

    Returns: {relevant: bool, title: str, category: str, summary: str}

    时效敏感：提示词注入"当前日期 + 文章发布日期"；超过 recency_days 天或
    常青/背景类旧文 → relevant=false。
    """
    from core.scheduler.llm_client import call_llm, parse_json_from_response

    now_str = datetime.now().strftime('%Y-%m-%d')

    system_prompt = (
        "你是一个情报价值判断器。根据给定的项目信息和文章内容，判断该文章是否与项目相关，"
        "若相关则提炼摘要。\n"
        "输出纯 JSON 对象：\n"
        '{"relevant": true/false, "title": "文章标题(简短)", "category": "分类", '
        '"summary": "摘要正文"}\n'
        f"category 必须且只能从以下列表中选择一项（不要自创新分类）：{CATEGORIES}\n"
        "选择依据：政策/法规/标准类→政策法规；新技术/专利/研发→技术进展；"
        "市场/价格/供应链→市场动态；竞争对手的产品或动作→竞品动态；"
        "客户/经销商/供应商→客户动态；财报/人事/投融资/并购→企业公告；"
        "一般行业新闻→行业动态；都不符合→其他。\n"
        "若文章与项目无关，relevant=false，其余字段为空字符串。\n"
    )

    if recency_days and recency_days > 0:
        system_prompt += (
            f"时效性要求（严格遵守）：当前日期为 {now_str}。"
            f"若文章发布日期早于当前日期 {recency_days} 天以上，"
            "或属于常青/背景/科普/盘点类旧文（与项目目标相关但不含新动态、新数据、新事件），"
            "则判 relevant=false。只保留时效内、有增量信息的内容。\n"
        )

    system_prompt += (
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
        f"目标类型: {context.get('target_type', '')}\n"
        f"当前日期: {now_str}\n"
        f"文章发布日期: {published_date or '未知'}\n\n"
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

def _tavily_search(query: str, max_results: int = 5, recency_days: int = 0) -> list:
    """Search via Tavily API. Returns [{title, url, content, published_date}].

    recency_days > 0 时按时效窗口硬过滤：
    1/7/30/365 天 → Tavily time_range（day/week/month/year），
    其余天数 → start_date/end_date。
    """
    from config import get_tavily_config
    cfg = get_tavily_config()
    api_key = cfg.get("api_key", "")
    if not api_key:
        logger.warning("[search_cycle] Tavily key not configured, skipping search")
        return []

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }
    if recency_days and recency_days > 0:
        tr = _TAVILY_TIME_RANGE.get(recency_days)
        if tr:
            payload["time_range"] = tr
        else:
            payload["start_date"] = (datetime.now() - timedelta(days=recency_days)).strftime('%Y-%m-%d')
            payload["end_date"] = datetime.now().strftime('%Y-%m-%d')

    try:
        resp = requests.post(
            cfg.get("base_url", "https://api.tavily.com").rstrip("/") + "/search",
            json=payload,
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "published_date": _parse_date_str(r.get("published_date") or ""),
            }
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.warning(f"[search_cycle] Tavily search failed for '{query[:40]}': {e}")
        return []


def _read_content(url: str) -> dict:
    """Read article. Handles mp.weixin.qq.com and general web.

    Returns: {"content": str, "published_date": str(YYYY-MM-DD 或 '')}
    """
    if "mp.weixin.qq.com" in url:
        return _read_wechat_article(url)
    return _read_web(url)


def _read_wechat_article(url: str) -> dict:
    """Read WeChat article body (same logic as mcp_server/wechat.py, inlined
    for use inside domain containers that don't have mcp_server/)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return {"content": "", "published_date": ""}
        text = resp.text
        if "请输入验证码" in text or "环境异常" in text:
            return {"content": "", "published_date": ""}
        soup = BeautifulSoup(text, "lxml")
        content_el = soup.select_one("#js_content")
        content = content_el.get_text(strip=True) if content_el else ""

        # 发布时间：内联 JS 的 var ct = "<unix>"，兜底 meta article:published_time
        published = ""
        m = _PUBLISH_TS_RE.search(text)
        if m:
            try:
                published = datetime.fromtimestamp(int(m.group(1))).strftime('%Y-%m-%d')
            except (ValueError, OverflowError, OSError):
                published = ""
        if not published:
            published = _extract_published_date(text)

        return {"content": content, "published_date": published}
    except Exception as e:
        logger.warning(f"[search_cycle] wechat read failed: {e}")
        return {"content": "", "published_date": ""}


def _read_web(url: str) -> dict:
    """Read general web article content + 提取发布时间。

    Returns: {"content": str, "published_date": str(YYYY-MM-DD 或 '')}
    """
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
            return {"content": "", "published_date": ""}
        published = _extract_published_date(resp.text)
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
        content = article.get_text(strip=True)[:3000] if article else ""
        return {"content": content, "published_date": published}
    except Exception as e:
        logger.warning(f"[search_cycle] web read failed for {url[:80]}: {e}")
        return {"content": "", "published_date": ""}


def _fetch_page_date(url: str, timeout: int = 10) -> str:
    """只抓页面提取发布时间（不取正文），供时效二次过滤用。失败返回 ''。"""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return ""
        return _extract_published_date(resp.text)
    except Exception as e:
        logger.debug(f"[search_cycle] date fetch failed for {url[:80]}: {e}")
        return ""


_MAX_DATE_FETCHES = 10  # 每项目每轮"抓页面取日期"的请求上限（控制轮次耗时）


def _fill_missing_dates(urls_dates: list, cfg: dict, budget: int = 0):
    """对缺少发布日期的 (url, date) 并发抓页面补日期。

    urls_dates: [(url, published_date), ...]
    返回 (dates, n_fetched)：同序日期列表（补不到的保持 ''）+ 实际发出的请求数。
    公众号 URL 跳过（后续全文抓取时解析 var ct=）。
    budget <= 0 表示不抓。
    """
    if not cfg.get('fetch_page_for_date', True) or budget <= 0:
        return [d for _, d in urls_dates], 0
    timeout = int(cfg.get('page_fetch_timeout', 10) or 10)
    workers = max(1, int(cfg.get('page_fetch_workers', 4) or 4))

    need = [
        i for i, (u, d) in enumerate(urls_dates)
        if u and not d and "mp.weixin.qq.com" not in u
    ]
    out = list(urls_dates)
    if not need:
        return [d for _, d in out], 0
    need = need[:min(len(need), budget)]

    def _work(i):
        return i, _fetch_page_date(out[i][0], timeout=timeout)

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for i, d in pool.map(_work, need):
                if d:
                    out[i] = (out[i][0], d)
    except Exception as e:
        logger.warning(f"[search_cycle] batch date fetch failed: {e}")
    return [d for _, d in out], len(need)


# ── Feed (RSS/Atom) 采集通道 ─────────────────────────────────

_FEED_TYPES = {'feed', 'rss', 'atom'}
_ATOM_NS = '{http://www.w3.org/2005/Atom}'
_DC_NS = '{http://purl.org/dc/elements/1.1/}'


def _is_feed_source(ds: dict) -> bool:
    """数据源是否为 feed：type 显式标记，或 URL 路径像 feed 地址。"""
    if (ds.get('type') or '').lower() in _FEED_TYPES:
        return True
    url = (ds.get('url') or '').split('?')[0].split('#')[0].lower()
    path = url.rstrip('/').rsplit('/', 1)[-1] if url else ''
    return path in ('feed', 'rss', 'atom', 'feed.xml', 'rss.xml', 'atom.xml') \
        or path.endswith(('.rss', '.xml')) and ('feed' in path or 'rss' in path)


def _strip_html(s: str) -> str:
    """去掉 HTML 标签（feed 的 description 常带标签/CDATA 残留）。"""
    if not s:
        return ''
    try:
        return BeautifulSoup(s, 'lxml').get_text(strip=True)
    except Exception:
        return re.sub(r'<[^>]+>', '', s).strip()


def _fetch_feed(url: str, timeout: int = 15, max_items: int = 20) -> list:
    """抓取 RSS/Atom feed，返回 [{title, url, content, published_date}]。

    新在前（feed 天然属性）；解析失败/非 200 返回 []。
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.info(f"[search_cycle] feed HTTP {resp.status_code}: {url[:80]}")
            return []
        root = ET.fromstring(resp.content)
    except Exception as e:
        logger.warning(f"[search_cycle] feed fetch/parse failed for {url[:80]}: {e}")
        return []

    items = []
    # RSS 2.0 / RDF
    for it in root.iter('item'):
        title = (it.findtext('title') or '').strip()
        link = (it.findtext('link') or '').strip()
        desc = (it.findtext('description') or '').strip()
        pub = (it.findtext('pubDate') or it.findtext(_DC_NS + 'date') or '').strip()
        items.append({
            'title': title,
            'url': link,
            'content': _strip_html(desc),
            'published_date': _parse_date_str(pub),
        })
        if len(items) >= max_items:
            break

    # Atom
    if not items:
        for it in root.iter(_ATOM_NS + 'entry'):
            title = (it.findtext(_ATOM_NS + 'title') or '').strip()
            link = ''
            for link_el in it.findall(_ATOM_NS + 'link'):
                rel = link_el.get('rel', 'alternate')
                if rel == 'alternate' or not link:
                    link = link_el.get('href', '')
            desc = (it.findtext(_ATOM_NS + 'summary') or it.findtext(_ATOM_NS + 'content') or '').strip()
            pub = (it.findtext(_ATOM_NS + 'published') or it.findtext(_ATOM_NS + 'updated') or '').strip()
            items.append({
                'title': title,
                'url': (link or '').strip(),
                'content': _strip_html(desc),
                'published_date': _parse_date_str(pub),
            })
            if len(items) >= max_items:
                break

    # feed 新在前：按发布日期倒序（无日期的排最后）
    items.sort(key=lambda x: x['published_date'] or '0000', reverse=True)
    return items[:max_items]


# ── 单条候选处理（feed 条目与搜索结果共用） ───────────────────

def _process_candidate(cand: dict, context: dict, window_days: int, state: dict) -> bool:
    """处理单条候选：URL 去重 → 正文长度 → 时效过滤 → LLM② → 标题去重 → 入库。

    cand: {title, url, content, published_date}
    state: 本轮/本项目共享的可变状态（llm_calls / total_new / project_new /
           seen_urls / recent_titles / intel_items 等）。
    返回 True 表示产生了新情报。
    """
    from core.db import create_intelligence, update_intelligence_status

    url = (cand.get("url") or "").strip()
    if not url or url in state["seen_urls"]:
        return False
    state["seen_urls"].add(url)

    content = (cand.get("content") or "").strip()
    if not content or len(content) < 50:
        return False

    # 时效二次过滤：已知发布日期且早于项目窗口 → 直接丢弃
    if _is_stale(cand.get("published_date", ""), window_days):
        state["stale_skips"] += 1
        logger.info(
            f"[search_cycle] stale item dropped (published {cand.get('published_date')}, "
            f"window {window_days}d): {url[:80]}"
        )
        return False

    # ── LLM ②: 判相关 + 提炼摘要（时效敏感） ──
    state["llm_calls"] += 1
    judged = _judge_and_extract(
        content, context, max_chars=state["content_max"],
        published_date=cand.get("published_date", ""),
        recency_days=window_days,
    )
    if not judged.get("relevant"):
        return False

    title = judged.get("title", "").strip()
    if not title:
        return False
    if title.lower() in state["recent_titles"]:
        return False

    # Create intelligence（分类强制归一到受控词表，防止词表外值再次进入）
    category = _normalize_category(
        judged.get("category") or state["target_type"] or "market"
    )
    summary = (judged.get("summary") or "").strip()
    # 附来源（markdown 引用行），来源清晰；链接文本优先用结果原标题
    if summary and url:
        link_text = (cand.get("title") or "").strip() or url
        content_final = summary + f"\n\n> 来源：[{link_text}]({url})"
    else:
        content_final = summary
    intel_id = create_intelligence(
        state["db_path"],
        title=title,
        content=content_final,
        category=category,
        contact_name="",
        metadata={"source_url": url},
        project_id=state["pid"],
        published_date=cand.get("published_date", ""),
    )
    if intel_id:
        state["recent_titles"].add(title.lower())
        update_intelligence_status(state["db_path"], intel_id, "done")
        state["project_new"] += 1
        state["total_new"] += 1
        state["intel_items"].append({
            "title": title,
            "url": url,
            "intel_id": intel_id,
            "project": state["project_name"],
        })
        return True
    return False


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
            # get_projects 只返回 datasource_count，需按项目单独查关联数据源
            # （否则 indicators 恒空、feed 通道永远发现不了 feed 源）
            datasources = project.get("datasources")
            if datasources is None:
                try:
                    from core.datasource import get_datasources_for_project
                    datasources = get_datasources_for_project(db_path, pid)
                except Exception as e:
                    logger.warning(f"[search_cycle] load datasources failed for project {pid}: {e}")
                    datasources = []
            indicators = []
            for ds in datasources:
                ind_raw = ds.get("indicators", "") or ""
                indicators.extend([i.strip() for i in ind_raw.split(",") if i.strip()])

            if not target_name:
                continue

            # 时效窗口：项目频率 → 天数（hourly=1 / daily=7 / weekly=30 / monthly=365，
            # oneshot 用 config recency_days 兜底）。"新旧"由此硬约束，不靠模型自觉。
            recency_days = _recency_window_days(project.get("frequency", ""), cfg)

            # Recent intel for dedup
            recent = get_intelligence_by_project(db_path, pid, limit=20)
            state = {
                "db_path": db_path,
                "pid": pid,
                "project_name": project.get("name", ""),
                "target_type": target_type,
                "content_max": content_max,
                "seen_urls": set(),
                "recent_titles": {r.get("title", "").lower() for r in recent},
                "intel_items": intel_items,
                "llm_calls": llm_calls,
                "total_new": total_new,
                "project_new": 0,
                "stale_skips": 0,
                "date_budget": _MAX_DATE_FETCHES,
            }

            context = {
                "target_name": target_name,
                "scope": scope,
                "instruction": instruction,
                "indicators": indicators,
                "target_type": target_type,
            }

            # ── 通道 A：feed（RSS/Atom 新在前、带 pubDate，天然规避旧内容） ──
            feed_sources = [
                ds for ds in datasources
                if ds.get("status") != "inactive" and _is_feed_source(ds)
            ]
            feed_worked = False
            if feed_sources:
                feed_max = int(cfg.get("feed_max_items", 20) or 20)
                feed_timeout = int(cfg.get("feed_timeout", 15) or 15)
                feed_items = []
                for ds in feed_sources:
                    items = _fetch_feed(ds.get("url") or "", timeout=feed_timeout, max_items=feed_max)
                    if items:
                        feed_worked = True
                        try:
                            from core.datasource import update_source_last_crawled
                            update_source_last_crawled(db_path, ds["id"])
                        except Exception as e:
                            logger.warning(f"[search_cycle] update last_crawled failed for {ds.get('name', '')}: {e}")
                        feed_items.extend(items)
                if feed_items:
                    logger.info(f"[search_cycle] project {pid}: feed 通道 {len(feed_items)} 条候选")
                    for item in feed_items:
                        if state["total_new"] + state["project_new"] >= max_per_domain or state["llm_calls"] >= max_llm_calls:
                            break
                        _process_candidate(item, context, recency_days, state)

            # 高频项目（hourly/daily）且 feed 通道可用 → 优先走 feed，跳过全网搜索
            prefer_feed = (
                project.get("frequency") in ("hourly", "daily")
                and feed_worked
                and bool(cfg.get("feed_prefer_high_freq", True))
            )
            if prefer_feed:
                logger.info(
                    f"[search_cycle] project {pid} 高频项目且 feed 可用 → 本轮仅走 feed 通道"
                )
                llm_calls, total_new = state["llm_calls"], state["total_new"]
                project_summaries.append({
                    "project_id": pid,
                    "project_name": project.get("name", ""),
                    "target_name": target_name,
                    "new_intel": state["project_new"],
                    "stale_skips": state["stale_skips"],
                })
                continue

            # ── 通道 B：开放式网页搜索（Tavily，带时间过滤） ──
            # ── LLM ①: build keywords ──
            if state["llm_calls"] >= max_llm_calls:
                break
            state["llm_calls"] += 1
            keywords = _build_keywords(context)
            keywords = keywords[:max_keywords]
            if not keywords:
                llm_calls, total_new = state["llm_calls"], state["total_new"]
                project_summaries.append({
                    "project_id": pid,
                    "project_name": project.get("name", ""),
                    "target_name": target_name,
                    "new_intel": state["project_new"],
                    "stale_skips": state["stale_skips"],
                })
                continue

            for kw in keywords:
                if state["total_new"] + state["project_new"] >= max_per_domain or state["llm_calls"] >= max_llm_calls:
                    break

                results = _tavily_search(kw, max_results=results_per_kw, recency_days=recency_days)
                if not results:
                    continue

                # 时效二次过滤的准备：批量补齐缺失的发布日期（并发抓页面，受限预算）
                if recency_days:
                    pairs = [
                        ((r.get("url") or "").strip(), r.get("published_date") or "")
                        for r in results
                    ]
                    dates, fetched = _fill_missing_dates(pairs, cfg, budget=state["date_budget"])
                    state["date_budget"] = max(0, state["date_budget"] - fetched)
                    for r, d in zip(results, dates):
                        if d:
                            r["published_date"] = d

                for r in results:
                    if state["total_new"] + state["project_new"] >= max_per_domain or state["llm_calls"] >= max_llm_calls:
                        break
                    url = (r.get("url") or "").strip()
                    if not url:
                        continue
                    cand = {
                        "title": r.get("title", ""),
                        "url": url,
                        "content": (r.get("content") or "").strip(),
                        "published_date": r.get("published_date", ""),
                    }
                    if "mp.weixin.qq.com" in url:
                        # 公众号需要完整正文 + 页面内发布时间（var ct=）
                        read = _read_content(url)
                        if read.get("content"):
                            cand["content"] = read["content"]
                        if read.get("published_date"):
                            cand["published_date"] = cand["published_date"] or read["published_date"]
                    _process_candidate(cand, context, recency_days, state)

            llm_calls, total_new = state["llm_calls"], state["total_new"]
            project_summaries.append({
                "project_id": pid,
                "project_name": project.get("name", ""),
                "target_name": target_name,
                "new_intel": state["project_new"],
                "stale_skips": state["stale_skips"],
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
