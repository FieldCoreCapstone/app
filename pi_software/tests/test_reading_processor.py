"""Tests for the shared reading processor."""

import sqlite3

import pytest

from services.reading_processor import process_reading, voltage_to_battery_pct


class TestVoltageToBatteryPct:
    def test_fresh_battery(self):
        assert voltage_to_battery_pct(9.6) == 100

    def test_above_max(self):
        assert voltage_to_battery_pct(10.0) == 100

    def test_dead_battery(self):
        assert voltage_to_battery_pct(6.0) == 0

    def test_below_min(self):
        assert voltage_to_battery_pct(5.0) == 0

    def test_mid_range(self):
        # 7.5V should be ~60%
        assert voltage_to_battery_pct(7.5) == 60

    def test_interpolation(self):
        # 8.55V is halfway between 9.6 and 7.5 → ~80%
        pct = voltage_to_battery_pct(8.55)
        assert 75 <= pct <= 85


class TestProcessReading:
    def test_valid_csv(self, test_db):
        result = process_reading("TEST_01,450,22.5,8.7", rssi=-67, db_path=test_db)
        assert result["node_id"] == "TEST_01"
        assert result["moisture"] == 450
        assert result["temperature"] == 22.5
        assert result["battery_voltage"] == 8.7
        assert 70 <= result["battery_pct"] <= 85
        assert result["rssi"] == -67
        assert result["reading_id"] is not None

    def test_reading_in_database(self, test_db):
        process_reading("TEST_01,450,22.5,8.7", rssi=-67, db_path=test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute("SELECT * FROM readings WHERE node_id = 'TEST_01'").fetchone()
        conn.close()
        assert row is not None

    def test_low_battery_voltage(self, test_db):
        result = process_reading("TEST_01,300,18.0,6.2", rssi=-70, db_path=test_db)
        assert result["battery_pct"] <= 10

    def test_whitespace_in_csv(self, test_db):
        result = process_reading("  TEST_01 , 450 , 22.5 , 8.7 ", rssi=-67, db_path=test_db)
        assert result["node_id"] == "TEST_01"
        assert result["moisture"] == 450

    def test_wrong_field_count(self, test_db):
        with pytest.raises(ValueError, match="Expected 4 CSV fields"):
            process_reading("TEST_01,450,22.5", rssi=-67, db_path=test_db)

    def test_non_numeric_moisture(self, test_db):
        with pytest.raises(ValueError, match="Invalid moisture"):
            process_reading("TEST_01,abc,22.5,8.7", rssi=-67, db_path=test_db)

    def test_non_numeric_temperature(self, test_db):
        with pytest.raises(ValueError, match="Invalid temperature"):
            process_reading("TEST_01,450,hot,8.7", rssi=-67, db_path=test_db)

    def test_non_numeric_battery(self, test_db):
        with pytest.raises(ValueError, match="Invalid battery voltage"):
            process_reading("TEST_01,450,22.5,full", rssi=-67, db_path=test_db)

    def test_empty_node_id(self, test_db):
        with pytest.raises(ValueError, match="Empty node_id"):
            process_reading(",450,22.5,8.7", rssi=-67, db_path=test_db)

    def test_no_rssi(self, test_db):
        result = process_reading("TEST_01,450,22.5,8.7", db_path=test_db)
        assert result["rssi"] is None
