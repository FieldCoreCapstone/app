"""Tests for the mock node simulator."""

import sqlite3
import time

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

    def test_moisture_within_percent_range(self):
        config = MOCK_NODES[0]
        for _ in range(50):
            csv_string, _ = generate_reading(config, time.time())
            moisture = float(csv_string.split(",")[1])
            assert 0 <= moisture <= 100

    def test_vcc_in_reasonable_range(self):
        config = MOCK_NODES[0]
        csv_string, _ = generate_reading(config, time.time())
        vcc_mv = int(csv_string.split(",")[3])
        assert 4500 <= vcc_mv <= 5500

    def test_twelve_distinct_nodes(self):
        ids = [c[0] for c in MOCK_NODES]
        assert len(ids) == 12
        assert len(set(ids)) == 12

    def test_csv_parses_through_process_reading(self, test_db):
        """Integration: generated CSV is valid input for process_reading."""
        from services.reading_processor import process_reading

        config = ("TEST_01", 50, 5, 0, 5100)
        csv_string, rssi = generate_reading(config, time.time())
        result = process_reading(csv_string, rssi=rssi, db_path=test_db)
        assert result["node_id"] == "TEST_01"

        conn = sqlite3.connect(test_db)
        count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        conn.close()
        assert count == 1
