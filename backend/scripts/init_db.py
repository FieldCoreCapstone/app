"""Initialize the FieldCore SQLite database.

Run directly:  python -m backend.scripts.init_db
Or via app:    The Flask app calls init_db() on startup if the DB doesn't exist.
"""

import logging
import sqlite3

from backend.config import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    x           REAL NOT NULL,
    y           REAL NOT NULL,
    installed   DATE,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     TEXT NOT NULL,
    timestamp   DATETIME NOT NULL DEFAULT (datetime('now')),
    battery     INTEGER,
    moisture    INTEGER,
    temperature REAL,
    signal_rssi INTEGER,
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);

CREATE INDEX IF NOT EXISTS idx_readings_node_time
    ON readings(node_id, timestamp DESC);
"""


def init_db(db_path=None):
    path = db_path or DATABASE_PATH
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    logger.info("Database initialized at %s", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
