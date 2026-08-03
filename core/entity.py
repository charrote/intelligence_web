"""Entity management — entities (companies, organizations, people) and their
linking to intelligence records."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime


def init_entities_table(db_path):
    """Create the entities and intel_entity link tables if missing."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT '',
            entity_type TEXT DEFAULT 'company',
            aliases TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(name, domain)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS intel_entity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intelligence_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            relevance TEXT DEFAULT 'primary',
            created_at TEXT NOT NULL,
            FOREIGN KEY (intelligence_id) REFERENCES intelligence(id) ON DELETE CASCADE,
            FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            UNIQUE(intelligence_id, entity_id)
        )
    ''')
    conn.commit()
    conn.close()


@contextmanager
def _get(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def list_entities(db, domain=None, type_=None):
    """Return list of entity dicts.  db is a sqlite3.Connection or path string."""
    if isinstance(db, str):
        with _get(db) as conn:
            return list_entities(conn, domain, type_)

    q = "SELECT id, name, domain, entity_type, aliases, description FROM entities WHERE 1=1"
    params = []
    if domain:
        q += " AND domain = ?"
        params.append(domain)
    if type_:
        q += " AND entity_type = ?"
        params.append(type_)
    q += " ORDER BY name"
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_entities_for_intel(db, intel_id):
    """Return entities linked to a given intelligence id."""
    if isinstance(db, str):
        with _get(db) as conn:
            return get_entities_for_intel(conn, intel_id)

    q = """
        SELECT e.id, e.name, e.domain, e.entity_type, e.aliases, e.description
        FROM entities e
        JOIN intel_entity ie ON ie.entity_id = e.id
        WHERE ie.intelligence_id = ?
        ORDER BY e.name
    """
    rows = conn.execute(q, (intel_id,)).fetchall()
    return [dict(r) for r in rows]


def get_intel_for_entity(db, entity_id, limit=20):
    """Return intelligence records linked to a given entity."""
    if isinstance(db, str):
        with _get(db) as conn:
            return get_intel_for_entity(conn, entity_id, limit)

    q = """
        SELECT i.id, i.title, i.status, i.category, ie.relevance
        FROM intelligence i
        JOIN intel_entity ie ON ie.intelligence_id = i.id
        WHERE ie.entity_id = ?
        ORDER BY i.created_at DESC
        LIMIT ?
    """
    rows = conn.execute(q, (entity_id, limit)).fetchall()
    return [dict(r) for r in rows]


def link_entity(db, intel_id, entity_id, relevance="primary"):
    """Link an entity to an intelligence record.  Returns True on success."""
    if isinstance(db, str):
        with _get(db) as conn:
            return link_entity(conn, intel_id, entity_id, relevance)

    now = datetime.now().isoformat()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO intel_entity (intelligence_id, entity_id, relevance, created_at) "
            "VALUES (?, ?, ?, ?)",
            (intel_id, entity_id, relevance, now),
        )
        conn.execute(
            "UPDATE entities SET updated_at = ? WHERE id = ?",
            (now, entity_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def ensure_entity(db, name, domain, entity_type="company", aliases="", description=""):
    """Create or return existing entity.  Returns the entity id."""
    if isinstance(db, str):
        with _get(db) as conn:
            return ensure_entity(conn, name, domain, entity_type, aliases, description)

    now = datetime.now().isoformat()
    cur = conn.execute(
        "SELECT id FROM entities WHERE name = ? AND domain = ?",
        (name, domain),
    )
    row = cur.fetchone()
    if row:
        return row["id"]

    conn.execute(
        "INSERT INTO entities (name, domain, entity_type, aliases, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, domain, entity_type, aliases, description, now, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_entity_by_name(db, name, domain=None):
    """Find an entity by name (case-insensitive).  Returns dict or None."""
    if isinstance(db, str):
        with _get(db) as conn:
            return get_entity_by_name(conn, name, domain)

    q = "SELECT id, name, domain, entity_type, aliases, description FROM entities WHERE LOWER(name) = LOWER(?)"
    params = [name]
    if domain:
        q += " AND domain = ?"
        params.append(domain)
    row = conn.execute(q, params).fetchone()
    return dict(row) if row else None

