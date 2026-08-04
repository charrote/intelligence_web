"""Shared database utilities for intelligence domains."""

import sqlite3
import os
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
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
            project_id INTEGER,
            source_url TEXT DEFAULT '',
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

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            role TEXT NOT NULL DEFAULT 'user',
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    conn.commit()

    # Seed default admin user if no users exist
    row = c.execute('SELECT COUNT(*) FROM users').fetchone()
    if row[0] == 0:
        _seed_default_users(conn)

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


def create_intelligence(db_path, title, content, category, contact_name, metadata=None, project_id=None):
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
        source_url = metadata.get("source_url", "") if metadata else ""
        now = datetime.now().isoformat()
        try:
            cursor = conn.execute(
                'INSERT INTO intelligence (title, content, category, status, opinion, contact_name, company, deal_value, industry, project_id, source_url, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (title.strip(), content, category or '', 'pending', '', contact_name or '', company, deal_value, industry, project_id, source_url, now, now)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception:
            return None


# =============================================================================
# Authentication
# =============================================================================

def _hash_password(password, salt=None):
    """Hash a password with a salt using SHA-256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((salt + password).encode('utf-8'))
    return hash_obj.hexdigest(), salt


def _seed_default_users(conn):
    """Seed default admin user."""
    now = datetime.now().isoformat()
    password_hash, salt = _hash_password('admin123')
    conn.execute(
        'INSERT INTO users (username, password_hash, salt, display_name, role, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        ('admin', password_hash, salt, '管理员', 'admin', 1, now, now)
    )
    conn.execute(
        'INSERT INTO users (username, password_hash, salt, display_name, role, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        ('user', _hash_password('user123')[0], _hash_password('user123')[1], '普通用户', 'user', 1, now, now)
    )


def authenticate_user(db_path, username, password):
    """Verify username and password. Returns user dict or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            'SELECT * FROM users WHERE username = ? AND enabled = 1',
            (username,)
        ).fetchone()
        if row is None:
            return None
        user = dict(row)
        hash_obj = hashlib.sha256((user['salt'] + password).encode('utf-8'))
        if hash_obj.hexdigest() != user['password_hash']:
            return None
        return {
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'],
            'role': user['role'],
        }


def get_user_by_id(db_path, user_id):
    """Get user by ID. Returns user dict or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            'SELECT id, username, display_name, role FROM users WHERE id = ? AND enabled = 1',
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


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
        sql = "SELECT intelligence.*, "
        sql += "(SELECT COUNT(*) FROM comments WHERE comments.intelligence_id = intelligence.id) AS comment_count "
        sql += "FROM intelligence WHERE 1=1"
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
            if filters.get('project_id'):
                sql += ' AND project_id = ?'
                params.append(int(filters['project_id']))

        sql += ' ORDER BY created_at DESC'
        if filters and filters.get('limit'):
            sql += ' LIMIT ?'
            params.append(int(filters['limit']))
            if filters.get('offset'):
                sql += ' OFFSET ?'
                params.append(int(filters['offset']))
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_intelligence_by_id(db_path, intel_id):
    with get_db(db_path) as conn:
        row = conn.execute('SELECT * FROM intelligence WHERE id = ?', (intel_id,)).fetchone()
        return dict(row) if row else None


def get_intelligence_by_project(db_path, project_id, limit=50):
    """Get intelligence records linked to a specific project."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        sql = "SELECT intelligence.*, "
        sql += "(SELECT COUNT(*) FROM comments WHERE comments.intelligence_id = intelligence.id) AS comment_count "
        sql += "FROM intelligence WHERE project_id = ?"
        params = [project_id]
        sql += ' ORDER BY created_at DESC'
        sql += ' LIMIT ?'
        params.append(int(limit))
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


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


def get_intelligence_count_for_project(db_path, project_id):
    """Return the count of intelligence records linked to a project."""
    with get_db(db_path) as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS c FROM intelligence WHERE project_id = ?',
            (project_id,)
        ).fetchone()
        return row['c'] if row else 0


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

        # Users table (with migration for existing DBs)
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user',
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        # Migration: add columns if missing (for DBs created before users table had full schema)
        for col, col_type in [
            ('display_name', 'TEXT DEFAULT ""'),
            ('role', 'TEXT DEFAULT "user"'),
            ('enabled', 'INTEGER DEFAULT 1'),
            ('salt', 'TEXT DEFAULT ""'),
            ('created_at', 'TEXT DEFAULT ""'),
            ('updated_at', 'TEXT DEFAULT ""'),
        ]:
            try:
                c.execute(f'ALTER TABLE users ADD COLUMN {col} {col_type}')
            except Exception:
                pass  # column already exists

        # Fix existing users that have empty salt (from old schema)
        rows = c.execute('SELECT id, username, password_hash, salt FROM users').fetchall()
        for row in rows:
            user = dict(row)
            if not user['salt']:
                # Re-hash the password with a proper salt
                # Use the existing password_hash as the password (since we can't reverse it)
                # Set a default password 'admin123' for admin, 'user123' for user
                default_pw = 'admin123' if user['username'] == 'admin' else 'user123'
                new_hash, new_salt = _hash_password(default_pw)
                now = datetime.now().isoformat()
                c.execute(
                    'UPDATE users SET password_hash=?, salt=?, updated_at=? WHERE id=?',
                    (new_hash, new_salt, now, user['id'])
                )

        # Migration: add entities table
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

        # Migration: add subscriptions table
        c.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT 'keyword',
                value TEXT NOT NULL,
                channel TEXT DEFAULT 'in_app',
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # Migration: add notifications table
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                content TEXT DEFAULT '',
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')

        # Fix NULL enabled values (from old migration that added column without default)
        c.execute("UPDATE users SET enabled=1 WHERE enabled IS NULL")

        # Migration: add project_id to intelligence table if missing
        try:
            c.execute('ALTER TABLE intelligence ADD COLUMN project_id INTEGER')
        except Exception:
            pass  # column already exists

        # Migration: add source_url to intelligence table if missing
        try:
            c.execute('ALTER TABLE intelligence ADD COLUMN source_url TEXT DEFAULT ""')
        except Exception:
            pass  # column already exists

        # Ensure default users exist
        now = datetime.now().isoformat()
        existing_users = {r['username'] for r in c.execute('SELECT username FROM users').fetchall()}
        if 'admin' not in existing_users:
            h, s = _hash_password('admin123')
            c.execute(
                'INSERT INTO users (username, password_hash, salt, display_name, role, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                ('admin', h, s, '管理员', 'admin', 1, now, now)
            )
        if 'user' not in existing_users:
            h, s = _hash_password('user123')
            c.execute(
                'INSERT INTO users (username, password_hash, salt, display_name, role, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                ('user', h, s, '普通用户', 'user', 1, now, now)
            )

        conn.commit()