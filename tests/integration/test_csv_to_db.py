"""Integration test: CSV packet → process_reading → SQLite.

Most of this surface is already covered by pi_software/tests/test_reading_processor.py.
This file is the integration-marked entry point that maps the Testing Plan's
"CSV → Database Pipeline" group to a single discoverable file in tests/.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[2]
PI_SOFTWARE = APP_ROOT / "pi_software"
if str(PI_SOFTWARE) not in sys.path:
    sys.path.insert(0, str(PI_SOFTWARE))

from services.reading_processor import process_reading  # noqa: E402

pytestmark = pytest.mark.integration


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    installed DATE,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT (datetime('now')),
    battery INTEGER,
    moisture INTEGER,
    temperature REAL,
    signal_rssi INTEGER,
    FOREIGN KEY (node_id) REFERENCES nodes(id)
);
"""


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "csv.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO nodes (id, name, latitude, longitude) VALUES (1, 'field_1', 0, 0)"
    )
    conn.commit()
    conn.close()
    return db_path


class TestCsvToDb:
    def test_valid_csv_inserts_row_with_derived_battery(self, db):
        result = process_reading("1,45.5,22.2,5161", rssi=-67, db_path=db)
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT node_id, moisture, temperature, battery, signal_rssi "
                "FROM readings WHERE id = ?",
                (result["reading_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == 1
        assert row[1] == 46  # moisture rounded from 45.5
        assert row[2] == pytest.approx(22.2)
        # VCC 5161 mV falls in the 4500–5500 mV linear band → ~66%.
        assert 60 <= row[3] <= 70
        assert row[4] == -67

    def test_rssi_persisted(self, db):
        process_reading("1,30.0,22.0,5000", rssi=-80, db_path=db)
        conn = sqlite3.connect(db)
        try:
            row = conn.execute("SELECT signal_rssi FROM readings").fetchone()
        finally:
            conn.close()
        assert row[0] == -80

    def test_malformed_csv_leaves_db_untouched(self, db):
        """A parse failure should not partial-insert into the DB."""
        conn = sqlite3.connect(db)
        try:
            before = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        finally:
            conn.close()

        with pytest.raises(ValueError):
            process_reading("1,not-a-number,22.0,5000", rssi=-67, db_path=db)

        conn = sqlite3.connect(db)
        try:
            after = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        finally:
            conn.close()
        assert before == after
