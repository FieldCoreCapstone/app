"""Lightweight SQLite helpers for Pi services.

Writes to the same sensors.db used by the Flask web app.
Uses the same schema (nodes + readings tables) — no ORM, just raw SQL.
"""

import os
import sqlite3
from contextlib import contextmanager

DEFAULT_DB_PATH = os.environ.get(
    "FIELDCORE_DB",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "cap-proj", "app", "backend", "sensors.db"),
)


@contextmanager
def get_db(db_path=None):
    path = db_path or DEFAULT_DB_PATH
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


def insert_reading(node_id, moisture, temperature, battery=None, signal_rssi=None, db_path=None):
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO readings (node_id, moisture, temperature, battery, signal_rssi)
               VALUES (?, ?, ?, ?, ?)""",
            (node_id, moisture, temperature, battery, signal_rssi),
        )
        conn.commit()
        return cursor.lastrowid


def node_exists(node_id, db_path=None):
    with get_db(db_path) as conn:
        row = conn.execute("SELECT 1 FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        return row is not None
