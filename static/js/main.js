/* ── FieldCore Dashboard — Frontend Logic ─────────────────────────────── */

/* ── Constants ────────────────────────────────────────────────────────── */
const MOISTURE_COLOR = {
    low:     '#E53E3E',
    fair:    '#ED8936',
    good:    '#ECC94B',
    optimal: '#48BB78',
};

const NODE_R = 18;
const REFRESH_MS = 3000; // auto-refresh every 3s
// Moisture is stored as integer percent (0-100); no raw-to-percent scaling needed.

const CHART_COLORS = [
    '#48BB78', // green
    '#4299E1', // blue
    '#ED8936', // orange
    '#9F7AEA', // purple
    '#F56565', // red
    '#38B2AC', // teal
];

// Human-readable windows for the Empty state message. `data-range` and
// `data-metric` attributes on the chart-controls buttons carry the raw
// keys (e.g. '15m', 'moisture') which also match backend VALID_RANGES.
// Metric names aren't aliased — the raw key ('moisture', 'temperature')
// reads naturally in 'No moisture readings in the last 7 days'.
const RANGE_LABELS = {
    '15m': '15 minutes', '1h': 'hour', '12h': '12 hours',
    '24h': '24 hours',    '7d': '7 days',
    '1m':  'month',       '3m': '3 months',
};

let historyChart = null;
let refreshTimer = null;
let currentRange = '7d';            // chart time-range key (matches VALID_RANGES)
let leafletMap = null;
let leafletMarkers = {};  // node_id -> L.circleMarker
let activeView = 'map'; // 'canvas' or 'map'
let knownNodeIds = null;   // Set of node_ids for fitBounds tracking
let mapControlPanel = null; // custom L.Control for tile/heatmap/metric
let heatmapOverlay = null; // L.imageOverlay for IDW heatmap
let heatmapLegend = null;  // L.Control for color bar legend

/* Two separate "active metric" states — do NOT cross-wire:
 *   activeMetric → drives the map heatmap + marker colors. Read by
 *     updateHeatmap, getMarkerColor, and passed into renderHeatmapCanvas
 *     in heatmap.js.
 *   chartMetric  → drives the chart card only. Flipped by the Moisture /
 *     Temperature toggle beneath "Historical Trends".
 */
let activeMetric = 'moisture';
let chartMetric = 'moisture';
let chartAbort = null;          // AbortController for the in-flight history fetch

let lastReadings = null;   // most recent readings for metric-switch re-renders
let heatmapBorderBlack = null;  // L.rectangle — black dashes
let heatmapBorderYellow = null; // L.rectangle — yellow dashes (offset)

/* ── Moisture helpers ─────────────────────────────────────────────────── */
// Moisture arrives as percent (0-100). Clamp only; no raw-to-percent scaling.
function normalizeMoisture(pct) {
    return Math.max(0, Math.min(100, Math.round(pct || 0)));
}

function moistureLevel(pct) {
    if (pct >= 60) return 'optimal';
    if (pct >= 40) return 'good';
    if (pct >= 20) return 'fair';
    return 'low';
}

function moistureBarColor(pct) {
    if (pct >= 60) return '#48BB78';
    if (pct >= 40) return '#ECC94B';
    if (pct >= 20) return '#ED8936';
    return '#E53E3E';
}

/* ── Temperature color helper ────────────────────────────────────────── */
function temperatureColor(temp) {
    if (temp == null) return '#A0AEC0'; // gray for no data
    // Blue (cold ≤15°C) → Yellow (moderate ~22°C) → Red (hot ≥30°C)
    const clamped = Math.max(15, Math.min(30, temp));
    const t = (clamped - 15) / 15; // 0..1
    if (t <= 0.5) {
        // Blue to Yellow (0..0.5)
        const s = t * 2;
        const r = Math.round(66 + s * (236 - 66));
        const g = Math.round(153 + s * (201 - 153));
        const b = Math.round(225 + s * (75 - 225));
        return `rgb(${r},${g},${b})`;
    } else {
        // Yellow to Red (0.5..1)
        const s = (t - 0.5) * 2;
        const r = Math.round(236 + s * (229 - 236));
        const g = Math.round(201 + s * (62 - 201));
        const b = Math.round(75 + s * (62 - 75));
        return `rgb(${r},${g},${b})`;
    }
}

