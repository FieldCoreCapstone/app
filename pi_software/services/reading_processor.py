"""Shared reading processor for LoRa listener and mock simulator.

Parses CSV packets, validates fields, converts VCC millivolts to a health
percentage, and inserts into SQLite via db.insert_reading().

Both the real LoRa listener and mock simulator call process_reading() so
the validation and insertion path is identical — no "mock mode".

Canonical packet format (matches Arduino output):
    node_id,moisture_pct,temperature_c,vcc_millivolts

Example: `1,45.50,22.20,5161`
    node_id      → positive integer matching the node's DB id (e.g. 1)
    moisture_pct → float 0.0-100.0, rounded to integer percent
    temperature  → float, degrees Celsius
    vcc_mv       → integer millivolts of the Arduino's 5V supply rail
"""

import logging

from services.db import insert_reading

logger = logging.getLogger(__name__)


def vcc_millivolts_to_health_pct(mv):
    """Convert Arduino VCC rail millivolts to a 0-100 health percentage.

    The Arduino reports its own 5V supply rail (not the battery voltage).
    A healthy rail should sit around 4800-5200 mV. Outside that band
    indicates brownout (low) or regulator fault (high).

    4500 mV or below → 0%
    5500 mV or above → 100%
    Linear in between.
    """
    if mv <= 4500:
        return 0
    if mv >= 5500:
        return 100
    return round((mv - 4500) / 10)


def process_reading(csv_string, rssi=None, db_path=None):
    """Parse a CSV reading string and insert into the database.

    CSV format: node_id,moisture_pct,temperature_c,vcc_millivolts
    RSSI is provided separately (from radio metadata or mock generator).

    Returns a dict of the parsed values on success.
    Raises ValueError on malformed input.
    """
    csv_string = csv_string.strip()
    parts = csv_string.split(",")

    if len(parts) != 4:
        raise ValueError(f"Expected 4 CSV fields, got {len(parts)}: {csv_string!r}")

    raw_node_id = parts[0].strip()
    if not raw_node_id:
        raise ValueError("Empty node_id")
    try:
        node_id = int(raw_node_id)
    except ValueError:
        raise ValueError(f"Invalid node_id: {raw_node_id!r}")
    if node_id < 1:
        raise ValueError(f"Invalid node_id: {node_id} (must be >= 1)")

    try:
        moisture = round(float(parts[1].strip()))
        moisture = max(0, min(100, moisture))
    except ValueError:
        raise ValueError(f"Invalid moisture value: {parts[1]!r}")

    try:
        temperature = float(parts[2].strip())
    except ValueError:
        raise ValueError(f"Invalid temperature value: {parts[2]!r}")

    try:
        vcc_mv = int(parts[3].strip())
    except ValueError:
        raise ValueError(f"Invalid VCC millivolts: {parts[3]!r}")

    battery_pct = vcc_millivolts_to_health_pct(vcc_mv)

    reading_id = insert_reading(
        node_id=node_id,
        moisture=moisture,
        temperature=temperature,
        battery=battery_pct,
        signal_rssi=rssi,
        db_path=db_path,
    )

    result = {
        "reading_id": reading_id,
        "node_id": node_id,
        "moisture": moisture,
        "temperature": temperature,
        "vcc_mv": vcc_mv,
        "battery_pct": battery_pct,
        "rssi": rssi,
    }
    logger.info("Inserted reading #%d for %s (moisture=%d%%, temp=%.1f°C, vcc=%dmV)",
                reading_id, node_id, moisture, temperature, vcc_mv)
    return result
