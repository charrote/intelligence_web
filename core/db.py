"""Shared database utilities for intelligence domains."""

import sqlite3
import os
import base64
from datetime import datetime
from contextlib import contextmanager


def get_db_path(project_root, db_filename):
    """Return the path to the domain's SQLite database."""
    data_dir = os.path.join(project_root, "data")
    return os.path.join(data_dir, db_filename)


def init_db(project_root, spec):
    """Initialize the domain database with the correct schema."""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    status_names = [s[1] for s in spec["statuses"]]
    extra_defs = " ".join(f"{c[0]} {c[1]}" for c in spec["extra_columns"])

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    default_status = status_names[0] if status_names else "pending"
    create_table_sql = f'''
        CREATE TABLE IF NOT EXISTS intelligence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '',
            status TEXT DEFAULT '{default_status}',
            opinion TEXT DEFAULT '',
            contact_name TEXT DEFAULT '',
            company TEXT DEFAULT '',
            deal_value REAL DEFAULT 0,
            industry TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    '''
    c.execute(create_table_sql)

    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intelligence_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            file_location TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (intelligence_id) REFERENCES intelligence(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intelligence_id INTEGER NOT NULL,
            agent_name TEXT NOT NULL,
            agent_id TEXT DEFAULT '',
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (intelligence_id) REFERENCES intelligence(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intelligence_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (intelligence_id) REFERENCES intelligence(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()


@contextmanager
def get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_intelligence(db_path, title, content, category, contact_name, metadata=None):
    """Create a new intelligence record. Returns the id or None on duplicate."""
    with get_db(db_path) as conn:
        title_norm = title.strip().lower()
        existing = conn.execute(
            "SELECT id FROM intelligence WHERE LOWER(TRIM(title)) = ?",
            (title_norm,)
        ).fetchone()
        if existing:
            return None

        company = metadata.get("company", "") if metadata else ""
        deal_value = metadata.get("deal_value", 0) if metadata else 0
        industry = metadata.get("industry", "") if metadata else ""
        now = datetime.now().isoformat()
        try:
            cursor = conn.execute(
                'INSERT INTO intelligence (title, content, category, status, opinion, contact_name, company, deal_value, industry, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (title.strip(), content, category or '', 'pending', '', contact_name or '', company, deal_value, industry, now, now)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception:
            return None


# =============================================================================
# Commands
# =============================================================================

def get_commands(db_path):
    with get_db(db_path) as conn:
        rows = conn.execute('SELECT * FROM commands ORDER BY created_at DESC').fetchall()
        return [dict(r) for r in rows]


def add_command_content(db_path, content):
    """Add a command entry. Returns the id."""
    now = datetime.now().isoformat()
    with get_db(db_path) as conn:
        cursor = conn.execute(
            'INSERT INTO commands (content, created_at) VALUES (?, ?)',
            (content.strip(), now)
        )
        conn.commit()
        return cursor.lastrowid


def get_intelligences(db_path, filters=None):
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        sql = 'SELECT * FROM intelligence WHERE 1=1'
        params = []

        if filters:
            if filters.get('search'):
                sql += ' AND (title LIKE ? OR content LIKE ?)'
                params.extend([f'%{filters["search"]}%', f'%{filters["search"]}%'])
            if filters.get('status'):
                sql += ' AND status = ?'
                params.append(filters['status'])
            if filters.get('category'):
                sql += ' AND category = ?'
                params.append(filters['category'])
            if filters.get('company'):
                sql += ' AND company LIKE ?'
                params.append(f'%{filters["company"]}%')
            if filters.get('date_from'):
                sql += ' AND created_at >= ?'
                params.append(filters['date_from'])
            if filters.get('date_to'):
                sql += ' AND created_at <= ?'
                params.append(filters['date_to'])

        sql += ' ORDER BY created_at DESC'
        if filters and filters.get('limit'):
            sql += ' LIMIT ?'
            params.append(int(filters['limit']))
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_intelligence_by_id(db_path, intel_id):
    with get_db(db_path) as conn:
        row = conn.execute('SELECT * FROM intelligence WHERE id = ?', (intel_id,)).fetchone()
        return dict(row) if row else None


def update_intelligence_status(db_path, id, status, opinion=''):
    with get_db(db_path) as conn:
        now = datetime.now().isoformat()
        conn.execute(
            'UPDATE intelligence SET status = ?, opinion = ?, updated_at = ? WHERE id = ?',
            (status, opinion, now, id)
        )
        conn.commit()


def add_history(db_path, intelligence_id, action, detail='', file_location=''):
    with get_db(db_path) as conn:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            'INSERT INTO history (intelligence_id, action, detail, file_location, created_at) VALUES (?, ?, ?, ?, ?)',
            (intelligence_id, action, detail, file_location, now)
        )
        conn.commit()
        return cursor.lastrowid


def get_history(db_path, intelligence_id):
    with get_db(db_path) as conn:
        rows = conn.execute(
            'SELECT * FROM history WHERE intelligence_id = ? ORDER BY created_at DESC',
            (intelligence_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_categories(db_path):
    with get_db(db_path) as conn:
        rows = conn.execute('SELECT DISTINCT category FROM intelligence WHERE category != ""').fetchall()
        return [r[0] for r in rows]


def add_comment(db_path, intelligence_id, agent_name, content, agent_id=''):
    with get_db(db_path) as conn:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            'INSERT INTO comments (intelligence_id, agent_name, agent_id, content, created_at) VALUES (?, ?, ?, ?, ?)',
            (intelligence_id, agent_name, agent_id, content, now)
        )
        conn.commit()
        return cursor.lastrowid


def get_comments(db_path, intelligence_id, limit=20):
    with get_db(db_path) as conn:
        rows = conn.execute(
            'SELECT * FROM comments WHERE intelligence_id = ? ORDER BY created_at DESC LIMIT ?',
            (intelligence_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def add_summary(db_path, intelligence_id, content):
    with get_db(db_path) as conn:
        now = datetime.now().isoformat()
        conn.execute('DELETE FROM summaries WHERE intelligence_id = ?', (intelligence_id,))
        cursor = conn.execute(
            'INSERT INTO summaries (intelligence_id, content, updated_at) VALUES (?, ?, ?)',
            (intelligence_id, content, now)
        )
        conn.commit()
        return cursor.lastrowid


def get_summary(db_path, intelligence_id):
    with get_db(db_path) as conn:
        row = conn.execute(
            'SELECT * FROM summaries WHERE intelligence_id = ? ORDER BY updated_at DESC LIMIT 1',
            (intelligence_id,)
        ).fetchone()
        return dict(row) if row else None


def get_dashboard_stats(db_path):
    """Get summary statistics for the dashboard."""
    with get_db(db_path) as conn:
        total = conn.execute('SELECT COUNT(*) FROM intelligence').fetchone()[0]
        by_status = conn.execute(
            'SELECT status, COUNT(*) FROM intelligence GROUP BY status'
        ).fetchall()
        status_dict = {row[0]: row[1] for row in by_status}
        by_category = conn.execute(
            'SELECT category, COUNT(*) FROM intelligence WHERE category != "" GROUP BY category'
        ).fetchall()
        category_dict = {row[0]: row[1] for row in by_category}
        return {
            "total": total,
            "by_status": status_dict,
            "by_category": category_dict,
        }


# =============================================================================
# System Settings (key-value store, shared across domains)
# =============================================================================

_SENSITIVE_KEYS = {'model.api_key', 'mcp.agent_key', 'system.jwt_secret'}


def _encrypt_settings(value):
    """Simple obfuscation for API keys in settings."""
    key = os.environ.get('SETTINGS_ENCRYPT_KEY', 'sys-settings-key-2026')
    encoded = value.encode('utf-8')
    encrypted = bytes([b ^ ord(key[i % len(key)]) for b in encoded])
    return base64.b64encode(encrypted).decode('ascii')


def get_setting(db_path, key):
    """Get a single setting value by key."""
    with get_db(db_path) as conn:
        row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else None


def set_setting(db_path, key, value, category=''):
    """Set or update a setting value."""
    now = datetime.now().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            'INSERT INTO settings (key, value, category, updated_at) VALUES (?, ?, ?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value, category=excluded.category, updated_at=excluded.updated_at',
            (key, value, category, now)
        )
        conn.commit()


def get_all_settings(db_path, category=None):
    """Get all settings, optionally filtered by category."""
    with get_db(db_path) as conn:
        if category:
            rows = conn.execute(
                'SELECT key, value FROM settings WHERE category = ? ORDER BY key', (category,)
            ).fetchall()
        else:
            rows = conn.execute('SELECT key, value FROM settings ORDER BY key').fetchall()
        result = {}
        for row in rows:
            result[row['key']] = row['value']
        return result


# =============================================================================
# Database Migration — new tables for projects & datasources
# =============================================================================

def migrate_db(db_path):
    """Create the projects / datasources / project_datasources tables if missing.

    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS.
    """
    with get_db(db_path) as conn:
        c = conn.cursor()

        # Projects table
        c.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT '',
                target_name TEXT NOT NULL DEFAULT '',
                scope TEXT DEFAULT '',
                frequency TEXT NOT NULL DEFAULT 'weekly',
                status TEXT NOT NULL DEFAULT 'active',
                instruction TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # Datasources table
        c.execute('''
            CREATE TABLE IF NOT EXISTS datasources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'website',
                url TEXT NOT NULL DEFAULT '',
                schedule TEXT NOT NULL DEFAULT 'daily',
                status TEXT NOT NULL DEFAULT 'active',
                indicators TEXT DEFAULT '',
                last_crawled_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # Target Types table
        c.execute('''
            CREATE TABLE IF NOT EXISTS target_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                description TEXT DEFAULT '',
                color TEXT DEFAULT '#3b4f8c',
                icon TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # Project-Datasource junction table
        c.execute('''
            CREATE TABLE IF NOT EXISTS project_datasources (
                project_id INTEGER NOT NULL,
                datasource_id INTEGER NOT NULL,
                PRIMARY KEY (project_id, datasource_id),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (datasource_id) REFERENCES datasources(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()