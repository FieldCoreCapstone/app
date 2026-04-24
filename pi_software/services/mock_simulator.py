"""Mock node simulator — generates realistic sensor data for demo nodes.

Produces readings for 12 simulated field nodes at staggered 15-minute
intervals, feeding them through the same process_reading() pipeline as
the real LoRa listener. The dashboard cannot distinguish real from mock.

Data patterns mirror the seed script: diurnal temperature cycles, per-node
moisture profiles with variance, and gradual battery drain.

Run: python3 -m services.mock_simulator
"""

import logging
import math
import random
import signal
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mock_simulator")

_running = True

INTERVAL_SECONDS = 900  # 15 minutes

# Each mock node: (node_id, base_moisture_pct, moisture_variance, temp_offset, initial_vcc_mv)
# node_id is an integer matching the `nodes.id` PK in the database. Ids 2-13
# are used; id=1 is reserved for the real Arduino hardware node.
# Moisture is percent (0-100). VCC is millivolts of the Arduino 5V rail.
MOCK_NODES = [
    ( 2, 46,  4, -2.0, 5120),
    ( 3, 83, 10,  1.5, 4980),
    ( 4, 40,  6, -1.0, 5100),
    ( 5, 88,  8,  0.5, 5080),
    ( 6, 78,  6,  0.8, 5150),
    ( 7, 68,  7, -0.5, 5120),
    ( 8, 85,  9,  1.0, 5050),
    ( 9, 52,  5, -1.5, 5180),
    (10, 92,  4,  0.3, 5000),
    (11, 57,  7, -0.8, 5100),
    (12, 28,  4, -2.5, 5080),
    (13, 71,  6,  0.2, 5150),
]


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down...", signum)
    _running = False


def generate_reading(node_config, start_time):
    """Generate a single realistic reading for a mock node.

    Returns a CSV string matching the Arduino's output format:
        node_id,moisture_pct,temperature_c,vcc_millivolts
    """
    node_id, base_m, m_var, t_offset, init_vcc_mv = node_config

    now = datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60.0

    # Diurnal temperature cycle: peak at 3pm, low at 3am
    temp = 20 + 8 * math.sin((hour - 9) * math.pi / 12)
    temp += t_offset + random.uniform(-0.5, 0.5)

    # Moisture percent with per-node variance, clamped 0-100
    moisture = base_m + random.randint(-m_var, m_var)
    moisture = max(0, min(100, moisture))

    # VCC millivolts drift slowly (regulators stay near nominal until
    # the battery gets very low). Small wander to look alive.
    elapsed_days = (time.time() - start_time) / 86400
    vcc_mv = init_vcc_mv - int(2 * elapsed_days) + random.randint(-15, 15)
    vcc_mv = max(4500, min(5500, vcc_mv))

    rssi = random.randint(-85, -60)

    csv_string = f"{node_id},{moisture}.00,{temp:.2f},{vcc_mv}"
    return csv_string, rssi


def main():
    from services.reading_processor import process_reading

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    start_time = time.time()

    # Assign each node a random initial offset (0 to INTERVAL_SECONDS)
    # so they don't all fire simultaneously
    node_schedules = {}
    for config in MOCK_NODES:
        node_id = config[0]
        offset = random.randint(0, INTERVAL_SECONDS)
        node_schedules[node_id] = {
            "config": config,
            "next_fire": start_time + offset,
        }

    logger.info("Mock simulator started with %d nodes (interval: %ds)", len(MOCK_NODES), INTERVAL_SECONDS)
    for node_id, sched in sorted(node_schedules.items()):
        delay = int(sched["next_fire"] - start_time)
        logger.info("  %s: first reading in %ds", node_id, delay)

    while _running:
        now = time.time()

        for node_id, sched in node_schedules.items():
            if now >= sched["next_fire"]:
                csv_string, rssi = generate_reading(sched["config"], start_time)
                try:
                    process_reading(csv_string, rssi=rssi)
                except Exception:
                    logger.exception("Failed to process mock reading for %s", node_id)

                sched["next_fire"] = now + INTERVAL_SECONDS

        # Sleep briefly to avoid busy-waiting
        time.sleep(1)

    logger.info("Mock simulator stopped.")


if __name__ == "__main__":
    main()
