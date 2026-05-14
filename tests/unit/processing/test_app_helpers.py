"""Unit tests for the data-processing helpers in app.py.

These tests exercise pure functions — no Flask app or DB needed.
"""

import pytest

from app import moisture_level, normalize_coordinates, normalize_moisture

pytestmark = pytest.mark.unit


class TestMoistureLevel:
    @pytest.mark.parametrize(
        "pct,expected",
        [
            (100, "optimal"),
            (60, "optimal"),  # boundary
            (59, "good"),
            (40, "good"),  # boundary
            (39, "fair"),
            (20, "fair"),  # boundary
            (19, "low"),
            (0, "low"),
        ],
    )
    def test_classification(self, pct, expected):
        assert moisture_level(pct) == expected


class TestNormalizeMoisture:
    def test_passthrough_in_range(self):
        assert normalize_moisture(0) == 0
        assert normalize_moisture(50) == 50
        assert normalize_moisture(100) == 100

    def test_upper_clamp(self):
        assert normalize_moisture(150) == 100
        assert normalize_moisture(999) == 100

    def test_lower_clamp(self):
        assert normalize_moisture(-10) == 0

    def test_rounds_floats(self):
        assert normalize_moisture(49.4) == 49
        assert normalize_moisture(49.6) == 50

    def test_none_returns_zero(self):
        """Bad input shouldn't blow up the dashboard render."""
        assert normalize_moisture(None) == 0

    def test_non_numeric_string_returns_zero(self):
        assert normalize_moisture("abc") == 0

    def test_numeric_string_is_parsed(self):
        assert normalize_moisture("42") == 42


class TestNormalizeCoordinates:
    def test_empty_list_returns_empty(self):
        assert normalize_coordinates([]) == []

    def test_two_points_land_inside_padded_range(self):
        """With padding=0.1, all normalized coordinates fall in [0.1, 0.9]."""
        readings = [
            {"latitude": 37.4, "longitude": -91.5},
            {"latitude": 37.5, "longitude": -91.4},
        ]
        out = normalize_coordinates(readings)
        for r in out:
            # Tiny float tolerance so 0.9000000000000001 still counts as 0.9.
            assert 0.1 - 1e-9 <= r["latitude"] <= 0.9 + 1e-9
            assert 0.1 - 1e-9 <= r["longitude"] <= 0.9 + 1e-9

    def test_extremes_map_to_padding_edges(self):
        readings = [
            {"latitude": 0.0, "longitude": 0.0},
            {"latitude": 10.0, "longitude": 10.0},
        ]
        out = normalize_coordinates(readings)
        # Min point goes to 0.1; max point goes to 0.9.
        assert out[0]["latitude"] == pytest.approx(0.1, abs=1e-6)
        assert out[1]["latitude"] == pytest.approx(0.9, abs=1e-6)

    def test_single_point_no_crash(self):
        """All readings at the same coordinate triggers the `or 1` guard."""
        readings = [{"latitude": 37.4, "longitude": -91.5}]
        # Should not raise ZeroDivisionError.
        normalize_coordinates(readings)

    def test_missing_coordinates_passthrough(self):
        """Readings without lat/lon should not crash and should pass through."""
        readings = [
            {"latitude": 37.4, "longitude": -91.5},
            {"latitude": None, "longitude": None},
            {"latitude": 37.5, "longitude": -91.4},
        ]
        out = normalize_coordinates(readings)
        # Third row of the original is still recognizable.
        assert out[1]["latitude"] is None
        assert out[1]["longitude"] is None
