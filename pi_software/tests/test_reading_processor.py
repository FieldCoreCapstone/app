"""Tests for the shared reading processor."""

import sqlite3

import pytest

from services.reading_processor import process_reading, vcc_millivolts_to_health_pct


class TestVccMillivoltsToHealthPct:
    def test_nominal(self):
        # 5000 mV is squarely in the healthy band
        pct = vcc_millivolts_to_health_pct(5000)
        assert 40 <= pct <= 60

    def test_full_health(self):
        assert vcc_millivolts_to_health_pct(5500) == 100

    def test_above_max(self):
        assert vcc_millivolts_to_health_pct(6000) == 100

    def test_brownout(self):
        assert vcc_millivolts_to_health_pct(4500) == 0

    def test_below_min(self):
        assert vcc_millivolts_to_health_pct(3000) == 0

    def test_mid_range(self):
        # 5200 mV is 70% of the way from 4500 to 5500
        assert vcc_millivolts_to_health_pct(5200) == 70


class TestProcessReading:
    def test_valid_csv(self, test_db):
        # Arduino-style payload: int nodeID, float moisture%, float tempC, int mV
        result = process_reading("1,45.50,22.20,5161", rssi=-67, db_path=test_db)
        assert result["node_id"] == 1
        assert result["moisture"] == 46  # rounded from 45.50
        assert result["temperature"] == 22.2
        assert result["vcc_mv"] == 5161
        assert 60 <= result["battery_pct"] <= 70
        assert result["rssi"] == -67
        assert result["reading_id"] is not None

    def test_reading_in_database(self, test_db):
        process_reading("1,45.50,22.20,5161", rssi=-67, db_path=test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute("SELECT * FROM readings WHERE node_id = 1").fetchone()
        conn.close()
        assert row is not None

    def test_moisture_clamped_over_100(self, test_db):
        result = process_reading("1,150.0,22.0,5100", rssi=-67, db_path=test_db)
        assert result["moisture"] == 100

    def test_moisture_clamped_below_zero(self, test_db):
        result = process_reading("1,-10.0,22.0,5100", rssi=-67, db_path=test_db)
        assert result["moisture"] == 0

    def test_dry_soil_zero_moisture(self, test_db):
        result = process_reading("1,0.00,21.20,5161", rssi=-67, db_path=test_db)
        assert result["moisture"] == 0

    def test_integer_moisture_also_works(self, test_db):
        result = process_reading("1,75,22.0,5100", rssi=-67, db_path=test_db)
        assert result["moisture"] == 75

    def test_brownout_battery(self, test_db):
        result = process_reading("1,50.0,20.0,4400", rssi=-70, db_path=test_db)
        assert result["battery_pct"] == 0

    def test_whitespace_in_csv(self, test_db):
        result = process_reading("  1 , 45.5 , 22.2 , 5161 ", rssi=-67, db_path=test_db)
        assert result["node_id"] == 1
        assert result["moisture"] == 46

    def test_wrong_field_count(self, test_db):
        with pytest.raises(ValueError, match="Expected 4 CSV fields"):
            process_reading("1,45.5,22.2", rssi=-67, db_path=test_db)

    def test_non_numeric_moisture(self, test_db):
        with pytest.raises(ValueError, match="Invalid moisture"):
            process_reading("1,abc,22.5,5100", rssi=-67, db_path=test_db)

    def test_non_numeric_temperature(self, test_db):
        with pytest.raises(ValueError, match="Invalid temperature"):
            process_reading("1,45.5,hot,5100", rssi=-67, db_path=test_db)

    def test_non_numeric_vcc(self, test_db):
        with pytest.raises(ValueError, match="Invalid VCC millivolts"):
            process_reading("1,45.5,22.5,full", rssi=-67, db_path=test_db)

    def test_empty_node_id(self, test_db):
        with pytest.raises(ValueError, match="Empty node_id"):
            process_reading(",45.5,22.5,5100", rssi=-67, db_path=test_db)

    def test_non_integer_node_id(self, test_db):
        with pytest.raises(ValueError, match="Invalid node_id"):
            process_reading("abc,45.5,22.5,5100", rssi=-67, db_path=test_db)

    def test_zero_node_id_rejected(self, test_db):
        with pytest.raises(ValueError, match="Invalid node_id"):
            process_reading("0,45.5,22.5,5100", rssi=-67, db_path=test_db)

    def test_no_rssi(self, test_db):
        result = process_reading("1,45.5,22.5,5100", db_path=test_db)
        assert result["rssi"] is None
