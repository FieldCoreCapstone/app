"""Unit tests for backend.scripts.seed_db.

The seed script creates 14 nodes and 60 days of readings. Tests use the
30-minute interval (the documented default) and assert on counts and
invariants rather than exact row totals (which can wobble by ±1 day at
the boundary).
"""

import sqlite3

import pytest

from backend.scripts.seed_db import seed_db

pytestmark = pytest.mark.unit


@pytest.fixture
def seeded_db(db):
    seed_db(interval_minutes=30, db_path=db)
    return db


class TestSeedDb:
    def test_creates_fourteen_nodes(self, seeded_db):
        conn = sqlite3.connect(seeded_db)
        try:
            n = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        finally:
            conn.close()
        assert n == 14

    def test_reading_count_in_expected_band(self, seeded_db):
        """14 nodes × 48 readings/day × 60 days = 40,320. Allow ±10 % for boundaries."""
        conn = sqlite3.connect(seeded_db)
        try:
            n = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        finally:
            conn.close()
        expected = 14 * 48 * 60
        assert 0.9 * expected <= n <= 1.1 * expected, (
            f"expected ~{expected}, got {n}"
        )

    def test_idempotent_wipe_first(self, db):
        """Running seed twice does not double-count — it wipes first."""
        seed_db(interval_minutes=30, db_path=db)
        conn = sqlite3.connect(db)
        try:
            first = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        finally:
            conn.close()
        seed_db(interval_minutes=30, db_path=db)
        conn = sqlite3.connect(db)
        try:
            second = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        finally:
            conn.close()
        # Counts should be within a small tolerance (different "now" anchors).
        assert abs(first - second) < first * 0.05

    def test_all_moisture_values_in_range(self, seeded_db):
        conn = sqlite3.connect(seeded_db)
        try:
            row = conn.execute(
                "SELECT MIN(moisture), MAX(moisture) FROM readings"
            ).fetchone()
        finally:
            conn.close()
        assert 0 <= row[0]
        assert row[1] <= 100

    def test_all_moisture_values_non_negative(self, seeded_db):
        conn = sqlite3.connect(seeded_db)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM readings WHERE moisture < 0"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_drying_trend_in_last_10_days(self, seeded_db):
        """The seed script subtracts moisture in the last 10 days. The
        average over the most-recent window should be lower than the
        prior window."""
        conn = sqlite3.connect(seeded_db)
        try:
            recent = conn.execute(
                "SELECT AVG(moisture) FROM readings "
                "WHERE timestamp >= datetime('now', '-10 days')"
            ).fetchone()[0]
            earlier = conn.execute(
                "SELECT AVG(moisture) FROM readings "
                "WHERE timestamp <  datetime('now', '-10 days')"
            ).fetchone()[0]
        finally:
            conn.close()
        assert recent < earlier, (
            f"expected drying trend (recent < earlier); got {recent=} {earlier=}"
        )

    def test_interval_15_minutes_doubles_reading_count(self, db):
        """A 15-minute interval should roughly double the count vs 30-minute."""
        seed_db(interval_minutes=15, db_path=db)
        conn = sqlite3.connect(db)
        try:
            n15 = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        finally:
            conn.close()
        # 14 × 96 × 60 ≈ 80,640.
        expected = 14 * 96 * 60
        assert 0.9 * expected <= n15 <= 1.1 * expected
