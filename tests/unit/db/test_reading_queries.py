"""Unit tests for backend.models.database reading helpers."""

import pytest

from backend.models.database import (
    create_node,
    get_history,
    get_latest_readings,
    insert_reading,
)

pytestmark = pytest.mark.unit


class TestInsertReading:
    def test_returns_positive_lastrowid(self, db):
        create_node(1, latitude=0, longitude=0, db_path=db)
        row_id = insert_reading(node_id=1, moisture=50, temperature=22, db_path=db)
        assert row_id >= 1

    def test_persists_optional_fields(self, db):
        create_node(1, latitude=0, longitude=0, db_path=db)
        row_id = insert_reading(
            node_id=1,
            moisture=50,
            temperature=22,
            battery=80,
            signal_rssi=-67,
            db_path=db,
        )
        # Pull it back through get_latest_readings to verify the round-trip.
        rows = get_latest_readings(db)
        assert rows[0]["battery"] == 80
        assert rows[0]["signal_rssi"] == -67


class TestGetLatestReadings:
    def test_empty_when_no_nodes(self, db):
        assert get_latest_readings(db) == []

    def test_node_with_no_readings_appears_with_null_sensor_fields(self, db):
        """LEFT JOIN — node still shows up even with zero readings."""
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        rows = get_latest_readings(db)
        assert len(rows) == 1
        assert rows[0]["node_id"] == 1
        assert rows[0]["name"] == "A"
        assert rows[0]["moisture"] is None
        assert rows[0]["temperature"] is None

    def test_returns_most_recent_per_node(self, db):
        """SQLite's `datetime('now')` is second-precision, so two rapid
        inserts can tie. Use explicit timestamps to make the test
        deterministic."""
        import sqlite3

        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        conn = sqlite3.connect(db)
        try:
            conn.executemany(
                "INSERT INTO readings (node_id, timestamp, moisture, temperature) "
                "VALUES (?, ?, ?, ?)",
                [
                    (1, "2026-05-13 12:00:00", 10, 20),
                    (1, "2026-05-14 12:00:00", 20, 22),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        rows = get_latest_readings(db)
        assert len(rows) == 1
        assert rows[0]["moisture"] == 20
        assert rows[0]["temperature"] == 22

    def test_sorted_by_node_id(self, db):
        create_node(2, latitude=0, longitude=0, name="B", db_path=db)
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        rows = get_latest_readings(db)
        assert [r["node_id"] for r in rows] == [1, 2]


class TestGetHistory:
    def test_invalid_range_returns_none(self, db):
        assert get_history("not-a-range", db_path=db) is None

    def test_returns_empty_list_when_no_readings(self, db):
        create_node(1, latitude=0, longitude=0, db_path=db)
        assert get_history("24h", db_path=db) == []

    def test_aggregates_by_node(self, db):
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        create_node(2, latitude=0, longitude=0, name="B", db_path=db)
        for m in (40, 50, 60):
            insert_reading(node_id=1, moisture=m, temperature=22, db_path=db)
        insert_reading(node_id=2, moisture=80, temperature=24, db_path=db)
        rows = get_history("24h", db_path=db)
        # At minimum, both nodes appear.
        node_ids = {r["node_id"] for r in rows}
        assert node_ids == {1, 2}

    def test_filter_by_node_id(self, db):
        create_node(1, latitude=0, longitude=0, name="A", db_path=db)
        create_node(2, latitude=0, longitude=0, name="B", db_path=db)
        insert_reading(node_id=1, moisture=50, temperature=22, db_path=db)
        insert_reading(node_id=2, moisture=70, temperature=24, db_path=db)
        rows = get_history("24h", node_id=1, db_path=db)
        assert all(r["node_id"] == 1 for r in rows)

    def test_history_rows_include_node_name_from_join(self, db):
        create_node(1, latitude=0, longitude=0, name="alpha", db_path=db)
        insert_reading(node_id=1, moisture=50, temperature=22, db_path=db)
        rows = get_history("24h", db_path=db)
        assert rows[0]["name"] == "alpha"

    @pytest.mark.parametrize("range_label", ["15m", "1h", "12h", "24h", "7d", "1m", "3m"])
    def test_all_documented_ranges_resolve(self, db, range_label):
        """Every key in _RANGE_MAP should return a list (possibly empty), not None."""
        create_node(1, latitude=0, longitude=0, db_path=db)
        result = get_history(range_label, db_path=db)
        assert result is not None
        assert isinstance(result, list)
