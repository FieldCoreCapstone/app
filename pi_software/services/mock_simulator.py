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

# Each mock node: (node_id, base_moisture, moisture_variance, temp_offset, initial_voltage)
MOCK_NODES = [
    ("RIDGE_04",  280, 40, -1.0,  9.3),
    ("CREEK_05",  620, 60,  0.5,  9.1),
    ("POND_06",   550, 45,  0.8,  9.4),
    ("TIMBER_07", 480, 55, -0.5,  9.2),
    ("HOLLOW_08", 600, 70,  1.0,  8.9),
    ("BENCH_09",  370, 35, -1.5,  9.5),
    ("SPRING_10", 650, 30,  0.3,  9.0),
    ("GATE_11",   400, 50, -0.8,  9.3),
    ("BLUFF_12",  200, 25, -2.5,  9.1),
    ("BARN_13",   500, 45,  0.2,  9.4),
    ("SOUTH_02",  320, 30, -2.0,  9.2),
    ("EAST_03",   580, 80,  1.5,  8.8),
]


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down...", signum)
    _running = False


def generate_reading(node_config, start_time):
    """Generate a single realistic reading for a mock node."""
    node_id, base_m, m_var, t_offset, init_voltage = node_config

    now = datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60.0

    # Diurnal temperature cycle: peak at 3pm, low at 3am
    temp = 20 + 8 * math.sin((hour - 9) * math.pi / 12)
    temp += t_offset + random.uniform(-0.5, 0.5)

    # Moisture with per-node variance
    moisture = base_m + random.randint(-m_var, m_var)
    moisture = max(0, moisture)

    # Battery drain: ~0.01V per day from initial voltage
    elapsed_days = (time.time() - start_time) / 86400
    voltage = init_voltage - 0.01 * elapsed_days
    voltage = max(5.5, round(voltage, 2))

    rssi = random.randint(-85, -60)

    csv_string = f"{node_id},{moisture},{temp:.2f},{voltage}"
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
