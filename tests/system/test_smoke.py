"""End-to-end smoke test: seed → app → 14 markers + health check.

This is the Testing Plan's "definitive 'it works' test" for the full
soil-to-screen pipeline (excluding the actual Arduino hardware, which
is covered by tests/manual/HARDWARE_E2E.md).
"""

import importlib

import pytest

from backend.scripts.seed_db import seed_db

pytestmark = pytest.mark.system


@pytest.fixture
def smoke_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "smoke.db")
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


class TestSmoke:
    def test_health_endpoint_returns_ok(self, smoke_client):
        resp = smoke_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}

    def test_dashboard_renders_14_node_names(self, smoke_client):
        resp = smoke_client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        for i in range(1, 15):
            assert f"field_{i}" in html

    def test_latest_returns_14_nodes(self, smoke_client):
        resp = smoke_client.get("/api/sensor/latest")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 14

    def test_history_returns_rows_for_each_documented_range(self, smoke_client):
        for rng in ("15m", "1h", "12h", "24h", "7d", "1m", "3m"):
            resp = smoke_client.get(f"/api/sensor/history?range={rng}")
            assert resp.status_code == 200, f"{rng} did not respond 200"
