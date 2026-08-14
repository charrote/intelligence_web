"""Shared database utilities for intelligence domains."""

import sqlite3
import os
import shutil
import glob
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
    """Initialize the domain database with the correct schema.

    Backs up the database before schema changes and verifies data integrity after.
    """
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    data_dir = os.path.dirname(db_path)

    # Ensure data directory exists and is writable
    try:
        os.makedirs(data_dir, exist_ok=True)
        if not os.access(data_dir, os.W_OK):
            raise PermissionError(f"Data directory not writable: {data_dir}")
    except (OSError, PermissionError) as e:
        raise RuntimeError(f"Cannot initialize database: {e}")

    # Backup before init (skip if DB doesn't exist yet — first run)
    backup_path = _backup_db(db_path)
    pre_counts = None

    try:
        # Record pre-init counts; if DB doesn't exist yet (brand new), it's empty
        if os.path.exists(db_path):
            pre_counts = _record_counts(db_path)

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

        c.execute('''
            CREATE TABLE IF NOT EXISTS intel_extraction_rule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL DEFAULT 'research',
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                scope TEXT NOT NULL DEFAULT 'full',
                max_fields INTEGER NOT NULL DEFAULT 15,
                enabled INTEGER NOT NULL DEFAULT 1,
                built_in INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS intel_extraction_field (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                field_label TEXT NOT NULL,
                field_type TEXT NOT NULL,
                is_required INTEGER NOT NULL DEFAULT 0,
                default_value TEXT DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                help_text TEXT DEFAULT '',
                FOREIGN KEY (rule_id) REFERENCES intel_extraction_rule(id) ON DELETE CASCADE
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS intel_fact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intel_id INTEGER NOT NULL,
                rule_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                field_label TEXT DEFAULT '',
                value_text TEXT DEFAULT '',
                value_num REAL,
                value_type TEXT NOT NULL,
                entity_name TEXT DEFAULT '',
                time_period TEXT DEFAULT '',
                source_anchor TEXT DEFAULT '',
                confidence TEXT NOT NULL DEFAULT 'high',
                created_at TEXT NOT NULL,
                FOREIGN KEY (intel_id) REFERENCES intelligence(id) ON DELETE CASCADE
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS intel_aggregate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                rule_id INTEGER NOT NULL,
                group_by TEXT NOT NULL,
                metrics TEXT DEFAULT '[]',
                filters TEXT DEFAULT '[]',
                chart_config TEXT DEFAULT '[]',
                prompt_template TEXT NOT NULL,
                schedule_minutes INTEGER NOT NULL DEFAULT 1440,
                lookback_days INTEGER NOT NULL DEFAULT 30,
                enabled INTEGER NOT NULL DEFAULT 1,
                next_run TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                fail_count INTEGER NOT NULL DEFAULT 0,
                last_fail_time TEXT,
                last_success_time TEXT,
                built_in INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (rule_id) REFERENCES intel_extraction_rule(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS report_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                domain TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                aggregated_data TEXT,
                output_analysis TEXT,
                output_charts TEXT,
                output_summary TEXT,
                fact_count INTEGER,
                duration_sec INTEGER,
                error_msg TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES intel_aggregate(id) ON DELETE CASCADE
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS report_scheduler (
                id INTEGER PRIMARY KEY DEFAULT 1,
                scheduler_enabled INTEGER NOT NULL DEFAULT 1,
                extract_enabled INTEGER NOT NULL DEFAULT 1,
                report_enabled INTEGER NOT NULL DEFAULT 1,
                extract_interval_min INTEGER NOT NULL DEFAULT 10,
                report_interval_min INTEGER NOT NULL DEFAULT 5,
                last_extract_time TEXT,
                last_report_time TEXT,
                extract_success_today INTEGER NOT NULL DEFAULT 0,
                report_success_today INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        ''')

        # Indexes for intel_fact
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_intel ON intel_fact(intel_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_rule ON intel_fact(rule_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_field ON intel_fact(field_key)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_entity ON intel_fact(entity_name)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_time ON intel_fact(time_period)')

        conn.commit()

        # Migration: add extracted column to intelligence
        try:
            c.execute('ALTER TABLE intelligence ADD COLUMN extracted INTEGER DEFAULT 0')
        except Exception:
            pass  # column already exists

        # Note: Extraction rule/field/template seeding is handled by migrate_db,
        # not here, to avoid duplicate data and rule_id mismatches.

        # Seed report_scheduler initial record
        c.execute(
            'INSERT OR IGNORE INTO report_scheduler(id, scheduler_enabled, extract_enabled, report_enabled, extract_interval_min, report_interval_min, updated_at) VALUES (1, 1, 1, 1, 10, 5, datetime("now"))'
        )

        conn.commit()

        # Seed default admin user if no users exist
        row = c.execute('SELECT COUNT(*) FROM users').fetchone()
        if row[0] == 0:
            _seed_default_users(conn)

        # Migration: ensure all existing intelligence records are marked for extraction
        try:
            c.execute("UPDATE intelligence SET extracted = 0 WHERE extracted = 0 OR extracted IS NULL")
            conn.commit()
            print(f"[init_db] Backfill: marked intelligence records for extraction")
        except Exception as e:
            print(f"[init_db] Backfill warning: {e}")

        conn.commit()
        conn.close()

        # Verify data integrity after init
        post_counts = _record_counts(db_path)
        if pre_counts:
            lost = {t: pre_counts[t] - post_counts.get(t, 0) for t in pre_counts if pre_counts[t] != post_counts.get(t, -1)}
            lost_real = {k: v for k, v in lost.items() if v > 0}
            if lost_real:
                msg = f"[init_db] DATA LOSS DETECTED! Lost records in: {lost_real}. Attempting restore from backup..."
                print(msg)
                if _restore_backup(db_path, backup_path):
                    print(f"[init_db] Restored from backup: {backup_path}")
                else:
                    print(f"[init_db] FAILED to restore backup: {backup_path}")
                raise RuntimeError(msg)
            else:
                print(f"[init_db] data integrity OK")

    except Exception as e:
        print(f"[init_db] error: {e}")
        if backup_path and _restore_backup(db_path, backup_path):
            print(f"[init_db] restored from backup: {backup_path}")
        raise


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
        except Exception as e:
            print(f"[create_intelligence] ERROR inserting '{title}': {e}")
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
# User Management CRUD
# =============================================================================

ROLE_LABELS = {
    'admin': 'admin',
    'power_user': 'power_user',
    'user': 'viewer',
    'agent': 'agent',
}


def _role_to_label(role):
    """Map internal role name to frontend label."""
    return ROLE_LABELS.get(role, 'viewer')


def _role_to_id(role):
    """Map internal role name to frontend numeric role_id."""
    mapping = {'admin': 1, 'power_user': 2, 'user': 3, 'agent': 4}
    return mapping.get(role, 3)


def list_users(db_path, search=None, limit=100):
    """List users with optional search. Returns dict with 'items' and 'total'."""
    with get_db(db_path) as conn:
        sql = "SELECT id, username, display_name, role, enabled, domains, created_at, updated_at FROM users WHERE 1=1"
        params = []
        if search:
            sql += " AND (username LIKE ? OR display_name LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])
        sql += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        items = []
        for r in rows:
            u = dict(r)
            u['role_name'] = _role_to_label(u.get('role', 'user'))
            u['role_id'] = _role_to_id(u.get('role', 'user'))
            u['domains'] = u.get('domains') or ''
            if isinstance(u.get('domains'), str):
                u['domains'] = [d.strip() for d in u['domains'].split(',') if d.strip()] if u['domains'] else []
            else:
                u['domains'] = u['domains'] or []
            items.append(u)
        # Also get total count
        count_sql = "SELECT COUNT(*) as cnt FROM users WHERE 1=1"
        count_params = []
        if search:
            count_sql += " AND (username LIKE ? OR display_name LIKE ?)"
            count_params.extend([f'%{search}%', f'%{search}%'])
        total = conn.execute(count_sql, count_params).fetchone()['cnt']
        return {'items': items, 'total': total}


def get_user_by_id_full(db_path, user_id):
    """Get user by ID with full details (including salt for edit form). Returns user dict or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            'SELECT id, username, display_name, role, enabled, domains, created_at, updated_at FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()
        if row is None:
            return None
        u = dict(row)
        u['role_name'] = _role_to_label(u.get('role', 'user'))
        u['role_id'] = _role_to_id(u.get('role', 'user'))
        u['domains'] = u.get('domains') or ''
        if isinstance(u.get('domains'), str):
            u['domains'] = [d.strip() for d in u['domains'].split(',') if d.strip()] if u['domains'] else []
        else:
            u['domains'] = u['domains'] or []
        return u


def create_user(db_path, username, display_name, password, role='user', domains=None):
    """Create a new user. Returns the new user id or None on error."""
    now = datetime.now().isoformat()
    password_hash, salt = _hash_password(password)
    domains_str = ','.join(domains) if domains else ''
    with get_db(db_path) as conn:
        try:
            cursor = conn.execute(
                'INSERT INTO users (username, password_hash, salt, display_name, role, enabled, domains, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)',
                (username.strip(), password_hash, salt, display_name.strip(), role, domains_str, now, now)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"[create_user] ERROR: {e}")
            return None


def update_user(db_path, user_id, fields):
    """Update user fields. Supported: username, display_name, role, domains.
    Password is separate via update_user_password. Returns updated user dict or None.
    """
    allowed_fields = ['username', 'display_name', 'role', 'domains']
    updates = []
    params = []
    for field in allowed_fields:
        if field in fields and fields[field] is not None:
            updates.append(f'{field} = ?')
            params.append(fields[field])
    if not updates:
        return None
    params.append(user_id)
    with get_db(db_path) as conn:
        try:
            conn.execute(
                f'UPDATE users SET {", ".join(updates)}, updated_at = ? WHERE id = ?',
                params + [datetime.now().isoformat()]
            )
            conn.commit()
            return get_user_by_id_full(db_path, user_id)
        except Exception as e:
            print(f"[update_user] ERROR: {e}")
            return None


def update_user_password(db_path, user_id, password):
    """Update user password only."""
    now = datetime.now().isoformat()
    password_hash, salt = _hash_password(password)
    with get_db(db_path) as conn:
        try:
            conn.execute(
                'UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?',
                (password_hash, salt, now, user_id)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[update_user_password] ERROR: {e}")
            return False


def delete_user(db_path, user_id):
    """Delete a user (soft disable, set enabled=0). Returns True on success."""
    with get_db(db_path) as conn:
        try:
            now = datetime.now().isoformat()
            conn.execute(
                'UPDATE users SET enabled = 0, updated_at = ? WHERE id = ?',
                (now, user_id)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[delete_user] ERROR: {e}")
            return False


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


def delete_intelligence(db_path, intel_id):
    """Delete an intelligence record and all its related data.
    Returns True on success, False if not found.
    Child tables cleaned up: history, comments, summaries, intel_entity.
    """
    with get_db(db_path) as conn:
        # Verify record exists
        row = conn.execute('SELECT id FROM intelligence WHERE id = ?', (intel_id,)).fetchone()
        if not row:
            return False
        # Delete related records (no CASCADE on these tables)
        conn.execute('DELETE FROM history WHERE intelligence_id = ?', (intel_id,))
        conn.execute('DELETE FROM comments WHERE intelligence_id = ?', (intel_id,))
        conn.execute('DELETE FROM summaries WHERE intelligence_id = ?', (intel_id,))
        conn.execute('DELETE FROM intel_entity WHERE intelligence_id = ?', (intel_id,))
        conn.execute('DELETE FROM intelligence WHERE id = ?', (intel_id,))
        conn.commit()
        return True


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

# =============================================================================
# Database Backup & Safety — backup before migration, verify after
# =============================================================================


def _backup_db(db_path):
    """Create a timestamped backup of the database. Returns backup path or None."""
    if not os.path.exists(db_path):
        return None
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except OSError as e:
        print(f"[backup] WARNING: cannot create backup dir {backup_dir}: {e}")
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{os.path.basename(db_path)}_{ts}.bak"
    backup_path = os.path.join(backup_dir, backup_name)
    try:
        shutil.copy2(db_path, backup_path)
        # Verify backup is readable and non-empty
        if os.path.getsize(backup_path) == 0:
            raise OSError(f"Backup file is empty: {backup_path}")
        return backup_path
    except Exception:
        return None


def _restore_backup(db_path, backup_path):
    """Restore database from backup. Returns True on success."""
    if not backup_path or not os.path.exists(backup_path):
        print(f"[restore] backup file not found: {backup_path}")
        return False
    try:
        shutil.copy2(backup_path, db_path)
        if os.path.getsize(db_path) == 0:
            print(f"[restore] ERROR: restored file is empty: {db_path}")
            return False
        print(f"[restore] restored {db_path} from {backup_path}")
        return True
    except Exception as e:
        print(f"[restore] ERROR: {e}")
        return False


def _record_counts(db_path):
    """Get record counts for all tables. Returns dict of {table: count}.

    Raises FileNotFoundError if db_path does not exist (database was deleted).
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at {db_path} (deleted before migration?)")
    counts = {}
    try:
        with get_db(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for t in tables:
                name = t["name"]
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
                    counts[name] = count
                except Exception:
                    counts[name] = -1
    except Exception:
        raise
    return counts


def migrate_db(db_path):
    """Create the projects / datasources / project_datasources tables if missing.

    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS.
    Backs up the database before migration and verifies data integrity after.
    """
    # Step 1: Backup before migration
    backup_path = _backup_db(db_path)
    if backup_path and not os.path.exists(backup_path):
        backup_path = None

    # If we couldn't create a backup (DB was deleted), look for existing backup
    if not backup_path:
        backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        if os.path.isdir(backup_dir):
            bak_files = sorted([f for f in os.listdir(backup_dir)
                                if f.startswith(os.path.basename(db_path)) and f.endswith('.bak')])
            if bak_files:
                backup_path = os.path.join(backup_dir, bak_files[-1])

    try:
        # Check DB still exists (catches deletion between backup and migration)
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file was deleted before migration: {db_path}")

        # Record pre-migration counts INSIDE try — catches deletion before migration
        pre_counts = _record_counts(db_path)
        if pre_counts:
            print(f"[migrate_db] pre-migration counts: {pre_counts}")

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
                ('domains', 'TEXT DEFAULT ""'),
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

            # ── Layer 2/3/4: Extraction Rules + Facts + Aggregates ──
            # init_db no longer seeds these. migrate_db seeds on first run only.

            # Check if built-in rules have been seeded yet
            try:
                _rule_count = c.execute('SELECT COUNT(*) FROM intel_extraction_rule').fetchone()[0]
            except Exception:
                _rule_count = 0

            if _rule_count == 0:
                c.execute('''
                    CREATE TABLE IF NOT EXISTS intel_extraction_rule (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        domain TEXT NOT NULL DEFAULT 'research',
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        scope TEXT NOT NULL DEFAULT 'full',
                        max_fields INTEGER NOT NULL DEFAULT 15,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        built_in INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                ''')

                c.execute('''
                    CREATE TABLE IF NOT EXISTS intel_extraction_field (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_id INTEGER NOT NULL,
                        field_key TEXT NOT NULL,
                        field_label TEXT NOT NULL,
                        field_type TEXT NOT NULL,
                        is_required INTEGER NOT NULL DEFAULT 0,
                        default_value TEXT DEFAULT '',
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        help_text TEXT DEFAULT '',
                        FOREIGN KEY (rule_id) REFERENCES intel_extraction_rule(id) ON DELETE CASCADE
                    )
                ''')

                c.execute('''
                    CREATE TABLE IF NOT EXISTS intel_fact (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        intel_id INTEGER NOT NULL,
                        rule_id INTEGER NOT NULL,
                        field_key TEXT NOT NULL,
                        field_label TEXT DEFAULT '',
                        value_text TEXT DEFAULT '',
                        value_num REAL,
                        value_type TEXT NOT NULL,
                        entity_name TEXT DEFAULT '',
                        time_period TEXT DEFAULT '',
                        source_anchor TEXT DEFAULT '',
                        confidence TEXT NOT NULL DEFAULT 'high',
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (intel_id) REFERENCES intelligence(id) ON DELETE CASCADE
                    )
                ''')

                c.execute('''
                    CREATE TABLE IF NOT EXISTS intel_aggregate (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        domain TEXT NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        rule_id INTEGER NOT NULL,
                        group_by TEXT NOT NULL,
                        metrics TEXT DEFAULT '[]',
                        filters TEXT DEFAULT '[]',
                        chart_config TEXT DEFAULT '[]',
                        prompt_template TEXT NOT NULL,
                        schedule_minutes INTEGER NOT NULL DEFAULT 1440,
                        lookback_days INTEGER NOT NULL DEFAULT 30,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        next_run TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        fail_count INTEGER NOT NULL DEFAULT 0,
                        last_fail_time TEXT,
                        last_success_time TEXT,
                        built_in INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (rule_id) REFERENCES intel_extraction_rule(id)
                    )
                ''')

                # Indexes
                c.execute('CREATE INDEX IF NOT EXISTS idx_fact_intel ON intel_fact(intel_id)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_fact_rule ON intel_fact(rule_id)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_fact_field ON intel_fact(field_key)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_fact_entity ON intel_fact(entity_name)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_fact_time ON intel_fact(time_period)')

                # Seed built-in rules (only if table is empty)
                try:
                    rule_count = c.execute('SELECT COUNT(*) FROM intel_extraction_rule').fetchone()[0]
                except Exception:
                    rule_count = 0

                if rule_count == 0:
                    now = datetime.now().isoformat()

                    # Insert rules and capture their auto-generated IDs
                    c.execute(
                        'INSERT INTO intel_extraction_rule (domain, name, description, scope, max_fields, enabled, built_in, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        ('research', '厂商市场数据', '从情报中抽取厂商市场相关结构化数据', 'full', 15, 1, 1, now, now)
                    )
                    rule1_id = c.lastrowid

                    c.execute(
                        'INSERT INTO intel_extraction_rule (domain, name, description, scope, max_fields, enabled, built_in, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        ('sales', '竞争情报摘要', '从情报中抽取竞争对手动态和竞争情报', 'full+tables', 15, 1, 1, now, now)
                    )
                    rule2_id = c.lastrowid

                    # Seed fields for Rule 1: 厂商市场数据
                    rule1_fields = [
                        (rule1_id, 'company_name', '厂商名称', 'company', 1, '', 1, ''),
                        (rule1_id, 'market_share', '市场份额', 'pct', 0, '', 2, ''),
                        (rule1_id, 'market_size', '市场规模', 'currency', 0, '', 3, ''),
                        (rule1_id, 'currency', '币种', 'currency_code', 0, '', 4, ''),
                        (rule1_id, 'country', '国家/地区', 'location', 0, '', 5, ''),
                        (rule1_id, 'year', '年份', 'year', 0, '', 6, ''),
                        (rule1_id, 'growth_rate', '增长率', 'pct', 0, '', 7, ''),
                        (rule1_id, 'data_source', '数据来源', 'text', 0, '', 8, ''),
                    ]
                    for f in rule1_fields:
                        c.execute(
                            'INSERT INTO intel_extraction_field (rule_id, field_key, field_label, field_type, is_required, default_value, sort_order, help_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                            f
                        )

                    # Seed fields for Rule 2: 竞争情报摘要
                    rule2_fields = [
                        (rule2_id, 'competitor_name', '竞争对手名称', 'company', 1, '', 1, ''),
                        (rule2_id, 'action_type', '动作类型', 'text', 1, '', 2, ''),
                        (rule2_id, 'action_desc', '动作描述', 'text', 0, '', 3, ''),
                        (rule2_id, 'market_impact', '市场影响', 'text', 0, '', 4, ''),
                        (rule2_id, 'date', '事件日期', 'date', 0, '', 5, ''),
                        (rule2_id, 'source', '信息来源', 'text', 0, '', 6, ''),
                    ]
                    for f in rule2_fields:
                        c.execute(
                            'INSERT INTO intel_extraction_field (rule_id, field_key, field_label, field_type, is_required, default_value, sort_order, help_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                            f
                        )

                    # Seed built-in report templates
                    next_run = (datetime.now() + timedelta(minutes=10)).isoformat()
                    c.execute(
                        'INSERT INTO intel_aggregate (domain, name, description, rule_id, group_by, metrics, filters, chart_config, prompt_template, schedule_minutes, lookback_days, enabled, next_run, status, fail_count, built_in, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        ('research', '市场份额概览', '基于市场数据生成市场份额分析报告', rule1_id, 'entity_name', '[{"field_key":"market_share","agg":"avg","unit":"%"},{"field_key":"market_size","agg":"sum","unit":"USD"},{"field_key":"growth_rate","agg":"avg","unit":"%"}]', '[]', '[]',
                         '你是一个情报分析师。请基于以下已聚合的数据，撰写市场份额分析报告。\n\n【报告名称】{{ report_name }}\n【分析范围】{{ start_date }} 至 {{ end_date }}\n【参与分析的数据】{{ fact_count }} 条结构化事实\n\n=== 数据聚合结果 ===\n{{ aggregated_data }}\n\n=== 图表数据 ===\n{{ chart_data }}\n\n请按 JSON 格式返回：\n{\n  "analysis": "文字分析内容（不少于 200 字，描述市场份额分布、趋势变化、关键厂商对比...）",\n  "summary": "一段话总结市场份额核心发现..."\n}',
                         1440, 30, 1, next_run, 'active', 0, 0, now, now)
                    )
                    c.execute(
                        'INSERT INTO intel_aggregate (domain, name, description, rule_id, group_by, metrics, filters, chart_config, prompt_template, schedule_minutes, lookback_days, enabled, next_run, status, fail_count, built_in, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        ('sales', '竞争情报摘要', '基于竞争情报数据生成竞争态势摘要', rule2_id, 'entity_name', '[{"field_key":"competitor_name","agg":"count","unit":""}]', '[]', '[]',
                         '你是竞争情报分析员。请基于以下数据，撰写竞争情报摘要。\n\n【报告名称】{{ report_name }}\n【分析范围】{{ start_date }} 至 {{ end_date }}\n【参与分析的数据】{{ fact_count }} 条结构化事实\n\n=== 数据聚合结果 ===\n{{ aggregated_data }}\n\n=== 图表数据 ===\n{{ chart_data }}\n\n请按 JSON 格式返回：\n{\n  "analysis": "文字分析内容（不少于 200 字，描述竞争对手最新动态、市场影响、趋势判断...）",\n  "summary": "一段话总结竞争情报核心发现..."\n}',
                         1440, 30, 1, next_run, 'active', 0, 0, now, now)
                    )

                conn.commit()

        # Step 3: Verify data integrity after migration
        post_counts = _record_counts(db_path)
        if pre_counts:
            lost = {t: pre_counts[t] - post_counts.get(t, 0) for t in pre_counts if pre_counts[t] != post_counts.get(t, -1)}
            lost_real = {k: v for k, v in lost.items() if v > 0}
            if lost_real:
                msg = f"[migrate_db] DATA LOSS DETECTED! Lost records in: {lost_real}. Attempting restore from backup..."
                print(msg)
                if _restore_backup(db_path, backup_path):
                    print(f"[migrate_db] Restored from backup: {backup_path}")
                else:
                    print(f"[migrate_db] FAILED to restore backup: {backup_path}")
                raise RuntimeError(msg)
            else:
                print(f"[migrate_db] post-migration counts: {post_counts}")
                print("[migrate_db] data integrity OK")

    except Exception as e:
        # Step 4: On any error, try to restore backup
        print(f"[migrate_db] error: {e}")
        if backup_path:
            if _restore_backup(db_path, backup_path):
                print(f"[migrate_db] restored from backup: {backup_path}")
            else:
                print(f"[migrate_db] FAILED to restore backup: {backup_path}")
        raise