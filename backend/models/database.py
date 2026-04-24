"""SQLite database helpers for FieldCore."""

import logging
import re
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

# The DB column is `nodes.id` (integer PK); every SELECT aliases it back to
# `node_id` on the wire so the JSON contract is unchanged. Never use SELECT *.
_NODE_COLUMNS = "id AS node_id, name, latitude, longitude, installed, notes"


def get_all_nodes(db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(f"SELECT {_NODE_COLUMNS} FROM nodes ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_node(node_id, db_path=None):
    with get_db(db_path) as conn:
        row = conn.execute(
            f"SELECT {_NODE_COLUMNS} FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row else None


def create_node(node_id, *, latitude, longitude, name=None, installed=None, notes=None, db_path=None):
    """Insert a node. `name` defaults to f"field_{node_id}" if not supplied.

    All arguments after `node_id` are keyword-only to prevent silent coordinate
    swaps (`create_node(1, -91.5, 37.4)` would otherwise insert inverted lat/lon).
    """
    if name is None:
        name = f"field_{node_id}"
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO nodes (id, name, latitude, longitude, installed, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (node_id, name, latitude, longitude, installed, notes),
        )
        conn.commit()
        row = conn.execute(
            f"SELECT {_NODE_COLUMNS} FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
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
        SELECT n.id AS node_id, n.name, n.latitude, n.longitude,
               r.temperature, r.moisture, r.battery, r.signal_rssi, r.timestamp
        FROM nodes n
        LEFT JOIN readings r ON r.node_id = n.id
            AND r.id = (
                SELECT id FROM readings
                WHERE node_id = n.id
                ORDER BY timestamp DESC
                LIMIT 1
            )
        ORDER BY n.id
    """
    with get_db(db_path) as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


# Range label -> SQLite interval expression + grouping.
# SAFETY: Values are trusted constants, never derived from user input.
# The range_label key is validated against this dict before use.
_RANGE_MAP = {
    "15m": ("datetime('now', '-15 minutes')", "strftime('%Y-%m-%d %H:%M', timestamp)"),
    "1h":  ("datetime('now', '-1 hour')",     "strftime('%Y-%m-%d %H:%M', timestamp)"),
    "12h": ("datetime('now', '-12 hours')",   "strftime('%Y-%m-%d %H:00', timestamp)"),
    "24h": ("datetime('now', '-1 day')",      "strftime('%Y-%m-%d %H:00', timestamp)"),
    "7d":  ("datetime('now', '-7 days')",     "strftime('%Y-%m-%d %H:00', timestamp)"),
    "1m":  ("datetime('now', '-1 month')",    "strftime('%Y-%m-%d', timestamp)"),
    "3m":  ("datetime('now', '-3 months')",   "strftime('%Y-%m-%d', timestamp)"),
}


def get_history(range_label, node_id=None, db_path=None):
    """Return aggregated sensor data for the given time range.

    Joins the nodes table so each row carries the human-readable `name`
    alongside the raw `node_id`. Frontend uses `name` as the chart legend
    label so users see 'field_1' instead of '1'.
    """
    if range_label not in _RANGE_MAP:
        return None

    since_expr, group_expr = _RANGE_MAP[range_label]

    # group_expr references a bare `timestamp` column — prefix the alias so
    # the SQL engine resolves it to the readings table after the JOIN.
    # Use a word-boundary regex so a future format string like 'timestamp-%m'
    # can't accidentally collide with the substring match.
    group_expr = re.sub(r"\btimestamp\b", "r.timestamp", group_expr)

    conditions = [f"r.timestamp >= {since_expr}"]
    params = []
    if node_id is not None:
        conditions.append("r.node_id = ?")
        params.append(node_id)

    where = " AND ".join(conditions)

    sql = f"""
        SELECT r.node_id,
               n.name,
               {group_expr} AS period,
               ROUND(AVG(r.temperature), 1) AS avg_temperature,
               ROUND(AVG(r.moisture), 0)    AS avg_moisture,
               ROUND(AVG(r.battery), 0)     AS avg_battery,
               COUNT(*)                     AS sample_count
        FROM readings r
        LEFT JOIN nodes n ON n.id = r.node_id
        WHERE {where}
        GROUP BY r.node_id, n.name, period
        ORDER BY r.node_id, period
    """
    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
