# Manual Test Checklist — Arduino Field Node

These tests require the physical Arduino, soil-moisture sensor (Modbus RS-485),
and the RFM95W LoRa radio. Run them on the bench before deploying a node.

**Tester:** _______________   **Date:** _______________
**Firmware commit:** _______________

---

## How to Run

1. Connect the Arduino to USB and open the Serial Monitor at 9600 baud.
2. Connect the soil-moisture sensor to the Modbus pins (or disconnect for negative tests).
3. Wire the RFM95W to its SPI pins (or disconnect for negative tests).
4. For battery-mode tests, swap USB for the 6×AA pack.

---

## Sensor Read (Modbus)

- [ ] **readRegister (moisture):** Upload firmware. Serial Monitor shows moisture register raw value > 0 (not `-1`).
  - **Expected:** Plausible reading in wet soil; near zero in dry sand.
  - **Notes:**

- [ ] **readRegister (temp):** Temperature register returns a raw value (not `-1`) close to ambient room temperature.
  - **Notes:**

- [ ] **readRegister failure path:** Disconnect the sensor. Serial Monitor prints a sensor-not-responding warning, no crash.
  - **Notes:**

- [ ] **Partial response:** Briefly disconnect mid-read. Serial Monitor prints `Noise or wrong baud` (or equivalent).
  - **Notes:**

- [ ] **modbusCRC:** Successful read prints `CRC OK` (or equivalent). Bad checksum prints a CRC-fail message.
  - **Notes:**

- [ ] **Sensor values plausibility:** Moisture and temp readings make physical sense — moisture rises when the probe is in wet soil, falls when in air; temperature is within ±5 °C of room temperature.
  - **Notes:**

---

## Voltage Read (VCC Rail, mV)

The Arduino reports its own 5 V supply rail as integer millivolts. Healthy
range: 4500–5500 mV. The Pi-side maps this linearly to a 0–100 health %.

- [ ] **USB power:** Serial Monitor shows VCC ≈ 5000 mV (±100) when powered via USB.
  - **Notes:**

- [ ] **Battery pack power:** With 6×AA installed, VCC reads in the 4500–5500 mV band as the regulator outputs the 5 V rail.
  - **Notes:**

- [ ] **Brownout warning:** Drop input voltage (low batteries or bench supply ≤ 4400 mV). Serial Monitor prints `LOW` or similar; Pi-side health % drops below 10 %.
  - **Notes:**

---

## Packet Format & LoRa

- [ ] **CSV format:** Serial output shows a CSV with exactly 4 fields: `nodeID,moisture,temperature,vcc_mv` (e.g. `1,46,22.5,5161`).
  - **Notes:**

- [ ] **CSV types:** node_id is integer, moisture is integer percent, temperature is float (one decimal), vcc_mv is integer.
  - **Notes:**

- [ ] **Node ID:** The configured node ID constant matches the first CSV field on every transmission.
  - **Notes:**

- [ ] **LoRa send success:** Serial Monitor prints a "sent" confirmation after each transmission.
  - **Notes:**

- [ ] **LoRa send failure:** Disconnect the RFM95W. Firmware reports the error on serial and does not crash.
  - **Notes:**

---

## Sleep & Wake Cycle

- [ ] **Software sleep:** After transmit, the Arduino enters sleep for the configured interval. Verify with a stopwatch: serial goes quiet, then resumes after the interval.
  - **Notes:**

- [ ] **Wake + re-read:** After sleep, the next cycle successfully reads the sensor and sends a fresh packet.
  - **Notes:**

- [ ] **Continuous run:** Leave the node running for at least 10 full cycles. No crashes, no hangs, no garbage data on serial.
  - **Notes:**

---

## Sign-Off

- [ ] All tests above either pass or have a documented reason for failure.
- [ ] Node is ready for field deployment.

**Verified by:** _______________   **Date:** _______________
