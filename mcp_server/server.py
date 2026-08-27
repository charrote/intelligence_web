#!/usr/bin/env python3
"""
Intelligence Platform MCP Server
提供情报管理、数据源管理、实体管理、通知订阅等工具的标准化 MCP 接口
支持 HTTP 传输 (Streamable HTTP)

=== 修复说明 (v1.0.1) ===
- 使用 server.run_streamable_http_async() 替代手动 Starlette 包装
- 使用 @server.custom_route() 替代 GatewayHandler 处理 /health 和 /
- 消除 /mcp 端点 500 错误（RuntimeError: Task group is not initialized）
"""

import os
import asyncio
import sys

# Ensure /app is in the Python path for module imports
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from config import get_mcp_config

# Database path (fixed to correct locations)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PROJECT_ROOT)
RESEARCH_DB = os.path.join(ROOT, "intelligence_web", "data", "intelligence")
SALES_DB = os.path.join(ROOT, "intelligence_sales", "data", "intelligence_sales")

def get_db(domain):
    return RESEARCH_DB if domain in ("research", "intelligence_web") else SALES_DB

from core import db as dblib
from core import datasource as dslib
from core import entity as entitylib
from core import notify as notifylib
from core import search as searchlib
from core import project as projlib
from mcp_server.wechat import search_wechat_articles, read_wechat_article
import importlib

# Use FastMCP for proper MCP protocol handling
server = FastMCP("intelligence-platform-mcp")

# API Key management
API_KEY = None
AUTH_ENABLED = True