function getMarkerColor(r) {
    if (activeMetric === 'temperature') {
        return temperatureColor(r.temperature);
    }
    const rawMoisture = r.moisture || 0;
    const pct = normalizeMoisture(rawMoisture);
    const level = moistureLevel(pct);
    return MOISTURE_COLOR[level] || '#A0AEC0';
}

/* ── API helpers ──────────────────────────────────────────────────────── */
async function fetchLatest() {
    const resp = await fetch('/api/sensor/latest');
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

/* ── Coordinate normalization ─────────────────────────────────────────── */
function normalizeCoords(readings) {
    const xs = readings.map(r => r.latitude).filter(v => v != null);
    const ys = readings.map(r => r.longitude).filter(v => v != null);

    if (xs.length === 0 || ys.length === 0) return readings;

    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const xRange = xMax - xMin || 1;
    const yRange = yMax - yMin || 1;
    const pad = 0.1;

    return readings.map(r => ({
        ...r,
        nx: pad + (1 - 2 * pad) * (r.latitude - xMin) / xRange,
        ny: pad + (1 - 2 * pad) * (r.longitude - yMin) / yRange,
    }));
}

/* ── Canvas helpers ───────────────────────────────────────────────────── */
function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
}

/**
 * Shared canvas renderer for sensor nodes.
 * Each node must have: { x, y, color, label }
 *   x, y  — normalized 0-1 position on the map
 *   color — hex fill color for the node circle
 *   label — text to render inside the circle
 */
