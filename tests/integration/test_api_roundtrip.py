"""Integration tests: API → DB → API roundtrips.

Reuses the Flask `client` fixture from tests/conftest.py.
"""

import pytest

pytestmark = pytest.mark.integration


class TestPostNodeGetNodes:
    def test_create_then_list_includes_new_node(self, client):
        client.post("/api/nodes", json={
            "node_id": 1, "name": "alpha", "latitude": 37.4, "longitude": -91.5
        })
        resp = client.get("/api/nodes")
        assert resp.status_code == 200
        nodes = resp.get_json()
        assert any(n["node_id"] == 1 and n["name"] == "alpha" for n in nodes)


class TestPostReadingGetLatest:
    def test_reading_round_trips_through_latest(self, client):
        client.post("/api/nodes", json={
            "node_id": 1, "name": "A", "latitude": 0, "longitude": 0
        })
        client.post("/api/sensor/reading", json={
            "node_id": 1, "moisture": 55, "temperature": 23.5, "battery": 90
        })
        resp = client.get("/api/sensor/latest")
        assert resp.status_code == 200
        latest = resp.get_json()
        assert len(latest) == 1
        assert latest[0]["moisture"] == 55
        assert latest[0]["temperature"] == 23.5
        assert latest[0]["battery"] == 90

    def test_post_then_post_reading_succeeds_for_same_node(self, client):
        """Creating a node and immediately posting a reading should land 201."""
        client.post("/api/nodes", json={
            "node_id": 2, "latitude": 0, "longitude": 0
        })
        resp = client.post("/api/sensor/reading", json={
            "node_id": 2, "moisture": 40, "temperature": 21.0
        })
        assert resp.status_code == 201


class TestPostMultipleReadingsAggregateInHistory:
    def test_multiple_readings_show_up_in_history(self, client):
        client.post("/api/nodes", json={
            "node_id": 1, "name": "A", "latitude": 0, "longitude": 0
        })
        for moisture in (40, 50, 60):
            client.post("/api/sensor/reading", json={
                "node_id": 1, "moisture": moisture, "temperature": 22.0
            })
        resp = client.get("/api/sensor/history?range=24h")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1
        # All rows should be for the node we just created.
        assert all(r["node_id"] == 1 for r in data)