async def init_api_key():
    """Initialize API key on startup."""
    global API_KEY, AUTH_ENABLED
    config = get_mcp_config()
    api_key_env = os.environ.get("MCP_API_KEY", "").strip()
    auth_env = os.environ.get("MCP_AUTH_ENABLED", "").strip().lower()

    if auth_env == "false" or config.get("enable_auth") is False:
        AUTH_ENABLED = False
        return None

    if api_key_env:
        API_KEY = api_key_env
        return api_key_env

    key_file = os.path.join(PROJECT_ROOT, "data", "agent_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            API_KEY = f.read().strip()
        return API_KEY

    key = os.urandom(24).hex()
    os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
    with open(key_file, "w") as f:
        f.write(key)
    API_KEY = key
    return key


def _check_auth(scope):
    """Check Bearer token authorization. Returns True if authorized."""
    if not AUTH_ENABLED or not API_KEY:
        return True

    headers = scope.get("headers", [])
    for key, value in headers:
        if key.decode() == "authorization":
            return value.decode() == f"Bearer {API_KEY}"
    return False


def _json_error(message: str, status_code: int = 401) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


# ====== Custom Routes ======

@server.custom_route("/health", ["GET"])
async def health_check(request):
    """Health check endpoint (no auth required)."""
    return JSONResponse({
        "status": "healthy",
        "server": "intelligence-platform-mcp",
        "version": "1.0.0",
        "auth_required": AUTH_ENABLED and bool(API_KEY),
    })


@server.custom_route("/", ["GET"])
async def root_info(request):
    """Platform info endpoint (no auth required)."""
    return JSONResponse({
        "name": "intelligence-platform-mcp",
        "version": "1.0.0",
        "status": "running",
        "transport": "streamable-http",
        "endpoint": "/mcp",
        "auth_required": AUTH_ENABLED and bool(API_KEY),
    })


# ====== Project & Workflow Tools (Agent 采集方向指导) ======

@server.tool()
def list_domains():
    """List all available intelligence domains.

    Returns each domain's slug, name, port, scout_label, and agent names.
    Agent should use this to dynamically discover which domains exist,
    then call get_agent_workflow(domain) and list_active_projects(domain)
    for each one.
    """
    domains = []
    for domain_key, mod_name in [
        ("research", "intelligence_web.domain_spec"),
        ("intelligence_web", "intelligence_web.domain_spec"),
        ("sales", "intelligence_sales.domain_spec"),
        ("intelligence_sales", "intelligence_sales.domain_spec"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            spec = mod.SPEC
            domains.append({
                "domain": spec["slug"],
                "name": spec.get("title_prefix", ""),
                "port": spec.get("port", ""),
                "scout_label": spec.get("scout_label", ""),
                "agent_names": spec.get("agent_names", []),
                "target_types": spec.get("target_types", []),
            })
        except Exception:
            pass
    # Deduplicate by slug
    seen = set()
    unique = []
    for d in domains:
        if d["domain"] not in seen:
            seen.add(d["domain"])
            unique.append(d)
    return {"domains": unique, "total": len(unique)}


@server.tool()
def get_agent_workflow(domain: str = "research"):
    """Get the operating workflow for the specified domain.

    Agent MUST call this first to understand:
    - What statuses are valid in this domain
    - What target types exist
    - Pre-defined entities and data sources
    - The complete collection workflow steps

    domain: "research" (制造情报) or "sales" (销售情报)
    """
    spec_module_map = {
        "research": "intelligence_web.domain_spec",
        "intelligence_web": "intelligence_web.domain_spec",
        "sales": "intelligence_sales.domain_spec",
        "intelligence_sales": "intelligence_sales.domain_spec",
    }
    mod_name = spec_module_map.get(domain, "intelligence_web.domain_spec")
    try:
        mod = importlib.import_module(mod_name)
        spec = mod.SPEC
    except Exception as e:
        return {"error": f"Cannot load domain spec for '{domain}': {e}"}

    statuses = [{"key": k, "label": v} for k, v in spec["statuses"]]

    workflow_steps = [
        "1. 调用 list_domains() 动态发现所有可用域",
        "2. 对每个域调用 get_agent_workflow(domain) 获取本域配置",
        "3. 对每个域调用 list_active_projects(domain) 获取 active 采集项目",
        "4. 对每个项目，自主解读 target_name + scope + instruction + datasources.indicators，构造搜索关键词",
        "5. 调用 web_search 搜索每个关键词（3-5 条结果）",
        "6. 调用 get_project_detail(domain, project_id) 获取已关联情报，用于去重",
        "7. 调用 create_intelligence 入库新情报，必须传入 project_id 关联到对应项目",
        "8. 每个域最多采集 20 条，完成后输出摘要",
    ]

    return {
        "domain": domain,
        "scout_label": spec.get("scout_label", ""),
        "agent_names": spec.get("agent_names", []),
        "statuses": statuses,
        "target_types": spec.get("target_types", []),
        "default_entities": spec.get("default_entities", []),
        "default_data_sources": spec.get("default_data_sources", []),
        "intelligence_ttl_days": spec.get("intelligence_ttl_days", {}),
        "workflow_steps": workflow_steps,
        "create_intelligence_fields": {
            "required": ["title", "content", "category", "domain"],
            "optional": ["project_id", "company", "contact", "deal_value", "source_url", "entity_ids"],
            "project_id": "必填：采集时必须传入对应项目的 ID，确保情报归属正确",
        },
    }


@server.tool()
def list_active_projects(domain: str = "research", status: str = "active",
                         target_type: str = None, limit: int = 50):
    """List all active collection projects for the Agent to guide its collection scope.

    Each project contains: target_name (采集目标), scope (采集范围),
    instruction (采集指令), and linked datasources with indicators (采集源+指标).

    The Agent should use these fields to autonomously construct search keywords.

    domain: "research" or "sales"
    status: "active" or "paused" (default "active")
    target_type: optional filter, e.g. "competitor", "market"
    """
    db = get_db(domain)
    filters = {"status": status} if status else {}

    items = projlib.get_projects(db, filters)

    # Batch-fetch linked datasources for all projects (avoid N+1 queries)
    # get_projects() returns datasource_count (int) but NOT datasources list,
    # so we must fetch them separately via the junction table.
    ds_lookup = {}  # project_id -> list of datasource dicts
    if items:
        project_ids = [p["id"] for p in items]
        placeholders = ",".join("?" for _ in project_ids)
        with dblib.get_db(db) as conn:
            ds_rows = conn.execute(f"""
                SELECT pd.project_id, d.id, d.name, d.url, d.type, d.schedule, d.indicators
                FROM project_datasources pd
                JOIN datasources d ON pd.datasource_id = d.id
                WHERE pd.project_id IN ({placeholders})
                ORDER BY pd.project_id, d.id
            """, project_ids).fetchall()
            for row in ds_rows:
                pid = row["project_id"]
                if pid not in ds_lookup:
                    ds_lookup[pid] = []
                ds_lookup[pid].append(dict(row))

    result = []
    for p in items[:limit]:
        if target_type and p.get("target_type") != target_type:
            continue

        # Build datasources list from batch-fetched lookup
        raw_datasources = ds_lookup.get(p["id"], [])
        datasources = []
        for ds in raw_datasources:
            indicators_raw = ds.get("indicators", "") or ""
            indicators = [i.strip() for i in indicators_raw.split(",") if i.strip()] if indicators_raw else []
            datasources.append({
                "id": ds.get("id"),
                "name": ds.get("name", ""),
                "url": ds.get("url", ""),
                "type": ds.get("type", ""),
                "schedule": ds.get("schedule", ""),
                "indicators": indicators,
            })

        result.append({
            "id": p.get("id"),
            "name": p.get("name", ""),
            "target_type": p.get("target_type", ""),
            "target_name": p.get("target_name", ""),
            "scope": p.get("scope", ""),
            "frequency": p.get("frequency", ""),
            "instruction": p.get("instruction", ""),
            "datasources": datasources,
            "intel_count": p.get("total_intel", 0),
            "status": p.get("status", ""),
            "created_at": p.get("created_at", ""),
        })
    return {"domain": domain, "total": len(result), "items": result}


@server.tool()
def get_project_detail(domain: str = "research", project_id: int = 0):
    """Get a single project's full detail including linked intelligence records.

    Use this to:
    - Understand the project's full context before deep collection
    - Check recently collected intelligence to avoid duplicates

    domain: "research" or "sales"
    project_id: the project ID (from list_active_projects)
    """
    db = get_db(domain)
    project = projlib.get_project_by_id(db, project_id)
    if not project:
        return {"error": f"Project ID {project_id} not found in domain '{domain}'"}

    # Parse datasources indicators
    datasources = []
    for ds in project.get("datasources", []):
        indicators_raw = ds.get("indicators", "") or ""
        indicators = [i.strip() for i in indicators_raw.split(",") if i.strip()] if indicators_raw else []
        datasources.append({
            "id": ds.get("id"),
            "name": ds.get("name", ""),
            "url": ds.get("url", ""),
            "type": ds.get("type", ""),
            "schedule": ds.get("schedule", ""),
            "indicators": indicators,
        })

    proj_detail = {
        "id": project.get("id"),
        "name": project.get("name", ""),
        "target_type": project.get("target_type", ""),
        "target_name": project.get("target_name", ""),
        "scope": project.get("scope", ""),
        "frequency": project.get("frequency", ""),
        "instruction": project.get("instruction", ""),
        "datasources": datasources,
        "intel_count": project.get("total_intel", 0),
        "status": project.get("status", ""),
        "created_at": project.get("created_at", ""),
    }

    # Recent intelligence records (last 20)
    recent_intel = dblib.get_intelligence_by_project(db, project_id, limit=20)
    intel_items = []
    for item in recent_intel:
        intel_items.append({
            "id": item.get("id"),
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "status": item.get("status", ""),
            "source_url": item.get("source_url", ""),
            "created_at": item.get("created_at", ""),
        })

    return {"domain": domain, "project": proj_detail, "recent_intel": intel_items}


# ====== Intelligence Tools ======

@server.tool()
def search_intelligence(query: str, domain: str = "research", limit: int = 10, status: str = None):
    """Search intelligence across domains using Meilisearch."""
    db = get_db(domain)
    engine = searchlib.create_search_engine(db, {})
    if engine is None:
        engine = searchlib.NoopEngine(db, {})
    result = engine.search(query, limit=limit)
    items = []
    for item in result.get("items", []):
        with dblib.get_db(db) as conn:
            intel_entities = conn.execute(
                "SELECT e.name FROM intel_entity ie JOIN entities e ON ie.entity_id = e.id WHERE ie.intelligence_id = ?",
                (item["id"],)
            ).fetchall()
            item["entity_names"] = [e["name"] for e in intel_entities]
        items.append(item)
    return {"query": query, "total": result.get("total", 0), "limit": limit, "items": items}


@server.tool()
def list_intelligence(domain: str = "research", status: str = None, limit: int = 50, offset: int = 0):
    """List intelligence with pagination and status filter."""
    db = get_db(domain)
    filters = {"limit": limit, "offset": offset}
    if status:
        filters["status"] = status
    total_filters = {k: v for k, v in filters.items() if k not in ("limit", "offset")}
    if total_filters:
        total_items = dblib.get_intelligences(db, total_filters)
        total = len(total_items)
    else:
        total = len(dblib.get_intelligences(db, {"limit": 10000}))
    items = dblib.get_intelligences(db, filters)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@server.tool()
def get_intelligence(id: int, domain: str = "research"):
    """Get single intelligence by ID with comments."""
    db = get_db(domain)
    intel = dblib.get_intelligence_by_id(db, id)
    if not intel:
        return {"error": f"Intelligence ID {id} not found"}
    comments = dblib.get_comments(db, id, limit=5)
    intel["comments"] = comments
    return intel


@server.tool()
def create_intelligence(title: str, content: str, category: str, domain: str = "research",
                        company: str = None, contact: str = None, deal_value: float = None,
                        source_url: str = None, entity_ids: list = None,
                        project_id: int = None):
    """Create new intelligence record.

    IMPORTANT: When collecting intelligence via project, MUST pass project_id
    to link the intelligence to the correct collection project.
    """
    db = get_db(domain)
    metadata = {}
    if company:
        metadata["company"] = company
    if deal_value:
        metadata["deal_value"] = deal_value
    if source_url:
        metadata["source_url"] = source_url

    intel_id = dblib.create_intelligence(
        db, title=title, content=content, category=category,
        contact_name=contact or "",
        metadata=metadata if metadata else None,
        project_id=project_id,
    )
    if entity_ids and intel_id:
        with dblib.get_db(db) as conn:
            for eid in entity_ids:
                conn.execute(
                    "INSERT INTO intel_entity (intelligence_id, entity_id, relevance) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                    (intel_id, eid, "primary")
                )
    return {"id": intel_id, "title": title, "domain": domain, "project_id": project_id}


@server.tool()
def update_intelligence_status(id: int, status: str, opinion: str = None, domain: str = "research"):
    """Update intelligence status."""
    db = get_db(domain)
    old_status = None
    with dblib.get_db(db) as conn:
        old_status = conn.execute("SELECT status FROM intelligence WHERE id = ?", (id,)).fetchone()
        old_status = old_status["status"] if old_status else None
    success = dblib.update_intelligence_status(db, id, status)
    if success and opinion:
        dblib.add_comment(db, id, opinion, "admin")
    return {"id": id, "old_status": old_status, "new_status": status, "success": success}


@server.tool()
def add_comment(id: int, content: str, agent_name: str = "agent", domain: str = "research"):
    """Add a comment to an intelligence record."""
    db = get_db(domain)
    intel = dblib.get_intelligence_by_id(db, id)
    if not intel:
        return {"error": f"Intelligence ID {id} not found"}
    comment_id = dblib.add_comment(db, id, agent_name, content)
    return {"id": comment_id, "intelligence_id": id, "content": content, "success": True}


@server.tool()
def list_data_sources(domain: str = "research"):
    """List data sources."""
    db = get_db(domain)
    return dslib.list_sources(db)


@server.tool()
def create_data_source(name: str, type_: str, url: str, indicators: list, schedule: str,
                       domain: str = "research", description: str = None):
    """Create a data source."""
    db = get_db(domain)
    dsid = dslib.add_source(db, name, type_, url, indicators=indicators, schedule=schedule, description=description)
    return {"id": dsid, "name": name, "type": type_, "url": url, "domain": domain}


@server.tool()
def get_crawl_logs(source_id: int, limit: int = 50):
    """Get crawl logs for a data source (placeholder)."""
    return {"source_id": source_id, "logs": [], "message": "Crawl log feature not yet implemented"}


@server.tool()
def list_entities(domain: str = "research", type_: str = None):
    """List entities."""
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.list_entities(db, type_=type_)


@server.tool()
def get_entity_by_name(name: str, domain: str = "research"):
    """Get entity by name or alias."""
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.get_entity_by_name(db, name)


@server.tool()
def link_intelligence_to_entity(intel_id: int, entity_id: int, relevance: str = "primary", domain: str = "research"):
    """Link intelligence to entity with relevance level."""
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.link_intel_to_entity(db, intel_id, entity_id, relevance)


@server.tool()
def get_intel_for_entity(entity_id: int, domain: str = "research", limit: int = 50):
    """Get all intelligence linked to an entity."""
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.get_intel_for_entity(db, entity_id, limit=limit)


@server.tool()
def list_subscriptions(user_id: int, domain: str = "research"):
    """List user subscriptions."""
    db = get_db(domain)
    notifylib.init_notifications_table(db)
    return notifylib.list_subscriptions(db, user_id)


@server.tool()
def create_subscription(value: str, type_: str, domain: str = "research", channel: str = "in_app", user_id: int = None):
    """Create a subscription."""
    db = get_db(domain)
    notifylib.init_notifications_table(db)
    sub_id = notifylib.add_subscription(db, user_id, type_, value, channel)
    return {"id": sub_id, "value": value, "type": type_, "domain": domain}


@server.tool()
def get_notifications(user_id: int, domain: str = "research", unread_only: bool = False, limit: int = 50):
    """Get notifications for user."""
    db = get_db(domain)
    notifylib.init_notifications_table(db)
    return notifylib.list_notifications(db, user_id, limit=limit, unread_only=unread_only)


@server.tool()
async def system_status():
    """Get system status and available tools."""
    research_rows = dblib.get_intelligences(RESEARCH_DB, {"limit": 100})
    sales_rows = dblib.get_intelligences(SALES_DB, {"limit": 100})
    research_sources = dslib.list_sources(RESEARCH_DB)
    sales_sources = dslib.list_sources(SALES_DB)
    entitylib.init_entities_table(RESEARCH_DB)
    research_entities = entitylib.list_entities(RESEARCH_DB)
    entitylib.init_entities_table(SALES_DB)
    sales_entities = entitylib.list_entities(SALES_DB)
    tools = await server.list_tools()
    return {
        "platform": "Intelligence Platform MCP Server",
        "version": "1.0.0",
        "domains": {
            "research": {"intelligence": len(research_rows), "data_sources": len(research_sources), "entities": len(research_entities)},
            "sales": {"intelligence": len(sales_rows), "data_sources": len(sales_sources), "entities": len(sales_entities)},
        },
        "available_tools": [t.name for t in tools],
        "total_tools": len(tools),
    }


# ====== 微信公众号「搜」+「读」工具 ======

@server.tool()
def wechat_search(account: str, keyword: str = "", max_results: int = 10) -> dict:
    """搜索指定公众号内的文章，返回 mp.weixin.qq.com 直链候选列表。

    用于公众号类型数据源的情报发现：
    - account: 公众号名称（必填），限定搜索范围，如"迅越印刷ERP"
    - keyword: 可选主题关键词，进一步过滤该号内的情报项
    - max_results: 最多返回条数（默认 10）

    返回 list[dict]，每条含 title / url / snippet / source / published_date。
    拿到 url 后调用 wechat_read_article 读取正文，再入库。
    """
    return {"results": search_wechat_articles(account, keyword, max_results)}


@server.tool()
def wechat_read_article(url: str) -> dict:
    """读取单篇微信公众号文章正文。

    Args:
        url: mp.weixin.qq.com 文章直链（来自 wechat_search 返回的 url）。

    Returns:
        dict: title / account / published_date / content / url。
        失败时返回 {error: ...}，Agent 据此决定是否跳过或重试。
    """
    return read_wechat_article(url)


# ====== Main ======

async def main():
    global AUTH_ENABLED
    # Initialize API key
    key = await init_api_key()
    auth_status = "enabled" if (AUTH_ENABLED and API_KEY) else "disabled"

    # Configure FastMCP settings for custom host/port
    # MCP_BIND_HOST: Docker 容器内监听地址（默认 127.0.0.1）
    # MCP_HOST: 对外 URL 中使用的域名（由 get_mcp_config() 使用）
    # Enable stateless HTTP mode — no session management required.
    # This makes the server work with simple POST requests (no session ID needed),
    # which is what most MCP clients and test agents expect.
    server.settings.stateless_http = True
    server.settings.json_response = True

    # Disable DNS rebinding protection because:
    # - frp/VPN tunnels modify the Host header (e.g. "nat.ywapi.com:8768")
    # - The MCP SDK only allows 127.0.0.1 / localhost by default
    # - This causes HTTP 421 "Invalid Host header" for proxied requests
    server.settings.transport_security.enable_dns_rebinding_protection = False

    host = os.environ.get("MCP_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))
    server.settings.host = host
    server.settings.port = port

    print(f"[MCP Server] Starting on {host}:{port} (auth={auth_status})")

    # Use run_streamable_http_async() which properly initializes the task group
    await server.run_streamable_http_async()


if __name__ == "__main__":
    asyncio.run(main())
