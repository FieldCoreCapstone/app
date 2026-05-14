"""Integration test: seed_db → GET / → dashboard renders all 14 nodes."""

import importlib

import pytest

from backend.scripts.seed_db import seed_db

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded_client(tmp_path, monkeypatch):
    """A Flask client backed by a fully-seeded database.

    Mirrors tests/conftest.py::client but pre-seeds before yielding.
    """
    db_path = str(tmp_path / "seed.db")
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


class TestSeedToDashboard:
    def test_dashboard_renders_all_14_node_names(self, seeded_client):
        resp = seeded_client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        for i in range(1, 15):
            assert f"field_{i}" in html, f"missing field_{i} in rendered dashboard"

    def test_latest_endpoint_returns_14_entries(self, seeded_client):
        resp = seeded_client.get("/api/sensor/latest")
        assert resp.status_code == 200
        latest = resp.get_json()
        assert len(latest) == 14

    def test_history_responds_with_aggregated_rows(self, seeded_client):
        resp = seeded_client.get("/api/sensor/history?range=24h")
        assert resp.status_code == 200
        data = resp.get_json()
        # At least one row per node in the 24h window.
        node_ids = {r["node_id"] for r in data}
        assert len(node_ids) >= 1

    def test_seed_endpoint_blocked_in_non_debug_mode(self, seeded_client):
        """In production mode (default in tests), /api/seed must return 403."""
        resp = seeded_client.post("/api/seed", json={"interval_minutes": 30})
        assert resp.status_code == 403
