---
title: "refactor: Chart in-place updates — kill refresh animation, persist hidden series"
type: refactor
status: active
date: 2026-04-24
---

# refactor: Chart in-place updates — kill refresh animation, persist hidden series

## Overview

Stop destroying and recreating the Chart.js instance on every 3s auto-refresh. Update the chart in place with `chart.update('none')` so (1) the line-draw animation no longer flashes every tick and (2) datasets the user has Xed out via the legend stay hidden across refreshes. Keep destroy+rebuild for the metric switch path only, since the y-axis config changes between Moisture and Temperature views.

## Problem Frame

`renderChart()` in `static/js/main.js:289-379` calls `historyChart.destroy()` then `new Chart(ctx, ...)` on every render. The freshly constructed chart plays Chart.js's default creation animation, producing a visible line-draw / fade every 3 seconds during normal auto-refresh. The same teardown also wipes the chart instance's per-dataset visibility state, so when the user clicks a legend label like `field_3` to hide that line, the line reappears on the next refresh tick (~3 seconds later) and the strikethrough on the legend label resets.

Both symptoms come from the same root cause: full instance recreation on every tick. The 2026-04-24-001 graph-view-cleanup plan explicitly deferred the in-place-update path until kiosk testing surfaced the flash. The flash is now confirmed and the persistence gap is also user-facing — both are addressed in this single follow-up.

## Requirements Trace

- **R1.** Auto-refresh ticks (every 3s) do not animate the chart; lines update silently.
- **R2.** Datasets hidden via legend click stay hidden across auto-refresh ticks. The legend label stays struck-through.
- **R3.** Datasets hidden via legend click also stay hidden across range changes within the same metric (e.g. 7d → 24h with Moisture selected).
- **R4.** Switching metric (Moisture ↔ Temperature) destroys and rebuilds the chart (y-axis config changes). Hidden state is allowed to reset on metric switch — fresh view.
- **R5.** No regressions in existing chart behavior: tooltip suffixing, gap rendering for `null` samples, range chip and metric toggle UX, loading/empty/error overlays, AbortController guards.

## Scope Boundaries

- No persistence of hidden series in localStorage. Resets on page reload, same as existing range/metric behavior.
- No change to API, backend, or data shape.
- No change to legend behavior, position, or styling.
- No change to `setInterval`-based 3s timer (`startAutoRefresh()` in `main.js:893-896`).
- No change to the metric-switch UX — losing hidden state when switching metric is acceptable.
- No keyboard or a11y polish beyond what Chart.js gives by default.
- No Chart.js version bump.

## Context & Research

### Relevant Code and Patterns

- **`renderChart()` — `static/js/main.js:289-379`.** The function under refactor. Currently always destroys+rebuilds. New behavior branches on whether the existing chart matches the incoming metric.
- **`loadHistory()` — `static/js/main.js:830-891`.** Caller of `renderChart`. Already handles empty-data and abort cases — those paths are untouched. The destroy-on-empty-and-user-click path at `main.js:864` (`if (historyChart) { historyChart.destroy(); historyChart = null; }`) stays as-is.
- **`setupChartMetricButtons()` — `static/js/main.js:899-912`** and **`setupChartRangeButtons()` — `static/js/main.js:914-927`.** Both call `loadHistory(currentRange, chartMetric)` on click. No changes needed in either handler — the metric-vs-prior-metric check lives inside `renderChart`.
- **Module-level chart state — `static/js/main.js:35`:** `let historyChart = null;`. The detection of "is this the same metric as the prior render" can be stored as a tag on the chart instance (e.g. `historyChart._fieldcoreMetric`) so we don't introduce another module-level `let` just for this.
- **Convention: pure vanilla JS, no build, no ES modules.** Module-level `let` globals plus jQuery-free DOM access is the entire frontend pattern. Don't pull in helpers; mirror the existing style.
- **Prior plan that teed this up — `docs/plans/2026-04-24-001-refactor-graph-view-cleanup-plan.md:66`.** Documents the explicit deferral: *"If the Pi visibly flashes on each 3s tick, add a narrow in-place-update path for the auto-refresh case only, at that point."*

