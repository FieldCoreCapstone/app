from flask import Flask, render_template, jsonify

app = Flask(__name__)

# ── Sensor node data ─────────────────────────────────────────────────────────
NODES = [
    {"id": "001", "x": 0.12, "y": 0.28, "moisture": "optimal"},
    {"id": "002", "x": 0.28, "y": 0.40, "moisture": "fair"},
    {"id": "003", "x": 0.43, "y": 0.26, "moisture": "optimal"},
    {"id": "004", "x": 0.55, "y": 0.42, "moisture": "low"},
    {"id": "005", "x": 0.78, "y": 0.20, "moisture": "optimal"},
    {"id": "006", "x": 0.13, "y": 0.62, "moisture": "optimal"},
    {"id": "007", "x": 0.30, "y": 0.68, "moisture": "fair"},
    {"id": "008", "x": 0.50, "y": 0.65, "moisture": "good"},
    {"id": "009", "x": 0.65, "y": 0.72, "moisture": "optimal"},
    {"id": "010", "x": 0.82, "y": 0.65, "moisture": "low"},
]

TABLE_DATA = [
    {"node_id": "Node-001", "battery": 95, "moisture": 78, "temp": 72, "temp_high": False},
    {"node_id": "Node-002", "battery": 87, "moisture": 45, "temp": 68, "temp_high": False},
    {"node_id": "Node-003", "battery": 92, "moisture": 62, "temp": 75, "temp_high": False},
    {"node_id": "Node-004", "battery": 78, "moisture": 25, "temp": 82, "temp_high": True},
    {"node_id": "Node-005", "battery": 88, "moisture": 88, "temp": 70, "temp_high": False},
    {"node_id": "Node-006", "battery": 91, "moisture": 71, "temp": 73, "temp_high": False},
    {"node_id": "Node-007", "battery": 65, "moisture": 33, "temp": 79, "temp_high": False},
    {"node_id": "Node-008", "battery": 94, "moisture": 55, "temp": 71, "temp_high": False},
    {"node_id": "Node-009", "battery": 89, "moisture": 62, "temp": 69, "temp_high": False},
    {"node_id": "Node-010", "battery": 72, "moisture": 15, "temp": 85, "temp_high": True},
]

TIME_RANGES = ["Live", "24 Hours", "7 Days", "1 Month", "3 Months", "1 Year"]


@app.route("/")
def index():
    return render_template(
        "index.html",
        nodes=NODES,
        table_data=TABLE_DATA,
        time_ranges=TIME_RANGES,
    )


@app.route("/api/sensors")
def api_sensors():
    return jsonify({"nodes": NODES, "table": TABLE_DATA})


if __name__ == "__main__":
    app.run(debug=True)
