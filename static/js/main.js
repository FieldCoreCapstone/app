/* ── FieldCore Dashboard — Frontend Logic ─────────────────────────────── */

/* ── Constants ────────────────────────────────────────────────────────── */
const MOISTURE_COLOR = {
    low:     '#E53E3E',
    fair:    '#ED8936',
    good:    '#ECC94B',
    optimal: '#48BB78',
};

const NODE_R = 18;
const REFRESH_MS = 30000; // auto-refresh every 30s
const MOISTURE_MAX = 700; // raw capacitance max for normalization

// Map button labels to API range keys
const RANGE_MAP = {
    'Live':      null,
    '24 Hours':  '24h',
    '7 Days':    '7d',
    '1 Month':   '1m',
    '3 Months':  '3m',
    '1 Year':    '1y',
};

const CHART_COLORS = [
    '#48BB78', // green
    '#4299E1', // blue
    '#ED8936', // orange
    '#9F7AEA', // purple
    '#F56565', // red
    '#38B2AC', // teal
];

let historyChart = null;
let refreshTimer = null;
let currentRange = 'Live';

/* ── Moisture helpers ─────────────────────────────────────────────────── */
function normalizeMoisture(raw) {
    return Math.max(0, Math.min(100, Math.round((raw / MOISTURE_MAX) * 100)));
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

/* ── API helpers ──────────────────────────────────────────────────────── */
async function fetchLatest() {
    const resp = await fetch('/api/sensor/latest');
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

async function fetchHistory(range, nodeId) {
    let url = `/api/sensor/history?range=${range}`;
    if (nodeId) url += `&node_id=${encodeURIComponent(nodeId)}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

/* ── Coordinate normalization ─────────────────────────────────────────── */
function normalizeCoords(readings) {
    const xs = readings.map(r => r.x).filter(v => v != null);
    const ys = readings.map(r => r.y).filter(v => v != null);

    if (xs.length === 0 || ys.length === 0) return readings;

    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const xRange = xMax - xMin || 1;
    const yRange = yMax - yMin || 1;
    const pad = 0.1;

    return readings.map(r => ({
        ...r,
        nx: pad + (1 - 2 * pad) * (r.x - xMin) / xRange,
        ny: pad + (1 - 2 * pad) * (r.y - yMin) / yRange,
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
        const safeNodeId = escapeHtml(r.node_id || '');

        return `<tr>
            <td class="node-id">${safeNodeId}</td>
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
function renderChart(historyData) {
    const ctx = document.getElementById('historyChart');
    if (!ctx) return;

    // Group by node_id
    const byNode = {};
    historyData.forEach(row => {
        if (!byNode[row.node_id]) byNode[row.node_id] = [];
        byNode[row.node_id].push(row);
    });

    const nodeIds = Object.keys(byNode).sort();

    // Build datasets — one line per node for avg_moisture
    const datasets = nodeIds.map((nodeId, i) => {
        const rows = byNode[nodeId];
        return {
            label: nodeId,
            data: rows.map(r => ({
                x: r.period,
                y: normalizeMoisture(r.avg_moisture || 0),
            })),
            borderColor: CHART_COLORS[i % CHART_COLORS.length],
            backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '20',
            borderWidth: 2,
            pointRadius: 1,
            tension: 0.3,
            fill: true,
        };
    });

    if (historyChart) {
        historyChart.destroy();
    }

    historyChart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        padding: 12,
                        font: { size: 11 },
                    },
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            return `${ctx.dataset.label}: ${ctx.parsed.y}% moisture`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    type: 'category',
                    // Union of all periods across all nodes for correct alignment
                    labels: [...new Set(datasets.flatMap(ds => ds.data.map(d => d.x)))].sort(),
                    ticks: {
                        maxTicksLimit: 12,
                        font: { size: 10 },
                        maxRotation: 45,
                    },
                    grid: { display: false },
                },
                y: {
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Moisture %',
                        font: { size: 11 },
                    },
                    ticks: { font: { size: 10 } },
                },
            },
        },
    });
}

/* ── Refresh logic ────────────────────────────────────────────────────── */
async function refreshDashboard() {
    try {
        const readings = await fetchLatest();

        // Update map
        const canvas = document.getElementById('sensorMap');
        if (canvas) drawMap(canvas, readings);

        // Update table
        updateTable(readings);
    } catch (err) {
        console.error('Failed to refresh dashboard:', err);
    }
}

async function loadHistory(rangeKey) {
    try {
        const data = await fetchHistory(rangeKey);
        renderChart(data);
    } catch (err) {
        console.error('Failed to load history:', err);
    }
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refreshDashboard, REFRESH_MS);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

/* ── Time-range button handlers ───────────────────────────────────────── */
function setupTimeButtons() {
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Toggle active class
            document.querySelector('.time-btn.active')?.classList.remove('active');
            btn.classList.add('active');

            const label = btn.dataset.range;
            currentRange = label;
            const rangeKey = RANGE_MAP[label];

            if (rangeKey === null) {
                // "Live" mode: show latest data, enable auto-refresh
                refreshDashboard();
                startAutoRefresh();
            } else {
                // Historical mode: fetch history, stop auto-refresh
                stopAutoRefresh();
                loadHistory(rangeKey);
                refreshDashboard(); // still show latest in map+table
            }
        });
    });
}

/* ── Init ─────────────────────────────────────────────────────────────── */
function init() {
    const canvas = document.getElementById('sensorMap');
    if (canvas) {
        // Initial draw from server-rendered data
        try {
            const nodes = JSON.parse(canvas.dataset.nodes);
            drawMapFromNodes(canvas, nodes);
        } catch (e) {
            // If no initial data, fetch from API
            refreshDashboard();
        }
    }

    setupTimeButtons();

    // Start auto-refresh in "Live" mode
    startAutoRefresh();

    // Load default chart (7 day history)
    loadHistory('7d');

    // Redraw on resize
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => refreshDashboard(), 100);
    });
}

document.addEventListener('DOMContentLoaded', init);
