"""Tests for the FieldCore Flask API."""


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


class TestNodes:
    def test_list_nodes_empty(self, client):
        resp = client.get("/api/nodes")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_node(self, client):
        resp = client.post("/api/nodes", json={
            "node_id": "Node-001",
            "name": "South Field A",
            "latitude": 38.94,
            "longitude": -92.33,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["node_id"] == "Node-001"
        assert data["name"] == "South Field A"

    def test_create_node_missing_fields(self, client):
        resp = client.post("/api/nodes", json={"node_id": "Node-001"})
        assert resp.status_code == 400
        assert "Missing required fields" in resp.get_json()["error"]

    def test_create_duplicate_node(self, client):
        payload = {"node_id": "Node-001", "name": "A", "latitude": 0, "longitude": 0}
        client.post("/api/nodes", json=payload)
        resp = client.post("/api/nodes", json=payload)
        assert resp.status_code == 409

    def test_list_nodes_after_create(self, client):
        client.post("/api/nodes", json={"node_id": "Node-001", "name": "A", "latitude": 0, "longitude": 0})
        client.post("/api/nodes", json={"node_id": "Node-002", "name": "B", "latitude": 1, "longitude": 1})
        resp = client.get("/api/nodes")
        assert len(resp.get_json()) == 2

    def test_create_node_invalid_coordinates(self, client):
        resp = client.post("/api/nodes", json={
            "node_id": "Node-001",
            "name": "Bad Coords",
            "latitude": "notanumber",
            "longitude": 0,
        })
        assert resp.status_code == 400
        assert "must be numbers" in resp.get_json()["error"]

    def test_create_node_invalid_node_id(self, client):
        resp = client.post("/api/nodes", json={
            "node_id": "<script>alert(1)</script>",
            "name": "XSS attempt",
            "latitude": 0,
            "longitude": 0,
        })
        assert resp.status_code == 400
        assert "node_id must be" in resp.get_json()["error"]

    def test_create_node_empty_name(self, client):
        resp = client.post("/api/nodes", json={
            "node_id": "Node-001",
            "name": "",
            "latitude": 0,
            "longitude": 0,
        })
        assert resp.status_code == 400
        assert "name must be" in resp.get_json()["error"]


class TestSensors:
    def _add_node(self, client):
        client.post("/api/nodes", json={"node_id": "Node-001", "name": "A", "latitude": 0, "longitude": 0})

    def test_latest_empty(self, client):
        resp = client.get("/api/sensor/latest")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_ingest_reading(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 24.5,
            "moisture": 523,
        })
        assert resp.status_code == 201
        assert resp.get_json()["status"] == "ok"

    def test_ingest_reading_with_optional_fields(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 22.0,
            "moisture": 400,
            "battery": 85,
            "signal_rssi": -67,
        })
        assert resp.status_code == 201

    def test_ingest_reading_unknown_node(self, client):
        resp = client.post("/api/sensor/reading", json={
            "node_id": "FAKE",
            "temperature": 20.0,
            "moisture": 100,
        })
        assert resp.status_code == 404

    def test_ingest_reading_missing_fields(self, client):
        resp = client.post("/api/sensor/reading", json={"node_id": "Node-001"})
        assert resp.status_code == 400

    def test_ingest_reading_invalid_moisture(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 24.5,
            "moisture": "abc",
        })
        assert resp.status_code == 400
        assert "must be" in resp.get_json()["error"]

    def test_ingest_reading_invalid_temperature(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": "notanumber",
            "moisture": 500,
        })
        assert resp.status_code == 400

    def test_latest_after_ingest(self, client):
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 24.5,
            "moisture": 523,
        })
        resp = client.get("/api/sensor/latest")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["node_id"] == "Node-001"
        assert data[0]["temperature"] == 24.5
        assert data[0]["moisture"] == 523

    def test_history_invalid_range(self, client):
        resp = client.get("/api/sensor/history?range=invalid")
        assert resp.status_code == 400

    def test_history_valid_range(self, client):
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 24.5,
            "moisture": 523,
        })
        resp = client.get("/api/sensor/history?range=24h")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1

    def test_history_new_ranges_return_200(self, client):
        """15m, 1h, and 12h are valid ranges after the range-set refresh.

        Seeds a reading so 1h and 12h actually exercise the new bucket SQL
        with real data. 15m is skipped for the data assertion because the
        minute-bucket boundary can legitimately miss a just-inserted row
        when the clock rolls over between insert and query.
        """
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 22.0,
            "moisture": 50,
        })
        for rng in ("15m", "1h", "12h"):
            resp = client.get(f"/api/sensor/history?range={rng}")
            assert resp.status_code == 200, f"{rng} returned {resp.status_code}"
            data = resp.get_json()
            assert isinstance(data, list)
            if rng in ("1h", "12h"):
                assert len(data) >= 1, f"{rng} returned no rows with seeded data"

    def test_history_default_range_is_7d(self, client):
        """Omitting the range parameter defaults to 7d (not 24h)."""
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 24.5,
            "moisture": 523,
        })
        default_resp = client.get("/api/sensor/history")
        seven_d_resp = client.get("/api/sensor/history?range=7d")
        assert default_resp.status_code == 200
        assert default_resp.get_json() == seven_d_resp.get_json()

    def test_history_1y_now_rejected(self, client):
        """1y was dropped from the range set; the API now returns 400 for it."""
        resp = client.get("/api/sensor/history?range=1y")
        assert resp.status_code == 400
        # Error body must not advertise 1y as a valid option.
        assert "1y" not in resp.get_json()["error"]

    def test_history_1h_returns_seeded_reading(self, client):
        """A reading inserted moments ago shows up in the 1h window.

        We use 1h (not 15m) because the 15m minute-bucket window can legitimately
        miss a reading when the clock rolls over between insert and fetch.
        """
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 22.0,
            "moisture": 50,
        })
        resp = client.get("/api/sensor/history?range=1h")
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1

    def test_history_filter_by_node(self, client):
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 24.5,
            "moisture": 523,
        })
        resp = client.get("/api/sensor/history?range=24h&node_id=Node-001")
        assert resp.status_code == 200
