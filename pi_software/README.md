# FieldCore Pi Software

Services that run on the Raspberry Pi base station alongside the Flask web app.

## Architecture

```
Arduino (field node) --LoRa--> RFM95W --SPI--> Pi
                                                 ├── lora_listener.py  → process_reading() → SQLite
                                                 ├── mock_simulator.py → process_reading() → SQLite
                                                 ├── Flask web app (reads SQLite, serves dashboard)
                                                 └── Chromium kiosk (fullscreen dashboard on touchscreen)
```

## Services

| Service | Description |
|---------|-------------|
| `services/lora_listener.py` | Polls LoRa radio for real sensor packets |
| `services/mock_simulator.py` | Generates realistic data for 12 simulated nodes |
| `services/reading_processor.py` | Shared CSV parsing, validation, and DB insertion |
| `services/db.py` | SQLite helpers (WAL mode, same schema as Flask app) |

## Packet Format

The Arduino sends CSV over LoRa: `node_id,moisture,temperature,battery_voltage`

Example: `FIELD_01,450,22.5,8.7`

The Pi reads RSSI from the radio metadata separately.

## Deploy to Pi

```bash
sudo bash deploy/install.sh
sudo reboot
```

This installs four systemd services that auto-start on boot:
- `fieldcore-web` — Flask dashboard
- `fieldcore-lora` — LoRa listener
- `fieldcore-mock` — Mock node simulator
- `fieldcore-kiosk` — Chromium in kiosk mode

## Development

```bash
# Run tests (no Pi hardware needed)
python3 -m pytest tests/ -v

# Run mock simulator standalone
python3 -m services.mock_simulator

# Run LoRa listener (Pi only — needs RFM95W hardware)
python3 -m services.lora_listener
```

## Dependencies

- Python 3.10+
- pytest (dev)
- adafruit-circuitpython-rfm9x (Pi only, for LoRa listener)
- adafruit-blinka (Pi only)
