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
- **Power:** LiFePO4 Battery + Adafruit TPL5110 Power Timer
- **Housing:** NSF-61 PVC Pipe

## Pinout Configuration

| Component        | Arduino Pin | Notes                         |
| :--------------- | :---------- | :---------------------------- |
| **RFM95W MOSI**  | 11          | SPI Bus                       |
| **RFM95W MISO**  | 12          | SPI Bus                       |
| **RFM95W SCK**   | 13          | SPI Bus                       |
| **RFM95W NSS**   | 10          | Chip Select                   |
| **TPL5110 Done** | 4           | Pull HIGH to signal sleep [5] |
| **Sensor RX/TX** | 2, 3        | SoftwareSerial                |

## LoRa Data Contract

> **CRITICAL:** The node must transmit data in the exact string format below to be compatible with the Receiving Station.

**Format:**
```text
"Temperature,Moisture"
```

**Example:**
```text
"24.5,523"
```

**Details:**
* **Temperature:** Float (Celsius)
* **Moisture:** Integer (Raw capacitance value)
* **Max Packet Size:** <20 Bytes

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
├── docs/         # Wiring diagrams and TPL5110 logic
└── libraries/    # Custom sensor drivers and dependencies
```
