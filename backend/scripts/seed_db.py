"""Seed the FieldCore database with 3 nodes and 2 months of historical data."""

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

        # 1. Create 3 Nodes
        nodes = [
            ('NORTH_01', 'North Corn Field', 38.942, -92.325, '2025-12-01', 'Near the drainage ditch'),
            ('SOUTH_02', 'South Soy Plot', 38.935, -92.321, '2025-12-05', 'High ground, sandy soil'),
            ('EAST_03', 'East Pasture', 38.939, -92.315, '2025-12-10', 'Near the weather station'),
        ]

        logger.info("Inserting nodes...")
        cursor.executemany(
            "INSERT INTO nodes (node_id, name, x, y, installed, notes) VALUES (?, ?, ?, ?, ?, ?)",
            nodes
        )

        # 2. Generate 2 months (60 days) of data (UTC timestamps)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=60)

        logger.info("Generating readings from %s to %s...", start_date.date(), end_date.date())

        node_configs = {
            'NORTH_01': {'base_m': 450, 'm_var': 50, 't_offset': 0},
            'SOUTH_02': {'base_m': 320, 'm_var': 30, 't_offset': -2},
            'EAST_03': {'base_m': 580, 'm_var': 80, 't_offset': 1.5},
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
                    moisture -= (10 - (end_date - current_time).days) * 5

                temp = temp_cycle + cfg['t_offset'] + random.uniform(-0.5, 0.5)
                battery = random.randint(85, 100) if (end_date - current_time).days > 30 else random.randint(70, 85)
                rssi = random.randint(-85, -60)

                readings_batch.append((
                    node_id,
                    current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    battery,
                    max(0, int(moisture)),
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
