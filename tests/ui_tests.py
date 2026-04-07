"""UI tests for the FieldCore dashboard (server-rendered HTML)."""

def _html(resp):
    return resp.data.decode("utf-8")


class TestDashboardLoads:
    def test_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_content_type_is_html(self, client):
        resp = client.get("/")
        assert "text/html" in resp.content_type

    def test_page_title(self, client):
        resp = client.get("/")
        assert "<title>FieldCore" in _html(resp)

    def test_has_dashboard_container(self, client):
        resp = client.get("/")
        assert 'class="dashboard"' in _html(resp)


class TestTimeRangeButtons:
    def test_all_time_range_buttons_present(self, client):
        resp = client.get("/")
        html = _html(resp)
        for label in ["Live", "24 Hours", "7 Days", "1 Month", "3 Months", "1 Year"]:
            assert f'data-range="{label}"' in html, f"Missing time range button: {label}"

    def test_first_button_is_active(self, client):
        resp = client.get("/")
        html = _html(resp)
        # The first time-btn rendered should carry the 'active' class
        assert 'class="time-btn active"' in html

    def test_time_bar_container_present(self, client):
        resp = client.get("/")
        assert 'class="time-bar"' in _html(resp)


class TestSensorTable:
    def test_table_headers_present(self, client):
        resp = client.get("/")
        html = _html(resp)
        for header in ["Node ID", "Battery Level", "Moisture Level", "Temperature"]:
            assert header in html, f"Missing table header: {header}"

    def test_table_body_element_present(self, client):
        resp = client.get("/")
        assert 'id="sensorTableBody"' in _html(resp)

    def test_empty_table_body_with_no_data(self, client):
        resp = client.get("/")
        html = _html(resp)
        # tbody should exist but contain no <tr> rows when there are no readings
        tbody_start = html.index('id="sensorTableBody"')
        tbody_end = html.index("</tbody>", tbody_start)
        tbody_content = html[tbody_start:tbody_end]
        assert "<tr>" not in tbody_content

    def test_node_appears_in_table_after_ingest(self, client):
        client.post("/api/nodes", json={
            "node_id": "Node-001",
            "name": "South Field A",
            "latitude": 38.94,
            "longitude": -92.33,
        })
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 24.5,
            "moisture": 420,
            "battery": 85,
        })
        resp = client.get("/")
        html = _html(resp)
        assert "Node-001" in html

    def test_multiple_nodes_appear_in_table(self, client):
        for i in range(1, 4):
            node_id = f"Node-00{i}"
            client.post("/api/nodes", json={
                "node_id": node_id,
                "name": f"Field {i}",
                "latitude": 38.0 + i,
                "longitude": -92.0 - i,
            })
            client.post("/api/sensor/reading", json={
                "node_id": node_id,
                "temperature": 20.0 + i,
                "moisture": 300 + i * 50,
                "battery": 70 + i,
            })
        resp = client.get("/")
        html = _html(resp)
        for i in range(1, 4):
            assert f"Node-00{i}" in html

    def test_battery_percentage_displayed(self, client):
        client.post("/api/nodes", json={
            "node_id": "Node-001",
            "name": "A",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 22.0,
            "moisture": 350,
            "battery": 75,
        })
        resp = client.get("/")
        assert "75%" in _html(resp)

    def test_high_temp_class_applied(self, client):
        """Rows with temperature > 30 should carry the 'high' CSS class."""
        client.post("/api/nodes", json={
            "node_id": "Node-H",
            "name": "Hot Field",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": "Node-H",
            "temperature": 35.0,
            "moisture": 200,
            "battery": 50,
        })
        resp = client.get("/")
        html = _html(resp)
        assert 'class="temp-cell high"' in html

    def test_normal_temp_class_applied(self, client):
        """Rows with temperature <= 30 should carry the 'normal' CSS class."""
        client.post("/api/nodes", json={
            "node_id": "Node-N",
            "name": "Normal Field",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": "Node-N",
            "temperature": 22.0,
            "moisture": 400,
            "battery": 80,
        })
        resp = client.get("/")
        html = _html(resp)
        assert 'class="temp-cell normal"' in html

    def test_moisture_bar_present_for_node(self, client):
        client.post("/api/nodes", json={
            "node_id": "Node-001",
            "name": "A",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": "Node-001",
            "temperature": 20.0,
            "moisture": 490,
            "battery": 90,
        })
        resp = client.get("/")
        assert 'class="mini-bar-fill"' in _html(resp)


class TestMapSection:
    def test_map_card_present(self, client):
        resp = client.get("/")
        assert "Field Sensor Map" in _html(resp)

    def test_leaflet_map_container_present(self, client):
        resp = client.get("/")
        assert 'id="leafletMap"' in _html(resp)

    def test_canvas_map_container_present(self, client):
        resp = client.get("/")
        assert 'id="sensorMap"' in _html(resp)

    def test_view_toggle_buttons_present(self, client):
        resp = client.get("/")
        html = _html(resp)
        assert 'data-view="canvas"' in html
        assert 'data-view="map"' in html

    def test_map_view_active_by_default(self, client):
        """The Map view toggle button should be active on initial load."""
        resp = client.get("/")
        html = _html(resp)
        # The map button renders with 'active' class
        assert 'data-view="map"' in html
        map_btn_idx = html.index('data-view="map"')
        snippet = html[max(0, map_btn_idx - 50):map_btn_idx]
        assert "active" in snippet

    def test_leaflet_css_included(self, client):
        resp = client.get("/")
        assert "leaflet" in _html(resp)

    def test_nodes_data_attribute_rendered(self, client):
        """The sensorMap canvas element should carry the server-rendered nodes JSON."""
        resp = client.get("/")
        assert 'data-nodes="' in _html(resp)


class TestChartSection:
    def test_history_chart_canvas_present(self, client):
        resp = client.get("/")
        assert 'id="historyChart"' in _html(resp)

    def test_historical_trends_card_present(self, client):
        resp = client.get("/")
        assert "Historical Trends" in _html(resp)

    def test_chartjs_script_included(self, client):
        resp = client.get("/")
        assert "chart.js" in _html(resp).lower()


class TestStaticAssets:
    def test_main_js_linked(self, client):
        resp = client.get("/")
        assert "main.js" in _html(resp)

    def test_heatmap_js_linked(self, client):
        resp = client.get("/")
        assert "heatmap.js" in _html(resp)

    def test_stylesheet_linked(self, client):
        resp = client.get("/")
        assert "style.css" in _html(resp)


class TestSeedEndpoint:
    def test_seed_blocked_in_non_debug_mode(self, client):
        """Seed endpoint must return 403 when DEBUG is off (default in tests)."""
        resp = client.post("/api/seed", json={"interval_minutes": 30})
        assert resp.status_code == 403
        assert "debug" in resp.get_json()["error"].lower()

    def test_seed_invalid_interval_blocked(self, client, monkeypatch):
        """Even with DEBUG on, an unsupported interval must return 400."""
        import importlib
        from backend import config as cfg
        monkeypatch.setenv("FLASK_DEBUG", "1")
        importlib.reload(cfg)

        import app as app_module
        importlib.reload(app_module)
        debug_app = app_module.create_app()
        debug_app.config["TESTING"] = True

        with debug_app.test_client() as debug_client:
            resp = debug_client.post("/api/seed", json={"interval_minutes": 99})
            assert resp.status_code == 400
            assert "Interval" in resp.get_json()["error"]

        monkeypatch.setenv("FLASK_DEBUG", "0")
        importlib.reload(cfg)
