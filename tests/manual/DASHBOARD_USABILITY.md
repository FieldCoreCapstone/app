# Manual Test Checklist — Dashboard Usability

These rows exercise the dashboard from a user's perspective — visual rendering,
map interaction, chart controls. Automate-able pieces are in `tests/ui_tests.py`;
this file covers the rendering and interaction nuances a test runner can't see.

**How to set up:**

```bash
./start.sh --seed     # wipe and seed with 60 days of data
# Open http://localhost:5001 in a browser
```

**Tester:** _______________   **Date:** _______________

---

## Page Load

- [ ] **Page load (no errors):** Open the dashboard. Map, table, and chart render with no errors in the browser console.
  - **Notes:**

---

## Map (Leaflet view)

- [ ] **14 markers:** The map shows 14 colored circle markers at the correct geographic positions for the seeded nodes.
  - **Notes:**

- [ ] **Marker popup:** Clicking a marker opens a popup with the node name, moisture %, temperature, battery %, and signal RSSI.
  - **Notes:**

- [ ] **Popup link:** A "View in table" link inside the popup scrolls the table into view and highlights the matching row.
  - **Notes:**

- [ ] **Tile toggle:** The tile toggle switches between street and satellite tiles without other visual changes.
  - **Notes:**

---

## Map (Canvas view)

- [ ] **View toggle:** Switching to the Canvas view hides the Leaflet map and renders the node circles on the canvas.
  - **Notes:**

---

## Heatmap Overlay

- [ ] **Heatmap renders:** The IDW heatmap overlay shows a smooth color gradient matching moisture levels at each sensor.
  - **Notes:**

- [ ] **Heatmap toggle:** Toggling the heatmap off then on removes and restores both the overlay image and the legend.
  - **Notes:**

- [ ] **Metric toggle (map):** Switching the map metric to Temperature recolors the heatmap and markers to the temperature scale.
  - **Notes:**

---

## Chart Card

- [ ] **Time range chips:** Clicking each chip (15m, 1h, 12h, 24h, 7d, 1m, 3m) updates the chart.
  - **Notes:**

- [ ] **Metric toggle (chart):** The chart Moisture/Temperature toggle redraws the chart with the correct y-axis.
  - **Notes:**

- [ ] **Legend hidden series persist:** Click a series in the chart legend to hide it. Wait for the next auto-refresh (~3 s). The series stays hidden.
  - **Notes:**

- [ ] **Chart empty/error states:** With an empty time window, the chart shows an "Empty" overlay (no broken renders).
  - **Notes:**

---

## Auto-Refresh

- [ ] **Live refresh:** With the dashboard open, post a new reading via `curl` (or wait for the mock simulator). Within ~3 seconds, the new value appears in the table and map without a page reload.
  - **Notes:**

---

## Responsive Layout

- [ ] **Window resize:** Resize the browser from narrow to wide. The layout adapts (cards stack on narrow, side-by-side on wide) without scroll-bar overlap.
  - **Notes:**

---

## Sign-Off

- [ ] All above pass or have a documented exception.

**Verified by:** _______________   **Date:** _______________