### Institutional Learnings

- None — `docs/solutions/` does not exist in this repo. Carrying forward the pattern from the prior chart-area plan instead.

### External References

- Not consulted. Chart.js in-place update via `chart.update('none')` is the documented approach for animation-free data swaps. The local Chart.js usage already covers all the surface area this plan needs.

## Key Technical Decisions

- **Branch on prior metric, not on `isAutoRefresh`.** The decision to update vs destroy belongs to the chart layer, not the fetch layer. `renderChart` checks whether the live `historyChart` was rendered with the same metric as the incoming call; if yes → in-place update; if no (or no chart yet) → destroy+rebuild. This keeps `loadHistory()` unchanged and means range changes (which keep the same metric) automatically get the in-place path with hidden-state preservation — bonus alignment with R3.
- **Tag the chart instance with its metric.** Set `historyChart._fieldcoreMetric = metric` after construction. Underscore prefix signals private/non-Chart.js field. Avoids adding another module-level `let lastChartMetric`.
- **Set `animation: false` on the chart options.** Belt-and-suspenders: `chart.update('none')` already disables animation for the update tick, but `animation: false` ensures the destroy+rebuild path on metric switch also doesn't animate. The metric switch should be instant, not theatrical.
- **Capture hidden state by label, reapply by label.** Before swapping `data.datasets`, build `Set<label>` of hidden dataset labels via `historyChart.isDatasetVisible(i)`. After `chart.update('none')`, walk the new datasets and call `historyChart.hide(i)` for any whose label is in the set. Keying by label (not index) is required because the dataset list can change between refreshes — a node may appear, drop out, or shuffle order — and Chart.js's internal visibility meta is keyed by index.
- **Update both `data.datasets` and the x-axis labels in place.** The chart uses `type: 'category'` with explicit `labels: [...new Set(...)]` (`main.js:371`). When the range or even just a new minute bucket rolls in, the x labels change. Set `historyChart.options.scales.x.labels = newXLabels` alongside `historyChart.data.datasets = newDatasets` before calling `update('none')`.
- **Compute datasets and x-labels once, branch after.** Both the in-place-update and the destroy+rebuild paths need the same `datasets` array and `xLabels` array. Compute them at the top of `renderChart`, then branch.
- **No change to `loadHistory`.** All decision logic stays inside `renderChart`. Keeps the fetch/empty/error/abort flow untouched and minimizes diff surface.
- **Hidden state intentionally resets on metric switch.** Switching from Moisture to Temperature is conceptually a fresh view — the user is asking different question. Re-applying hidden labels across metric change would be confusing (different y-scale, different meaning) and adds code without clear UX win.

## Open Questions

### Resolved During Planning

- **Should hidden state persist across metric switches?** No. Metric switch = fresh view. Range change within the same metric = persist (free benefit of the metric-tag branching).
- **Should we use a module-level `let lastChartMetric`?** No. Tag the chart instance instead — same lifetime as the chart, no separate state to keep in sync.
- **Will `chart.hide(i)` cause a second animation?** No. With `animation: false` on the chart, `hide()` calls are also non-animated.
- **What if a dataset is added or removed between refreshes?** New datasets default to visible. Removed datasets drop their hidden tag (label no longer present in the new list). The label-keyed `Set` handles both correctly without extra logic.

### Deferred to Implementation

