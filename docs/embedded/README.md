# FieldCore Firmware (Field Nodes)

> **Status:** Development / Prototype  
> **Hardware Target:** Arduino Uno + RFM95W LoRa Transceiver  
> **Maintainers:** Carson Agee, Ian Cooper, Nate Spencer

## Overview

This repository contains the embedded C++ firmware for the FieldCore autonomous sensor nodes. These nodes are designed to be buried in the field to monitor soil conditions. They operate on a cycle: wake up on a timer, read soil data, transmit via LoRa, and return to deep sleep to conserve power.

## Hardware Manifest

To build a single node, you will need the following components:

- **Microcontroller:** Arduino Uno R3
- **Radio:** HopeRF RFM95W LoRa Transceiver (915 MHz)
- **Sensor:** RS485 Modbus Soil Sensor (Moisture & Temperature)
- **Power:** 6×AA battery pack (5 V regulated rail). Sleep is handled in firmware — no external power timer.
- **Housing:** NSF-61 PVC Pipe

## Pinout Configuration

| Component        | Arduino Pin | Notes                         |
| :--------------- | :---------- | :---------------------------- |
| **RFM95W MOSI**  | 11          | SPI Bus                       |
| **RFM95W MISO**  | 12          | SPI Bus                       |
| **RFM95W SCK**   | 13          | SPI Bus                       |
| **RFM95W NSS**   | 10          | Chip Select                   |
| **Sensor RX/TX** | 2, 3        | SoftwareSerial                |

## LoRa Data Contract

> **CRITICAL:** The node must transmit data in the exact string format below to be compatible with the Receiving Station.

**Format:**
```text
"node_id,moisture_pct,temperature_c,vcc_millivolts"
```

**Example:**
```text
"1,46,22.5,5161"
```

**Details:**
* **node_id:** Integer (matches the node's row in the Pi database)
* **moisture_pct:** Integer 0-100 (already a percent — Modbus raw value is converted on the Arduino)
* **temperature_c:** Float, degrees Celsius
* **vcc_millivolts:** Integer mV of the Arduino's 5 V supply rail
* **Max Packet Size:** <30 Bytes

## Setup & Flashing

1. **Install Tools:** Download and install the [Arduino IDE](https://www.arduino.cc/en/software).
2. **Install Libraries:** Install `RadioHead` (for LoRa) and `SoftwareSerial` via the Library Manager.
3. **Open Project:** Open `src/main.ino` in the Arduino IDE.
4. **Connect Hardware:** Plug in the Arduino via USB and select the correct Port/Board in `Tools`.
5. **Upload:** Click the **Upload** button (arrow icon).

## Folder Structure

```text
/
├── src/          # Main source code (main.ino)
├── docs/         # Wiring diagrams and sleep-cycle logic
└── libraries/    # Custom sensor drivers and dependencies
```
