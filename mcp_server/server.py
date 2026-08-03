#!/usr/bin/env python3
"""
Intelligence Platform MCP Server
提供情报管理、数据源管理、实体管理、通知订阅等工具的标准化 MCP 接口
支持 HTTP 传输 (Streamable HTTP)
"""

import os
import asyncio
import sys

# Ensure /app is in the Python path for module imports
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

from mcp.server.fastmcp import FastMCP
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

# API Key middleware
API_KEY = None
AUTH_ENABLED = True

async def check_api_key():
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

# ====== Tools ======

@server.tool(description="Search intelligence across domains using Meilisearch")
def search_intelligence(query: str, domain: str = "research", limit: int = 10, status: str = None):
    db = get_db(domain)
    engine = searchlib.create_search_engine(db, {})
    if engine is None:
        engine = searchlib.NoopEngine(db, {})
    result = engine.search(query, limit=limit)
    items = []
    for item in result.get("items", []):
        # Enhance with entity names
        with dblib.get_db(db) as conn:
            intel_entities = conn.execute(
                "SELECT e.name FROM intel_entity ie JOIN entities e ON ie.entity_id = e.id WHERE ie.intelligence_id = ?",
                (item["id"],)
            ).fetchall()
            item["entity_names"] = [e["name"] for e in intel_entities]
        items.append(item)
    return {"query": query, "total": result.get("total", 0), "limit": limit, "items": items}

@server.tool(description="List intelligence with pagination and status filter")
def list_intelligence(domain: str = "research", status: str = None, limit: int = 50, offset: int = 0):
    db = get_db(domain)
    filters = {"limit": limit, "offset": offset}
    if status:
        filters["status"] = status
    # Fetch total count first (without limit/offset) for accurate pagination
    total_filters = {k: v for k, v in filters.items() if k not in ("limit", "offset")}
    if total_filters:
        total_items = dblib.get_intelligences(db, total_filters)
        total = len(total_items)
    else:
        total = len(dblib.get_intelligences(db, {"limit": 10000}))
    items = dblib.get_intelligences(db, filters)
    return {"total": total, "limit": limit, "offset": offset, "items": items}

@server.tool(description="Get single intelligence by ID with comments")
def get_intelligence(id: int, domain: str = "research"):
    db = get_db(domain)
    intel = dblib.get_intelligence_by_id(db, id)
    if not intel:
        return {"error": f"Intelligence ID {id} not found"}
    comments = dblib.get_comments(db, id, limit=5)
    intel["comments"] = comments
    return intel

@server.tool(description="Create new intelligence record")
def create_intelligence(title: str, content: str, category: str, domain: str = "research",
                        company: str = None, contact: str = None, deal_value: float = None,
                        source_url: str = None, entity_ids: list = None):
    db = get_db(domain)
    # Build metadata dict for the core db layer
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

@server.tool(description="Update intelligence status")
def update_intelligence_status(id: int, status: str, opinion: str = None, domain: str = "research"):
    db = get_db(domain)
    old_status = None
    with dblib.get_db(db) as conn:
        old_status = conn.execute("SELECT status FROM intelligence WHERE id = ?", (id,)).fetchone()
        old_status = old_status["status"] if old_status else None
    success = dblib.update_intelligence_status(db, id, status)
    if success and opinion:
        dblib.add_comment(db, id, opinion, "admin")
    return {"id": id, "old_status": old_status, "new_status": status, "success": success}

# ---- Data Sources ----

@server.tool(description="List data sources")
def list_data_sources(domain: str = "research"):
    db = get_db(domain)
    return dslib.list_sources(db)

@server.tool(description="Create a data source")
def create_data_source(name: str, type_: str, url: str, indicators: list, schedule: str,
                       domain: str = "research", description: str = None):
    db = get_db(domain)
    dsid = dslib.add_source(db, name, type_, url, indicators=indicators, schedule=schedule, description=description)
    return {"id": dsid, "name": name, "type": type_, "url": url, "domain": domain}

@server.tool(description="Get crawl logs for a data source (placeholder)")
def get_crawl_logs(source_id: int, limit: int = 50):
    return {"source_id": source_id, "logs": [], "message": "Crawl log feature not yet implemented"}

# ---- Entities ----

@server.tool(description="List entities")
def list_entities(domain: str = "research", type_: str = None):
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.list_entities(db, type_=type_)

@server.tool(description="Get entity by name or alias")
def get_entity_by_name(name: str, domain: str = "research"):
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.get_entity_by_name(db, name)

