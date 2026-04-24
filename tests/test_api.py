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
            "node_id": 1,
            "name": "South Field A",
            "latitude": 38.94,
            "longitude": -92.33,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["node_id"] == 1
        assert data["name"] == "South Field A"

    def test_create_node_defaults_name_to_field_id(self, client):
        """Omitting `name` derives `field_{id}` server-side."""
        resp = client.post("/api/nodes", json={
            "node_id": 7,
            "latitude": 38.94,
            "longitude": -92.33,
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["node_id"] == 7
        assert body["name"] == "field_7"

    def test_create_node_missing_fields(self, client):
        resp = client.post("/api/nodes", json={"node_id": 1})
        assert resp.status_code == 400
        assert "Missing required fields" in resp.get_json()["error"]

    def test_create_duplicate_node(self, client):
        payload = {"node_id": 1, "name": "A", "latitude": 0, "longitude": 0}
        client.post("/api/nodes", json=payload)
        resp = client.post("/api/nodes", json=payload)
        assert resp.status_code == 409

    def test_list_nodes_after_create(self, client):
        client.post("/api/nodes", json={"node_id": 1, "name": "A", "latitude": 0, "longitude": 0})
        client.post("/api/nodes", json={"node_id": 2, "name": "B", "latitude": 1, "longitude": 1})
        resp = client.get("/api/nodes")
        assert len(resp.get_json()) == 2

    def test_create_node_invalid_coordinates(self, client):
        resp = client.post("/api/nodes", json={
            "node_id": 1,
            "name": "Bad Coords",
            "latitude": "notanumber",
            "longitude": 0,
        })
        assert resp.status_code == 400
        assert "must be numbers" in resp.get_json()["error"]

    def test_create_node_rejects_non_integer_id(self, client):
        """Non-numeric strings, zero, and negatives are all 400."""
        for bad in ["abc", "<script>", ""]:
            resp = client.post("/api/nodes", json={
                "node_id": bad,
                "latitude": 0,
                "longitude": 0,
            })
            assert resp.status_code == 400, f"{bad!r} should be rejected"

        for bad in [0, -1, -100]:
            resp = client.post("/api/nodes", json={
                "node_id": bad,
                "latitude": 0,
                "longitude": 0,
            })
            assert resp.status_code == 400, f"{bad!r} should be rejected"

    def test_create_node_rejects_stringified_integer(self, client):
        """POST bodies accept JSON integers only — '1' as a string is 400."""
        resp = client.post("/api/nodes", json={
            "node_id": "1",
            "latitude": 0,
            "longitude": 0,
        })
        assert resp.status_code == 400

    def test_create_node_empty_name(self, client):
        resp = client.post("/api/nodes", json={
            "node_id": 1,
            "name": "",
            "latitude": 0,
            "longitude": 0,
        })
        assert resp.status_code == 400
        assert "name must be" in resp.get_json()["error"]


class TestSensors:
    def _add_node(self, client, node_id=1):
        client.post("/api/nodes", json={"node_id": node_id, "name": "A", "latitude": 0, "longitude": 0})

    def test_latest_empty(self, client):
        resp = client.get("/api/sensor/latest")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_ingest_reading(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": 1,
            "moisture": 60,
            "temperature": 22.5,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["id"] >= 1

    def test_ingest_reading_with_optional_fields(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": 1,
            "moisture": 60,
            "temperature": 22.5,
            "battery": 95,
            "signal_rssi": -67,
        })
        assert resp.status_code == 201

    def test_ingest_reading_unknown_node(self, client):
        resp = client.post("/api/sensor/reading", json={
            "node_id": 999,
            "moisture": 60,
            "temperature": 22.5,
        })
        assert resp.status_code == 404

    def test_ingest_reading_missing_fields(self, client):
        resp = client.post("/api/sensor/reading", json={"node_id": 1})
        assert resp.status_code == 400

    def test_ingest_reading_invalid_moisture(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": 1,
            "moisture": "wet",
            "temperature": 22.5,
        })
        assert resp.status_code == 400

    def test_ingest_reading_invalid_temperature(self, client):
        self._add_node(client)
        resp = client.post("/api/sensor/reading", json={
            "node_id": 1,
            "moisture": 60,
            "temperature": "hot",
        })
        assert resp.status_code == 400

    def test_latest_after_ingest(self, client):
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 24.5,
            "moisture": 52,
        })
        resp = client.get("/api/sensor/latest")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["node_id"] == 1
        assert data[0]["name"] == "A"
        assert data[0]["temperature"] == 24.5

    def test_history_invalid_range(self, client):
        resp = client.get("/api/sensor/history?range=invalid")
        assert resp.status_code == 400

    def test_history_valid_range(self, client):
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 24.5,
            "moisture": 52,
        })
        resp = client.get("/api/sensor/history?range=24h")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1
        # History rows now include the node's name (from the JOIN).
        assert data[0]["node_id"] == 1
        assert data[0]["name"] == "A"

    def test_history_new_ranges_return_200(self, client):
        """15m, 1h, and 12h are valid ranges with data coverage for 1h/12h."""
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": 1,
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
        """Omitting the range parameter defaults to 7d."""
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 24.5,
            "moisture": 52,
        })
        default_resp = client.get("/api/sensor/history")
        seven_d_resp = client.get("/api/sensor/history?range=7d")
        assert default_resp.status_code == 200
        assert default_resp.get_json() == seven_d_resp.get_json()

    def test_history_1y_now_rejected(self, client):
        resp = client.get("/api/sensor/history?range=1y")
        assert resp.status_code == 400
        assert "1y" not in resp.get_json()["error"]

    def test_history_1h_returns_seeded_reading(self, client):
        """A reading inserted moments ago shows up in the 1h window."""
        self._add_node(client)
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 22.0,
            "moisture": 50,
        })
        resp = client.get("/api/sensor/history?range=1h")
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1

    def test_history_filter_by_node(self, client):
        self._add_node(client, node_id=1)
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 24.5,
            "moisture": 52,
        })
        resp = client.get("/api/sensor/history?range=24h&node_id=1")
        assert resp.status_code == 200

    def test_history_filter_rejects_non_integer_node_id(self, client):
        """GET ?node_id=abc returns 400 with a clear error."""
        resp = client.get("/api/sensor/history?range=24h&node_id=abc")
        assert resp.status_code == 400
        assert "positive integer" in resp.get_json()["error"]

    def test_history_filter_rejects_zero_node_id(self, client):
        resp = client.get("/api/sensor/history?range=24h&node_id=0")
        assert resp.status_code == 400
