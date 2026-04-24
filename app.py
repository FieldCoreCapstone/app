"""FieldCore — Unified Flask App (Dashboard + API)."""

import logging
import os

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from backend import config
from backend.models.database import get_latest_readings
from backend.routes.health import health_bp
from backend.routes.nodes import nodes_bp
from backend.routes.sensors import sensors_bp
from backend.scripts.init_db import init_db

logger = logging.getLogger(__name__)


def normalize_moisture(value, *_unused):
    """Moisture is stored as integer percent (0-100).

    This function only clamps incoming values to the valid range so any
    stale data or edge cases still render cleanly. The *_unused args
    preserve the old signature (raw_min, raw_max) for call sites that
    may still pass them.
    """
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0


def moisture_level(pct):
    """Map a 0-100 moisture percentage to a human-readable level."""
    if pct >= 60:
        return "optimal"
    elif pct >= 40:
        return "good"
    elif pct >= 20:
        return "fair"
    return "low"


def normalize_coordinates(readings):
    """Normalize lat/lon coordinates to 0.0-1.0 range for canvas rendering."""
    xs = [r.get("latitude") for r in readings if r.get("latitude") is not None]
    ys = [r.get("longitude") for r in readings if r.get("longitude") is not None]

    if not xs or not ys:
        return readings

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    pad = 0.1
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1

    for r in readings:
        if r.get("latitude") is not None:
            r["latitude"] = pad + (1 - 2 * pad) * (r["latitude"] - x_min) / x_range
        if r.get("longitude") is not None:
            r["longitude"] = pad + (1 - 2 * pad) * (r["longitude"] - y_min) / y_range

    return readings


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB max request body

    if config.DEBUG:
        CORS(app)
    else:
        CORS(app, origins=os.environ.get("CORS_ORIGINS", "http://localhost:5001").split(","))

    # Initialize database if it doesn't exist
    if not os.path.exists(config.DATABASE_PATH):
        init_db()

    # ── Dashboard (frontend) ────────────────────────────────────────────
    @app.route("/")
    def index():
        """Serve the main sensor dashboard, backed by real database data."""
        readings = get_latest_readings()
        readings = normalize_coordinates(readings)

        nodes = []
        for r in readings:
            raw_moisture = r.get("moisture") or 0
            pct = normalize_moisture(raw_moisture)

            nodes.append({
                "id": r["node_id"],
                "name": r.get("name") or f"field_{r['node_id']}",
                "x": r.get("latitude", 0.5),
                "y": r.get("longitude", 0.5),
                "moisture": moisture_level(pct),
            })

        table_data = []
        for r in readings:
            battery = r.get("battery") or 0
            raw_moisture = r.get("moisture") or 0
            pct = normalize_moisture(raw_moisture)
            temp = r.get("temperature") or 0
            table_data.append({
                "node_id": r["node_id"],
                "name": r.get("name") or f"field_{r['node_id']}",
                "battery": battery,
                "moisture": pct,
                "temp": round(temp, 1),
                "temp_high": temp > 30,
            })

        return render_template(
            "index.html",
            nodes=nodes,
            table_data=table_data,
        )

    # ── Seed endpoint (dev tool) ────────────────────────────────────────
    @app.route("/api/seed", methods=["POST"])
    def trigger_seed():
        if not config.DEBUG:
            return jsonify({"error": "Seed endpoint is only available in debug mode"}), 403

        from backend.scripts.seed_db import seed_db
        data = request.get_json() or {}
        interval = data.get("interval_minutes", 30)

        if interval not in [15, 30]:
            return jsonify({"error": "Interval must be 15 or 30"}), 400

        try:
            seed_db(interval_minutes=interval)
            return jsonify({"status": "success", "message": f"Database wiped and seeded with {interval}m intervals"}), 200
        except Exception as e:
            logger.exception("Seed failed")
            return jsonify({"error": str(e)}), 500

    # ── API blueprints ──────────────────────────────────────────────────
    app.register_blueprint(health_bp)
    app.register_blueprint(nodes_bp)
    app.register_blueprint(sensors_bp)

    return app


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG if config.DEBUG else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=config.DEBUG)