@server.tool(description="Link intelligence to entity with relevance level")
def link_intelligence_to_entity(intel_id: int, entity_id: int, relevance: str = "primary", domain: str = "research"):
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.link_intel_to_entity(db, intel_id, entity_id, relevance)

@server.tool(description="Get all intelligence linked to an entity")
def get_intel_for_entity(entity_id: int, domain: str = "research", limit: int = 50):
    db = get_db(domain)
    entitylib.init_entities_table(db)
    return entitylib.get_intel_for_entity(db, entity_id, limit=limit)

# ---- Notifications & Subscriptions ----

@server.tool(description="List user subscriptions")
def list_subscriptions(user_id: int, domain: str = "research"):
    db = get_db(domain)
    notifylib.init_notifications_table(db)
    return notifylib.list_subscriptions(db, user_id)

@server.tool(description="Create a subscription")
def create_subscription(value: str, type_: str, domain: str = "research", channel: str = "in_app", user_id: int = None):
    db = get_db(domain)
    notifylib.init_notifications_table(db)
    sub_id = notifylib.add_subscription(db, user_id, type_, value, channel)
    return {"id": sub_id, "value": value, "type": type_, "domain": domain}

@server.tool(description="Get notifications for user")
def get_notifications(user_id: int, domain: str = "research", unread_only: bool = False, limit: int = 50):
    db = get_db(domain)
    notifylib.init_notifications_table(db)
    return notifylib.list_notifications(db, user_id, limit=limit, unread_only=unread_only)

# ---- System ----

@server.tool(description="Get system status and available tools")
def system_status():
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


# ====== HTTP Serving ======

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

mcp_app = server.streamable_http_app()


class GatewayHandler:
    """Unified ASGI middleware that handles auth, health, root info,
    and forwards MCP requests to the FastMCP app (which serves at /mcp).

    This ensures:
      - GET  /        → platform info (no auth needed)
      - POST /        → rewritten to /mcp, handled by MCP (auth required)
      - GET  /mcp     → forwarded to MCP app (auth required)
      - POST /mcp     → MCP JSON-RPC (auth required)
      - GET  /health  → health check (no auth needed)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # --- Public endpoints (no auth) ---

        # Health check
        if path == "/health":
            response = JSONResponse({
                "status": "healthy",
                "server": "intelligence-platform-mcp",
                "version": "1.0.0",
                "auth_required": AUTH_ENABLED and bool(API_KEY),
            })
            await response(scope, receive, send)
            return

        # Root info — GET returns platform info, POST rewrites to /mcp for MCP
        if path == "/":
            if method == "POST":
                # Rewrite path to /mcp so FastMCP's internal routing works
                scope = dict(scope)
                scope["path"] = "/mcp"
                # Auth check applies, fall through to auth check below
            else:
                response = JSONResponse({
                    "name": "intelligence-platform-mcp",
                    "version": "1.0.0",
                    "status": "running",
                    "transport": "streamable-http",
                    "endpoint": "/mcp",
                    "auth_required": AUTH_ENABLED and bool(API_KEY),
                })
                await response(scope, receive, send)
                return

        # --- Auth check ---
        auth = None
        headers = scope.get("headers", [])
        for key, value in headers:
            if key.decode() == "authorization":
                auth = value.decode()
                break

        if AUTH_ENABLED and API_KEY and not auth:
            response = JSONResponse(
                {"error": "Unauthorized: Authorization header required"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        if AUTH_ENABLED and API_KEY and auth != f"Bearer {API_KEY}":
            response = JSONResponse(
                {"error": "Unauthorized: Invalid API key"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        # Forward to MCP app
        await self.app(scope, receive, send)


# ====== Main ======

async def main():
    # Initialize API key on startup
    await check_api_key()

    # Mount the MCP app at / and wrap with GatewayHandler.
    # GatewayHandler handles /health, GET /, POST / rewriting to /mcp.
    # The FastMCP app internally routes /mcp to the MCP JSON-RPC handler.
    # Use the inner app's lifespan to initialize the session manager.
    final_app = Starlette(
        routes=[
            Mount("/", app=GatewayHandler(mcp_app)),
        ],
        lifespan=mcp_app.router.lifespan_context,
    )
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8768"))
    auth_status = "enabled" if (AUTH_ENABLED and API_KEY) else "disabled"
    print(f"[MCP Server] Starting on {host}:{port} (auth={auth_status})")
    config = uvicorn.Config(final_app, host=host, port=port, lifespan="on")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
