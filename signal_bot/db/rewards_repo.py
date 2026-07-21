"""لایه دسترسی به جدول rewards — دفتر پاداش مستقل از prize_pool (بند ۱۲)."""
from datetime import datetime

from signal_bot.db.connection import get_db


def insert_reward(user_id, amount, reason, granted_by):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO rewards (user_id, amount, reason, granted_by, granted_at, status)
                 VALUES (?,?,?,?,?,'recorded')""",
              (user_id, amount, reason, granted_by, datetime.now().isoformat()))
    reward_id = c.lastrowid
    conn.commit()
    conn.close()
    return reward_id


def mark_paid(reward_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE rewards SET status='paid' WHERE id=?", (reward_id,))
    conn.commit()
    conn.close()


def list_for_user(user_id, limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, amount, reason, granted_at, status
                 FROM rewards WHERE user_id=? ORDER BY granted_at DESC LIMIT ?""",
              (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_total_for_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM rewards WHERE user_id=?", (user_id,))
    total = c.fetchone()[0] or 0
    conn.close()
    return total


def list_recent_all(limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT r.id, u.full_name, r.amount, r.reason, r.granted_at, r.status
                 FROM rewards r JOIN users u ON r.user_id=u.user_id
                 ORDER BY r.granted_at DESC LIMIT ?""", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows
