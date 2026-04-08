# FieldCore Database

## Architecture

| Component | Detail |
| :--- | :--- |
| **Database Engine** | SQLite (WAL mode) |
| **File Location** | `backend/sensors.db` (configurable via `FIELDCORE_DB` env var) |
| **Init Script** | `backend/scripts/init_db.py` |
| **Seed Script** | `backend/scripts/seed_db.py` |

The database uses a **normalized design** with two primary tables:

1. **`nodes`** — Stores static configuration: node identity, geographic coordinates, and metadata.
2. **`readings`** — Stores the immutable time-series history of every sensor packet received.

## Schema

### `nodes`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `node_id` | TEXT | PRIMARY KEY | Unique sensor node identifier (e.g., `NORTH_01`) |
| `name` | TEXT | NOT NULL | Human-readable name (e.g., "North Corn Field") |
| `latitude` | REAL | NOT NULL | Latitude coordinate |
| `longitude` | REAL | NOT NULL | Longitude coordinate |
| `installed` | DATE | | Installation date |
| `notes` | TEXT | | Free-text notes |

### `readings`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Auto-incrementing row ID |
| `node_id` | TEXT | NOT NULL, FK -> nodes | References the source sensor node |
| `timestamp` | DATETIME | NOT NULL, DEFAULT now (UTC) | When the reading was recorded |
| `battery` | INTEGER | | Battery level percentage |
| `moisture` | INTEGER | | Raw soil capacitance value (0-700) |
| `temperature` | REAL | | Temperature in Celsius |
| `signal_rssi` | INTEGER | | LoRa signal strength (dBm) |

### Indexes

| Index | Columns | Purpose |
| :--- | :--- | :--- |
| `idx_readings_node_time` | `node_id`, `timestamp DESC` | Fast lookup for latest readings per node and time-range queries |

## Configuration

| Setting | Description |
| :--- | :--- |
| `PRAGMA journal_mode=WAL` | Write-Ahead Logging for better concurrent read performance |
| `PRAGMA foreign_keys=ON` | Enforces referential integrity between readings and nodes |

## Timestamps

All timestamps are stored in **UTC** using SQLite's `datetime('now')` default. The seed script generates UTC timestamps. History queries use SQLite date functions which operate in UTC.

## Data Flow

```text
Sensor Node --(LoRa)--> Receiving Station --(POST /api/sensor/reading)--> SQLite
                                                                             |
Dashboard <--(GET /api/sensor/latest)-- Flask <-- SQLite queries ------------+
           <--(GET /api/sensor/history)--
```

## Initialization

The database is automatically created on first app startup if the file does not exist. To manually initialize:

```bash
python -m backend.scripts.init_db
```

## Seeding Test Data

The seed script generates 13 nodes with 60 days of realistic sensor data including diurnal temperature cycles, per-node moisture profiles, and a 10-day drying trend.

```bash
# Via Python
python -c "from backend.scripts.seed_db import seed_db; seed_db()"

# Via API (debug mode only)
curl -X POST http://localhost:5001/api/seed -H "Content-Type: application/json" -d '{"interval_minutes": 30}'
```

**Warning:** Seeding wipes all existing data (nodes and readings) before inserting fresh data.
