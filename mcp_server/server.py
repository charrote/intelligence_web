"""MCP Server for Intelligence Platform.

Provides AI agents with tools to query, create, and manage intelligence data.
Supports stdio transport for integration with Claude, OpenClaw, Hermes, etc.
"""

import os
import sys
import json
import asyncio

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core import db as dblib
from core import datasource as dslib
from core import entity as entitylib
from core import notify as notifylib
from core import search as searchlib

# Crawler MCP tools (placeholder — crawler_service removed, stub for compatibility)
_CRAWLER_TOOLS = {}
_CRAWLER_HANDLERS = {}

RESEARCH_DB = dblib.get_db_path(PROJECT_ROOT, "intelligence")
SALES_DB = dblib.get_db_path(PROJECT_ROOT, "intelligence_sales")


def get_db(domain):
    return SALES_DB if domain == "sales" else RESEARCH_DB


# ===========================================================================
# Tool definitions (simple JSON-RPC style)
# ===========================================================================

TOOLS = {
    "search_intelligence": {
        "description": "Search intelligence by keyword across domains",
        "parameters": {
            "query": {"type": "string", "description": "Search keyword"},
            "domain": {"type": "string", "default": "research", "enum": ["research", "sales"]},
            "limit": {"type": "integer", "default": 20, "maximum": 50},
            "status": {"type": "string", "description": "Filter by status"},
        },
        "handler": "search_intelligence",
    },
    "list_intelligence": {
        "description": "List intelligence items from a domain",
        "parameters": {
            "domain": {"type": "string", "default": "research", "enum": ["research", "sales"]},
            "status": {"type": "string", "description": "Filter by status"},
            "limit": {"type": "integer", "default": 50, "maximum": 100},
            "offset": {"type": "integer", "default": 0},
        },
        "handler": "list_intelligence",
    },
    "get_intelligence": {
        "description": "Get a specific intelligence item by ID",
        "parameters": {
            "id": {"type": "integer", "description": "Intelligence item ID"},
            "domain": {"type": "string", "default": "research", "enum": ["research", "sales"]},
        },
        "handler": "get_intelligence",
    },
    "create_intelligence": {
        "description": "Create a new intelligence item",
        "parameters": {
            "title": {"type": "string", "description": "Title"},
            "content": {"type": "string", "description": "Content (Markdown)"},
            "category": {"type": "string", "default": ""},
            "company": {"type": "string", "default": ""},
            "deal_value": {"type": "number", "default": 0},
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
            "source_url": {"type": "string", "default": ""},
            "entity_ids": {"type": "string", "default": "", "description": "Comma-separated entity IDs"},
        },
        "handler": "create_intelligence",
    },
    "update_intelligence_status": {
        "description": "Update intelligence status",
        "parameters": {
            "id": {"type": "integer", "description": "ID"},
            "status": {"type": "string", "description": "New status"},
            "opinion": {"type": "string", "default": ""},
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
        },
        "handler": "update_intelligence_status",
    },
    "list_data_sources": {
        "description": "List data sources for a domain",
        "parameters": {
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
        },
        "handler": "list_data_sources",
    },
    "create_data_source": {
        "description": "Create a data source",
        "parameters": {
            "name": {"type": "string"},
            "type_": {"type": "string", "default": "website"},
            "url": {"type": "string"},
            "indicators": {"type": "string", "default": ""},
            "schedule": {"type": "string", "default": "daily"},
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
            "description": {"type": "string", "default": ""},
        },
        "handler": "create_data_source",
    },
    "get_crawl_logs": {
        "description": "Get crawl logs",
        "parameters": {
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
            "source_id": {"type": "integer"},
            "limit": {"type": "integer", "default": 20},
        },
        "handler": "get_crawl_logs",
    },
    "list_entities": {
        "description": "List entities for a domain",
        "parameters": {
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
            "type_": {"type": "string"},
        },
        "handler": "list_entities",
    },
    "get_entity_by_name": {
        "description": "Find entity by name or alias",
        "parameters": {
            "name": {"type": "string"},
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
        },
        "handler": "get_entity_by_name",
    },
    "link_intelligence_to_entity": {
        "description": "Link intelligence to entity",
        "parameters": {
            "intel_id": {"type": "integer"},
            "entity_id": {"type": "integer"},
            "relevance": {"type": "string", "default": "primary"},
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
        },
        "handler": "link_intelligence_to_entity",
    },
    "get_intel_for_entity": {
        "description": "Get intelligence linked to an entity",
        "parameters": {
            "entity_id": {"type": "integer"},
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
            "limit": {"type": "integer", "default": 20},
        },
        "handler": "get_intel_for_entity",
    },
    "list_subscriptions": {
        "description": "List subscriptions for a user",
        "parameters": {
            "user_id": {"type": "integer", "default": 1},
        },
        "handler": "list_subscriptions",
    },
    "create_subscription": {
        "description": "Create a subscription",
        "parameters": {
            "value": {"type": "string"},
            "type_": {"type": "string", "default": "keyword"},
            "domain": {"type": "string", "default": "sales", "enum": ["research", "sales"]},
            "channel": {"type": "string", "default": "in_app"},
        },
        "handler": "create_subscription",
    },
    "get_notifications": {
        "description": "Get notifications for a user",
        "parameters": {
            "user_id": {"type": "integer", "default": 1},
            "unread_only": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "default": 20},
        },
        "handler": "get_notifications",
    },
    "system_status": {
        "description": "Get system status and available tools",
        "parameters": {},
        "handler": "system_status",
    },
}

