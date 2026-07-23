"""Target Types CRUD operations.

Provides CRUD for target types used in project creation.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager


@contextmanager
def _get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_target_type(db_path, slug, label, description='', color='#3b4f8c', icon='', sort_order=0, enabled=True):
    """Create a new target type. Returns the id."""
    now = datetime.now().isoformat()
    with _get_db(db_path) as conn:
        cursor = conn.execute(
            '''INSERT INTO target_types (slug, label, description, color, icon, sort_order, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (slug, label, description, color, icon, sort_order, 1 if enabled else 0, now, now)
        )
        conn.commit()
        return cursor.lastrowid


def get_target_types(db_path, filters=None):
    """List target types with optional filters.
    
    Supports: enabled (filter by enabled status)
    """
    sql = 'SELECT * FROM target_types WHERE 1=1'
    params = []
    
    if filters:
        if filters.get('enabled') is not None:
            sql += ' AND enabled = ?'
            params.append(1 if filters['enabled'] else 0)
    
    sql += ' ORDER BY sort_order ASC, label ASC'
    
    with _get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_target_type_by_slug(db_path, slug):
    """Get a single target type by slug."""
    with _get_db(db_path) as conn:
        row = conn.execute('SELECT * FROM target_types WHERE slug = ?', (slug,)).fetchone()
        return dict(row) if row else None


def get_target_type_by_id(db_path, type_id):
    """Get a single target type by id."""
    with _get_db(db_path) as conn:
        row = conn.execute('SELECT * FROM target_types WHERE id = ?', (type_id,)).fetchone()
        return dict(row) if row else None


def update_target_type(db_path, type_id, data):
    """Update target type fields. Returns updated type or None."""
    allowed = {'slug', 'label', 'description', 'color', 'icon', 'sort_order', 'enabled'}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        return get_target_type_by_id(db_path, type_id)
    
    now = datetime.now().isoformat()
    
    # Handle enabled field
    if 'enabled' in updates:
        updates['enabled'] = 1 if updates['enabled'] else 0
    
    set_parts = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [now, type_id]
    
    with _get_db(db_path) as conn:
        conn.execute(
            f'UPDATE target_types SET {set_parts}, updated_at = ? WHERE id = ?',
            values
        )
        conn.commit()
    
    return get_target_type_by_id(db_path, type_id)


def toggle_target_type_enabled(db_path, type_id, enabled):
    """Toggle a target type between enabled/disabled."""
    new_enabled = 1 if enabled else 0
    now = datetime.now().isoformat()
    with _get_db(db_path) as conn:
        conn.execute(
            'UPDATE target_types SET enabled = ?, updated_at = ? WHERE id = ?',
            (new_enabled, now, type_id)
        )
        conn.commit()
    return get_target_type_by_id(db_path, type_id)


def delete_target_type(db_path, type_id):
    """Delete a target type."""
    with _get_db(db_path) as conn:
        conn.execute('DELETE FROM target_types WHERE id = ?', (type_id,))
        conn.commit()


def get_enabled_target_types(db_path):
    """Get all enabled target types."""
    return get_target_types(db_path, {'enabled': True})


def seed_target_types(db_path, types):
    """Seed target types into the database.
    
    types: list of dicts with keys: slug, label, description, color, icon, sort_order
    """
    now = datetime.now().isoformat()
    with _get_db(db_path) as conn:
        for tt in types:
            existing = conn.execute('SELECT id FROM target_types WHERE slug = ?', (tt['slug'],)).fetchone()
            if existing:
                # Update existing
                conn.execute('''UPDATE target_types SET label=?, description=?, color=?, icon=?, sort_order=?, enabled=1, updated_at=? WHERE slug=?''',
                             (tt['label'], tt.get('description', ''), tt.get('color', '#3b4f8c'), 
                              tt.get('icon', ''), tt.get('sort_order', 0), now, tt['slug']))
            else:
                # Insert new
                conn.execute('''INSERT INTO target_types (slug, label, description, color, icon, sort_order, enabled, created_at, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)''',
                             (tt['slug'], tt['label'], tt.get('description', ''), tt.get('color', '#3b4f8c'),
                              tt.get('icon', ''), tt.get('sort_order', 0), now, now))
        conn.commit()