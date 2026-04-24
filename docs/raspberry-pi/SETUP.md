# Raspberry Pi Base Station Setup

Complete guide for setting up the FieldCore base station on a Raspberry Pi 4.

## Table of Contents

- [Hardware Requirements](#hardware-requirements)
- [Operating System](#operating-system)
- [SPI Configuration](#spi-configuration)
- [Python Dependencies](#python-dependencies)
- [LoRa Radio Wiring](#lora-radio-wiring)
- [Project Installation](#project-installation)
- [Database Initialization](#database-initialization)
- [Service Installation](#service-installation)
- [Touchscreen & Kiosk Mode](#touchscreen--kiosk-mode)
- [Verifying the Installation](#verifying-the-installation)
- [Troubleshooting](#troubleshooting)

---

## Hardware Requirements

| Component | Purpose |
|-----------|---------|
| Raspberry Pi 4 Model B (4GB) | Base station compute |
| Adafruit RFM95W LoRa Radio (915 MHz) | Receives sensor packets from field nodes |
| 915 MHz antenna (RP-SMA or wire) | Required — never power the radio without an antenna |
| Touchscreen display (USB or DSI) | Dashboard display in kiosk mode |
| MicroSD card (32GB+) | OS and application storage |
| USB-C power supply (5V 3A) | Pi power |
| Jumper wires (female-to-female) | SPI connection between Pi and RFM95W |

**Important:** Always connect the antenna to the RFM95W before powering on. Operating the radio without an antenna can damage the SX1276 chip.

## Operating System

Install **Raspberry Pi OS with Desktop** (Bookworm or later). The desktop environment is required for Chromium kiosk mode.

1. Download Raspberry Pi Imager from https://www.raspberrypi.com/software/
2. Flash "Raspberry Pi OS (64-bit)" to the microSD card
3. During imaging, configure:
   - Hostname: `fieldcore`
   - Username: `pi`
   - Password: (your choice)
   - WiFi: configure if available (optional — system works offline)
   - SSH: enable for remote access during setup
4. Boot the Pi and complete initial setup

## SPI Configuration

The LoRa radio communicates over SPI. This must be enabled manually.

```bash
sudo raspi-config
```

Navigate to **Interface Options → SPI → Enable**. Reboot when prompted.

Verify SPI is active:

```bash
ls /dev/spidev*
# Should show: /dev/spidev0.0  /dev/spidev0.1
```

## Python Dependencies

The Pi services require Python 3.10+ (ships with Bookworm) and the following packages:

```bash
# Core dependencies
pip install flask flask-cors pytest

# CircuitPython for LoRa radio (Pi only)
pip install adafruit-blinka adafruit-circuitpython-rfm9x

# Cursor hiding for kiosk mode
sudo apt install -y unclutter
```

**Note:** `adafruit-blinka` and `adafruit-circuitpython-rfm9x` only work on Raspberry Pi hardware. They will fail to install or import on macOS/Windows development machines. The mock simulator and tests run fine without them.

## LoRa Radio Wiring

Connect the RFM95W breakout to the Pi's GPIO header:

| Pi GPIO Pin | RFM95W Pin | Purpose |
|-------------|-----------|---------|
| GPIO 11 (SCLK, pin 23) | SCK | SPI clock |
| GPIO 9 (MISO, pin 21) | MISO | Data from radio to Pi |
| GPIO 10 (MOSI, pin 19) | MOSI | Data from Pi to radio |
| GPIO 7 (CE1, pin 26) | CS | SPI chip select |
| GPIO 25 (pin 22) | RST | Radio hardware reset |
| 3.3V (pin 1 or 17) | VIN | Power (breakout regulates internally) |
| GND (pin 6, 9, 14, 20, 25, 30, 34, or 39) | GND | Common ground |

**Wiring diagram:**

```
Raspberry Pi GPIO Header          RFM95W Breakout
┌─────────────────────┐          ┌──────────────┐
│ Pin 1  (3.3V) ──────┼──────────┤ VIN          │
│ Pin 6  (GND)  ──────┼──────────┤ GND          │
│ Pin 19 (MOSI) ──────┼──────────┤ MOSI         │
│ Pin 21 (MISO) ──────┼──────────┤ MISO         │
│ Pin 22 (GPIO25)─────┼──────────┤ RST          │
│ Pin 23 (SCLK) ──────┼──────────┤ SCK          │
│ Pin 26 (CE1)  ──────┼──────────┤ CS           │
└─────────────────────┘          └──────────────┘
```

After wiring, test the radio:

```bash
cd pi_software
python3 test_receive.py
```

You should see `RFM95W initialized. Listening on 915 MHz...` followed by dots (waiting for packets) or received data.

## Project Installation

Clone the repository and install dependencies:

```bash
cd /home/pi
git clone git@github.com:FieldCoreCapstone/app.git
cd app

# Install Python dependencies
pip install -r requirements.txt
pip install adafruit-blinka adafruit-circuitpython-rfm9x
```

## Database Initialization

The Flask app auto-creates the database on first run. To seed it with the 13-node configuration (1 real + 12 mock):

```bash
cd /home/pi/app

# Start Flask once to create the DB
python3 app.py &
sleep 3

# Seed nodes and historical data
curl -X POST http://localhost:5001/api/seed \
  -H "Content-Type: application/json" \
  -d '{"interval_minutes": 30}'

# Stop Flask (systemd will manage it from now on)
kill %1
```

This creates `backend/sensors.db` with:
- 14 nodes numbered `1`-`14` with names `field_1` through `field_14` (id `1` is the real Arduino; ids `2`-`13` mirror the mock simulator; `14` is a spare demo node)
- 60 days of historical sensor data for charts

## Service Installation

Install all four systemd services:

```bash
cd /home/pi/app
sudo bash pi_software/deploy/install.sh
```

This copies service files to `/etc/systemd/system/`, enables them for boot, and installs `unclutter` for cursor hiding.

Start everything immediately:

```bash
sudo systemctl start fieldcore-web fieldcore-lora fieldcore-mock fieldcore-kiosk
```

Or simply reboot:

```bash
sudo reboot
```

After boot, the dashboard should appear on the touchscreen within 30 seconds.

## Touchscreen & Kiosk Mode

The kiosk service launches Chromium in fullscreen mode pointing at `http://localhost:5001`. It:

- Waits for Flask to respond before opening the browser (up to 30 seconds)
- Runs in `--kiosk` mode (no address bar, no window controls)
- Uses `--incognito` to prevent session restore prompts
- Hides the mouse cursor after 3 seconds of inactivity via `unclutter`

**To exit kiosk mode** (for debugging): Press `Alt+F4` or `Ctrl+Alt+T` to open a terminal.

**Touchscreen calibration:** If touch input is offset, calibrate with:

```bash
sudo apt install -y xinput-calibrator
xinput_calibrator
```

## Verifying the Installation

Check that all services are running:

```bash
systemctl status fieldcore-web fieldcore-lora fieldcore-mock fieldcore-kiosk
```

All four should show `active (running)`.

Check the Flask app:

```bash
curl http://localhost:5001/api/health
# {"status": "ok"}
```

Check that readings are being inserted (mock simulator):

```bash
curl http://localhost:5001/api/sensor/latest | python3 -m json.tool | head -20
```

You should see 13 nodes with recent timestamps.

View service logs:

```bash
# Flask web app
journalctl -u fieldcore-web -f

# LoRa listener
journalctl -u fieldcore-lora -f

# Mock simulator
journalctl -u fieldcore-mock -f

# Kiosk
journalctl -u fieldcore-kiosk -f
```

## Troubleshooting

### Radio not initializing

```
ERROR: Failed to initialize LoRa radio
```

- Verify SPI is enabled: `ls /dev/spidev*`
- Check wiring — especially CS (CE1, pin 26) and RST (GPIO25, pin 22)
- Ensure antenna is connected
- Test with: `python3 pi_software/test_receive.py`

### Dashboard not loading on touchscreen

- Check Flask is running: `systemctl status fieldcore-web`
- Check kiosk service: `systemctl status fieldcore-kiosk`
- View kiosk logs: `journalctl -u fieldcore-kiosk -e`
- Try manually: `chromium-browser --kiosk http://localhost:5001`

### No sensor data appearing

- Check mock simulator: `systemctl status fieldcore-mock`
- Mock nodes fire every 15 minutes with random initial offsets — wait up to 15 minutes after boot for all nodes to appear
- Check for database errors: `journalctl -u fieldcore-mock -e`

### Map tiles not loading (blank map)

- Map tiles require internet (WiFi). Without WiFi, use the Canvas view toggle
- Verify WiFi: `ping -c 3 google.com`
- The Canvas view works fully offline — toggle via the Canvas/Map buttons in the card header

### Service won't start after reboot

- Check that services are enabled: `systemctl is-enabled fieldcore-web`
- Re-run the installer: `sudo bash pi_software/deploy/install.sh`
- Check disk space: `df -h` (SQLite writes will fail if the SD card is full)
