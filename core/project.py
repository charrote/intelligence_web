"""Project (采集项目) CRUD operations.

Each domain has its own database, so all functions take a db_path.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager
from core.db import get_intelligence_count_for_project


@contextmanager
def _get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── Create ──────────────────────────────────────────────────────────────────

def create_project(db_path, name, target_type, target_name, scope='',
                   frequency='weekly', instruction='', datasource_ids=None):
    """Create a new project. Optionally link existing datasource IDs.

    last_search_at 初始化为当前时间：oneshot 项目因此永远不会进入自动调度
    （到期判定只认 >=1h 的频率）；其余项目从创建时刻起算第一个完整周期。
    """
    now = datetime.now().isoformat()
    with _get_db(db_path) as conn:
        cursor = conn.execute(
            '''INSERT INTO projects (name, target_type, target_name, scope,
               frequency, status, instruction, last_search_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)''',
            (name.strip(), target_type, target_name.strip(), scope.strip(),
             frequency, instruction or '', now, now, now)
        )
        project_id = cursor.lastrowid

        # Link datasources
        if datasource_ids:
            for ds_id in datasource_ids:
                conn.execute(
                    'INSERT OR IGNORE INTO project_datasources (project_id, datasource_id) VALUES (?, ?)',
                    (project_id, ds_id)
                )

        conn.commit()
        return project_id


# ── Read ────────────────────────────────────────────────────────────────────

def get_projects(db_path, filters=None):
    """List projects with optional filters.

    Returns dicts with extra 'datasource_count' and 'total_intel' fields.
    """
    sql = '''
        SELECT p.*,
               (SELECT COUNT(*) FROM project_datasources pd WHERE pd.project_id = p.id) AS datasource_count,
               (SELECT COUNT(*) FROM intelligence i WHERE i.project_id = p.id) AS total_intel
        FROM projects p
        WHERE 1=1
    '''
    params = []

    if filters:
        if filters.get('status'):
            sql += ' AND p.status = ?'
            params.append(filters['status'])

    sql += ' ORDER BY p.created_at DESC'

    with _get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_project_by_id(db_path, project_id):
    """Get a single project with its linked datasources and intel count."""
    sql = '''
        SELECT p.*,
               (SELECT COUNT(*) FROM project_datasources pd WHERE pd.project_id = p.id) AS datasource_count,
               (SELECT COUNT(*) FROM intelligence i WHERE i.project_id = p.id) AS total_intel
        FROM projects p WHERE p.id = ?
    '''
    with _get_db(db_path) as conn:
        row = conn.execute(sql, (project_id,)).fetchone()
        if not row:
            return None
        result = dict(row)

        # Fetch linked datasources
        ds_rows = conn.execute(
            '''SELECT d.* FROM datasources d
               INNER JOIN project_datasources pd ON pd.datasource_id = d.id
               WHERE pd.project_id = ?''',
            (project_id,)
        ).fetchall()
        result['datasources'] = [dict(r) for r in ds_rows]
        return result


# ── Update ──────────────────────────────────────────────────────────────────

def update_project(db_path, project_id, data):
    """Update project fields. Returns updated project or None."""
    allowed = {'name', 'target_type', 'target_name', 'scope', 'frequency', 'instruction'}
    _FREQS = ('hourly', 'daily', 'weekly', 'monthly', 'oneshot')
    if data.get('frequency') is not None and data.get('frequency') not in _FREQS:
        raise ValueError(f"frequency 必须是 {_FREQS} 之一，收到 {data.get('frequency')!r}")
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        return get_project_by_id(db_path, project_id)

    now = datetime.now().isoformat()
    set_parts = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [now, project_id]

    with _get_db(db_path) as conn:
        conn.execute(
            f'UPDATE projects SET {set_parts}, updated_at = ? WHERE id = ?',
            values
        )
        conn.commit()

    return get_project_by_id(db_path, project_id)


def touch_project_last_search(db_path, project_id, ts=None):
    """记录项目最近一次自动/手动采集时间（到期判定用）。"""
    now = (ts or datetime.now().isoformat())
    with _get_db(db_path) as conn:
        conn.execute(
            'UPDATE projects SET last_search_at = ? WHERE id = ?',
            (now, project_id)
        )
        conn.commit()


def toggle_project_status(db_path, project_id, enabled):
    """Toggle a project between active/paused."""
    new_status = 'active' if enabled else 'paused'
    now = datetime.now().isoformat()
    with _get_db(db_path) as conn:
        conn.execute(
            'UPDATE projects SET status = ?, updated_at = ? WHERE id = ?',
            (new_status, now, project_id)
        )
        conn.commit()
    return get_project_by_id(db_path, project_id)


def set_project_datasources(db_path, project_id, datasource_ids):
    """Replace all datasource links for a project."""
    with _get_db(db_path) as conn:
        conn.execute('DELETE FROM project_datasources WHERE project_id = ?', (project_id,))
        if datasource_ids:
            for ds_id in datasource_ids:
                conn.execute(
                    'INSERT OR IGNORE INTO project_datasources (project_id, datasource_id) VALUES (?, ?)',
                    (project_id, ds_id)
                )
        conn.commit()
    return get_project_by_id(db_path, project_id)


# ── Delete ──────────────────────────────────────────────────────────────────

def delete_project(db_path, project_id):
    """Delete a project and its datasource links."""
    with _get_db(db_path) as conn:
        conn.execute('DELETE FROM project_datasources WHERE project_id = ?', (project_id,))
        conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
        conn.commit()


# ── Statistics ──────────────────────────────────────────────────────────────

def get_project_count(db_path):
    """Return total project count."""
    with _get_db(db_path) as conn:
        row = conn.execute('SELECT COUNT(*) AS c FROM projects').fetchone()
        return row['c']


def get_active_project_count(db_path):
    """Return active project count."""
    with _get_db(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM projects WHERE status = 'active'").fetchone()
        return row['c']