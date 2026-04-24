# Graph View Cleanup — Requirements

**Date:** 2026-04-24
**Status:** Ready for planning
**Owner:** Alex / wex

## Problem

The dashboard's time-range tabs (`Live / 24 Hours / 7 Days / 1 Month / 3 Months / 1 Year`) sit at the top of the page, but functionally they only drive the chart. This creates two problems:

1. **Misleading scope.** The tab strip looks global. In reality, selecting a historical range also *freezes* the map/table (auto-refresh is disabled in `loadHistory` vs `refreshDashboard` paths). "Live" is secretly a dashboard mode, not a time range.
2. **Graph controls are sparse.** The chart is locked to moisture. There are no affordances for switching metric, even though `get_history()` already returns `avg_temperature` and `avg_battery` (`backend/models/database.py:125-127`).

## Goals

- Move time-range tabs into the graph card, so their scope is visually obvious.
- Add a metric toggle (moisture ↔ temperature) to the chart.
- Decouple "dashboard freeze" from chart time range — nothing on the dashboard ever freezes. Map, table, and chart all auto-refresh on one 3s timer.
- Align range options with what matters in the field: `15m / 1h / 12h / 24h / 7d / 1m / 3m`.
- Keep the change tight. No node filtering, no aggregation toggles, no threshold bands — the graph stays focused.

## Non-goals

- Node filtering / show-hide lines (Chart.js legend click already hides individual nodes; good enough for now).
- Battery or RSSI as chart metrics (not useful as trend lines day-to-day).
- Dashboard redesign beyond the graph area.
- Replacing Chart.js.
- Any Arduino or LoRa listener changes.

## Users and use

Primary: Alex, using the Pi dashboard in kiosk mode on a 15.6" touchscreen. Secondary: anyone viewing the Flask app over LAN. Touch targets need to be finger-sized.

## User-facing behavior

### Layout

Single combined control row inside the chart card, directly under the card title:

```
┌─ Historical Trends ──────────────────────────────────────┐
│  [Moisture|Temp]  15m 1h 12h 24h 7d 1m 3m                │
│                                                          │
│     (chart fills the rest of the card)                   │
└──────────────────────────────────────────────────────────┘
```

The top-of-page time-range bar (`templates/index.html:17-21`) is removed entirely. Only the map card's Canvas/Map toggle (currently bottom of that same top area) stays where it is — inside the map card header, which it already is.

### Metric toggle

- Two-segment control: `Moisture` | `Temperature`.
- Default on load: `Moisture`.
- Selecting a metric re-renders the chart with the corresponding series. Dataset key comes from the existing `/api/sensor/history` response (`avg_moisture` or `avg_temperature`).
- The y-axis label, y-axis range, and tooltip units update with the metric.
- `null` / missing `avg_temperature` values emit as Chart.js null points (gaps), not coerced to `0`. Prevents phantom 0 °C lines for nodes with partial rows.
- Clicking the already-active metric is a no-op (no re-fetch, no redraw).

### Time range chips

- Seven chips: `15m`, `1h`, `12h`, `24h`, `7d`, `1m`, `3m`. Exactly one selected at a time.
- Default on load: `7d` (matches the current default in `main.js:849`).
- Selecting a range re-fetches `/api/sensor/history?range=<key>` for the currently active metric and re-renders.
- Clicking the already-active range chip is a no-op (no re-fetch, no redraw).
- `1y` is dropped. Not useful at the current data scale; can be re-added later if needed.

### Initial load

On page load, the chart immediately issues one fetch for `Moisture` + `7d` and renders on return. No user interaction needed.

Metric and range **do not persist** across reloads or kiosk reboots. Every page load resets to `Moisture` + `7d`. Predictable starting state is more valuable here than remembered preference.

### Chart states

The chart card must render four distinct states:

1. **Loading** — while a fetch is in flight. Show a centered spinner over the chart area. Chips and the metric toggle remain clickable (a new click cancels the prior request via `AbortController`).
2. **Populated** — normal line chart. This is the steady state during 3s auto-refresh.
3. **Empty** — API returned `[]` (e.g. `15m` range on a cold DB). Hide axes; show centered text `No readings in this range`.
4. **Error** — API returned 4xx/5xx or fetch threw. Show centered text `Could not load history` and a `Retry` button (≥36px tall) that re-issues the same request.

When auto-refresh ticks fail, stay on the last populated chart and silently log — only surface the Error state on the *first* failed load or after a user-initiated retry. Goal: transient network blips don't flash errors across the kiosk.

