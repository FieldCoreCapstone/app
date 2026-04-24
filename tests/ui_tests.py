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


class TestChartControls:
    """The time-range tabs and metric toggle live inside the chart card now.

    The old top-of-page .time-bar and its .time-btn buttons are gone; these
    tests cover the replacement .chart-controls block.
    """

    def test_top_time_bar_removed(self, client):
        """The old global .time-bar container must not render anywhere."""
        html = _html(client.get("/"))
        assert 'class="time-bar"' not in html

    def test_chart_controls_container_present(self, client):
        html = _html(client.get("/"))
        assert 'class="chart-controls"' in html

    def test_all_range_chips_present(self, client):
        html = _html(client.get("/"))
        for rng in ["15m", "1h", "12h", "24h", "7d", "1m", "3m"]:
            assert f'data-range="{rng}"' in html, f"Missing range chip: {rng}"

    def test_1y_range_chip_removed(self, client):
        html = _html(client.get("/"))
        assert 'data-range="1y"' not in html

    def test_metric_toggle_present(self, client):
        html = _html(client.get("/"))
        assert 'data-metric="moisture"' in html
        assert 'data-metric="temperature"' in html

    def test_default_active_chip_is_7d(self, client):
        html = _html(client.get("/"))
        assert 'class="chart-range-btn active" data-range="7d"' in html

    def test_default_active_metric_is_moisture(self, client):
        html = _html(client.get("/"))
        assert 'class="chart-metric-btn active" data-metric="moisture"' in html

    def test_chart_state_overlays_present(self, client):
        html = _html(client.get("/"))
        assert 'class="chart-loading"' in html
        assert 'class="chart-empty"' in html
        assert 'class="chart-error"' in html

    def test_time_btn_class_retired(self, client):
        """The .time-btn class should no longer appear anywhere in the dashboard."""
        html = _html(client.get("/"))
        assert "time-btn" not in html


class TestSensorTable:
    def test_table_headers_present(self, client):
        resp = client.get("/")
        html = _html(resp)
        for header in ["Node", "Battery Level", "Moisture Level", "Temperature"]:
            assert header in html, f"Missing table header: {header}"

    def test_node_column_header_is_node(self, client):
        """Header reads 'Node' (not 'Node ID') now that the cell shows a name."""
        html = _html(client.get("/"))
        assert "<th>Node</th>" in html
        assert "<th>Node ID</th>" not in html

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
        """Creating a node without a name derives `field_{id}`; table renders it."""
        client.post("/api/nodes", json={
            "node_id": 1,
            "latitude": 38.94,
            "longitude": -92.33,
        })
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 24.5,
            "moisture": 52,
            "battery": 85,
        })
        resp = client.get("/")
        html = _html(resp)
        assert "field_1" in html

    def test_multiple_nodes_appear_in_table(self, client):
        """Three nodes created via POST without names — all three derived names render."""
        for i in range(1, 4):
            client.post("/api/nodes", json={
                "node_id": i,
                "latitude": 38.0 + i,
                "longitude": -92.0 - i,
            })
            client.post("/api/sensor/reading", json={
                "node_id": i,
                "temperature": 20.0 + i,
                "moisture": 50 + i,
                "battery": 70 + i,
            })
        resp = client.get("/")
        html = _html(resp)
        for i in range(1, 4):
            assert f"field_{i}" in html

    def test_battery_percentage_displayed(self, client):
        client.post("/api/nodes", json={
            "node_id": 1,
            "name": "A",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 22.0,
            "moisture": 45,
            "battery": 75,
        })
        resp = client.get("/")
        assert "75%" in _html(resp)

    def test_high_temp_class_applied(self, client):
        """Rows with temperature > 30 should carry the 'high' CSS class."""
        client.post("/api/nodes", json={
            "node_id": 99,
            "name": "Hot Field",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": 99,
            "temperature": 35.0,
            "moisture": 20,
            "battery": 50,
        })
        resp = client.get("/")
        html = _html(resp)
        assert 'class="temp-cell high"' in html

    def test_normal_temp_class_applied(self, client):
        """Rows with temperature <= 30 should carry the 'normal' CSS class."""
        client.post("/api/nodes", json={
            "node_id": 50,
            "name": "Normal Field",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": 50,
            "temperature": 22.0,
            "moisture": 45,
            "battery": 80,
        })
        resp = client.get("/")
        html = _html(resp)
        assert 'class="temp-cell normal"' in html

    def test_moisture_bar_present_for_node(self, client):
        client.post("/api/nodes", json={
            "node_id": 1,
            "name": "A",
            "latitude": 38.0,
            "longitude": -92.0,
        })
        client.post("/api/sensor/reading", json={
            "node_id": 1,
            "temperature": 20.0,
            "moisture": 62,
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
