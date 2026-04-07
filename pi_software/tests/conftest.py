"""Shared test fixtures for pi_software tests."""

import sqlite3

import pytest


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    latitude    REAL NOT NULL,
    longitude   REAL NOT NULL,
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
"""


@pytest.fixture
def test_db(tmp_path):
    """Create an isolated test database with the FieldCore schema and one test node."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO nodes (node_id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
        ("TEST_01", "Test Node", 37.42, -91.56),
    )
    conn.commit()
    conn.close()
    return db_path