function drawNodes(canvas, nodes) {
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const pad = 4;

    // Map background
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#E8F5E9';
    ctx.strokeStyle = '#E8ECF0';
    ctx.lineWidth = 1;
    roundRect(ctx, pad, pad, w - pad * 2, h - pad * 2, 8);
    ctx.fill();
    ctx.stroke();

    const mapX = pad;
    const mapY = pad;
    const mapW = w - pad * 2;
    const mapH = h - pad * 2;

    nodes.forEach(node => {
        const cx = mapX + node.x * mapW;
        const cy = mapY + node.y * mapH;

        // White outer ring
        ctx.beginPath();
        ctx.arc(cx, cy, NODE_R + 3, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF';
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();

        // Colored fill
        ctx.beginPath();
        ctx.arc(cx, cy, NODE_R, 0, Math.PI * 2);
        ctx.fillStyle = node.color;
        ctx.fill();

        // Label
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 8px "Segoe UI", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(node.label, cx, cy);
    });
}

/* ── Sensor map (API data — raw readings) ────────────────────────────── */
function drawMap(canvas, readings) {
    const normalized = normalizeCoords(readings);
    const nodes = normalized.map(node => ({
        x: node.nx || 0.5,
        y: node.ny || 0.5,
        color: MOISTURE_COLOR[moistureLevel(normalizeMoisture(node.moisture || 0))],
        label: node.node_id || node.id || '',
    }));
    drawNodes(canvas, nodes);
}

/* ── Sensor map (server-rendered data — pre-normalized) ──────────────── */
function drawMapFromNodes(canvas, serverNodes) {
    const nodes = serverNodes.map(node => ({
        x: node.x,
        y: node.y,
        color: MOISTURE_COLOR[node.moisture] || '#A0AEC0',
        label: node.id || '',
    }));
    drawNodes(canvas, nodes);
}

/* ── HTML escaping ────────────────────────────────────────────────────── */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/* ── Table rendering ──────────────────────────────────────────────────── */
function updateTable(readings) {
    const tbody = document.getElementById('sensorTableBody');
    if (!tbody) return;

    tbody.innerHTML = readings.map(r => {
        const battery = r.battery || 0;
        const rawMoisture = r.moisture || 0;
        const pct = normalizeMoisture(rawMoisture);
        const temp = r.temperature != null ? r.temperature.toFixed(1) : '\u2014';
        const tempHigh = (r.temperature || 0) > 30;
        const batColor = battery >= 70 ? '#68D391' : '#F6AD55';
        const safeNodeId = escapeHtml(r.node_id ?? '');
        const safeName = escapeHtml(r.name || `field_${r.node_id ?? ''}`);

        return `<tr id="row-${safeNodeId}">
            <td class="node-id">${safeName}</td>
            <td>
                <div class="bar-cell">
                    <div class="mini-bar">
                        <div class="mini-bar-fill" style="width:${battery}%; background:${batColor};"></div>
                    </div>
                    <span class="bar-label">${battery}%</span>
                </div>
            </td>
            <td>
                <div class="bar-cell">
                    <div class="mini-bar">
                        <div class="mini-bar-fill" style="width:${pct}%; background:${moistureBarColor(pct)};"></div>
                    </div>
                    <span class="bar-label">${pct}%</span>
                </div>
            </td>
            <td>
                <span class="temp-cell ${tempHigh ? 'high' : 'normal'}">&#x1f321; ${temp}&deg;C</span>
            </td>
        </tr>`;
    }).join('');
}

/* ── Chart rendering ──────────────────────────────────────────────────── */
function renderChart(metric, historyData) {
    const ctx = document.getElementById('historyChart');
    if (!ctx) return;

    const dataKey = metric === 'temperature' ? 'avg_temperature' : 'avg_moisture';
    const isTemp  = metric === 'temperature';

    // Group by node_id. Capture each node's display name from the history
    // response (backend JOINs nodes so each row carries `name`).
    const byNode = {};
    const nodeNames = {};
    historyData.forEach(row => {
        if (!byNode[row.node_id]) byNode[row.node_id] = [];
        byNode[row.node_id].push(row);
        if (row.name) nodeNames[row.node_id] = row.name;
    });

    // Object.keys returns strings — sort numerically so ids 1-14 render in
    // natural order instead of the lexicographic 1, 10, 11, 12, ... .
    const nodeIds = Object.keys(byNode).sort((a, b) => Number(a) - Number(b));

    const datasets = nodeIds.map((nodeId, i) => {
        const rows = byNode[nodeId];
        return {
            label: nodeNames[nodeId] || `field_${nodeId}`,
            data: rows.map(r => {
                const raw = r[dataKey];
                let y;
                if (raw === null || raw === undefined) {
                    y = null; // Chart.js renders as a gap when spanGaps is false
                } else {
                    y = isTemp ? Number(raw) : normalizeMoisture(raw);
                }
                return { x: r.period, y };
            }),
            borderColor: CHART_COLORS[i % CHART_COLORS.length],
            backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '20',
            borderWidth: 2,
            pointRadius: 1,
            tension: 0.3,
            fill: !isTemp, // fill under moisture looks nice; leaves temp lines clean
            spanGaps: false,
        };
    });

    if (historyChart) {
        historyChart.destroy();
    }

    const yAxis = isTemp
        ? { suggestedMin: 0, suggestedMax: 40, title: { display: true, text: 'Temperature (°C)', font: { size: 11 } }, ticks: { font: { size: 10 } } }
        : { min: 0, max: 100,                  title: { display: true, text: 'Moisture %',       font: { size: 11 } }, ticks: { font: { size: 10 } } };

    historyChart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, padding: 12, font: { size: 11 } },
                },
                tooltip: {
                    callbacks: {
                        label: (c) => {
                            // Suppress tooltip rows for gap points (y === null);
                            // returning null from a label callback hides that
                            // series from the shared-index tooltip.
                            if (c.parsed.y === null || c.parsed.y === undefined) return null;
                            return isTemp
                                ? `${c.dataset.label}: ${c.parsed.y.toFixed(1)} °C`
                                : `${c.dataset.label}: ${c.parsed.y}%`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    type: 'category',
                    labels: [...new Set(datasets.flatMap(ds => ds.data.map(d => d.x)))].sort(),
                    ticks: { maxTicksLimit: 12, font: { size: 10 }, maxRotation: 45 },
                    grid: { display: false },
                },
                y: yAxis,
            },
        },
    });
}