# Merge crawler MCP tools
TOOLS.update(_CRAWLER_TOOLS)


# ===========================================================================
# Handlers
# ===========================================================================

def search_intelligence(query, domain="research", limit=20, status=None):
    db = get_db(domain)
    engine = searchlib.create_search_engine(db, {"engine": "meilisearch"})
    results = engine.search(query, limit=min(limit, 50))
    items = []
    for r in results.get("items", [])[:limit]:
        item = {
            "id": r["id"],
            "title": r["title"],
            "status": r.get("status", ""),
            "category": r.get("category", ""),
            "created_at": r.get("created_at", ""),
            "content_preview": (r.get("content") or "")[:200],
            "entity_ids": r.get("entity_ids", []),
        }
        # Enrich with entity names from db
        try:
            entity_rows = entitylib.get_entities_for_intel(db, r["id"])
            if entity_rows:
                item["entities"] = [e["name"] for e in entity_rows]
        except Exception:
            pass
        items.append(item)
    return {"query": query, "count": len(items), "items": items}


def list_intelligence(domain="research", status=None, limit=50, offset=0):
    db = get_db(domain)
    filters = {"limit": min(limit, 100), "offset": offset}
    if status:
        filters["status"] = status
    result = dblib.get_intelligences(db, filters)
    items = []
    for r in result["items"]:
        items.append({
            "id": r["id"],
            "title": r["title"],
            "status": r.get("status", ""),
            "category": r.get("category", ""),
            "company": r.get("company", ""),
            "deal_value": r.get("deal_value", 0),
            "created_at": r.get("created_at", ""),
            "source_url": r.get("source_url", ""),
        })
    return {"total": result["total"], "limit": limit, "offset": offset, "items": items}


def get_intelligence(id, domain="research"):
    db = get_db(domain)
    intel = dblib.get_intelligence_by_id(db, id)
    if not intel:
        return {"error": "Not found", "id": id}
    comments = dblib.get_comments(db, id, limit=10)
    intel["comments"] = [{"agent_name": c["agent_name"], "content": c["content"], "created_at": c["created_at"]} for c in comments]
    intel["entities"] = entitylib.get_entities_for_intel(db, id)
    return intel


def create_intelligence(title, content, category="", company="", deal_value=0, domain="sales", source_url="", entity_ids=""):
    db = get_db(domain)
    extra = {}
    if domain == "sales" and company:
        extra = {"company": company, "deal_value": deal_value}
    intel_id = dblib.create_intelligence(db, title, content, category, source_url, extra if extra else None)
    if intel_id is None:
        return {"error": "Duplicate title, skipping", "title": title}
    if entity_ids:
        for eid in entity_ids.split(","):
            eid = eid.strip()
            if eid:
                try:
                    entitylib.link_entity(db, intel_id, int(eid), "primary")
                except:
                    pass
    return {"id": intel_id, "status": "pending", "title": title}


def update_intelligence_status(id, status, opinion="", domain="sales"):
    db = get_db(domain)
    if dblib.update_intelligence_status(db, id, status, opinion):
        return {"success": True, "id": id, "status": status}
    return {"error": "Not found", "id": id}


def list_data_sources(domain="sales"):
    db = get_db(domain)
    sources = dslib.list_sources(db, domain)
    return {"count": len(sources), "sources": sources}


def create_data_source(name, type_="website", url="", indicators="", schedule="daily", domain="sales", description=""):
    db = get_db(domain)
    inds = [i.strip() for i in indicators.split(",") if i.strip()] if indicators else []
    sid = dslib.create_source(db, domain, name, type_, url, inds, schedule, description)
    return {"id": sid, "name": name, "success": True}


def get_crawl_logs(domain="sales", source_id=None, limit=20):
    db = get_db(domain)
    logs = dslib.get_crawl_logs(db, source_id, limit=min(limit, 50))
    return {"count": len(logs), "logs": logs}


def list_entities(domain="sales", type_=None):
    db = get_db(domain)
    entities = entitylib.list_entities(db, domain, type_)
    return {"count": len(entities), "entities": entities}


