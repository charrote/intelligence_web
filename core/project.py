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


def _truthy(v) -> bool:
    """宽松的真值判定：bool / 0-1 / 'true'/'1'/'yes' 等。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(v)


# 采集频率单位（与 search_cycle 的 _FREQ_HOURS / UI 下拉保持一致）
_FREQS = ('hourly', 'daily', 'weekly', 'monthly', 'oneshot')

# 各频率单位下"数值"（interval）的上限：防呆，超出报可读错误。
# 语义：每 N <单位>；oneshot 无周期语义，固定 1（不参与校验）。
_FREQ_INTERVAL_MAX = {
    'hourly': 24,    # 每 N 小时，N ≤ 24
    'daily': 31,     # 每 N 天，N ≤ 31
    'weekly': 4,     # 每 N 周，N ≤ 4
    'monthly': 12,   # 每 N 个月，N ≤ 12
}


def normalize_frequency(frequency, interval):
    """校验并归一（频率单位, 数值）。

    - frequency 必须是 _FREQS 之一，否则 ValueError。
    - oneshot → 数值固定 1（无数值）。
    - interval 缺省/None → 1；须为正整数；超出该单位上限 → ValueError。
    返回 (frequency, int)。
    """
    if frequency not in _FREQS:
        raise ValueError(f"频率必须是 {_FREQS} 之一，收到 {frequency!r}")
    if frequency == 'oneshot':
        return frequency, 1
    if interval is None:
        interval = 1
    try:
        n = int(interval)
    except (TypeError, ValueError):
        raise ValueError(f"频率数值必须为正整数，收到 {interval!r}")
    if n < 1:
        raise ValueError(f"频率数值必须 ≥ 1，收到 {n}")
    max_n = _FREQ_INTERVAL_MAX.get(frequency)
    if max_n is not None and n > max_n:
        raise ValueError(f"频率数值超出范围：{frequency} 最大 {max_n}，收到 {n}")
    return frequency, n


# ── Create ──────────────────────────────────────────────────────────────────

def create_project(db_path, name, target_type, target_name, scope='',
                    frequency='weekly', instruction='', datasource_ids=None,
                    source_only=False, frequency_interval=1):
    """Create a new project. Optionally link existing datasource IDs.

    last_search_at 初始化为当前时间：oneshot 项目因此永远不会进入自动调度
    （到期判定只认 >=1h 的频率）；其余项目从创建时刻起算第一个完整周期。

    source_only=1 时情报只从关联数据源采集（不做开放式搜索）；
    默认 0 沿用现有开放式搜索逻辑。

    frequency + frequency_interval：单位 + 数值（如 hourly + 3 = 每 3 小时）。
    数值缺省 1（等价于"每小时/每日…"）；非法数值抛 ValueError（可读提示）。
    """
    freq, interval = normalize_frequency(frequency, frequency_interval)
    now = datetime.now().isoformat()
    source_only = 1 if _truthy(source_only) else 0
    with _get_db(db_path) as conn:
        cursor = conn.execute(
            '''INSERT INTO projects (name, target_type, target_name, scope,
               frequency, frequency_interval, status, instruction, last_search_at,
               source_only, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)''',
            (name.strip(), target_type, target_name.strip(), scope.strip(),
             freq, interval, instruction or '', now, source_only, now, now)
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
    allowed = {'name', 'target_type', 'target_name', 'scope', 'frequency',
               'frequency_interval', 'instruction', 'source_only'}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    # source_only 归一到 0/1（兼容 bool / 0/1 / "true" 等入参）
    if 'source_only' in updates:
        updates['source_only'] = 1 if _truthy(updates['source_only']) else 0

    # 频率（单位 + 数值）联合校验：改单位时按新单位校验数值；只改数值时
    # 按库里当前单位校验。非法数值/超上限 → ValueError（可读提示）。
    if 'frequency' in updates or 'frequency_interval' in updates:
        cur = get_project_by_id(db_path, project_id)
        cur_freq = (cur.get('frequency') if cur else None) or 'weekly'
        cur_interval = (cur.get('frequency_interval') if cur else None) or 1
        freq, interval = normalize_frequency(
            updates.get('frequency', cur_freq),
            updates.get('frequency_interval', cur_interval),
        )
        updates['frequency'] = freq
        updates['frequency_interval'] = interval

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