/* ── Leaflet map ─────────────────────────────────────────────────────── */
let osmLayer = null;
let satelliteLayer = null;
let heatmapEnabled = true; // heatmap on by default

function initLeafletMap() {
    osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
    });

    satelliteLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
            attribution: '&copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
            maxZoom: 18,
        }
    );

    leafletMap = L.map('leafletMap', {
        layers: [osmLayer],
        zoomControl: true,
        minZoom: 13,
    });

    // Custom pane for heatmap — between tiles (200) and overlayPane (400)
    leafletMap.createPane('heatmapPane');
    leafletMap.getPane('heatmapPane').style.zIndex = 350;
    leafletMap.getPane('heatmapPane').style.pointerEvents = 'none';

    // Set a default view until markers load
    leafletMap.setView([37.421, -91.565], 14);

    // Initialize custom control panel and heatmap legend
    initMapControlPanel();
    initHeatmapLegend();
}

/* ── Custom map control panel ────────────────────────────────────────── */
const MapControlPanel = L.Control.extend({
    options: { position: 'topright' },

    onAdd: function () {
        const container = L.DomUtil.create('div', 'map-control-panel');
        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.disableScrollPropagation(container);

        container.innerHTML =
            '<div class="mcp-section">' +
                '<div class="mcp-label">Tiles</div>' +
                '<div class="mcp-btn-group">' +
                    '<button class="mcp-btn active" data-tile="street">Street</button>' +
                    '<button class="mcp-btn" data-tile="satellite">Satellite</button>' +
                '</div>' +
            '</div>' +
            '<div class="mcp-divider"></div>' +
            '<div class="mcp-section">' +
                '<div class="mcp-btn-group">' +
                    '<button class="mcp-btn mcp-toggle active" data-action="heatmap">Heatmap</button>' +
                '</div>' +
            '</div>' +
            '<div class="mcp-divider"></div>' +
            '<div class="mcp-section">' +
                '<div class="mcp-label">Metric</div>' +
                '<div class="mcp-btn-group">' +
                    '<button class="mcp-btn active" data-metric="moisture">Moisture</button>' +
                    '<button class="mcp-btn" data-metric="temperature">Temp</button>' +
                '</div>' +
            '</div>';

        // Tile layer buttons
        container.querySelectorAll('[data-tile]').forEach(btn => {
            btn.addEventListener('click', () => {
                const tile = btn.dataset.tile;
                container.querySelectorAll('[data-tile]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                if (tile === 'satellite') {
                    leafletMap.removeLayer(osmLayer);
                    if (!leafletMap.hasLayer(satelliteLayer)) leafletMap.addLayer(satelliteLayer);
                } else {
                    leafletMap.removeLayer(satelliteLayer);
                    if (!leafletMap.hasLayer(osmLayer)) leafletMap.addLayer(osmLayer);
                }
            });
        });

        // Heatmap toggle
        container.querySelector('[data-action="heatmap"]').addEventListener('click', function () {
            this.classList.toggle('active');
            heatmapEnabled = this.classList.contains('active');
            if (heatmapEnabled) {
                if (heatmapOverlay) {
                    heatmapOverlay.addTo(leafletMap);
                    if (heatmapBorderBlack) heatmapBorderBlack.addTo(leafletMap);
                    if (heatmapBorderYellow) heatmapBorderYellow.addTo(leafletMap);
                }
                if (heatmapLegend) heatmapLegend.show();
                if (lastReadings) updateHeatmap(lastReadings);
            } else {
                if (heatmapOverlay) leafletMap.removeLayer(heatmapOverlay);
                if (heatmapBorderBlack) leafletMap.removeLayer(heatmapBorderBlack);
                if (heatmapBorderYellow) leafletMap.removeLayer(heatmapBorderYellow);
                if (heatmapLegend) heatmapLegend.hide();
            }
        });

        // Metric buttons
        container.querySelectorAll('[data-metric]').forEach(btn => {
            btn.addEventListener('click', () => {
                const metric = btn.dataset.metric;
                if (metric === activeMetric) return;
                container.querySelectorAll('[data-metric]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeMetric = metric;
                if (lastReadings) {
                    updateHeatmap(lastReadings);
                    updateLeafletMarkers(lastReadings);
                }
            });
        });

        return container;
    },
});

function initMapControlPanel() {
    if (!leafletMap || mapControlPanel) return;
    mapControlPanel = new MapControlPanel();
    mapControlPanel.addTo(leafletMap);
}

function updateLeafletMarkers(readings) {
    if (!leafletMap) return;

    // String() coercion: Object.keys(leafletMarkers) always returns strings,
    // so the Set must hold strings too for `has()` to match after the integer
    // node_id refactor. Without this, every auto-refresh deletes and recreates
    // every marker (visible flicker + fitBounds never stabilises).
    const currentIds = new Set(readings.map(r => String(r.node_id)));

    // Remove markers for nodes no longer present
    for (const id of Object.keys(leafletMarkers)) {
        if (!currentIds.has(id)) {
            leafletMap.removeLayer(leafletMarkers[id]);
            delete leafletMarkers[id];
        }
    }

    readings.forEach(r => {
        const lat = r.latitude;
        const lng = r.longitude;
        if (lat == null || lng == null) return;

        const color = getMarkerColor(r);

        if (leafletMarkers[r.node_id]) {
            // Update existing marker
            const marker = leafletMarkers[r.node_id];
            marker.setLatLng([lat, lng]);
            marker.setStyle({ fillColor: color });
            // Update popup content if bound
            if (marker.getPopup()) {
                marker.getPopup().setContent(buildPopupContent(r));
            }
        } else {
            // Create new marker
            const marker = L.circleMarker([lat, lng], {
                radius: 14,
                fillColor: color,
                color: '#FFFFFF',
                weight: 3,
                opacity: 1,
                fillOpacity: 0.9,
            }).addTo(leafletMap);
            marker.bindPopup(buildPopupContent(r), { maxWidth: 220 });
            leafletMarkers[r.node_id] = marker;
        }
    });

    // Fit bounds only on first render or when node set changes
    const newNodeIds = JSON.stringify([...currentIds].sort());
    if (knownNodeIds !== newNodeIds) {
        knownNodeIds = newNodeIds;
        const markers = Object.values(leafletMarkers);
        if (markers.length > 0) {
            const group = L.featureGroup(markers);
            const bounds = group.getBounds();
            // Tight fit to the node area
            leafletMap.fitBounds(bounds, { padding: [20, 20], maxZoom: 16 });
            // Lock pan to a padded bounding box around the nodes
            const paddedBounds = bounds.pad(0.5); // 50% padding around node cluster
            leafletMap.setMaxBounds(paddedBounds);
        }
    }
}

function buildPopupContent(r) {
    const name = escapeHtml(r.name || r.node_id);
    const nodeId = escapeHtml(r.node_id || '');
    const rawMoisture = r.moisture;
    const moisture = rawMoisture != null ? normalizeMoisture(rawMoisture) + '%' : 'No data';
    const temp = r.temperature != null ? r.temperature.toFixed(1) + '°C' : 'No data';
    const battery = r.battery != null ? r.battery + '%' : 'No data';
    const rssi = r.signal_rssi != null ? r.signal_rssi + ' dBm' : 'No data';

    return `<div class="map-popup">
        <strong>${name}</strong>
        <div class="popup-fields">
            <span>Moisture: ${moisture}</span>
            <span>Temp: ${temp}</span>
            <span>Battery: ${battery}</span>
            <span>Signal: ${rssi}</span>
        </div>
        <a href="#" class="popup-link" onclick="scrollToNode('${nodeId}'); return false;">View in table</a>
    </div>`;
}

function scrollToNode(nodeId) {
    const row = document.getElementById('row-' + nodeId);
    if (!row) return;
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.add('row-highlight');
    setTimeout(() => row.classList.remove('row-highlight'), 2000);
}

/* ── Heatmap overlay ─────────────────────────────────────────────────── */
function updateHeatmap(readings) {
    if (!leafletMap) return;

    lastReadings = readings;
    const result = renderHeatmapCanvas(readings, activeMetric, HEATMAP_GRID_SIZE);

    if (!result) {
        // Not enough data — remove overlay if it exists
        if (heatmapOverlay && leafletMap.hasLayer(heatmapOverlay)) {
            heatmapOverlay.setUrl('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');
        }
        return;
    }

    const bounds = L.latLngBounds(
        [result.bounds.south, result.bounds.west],
        [result.bounds.north, result.bounds.east]
    );

    if (!heatmapOverlay) {
        // Create overlay on first data
        heatmapOverlay = L.imageOverlay(result.dataUrl, bounds, {
            opacity: HEATMAP_OPACITY,
            pane: 'heatmapPane',
            interactive: false,
        });
        // Add to map immediately if heatmap is enabled (on by default)
        if (heatmapEnabled) {
            heatmapOverlay.addTo(leafletMap);
            if (heatmapLegend) heatmapLegend.show();
        }

        // Dashed border — two overlapping rectangles for alternating black/yellow
        const dashOpts = {
            fill: false,
            weight: 2,
            opacity: 0.8,
            interactive: false,
        };
        heatmapBorderBlack = L.rectangle(bounds, {
            ...dashOpts,
            color: '#1A202C',
            dashArray: '8, 8',
        });
        heatmapBorderYellow = L.rectangle(bounds, {
            ...dashOpts,
            color: '#ECC94B',
            dashArray: '8, 8',
            dashOffset: '8',
        });
        if (heatmapEnabled) {
            heatmapBorderBlack.addTo(leafletMap);
            heatmapBorderYellow.addTo(leafletMap);
        }
    } else {
        heatmapOverlay.setUrl(result.dataUrl);
        heatmapOverlay.setBounds(bounds);
        if (heatmapBorderBlack) heatmapBorderBlack.setBounds(bounds);
        if (heatmapBorderYellow) heatmapBorderYellow.setBounds(bounds);
    }

    // Update legend if it exists
    if (heatmapLegend && heatmapLegend.update) {
        heatmapLegend.update(activeMetric, result.min, result.max);
    }
}

/* ── Heatmap legend control ──────────────────────────────────────────── */
const HeatmapLegend = L.Control.extend({
    options: { position: 'bottomright' },

    onAdd: function () {
        const container = L.DomUtil.create('div', 'heatmap-legend');
        L.DomEvent.disableClickPropagation(container);

        container.innerHTML =
            '<div class="heatmap-legend-title">Moisture (%)</div>' +
            '<div class="heatmap-legend-bar"></div>' +
            '<div class="heatmap-legend-labels">' +
                '<span class="heatmap-legend-min">0</span>' +
                '<span class="heatmap-legend-max">100</span>' +
            '</div>';

        this._container = container;
        return container;
    },

    update: function (metric, min, max) {
        if (!this._container) return;

        const title = this._container.querySelector('.heatmap-legend-title');
        const bar = this._container.querySelector('.heatmap-legend-bar');
        const minLabel = this._container.querySelector('.heatmap-legend-min');
        const maxLabel = this._container.querySelector('.heatmap-legend-max');

        if (metric === 'moisture') {
            title.textContent = 'Moisture (%)';
            bar.style.background = 'linear-gradient(to right, #E53E3E, #ED8936, #ECC94B, #48BB78)';
            minLabel.textContent = Math.round(min) + '%';
            maxLabel.textContent = Math.round(max) + '%';
        } else {
            title.textContent = 'Temperature (\u00B0C)';
            bar.style.background = 'linear-gradient(to right, #4299E1, #ECC94B, #E53E3E)';
            minLabel.textContent = min.toFixed(1) + '\u00B0';
            maxLabel.textContent = max.toFixed(1) + '\u00B0';
        }
    },

    show: function () {
        if (this._container) this._container.style.display = '';
    },

    hide: function () {
        if (this._container) this._container.style.display = 'none';
    },
});

function initHeatmapLegend() {
    if (!leafletMap || heatmapLegend) return;

    heatmapLegend = new HeatmapLegend();
    heatmapLegend.addTo(leafletMap);
    // Show by default since heatmap is on by default
    if (!heatmapEnabled) heatmapLegend.hide();
}

/* ── Metric toggle (now handled by MapControlPanel on the map) ──────── */

/* ── View toggle ─────────────────────────────────────────────────────── */
function setupViewToggle() {
    document.querySelectorAll('.view-toggle .view-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            if (view === activeView) return;

            // Update button states
            document.querySelectorAll('.view-toggle .view-toggle-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            activeView = view;

            const canvasWrap = document.querySelector('.canvas-wrap');
            const leafletWrap = document.getElementById('leafletMap');

            if (view === 'map') {
                canvasWrap.style.display = 'none';
                leafletWrap.style.display = 'block';
                if (!leafletMap) {
                    initLeafletMap();
                    // Fetch and render markers + heatmap immediately
                    fetchLatest().then(readings => {
                        updateLeafletMarkers(readings);
                        updateHeatmap(readings);
                    }).catch(() => {});
                } else {
                    leafletMap.invalidateSize();
                }
            } else {
                leafletWrap.style.display = 'none';
                canvasWrap.style.display = '';
                refreshDashboard();
            }
        });
    });
}

