"""微信公众号「搜」+「读」核心工具。

供情报社 MCP 暴露给 Agent 调用：
- search_wechat_articles(account, keyword, ...)  搜：按公众号名 + 关键词，
  通过 Tavily 搜索 site:mp.weixin.qq.com 直链，返回候选文章列表。
- read_wechat_article(url)                        读：直读单篇 mp.weixin.qq.com
  文章，返回标题 / 公众号名 / 发布时间 / 正文。

设计原则：
- 轻量增量，不做全量抓取，配合 Agent「每天 2 次 x 3-4 条」的节奏。
- 搜用 Tavily（覆盖公众号直链最稳的现成路径），读用 httpx/requests 直读
  mp.weixin.qq.com（无需登录、无需 cookie）。
- 反爬/限速：读请求间留最小间隔，检测到验证码/环境异常直接报错。
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

_REQUEST_TIMEOUT = 20
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 读请求最小间隔（秒），避免被当成高频爬虫
_MIN_READ_INTERVAL_S = float(os.environ.get("WECHAT_READ_INTERVAL_S", "1.0"))
_last_read_ts = 0.0

_PUBLISH_TS_RE = re.compile(r"var\s+ct\s*=\s*[\"'](\d+)[\"']")
_MP_HOST = "mp.weixin.qq.com"


def _get_tavily_key():
    """Tavily API key：唯一来源 = 系统设置（config/tavily.json）。

    未配置时返回空字符串，由调用方明确报错（不设 key 就不能搜索）。
    """
    try:
        from config import get_tavily_config
        return (get_tavily_config().get("api_key") or "").strip()
    except Exception:
        return ""


def _get_tavily_base_url():
    """Tavily base URL：系统配置优先，默认 https://api.tavily.com。"""
    try:
        from config import get_tavily_config
        base = (get_tavily_config().get("base_url") or "").strip()
        if base:
            return base.rstrip("/")
    except Exception:
        pass
    return "https://api.tavily.com"


def _throttle():
    """读请求限速：保证相邻请求间隔 >= _MIN_READ_INTERVAL_S。"""
    global _last_read_ts
    elapsed = time.monotonic() - _last_read_ts
    if elapsed < _MIN_READ_INTERVAL_S:
        time.sleep(_MIN_READ_INTERVAL_S - elapsed)
    _last_read_ts = time.monotonic()


def search_wechat_articles(
    account: str,
    keyword: str = "",
    max_results: int = 10,
) -> list:
    """在微信公众号内搜索文章，返回候选 mp 直链列表。

    Args:
        account: 公众号名称（必填，用于限定搜索范围，如"迅越印刷ERP"）。
        keyword: 可选主题关键词，进一步过滤该号内的情报项（如"MES 追溯"）。
        max_results: 最多返回条数。

    Returns:
        list[dict]: 每条含 title / url / snippet / source / published_date。
        仅保留 mp.weixin.qq.com 直链。
    """
    api_key = _get_tavily_key()
    if not api_key:
        return [{"error": "Tavily API Key 未配置（系统设置 → Tavily 搜索），无法搜索"}]

    # 构造搜索词：公众号名 + 关键词 + site 限定
    account_q = f'"{account}"' if account else ""
    keyword_q = keyword.strip()
    query = f"{account_q} {keyword_q} site:mp.weixin.qq.com".strip()
    if not query or query == "site:mp.weixin.qq.com":
        return [{"error": "需要提供公众号名或关键词"}]

    try:
        resp = requests.post(
            _get_tavily_base_url() + "/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max(5, max_results),
                "search_depth": "advanced",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"error": f"Tavily 搜索失败: {type(e).__name__}: {e}"}]

    results = []
    for item in data.get("results", []):
        url = (item.get("url") or "").strip()
        if _MP_HOST not in url:
            continue
        raw_title = (item.get("title") or "").strip()
        # Tavily 对 mp 文章常把 title 填成 URL 或留空，回退处理
        title = "" if (not raw_title or raw_title.startswith("http")) else raw_title
        results.append({
            "title": title,
            "url": url,
            "snippet": (item.get("content") or "").strip(),
            "source": account,
            "published_date": (item.get("published_date") or "").strip(),
        })
        if len(results) >= max_results:
            break

    if not results:
        return [{
            "error": "未搜到该公众号的 mp.weixin.qq.com 直链",
            "hint": "公众号名可能不精确，或该号内容未被搜索引擎收录。可换关键词或放宽 account 再试。",
        }]
    return results


def read_wechat_article(url: str) -> dict:
    """读取单篇微信公众号文章正文。

    Args:
        url: mp.weixin.qq.com 文章直链。

    Returns:
        dict: title / account / published_date / content / url。
        失败返回 {error: ...}。
    """
    if not url or _MP_HOST not in url:
        return {"error": "不是有效的 mp.weixin.qq.com 文章链接"}

    _throttle()
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": _UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=_REQUEST_TIMEOUT,
        )
    except Exception as e:
        return {"error": f"网络请求失败: {type(e).__name__}: {e}"}

    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}"}

    text = resp.text
    # 反爬/验证码检测
    if "请输入验证码" in text or "环境异常" in text:
        return {"error": "触发微信反爬验证（请输入验证码/环境异常），请稍后重试"}

    soup = BeautifulSoup(text, "lxml")

    title_el = soup.select_one("#activity-name")
    account_el = soup.select_one("#js_name")
    content_el = soup.select_one("#js_content")

    title = title_el.get_text(strip=True) if title_el else ""
    account = account_el.get_text(strip=True) if account_el else ""
    content = content_el.get_text(strip=True) if content_el else ""

    # 发布时间：mp 页面内联 JS 的 var ct = "<unix>"（可能是字符串或数字）
    published = ""
    m = _PUBLISH_TS_RE.search(text)
    if m:
        try:
            published = time.strftime(
                "%Y-%m-%d", time.localtime(int(m.group(1)))
            )
        except Exception:
            published = ""
    # 兜底：部分文章 ct 缺失，用 <meta property="article:published_time">
    if not published:
        meta = soup.select_one('meta[property="article:published_time"]')
        if meta and meta.get("content"):
            published = meta["content"][:10]

    if not content:
        return {"error": "正文为空，文章可能已删除或需要验证", "url": url}

    return {
        "title": title,
        "account": account,
        "published_date": published,
        "content": content,
        "url": url,
    }
