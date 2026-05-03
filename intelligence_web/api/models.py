import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'intelligence.db')

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intelligence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
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
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO intelligence (title, content, category, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
            (title, content, category, 'pending', now, now)
        )
        conn.commit()
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT created_at FROM commands ORDER BY created_at DESC')
        rows = cursor.fetchall()
        if position < len(rows):
            cursor.execute('UPDATE commands SET created_at = ? WHERE id = ?', (rows[position][0], id))
        conn.commit()
        return cursor.rowcount > 0