/* ── Refresh logic ────────────────────────────────────────────────────── */
async function refreshDashboard() {
    try {
        const readings = await fetchLatest();

        // Update canvas map
        if (activeView === 'canvas') {
            const canvas = document.getElementById('sensorMap');
            if (canvas) drawMap(canvas, readings);
        }

        // Update Leaflet map
        if (activeView === 'map') {
            updateLeafletMarkers(readings);
            updateHeatmap(readings);
        }

        // Update table
        updateTable(readings);
    } catch (err) {
        console.error('Failed to refresh dashboard:', err);
    }

    // Chart also rides the same 3s timer, tagged so the loading spinner
    // stays hidden and transient network blips don't flash the error card.
    loadHistory(currentRange, chartMetric, { isAutoRefresh: true });
}

/* ── Chart state overlays ─────────────────────────────────────────────── */
function showChartState(name) {
    ['loading', 'empty', 'error'].forEach(key => {
        const el = document.querySelector(`.chart-${key}`);
        if (!el) return;
        if (key === name) el.removeAttribute('hidden');
        else el.setAttribute('hidden', '');
    });
}

function hideChartStates() {
    ['loading', 'empty', 'error'].forEach(key => {
        document.querySelector(`.chart-${key}`)?.setAttribute('hidden', '');
    });
}

