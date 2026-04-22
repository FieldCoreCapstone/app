"""Seed the FieldCore database with 13 nodes and 2 months of historical data."""

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
        # node_id '1' matches the int the Arduino sends as nodeID.
        # Legacy 'FIELD_01' kept alongside for historical continuity.
        nodes = [
            ('1',        'Arduino Field Node', 37.4225, -91.5680, '2026-04-20', 'Real hardware node — live Arduino over LoRa'),
            ('FIELD_01', 'Primary Field Node', 37.4225, -91.5680, '2025-12-01', 'Legacy mock identifier — retained for history'),
            ('SOUTH_02', 'South Soy Plot',      37.4190, -91.5645, '2025-12-05', 'Mock node — high ground, sandy soil'),
            ('EAST_03',  'East Pasture',         37.4210, -91.5610, '2025-12-10', 'Mock node — near the weather station'),
            ('RIDGE_04', 'Ridge Alfalfa',        37.4240, -91.5650, '2026-01-03', 'Mock node — hilltop, windy exposure'),
            ('CREEK_05', 'Creek Bottom West',    37.4178, -91.5700, '2026-01-08', 'Mock node — flood-prone lowland'),
            ('POND_06',  'Pond Field',           37.4200, -91.5725, '2026-01-12', 'Mock node — adjacent to stock pond'),
            ('TIMBER_07','Timber Edge North',    37.4250, -91.5615, '2026-01-15', 'Mock node — forest-field boundary'),
            ('HOLLOW_08','Hollow Meadow',        37.4170, -91.5580, '2026-01-20', 'Mock node — sheltered low area'),
            ('BENCH_09', 'Bench Terrace',        37.4235, -91.5570, '2026-02-01', 'Mock node — terraced hillside plot'),
            ('SPRING_10','Spring Fed Plot',      37.4195, -91.5550, '2026-02-05', 'Mock node — natural spring nearby'),
            ('GATE_11',  'Gate Field South',     37.4160, -91.5635, '2026-02-10', 'Mock node — near main access gate'),
            ('BLUFF_12', 'Bluff Overlook',       37.4255, -91.5700, '2026-02-15', 'Mock node — rocky soil, exposed'),
            ('BARN_13',  'Barn Lot East',        37.4215, -91.5540, '2026-02-20', 'Mock node — close to equipment barn'),
        ]

        logger.info("Inserting nodes...")
        cursor.executemany(
            "INSERT INTO nodes (node_id, name, latitude, longitude, installed, notes) VALUES (?, ?, ?, ?, ?, ?)",
            nodes
        )

        # 2. Generate 2 months (60 days) of data (UTC timestamps)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=60)

        logger.info("Generating readings from %s to %s...", start_date.date(), end_date.date())

        # Moisture baselines are expressed as percent (0-100).
        node_configs = {
            '1':         {'base_m': 64, 'm_var': 7, 't_offset': 0},
            'FIELD_01':  {'base_m': 64, 'm_var': 7, 't_offset': 0},
            'SOUTH_02':  {'base_m': 46, 'm_var': 4, 't_offset': -2},
            'EAST_03':   {'base_m': 83, 'm_var': 11, 't_offset': 1.5},
            'RIDGE_04':  {'base_m': 40, 'm_var': 6, 't_offset': -1},
            'CREEK_05':  {'base_m': 89, 'm_var': 9, 't_offset': 0.5},
            'POND_06':   {'base_m': 79, 'm_var': 6, 't_offset': 0.8},
            'TIMBER_07': {'base_m': 69, 'm_var': 8, 't_offset': -0.5},
            'HOLLOW_08': {'base_m': 86, 'm_var': 10, 't_offset': 1.0},
            'BENCH_09':  {'base_m': 53, 'm_var': 5, 't_offset': -1.5},
            'SPRING_10': {'base_m': 93, 'm_var': 4, 't_offset': 0.3},
            'GATE_11':   {'base_m': 57, 'm_var': 7, 't_offset': -0.8},
            'BLUFF_12':  {'base_m': 29, 'm_var': 4, 't_offset': -2.5},
            'BARN_13':   {'base_m': 71, 'm_var': 6, 't_offset': 0.2},
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
