import logging

from flask import Blueprint, jsonify, request

from backend.models.database import create_node, get_all_nodes

logger = logging.getLogger(__name__)

nodes_bp = Blueprint("nodes", __name__)

_MAX_NAME_LEN = 100


def _validate_node_id(raw):
    """Accept a JSON integer only. Reject strings, floats, booleans, and non-positive.

    Returns (node_id, None) on success, or (None, error_message) on failure.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None, "node_id must be a positive integer"
    if raw < 1:
        return None, "node_id must be a positive integer"
    return raw, None


@nodes_bp.route("/api/nodes", methods=["GET"])
def list_nodes():
    return jsonify(get_all_nodes())


@nodes_bp.route("/api/nodes", methods=["POST"])
def add_node():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    required = ["node_id", "latitude", "longitude"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    node_id, err = _validate_node_id(data["node_id"])
    if err:
        return jsonify({"error": err}), 400

    name = data.get("name")
    if name is not None:
        name = str(name)
        if len(name) == 0 or len(name) > _MAX_NAME_LEN:
            return jsonify({"error": f"name must be 1-{_MAX_NAME_LEN} characters"}), 400

    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
    except (ValueError, TypeError):
        return jsonify({"error": "latitude and longitude must be numbers"}), 400

    try:
        node = create_node(
            node_id=node_id,
            latitude=latitude,
            longitude=longitude,
            name=name,
            installed=data.get("installed"),
            notes=data.get("notes"),
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            return jsonify({"error": f"Node '{node_id}' already exists"}), 409
        return jsonify({"error": str(e)}), 500

    return jsonify(node), 201
