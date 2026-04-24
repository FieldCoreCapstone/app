---
title: "refactor: Graph view cleanup — move tabs to chart, add metric toggle, fix class collision"
type: refactor
status: completed
date: 2026-04-24
origin: docs/brainstorms/graph-view-cleanup-requirements.md
---

# refactor: Graph view cleanup — move tabs to chart, add metric toggle, fix class collision

## Overview

Move the dashboard's time-range tabs out of the top bar and into the chart card, add a moisture/temperature metric toggle, update the range set to `15m / 1h / 12h / 24h / 7d / 1m / 3m` (drop `1y`), and make every dashboard surface — map, table, and chart — refresh on one 3s timer. Fix a latent class collision between the top time bar and the map's Canvas/Map toggle. Add explicit loading, empty, and error states to the chart card.

(see origin: docs/brainstorms/graph-view-cleanup-requirements.md)

## Problem Frame

Today the top-of-dashboard tab strip looks like a global control but only drives the chart. Any non-Live selection silently freezes the map and table via `stopAutoRefresh()` in `static/js/main.js:823-826`. The chart itself is locked to moisture (`main.js:284-371`), even though `/api/sensor/history` already returns `avg_temperature` too. Two button groups share `class="time-btn"` — after the top bar is removed, the leftover `setupTimeButtons()` handler would fire on every Canvas/Map click with `undefined` args. The cleanup fixes all four in one pass.

## Requirements Trace

