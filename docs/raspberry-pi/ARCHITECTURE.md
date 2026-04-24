# Raspberry Pi Software Architecture

Technical overview of the software stack running on the FieldCore base station.

## Table of Contents

- [System Overview](#system-overview)
- [Process Architecture](#process-architecture)
- [Data Flow](#data-flow)
- [LoRa Packet Protocol](#lora-packet-protocol)
- [Shared Reading Pipeline](#shared-reading-pipeline)
- [Mock Node Simulation](#mock-node-simulation)
- [Database](#database)
- [Service Management](#service-management)
- [Offline vs Online Operation](#offline-vs-online-operation)

---

## System Overview

The Raspberry Pi runs four independent processes managed by systemd:

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi 4                            │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐  │
│  │ LoRa        │  │ Mock Node   │  │ Flask Web App     │  │
│  │ Listener    │  │ Simulator   │  │ (port 5001)       │  │
│  │             │  │             │  │                   │  │
│  │ Polls radio │  │ 12 fake     │  │ Dashboard +       │  │
│  │ for real    │  │ nodes on    │  │ REST API          │  │
│  │ packets     │  │ 15-min      │  │                   │  │
│  │             │  │ intervals   │  │                   │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬──────────┘  │
│         │                │                   │             │
│         │  process_      │  process_         │ SELECT      │
│         │  reading()     │  reading()        │ queries     │
│         │                │                   │             │
│         └───────┬────────┘                   │             │
│                 │                            │             │
│         ┌───────▼────────────────────────────▼──┐          │
│         │           sensors.db (SQLite)          │          │
│         │     nodes table  |  readings table     │          │
│         └────────────────────────────────────────┘          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Chromium Kiosk (fullscreen)             │   │
│  │              → http://localhost:5001                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                         ▲                                   │
│                         │                                   │
│              ┌──────────┴──────────┐                        │
│              │   Touchscreen       │                        │
│              │   Display           │                        │
│              └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ LoRa 915 MHz
         │
┌────────┴──────────┐
│   Arduino Field   │
│   Node            │
│   (real hardware) │
└───────────────────┘
```

Each process is a separate Python script running as a systemd service. They share the SQLite database file but otherwise have no direct communication. This keeps the system simple — if any one process crashes, the others continue working and systemd restarts the failed one.

## Process Architecture

### LoRa Listener (`services/lora_listener.py`)

A continuous polling loop that receives LoRa packets from the real field node.

**Lifecycle:**
1. Initialize SPI bus and RFM95W radio at 915 MHz
2. Configure radio parameters to match Arduino (SF7, BW125k, CR4/5, CRC off)
3. Enter receive loop: `rfm9x.receive()` with 5-second timeout
4. On packet: strip 4-byte RadioHead header, decode UTF-8, parse CSV
5. Pass parsed data to `process_reading()` for validation and DB insertion
6. On SIGTERM: exit cleanly

**Error handling:** Malformed packets (short, bad encoding, invalid CSV) are logged and discarded. The listener never crashes on bad data — it logs a warning and continues polling.

### Mock Node Simulator (`services/mock_simulator.py`)

Generates realistic sensor data for 12 simulated field nodes, producing readings that are indistinguishable from real hardware data.

**Lifecycle:**
1. Load 12 mock node configurations (moisture profiles, temp offsets, battery voltages)
2. Assign each node a random initial offset (0–15 minutes)
3. Enter main loop: every second, check which nodes are due
4. For due nodes: generate reading using diurnal temperature model, moisture variance, and battery drain
5. Call `process_reading()` — same function the real listener uses
6. On SIGTERM: exit cleanly

**Data realism:**
- **Temperature:** Follows a sinusoidal diurnal cycle peaking at 3 PM and bottoming at 3 AM, with per-node offsets (e.g., shaded areas run cooler, exposed ridges run warmer)
- **Moisture:** Each node has a base moisture level and variance that creates natural scatter. Values stay within realistic bounds for the soil type described in the node's metadata
- **Battery:** Starts at 8.8–9.5V per node and drains ~0.01V per day, simulating real alkaline discharge over weeks
- **RSSI:** Random between -85 and -60 dBm, simulating varying distances and obstructions

### Flask Web App (`app.py`)

The existing FieldCore dashboard, completely unchanged. Reads from SQLite and serves the dashboard UI and REST API on port 5001.

### Chromium Kiosk (`deploy/kiosk.sh`)

A shell script that waits for Flask to be ready, then launches Chromium in fullscreen kiosk mode. Hides the mouse cursor after 3 seconds of inactivity.

## Data Flow

### Real Node (Arduino → Dashboard)

```
Arduino field node
    │
    │ LoRa 915 MHz packet (CSV string)
    ▼
RFM95W radio on Pi (SPI bus)
    │
    │ rfm9x.receive() returns raw bytes
    ▼
LoRa Listener (lora_listener.py)
    │
    │ 1. Strip 4-byte RadioHead header
    │ 2. Decode UTF-8
    │ 3. Read RSSI from rfm9x.last_rssi
    ▼
process_reading(csv_string, rssi)
    │
    │ 1. Parse CSV: node_id, moisture, temperature, battery_voltage
    │ 2. Validate all fields
    │ 3. Convert battery voltage → percentage
    │ 4. Call insert_reading() → SQLite
    ▼
sensors.db (readings table)
    │
    │ Flask reads via GET /api/sensor/latest
    ▼
Dashboard (auto-refreshes every 30 seconds)
```

### Mock Node (Simulator → Dashboard)

```
Mock Simulator (mock_simulator.py)
    │
    │ generate_reading() produces CSV string + fake RSSI
    ▼
process_reading(csv_string, rssi)
    │
    │ (identical path as real node from here)
    ▼
sensors.db → Flask → Dashboard
```

The key design point: from `process_reading()` onward, the paths are identical. The database, API, and dashboard have no knowledge of whether a reading came from hardware or simulation.

## LoRa Packet Protocol

### Packet Format

The Arduino transmits a UTF-8 CSV string over LoRa:

```
1,62,22.5,5161
```

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `node_id` | integer | Positive integer matching `nodes.id` in the DB | `1` |
| `moisture` | integer | Soil moisture percent (0–100) | `62` |
| `temperature` | float | Celsius from SEN0600 | `22.5` |
| `vcc_millivolts` | integer | Arduino 5V rail in millivolts | `5161` |

### What's NOT in the Packet

**RSSI** is not transmitted by the field node. The node cannot measure how well the base station received its signal. Instead, the Pi reads RSSI from the radio hardware after receiving each packet via `rfm9x.last_rssi`.

### RadioHead Header

The Adafruit RFM9x library on the Pi prepends a 4-byte RadioHead-compatible header to every received packet:

| Byte | Purpose | Default |
|------|---------|---------|
| 0 | Destination address | 0xFF (broadcast) |
| 1 | Source address | 0xFF |
| 2 | Packet ID | increments |
| 3 | Flags | 0x00 |

The Arduino's `sandeepmistry/arduino-LoRa` library sends raw packets without this header. The Pi listener strips the first 4 bytes before parsing the CSV payload.

### Radio Configuration

Both radios must use matching settings:

| Parameter | Value | Notes |
|-----------|-------|-------|
| Frequency | 915 MHz | North American ISM band |
| Spreading Factor | 7 | Default, good balance of range/speed |
| Bandwidth | 125 kHz | Default |
| Coding Rate | 4/5 | Default |
| CRC | Disabled | Arduino LoRa library default |
| Sync Word | 0x12 | Default |
| Preamble Length | 8 | Default |

## Shared Reading Pipeline

The `process_reading()` function in `services/reading_processor.py` is the single entry point for all sensor data, real or mock.

### Processing Steps

1. **Parse CSV** — Split on commas, expect exactly 4 fields
2. **Validate types** — node_id is a positive integer, moisture is an integer percent, temperature is a float, vcc_millivolts is an integer
3. **Convert battery** — Map 6xAA voltage to 0–100% using the alkaline discharge curve:

   | Voltage | Percentage | Battery State |
   |---------|-----------|---------------|
   | 9.6V | 100% | Fresh |
   | 7.5V | 60% | Good |
   | 6.5V | 15% | Low — replace soon |
   | 6.0V | 0% | Dead |

   Linear interpolation between these points.

4. **Insert reading** — Write to the `readings` table via `insert_reading(node_id, moisture, temperature, battery_pct, signal_rssi)`

### Error Handling

`process_reading()` raises `ValueError` for any validation failure. Callers (the listener and simulator) catch these, log them, and continue operating. A bad packet never crashes a service.

## Mock Node Simulation

### Node Profiles

Each of the 12 mock nodes uses an integer id matching its row in the `nodes` table and produces visually distinguishable moisture data on the dashboard. Node id `1` is **reserved for the real Arduino hardware** and is absent from the mock list. The dashboard renders the derived `field_N` name for each node:

| Node ID | Display Name | Moisture Profile (percent) | Notes |
|---------|------|-----------------|-------|
| 2 | field_2 | Low (46 ± 4) | Sandy soil, drains fast |
| 3 | field_3 | High (83 ± 10) | Near weather station |
| 4 | field_4 | Low (40 ± 6) | Windy hilltop, dries out |
| 5 | field_5 | Very high (88 ± 8) | Flood-prone lowland |
| 6 | field_6 | High (78 ± 6) | Adjacent to stock pond |
| 7 | field_7 | Mid (68 ± 7) | Forest-field boundary |
| 8 | field_8 | High (85 ± 9) | Sheltered, retains moisture |
| 9 | field_9 | Low-mid (52 ± 5) | Terraced hillside |
| 10 | field_10 | Very high (92 ± 4) | Natural spring nearby |
| 11 | field_11 | Mid (57 ± 7) | Near access gate |
| 12 | field_12 | Very low (28 ± 4) | Rocky, exposed bluff |
| 13 | field_13 | Mid (71 ± 6) | Near equipment barn |

The real hardware node (id `1`, name `field_1`) transmits actual sensor data and is not simulated.

### Staggered Timing

Mock nodes don't all fire at the same time. On startup, each node receives a random offset between 0 and 15 minutes. After the initial offset, each node generates a reading every 15 minutes. This produces a natural-looking pattern of readings arriving throughout the interval.

## Database

The Pi services write to the same `sensors.db` file the Flask app reads. SQLite handles concurrent access from multiple processes via WAL (Write-Ahead Logging) mode.

### Concurrency Model

- **Writers:** LoRa listener + mock simulator (2 processes)
- **Reader:** Flask web app (1 process, many concurrent requests)
- **Write frequency:** ~1 reading per minute across all mock nodes, plus occasional real node packets
- **Contention risk:** Negligible at this scale. SQLite WAL handles this natively.

### Crash Safety

SQLite's WAL mode is crash-safe. If the Pi loses power mid-write, the database will not be corrupted. The WAL file is replayed on next open, recovering any committed transactions.

## Service Management

### Boot Order

```
multi-user.target
    └── fieldcore-web.service         (Flask app)
         ├── fieldcore-lora.service   (LoRa listener, After=web)
         ├── fieldcore-mock.service   (Mock simulator, After=web)
         └── graphical.target
              └── fieldcore-kiosk.service  (Chromium, After=web + graphical)
```

Flask starts first so the database exists. The listener and simulator start after Flask. The kiosk starts last, after both Flask and the desktop environment are ready.

### Restart Behavior

| Service | Restart Policy | Delay |
|---------|---------------|-------|
| fieldcore-web | Always | 3 seconds |
| fieldcore-lora | Always | 5 seconds |
| fieldcore-mock | Always | 5 seconds |
| fieldcore-kiosk | On failure | 10 seconds |

### Useful Commands

```bash
# Check all services
systemctl status fieldcore-*

# View live logs for a service
journalctl -u fieldcore-lora -f

# Restart a service
sudo systemctl restart fieldcore-mock

# Stop everything
sudo systemctl stop fieldcore-web fieldcore-lora fieldcore-mock fieldcore-kiosk

# Start everything
sudo systemctl start fieldcore-web fieldcore-lora fieldcore-mock fieldcore-kiosk
```

## Offline vs Online Operation

The base station works with or without internet:

| Feature | Offline | Online (WiFi) |
|---------|---------|---------------|
| LoRa listener | Works | Works |
| Mock simulator | Works | Works |
| Flask API | Works | Works |
| Dashboard (Canvas view) | Works | Works |
| Dashboard (Map view) | No tiles load | Full interactive map |
| Heatmap overlay | Works | Works |
| Data table & charts | Works | Works |

The Leaflet map view loads tiles from OpenStreetMap and Esri CDNs, which require internet. The Canvas view renders nodes using pure local drawing with no external dependencies. Both views are always accessible via the toggle buttons in the card header.

For demo scenarios without WiFi, the Canvas view is the primary display. When WiFi is available, the Map view with satellite imagery provides richer geographic context.
