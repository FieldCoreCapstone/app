# Manual Test — Full Hardware End-to-End

The definitive "soil-to-screen" test. Confirms the complete path:

```
sensor → Arduino → LoRa → Pi (lora_listener) → process_reading → SQLite
       → Flask API → dashboard
```

**Tester:** _______________   **Date:** _______________
**Hardware:** Arduino #_____,   Pi #_____,   Sensor #_____

---

## Setup

1. Power on the Raspberry Pi base station; confirm the Flask app is running:
   ```bash
   curl http://<pi-ip>:5001/api/health
   # → {"status":"ok"}
   ```
2. Confirm `lora_listener.py` is running on the Pi (systemd service `fieldcore-lora`
   or manual `python -m services.lora_listener`).
3. Place the Arduino field node within LoRa range, sensor probe in soil or test medium.
4. Power on the Arduino (USB or battery pack).
5. Open the dashboard at `http://<pi-ip>:5001/` in a browser.

---

## Verification

- [ ] **Packet in log:** Within one transmit interval, `lora_listener` logs receipt of a CSV packet from the node.
  - Log line includes: node_id, moisture, temperature, vcc_mv, RSSI.
  - **Notes:**

- [ ] **Reading in API:** Query the latest endpoint and confirm the just-received reading appears:
  ```bash
  curl http://<pi-ip>:5001/api/sensor/latest | jq '.[] | select(.node_id == 1)'
  ```
  - **Notes:**

- [ ] **Marker on dashboard:** Within ~3 seconds (auto-refresh tick), the node's marker on the map shows the updated moisture level, and the table row updates.
  - **Notes:**

- [ ] **Chart updates:** With the chart on Moisture, 15m or 1h range, the new reading shows up as a new point on the relevant node's series.
  - **Notes:**

- [ ] **End-to-end latency:** Measure: time-of-sensor-read on Arduino serial vs. time-of-dashboard-update. Record the observed latency.
  - **Observed latency:** _______________
  - **Notes:**

---

## Stress Pass (Optional)

- [ ] Power-cycle the Arduino and verify the next packet arrives correctly after re-init.
- [ ] Move the Arduino to the maximum LoRa range expected in deployment; confirm packets still arrive (note RSSI).

---

## Sign-Off

- [ ] All required rows pass.
- [ ] Any failures are documented above with the node + Pi + sensor IDs.

**Verified by:** _______________   **Date:** _______________
