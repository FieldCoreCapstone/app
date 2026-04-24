import logging

from flask import Blueprint, jsonify, request

from backend.models.database import get_history, get_latest_readings, get_node, insert_reading
from backend.routes.nodes import _validate_node_id

logger = logging.getLogger(__name__)

sensors_bp = Blueprint("sensors", __name__)

VALID_RANGES = {"15m", "1h", "12h", "24h", "7d", "1m", "3m"}


@sensors_bp.route("/api/sensor/latest")
def latest():
    """Return the latest reading for every node (map + table data)."""
    return jsonify(get_latest_readings())


@sensors_bp.route("/api/sensor/history")
def history():
    """Return aggregated historical data for charts."""
    range_label = request.args.get("range", "7d")
    if range_label not in VALID_RANGES:
        return jsonify({"error": f"Invalid range. Use one of: {', '.join(sorted(VALID_RANGES))}"}), 400

    raw_node_id = request.args.get("node_id")
    node_id = None
    if raw_node_id is not None:
        # Query-string values are always strings — coerce to int here.
        try:
            node_id = int(raw_node_id)
        except (ValueError, TypeError):
            return jsonify({"error": "node_id must be a positive integer"}), 400
        if node_id < 1:
            return jsonify({"error": "node_id must be a positive integer"}), 400

    data = get_history(range_label, node_id=node_id)
    return jsonify(data)


@sensors_bp.route("/api/sensor/reading", methods=["POST"])
def ingest_reading():
    """Receive a sensor reading from the receiving station."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    required = ["node_id", "moisture", "temperature"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    node_id, err = _validate_node_id(data["node_id"])
    if err:
        return jsonify({"error": err}), 400

    # Verify the node exists
    if not get_node(node_id):
        return jsonify({"error": f"Unknown node_id: {node_id}"}), 404

    try:
        moisture = int(data["moisture"])
        temperature = float(data["temperature"])
        battery = int(data["battery"]) if data.get("battery") is not None else None
        signal_rssi = int(data["signal_rssi"]) if data.get("signal_rssi") is not None else None
    except (ValueError, TypeError):
        return jsonify({"error": "moisture and battery must be integers; temperature must be a number"}), 400

    reading_id = insert_reading(
        node_id=node_id,
        moisture=moisture,
        temperature=temperature,
        battery=battery,
        signal_rssi=signal_rssi,
    )

    return jsonify({"id": reading_id, "status": "ok"}), 201
