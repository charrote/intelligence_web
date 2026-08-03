"""Notification and subscription management."""

import sqlite3
from datetime import datetime
from contextlib import contextmanager


def init_notifications_table(db_path):
    """Create subscriptions and notifications tables if missing."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
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
    conn.commit()
    conn.close()


@contextmanager
def _get(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def list_subscriptions(db, user_id):
    """Return list of subscription dicts for a user."""
    if isinstance(db, str):
        with _get(db) as conn:
            return list_subscriptions(conn, user_id)
    rows = conn.execute(
        "SELECT id, user_id, domain, type, value, channel, enabled, created_at "
        "FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_subscription(db, user_id, domain, type_, value, channel="in_app"):
    """Create a new subscription.  Returns the id."""
    if isinstance(db, str):
        with _get(db) as conn:
            return create_subscription(conn, user_id, domain, type_, value, channel)
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO subscriptions (user_id, domain, type, value, channel, enabled, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
        (user_id, domain, type_, value, channel, now, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_notifications(db, user_id, limit=20, unread_only=False):
    """Return list of notification dicts for a user."""
    if isinstance(db, str):
        with _get(db) as conn:
            return list_notifications(conn, user_id, limit, unread_only)
    if unread_only:
        rows = conn.execute(
            "SELECT id, user_id, domain, title, content, is_read, created_at "
            "FROM notifications WHERE user_id = ? AND is_read = 0 "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, user_id, domain, title, content, is_read, created_at "
            "FROM notifications WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def count_unread(db, user_id):
    """Return count of unread notifications for a user."""
    if isinstance(db, str):
        with _get(db) as conn:
            return count_unread(conn, user_id)
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()
    return row["cnt"] if row else 0


def mark_notification_read(db, notification_id):
    """Mark a notification as read."""
    if isinstance(db, str):
        with _get(db) as conn:
            return mark_notification_read(conn, notification_id)
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ?",
        (notification_id,),
    )
    conn.commit()


def mark_all_notifications_read(db, user_id):
    """Mark all notifications for a user as read."""
    if isinstance(db, str):
        with _get(db) as conn:
            return mark_all_notifications_read(conn, user_id)
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