def get_entity_by_name(name, domain="sales"):
    db = get_db(domain)
    entities = entitylib.list_entities(db, domain)
    for e in entities:
        if e["name"].lower() == name.lower() or any(a.lower() == name.lower() for a in e.get("aliases", [])):
            return e
    return {"error": f"Entity '{name}' not found", "domain": domain}


def link_intelligence_to_entity(intel_id, entity_id, relevance="primary", domain="sales"):
    db = get_db(domain)
    entitylib.link_entity(db, intel_id, entity_id, relevance)
    return {"success": True, "intelligence_id": intel_id, "entity_id": entity_id}


def get_intel_for_entity(entity_id, domain="sales", limit=20):
    db = get_db(domain)
    items = entitylib.get_intel_for_entity(db, entity_id, limit=min(limit, 50))
    return {"count": len(items), "items": [{"id": i["id"], "title": i["title"], "status": i["status"], "relevance": i.get("relevance", "")} for i in items]}


def list_subscriptions(user_id=1):
    db = SALES_DB
    subs = notifylib.list_subscriptions(db, user_id)
    return {"count": len(subs), "subscriptions": subs}


def create_subscription(value, type_="keyword", domain="sales", channel="in_app"):
    db = SALES_DB
    sid = notifylib.create_subscription(db, 1, domain, type_, value, channel)
    return {"id": sid, "value": value, "type": type_, "success": True}


def get_notifications(user_id=1, unread_only=False, limit=20):
    db = SALES_DB
    notifs = notifylib.list_notifications(db, user_id, limit=min(limit, 50), unread_only=unread_only)
    unread = notifylib.count_unread(db, user_id)
    return {"unread": unread, "count": len(notifs), "notifications": notifs}


def system_status():
    research_count = dblib.get_intelligences(RESEARCH_DB, {"limit": 1})["total"]
    sales_count = dblib.get_intelligences(SALES_DB, {"limit": 1})["total"]
    research_sources = len(dslib.list_sources(RESEARCH_DB, "intelligence_web"))
    sales_sources = len(dslib.list_sources(SALES_DB, "intelligence_sales"))
    research_entities = len(entitylib.list_entities(RESEARCH_DB, "intelligence_web"))
    sales_entities = len(entitylib.list_entities(SALES_DB, "intelligence_sales"))
    return {
        "platform": "Intelligence Platform MCP Server",
        "version": "1.0.0",
        "domains": {
            "research": {"intelligence": research_count, "data_sources": research_sources, "entities": research_entities},
            "sales": {"intelligence": sales_count, "data_sources": sales_sources, "entities": sales_entities},
        },
        "available_tools": list(TOOLS.keys()),
        "total_tools": len(TOOLS),
    }


HANDLERS = {
    "search_intelligence": search_intelligence,
    "list_intelligence": list_intelligence,
    "get_intelligence": get_intelligence,
    "create_intelligence": create_intelligence,
    "update_intelligence_status": update_intelligence_status,
    "list_data_sources": list_data_sources,
    "create_data_source": create_data_source,
    "get_crawl_logs": get_crawl_logs,
    "list_entities": list_entities,
    "get_entity_by_name": get_entity_by_name,
    "link_intelligence_to_entity": link_intelligence_to_entity,
    "get_intel_for_entity": get_intel_for_entity,
    "list_subscriptions": list_subscriptions,
    "create_subscription": create_subscription,
    "get_notifications": get_notifications,
    "system_status": system_status,
    # Crawler tools (Phase 15.3)
    **_CRAWLER_HANDLERS,
}


# ===========================================================================
# MCP Protocol (JSON-RPC over stdio)
# ===========================================================================

def handle_message(message):
    """Handle a single MCP message."""
    method = message.get("method", "")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "intelligence-platform-mcp",
                    "version": "1.0.0",
                },
            },
        }

    elif method == "initialized":
        return None  # No response needed

    elif method == "tools/list":
        tools = []
        for name, spec in TOOLS.items():
            tools.append({
                "name": name,
                "description": spec["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": {k: v for k, v in spec["parameters"].items()},
                    "required": [k for k, v in spec["parameters"].items() if "default" not in v],
                },
            })
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"tools": tools},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"error": f"Tool '{tool_name}' not found", "content": []},
            }
        try:
            result = handler(**arguments)
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"error": str(e), "content": []},
            }

    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"content": [{"type": "text", "text": "pong"}]},
        }

    return None


async def run_stdio():
    """Run MCP server with stdio transport."""
    import asyncio
    import json

    async def read_line():
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        return line

    while True:
        try:
            line = await read_line()
            if not line:
                break
            message = json.loads(line.strip())
            response = handle_message(message)
            if response:
                print(json.dumps(response, ensure_ascii=False))
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)


if __name__ == "__main__":
    asyncio.run(run_stdio())
