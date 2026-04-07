import logging
import re

from flask import Blueprint, jsonify, request

from backend.models.database import create_node, get_all_nodes

logger = logging.getLogger(__name__)

nodes_bp = Blueprint("nodes", __name__)

# node_id: alphanumeric, hyphens, underscores, 1-50 chars
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
_MAX_NAME_LEN = 100


@nodes_bp.route("/api/nodes", methods=["GET"])
def list_nodes():
    return jsonify(get_all_nodes())


@nodes_bp.route("/api/nodes", methods=["POST"])
def add_node():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    required = ["node_id", "name", "latitude", "longitude"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    node_id = str(data["node_id"])
    if not _NODE_ID_RE.match(node_id):
        return jsonify({"error": "node_id must be 1-50 alphanumeric, hyphen, or underscore characters"}), 400

    name = str(data["name"])
    if len(name) > _MAX_NAME_LEN or len(name) == 0:
        return jsonify({"error": f"name must be 1-{_MAX_NAME_LEN} characters"}), 400

    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
    except (ValueError, TypeError):
        return jsonify({"error": "latitude and longitude must be numbers"}), 400

    try:
        node = create_node(
            node_id=node_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            installed=data.get("installed"),
            notes=data.get("notes"),
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            return jsonify({"error": f"Node '{node_id}' already exists"}), 409
        return jsonify({"error": str(e)}), 500

    return jsonify(node), 201