- Final placement of the metric tag and hidden-label capture — inline in `renderChart` vs small helper function. Decide based on what reads cleanly once the diff is in front of you.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
renderChart(metric, historyData):
    # 1. Compute (always)
    datasets, xLabels = build_from(historyData, metric)
    
    # 2. Branch
    if historyChart exists AND historyChart._fieldcoreMetric == metric:
        # In-place path — preserves Chart.js internal visibility meta
        hiddenLabels = { ds.label for i, ds in enumerate(historyChart.data.datasets)
                         if not historyChart.isDatasetVisible(i) }
        historyChart.data.datasets = datasets
        historyChart.options.scales.x.labels = xLabels
        historyChart.update('none')
        # Reapply hidden state by label (handles dataset reordering)
        for i, ds in enumerate(datasets):
            if ds.label in hiddenLabels:
                historyChart.hide(i)
        return
    
    # Destroy+rebuild path (first render or metric switch)
    if historyChart exists:
        historyChart.destroy()
    historyChart = new Chart(ctx, {
        ...current options...,
        animation: false,   # NEW
    })
    historyChart._fieldcoreMetric = metric
```

The flow into `renderChart` is unchanged. `loadHistory()` still calls `renderChart(metric, data)` on success; the same-metric branching is internal.

## Implementation Units

- [ ] **Unit 1: In-place chart update with hidden-state preservation**

**Goal:** Refactor `renderChart()` so auto-refresh and range changes update the existing Chart.js instance in place (no animation, hidden series preserved); metric switches still destroy+rebuild with `animation: false`.

**Requirements:** R1, R2, R3, R4, R5.

**Dependencies:** None.

**Files:**
- Modify: `static/js/main.js` (`renderChart()` at lines 289-379)
- Test: manual browser verification (no JS unit-test framework; covered below)

**Approach:**
- At the top of `renderChart`, compute `datasets` and the new x-axis `labels` array exactly as today (lines 298-332 and 371). Lift the `labels` computation out of the inline `scales.x.labels` so both branches can use it.
- Determine `sameMetric = historyChart && historyChart._fieldcoreMetric === metric`.
- **In-place branch:** Build `hiddenLabels` set from `historyChart.data.datasets` using `historyChart.isDatasetVisible(i)`. Assign `historyChart.data.datasets = datasets` and `historyChart.options.scales.x.labels = xLabels`. Call `historyChart.update('none')`. Loop through `datasets` and call `historyChart.hide(i)` for any whose `label` is in `hiddenLabels`.
- **Destroy+rebuild branch:** Existing `historyChart.destroy()` + `new Chart(...)` flow, with two changes: (a) add `animation: false` to the options object; (b) tag `historyChart._fieldcoreMetric = metric` after construction.
- Both branches must keep the existing `yAxis` selection (lines 338-340), tooltip callback (lines 354-365), `interaction`, `legend`, and `scales.y` configuration intact. Only the dataset/x-label payload and the construction-vs-update branching changes.

**Patterns to follow:**
- Module-level `let` for chart state (already established at `main.js:35`).
- Underscore-prefixed private field on chart instance — matches the convention of `_validate_node_id`-style underscore-private helpers used elsewhere in the codebase.
- No new module-level globals beyond what already exists.

**Test scenarios:**
- *Happy path — animation gone:* Open dashboard with Moisture / 7d default. Wait through 3+ auto-refresh ticks (~10 seconds). Chart lines update silently each tick — no line-draw, fade, or visible flash.
- *Happy path — hidden persistence across auto-refresh:* Click `field_3` in the legend to Xthe label and hide the line. Wait through 3+ auto-refresh ticks. The `field_3` label stays struck-through and its line stays hidden. Click the label again — line reappears immediately and stays through subsequent ticks.
- *Happy path — hidden persistence across range change:* Hide `field_3` and `field_5`. Click `24h` range chip. Chart updates to the new range; both labels remain struck-through; both lines remain hidden.
- *Happy path — metric switch resets hidden state:* Hide `field_3`. Click `Temperature` toggle. Chart rebuilds with °C y-axis; all labels (including `field_3`) are visible again. No animation on the rebuild.
- *Happy path — metric switch back:* Click `Moisture`. Chart rebuilds with `0-100` y-axis; all labels visible; no animation.
- *Edge case — first render:* Hard reload page. First chart paint shows lines instantly with no animation (because `animation: false` on construction).
- *Edge case — dataset shuffle:* (Hard to force manually; verify by reading the diff.) When new node data arrives that reorders the `nodeIds` array between refreshes, hidden-by-label reapplication still hides the correct series.
- *Edge case — empty-then-data:* If `loadHistory` enters the empty-on-user-click branch and destroys the chart (`main.js:864`), the next non-empty render goes through the destroy+rebuild branch (since `historyChart` is null) and works correctly. (Auto-refresh empty ticks already early-return at `main.js:861` and don't touch the chart.)
- *Regression — tooltip:* Hover the chart after several refresh ticks. Tooltip shows correct values with `°C` or `%` suffix per metric. Null samples don't appear as 0.
- *Regression — gap rendering:* If a node has missing data (`null` `avg_*`), the line shows a gap, not a phantom 0. (Behavior preserved from existing `spanGaps: false`.)
- *Regression — loading/empty/error overlays:* Force an error (e.g. throttle network in DevTools to time out a user-click `loadHistory`). Error overlay shows. Click retry — chart recovers.

**Verification:**
- Open the dashboard at `http://localhost:5001` after `./start.sh`. Walk through every test scenario above.
- Pi-kiosk smoke check: SSH into the Pi (or whatever the test rig is), confirm the dashboard renders without the per-tick flash that triggered this refactor.
- Existing pytest suite (`pytest tests/`) still passes — no backend changes, but run it as a sanity check that nothing in `app.py` was accidentally touched.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `chart.hide(i)` triggers an unwanted animation tick on Chart.js versions where `animation: false` doesn't suppress visibility-change animations. | Verify with manual scenarios above. If a flicker appears on the hide-reapply step, switch to setting `chart.getDatasetMeta(i).hidden = true` directly *before* the `update('none')` call instead of after. |
| Index-keyed visibility breaks when the dataset list shifts between refreshes. | Already addressed: capture hidden state as a `Set` of labels, reapply by walking the new datasets and matching labels. Order-independent. |
| `historyChart._fieldcoreMetric` collides with a real Chart.js internal field in some future version. | Underscore-prefixed custom field on a chart instance is a low-risk convention. If Chart.js ever ships a colliding field, rename to a more obviously bespoke key (e.g. `__fieldcoreMetric`). |
| Range changes that cross aggregation buckets (e.g. 15m → 7d) produce wildly different x-axis label sets and trip up Chart.js category-axis caching. | Both `data.datasets` and `options.scales.x.labels` are reassigned before `update('none')`. Chart.js handles full label-set replacement on category axes. Verify in the manual range-switch scenario above. |
| User Xes out a series, immediately switches metric, switches back — and is surprised the series is visible again. | Documented decision: metric switch is a fresh view. If user feedback says otherwise, lift the hidden-label capture out of `renderChart` into a module-level `Map<metric, Set<label>>` and re-apply on every render. Not in this scope. |

## Documentation / Operational Notes

- No public API or doc changes. The chart card UX is unchanged for any user who never clicked a legend label; the only visible difference is the absence of the per-tick flash.
- Optional: a one-line note on the prior plan (`docs/plans/2026-04-24-001-refactor-graph-view-cleanup-plan.md`) marking the deferred in-place-update follow-up as completed by this plan. Skip if it adds noise.

## Sources & References

- Prior plan that deferred this work: `docs/plans/2026-04-24-001-refactor-graph-view-cleanup-plan.md` (see Key Technical Decisions, "Always destroy+rebuild the chart" — line 66).
- Code under refactor: `static/js/main.js:289-379` (`renderChart`), `static/js/main.js:830-891` (`loadHistory`, unchanged), `static/js/main.js:899-927` (chart control handlers, unchanged).
