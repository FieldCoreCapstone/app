"""SQLite database helpers for FieldCore."""

import logging
import sqlite3
from contextlib import contextmanager

from backend import config

logger = logging.getLogger(__name__)


@contextmanager
def get_db(db_path=None):
    """Yield a SQLite connection with row_factory set to sqlite3.Row.

    Write operations must call conn.commit() explicitly within the context.
    On exception, uncommitted changes are rolled back automatically.
    """
    path = db_path or config.DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Node queries
# ---------------------------------------------------------------------------

def get_all_nodes(db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM nodes ORDER BY node_id").fetchall()
        return [dict(r) for r in rows]


def get_node(node_id, db_path=None):
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        return dict(row) if row else None


def create_node(node_id, name, x, y, installed=None, notes=None, db_path=None):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO nodes (node_id, name, x, y, installed, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (node_id, name, x, y, installed, notes),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Reading queries
# ---------------------------------------------------------------------------

def insert_reading(node_id, moisture, temperature, battery=None, signal_rssi=None, db_path=None):
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO readings (node_id, moisture, temperature, battery, signal_rssi)
               VALUES (?, ?, ?, ?, ?)""",
            (node_id, moisture, temperature, battery, signal_rssi),
        )
        conn.commit()
        return cursor.lastrowid


def get_latest_readings(db_path=None):
    """Return the most recent reading for every node, joined with node info."""
    sql = """
        SELECT n.node_id, n.name, n.x, n.y,
               r.temperature, r.moisture, r.battery, r.signal_rssi, r.timestamp
        FROM nodes n
        LEFT JOIN readings r ON r.node_id = n.node_id
            AND r.id = (
                SELECT id FROM readings
                WHERE node_id = n.node_id
                ORDER BY timestamp DESC
                LIMIT 1
            )
        ORDER BY n.node_id
    """
    with get_db(db_path) as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


# Range label -> SQLite interval expression + grouping.
# SAFETY: Values are trusted constants, never derived from user input.
# The range_label key is validated against this dict before use.
_RANGE_MAP = {
    "24h": ("datetime('now', '-1 day')", "strftime('%Y-%m-%d %H:00', timestamp)"),
    "7d":  ("datetime('now', '-7 days')", "strftime('%Y-%m-%d %H:00', timestamp)"),
    "1m":  ("datetime('now', '-1 month')", "strftime('%Y-%m-%d', timestamp)"),
    "3m":  ("datetime('now', '-3 months')", "strftime('%Y-%m-%d', timestamp)"),
    "1y":  ("datetime('now', '-1 year')", "strftime('%Y-W%W', timestamp)"),
}


def get_history(range_label, node_id=None, db_path=None):
    """Return aggregated sensor data for the given time range."""
    if range_label not in _RANGE_MAP:
        return None

    since_expr, group_expr = _RANGE_MAP[range_label]

    conditions = [f"timestamp >= {since_expr}"]
    params = []
    if node_id:
        conditions.append("node_id = ?")
        params.append(node_id)

    where = " AND ".join(conditions)

    sql = f"""
        SELECT node_id,
               {group_expr} AS period,
               ROUND(AVG(temperature), 1) AS avg_temperature,
               ROUND(AVG(moisture), 0)    AS avg_moisture,
               ROUND(AVG(battery), 0)     AS avg_battery,
               COUNT(*)                    AS sample_count
        FROM readings
        WHERE {where}
        GROUP BY node_id, period
        ORDER BY node_id, period
    """
    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
