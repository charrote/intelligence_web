"""DataSource (数据源) CRUD operations.

Also provides the interface expected by mcp_server/server.py (dslib).
Each domain has its own database, so all functions take a db_path.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager

from core.credentials import encrypt_secret, decrypt_secret

# 允许的鉴权类型。none = 不鉴权（现状）；其余见 core/scheduler/auth_fetch.py
AUTH_TYPES = {'none', 'basic', 'bearer', 'cookie', 'form_login'}


def normalize_auth_type(value) -> str:
    """Normalize an auth_type value; unknown/empty values become 'none'."""
    v = str(value or 'none').strip().lower()
    return v if v in AUTH_TYPES else 'none'


@contextmanager
def _get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── Create ──────────────────────────────────────────────────────────────────

def create_source(db_path, name, type_, url, schedule='daily', status='active',
                 indicators='', description='', auth_type='none', username='',
                 password=''):
    """Create a new datasource. Returns the id.

    auth_type: none/basic/bearer/cookie/form_login。
    username/password 仅在 auth_type != 'none' 且 password 非空时入库
    （password 经 Fernet 加密后存入 credential 列）。
    未配置 CREDENTIALS_ENCRYPT_KEY 时保存密码会抛
    core.credentials.CredentialKeyMissingError（API 层转 400）。
    """
    now = datetime.now().isoformat()
    indicator_str = ','.join(indicators) if isinstance(indicators, list) else indicators
    auth = normalize_auth_type(auth_type)
    username = str(username or '').strip()
    credential = ''
    if auth != 'none' and password:
        credential = encrypt_secret(str(password))
    with _get_db(db_path) as conn:
        cursor = conn.execute(
            '''INSERT INTO datasources (name, type, url, schedule, status,
                indicators, last_crawled_at, auth_type, username, credential,
                created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)''',
            (name.strip(), type_, url.strip(), schedule, status,
              indicator_str, auth, username, credential, now, now)
        )
        conn.commit()
        return cursor.lastrowid


# ── Read ────────────────────────────────────────────────────────────────────

def list_sources(db_path, filters=None):
    """List datasources with optional filters.

    Supports: type, status, search (name/url)
    """
    sql = 'SELECT * FROM datasources WHERE 1=1'
    params = []

    if filters:
        if filters.get('type'):
            sql += ' AND type = ?'
            params.append(filters['type'])
        if filters.get('status'):
            sql += ' AND status = ?'
            params.append(filters['status'])
        if filters.get('search'):
            sql += ' AND (name LIKE ? OR url LIKE ?)'
            params.extend([f'%{filters["search"]}%', f'%{filters["search"]}%'])

    sql += ' ORDER BY created_at DESC'

    with _get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_source_by_id(db_path, source_id):
    """Get a single datasource."""
    with _get_db(db_path) as conn:
        row = conn.execute('SELECT * FROM datasources WHERE id = ?', (source_id,)).fetchone()
        return dict(row) if row else None


# ── Update ──────────────────────────────────────────────────────────────────

def update_source(db_path, source_id, data):
    """Update datasource fields. Returns updated source or None.

    鉴权字段语义：
    - auth_type: 归一化后写入；改为 'none' 时同时清空 username 与 credential。
    - username: 仅当 key 存在且非 None 时写入（空串 = 清空）；缺省 = 保持不变。
    - password: 明文，仅当非空时加密写入 credential；缺省/空 = 保持原凭证不变。
    """
    allowed = {'name', 'type', 'url', 'schedule', 'status', 'indicators', 'description'}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if 'auth_type' in data and data['auth_type'] is not None:
        updates['auth_type'] = normalize_auth_type(data['auth_type'])
    if 'username' in data and data['username'] is not None:
        updates['username'] = str(data['username']).strip()
    if data.get('password'):
        updates['credential'] = encrypt_secret(str(data['password']))
    if updates.get('auth_type') == 'none':
        updates['username'] = ''
        updates['credential'] = ''
    if not updates:
        return get_source_by_id(db_path, source_id)

    now = datetime.now().isoformat()
    # Handle indicators: convert list → comma-separated string
    if 'indicators' in updates and isinstance(updates['indicators'], list):
        updates['indicators'] = ','.join(updates['indicators'])

    set_parts = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [now, source_id]

    with _get_db(db_path) as conn:
        conn.execute(
            f'UPDATE datasources SET {set_parts}, updated_at = ? WHERE id = ?',
            values
        )
        conn.commit()

    return get_source_by_id(db_path, source_id)


def toggle_source_status(db_path, source_id, enabled):
    """Toggle a datasource between active/inactive."""
    new_status = 'active' if enabled else 'inactive'
    now = datetime.now().isoformat()
    with _get_db(db_path) as conn:
        conn.execute(
            'UPDATE datasources SET status = ?, updated_at = ? WHERE id = ?',
            (new_status, now, source_id)
        )
        conn.commit()
    return get_source_by_id(db_path, source_id)


def update_source_last_crawled(db_path, source_id):
    """Record last_crawled_at timestamp."""
    now = datetime.now().isoformat()
    with _get_db(db_path) as conn:
        conn.execute(
            'UPDATE datasources SET last_crawled_at = ?, updated_at = ? WHERE id = ?',
            (now, now, source_id)
        )
        conn.commit()


# ── Delete ──────────────────────────────────────────────────────────────────

def delete_source(db_path, source_id):
    """Delete a datasource (junction table rows cleaned up by CASCADE)."""
    with _get_db(db_path) as conn:
        conn.execute('DELETE FROM datasources WHERE id = ?', (source_id,))
        conn.commit()


# ── Auth / credential helpers ───────────────────────────────────────────────

def mask_source(source):
    """Return a copy safe for API/MCP output.

    Never exposes the credential (Fernet token) and never exposes the raw
    username; instead reports auth_type + has_credentials + masked username.
    """
    if source is None:
        return None
    out = dict(source)
    auth = normalize_auth_type(out.get('auth_type'))
    username = str(out.get('username') or '')
    out['auth_type'] = auth
    out['has_credentials'] = bool(out.get('credential')) and auth != 'none'
    if username and auth != 'none':
        out['username'] = username[0] + '***'
    else:
        out['username'] = ''
    out.pop('credential', None)
    return out


def build_auth_map(datasources):
    """Build {hostname: auth} for datasources that carry usable credentials.

    auth = {'auth_type', 'username', 'password' (plaintext), 'login_url'}.
    Skips sources with auth_type='none', empty/undecryptable credential,
    or a url without a hostname. Used by the search cycle to match result
    URLs against credentialed sources.
    """
    from urllib.parse import urlparse

    auth_map = {}
    for ds in datasources or []:
        auth = normalize_auth_type(ds.get('auth_type'))
        if auth == 'none':
            continue
        password = decrypt_secret(ds.get('credential') or '')
        if not password:
            continue
        url = str(ds.get('url') or '').strip()
        host = urlparse(url).hostname or ''
        if not host:
            continue
        auth_map[host] = {
            'auth_type': auth,
            'username': str(ds.get('username') or ''),
            'password': password,
            'login_url': url,
        }
    return auth_map


def match_auth(url, auth_map):
    """Match a URL against the auth map (exact host, then subdomain relation).

    Returns the auth dict or None. Subdomain fallback covers e.g. a source
    configured as 'example.com' and results on 'www.example.com'.
    """
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ''
    if not host:
        return None
    if host in auth_map:
        return auth_map[host]
    for ds_host, auth in auth_map.items():
        if host.endswith('.' + ds_host) or ds_host.endswith('.' + host):
            return auth
    return None


# ── Link / Unlink ──────────────────────────────────────────────────────────

def link_datasource_to_project(db_path, project_id, datasource_id):
    """Link a datasource to a project."""
    with _get_db(db_path) as conn:
        conn.execute(
            'INSERT OR IGNORE INTO project_datasources (project_id, datasource_id) VALUES (?, ?)',
            (project_id, datasource_id)
        )
        conn.commit()


def unlink_datasource_from_project(db_path, project_id, datasource_id):
    """Remove a datasource link from a project."""
    with _get_db(db_path) as conn:
        conn.execute(
            'DELETE FROM project_datasources WHERE project_id = ? AND datasource_id = ?',
            (project_id, datasource_id)
        )
        conn.commit()


# ── Get datasources for a project ──────────────────────────────────────────

def get_datasources_for_project(db_path, project_id):
    """Get all datasources linked to a project."""
    with _get_db(db_path) as conn:
        rows = conn.execute(
            '''SELECT d.* FROM datasources d
               INNER JOIN project_datasources pd ON pd.datasource_id = d.id
               WHERE pd.project_id = ?
               ORDER BY d.name''',
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_project_ids_for_datasource(db_path, datasource_id):
    """Get all projects linked to a datasource."""
    with _get_db(db_path) as conn:
        rows = conn.execute(
            'SELECT project_id FROM project_datasources WHERE datasource_id = ?',
            (datasource_id,)
        ).fetchall()
        return [r['project_id'] for r in rows]


# ── MCP compatibility layer ────────────────────────────────────────────────

def get_crawl_logs(db_path, source_id, limit=50):
    """Return recent crawl log entries for a datasource (placeholder).

    In a real implementation this would read from a crawl_logs table.
    """
    return []


def list_sources_for_domain(db_path, domain_slug):
    """Return datasources, optionally filtered by domain.

    Currently all datasources are shared; domain filtering reserved for future.
    """
    return list_sources(db_path)