function setChartEmptyMessage(metric, range) {
    const el = document.querySelector('.chart-empty');
    if (!el) return;
    const r = RANGE_LABELS[range] || range;
    el.textContent = `No ${metric} readings in the last ${r}`;
}

/* ── Chart fetch ──────────────────────────────────────────────────────── */
async function loadHistory(range, metric, { isAutoRefresh = false } = {}) {
    // Livelock guard: if an auto fetch is already pending, don't stack another.
    if (isAutoRefresh && chartAbort) return;

    // User click always wins — abort any prior in-flight request.
    if (!isAutoRefresh && chartAbort) chartAbort.abort();

    if (!isAutoRefresh) showChartState('loading');

    const myController = new AbortController();
    chartAbort = myController;

    try {
        const resp = await fetch(`/api/sensor/history?range=${encodeURIComponent(range)}`, {
            signal: myController.signal,
        });
        // Stale-response race guard: a newer call may have overwritten chartAbort.
        if (myController !== chartAbort) return;

        if (!resp.ok) throw new Error(`API ${resp.status}`);
        const data = await resp.json();
        if (myController !== chartAbort) return;
        // A 200 with a non-array body is a malformed response — route it
        // through the error path instead of silently claiming "no readings".
        if (!Array.isArray(data)) throw new Error('Unexpected response shape');

        chartAbort = null;

        if (data.length === 0) {
            // On auto-refresh ticks keep the last good chart visible — a
            // transient empty window mid-session shouldn't wipe the chart.
            if (isAutoRefresh) return;
            setChartEmptyMessage(metric, range);
            showChartState('empty');
            if (historyChart) { historyChart.destroy(); historyChart = null; }
            return;
        }

        hideChartStates();
        renderChart(metric, data);
    } catch (err) {
        if (err.name === 'AbortError') {
            // Clear chartAbort only if this controller is still the "current"
            // one — normally a newer call already overwrote it, but if this
            // was the last pending fetch with no successor, the livelock guard
            // would otherwise block every future auto-tick.
            if (myController === chartAbort) chartAbort = null;
            return;
        }
        // Only this controller's failure matters.
        if (myController !== chartAbort) return;
        chartAbort = null;

        if (isAutoRefresh) {
            // Leave the last populated chart visible; silent log.
            console.warn('Chart auto-refresh failed:', err);
        } else {
            console.error('Failed to load history:', err);
            showChartState('error');
        }
    }
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refreshDashboard, REFRESH_MS);
}

