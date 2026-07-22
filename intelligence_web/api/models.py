import sqlite3
import os
import json
from datetime import datetime, timedelta
import base64
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'intelligence.db')
OPENCLAW_CONFIG_PATH = '/home/uantek/.openclaw/openclaw.json'

def get_agent_names():
    """从 openclaw.json 读取所有 Agent 的 id:name 映射"""
    try:
        with open(OPENCLAW_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        agents = {}
        for agent in config.get('agents', {}).get('list', []):
            aid = agent.get('id', '')
            name = agent.get('name', aid)
            if aid and name:
                agents[aid] = name
        return agents
    except Exception:
        return {'main': '贾维斯'}

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intelligence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            opinion TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intelligence_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (intelligence_id) REFERENCES intelligence(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            role TEXT DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
    ''')
    
    # 创建默认管理员账号（密码: admin123）
    import hashlib
    now = datetime.now().isoformat()
    admin_hash = hashlib.sha256(b'admin123').hexdigest()
    cursor.execute(
        'INSERT OR IGNORE INTO users (username, password_hash, display_name, role, created_at) VALUES (?, ?, ?, ?, ?)',
        ('admin', admin_hash, '管理员', 'admin', now)
    )
    cursor.execute(
        'INSERT OR IGNORE INTO users (username, password_hash, display_name, role, created_at) VALUES (?, ?, ?, ?, ?)',
        ('yoo', admin_hash, 'Yoo', 'user', now)
    )
    
    conn.commit()
    conn.close()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def create_intelligence(title, content, category=''):
    with get_db() as conn:
        # 去重：检查是否已有相同标题（不区分大小写）的情报
        title_norm = title.strip().lower()
        existing_row = conn.execute(
            "SELECT id FROM intelligence WHERE LOWER(TRIM(title)) = ?",
            (title_norm,)
        ).fetchone()
        if existing_row:
            return None  # 重复情报，返回None
    
        with get_db() as conn2:
            cursor = conn2.cursor()
            now = datetime.now().isoformat()
            try:
                cursor.execute(
                    'INSERT INTO intelligence (title, content, category, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                    (title.strip(), content, category or '', 'pending', now, now)
                )
                conn2.commit()
            except Exception:
                return None  # UNIQUE约束冲突兜底
            return cursor.lastrowid

def get_intelligences(filters=None):
    with get_db() as conn:
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
            if filters.get('date_from'):
                sql += ' AND created_at >= ?'
                params.append(filters['date_from'])
            if filters.get('date_to'):
                sql += ' AND created_at <= ?'
                params.append(filters['date_to'])
        
        sql += ' ORDER BY created_at DESC'
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

def get_intelligence_by_id(id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM intelligence WHERE id = ?', (id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_intelligence_status(id, status, opinion=''):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            'UPDATE intelligence SET status = ?, opinion = ?, updated_at = ? WHERE id = ?',
            (status, opinion, now, id)
        )
        conn.commit()
        return cursor.rowcount > 0

def add_history(intelligence_id, action, detail='', file_location=''):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO history (intelligence_id, action, detail, file_location, created_at) VALUES (?, ?, ?, ?, ?)',
            (intelligence_id, action, detail, file_location, now)
        )
        conn.commit()
        return cursor.lastrowid

def get_history(intelligence_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM history WHERE intelligence_id = ? ORDER BY created_at DESC',
            (intelligence_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_categories():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT category FROM intelligence WHERE category != ""')
        return [row[0] for row in cursor.fetchall()]

def get_commands():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM commands ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

def add_command(content):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('INSERT INTO commands (content, created_at) VALUES (?, ?)', (content, now))
        conn.commit()
        return cursor.lastrowid

def delete_command(id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM commands WHERE id = ?', (id,))
        conn.commit()
        return cursor.rowcount > 0

def generate_command_file():
    commands = get_commands()
    cmd_texts = [c['content'] for c in commands]
    content = "# Scout Configuration\n\n## Search Keywords\n"
    for i, text in enumerate(cmd_texts, 1):
        content += f"- {text}\n"
    content += "\n## Target Sources\n"
    content += "- Reddit (r/manufacturing, r/automation, r/industrialautomation)\n"
    content += "- Tech Blogs (TechCrunch, Wired - focus on industrial tech sections)\n"
    content += "- Industry News Sites (Manufacturing Tomorrow, Smart Manufacturing)\n"
    content += "- Specialized Engineering Forums\n"
    return content

def reorder_command(id, position):
    """将单个命令移动到指定位置（通过修改 created_at 实现排序）"""
    with get_db() as conn:
        cursor = conn.cursor()
        # 获取所有命令按当前顺序
        cursor.execute('SELECT id, created_at FROM commands ORDER BY created_at DESC')
        rows = cursor.fetchall()
        if position >= len(rows):
            return False
        # 找到目标项在旧列表中的位置
        old_pos = None
        for i, row in enumerate(rows):
            if row[0] == id:
                old_pos = i
                break
        if old_pos is None:
            return False
        # 交换 created_at：把目标项的 created_at 和新位置的 created_at 互换
        target_created_at = rows[position][1]
        old_created_at = rows[old_pos][1]
        cursor.execute('UPDATE commands SET created_at = ? WHERE id = ?', (target_created_at, id))
        if old_pos != position:
            cursor.execute('UPDATE commands SET created_at = ? WHERE id = ?', (old_created_at, rows[position][0]))
        conn.commit()
        return True


def add_comment(intelligence_id, agent_name, content, agent_id='',):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO comments (intelligence_id, agent_name, agent_id, content, created_at) VALUES (?, ?, ?, ?, ?)',
            (intelligence_id, agent_name, agent_id, content, now)
        )
        conn.commit()
        return cursor.lastrowid

def get_comments(intelligence_id, limit=20):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM comments WHERE intelligence_id = ? ORDER BY created_at DESC LIMIT ?',
            (intelligence_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def add_summary(intelligence_id, content):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        # 删除旧总结，插入新总结
        cursor.execute('DELETE FROM summaries WHERE intelligence_id = ?', (intelligence_id,))
        cursor.execute(
            'INSERT INTO summaries (intelligence_id, content, updated_at) VALUES (?, ?, ?)',
            (intelligence_id, content, now)
        )
        conn.commit()
        return cursor.lastrowid

def get_summary(intelligence_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM summaries WHERE intelligence_id = ? ORDER BY updated_at DESC LIMIT 1',
            (intelligence_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

def get_approved_intelligences():
    """获取所有标记为 approved 的情报，用于分发给子 Agent 评论（active 状态不评论）"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM intelligence WHERE status = \'approved\' ORDER BY updated_at DESC'
        )
        return [dict(row) for row in cursor.fetchall()]

def reorder_commands_batch(ids):
    """批量重新排序：按 ids 列表的顺序更新所有命令的 created_at
    get_commands 用 ORDER BY created_at DESC，所以第一个元素需要最大的时间戳（最新）
    """
    with get_db() as conn:
        cursor = conn.cursor()
        now_base = datetime.now()
        # ids[0] 排最前 → 给它最大的时间戳（offset=0, 最新）；ids[-1] 排最后 → 给它最小的时间戳（offset=len-1, 最旧）
        for i, cmd_id in enumerate(ids):
            new_created_at = (now_base - timedelta(seconds=i)).isoformat()
            cursor.execute('UPDATE commands SET created_at = ? WHERE id = ?', (new_created_at, cmd_id))
        conn.commit()
        return True


# =============================================================================
# System Settings (key-value store)
# =============================================================================

def _encrypt(value):
    """Base64 + XOR simple obfuscation (not real encryption, just avoids plaintext in DB)"""
    key = os.environ.get('SETTINGS_ENCRYPT_KEY', 'sys-settings-key-2026')
    encoded = value.encode('utf-8')
    encrypted = bytes([b ^ ord(key[i % len(key)]) for b in encoded])
    return base64.b64encode(encrypted).decode('ascii')


def _decrypt(encrypted_b64):
    key = os.environ.get('SETTINGS_ENCRYPT_KEY', 'sys-settings-key-2026')
    encrypted = base64.b64decode(encrypted_b64)
    decrypted = bytes([b ^ ord(key[i % len(key)]) for b in encrypted])
    return decrypted.decode('utf-8')


def get_setting(key, decrypt_sensitive=False):
    """Get a single setting value by key"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        if not row:
            return None
        value = row['value']
        if decrypt_sensitive:
            try:
                value = _decrypt(value)
            except Exception:
                pass  # Fall back to raw value
        return value


def set_setting(key, value, category=''):
    """Set or update a setting value"""
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO settings (key, value, category, updated_at) VALUES (?, ?, ?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value, category=excluded.category, updated_at=excluded.updated_at',
            (key, value, category, now)
        )
        conn.commit()
        return True


def get_all_settings(category=None):
    """Get all settings. Returns {key: value} dict."""
    with get_db() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute('SELECT key, value FROM settings WHERE category = ? ORDER BY key', (category,))
        else:
            cursor.execute('SELECT key, value FROM settings ORDER BY key')
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            result[row['key']] = row['value']
        return result