- **R1.** Top time-range bar is gone from the page. (origin Success #1)
- **R2.** Chart card has a single control row: metric toggle + range chips. (origin Success #2)
- **R3.** Clicking `Temperature` swaps the chart to temperature lines with `°C` y-axis and tooltip suffix. (origin Success #3)
- **R4.** Map, table, and chart all tick on one 3s timer; no selection freezes anything. (origin Success #4 + Dashboard liveness)
- **R5.** Map's Canvas/Map toggle works and no longer shares a class with chart controls. (origin Success #5)
- **R6.** Default load state: `Moisture` + `7d`; chart renders immediately. (origin Success #6)
- **R7.** `/api/sensor/history?range=<k>` returns 200 for `15m, 1h, 12h, 24h, 7d, 1m, 3m` and 400 for `1y`; tests cover the new surface. (origin Success #7)
- **R8.** No regressions in Leaflet map, heatmap, or sensor table. (origin Success #8)
- **R9.** Chart shows explicit Loading, Empty, and Error states. (origin Chart states section)
- **R10.** Metric/range selection does not persist across reloads; every page load resets to `Moisture` + `7d`. (origin Initial load section)

## Scope Boundaries

- No node filtering / per-series show-hide (Chart.js legend click still handles it).
- No battery or RSSI chart metrics.
- No dashboard redesign beyond the graph area.
- No Chart.js replacement; no new frontend build tooling.
- No Arduino or LoRa listener changes.
- No localStorage persistence of chart state.
- No keyboard/a11y polish beyond what Chart.js gives for free — LAN use is secondary.

## Context & Research

### Relevant Code and Patterns

- **Segmented-control pattern to mirror:** `.mcp-btn` / `.mcp-btn.active` in `static/css/style.css:361-390` is the in-map control panel's segmented button style. Same visual language we want for the chart's metric toggle. Active state convention across the codebase: dark bg `var(--accent)` + white fg + `font-weight: 600`; inactive: white bg + `var(--btn-border)` + `var(--text-mid)`; hover: `#EDF2F7`.
- **Chart.js usage:** `static/js/main.js:315-317` uses `historyChart.destroy()` + `new Chart(...)` on every render. No existing `.update()` call. We considered introducing `historyChart.update('none')` for auto-refresh ticks to avoid flashing, but see the Key Technical Decisions section below — the plan ships with **always destroy+rebuild** for simplicity, and adds an in-place update path only if kiosk testing reveals visible flash.
- **No existing loading/empty/error pattern for Chart.js.** `loadHistory()` (`main.js:785-792`) currently `console.error`s on failure. Closest precedent is the heatmap swapping to a 1x1 transparent GIF on insufficient data (`main.js:601-607`) — not reusable. We are establishing the pattern.
- **Frontend module layout:** `static/js/heatmap.js` defines globals that `static/js/main.js` reads. No bundler, no ES modules. All dashboard state lives as module-level `let` globals in `main.js` (`historyChart`, `currentRange`, `activeMetric`, `lastReadings`). Add chart state the same way.
- **Existing `activeMetric`:** `main.js:44, 93, 483, 486, 599, 658` drives map heatmap and marker coloring, plus `renderHeatmapCanvas()` in `heatmap.js`. Do not rename it. Introduce a new `chartMetric` for the chart.
- **Test layout:** `tests/conftest.py:11-29` exposes a single `client` fixture that sets `FIELDCORE_DB=tmp_path/test.db`, reloads `backend.config` + `app`, runs `init_db()`, yields `app.test_client()`. Every API test takes `client` as its only fixture. Group new tests by class in `tests/test_api.py::TestSensors`.

### Institutional Learnings

- None — `docs/solutions/` does not exist. This is the first durable planning artifact of its kind in this repo.

### External References

- Not consulted — codebase has strong local patterns for every layer this plan touches.

## Key Technical Decisions

- **One 3s timer drives everything.** `refreshDashboard()` stays the single interval callback. It calls `fetchLatest()` (map + table) and also kicks off a chart refresh for the current `(chartMetric, currentRange)` with `isAutoRefresh: true`. No second timer.
- **Always destroy+rebuild the chart.** Every `loadHistory` call destroys the existing `historyChart` and constructs a new one — same pattern as today (`main.js:315-317`). Simpler than branching between in-place update and rebuild, and sidesteps label-drift glitches when a new minute bucket rolls in on `15m`/`1h` views. If the Pi visibly flashes on each 3s tick, add a narrow in-place-update path for the auto-refresh case only, at that point.
- **`AbortController` on chart fetches.** Captured as a module-level `chartAbort` reference. Before committing render on any response, guard with `if (myController !== chartAbort) return;` — this protects against the stale-commit race where a fetch resolves just before a newer click aborts its controller.
- **No auto-fetch stacking.** If an auto-refresh fetch is still pending when the next 3s tick fires, the next tick no-ops instead of aborting and re-issuing. Prevents livelock on a slow Pi (fetch >3s would otherwise auto-abort forever). User clicks always abort any in-flight fetch and start fresh.
- **Null handling for `avg_temperature`:** emit `null` to Chart.js (rendered as gaps, `spanGaps: false`), never coerce to `0`. A missing sample must not become a phantom 0 °C point.
- **Delete `setupTimeButtons()` entirely.** Do not try to rescope its selector. The new chart controls bind their own handlers (`.chart-metric-btn`, `.chart-range-btn`).
- **Rename Canvas/Map toggle to `.view-toggle-btn`.** Update **both** of `setupViewToggle`'s `.view-toggle .time-btn` selectors (`main.js:725` and `main.js:731`) to `.view-toggle .view-toggle-btn`. The `.time-btn` class is retired from the codebase.
- **Default range `7d` lives in one place.** Update `backend/routes/sensors.py` default from `"24h"` to `"7d"`. Frontend default stays at `7d` as today. Prevents silent divergence if the frontend ever fires a range-less request.
- **Y-axis per metric:** Moisture keeps `min:0, max:100` hard clamp. Temperature uses `suggestedMin:0, suggestedMax:40` with no hard clamp so outlier readings (direct sun, brownout-garbage) still show.
- **No localStorage.** Metric+range reset to `Moisture` + `7d` on every page load. Predictable over "personalized".
- **`chartMetric` vs `activeMetric` — distinct state.** A comment block in `main.js` at the state declarations must call out the split: `chartMetric` drives the chart card only; `activeMetric` drives the map heatmap/markers (read by `updateHeatmap`, `getMarkerColor`, and passed into `renderHeatmapCanvas`). Never cross-wire them.

## Open Questions

### Resolved During Planning

- **Auto-refresh cadence for long ranges (3m):** Same 3s as short ranges. Destroy+rebuild is cheap; SQLite is local; simpler mental model. If the Pi visibly flashes on each 3s tick, revisit as a follow-up.
- **Chart update pattern:** Always `historyChart.destroy()` + `new Chart(...)` on every `loadHistory` call — same pattern as today (`main.js:315-317`). No `.update('none')` in-place path. Starting with one rendering mode removes a whole class of label-drift and in-flight-commit races; if the Pi kiosk visibly flashes, add in-place update for the auto-tick path at that point.
- **Where to put the initial fetch:** Inside `init()` after `setupChartMetricButtons()` and `setupChartRangeButtons()` are wired up, not as part of the first tick. Ensures a visible `Loading` state on first paint.
- **Loading spinner source:** Pure CSS keyframe animation, no dependency. Mirrored via a `.chart-loading` overlay positioned absolutely over the chart canvas. The overlay only mounts on **user-initiated** and **initial** loads, not on 3s auto-refresh ticks — otherwise the kiosk flashes the spinner every 3 seconds.
- **`isAutoRefresh` boolean:** `loadHistory(range, metric, { isAutoRefresh = false })` takes a single boolean. Auto-refresh callers pass `true`; user clicks and init pass `false` (default). Drives both loading-overlay suppression and error-state suppression.
- **Tests audit of `tests/ui_tests.py`:** Before landing any unit, open that file and see what it actually covers. If it exercises the dashboard via Selenium/Playwright and touches the `.time-btn` class or old range set, extend it as part of Unit 4 verification (treat as "Modify" in that unit's Files). If it's unrelated or dead, note it in Risks and move on.
- **Seed DB cadence note for dev:** `backend/scripts/seed_db.py` seeds at 15 or 30 minute intervals (per its `interval_minutes` arg). On a freshly seeded dev DB, the `15m` range will almost always hit the Empty state — this is correct behavior, not a bug. First-run dev verification should use the `1h` or `24h` range.
- **Plan file path for tests:** UI interaction tests stay manual for new behavior (no JS unit framework). API tests extend `tests/test_api.py::TestSensors`.

### Deferred to Implementation

- Exact `strftime` bucket granularity for `15m` and `1h` — plan spec uses minute buckets; implementer verifies live data renders cleanly and adjusts to finer buckets only if samples collapse too aggressively.
- Chart x-axis tick formatting (the existing `YYYY-MM-DD HH:MM` string labels are ugly at 15m). Implementer picks a compact tick formatter via Chart.js `ticks.callback`.
- Whether rapid metric/range toggle benefits from a 150ms debounce on top of AbortController. Measure first.
- Specific CSS `:active` pressed-state appearance and `@media (pointer: coarse)` tweaks — implementer picks values that feel right on the kiosk. Touch-target **dimensions** are specified in Unit 3; only the pressed-state visual is deferred.
- Whether the chart card's in-flight latency ever exceeds 3s on the Pi against realistic DB size. Measurement decides whether the "auto-refresh tick no-op if auto fetch pending" rule needs a secondary cadence for long ranges.

## Implementation Units

- [ ] **Unit 1: Backend — update range contract and tests**

**Goal:** Extend `_RANGE_MAP` with `15m / 1h / 12h`; drop `1y`; update `VALID_RANGES` to match; change default range to `7d`; update and extend `tests/test_api.py` coverage.

**Requirements:** R7

**Dependencies:** None — pure backend, can land first and verified before any UI work.

**Files:**
- Modify: `backend/models/database.py` (`_RANGE_MAP`)
- Modify: `backend/routes/sensors.py` (`VALID_RANGES`, default range)
- Modify: `tests/test_api.py` (extend `TestSensors`)
- Test: `tests/test_api.py` (same file — new/updated cases)

**Approach:**
- `_RANGE_MAP` keys: `15m, 1h, 12h, 24h, 7d, 1m, 3m`. Bucket expressions:
  - `15m`, `1h` → `strftime('%Y-%m-%d %H:%M', timestamp)`
  - `12h`, `24h`, `7d` → `strftime('%Y-%m-%d %H:00', timestamp)` (unchanged for 24h/7d)
  - `1m`, `3m` → `strftime('%Y-%m-%d', timestamp)`
- `VALID_RANGES = {"15m", "1h", "12h", "24h", "7d", "1m", "3m"}`.
- `request.args.get("range", "24h")` becomes `request.args.get("range", "7d")`.
- The error message at `backend/routes/sensors.py:25` auto-formats from the set — no string update needed.

**Patterns to follow:**
- `_RANGE_MAP` tuple shape `(since_expr, group_expr)` is already established at `backend/models/database.py:98-104`. Keep both expressions as trusted constants.
- Test class structure: add to existing `TestSensors` class in `tests/test_api.py`. Use the `client` fixture. Seed a node with `self._add_node(client)` and a reading before fetching history.

**Test scenarios:**
- *Happy path (parametrized)* — a single test method loops over `["15m", "1h", "12h"]` and asserts `GET /api/sensor/history?range=<k>` returns 200 with a JSON list. Keeps coverage without three copy-pasted methods.
- *Happy path* — `GET /api/sensor/history` (no `range` param) returns 200 with the same shape as `?range=7d`, proving the default changed.
- *Error path* — `GET /api/sensor/history?range=1y` returns 400. (The existing `test_history_valid_range` test uses `?range=24h` and should stay green without change; read the file to confirm it doesn't iterate over `VALID_RANGES`.)
- *Error path* — existing `test_history_invalid_range` (with `?range=invalid`) still returns 400; the error message auto-formats from the set and now lists the new valid ranges.
- *Happy path* — with one seeded reading, `GET /api/sensor/history?range=1h` returns a list of length ≥ 1. (Using `1h`, not `15m`, because `seed_db.py` seeds at 15-minute intervals — a `15m` window on a fresh seed can legitimately return zero rows.)

**Verification:**
- `pytest tests/test_api.py::TestSensors -v` passes end-to-end.
- `curl http://localhost:5001/api/sensor/history?range=15m` returns 200 when the server is running against a seeded DB.

---

- [ ] **Unit 2: Template restructure and `app.py` context cleanup**

**Goal:** Remove the top `.time-bar` from `templates/index.html`; add a new controls row inside `.chart-card`; rename the Canvas/Map toggle buttons off `class="time-btn"`; strip the now-unused `time_ranges` context from `app.py`.

**Requirements:** R1, R2, R5

**Dependencies:** None — template and app.py can change together. Unit 4 depends on this markup existing.

**Files:**
- Modify: `templates/index.html`
- Modify: `app.py`

**Approach:**
- Delete the entire top `<div class="time-bar"> … </div>` block (lines 17-21 today).
- Inside `<div class="card chart-card">`, after the existing `<div class="card-title">Historical Trends</div>`, insert a new `<div class="chart-controls">` containing:
  - A `<div class="chart-metric-group">` holding two `<button class="chart-metric-btn" data-metric="moisture">Moisture</button>` and `<button class="chart-metric-btn" data-metric="temperature">Temperature</button>` (the `moisture` one gets `active` class for default).
  - A `<div class="chart-range-group">` holding seven `<button class="chart-range-btn" data-range="…">` buttons for `15m, 1h, 12h, 24h, 7d, 1m, 3m` in that order (the `7d` one gets `active` for default).
- Change the two Canvas/Map buttons (currently `class="time-btn" data-view="canvas/map"`, lines 32-33 today) to `class="view-toggle-btn"` — drop `time-btn` entirely from the codebase after this unit + Unit 3.
- In `app.py`, remove the `time_ranges = [...]` list near the bottom of the `index()` view and drop the `time_ranges=time_ranges` kwarg from `render_template(...)`. The template no longer consumes it.

**Patterns to follow:**
- Markup style matches the existing `.mcp-btn-group` pattern in `templates/index.html` if it appears there, otherwise matches the structure of the current `.time-bar` button list (plain `<button>` tags with `data-` attributes).
- Keep the `data-` attribute naming consistent: `data-metric` and `data-range` (singular, lowercase).

**Test scenarios:**
- Test expectation: none — structural markup change. Behavioral coverage is exercised by Unit 1 (backend API) and Unit 4 (frontend wiring). Verified manually by rendering the page and confirming no duplicate `.time-btn` elements remain via `document.querySelectorAll('.time-btn').length === 0`.

**Verification:**
- Page loads without JS errors. `grep -rn "time-btn" templates/ static/ static/css/` returns zero hits after Unit 3 also ships.
- `grep -rn "time_ranges" app.py templates/` returns zero hits.

---

- [ ] **Unit 3: CSS — style new controls and chart-state overlays**

**Goal:** Style `.chart-controls`, `.chart-metric-btn`, `.chart-range-btn`, and the new `.chart-loading` / `.chart-empty` / `.chart-error` overlays. Update `.view-toggle`'s scoped selector. Remove now-orphaned `.time-btn` rules.

**Requirements:** R2, R5, R9

**Dependencies:** Unit 2 (markup exists).

**Files:**
- Modify: `static/css/style.css`

**Approach:**
- **Chart controls row:** `.chart-controls` uses `display: flex; gap: 16px; align-items: center; flex-wrap: wrap; padding: 8px 0 12px` so it sits under the card title. Inner groups `.chart-metric-group` and `.chart-range-group` each use `display: flex; gap: 8px; flex-shrink: 0` so they wrap as whole units (never splitting individual chips across rows).
- **Metric + range buttons:** mirror the `.mcp-btn` visual from `style.css:361-390` — rounded corners, border, white bg, `var(--text-mid)` fg; `.active` applies `var(--accent)` bg + white fg + `font-weight: 600`. Chips are **≥36px tall** and **≥44px wide** (WCAG 2.5.5 minimum) with `padding: 0 14px`. Chips within a group have **8px gap**; the two groups have **16px gap** between them, so a fat-finger miss cannot jump across groups.
- **`.chart-wrap`** gets `position: relative` and `min-height: 300px` so state overlays render at a stable card height even when the canvas is unmounted or empty.
- **`.chart-loading`** — absolutely-positioned center-flex container with a 32px CSS `@keyframes spin` spinner (border-based, no SVG).
- **`.chart-empty`** — absolutely-positioned centered text label with `color: var(--text-mid)`. The text is set from JS (see Unit 4) as `No <metric> readings in the last <range>` using the active metric and range labels.
- **`.chart-error`** — absolutely-positioned centered message with `color: var(--text-mid)` + a `.chart-error-retry` button directly below. Style `.chart-error-retry` independently using the same `.mcp-btn` token pattern (do not depend on `.chart-metric-btn` cascading — avoids unit-ordering risk). The retry button gets a `:disabled` state that fades the button and blocks additional taps while a retry fetch is in flight.
- **View-toggle scoped selector:** replace both occurrences of `.view-toggle .time-btn` in the CSS (search the full file, not a line-range guess) with `.view-toggle .view-toggle-btn`.
- **Delete:** all `.time-btn` and `.time-btn.active` rules in the stylesheet (top-level and any scoped) plus the old `.time-bar` container rule. Grep the file first: `grep -n 'time-btn\|time-bar' static/css/style.css`.

**Patterns to follow:**
- CSS variables in `:root` at `static/css/style.css:10-29` (`--accent`, `--btn-border`, `--text-mid`).
- Section banner comments (`/* ── Section ── */`).

**Test scenarios:**
- Test expectation: none — pure styling change. Verified manually: buttons render in the right card, active state visible, spinner animates, overlays center correctly at 1920×1080 and narrower viewports.

**Verification:**
- No horizontal scrollbars at ≥1280px width.
- Metric and range active states visually distinct from inactive.
- Spinner animates continuously when `.chart-loading` is mounted on the chart container (manually toggle via devtools).

---

- [ ] **Unit 4: Frontend JS — chart state, handlers, auto-refresh, metric-aware renderChart**

**Goal:** Wire up the new chart controls; fold chart refresh into the existing 3s dashboard timer; refactor `renderChart` to take `(metric, data)` and handle Loading/Empty/Error states; remove the old dashboard-freezing branch; delete `setupTimeButtons()`; fix the `.time-btn` selector collision; update `setupViewToggle`.

**Requirements:** R2, R3, R4, R5, R6, R9, R10, R8 (regression-free)

**Dependencies:** Units 1, 2, 3.

**Files:**
- Modify: `static/js/main.js`

**Approach:**

*State (top-of-file block, with a comment clarifying intent)*
- Introduce `let chartMetric = 'moisture';` — chart-card state only.
- Keep existing `let activeMetric = 'moisture';` (`main.js:44`) untouched — drives the map heatmap/markers.
- Add a comment banner above both declarations spelling out which is which and pointing to `heatmap.js::renderHeatmapCanvas` as a downstream consumer of `activeMetric`. This prevents future readers from cross-wiring them.
- Add `let chartAbort = null;` for the in-flight AbortController.
- Change `let currentRange = 'Live';` to `let currentRange = '7d';`. After this refactor, `currentRange` is a raw API key (`'15m'`, `'1h'`, …) that matches the `data-range` attribute value — no label-to-key translation layer.
- **`RANGE_MAP` goes away.** Delete it at `main.js:16-23`. The button `data-range` values *are* the API keys now; no mapping needed.

*Handlers*
- Delete `setupTimeButtons()` entirely. Run `grep -n 'setupTimeButtons\|stopAutoRefresh' static/js/ templates/` to confirm no remaining callers; delete `stopAutoRefresh()` at the same time if the grep comes back clean. (Legacy reasoning: `stopAutoRefresh` was only called from the removed historical-range branch.)
- Add `setupChartMetricButtons()` that queries `.chart-metric-btn`, binds click. Click handler:
  1. Read `btn.dataset.metric`. If equal to `chartMetric`, return (no-op).
  2. Update active class; set `chartMetric = newMetric`.
  3. Call `loadHistory(currentRange, chartMetric)` (no options — default `isAutoRefresh: false`).
- Add `setupChartRangeButtons()` that queries `.chart-range-btn`, binds click. Same shape — guard, update active class, set `currentRange = btn.dataset.range`, call `loadHistory(...)`.
- Update `setupViewToggle()` — replace both `.view-toggle .time-btn` selectors at `main.js:725` and `main.js:731` with `.view-toggle .view-toggle-btn`. Behavior unchanged.

*Fetch + render*
- New `loadHistory(range, metric, { isAutoRefresh = false } = {})`:
  1. If `isAutoRefresh && chartAbort !== null`: an auto fetch is already pending → `return` (no-op). Prevents livelock on a slow Pi.
  2. If user-initiated and `chartAbort !== null`: `chartAbort.abort()` the prior. (User clicks always win.)
  3. If **not** `isAutoRefresh`: show the `.chart-loading` overlay. On auto ticks, the overlay stays hidden so the kiosk never flashes a spinner on the 3s cadence.
  4. Create `const myController = new AbortController(); chartAbort = myController;`.
  5. `fetch('/api/sensor/history?range=' + range, { signal: myController.signal })`.
  6. On response: before committing anything, check `if (myController !== chartAbort) return;` — prevents a just-resolved stale request from winning a race against a newer one. Then clear `chartAbort = null`.
  7. On success: hide loading overlay; if `data.length === 0`, show `.chart-empty` with text `No ${metricLabel} readings in the last ${rangeLabel}` (use `chartMetric` and `currentRange` to build); else call `renderChart(metric, data)`.
  8. On `AbortError`: do nothing (a newer call owns the pipeline).
  9. On any other failure, branch on `isAutoRefresh`:
     - `true` → log only. Leave the last populated chart visible. No overlay change.
     - `false` → hide loading, show `.chart-error` with message + Retry button. Retry click: disable the button, call `loadHistory(range, metric, { isAutoRefresh: false })` which re-enters the same path (Loading overlay replaces the error card). Re-enable the retry button only if the error recurs.
- New `renderChart(metric, data)`:
  - Pick `avg_moisture` or `avg_temperature` off each row based on `metric`.
  - Convert null/undefined metric values to `null` (not `0`) in the dataset.
  - y-axis config driven by metric:
    - `moisture`: `{ min: 0, max: 100, title: 'Moisture %' }`, tooltip suffix `%`.
    - `temperature`: `{ suggestedMin: 0, suggestedMax: 40, title: 'Temperature (°C)' }`, tooltip suffix ` °C`, one decimal.
  - Always: `historyChart?.destroy(); historyChart = new Chart(ctx, { ... });` (same pattern as today at `main.js:315-319`). `spanGaps: false` so null temperature points show as breaks.

*Auto-refresh wiring*
- `refreshDashboard()` (existing, fires every 3s) keeps its existing map/table refresh, and at the end calls `loadHistory(currentRange, chartMetric, { isAutoRefresh: true })`.
- The resize handler at `main.js:851-856` calls `refreshDashboard()` on window resize; this naturally picks up the `isAutoRefresh: true` path since it goes through the same function — no change needed there.
- `startAutoRefresh()` is called unconditionally on init.

*Init*
- `init()` sequence: init Leaflet → `fetchLatest()` → update markers/heatmap/table → `setupChartMetricButtons()` → `setupChartRangeButtons()` → `setupViewToggle()` → `startAutoRefresh()` → one explicit `loadHistory('7d', 'moisture')` (no options, default `isAutoRefresh: false`) so the first paint shows a Loading state.

*Audit `tests/ui_tests.py`*
- Open the file. If it tests any of: the removed top time bar, the `.time-btn` class, the `'24 Hours'` etc. label strings, or the old `1y` range — either update the assertions to match the new surface, or, if the file is effectively dead, note it in Risks and skip.

**Execution note:** Treat Unit 4 as one atomic change — partial landings leave the UI in a broken state (e.g., markup exists but handlers don't bind). Verify by hand in the browser after each section: metric toggle, range chip, auto-refresh, Canvas/Map toggle, Leaflet heatmap, table refresh.

**Patterns to follow:**
- Module-level `let` globals for state (`main.js:34-47`).
- `fetch` + `.then` style used in `fetchLatest()` / `fetchHistory()` (`main.js:103-115`).
- Chart.js options object shape already present at `main.js:319-370`.

**Test scenarios:**
- Test expectation: none (automated) — no JS test framework in the repo. Manual browser verification is required:
  - *Happy path* — Load dashboard. Chart paints within ~1s showing Moisture over 7d. Map and table populate.
  - *Happy path* — Click `Temperature`. Chart re-renders with °C y-axis, temperature series, no flash-then-snap. Click `Moisture` — reverses cleanly.
  - *Happy path* — Click `15m`. Fetch fires, Loading overlay appears briefly, chart re-renders scoped to 15m.
  - *Happy path* — Leave dashboard open for 30 seconds; chart updates smoothly every 3s without destroy/rebuild flash (verify via DevTools Performance tab — no Chart.js construction events on each tick).
  - *Edge case* — Rapid-click `15m → 1h → 12h → 7d`. Only the final range's data renders (AbortController cancels the prior fetches).
  - *Edge case* — Click already-active metric or range: no fetch fires (check Network tab).
  - *Edge case* — Empty `15m` on a cold DB: `No readings in this range` message centered in the chart area.
  - *Error path* — Stop the Flask server; refresh the page. Chart shows `Could not load history` + Retry. Click Retry with server down: same error. Restart server; click Retry: chart loads.
  - *Error path* — Temp-drop the server for ~4 seconds while the dashboard is open. 3s auto-refresh tick fails silently; prior chart stays visible; no error flash.
  - *Regression check* — Canvas/Map toggle still swaps between views.
  - *Regression check* — Leaflet heatmap still renders and updates with new readings.
  - *Regression check* — Sensor table still updates every 3s.
  - *Reload behavior* — Switch to Temperature + 1h, reload page. Comes back at Moisture + 7d (no persistence).

**Verification:**
- All manual scenarios above pass on the Pi in kiosk mode and on a dev Mac in Chrome.
- Broad grep returns zero hits: `grep -rn 'time-btn\|time_btn\|timeBtn' . --include='*.html' --include='*.css' --include='*.js' --include='*.py' --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules`. This catches kebab-case, snake_case, and camelCase references that a single narrow grep would miss.
- `grep -n 'setupTimeButtons\|stopAutoRefresh' static/js/` returns zero hits after the refactor.
- `grep -n 'RANGE_MAP' static/js/main.js` returns zero hits (the constant is deleted).
- During 30s of auto-refresh, the page does not visibly flash. If it does, revisit the "always destroy+rebuild" decision and add an in-place update for auto ticks (see Key Technical Decisions).

## System-Wide Impact

- **Interaction graph:** The 3s `refreshTimer` now has one additional callback leg (chart refresh). No new timers or observers.
- **Error propagation:** Chart fetch failures are isolated to the chart card — they do not suppress map/table refresh. AbortError is explicitly swallowed. Network errors on auto-refresh ticks are logged only; Error state surfaces only on first-load and user-initiated retry.
- **State lifecycle risks:** In-flight fetch can race with a new user click. `AbortController` covers this. Multiple rapid clicks cannot produce duplicate Chart.js instances because each `loadHistory` call first aborts the prior.
- **API surface parity:** `/api/sensor/history` query-string contract changes (range set). Anyone bookmarking `?range=1y` sees a 400 instead of silently-200-with-empty. Acceptable given this is a single-deployment capstone with no external consumers. Update `docs/API.md` if it enumerates the range set — implementer checks.
- **Integration coverage:** Unit tests exercise backend alone. End-to-end chart↔DB↔API integration is manually verified because no frontend test framework exists.
- **Unchanged invariants:**
  - `/api/sensor/latest` response shape.
  - `/api/sensor/history` JSON row shape (keys still `node_id, period, avg_moisture, avg_temperature, avg_battery, sample_count`).
  - The `nodes` table schema, `readings` table schema, and existing `REFRESH_MS = 3000`.
  - Leaflet markers, heatmap canvas, Canvas/Map toggle behavior.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Chart.js `.update('none')` with changed dataset labels causes visual glitches | Keep the `rebuild: true` path for metric/range changes where labels change; only use in-place update for auto-refresh ticks where dataset shape is the same. If glitches appear, fall back to destroy+rebuild on every tick; kiosk is local so perf cost is real but bounded. |
| AbortController rapid-click cancels the legit auto-refresh tick | Auto-refresh initiates its own abort token. A user click aborts prior in-flight (both auto and user). The next 3s tick issues a fresh request. Worst case is one skipped tick. |
| `docs/API.md` documents the old range set and drifts | Implementer checks and updates if the file enumerates ranges. Low-effort, catches downstream confusion. |
| Removing `1y` breaks anyone's bookmarks / scripts | No external consumers for this capstone. 400 response has a clear error message. Acceptable. |
| 15m bucket granularity (`%Y-%m-%d %H:%M`) collapses too aggressively at higher sample rates | Currently sample rate is minutes apart at best (real LoRa cadence). Future 3s LoRa would mean 20 samples per minute bucket, still fine. Revisit only if observed. |
| Unit 4 partial landing leaves the UI broken | Execution note on Unit 4 flags atomic landing. CI does not catch this (no JS tests). |

## Documentation / Operational Notes

- **`docs/API.md` updates** (both of these are real drift and should land with Unit 1):
  - Line 63 enumerates the range set as `24h | 7d | 1m | 3m | 1y` — replace with `15m | 1h | 12h | 24h | 7d | 1m | 3m`.
  - Line 92 mentions "every 30 seconds" for dashboard auto-refresh — this is already stale vs. the current `REFRESH_MS = 3000` (3 seconds). Fix the number while you're in the file.
- No migration or rollout work. No feature flag. Single-node Pi deployment; SSH in, `git pull`, `sudo systemctl restart fieldcore-web` — that's the whole rollout.
- No monitoring changes.

## Sources & References

- **Origin document:** [docs/brainstorms/graph-view-cleanup-requirements.md](../brainstorms/graph-view-cleanup-requirements.md)
- Related code:
  - `backend/models/database.py` — `_RANGE_MAP`
  - `backend/routes/sensors.py` — `VALID_RANGES`, `/api/sensor/history`
  - `static/js/main.js` — chart, auto-refresh, RANGE_MAP, view toggle
  - `static/css/style.css` — segmented-control patterns
  - `templates/index.html` — dashboard markup
  - `tests/test_api.py::TestSensors` — range tests
  - `tests/conftest.py` — `client` fixture