### Temperature y-axis

Moisture uses a hard `min: 0, max: 100` clamp (matches current `main.js:359-360`). Temperature uses `suggestedMin: 0, suggestedMax: 40` with no hard clamp, so outlier readings (a sensor in direct sun, a brownout sending garbage) still render. Tooltip suffix `°C`, one decimal place.

### Dashboard liveness

- Map and table auto-refresh every 3s regardless of chart state. The existing `REFRESH_MS = 3000` timer (`main.js:12`) runs continuously; there is no "Live mode" toggle.
- **The chart also auto-refreshes every 3s** for the currently selected `(metric, range)`. This keeps a `15m` view honest and avoids the kiosk-staleness trap where a frozen chart diverges from a ticking map.
- Chart refresh is triggered from the same 3s interval that drives the map/table — one timer, not two.
- To avoid out-of-order renders when the user rapidly switches range or metric, use an `AbortController` (or a monotonic sequence token) so a prior in-flight request can't overwrite a newer response.
- The `renderChart` path must not flash on each 3s tick. Either reuse `historyChart.update()` when the dataset shape is unchanged, or gate the `destroy()+rebuild` path to metric/range changes only.

### Removal of mode-switching behavior

Today, clicking any historical range calls `stopAutoRefresh()` and `loadHistory()`, which freezes the map and table (`main.js:823-826`). After this change, that branch disappears. Picking `3m` on the chart does not affect the map or table.

## Business-logic alignment

This is the "business logic matches the UI" piece.

| Concern | Today | After |
|---|---|---|
| What do the tabs control? | Chart data *and* map/table freeze | Chart data only |
| Does selecting "Live" do anything? | Yes — resumes map/table auto-refresh | N/A — there is no Live tab |
| Is the map/table ever frozen? | Yes, any non-Live selection freezes them | Never |
| Is the chart tied to the same timer as the map/table? | Partially (Live mode re-fetches history via `refreshDashboard`) | Yes — one 3s timer drives map, table, and chart refresh |

### Subtle bug to fix along the way

The top time bar and the map card's Canvas/Map buttons **both use `class="time-btn"`** (`templates/index.html:19` and `:32-33`). The global `setupTimeButtons()` query selector `.time-btn` binds click handlers to both (`main.js:808`). It works today only because view-toggle buttons have `data-view` and no `data-range`, so the `RANGE_MAP[undefined]` lookup silently no-ops.

After this change, the top `.time-bar` is gone, and if we only add `.chart-range-btn` on the new chart chips, `setupTimeButtons()` would still run its `.time-btn` query and match **only** the Canvas/Map buttons — calling `loadHistory(undefined)` on every map-view click. Half-fix.

Full fix, both steps required:

1. Rename the Canvas/Map toggle buttons off `class="time-btn"` (use `.view-toggle-btn` — the existing `setupViewToggle` handler uses the scoped selector `.view-toggle .time-btn`, so update that selector to `.view-toggle .view-toggle-btn` or similar).
2. Delete `setupTimeButtons()` entirely. The new chart controls get their own handlers bound to `.chart-range-btn` and `.chart-metric-btn`, with no shared state.

## Backend changes

Extend `_RANGE_MAP` in `backend/models/database.py:98`:

```python
_RANGE_MAP = {
    "15m": ("datetime('now', '-15 minutes')", "strftime('%Y-%m-%d %H:%M', timestamp)"),
    "1h":  ("datetime('now', '-1 hour')",     "strftime('%Y-%m-%d %H:%M', timestamp)"),
    "12h": ("datetime('now', '-12 hours')",   "strftime('%Y-%m-%d %H:00', timestamp)"),
    "24h": ("datetime('now', '-1 day')",      "strftime('%Y-%m-%d %H:00', timestamp)"),
    "7d":  ("datetime('now', '-7 days')",     "strftime('%Y-%m-%d %H:00', timestamp)"),
    "1m":  ("datetime('now', '-1 month')",    "strftime('%Y-%m-%d', timestamp)"),
    "3m":  ("datetime('now', '-3 months')",   "strftime('%Y-%m-%d', timestamp)"),
}
```

Notes:
- `15m` and `1h` group by minute: 15-minute window ≈ 15 rows per node, 1-hour window ≈ 60 rows per node. Comfortably inside Chart.js budget.
- `12h` groups by hour (same as `24h` and `7d`), which gives ~12 bins. Acceptable.
- `1y` is removed from the map.

