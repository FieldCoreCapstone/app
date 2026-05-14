"""Integration tests for the history aggregation pipeline.

Maps the Testing Plan's "History Aggregation Pipeline" group:
seed → /api/sensor/history exercises range grouping and node filtering.
"""

import importlib

import pytest

from backend.scripts.seed_db import seed_db

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "hist.db")
    monkeypatch.setenv("FIELDCORE_DB", db_path)
    from backend import config
    importlib.reload(config)
    from backend.scripts.init_db import init_db
    init_db(db_path)
    seed_db(interval_minutes=30, db_path=db_path)

    import app as app_module
    importlib.reload(app_module)
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


class TestHistoryRanges:
    @pytest.mark.parametrize("range_label", ["15m", "1h", "12h", "24h", "7d", "1m", "3m"])
    def test_all_documented_ranges_return_200(self, seeded_client, range_label):
        resp = seeded_client.get(f"/api/sensor/history?range={range_label}")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_24h_data_grouped_by_hour(self, seeded_client):
        """24h bucket key is hour-precision: 'YYYY-MM-DD HH:00'."""
        resp = seeded_client.get("/api/sensor/history?range=24h")
        rows = resp.get_json()
        assert rows  # non-empty after seed
        # Every period string should end in :00 (top of the hour).
        for r in rows:
            assert r["period"].endswith(":00"), f"unexpected bucket: {r['period']}"

    def test_1m_data_grouped_by_day(self, seeded_client):
        """1m bucket key is day-precision: 'YYYY-MM-DD' (no time)."""
        resp = seeded_client.get("/api/sensor/history?range=1m")
        rows = resp.get_json()
        assert rows
        for r in rows:
            # Day buckets have no space: 'YYYY-MM-DD'.
            assert " " not in r["period"], f"unexpected bucket: {r['period']}"

    def test_default_range_is_7d(self, seeded_client):
        with_default = seeded_client.get("/api/sensor/history").get_json()
        explicit_7d = seeded_client.get("/api/sensor/history?range=7d").get_json()
        assert with_default == explicit_7d

    def test_invalid_range_returns_400(self, seeded_client):
        resp = seeded_client.get("/api/sensor/history?range=99y")
        assert resp.status_code == 400


class TestHistoryNodeFilter:
    def test_node_id_filter_restricts_results(self, seeded_client):
        resp = seeded_client.get("/api/sensor/history?range=24h&node_id=1")
        assert resp.status_code == 200
        rows = resp.get_json()
        assert all(r["node_id"] == 1 for r in rows)

    def test_invalid_node_id_returns_400(self, seeded_client):
        resp = seeded_client.get("/api/sensor/history?range=24h&node_id=not-an-int")
        assert resp.status_code == 400

    def test_history_rows_include_joined_name(self, seeded_client):
        resp = seeded_client.get("/api/sensor/history?range=24h&node_id=1")
        rows = resp.get_json()
        assert rows
        assert rows[0]["name"] == "field_1"
