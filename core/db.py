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
from core.seed_data import DEMOS as _RESEARCH_DEMOS


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


        c.execute('''
            CREATE TABLE IF NOT EXISTS ai_analysis_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                intent TEXT DEFAULT '',
                entity_type TEXT DEFAULT '',
                time_range INTEGER DEFAULT 30,
                group_by TEXT DEFAULT '',
                metrics_config TEXT DEFAULT '[]',
                filters_config TEXT DEFAULT '[]',
                chart_config TEXT DEFAULT '[]',
                llm_prompt TEXT DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft',
                source TEXT DEFAULT 'user_input',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS ai_analysis_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_id INTEGER DEFAULT NULL,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                error_msg TEXT DEFAULT '',
                result_markdown TEXT DEFAULT '',
                result_charts TEXT DEFAULT '[]',
                result_summary TEXT DEFAULT '',
                result_data TEXT DEFAULT '[]',
                lookback_days INTEGER DEFAULT 30,
                execution_time_ms INTEGER DEFAULT 0,
                start_time TEXT NOT NULL,
                end_time TEXT,
                created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # Indexes for intel_fact
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_intel ON intel_fact(intel_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_rule ON intel_fact(rule_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_field ON intel_fact(field_key)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_entity ON intel_fact(entity_name)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_fact_time ON intel_fact(time_period)')

        c.execute('CREATE INDEX IF NOT EXISTS idx_ai_config_domain ON ai_analysis_config(domain)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ai_config_status ON ai_analysis_config(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ai_config_enabled ON ai_analysis_config(enabled)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ai_run_config ON ai_analysis_run(config_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ai_run_domain ON ai_analysis_run(domain)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ai_run_status ON ai_analysis_run(status)')


        conn.commit()

        # Migration: add extracted column to intelligence
        try:
            c.execute('ALTER TABLE intelligence ADD COLUMN extracted INTEGER DEFAULT 0')
        except Exception:
            pass  # column already exists

        # Migration: intel_fact legacy (metric_*) → current (value_*)
        _migrate_intel_fact_schema(conn)

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


def _migrate_intel_fact_schema(conn):
    """Migrate intel_fact from legacy (metric_*) to current (value_*) schema.

    历史生产库的 intel_fact 仍是旧列（metric_name/metric_value/metric_unit/
    context），而抽取引擎与 sql_aggregator 全部使用新列（field_label/
    value_text/value_num/value_type）。init_db 的 CREATE TABLE IF NOT EXISTS
    对已存在的旧表不会迁移，导致抽取一直写不进 intel_fact。

    幂等：已在新 schema（含 field_label 列）时直接返回。
    旧列在所有代码路径中零引用（extraction + sql_aggregator 均用 value_*），
    且生产库 intel_fact 为空，故将旧表改名保留作安全备份，按当前 schema 重建。
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(intel_fact)")]
    if "field_label" in cols:
        return  # 已是当前 schema

    print("[init_db] Migrate intel_fact: legacy metric_* schema -> current value_* schema")
    conn.execute("ALTER TABLE intel_fact RENAME TO intel_fact_legacy")
    conn.execute("""
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
            FOREIGN KEY (intel_id) REFERENCES intelligence(id) ON DELETE CASCADE,
            FOREIGN KEY (rule_id) REFERENCES intel_extraction_rule(id) ON DELETE CASCADE
        )
    """)
    # 重建索引（rename 后旧索引仍指向 intel_fact_legacy，需为新表重建）
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_intel ON intel_fact(intel_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_rule ON intel_fact(rule_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_field ON intel_fact(field_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_entity ON intel_fact(entity_name)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_time ON intel_fact(time_period)')
    conn.commit()
    print("[init_db] intel_fact migrated (legacy table preserved as intel_fact_legacy)")


def _seed_research_demos(db_path, spec):
    """Seed demo intelligence records into an empty research-domain database.

    Runs only for the research domain (slug == 'intelligence_web') and only
    when the intelligence table is completely empty (first run on a fresh
    deployment). Uses create_intelligence so titles are deduped.
    Returns the number of records inserted.
    """
    if spec.get("slug") != "intelligence_web":
        return 0
    try:
        with get_db(db_path) as conn:
            n = conn.execute("SELECT COUNT(*) FROM intelligence").fetchone()[0]
    except Exception:
        return 0
    if n != 0:
        return 0
    inserted = 0
    for title, content, category, contact, metadata in _RESEARCH_DEMOS:
        if create_intelligence(db_path, title, content, category, contact, metadata):
            inserted += 1
    if inserted:
        print(f"[init_db] Seeded {inserted} demo intelligence records (research domain, empty db)")
    return inserted


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


def add_comment(db_path, intelligence_id, agent_name, content, agent_id='', user_id=None):
    """Add a comment to an intelligence record.

    Human comments set user_id (the commenter's user id); agent comments
    leave it NULL. agent_name holds the display name for both kinds.
    """
    with get_db(db_path) as conn:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            'INSERT INTO comments (intelligence_id, agent_name, agent_id, user_id, content, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (intelligence_id, agent_name, agent_id, user_id, content, now)
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

            # Migration: add user_id to comments table if missing (human comments)
            try:
                c.execute('ALTER TABLE comments ADD COLUMN user_id INTEGER')
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

                c.execute('CREATE INDEX IF NOT EXISTS idx_ai_config_domain ON ai_analysis_config(domain)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_ai_config_status ON ai_analysis_config(status)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_ai_config_enabled ON ai_analysis_config(enabled)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_ai_run_config ON ai_analysis_run(config_id)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_ai_run_domain ON ai_analysis_run(domain)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_ai_run_status ON ai_analysis_run(status)')


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

            # Always commit schema changes (DDL) even when the rule-seeding
            # block above is skipped on non-first runs. Without this, ALTER
            # TABLE statements issued outside the `if _rule_count == 0` block
            # would be rolled back when the connection closes (no commit).
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

# ──────────────────────────────────────────────
# AI Analysis Config CRUD
# ──────────────────────────────────────────────

def get_ai_analysis_configs(db_path, domain=None, enabled=None):
    """查询分析配置列表"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = "SELECT * FROM ai_analysis_config WHERE 1=1"
    params = []
    if domain:
        query += " AND domain = ?"
        params.append(domain)
    if enabled is not None:
        query += " AND enabled = ?"
        params.append(1 if enabled else 0)
    query += " ORDER BY sort_order ASC, updated_at DESC"
    c.execute(query, params)
    configs = [dict(r) for r in c.fetchall()]
    conn.close()
    return configs


def get_ai_analysis_config_by_id(db_path, config_id):
    """根据 ID 查询配置"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM ai_analysis_config WHERE id = ?", (config_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def save_ai_analysis_config(db_path, config_data):
    """保存分析配置（新增或更新）"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    if config_data.get("id"):
        # Update
        c.execute("""
            UPDATE ai_analysis_config SET
                domain = ?, name = ?, description = ?, intent = ?,
                entity_type = ?, time_range = ?, group_by = ?,
                metrics_config = ?, filters_config = ?, chart_config = ?,
                llm_prompt = ?, enabled = ?, status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            config_data["domain"], config_data["name"],
            config_data.get("description", ""),
            config_data.get("intent", ""),
            config_data.get("entity_type", ""),
            config_data.get("time_range", 30),
            config_data.get("group_by", ""),
            json.dumps(config_data.get("metrics_config", [])),
            json.dumps(config_data.get("filters_config", [])),
            json.dumps(config_data.get("chart_config", [])),
            config_data.get("llm_prompt", ""),
            config_data.get("enabled", 1),
            config_data.get("status", "active"),
            now, config_data["id"]
        ))
    else:
        # Insert
        c.execute("""
            INSERT INTO ai_analysis_config (
                domain, name, description, intent, entity_type, time_range,
                group_by, metrics_config, filters_config, chart_config,
                llm_prompt, enabled, status, source, sort_order,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config_data["domain"], config_data["name"],
            config_data.get("description", ""),
            config_data.get("intent", ""),
            config_data.get("entity_type", ""),
            config_data.get("time_range", 30),
            config_data.get("group_by", ""),
            json.dumps(config_data.get("metrics_config", [])),
            json.dumps(config_data.get("filters_config", [])),
            json.dumps(config_data.get("chart_config", [])),
            config_data.get("llm_prompt", ""),
            config_data.get("enabled", 1),
            config_data.get("status", "draft"),
            config_data.get("source", "user_input"),
            config_data.get("sort_order", 0),
            now, now
        ))
        config_data["id"] = c.lastrowid

    conn.commit()
    conn.close()
    return config_data["id"]


def delete_ai_analysis_config(db_path, config_id):
    """删除分析配置"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM ai_analysis_config WHERE id = ?", (config_id,))
    conn.commit()
    conn.close()
    return True


def enable_ai_analysis_config(db_path, config_id, enabled):
    """启用/停用分析配置"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("""
        UPDATE ai_analysis_config SET enabled = ?, status = ?, updated_at = ?
        WHERE id = ?
    """, (1 if enabled else 0, 'active' if enabled else 'inactive', now, config_id))
    conn.commit()
    conn.close()
    return True


# ──────────────────────────────────────────────
# AI Analysis Run CRUD
# ──────────────────────────────────────────────

def get_ai_analysis_runs(db_path, config_id=None, limit=20, offset=0):
    """查询报告执行记录"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = "SELECT id, config_id, domain, title, status, progress, error_msg, result_summary, start_time, end_time, execution_time_ms, created_at FROM ai_analysis_run WHERE 1=1"
    params = []
    if config_id:
        query += " AND config_id = ?"
        params.append(config_id)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    c.execute(query, params)
    runs = [dict(r) for r in c.fetchall()]
    conn.close()
    return runs


def get_ai_analysis_run_by_id(db_path, run_id):
    """根据 ID 查询报告执行记录"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM ai_analysis_run WHERE id = ?", (run_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def save_ai_analysis_run(db_path, run_data):
    """保存报告执行记录"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    if run_data.get("id"):
        # Update
        c.execute("""
            UPDATE ai_analysis_run SET
                status = ?, progress = ?, error_msg = ?,
                result_markdown = ?, result_charts = ?, result_summary = ?,
                result_data = ?, execution_time_ms = ?, end_time = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            run_data["status"], run_data.get("progress", 0),
            run_data.get("error_msg", ""),
            run_data.get("result_markdown", ""),
            json.dumps(run_data.get("result_charts", [])),
            run_data.get("result_summary", ""),
            json.dumps(run_data.get("result_data", [])),
            run_data.get("execution_time_ms", 0),
            now if run_data["status"] in ["completed", "failed"] else None,
            now, run_data["id"]
        ))
    else:
        # Insert
        c.execute("""
            INSERT INTO ai_analysis_run (
                config_id, domain, title, status, progress, error_msg,
                result_markdown, result_charts, result_summary, result_data,
                lookback_days, execution_time_ms, start_time, end_time,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data.get("config_id"), run_data["domain"], run_data["title"],
            run_data["status"], run_data.get("progress", 0),
            run_data.get("error_msg", ""),
            run_data.get("result_markdown", ""),
            json.dumps(run_data.get("result_charts", [])),
            run_data.get("result_summary", ""),
            json.dumps(run_data.get("result_data", [])),
            run_data.get("lookback_days", 30),
            run_data.get("execution_time_ms", 0),
            run_data["start_time"],
            datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') if run_data["status"] in ["completed", "failed"] else None,
            run_data.get("created_by", ""),
            now, now
        ))
        run_data["id"] = c.lastrowid

    conn.commit()
    conn.close()
    return run_data["id"]


def delete_ai_analysis_run(db_path, run_id):
    """删除报告执行记录"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM ai_analysis_run WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()
    return True


# ──────────────────────────────────────────────
# AI Config generation (NL → structured config)
# ──────────────────────────────────────────────

FIELD_TYPE_META = {
    "company": "公司/厂商名称",
    "pct": "百分比（如 35%）",
    "currency": "金额（如 1200万）",
    "currency_code": "货币代码（如 USD）",
    "location": "地点/国家/区域",
    "year": "年份",
    "number": "纯数字",
    "date": "日期",
    "text": "任意文本",
}

GROUP_BY_META = {
    "entity_name": "按实体名称（厂商/公司）",
    "time_period": "按时间周期",
    "value_text": "按抽取值",
    "value_type": "按字段类型",
}

CHART_TYPES = ["bar", "line", "pie"]


def generate_analysis_config(db_path, spec, intent, lookback_days=30):
    """
    Use lightweight LLM call to translate user's natural language into
    a structured config (extraction rule + report template).

    Returns:
        {"ok": True, "config": {...}} on success
        {"ok": False, "error": "..."} on failure
    """
    from core.scheduler.llm_client import call_llm, parse_json_from_response

    # 1. Query existing fields for context (so LLM knows what's already extracted)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT f.field_label, f.field_key, f.field_type
        FROM intel_extraction_field f
        JOIN intel_extraction_rule r ON f.rule_id = r.id
        WHERE r.enabled = 1
        LIMIT 30
    """)
    existing_fields = [dict(r) for r in c.fetchall()]
    conn.close()

    # Build field list for prompt
    existing_fields_str = ""
    if existing_fields:
        existing_fields_str = "已有字段：\n" + "\n".join(
            f"- {f['field_label']} (field_key={f['field_key']}, 类型={f['field_type']})"
            for f in existing_fields[:20]
        )
    else:
        existing_fields_str = "暂无已有字段。"

    # 2. Build prompt
    system_prompt = """你是一个配置生成器。用户用自然语言描述他想要的情报分析报告，你需要输出完整的配置 JSON。

约束：
1. field_key 必须英文小写下划线命名，唯一
2. field_type 从以下选择: company, pct, currency, currency_code, location, year, number, date, text
3. group_by 从以下选择: entity_name, time_period, value_text, value_type
4. chart type 从以下选择: bar, line, pie
5. 如果用户说的指标已有字段，直接复用（不新建）
6. 最多 5 个抽取字段
7. metrics 的 field 必须是抽取字段的 field_key
8. 只输出 JSON，不要任何解释文字

输出格式（严格 JSON）：
{
  "extraction_rule": {
    "name": "规则名称（中文，简短）",
    "description": "一句话描述",
    "fields": [
      {"field_key": "english_key", "field_label": "中文名称", "field_type": "pct", "is_required": true, "sort_order": 0}
    ]
  },
  "report_template": {
    "name": "报告名称（中文，简短）",
    "description": "一句话描述",
    "group_by": "entity_name",
    "metrics": [
      {"field": "field_key", "agg": "avg", "label": "中文标签", "unit": ""}
    ],
    "filters": [],
    "chart_config": [
      {"chart_type": "line", "title": "图表标题", "name_field": "entity_name", "value_field": "field_key"}
    ],
    "lookback_days": 30,
    "schedule_minutes": 1440
  }
}"""

    user_prompt = f"""用户想要的报告：{intent}
时间范围：{lookback_days} 天

{existing_fields_str}

请生成配置 JSON："""

    # 3. Call LLM (reasoning 模型需要足够 token 用于思考 + 输出)
    llm_result = call_llm(
        system_prompt, user_prompt,
        temperature=0.1, max_tokens=4000, timeout=90
    )

    if not llm_result.get("ok"):
        return {"ok": False, "error": llm_result.get("error", "LLM 调用失败")}

    # 空值防护：reasoning 模型可能在 token 耗尽时返回空 content
    raw = llm_result.get("raw")
    if not raw or not raw.strip():
        return {"ok": False, "error": "模型返回空内容（可能是 reasoning 模型 token 不足，请重试或调大 max_tokens）"}

    # 4. Parse JSON
    parsed, json_ok = parse_json_from_response(raw)
    if not json_ok or not parsed:
        return {"ok": False, "error": f"LLM 返回格式异常: {llm_result['raw'][:200]}"}

    # 5. Validate and normalize
    config = _normalize_config(parsed, lookback_days)
    if config.get("error"):
        return {"ok": False, "error": config["error"]}

    return {"ok": True, "config": config}


def _normalize_config(raw, lookback_days):
    """Validate and normalize LLM output."""
    # Check required top-level keys
    if "extraction_rule" not in raw or "report_template" not in raw:
        return {"error": "配置缺少 extraction_rule 或 report_template"}

    rule = raw["extraction_rule"]
    template = raw["report_template"]

    # Validate fields
    valid_types = set(FIELD_TYPE_META.keys())
    fields = []
    seen_keys = set()
    for f in rule.get("fields", []):
        key = f.get("field_key", "")
        ftype = f.get("field_type", "text")
        if not key:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if ftype not in valid_types:
            ftype = "text"
        fields.append({
            "field_key": key,
            "field_label": f.get("field_label", key),
            "field_type": ftype,
            "is_required": bool(f.get("is_required", False)),
            "sort_order": len(fields),
        })

    if not fields:
        return {"error": "未生成任何抽取字段"}

    # Validate group_by
    valid_groups = set(GROUP_BY_META.keys())
    group_by = template.get("group_by", "entity_name")
    if group_by not in valid_groups:
        group_by = "entity_name"

    # Validate metrics
    valid_keys = seen_keys
    metrics = []
    for m in template.get("metrics", []):
        field = m.get("field", "")
        if field not in valid_keys:
            continue
        agg = m.get("agg", "avg")
        if agg not in ("avg", "sum", "max", "min", "count"):
            agg = "avg"
        metrics.append({
            "field": field,
            "agg": agg,
            "label": m.get("label", field),
            "unit": m.get("unit", ""),
        })

    # Validate charts
    valid_chart_types = set(CHART_TYPES)
    charts = []
    for ch in template.get("chart_config", []):
        ctype = ch.get("chart_type", "bar")
        if ctype not in valid_chart_types:
            ctype = "bar"
        charts.append({
            "chart_type": ctype,
            "title": ch.get("title", ""),
            "name_field": ch.get("name_field", "entity_name"),
            "value_field": ch.get("value_field", ""),
        })

    # Validate lookback
    lb = int(template.get("lookback_days", lookback_days) or lookback_days)
    if lb not in (7, 14, 30, 60, 90):
        lb = lookback_days

    # Validate schedule
    sched = int(template.get("schedule_minutes", 1440) or 1440)
    if sched < 60:
        sched = 1440

    return {
        "extraction_rule": {
            "name": rule.get("name", "未命名规则"),
            "domain": rule.get("domain", "research"),
            "description": rule.get("description", ""),
            "scope": "full",
            "max_fields": max(5, len(fields)),
            "enabled": True,
            "fields": fields,
        },
        "report_template": {
            "name": template.get("name", "未命名报告"),
            "domain": template.get("domain", "research"),
            "description": template.get("description", ""),
            "group_by": group_by,
            "metrics": metrics,
            "filters": template.get("filters", []),
            "chart_config": charts,
            "lookback_days": lb,
            "schedule_minutes": sched,
            "enabled": True,
        },
    }


# ──────────────────────────────────────────────
# AI Analysis execution engine
# ──────────────────────────────────────────────

def run_ai_analysis(db_path, spec, intent, lookback_days=30):
    """执行 AI 分析"""
    from core.scheduler.llm_client import call_llm, parse_json_from_response

    start_time = datetime.utcnow()

    # 1. Query intelligence data
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    c.execute("""
        SELECT id, title, content, company, category, status,
               contact_name, deal_value, industry, source_url, created_at
        FROM intelligence
        WHERE created_at >= ?
        ORDER BY created_at DESC
    """, (cutoff,))
    intel_list = [dict(r) for r in c.fetchall()]
    conn.close()

    if not intel_list:
        return {
            "success": False,
            "error": "该时间范围内没有情报数据",
            "data_count": 0
        }

    # 2. Build LLM prompt for intent parsing + analysis
    system_prompt = """你是一个数据分析助手。你的任务是根据用户的自然语言需求，从情报数据中提取和分析信息，生成结构化的分析报告。

你需要：
1. 理解用户的分析意图
2. 从情报数据中提取相关数据
3. 生成 Markdown 格式的分析报告
4. 如果数据适合可视化，提供图表配置（JSON 格式）
5. 提供一段简短的摘要

请严格按以下 JSON 格式返回：
{
  "intent": "你理解的用户意图",
  "data_count": 提取到的数据条数,
  "markdown": "Markdown 格式的分析报告",
  "summary": "一段话总结核心发现",
  "charts": [
    {
      "title": "图表标题",
      "type": "bar|line|pie",
      "data": {
        "categories": ["分类名1", "分类名2"],
        "values": [数值1, 数值2]
      }
    }
  ],
  "entity_type": "推断的实体类型: company|market|tech|deal|investment|region"
}"""

    # Build user prompt from intelligence data
    intel_preview = []
    for intel in intel_list[:30]:  # Limit to 30 for token budget
        preview = {
            "title": intel.get("title", ""),
            "company": intel.get("company", ""),
            "category": intel.get("category", ""),
            "content_short": intel.get("content", "")[:200],
            "date": intel.get("created_at", "")[:10]
        }
        if intel.get("deal_value"):
            preview["deal_value"] = intel["deal_value"]
        intel_preview.append(preview)

    user_prompt = f"""用户想分析：{intent}

请从以下 {len(intel_list)} 条情报数据中分析：
时间范围：过去 {lookback_days} 天

"""
    for i, intel in enumerate(intel_preview):
        user_prompt += f"--- 情报 {i+1} ---\n"
        user_prompt += f"标题: {intel['title']}\n"
        if intel.get('company'):
            user_prompt += f"公司: {intel['company']}\n"
        if intel.get('category'):
            user_prompt += f"分类: {intel['category']}\n"
        user_prompt += f"内容: {intel['content_short']}\n"
        user_prompt += f"日期: {intel['date']}\n"

    # 3. Call LLM
    llm_result = call_llm(system_prompt, user_prompt)

    # 4. Parse LLM response
    try:
        parsed = parse_json_from_response(llm_result)
    except Exception:
        parsed = {
            "intent": intent,
            "data_count": len(intel_list),
            "markdown": llm_result,
            "summary": "分析完成",
            "charts": [],
            "entity_type": ""
        }

    end_time = datetime.utcnow()
    execution_ms = int((end_time - start_time).total_seconds() * 1000)

    # 5. Save run record
    run_id = save_ai_analysis_run(db_path, {
        "config_id": None,
        "domain": spec.get("slug", "research"),
        "title": intent[:100],
        "status": "completed",
        "result_markdown": parsed.get("markdown", ""),
        "result_charts": parsed.get("charts", []),
        "result_summary": parsed.get("summary", ""),
        "result_data": intel_list,
        "lookback_days": lookback_days,
        "execution_time_ms": execution_ms,
        "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S')
    })

    return {
        "success": True,
        "run_id": run_id,
        "data_count": len(intel_list),
        "execution_time_ms": execution_ms,
        "result_markdown": parsed.get("markdown", ""),
        "result_charts": parsed.get("charts", []),
        "result_summary": parsed.get("summary", "")
    }

