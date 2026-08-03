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


# ====== MCP Tools ======

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
                        source_url: str = None, entity_ids: list = None):
    """Create new intelligence record."""
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
    )
    if entity_ids and intel_id:
        with dblib.get_db(db) as conn:
            for eid in entity_ids:
                conn.execute(
                    "INSERT INTO intel_entity (intelligence_id, entity_id, relevance) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                    (intel_id, eid, "primary")
                )
    return {"id": intel_id, "title": title, "domain": domain}


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
def system_status():
    """Get system status and available tools."""
    research_rows = dblib.get_intelligences(RESEARCH_DB, {"limit": 100})
    sales_rows = dblib.get_intelligences(SALES_DB, {"limit": 100})
    research_sources = dslib.list_sources(RESEARCH_DB)
    sales_sources = dslib.list_sources(SALES_DB)
    entitylib.init_entities_table(RESEARCH_DB)
    research_entities = entitylib.list_entities(RESEARCH_DB)
    entitylib.init_entities_table(SALES_DB)
    sales_entities = entitylib.list_entities(SALES_DB)
    return {
        "platform": "Intelligence Platform MCP Server",
        "version": "1.0.0",
        "domains": {
            "research": {"intelligence": len(research_rows), "data_sources": len(research_sources), "entities": len(research_entities)},
            "sales": {"intelligence": len(sales_rows), "data_sources": len(sales_sources), "entities": len(sales_entities)},
        },
        "available_tools": [t.name for t in server.list_tools()],
        "total_tools": len(server.list_tools()),
    }


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

    host = os.environ.get("MCP_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))
    server.settings.host = host
    server.settings.port = port

    print(f"[MCP Server] Starting on {host}:{port} (auth={auth_status})")

    # Use run_streamable_http_async() which properly initializes the task group
    await server.run_streamable_http_async()


if __name__ == "__main__":
    asyncio.run(main())
