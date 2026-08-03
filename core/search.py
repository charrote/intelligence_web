"""Search engine abstraction — currently backed by Meilisearch HTTP API.

The search module provides a unified interface for indexing and querying
intelligence records across domains.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None


# ---------------------------------------------------------------------------
# Meilisearch HTTP client (no SDK dependency)
# ---------------------------------------------------------------------------

class MeiliSearchEngine:
    """Thin HTTP client wrapping Meilisearch REST API."""

    def __init__(self, url, api_key, index_name):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.index_name = index_name
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # -- public API used by server.py handlers --------------------------------

    def search(self, query, limit=20):
        """Search the index and return results in the same shape as other
        search backends: ``{"items": [...], "total": N}``."""
        url = f"{self.url}/indexes/{self.index_name}/search"
        payload = {
            "q": query,
            "limit": min(limit, 50),
            "attributesToRetrieve": [
                "id", "title", "content", "category", "status",
                "company", "contact_name", "created_at", "source_url",
                "entity_ids",
            ],
        }
        resp = requests.post(
            url,
            json=payload,
            headers=self._headers,
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        items = []
        for hit in data.get("hits", []):
            items.append({
                "id": hit.get("id"),
                "title": hit.get("title", ""),
                "category": hit.get("category", ""),
                "status": hit.get("status", ""),
                "company": hit.get("company", ""),
                "contact_name": hit.get("contact_name", ""),
                "created_at": hit.get("created_at", ""),
                "source_url": hit.get("source_url", ""),
                "content": hit.get("content", ""),
                "entity_ids": hit.get("entity_ids", []),
                "_score": hit.get("_score", 0),
            })
        return {"items": items, "total": len(items), "query": query}

    def index_intelligence(self, db_path):
        """Re-index all intelligence records from the given SQLite database."""
        docs = self._collect_documents(db_path)
        if not docs:
            return 0

        # Upsert via replaceAllDocuments
        url = f"{self.url}/indexes/{self.index_name}/documents"
        resp = requests.put(
            url,
            json=docs,
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return len(docs)

    def _collect_documents(self, db_path):
        """Extract intelligence records ready for Meilisearch indexing."""
        docs = []
        with _get(db_path) as conn:
            rows = conn.execute("""
                SELECT i.id, i.title, i.content, i.category, i.status,
                       i.company, i.contact_name, i.created_at,
                       i.updated_at, p.name AS project_name
                FROM intelligence i
                LEFT JOIN projects p ON i.project_id = p.id
                ORDER BY i.id
            """).fetchall()
            for row in rows:
                # Get linked entity IDs
                entity_ids = []
                eids = conn.execute(
                    "SELECT entity_id FROM intel_entity WHERE intelligence_id = ?",
                    (row["id"],),
                ).fetchall()
                entity_ids = [e["entity_id"] for e in eids]

                docs.append({
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"][:2000],  # Truncate for relevance
                    "category": row["category"],
                    "status": row["status"],
                    "company": row["company"],
                    "contact_name": row["contact_name"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "source_url": "",  # Not stored per-record in current schema
                    "entity_ids": entity_ids,
                })
        return docs

    def index_documents(self, documents):
        """Index raw document dicts directly (used by other services)."""
        if not documents:
            return 0
        url = f"{self.url}/indexes/{self.index_name}/documents"
        resp = requests.put(
            url,
            json=documents,
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return len(documents)

    def get_status(self):
        """Return Meilisearch service status."""
        try:
            resp = requests.get(
                f"{self.url}/health",
                headers=self._headers,
                timeout=3,
            )
            return resp.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_search_engine(db_path, config):
    """Create a search engine instance from a domain spec's ``search`` config.

    Config example::

        {"engine": "meilisearch", "url": "http://meilisearch:7700", "api_key": "..."}

    Returns a MeiliSearchEngine (or a NoopEngine if requests is unavailable).
    """
    engine = config.get("engine", "none")
    if engine == "meilisearch":
        if requests is None:
            return NoopEngine(db_path, config)
        return MeiliSearchEngine(
            url=config.get("url", "http://localhost:7700"),
            api_key=config.get("api_key", ""),
            index_name=config.get("index_name", f"intelligence_{db_path.split('/')[-1].replace('.db', '').replace('.sqlite', '')}"),
        )
    return NoopEngine(db_path, config)


class NoopEngine:
    """Fallback search engine when Meilisearch is unavailable.

    Performs a simple SQLite LIKE search on the intelligence table.
    """

    def __init__(self, db_path, config):
        self.db_path = db_path

    def search(self, query, limit=20):
        """Basic SQLite full-text search."""
        results = []
        search_term = f"%{query}%"
        try:
            with _get(self.db_path) as conn:
                rows = conn.execute("""
                    SELECT id, title, content, category, status,
                           company, contact_name, created_at
                    FROM intelligence
                    WHERE title LIKE ? OR content LIKE ? OR category LIKE ?
                    LIMIT ?
                """, (search_term, search_term, search_term, limit)).fetchall()
                for row in rows:
                    results.append({
                        "id": row["id"],
                        "title": row["title"],
                        "content": (row["content"] or "")[:200],
                        "category": row["category"],
                        "status": row["status"],
                        "company": row["company"],
                        "contact_name": row["contact_name"],
                        "created_at": row["created_at"],
                        "entity_ids": [],
                        "_score": 0.0,
                    })
        except Exception:
            pass
        return {"items": results, "total": len(results), "query": query}

    def index_intelligence(self, db_path):
        return 0  # Noop — no-op engine does not index

    def get_status(self):
        return True  # Noop engine is always "available"
