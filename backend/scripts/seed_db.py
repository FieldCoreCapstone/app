"""Seed the FieldCore database with 14 nodes and 2 months of historical data.

Node ids are integers 1..14 with names auto-derived as field_1..field_14.
Node 1 is the real Arduino hardware node; nodes 2-13 feed from the mock
simulator; node 14 is a spare demo node.
"""

import logging
import math
import random
import sqlite3
from datetime import datetime, timedelta, timezone

from backend import config
from backend.scripts.init_db import init_db

logger = logging.getLogger(__name__)


def seed_db(interval_minutes=30, db_path=None):
    db_path = db_path or config.DATABASE_PATH
    logger.info("Seeding database at: %s with %dm intervals", db_path, interval_minutes)

    # Ensure DB exists
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 0. WIPE OLD DATA (single transaction for atomicity)
        logger.info("Wiping old data...")
        cursor.execute("DELETE FROM readings")
        cursor.execute("DELETE FROM nodes")

        # 1. Create Nodes
        # Integer ids 1..14, names auto-derived as field_N. Node 1 is the
        # real Arduino; nodes 2-13 match the mock simulator's MOCK_NODES;
        # node 14 is a spare demo node.
        nodes = [
            ( 1, 'field_1',  37.4208, -91.5633, '2026-04-20', 'Real hardware node — live Arduino over LoRa, centered in the cluster'),
            ( 2, 'field_2',  37.4190, -91.5645, '2025-12-05', 'Mock node — high ground, sandy soil'),
            ( 3, 'field_3',  37.4210, -91.5610, '2025-12-10', 'Mock node — near the weather station'),
            ( 4, 'field_4',  37.4240, -91.5650, '2026-01-03', 'Mock node — hilltop, windy exposure'),
            ( 5, 'field_5',  37.4178, -91.5700, '2026-01-08', 'Mock node — flood-prone lowland'),
            ( 6, 'field_6',  37.4200, -91.5725, '2026-01-12', 'Mock node — adjacent to stock pond'),
            ( 7, 'field_7',  37.4250, -91.5615, '2026-01-15', 'Mock node — forest-field boundary'),
            ( 8, 'field_8',  37.4170, -91.5580, '2026-01-20', 'Mock node — sheltered low area'),
            ( 9, 'field_9',  37.4235, -91.5570, '2026-02-01', 'Mock node — terraced hillside plot'),
            (10, 'field_10', 37.4195, -91.5550, '2026-02-05', 'Mock node — natural spring nearby'),
            (11, 'field_11', 37.4160, -91.5635, '2026-02-10', 'Mock node — near main access gate'),
            (12, 'field_12', 37.4255, -91.5700, '2026-02-15', 'Mock node — rocky soil, exposed'),
            (13, 'field_13', 37.4215, -91.5540, '2026-02-20', 'Mock node — close to equipment barn'),
            (14, 'field_14', 37.4225, -91.5680, '2025-12-01', 'Spare demo node — adjacent to field_1'),
        ]

        logger.info("Inserting nodes...")
        cursor.executemany(
            "INSERT INTO nodes (id, name, latitude, longitude, installed, notes) VALUES (?, ?, ?, ?, ?, ?)",
            nodes
        )

        # 2. Generate 2 months (60 days) of data (UTC timestamps)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=60)

        logger.info("Generating readings from %s to %s...", start_date.date(), end_date.date())

        # Moisture baselines are expressed as percent (0-100). Keys are integer
        # ids matching the `nodes` table above.
        node_configs = {
             1: {'base_m': 64, 'm_var':  7, 't_offset':  0.0},
             2: {'base_m': 46, 'm_var':  4, 't_offset': -2.0},
             3: {'base_m': 83, 'm_var': 11, 't_offset':  1.5},
             4: {'base_m': 40, 'm_var':  6, 't_offset': -1.0},
             5: {'base_m': 89, 'm_var':  9, 't_offset':  0.5},
             6: {'base_m': 79, 'm_var':  6, 't_offset':  0.8},
             7: {'base_m': 69, 'm_var':  8, 't_offset': -0.5},
             8: {'base_m': 86, 'm_var': 10, 't_offset':  1.0},
             9: {'base_m': 53, 'm_var':  5, 't_offset': -1.5},
            10: {'base_m': 93, 'm_var':  4, 't_offset':  0.3},
            11: {'base_m': 57, 'm_var':  7, 't_offset': -0.8},
            12: {'base_m': 29, 'm_var':  4, 't_offset': -2.5},
            13: {'base_m': 71, 'm_var':  6, 't_offset':  0.2},
            14: {'base_m': 68, 'm_var':  7, 't_offset':  0.1},
        }

        readings_batch = []
        current_time = start_date

        while current_time < end_date:
            hour = current_time.hour
            # Peak at 3pm, Low at 3am
            temp_cycle = 20 + 8 * math.sin((hour - 9) * math.pi / 12)

            for node_id, cfg in node_configs.items():
                moisture = cfg['base_m'] + random.randint(-cfg['m_var'], cfg['m_var'])
                # Add a slow "drying out" trend for the last 10 days
                if (end_date - current_time).days < 10:
                    moisture -= (10 - (end_date - current_time).days)

                temp = temp_cycle + cfg['t_offset'] + random.uniform(-0.5, 0.5)
                # Battery is VCC-health percent (5V rail); stays ~90-100 in normal operation.
                battery = random.randint(90, 100) if (end_date - current_time).days > 30 else random.randint(80, 95)
                rssi = random.randint(-85, -60)

                readings_batch.append((
                    node_id,
                    current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    battery,
                    max(0, min(100, int(moisture))),
                    round(temp, 2),
                    rssi
                ))

            if len(readings_batch) >= 1000:
                cursor.executemany(
                    "INSERT INTO readings (node_id, timestamp, battery, moisture, temperature, signal_rssi) VALUES (?, ?, ?, ?, ?, ?)",
                    readings_batch
                )
                readings_batch = []

            current_time += timedelta(minutes=interval_minutes)

        if readings_batch:
            cursor.executemany(
                "INSERT INTO readings (node_id, timestamp, battery, moisture, temperature, signal_rssi) VALUES (?, ?, ?, ?, ?, ?)",
                readings_batch
            )

        conn.commit()
        logger.info("Seeding complete!")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=30, help="Interval in minutes")
    args = parser.parse_args()
    seed_db(args.interval)
