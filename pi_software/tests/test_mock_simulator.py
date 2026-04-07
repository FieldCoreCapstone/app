"""Tests for the mock node simulator."""

import sqlite3
import time

import pytest

from services.mock_simulator import MOCK_NODES, generate_reading


class TestGenerateReading:
    def test_returns_csv_and_rssi(self):
        config = MOCK_NODES[0]
        csv_string, rssi = generate_reading(config, time.time())
        assert isinstance(csv_string, str)
        assert isinstance(rssi, int)
        assert -85 <= rssi <= -60

    def test_csv_has_four_fields(self):
        config = MOCK_NODES[0]
        csv_string, _ = generate_reading(config, time.time())
        parts = csv_string.split(",")
        assert len(parts) == 4

    def test_node_id_matches(self):
        for config in MOCK_NODES:
            csv_string, _ = generate_reading(config, time.time())
            assert csv_string.startswith(config[0] + ",")

    def test_moisture_is_non_negative(self):
        config = MOCK_NODES[0]
        for _ in range(50):
            csv_string, _ = generate_reading(config, time.time())
            moisture = int(csv_string.split(",")[1])
            assert moisture >= 0

    def test_battery_drains_over_time(self):
        config = ("TEST", 400, 30, 0, 9.5)
        csv_recent, _ = generate_reading(config, time.time())
        csv_old, _ = generate_reading(config, time.time() - 30 * 86400)  # 30 days ago
        v_recent = float(csv_recent.split(",")[3])
        v_old = float(csv_old.split(",")[3])
        assert v_recent > v_old

    def test_twelve_distinct_nodes(self):
        ids = [c[0] for c in MOCK_NODES]
        assert len(ids) == 12
        assert len(set(ids)) == 12

    def test_csv_parses_through_process_reading(self, test_db):
        """Integration: generated CSV is valid input for process_reading."""
        from services.reading_processor import process_reading

        config = ("TEST_01", 400, 30, 0, 9.0)
        csv_string, rssi = generate_reading(config, time.time())
        result = process_reading(csv_string, rssi=rssi, db_path=test_db)
        assert result["node_id"] == "TEST_01"

        conn = sqlite3.connect(test_db)
        count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        conn.close()
        assert count == 1
