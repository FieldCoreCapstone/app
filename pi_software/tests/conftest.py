"""Shared test fixtures for pi_software tests."""

import sqlite3

import pytest


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    latitude    REAL NOT NULL,
    longitude   REAL NOT NULL,
    installed   DATE,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     INTEGER NOT NULL,
    timestamp   DATETIME NOT NULL DEFAULT (datetime('now')),
    battery     INTEGER,
    moisture    INTEGER,
    temperature REAL,
    signal_rssi INTEGER,
    FOREIGN KEY (node_id) REFERENCES nodes(id)
);
"""


@pytest.fixture
def test_db(tmp_path):
    """Create an isolated test database with integer-keyed nodes.

    Seeds ids 1, 2, 3 with names field_1, field_2, field_3. Node 1 covers
    Arduino-shaped tests; node 2 covers the mock-simulator integration test.
    """
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO nodes (id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
        [
            (1, "field_1", 37.42, -91.56),
            (2, "field_2", 37.42, -91.56),
            (3, "field_3", 37.42, -91.56),
        ],
    )
    conn.commit()
    conn.close()
    return db_path
