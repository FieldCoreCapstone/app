"""Shared reading processor for LoRa listener and mock simulator.

Parses CSV packets, validates fields, converts battery voltage to
percentage, and inserts into SQLite via db.insert_reading().

Both the real LoRa listener and mock simulator call process_reading()
so the validation and insertion path is identical — no "mock mode".
"""

import logging

from services.db import insert_reading, node_exists

logger = logging.getLogger(__name__)

# 6xAA alkaline battery curve (linear interpolation)
# 9.6V = 100% (fresh), 7.5V ≈ 60%, 6.5V ≈ 15%, 6.0V = 0% (dead)
_BATTERY_CURVE = [
    (9.6, 100),
    (7.5, 60),
    (6.5, 15),
    (6.0, 0),
]


def voltage_to_battery_pct(voltage):
    """Convert battery voltage (6xAA pack) to percentage (0-100).

    Uses linear interpolation between known points on the
    alkaline discharge curve. Clamps to 0-100.
    """
    if voltage >= _BATTERY_CURVE[0][0]:
        return 100
    if voltage <= _BATTERY_CURVE[-1][0]:
        return 0

    for i in range(len(_BATTERY_CURVE) - 1):
        v_high, pct_high = _BATTERY_CURVE[i]
        v_low, pct_low = _BATTERY_CURVE[i + 1]
        if v_low <= voltage <= v_high:
            t = (voltage - v_low) / (v_high - v_low)
            return round(pct_low + t * (pct_high - pct_low))

    return 0


def process_reading(csv_string, rssi=None, db_path=None):
    """Parse a CSV reading string and insert into the database.

    CSV format: node_id,moisture,temperature,battery_voltage
    RSSI is provided separately (from radio metadata or mock generator).

    Returns a dict of the parsed values on success.
    Raises ValueError on malformed input.
    """
    csv_string = csv_string.strip()
    parts = csv_string.split(",")

    if len(parts) != 4:
        raise ValueError(f"Expected 4 CSV fields, got {len(parts)}: {csv_string!r}")

    node_id = parts[0].strip()
    if not node_id:
        raise ValueError("Empty node_id")

    try:
        moisture = int(parts[1].strip())
    except ValueError:
        raise ValueError(f"Invalid moisture value: {parts[1]!r}")

    try:
        temperature = float(parts[2].strip())
    except ValueError:
        raise ValueError(f"Invalid temperature value: {parts[2]!r}")

    try:
        battery_voltage = float(parts[3].strip())
    except ValueError:
        raise ValueError(f"Invalid battery voltage: {parts[3]!r}")

    battery_pct = voltage_to_battery_pct(battery_voltage)

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
        "battery_voltage": battery_voltage,
        "battery_pct": battery_pct,
        "rssi": rssi,
    }
    logger.info("Inserted reading #%d for %s (moisture=%d, temp=%.1f°C, bat=%d%%)",
                reading_id, node_id, moisture, temperature, battery_pct)
    return result