**`/api/sensor/history` route also needs updating.** The route handler in `backend/routes/sensors.py:11` keeps an independent allowlist `VALID_RANGES = {"24h", "7d", "1m", "3m", "1y"}` and rejects anything else with HTTP 400. Without this change, every `15m`/`1h`/`12h` click in the UI returns 400 and the chart goes silently blank.

- Update `VALID_RANGES` to `{"15m", "1h", "12h", "24h", "7d", "1m", "3m"}`.
- Drop `1y` from the allowlist (the `_RANGE_MAP` fallback to `None` is no longer a safety net — rejection at the route is cleaner).
- Update the route's default range from `"24h"` to `"7d"` to match the UI default.
- Update `tests/test_api.py` — valid range cases for `15m`, `1h`, `12h`; invalid range case for `1y`.

Response already contains `avg_moisture` and `avg_temperature`, so no schema changes.

## Frontend changes (high level)

- `templates/index.html`
  - Remove the top `.time-bar` block.
  - Inside `.chart-card`, add a controls row: metric segmented control + range chips.
  - Give the chart controls their own CSS classes so the selector collision is gone.
  - Rename Canvas/Map toggle buttons off `class="time-btn"` (see Subtle bug section).

- `app.py`
  - Remove the `time_ranges` list at `app.py:114` and drop the `time_ranges=time_ranges` kwarg from `render_template(...)`. The template no longer consumes it.

- `static/js/main.js`
  - Update `RANGE_MAP` (`main.js:16`) with the new labels/keys. Frontend keys must match backend `VALID_RANGES` exactly (`15m`, `1h`, `12h`, `24h`, `7d`, `1m`, `3m`).
  - Introduce a **new** variable `chartMetric` (default `"moisture"`). Leave the existing `activeMetric` (which drives the map heatmap and marker coloring at `main.js:44, 93, 483, 486, 599, 658` and passes into `renderHeatmapCanvas` in `heatmap.js`) **unchanged** — do not rename the heatmap-side identifier, it has too many callers.
  - Refactor `renderChart()` (`main.js:284`) to take `(metric, data)` — the function picks `avg_moisture` or `avg_temperature` based on the `metric` argument and updates the y-axis title/min/max and tooltip suffix.
  - Delete `setupTimeButtons()` entirely (see Subtle bug section). Add two new handlers: one for `.chart-range-btn` click, one for `.chart-metric-btn` click. Both guard against re-selecting the already-active option.
  - `startAutoRefresh()` runs unconditionally on init. No other code path ever calls `stopAutoRefresh()`.

- `static/css/style.css`
  - Style the new segmented metric control and chip strip.
  - Touch-friendly sizing: chips ≥ 36px tall.

## Success criteria

1. Top time-range bar is gone from the page.
2. Chart card has a single control row: metric toggle + range chips.
3. Clicking `Temperature` swaps the chart to temperature lines, y-axis to `°C`, tooltips to `°C`.
4. Clicking a range re-fetches only the chart; the 3s timer keeps map, table, and chart ticking afterward.
5. Map's Canvas/Map toggle still works and no longer shares a class with chart controls.
6. Default load state: `Moisture` + `7d` selected; chart renders immediately on page load.
7. `/api/sensor/history?range=<k>` returns 200 for each of `15m, 1h, 12h, 24h, 7d, 1m, 3m` and 400 for `1y`. `tests/test_api.py` updated to cover the new surface.
8. No regressions in Leaflet map behavior, heatmap, or sensor table.

## Open questions

*(none — ready for `/ce:plan`)*

### Deferred to planning / implementation

These were surfaced during review but are implementation-detail judgment calls, not open product questions:

- Chart x-axis tick formatting for short ranges (15m/1h show `YYYY-MM-DD HH:MM` strings today) — implementer picks a compact format.
- Keyboard focus order / screen-reader labels on the new controls — LAN use is secondary; treat as a "nice to have" during implementation.
- Chart legend position and wrapping when node count grows — not a current-field-state problem (1 Arduino node live).
- Touch `:active` / pressed states on chips — CSS detail during implementation.
- Whether a metric switch re-fetches or re-renders from cache — both are correct; pick the simpler one (re-fetch) to avoid caching bugs.

## References

- `templates/index.html` — existing time-bar and chart card markup
- `static/js/main.js:12,16,34,284,808,849` — refresh timer, range map, chart state, chart render, button wiring, default load
- `backend/models/database.py:98-104` — `_RANGE_MAP`
- `backend/routes/sensors.py:20-28` — `/api/sensor/history` endpoint
- `static/css/style.css` — chart-card and time-bar styles