/* ── Chart control handlers ───────────────────────────────────────────── */
function setupChartMetricButtons() {
    document.querySelectorAll('.chart-metric-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const newMetric = btn.dataset.metric;
            if (newMetric === chartMetric) return; // no-op on already-active

            document.querySelector('.chart-metric-btn.active')?.classList.remove('active');
            btn.classList.add('active');
            chartMetric = newMetric;

            loadHistory(currentRange, chartMetric);
        });
    });
}

function setupChartRangeButtons() {
    document.querySelectorAll('.chart-range-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const newRange = btn.dataset.range;
            if (newRange === currentRange) return; // no-op on already-active

            document.querySelector('.chart-range-btn.active')?.classList.remove('active');
            btn.classList.add('active');
            currentRange = newRange;

            loadHistory(currentRange, chartMetric);
        });
    });
}

function setupChartErrorRetry() {
    const btn = document.querySelector('.chart-error-retry');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        btn.disabled = true;
        try {
            await loadHistory(currentRange, chartMetric);
        } finally {
            btn.disabled = false;
        }
    });
}

/* ── Init ─────────────────────────────────────────────────────────────── */
function init() {
    // Initialize Leaflet map as the default view
    initLeafletMap();
    fetchLatest().then(readings => {
        updateLeafletMarkers(readings);
        updateHeatmap(readings);
        updateTable(readings);
    }).catch(() => {});

    setupChartMetricButtons();
    setupChartRangeButtons();
    setupChartErrorRetry();
    setupViewToggle();

    // Auto-refresh drives map, table, and chart on one 3s timer.
    startAutoRefresh();

    // First chart paint — shows the loading spinner until the fetch resolves.
    loadHistory(currentRange, chartMetric);

    // Redraw on resize
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => refreshDashboard(), 100);
    });
}

document.addEventListener('DOMContentLoaded', init);
